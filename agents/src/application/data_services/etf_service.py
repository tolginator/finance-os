"""ETF classification and taxonomy service.

Maps ETF tickers to canonical asset classes and diagnostic attributes
using Yahoo Finance data with manual override support. All yfinance
calls are dispatched to threads to avoid blocking async event loops.
"""

import asyncio
import json
import logging
import os
import tempfile
import threading
import time
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

import yfinance as yf
from pydantic import BaseModel, Field, field_validator

from src.application.config import CONFIG_DIR
from src.application.contracts.household import AssetClass

logger = logging.getLogger(__name__)

OVERRIDES_FILE = CONFIG_DIR / "etf-overrides.json"
_OVERRIDES_SCHEMA_VERSION = 1
_STALE_OVERRIDE_DAYS = 90


# ---------------------------------------------------------------------------
# Classification confidence
# ---------------------------------------------------------------------------


class Confidence(StrEnum):
    """How confident the classification is."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCLASSIFIED = "unclassified"


# ---------------------------------------------------------------------------
# Category → AssetClass mapping
# ---------------------------------------------------------------------------

# Maps yfinance category strings to (AssetClass, Confidence).
# Categories not in this map get heuristic fallback.
CATEGORY_MAP: dict[str, tuple[AssetClass, Confidence]] = {
    # US Equity
    "Large Blend": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Large Growth": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Large Value": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Mid-Cap Blend": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Mid-Cap Growth": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Mid-Cap Value": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Small Blend": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Small Growth": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Small Value": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Technology": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Health": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Financial": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Real Estate": (AssetClass.REAL_ASSETS, Confidence.HIGH),
    "Communications": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Utilities": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Energy": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Industrials": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Consumer Cyclical": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Consumer Defensive": (AssetClass.US_EQUITY, Confidence.HIGH),
    "Basic Materials": (AssetClass.US_EQUITY, Confidence.HIGH),
    # International Developed
    "Foreign Large Blend": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Foreign Large Growth": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Foreign Large Value": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Foreign Small/Mid Blend": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Foreign Small/Mid Growth": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Foreign Small/Mid Value": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Europe Stock": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Japan Stock": (AssetClass.INTL_DEVELOPED, Confidence.HIGH),
    "Pacific/Asia ex-Japan Stk": (AssetClass.INTL_DEVELOPED, Confidence.MEDIUM),
    # Emerging Markets
    "Diversified Emerging Mkts": (AssetClass.EMERGING_MARKETS, Confidence.HIGH),
    "China Region": (AssetClass.EMERGING_MARKETS, Confidence.HIGH),
    "India Equity": (AssetClass.EMERGING_MARKETS, Confidence.HIGH),
    "Latin America Stock": (AssetClass.EMERGING_MARKETS, Confidence.HIGH),
    # US Treasuries
    "Long Government": (AssetClass.US_TREASURIES, Confidence.HIGH),
    "Intermediate Government": (AssetClass.US_TREASURIES, Confidence.HIGH),
    "Short Government": (AssetClass.US_TREASURIES, Confidence.HIGH),
    "Ultrashort Bond": (AssetClass.US_TREASURIES, Confidence.MEDIUM),
    # IG Corporate
    "Corporate Bond": (AssetClass.IG_CORPORATE, Confidence.HIGH),
    "Intermediate Core Bond": (AssetClass.IG_CORPORATE, Confidence.MEDIUM),
    "Intermediate Core-Plus Bond": (AssetClass.IG_CORPORATE, Confidence.MEDIUM),
    "Long-Term Bond": (AssetClass.IG_CORPORATE, Confidence.MEDIUM),
    "Short-Term Bond": (AssetClass.IG_CORPORATE, Confidence.MEDIUM),
    # High Yield
    "High Yield Bond": (AssetClass.HIGH_YIELD, Confidence.HIGH),
    # TIPS
    "Inflation-Protected Bond": (AssetClass.TIPS, Confidence.HIGH),
    # Real Assets
    "Commodities Broad Basket": (AssetClass.REAL_ASSETS, Confidence.HIGH),
    "Commodities Focused": (AssetClass.REAL_ASSETS, Confidence.HIGH),
    "Natural Resources": (AssetClass.REAL_ASSETS, Confidence.HIGH),
    "Global Real Estate": (AssetClass.REAL_ASSETS, Confidence.HIGH),
    # Cash / Money Market
    "Money Market-Taxable": (AssetClass.CASH_MONEY_MARKET, Confidence.HIGH),
    "Money Market-Tax-Free": (AssetClass.CASH_MONEY_MARKET, Confidence.HIGH),
}

# Keyword fallbacks when category is missing or unknown
_KEYWORD_RULES: list[tuple[list[str], AssetClass, Confidence]] = [
    (
        ["treasury", "govt", "government bond"],
        AssetClass.US_TREASURIES,
        Confidence.MEDIUM,
    ),
    (["tips", "inflation"], AssetClass.TIPS, Confidence.MEDIUM),
    (["high yield", "junk"], AssetClass.HIGH_YIELD, Confidence.MEDIUM),
    (
        ["corporate bond", "investment grade"],
        AssetClass.IG_CORPORATE,
        Confidence.MEDIUM,
    ),
    (["emerging", "emerging markets"], AssetClass.EMERGING_MARKETS, Confidence.MEDIUM),
    (
        ["international", "foreign", "ex-us", "world ex", "eafe"],
        AssetClass.INTL_DEVELOPED,
        Confidence.MEDIUM,
    ),
    (
        ["reit", "real estate", "commodity", "gold", "silver"],
        AssetClass.REAL_ASSETS,
        Confidence.MEDIUM,
    ),
    (
        ["money market", "cash", "ultra-short"],
        AssetClass.CASH_MONEY_MARKET,
        Confidence.MEDIUM,
    ),
    (
        ["s&p 500", "total market", "russell", "nasdaq", "dow jones"],
        AssetClass.US_EQUITY,
        Confidence.MEDIUM,
    ),
]


# ---------------------------------------------------------------------------
# ETF Profile model
# ---------------------------------------------------------------------------


class FieldProvenance(BaseModel):
    """Tracks where a field's value came from."""

    source: str = Field(description="'yahoo', 'override', or 'inferred'")
    as_of: date | None = None
    confidence: Confidence = Confidence.HIGH


class ETFProfile(BaseModel):
    """Classification and metadata for a single ETF."""

    ticker: str
    name: str = ""
    asset_class: AssetClass | None = None
    classification_confidence: Confidence = Confidence.UNCLASSIFIED
    classification_rule: str = ""

    # Diagnostic attributes
    category: str = ""
    expense_ratio: Decimal | None = None
    fund_family: str = ""
    inception_date: date | None = None
    aum: Decimal | None = None

    # Diagnostic breakdown (optional)
    cap_size: str = ""
    style: str = ""
    sector_focus: str = ""
    geography: str = "US"
    duration_bucket: str = ""
    credit_quality: str = ""

    # Field provenance
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)

    # Warnings accumulated during classification
    warnings: list[str] = Field(default_factory=list)


class ETFProfileResponse(BaseModel):
    """Wrapper for an ETF profile with freshness metadata."""

    profile: ETFProfile
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    served_from_cache: bool = False


# ---------------------------------------------------------------------------
# Override models
# ---------------------------------------------------------------------------


class ETFOverride(BaseModel):
    """Manual override for a single ETF's classification."""

    asset_class: AssetClass | None = None
    sector: str | None = None
    geography: str | None = None
    duration: str | None = None
    credit_quality: str | None = None
    as_of: date
    mode: str = "replace"

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("replace", "patch"):
            raise ValueError("mode must be 'replace' or 'patch'")
        return v


class OverridesFile(BaseModel):
    """Schema for etf-overrides.json."""

    schema_version: int = _OVERRIDES_SCHEMA_VERSION
    overrides: dict[str, ETFOverride] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Override store
# ---------------------------------------------------------------------------


class OverrideStore:
    """Loads/saves ETF overrides from persistent storage.

    Uses a threading lock for concurrent write safety and fsync
    for durability before replacing the target file. Thread-safe
    public methods are `get`, `set`, and `remove`. The `_save`
    helper is private and always called under the lock.
    """

    def __init__(self, path: Path = OVERRIDES_FILE) -> None:
        self._path = path
        self._lock = threading.Lock()

    def load(self) -> OverridesFile:
        """Load overrides from disk. Returns empty on missing/corrupt file."""
        if not self._path.exists():
            return OverridesFile()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return OverridesFile.model_validate(raw)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("Corrupt overrides file %s: %s", self._path, exc)
            return OverridesFile()

    def _save(self, data: OverridesFile) -> None:
        """Atomic write to disk with fsync for durability."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = data.model_dump_json(indent=2).encode("utf-8")
        fd = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        tmp_fd, tmp_path = fd[0], Path(fd[1])
        try:
            os.write(tmp_fd, content)
            os.fsync(tmp_fd)
        finally:
            os.close(tmp_fd)
        os.chmod(str(tmp_path), 0o600)
        tmp_path.replace(self._path)
        # Best-effort fsync of parent directory to persist the rename.
        # Some platforms/filesystems do not support this.
        dir_fd: int | None = None
        try:
            dir_fd = os.open(str(self._path.parent), os.O_RDONLY)
            os.fsync(dir_fd)
        except OSError as exc:
            logger.warning(
                "Could not fsync parent directory %s: %s",
                self._path.parent,
                exc,
            )
        finally:
            if dir_fd is not None:
                os.close(dir_fd)

    def get(self, ticker: str) -> ETFOverride | None:
        """Get override for a single ticker."""
        with self._lock:
            data = self.load()
            return data.overrides.get(ticker.upper())

    def set(self, ticker: str, override: ETFOverride) -> None:
        """Set override for a single ticker."""
        with self._lock:
            data = self.load()
            data.overrides[ticker.upper()] = override
            self._save(data)

    def remove(self, ticker: str) -> bool:
        """Remove override. Returns True if existed."""
        with self._lock:
            data = self.load()
            removed = data.overrides.pop(ticker.upper(), None) is not None
            if removed:
                self._save(data)
            return removed


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def _safe_decimal(val: object) -> Decimal | None:
    """Parse a value to Decimal, returning None on failure."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def classify_from_yahoo(info: dict[str, object]) -> ETFProfile:
    """Build an ETFProfile from a yfinance info dict.

    Uses category mapping first, then keyword fallback on fund name.
    """
    ticker = str(info.get("symbol", "")).upper()
    name = str(info.get("longName") or info.get("shortName") or "")
    category = str(info.get("category") or "")
    fund_family = str(info.get("fundFamily") or "")

    profile = ETFProfile(
        ticker=ticker,
        name=name,
        category=category,
        fund_family=fund_family,
        expense_ratio=_safe_decimal(info.get("annualReportExpenseRatio")),
        aum=_safe_decimal(info.get("totalAssets")),
    )

    # Parse inception date
    fund_inception = info.get("fundInceptionDate")
    if fund_inception:
        try:
            if isinstance(fund_inception, (int, float)):
                profile.inception_date = datetime.fromtimestamp(
                    fund_inception, tz=UTC
                ).date()
            else:
                profile.inception_date = date.fromisoformat(str(fund_inception))
        except (ValueError, OSError):
            pass

    # Parse diagnostic attributes from category
    _extract_diagnostics(profile, category)

    # Provenance for yahoo-sourced fields
    today = date.today()
    for field_name in ("name", "category", "expense_ratio", "fund_family", "aum"):
        profile.provenance[field_name] = FieldProvenance(
            source="yahoo", as_of=today
        )

    # Step 1: Try direct category mapping
    if category and category in CATEGORY_MAP:
        ac, conf = CATEGORY_MAP[category]
        profile.asset_class = ac
        profile.classification_confidence = conf
        profile.classification_rule = f"category_map:{category}"
        profile.provenance["asset_class"] = FieldProvenance(
            source="yahoo", as_of=today, confidence=conf
        )
        return profile

    # Step 2: Keyword fallback on name + category
    search_text = f"{name} {category}".lower()
    for keywords, ac, conf in _KEYWORD_RULES:
        if any(kw in search_text for kw in keywords):
            profile.asset_class = ac
            profile.classification_confidence = conf
            profile.classification_rule = f"keyword:{keywords[0]}"
            profile.provenance["asset_class"] = FieldProvenance(
                source="inferred", as_of=today, confidence=conf
            )
            return profile

    # Step 3: Unclassified
    profile.classification_confidence = Confidence.UNCLASSIFIED
    profile.classification_rule = "none"
    profile.warnings.append(
        f"Could not classify {ticker} (category='{category}'). "
        "Manual override recommended."
    )
    return profile


def _extract_diagnostics(profile: ETFProfile, category: str) -> None:
    """Extract diagnostic attributes from a category string.

    May populate `cap_size`, `style`, `geography`, and
    `duration_bucket` on the provided profile when those hints are
    present in the category text.
    """
    cat_lower = category.lower()

    # Bond categories should not get equity-style diagnostics.
    _bond_hints = (
        "bond", "government", "treasury", "corporate", "high yield",
        "inflation", "money market", "ultrashort",
    )
    is_bond = any(h in cat_lower for h in _bond_hints)

    if not is_bond:
        if "large" in cat_lower:
            profile.cap_size = "large"
        elif "mid-cap" in cat_lower or "mid cap" in cat_lower:
            profile.cap_size = "mid"
        elif "small" in cat_lower:
            profile.cap_size = "small"

        if "growth" in cat_lower:
            profile.style = "growth"
        elif "value" in cat_lower:
            profile.style = "value"
        elif "blend" in cat_lower:
            profile.style = "blend"

    if "foreign" in cat_lower or "international" in cat_lower:
        profile.geography = "international"
    elif "emerging" in cat_lower:
        profile.geography = "emerging"
    elif "europe" in cat_lower:
        profile.geography = "europe"
    elif "japan" in cat_lower:
        profile.geography = "japan"
    elif "china" in cat_lower or "india" in cat_lower:
        profile.geography = "emerging"
    elif "latin" in cat_lower:
        profile.geography = "emerging"

    if "short" in cat_lower:
        profile.duration_bucket = "short"
    elif "intermediate" in cat_lower:
        profile.duration_bucket = "intermediate"
    elif "long" in cat_lower:
        profile.duration_bucket = "long"


def apply_override(
    profile: ETFProfile, override: ETFOverride
) -> ETFProfile:
    """Apply a manual override to an ETF profile.

    In 'replace' mode, provided override fields replace provider values.
    In 'patch' mode, override fields are used to fill provider gaps, except
    `asset_class`, which is treated as authoritative and replaces any
    existing provider classification when supplied. Geography also treats a
    default "US" value as a gap that a patch override may replace.
    """
    today = date.today()
    stale = (today - override.as_of).days > _STALE_OVERRIDE_DAYS
    if stale:
        profile.warnings.append(
            f"Override for {profile.ticker} is {(today - override.as_of).days} "
            f"days old (as_of={override.as_of}). Consider updating."
        )

    prov = FieldProvenance(
        source="override",
        as_of=override.as_of,
        confidence=Confidence.HIGH if not stale else Confidence.MEDIUM,
    )

    if override.mode == "replace":
        if override.asset_class is not None:
            profile.asset_class = override.asset_class
            profile.classification_confidence = prov.confidence
            profile.classification_rule = "override:replace"
            profile.provenance["asset_class"] = prov
        if override.sector is not None:
            profile.sector_focus = override.sector
            profile.provenance["sector_focus"] = prov
        if override.geography is not None:
            profile.geography = override.geography
            profile.provenance["geography"] = prov
        if override.duration is not None:
            profile.duration_bucket = override.duration
            profile.provenance["duration_bucket"] = prov
        if override.credit_quality is not None:
            profile.credit_quality = override.credit_quality
            profile.provenance["credit_quality"] = prov
    else:
        # Patch: override fills gaps only (except asset_class always wins)
        if override.asset_class is not None:
            profile.asset_class = override.asset_class
            profile.classification_confidence = prov.confidence
            profile.classification_rule = "override:patch"
            profile.provenance["asset_class"] = prov
        if override.sector is not None and not profile.sector_focus:
            profile.sector_focus = override.sector
            profile.provenance["sector_focus"] = prov
        if override.geography is not None and profile.geography == "US":
            profile.geography = override.geography
            profile.provenance["geography"] = prov
        if override.duration is not None and not profile.duration_bucket:
            profile.duration_bucket = override.duration
            profile.provenance["duration_bucket"] = prov
        if (
            override.credit_quality is not None
            and not profile.credit_quality
        ):
            profile.credit_quality = override.credit_quality
            profile.provenance["credit_quality"] = prov

    return profile


# ---------------------------------------------------------------------------
# ETF Service
# ---------------------------------------------------------------------------


class ETFService:
    """Classifies ETFs using Yahoo Finance with manual override support.

    All yfinance calls dispatched to threads. Results cached per-ticker.
    """

    _MAX_CONCURRENT_CLASSIFY = 10

    def __init__(
        self,
        cache_ttl: float = 3600.0,
        override_store: OverrideStore | None = None,
    ) -> None:
        self._cache: dict[str, tuple[float, ETFProfileResponse]] = {}
        self._cache_ttl = cache_ttl
        self._cache_lock = threading.Lock()
        self._override_store = override_store or OverrideStore()

    def classify_sync(self, ticker: str) -> ETFProfileResponse:
        """Classify an ETF synchronously (blocking yfinance call)."""
        ticker = ticker.upper()

        # Check cache for the provider-derived profile, then apply the
        # latest override on a copy so override changes are visible
        # immediately without mutating the cached base result.
        cached = self._cache_get(ticker)
        if cached is not None:
            profile = cached.profile.model_copy(deep=True)
            override = self._override_store.get(ticker)
            if override:
                profile = apply_override(profile, override)
            return cached.model_copy(
                deep=True,
                update={"profile": profile, "served_from_cache": True},
            )

        # Fetch from Yahoo and cache the provider-derived profile only.
        profile = self._fetch_and_classify(ticker)
        base_response = ETFProfileResponse(profile=profile)
        self._cache_put(ticker, base_response)

        # Apply override if present to a copy so the cache remains the
        # unmodified provider-derived result.
        effective_profile = profile.model_copy(deep=True)
        override = self._override_store.get(ticker)
        if override:
            effective_profile = apply_override(effective_profile, override)

        return ETFProfileResponse(profile=effective_profile)

    async def classify(self, ticker: str) -> ETFProfileResponse:
        """Classify an ETF asynchronously (thread-dispatched)."""
        return await asyncio.to_thread(self.classify_sync, ticker)

    async def classify_multiple(
        self, tickers: list[str]
    ) -> dict[str, ETFProfileResponse]:
        """Classify multiple ETFs concurrently (bounded concurrency)."""
        sem = asyncio.Semaphore(self._MAX_CONCURRENT_CLASSIFY)
        upper_tickers = [t.upper() for t in tickers]

        async def _limited(t: str) -> ETFProfileResponse:
            async with sem:
                return await self.classify(t)

        tasks = [asyncio.create_task(_limited(t)) for t in upper_tickers]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        results: dict[str, ETFProfileResponse] = {}
        for ticker, result in zip(upper_tickers, gathered, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to classify %s: %s", ticker, result
                )
                results[ticker] = ETFProfileResponse(
                    profile=ETFProfile(
                        ticker=ticker,
                        warnings=[f"Classification failed: {result}"],
                    )
                )
            else:
                results[ticker] = result
        return results

    def _fetch_and_classify(self, ticker: str) -> ETFProfile:
        """Fetch yfinance info and classify."""
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info or {}
        except Exception as exc:
            logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
            return ETFProfile(
                ticker=ticker,
                warnings=[f"Yahoo Finance fetch failed: {exc}"],
            )

        if not info:
            return ETFProfile(
                ticker=ticker,
                warnings=["No data returned from Yahoo Finance"],
            )

        quote_type = info.get("quoteType")
        qt_upper = (
            quote_type.strip().upper()
            if isinstance(quote_type, str)
            else None
        )
        if qt_upper != "ETF":
            warning = (
                f"quoteType is '{quote_type}', not ETF"
                if quote_type is not None
                else "quoteType missing; cannot confirm ETF"
            )
            return ETFProfile(ticker=ticker, warnings=[warning])

        return classify_from_yahoo(info)

    # -- Cache helpers (thread-safe) --

    def _cache_get(self, key: str) -> ETFProfileResponse | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, resp = entry
            if time.monotonic() - ts > self._cache_ttl:
                self._cache.pop(key, None)
                return None
            copy = resp.model_copy(deep=True)
            copy.served_from_cache = True
            return copy

    def _cache_put(self, key: str, resp: ETFProfileResponse) -> None:
        with self._cache_lock:
            self._cache[key] = (
                time.monotonic(),
                resp.model_copy(deep=True),
            )
