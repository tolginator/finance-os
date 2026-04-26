"""Tests for ETF classification and taxonomy service."""

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.application.contracts.household import AssetClass
from src.application.data_services.etf_service import (
    CATEGORY_MAP,
    Confidence,
    ETFOverride,
    ETFProfile,
    ETFService,
    OverrideStore,
    _extract_diagnostics,
    apply_override,
    classify_from_yahoo,
)

# ---------------------------------------------------------------------------
# Golden corpus — one representative ETF per canonical asset class
# ---------------------------------------------------------------------------

_AC = AssetClass
_C = Confidence

_GOLDEN_CORPUS: list[
    tuple[str, str, str, AssetClass, Confidence]
] = [
    ("SPY", "SPDR S&P 500 ETF", "Large Blend",
     _AC.US_EQUITY, _C.HIGH),
    ("IWM", "iShares Russell 2000 ETF", "Small Blend",
     _AC.US_EQUITY, _C.HIGH),
    ("VGK", "Vanguard FTSE Europe ETF", "Europe Stock",
     _AC.INTL_DEVELOPED, _C.HIGH),
    ("EFA", "iShares MSCI EAFE ETF", "Foreign Large Blend",
     _AC.INTL_DEVELOPED, _C.HIGH),
    ("VWO", "Vanguard FTSE EM ETF", "Diversified Emerging Mkts",
     _AC.EMERGING_MARKETS, _C.HIGH),
    ("SHY", "iShares 1-3Y Treasury", "Short Government",
     _AC.US_TREASURIES, _C.HIGH),
    ("TLT", "iShares 20+Y Treasury", "Long Government",
     _AC.US_TREASURIES, _C.HIGH),
    ("LQD", "iShares IG Corp Bond ETF", "Corporate Bond",
     _AC.IG_CORPORATE, _C.HIGH),
    ("HYG", "iShares HY Corp Bond ETF", "High Yield Bond",
     _AC.HIGH_YIELD, _C.HIGH),
    ("TIP", "iShares TIPS Bond ETF", "Inflation-Protected Bond",
     _AC.TIPS, _C.HIGH),
    ("VNQ", "Vanguard Real Estate ETF", "Real Estate",
     _AC.REAL_ASSETS, _C.HIGH),
    ("GLD", "SPDR Gold Shares", "Commodities Focused",
     _AC.REAL_ASSETS, _C.HIGH),
]


class TestClassifyFromYahoo:
    """Tests for the core classification logic."""

    @pytest.mark.parametrize(
        "ticker,name,category,expected_class,expected_confidence",
        _GOLDEN_CORPUS,
        ids=[c[0] for c in _GOLDEN_CORPUS],
    )
    def test_golden_corpus(
        self,
        ticker: str,
        name: str,
        category: str,
        expected_class: AssetClass,
        expected_confidence: Confidence,
    ) -> None:
        info = {
            "symbol": ticker,
            "longName": name,
            "category": category,
        }
        profile = classify_from_yahoo(info)
        assert profile.asset_class == expected_class
        assert profile.classification_confidence == expected_confidence
        assert profile.ticker == ticker

    def test_keyword_fallback_when_category_missing(self) -> None:
        info = {
            "symbol": "VXUS",
            "longName": "Vanguard Total International Stock ETF",
            "category": "",
        }
        profile = classify_from_yahoo(info)
        assert profile.asset_class == AssetClass.INTL_DEVELOPED
        assert profile.classification_confidence == Confidence.MEDIUM
        assert "keyword:" in profile.classification_rule

    def test_keyword_fallback_treasury(self) -> None:
        info = {
            "symbol": "GOVT",
            "longName": "iShares US Treasury Bond ETF",
            "category": "Some Unknown Category",
        }
        profile = classify_from_yahoo(info)
        assert profile.asset_class == AssetClass.US_TREASURIES

    def test_unclassified_when_no_match(self) -> None:
        info = {
            "symbol": "XYZ",
            "longName": "Exotic Leveraged Volatility Fund",
            "category": "Trading--Leveraged Equity",
        }
        profile = classify_from_yahoo(info)
        assert profile.asset_class is None
        assert profile.classification_confidence == Confidence.UNCLASSIFIED
        assert len(profile.warnings) > 0

    def test_diagnostic_extraction_large_growth(self) -> None:
        info = {
            "symbol": "VUG",
            "longName": "Vanguard Growth ETF",
            "category": "Large Growth",
        }
        profile = classify_from_yahoo(info)
        assert profile.cap_size == "large"
        assert profile.style == "growth"

    def test_diagnostic_extraction_foreign(self) -> None:
        info = {
            "symbol": "VEA",
            "longName": "Vanguard FTSE Developed Markets ETF",
            "category": "Foreign Large Blend",
        }
        profile = classify_from_yahoo(info)
        assert profile.geography == "international"
        assert profile.cap_size == "large"
        assert profile.style == "blend"

    def test_diagnostic_extraction_bond_duration(self) -> None:
        info = {
            "symbol": "IEF",
            "longName": "iShares 7-10 Year Treasury Bond ETF",
            "category": "Intermediate Government",
        }
        profile = classify_from_yahoo(info)
        assert profile.duration_bucket == "intermediate"

    def test_expense_ratio_parsed(self) -> None:
        info = {
            "symbol": "VTI",
            "longName": "Vanguard Total Stock Market ETF",
            "category": "Large Blend",
            "annualReportExpenseRatio": 0.0003,
        }
        profile = classify_from_yahoo(info)
        assert profile.expense_ratio == Decimal("0.0003")

    def test_aum_parsed(self) -> None:
        info = {
            "symbol": "SPY",
            "longName": "SPDR S&P 500 ETF",
            "category": "Large Blend",
            "totalAssets": 500000000000,
        }
        profile = classify_from_yahoo(info)
        assert profile.aum == Decimal("500000000000")

    def test_provenance_tracked(self) -> None:
        info = {
            "symbol": "SPY",
            "longName": "SPDR S&P 500 ETF",
            "category": "Large Blend",
        }
        profile = classify_from_yahoo(info)
        assert "asset_class" in profile.provenance
        assert profile.provenance["asset_class"].source == "yahoo"
        assert "name" in profile.provenance

    def test_inception_date_from_timestamp(self) -> None:
        info = {
            "symbol": "SPY",
            "longName": "SPDR S&P 500 ETF",
            "category": "Large Blend",
            "fundInceptionDate": 759024000,  # 1994-01-22
        }
        profile = classify_from_yahoo(info)
        assert profile.inception_date is not None
        assert profile.inception_date.year == 1994

    def test_empty_info_returns_minimal_profile(self) -> None:
        profile = classify_from_yahoo({})
        assert profile.ticker == ""
        assert profile.asset_class is None


class TestExtractDiagnostics:
    """Tests for diagnostic extraction from category strings."""

    def _base_profile(self) -> ETFProfile:
        return ETFProfile(ticker="TEST", name="Test ETF")

    def test_mid_cap_equity(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "Mid-Cap Blend")
        assert profile.cap_size == "mid"
        assert profile.style == "blend"

    def test_bond_category_skips_equity_diagnostics(self) -> None:
        """Intermediate Government should not set cap_size='mid'."""
        profile = self._base_profile()
        _extract_diagnostics(profile, "Intermediate Government")
        assert profile.cap_size == ""
        assert profile.duration_bucket == "intermediate"

    def test_corporate_bond_no_equity_diagnostics(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "Corporate Bond")
        assert profile.cap_size == ""
        assert profile.style == ""

    def test_geography_international(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "Foreign Large Blend")
        assert profile.geography == "international"
        assert profile.cap_size == "large"

    def test_geography_emerging(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "China Region")
        assert profile.geography == "emerging"

    def test_ex_japan_not_tagged_japan(self) -> None:
        """'Pacific/Asia ex-Japan Stk' should not set geography to japan."""
        profile = self._base_profile()
        _extract_diagnostics(profile, "Pacific/Asia ex-Japan Stk")
        assert profile.geography != "japan"

    def test_ex_china_not_tagged_emerging(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "EM ex-China")
        assert profile.geography != "emerging"

    def test_ex_europe_not_tagged_europe(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "World ex-Europe")
        assert profile.geography != "europe"

    def test_japan_stock_tagged_japan(self) -> None:
        """Positive case: 'Japan Stock' should set geography to japan."""
        profile = self._base_profile()
        _extract_diagnostics(profile, "Japan Stock")
        assert profile.geography == "japan"

    def test_europe_stock_tagged_europe(self) -> None:
        profile = self._base_profile()
        _extract_diagnostics(profile, "Europe Stock")
        assert profile.geography == "europe"


class TestOverrideModels:
    """Tests for override Pydantic models."""

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            ETFOverride(as_of=date.today(), mode="invalid")

    def test_replace_mode_accepted(self) -> None:
        override = ETFOverride(as_of=date.today(), mode="replace")
        assert override.mode == "replace"


class TestApplyOverride:
    """Tests for override application logic."""

    def _base_profile(self) -> ETFProfile:
        return ETFProfile(
            ticker="TEST",
            name="Test ETF",
            asset_class=AssetClass.US_EQUITY,
            classification_confidence=Confidence.MEDIUM,
            geography="US",
        )

    def test_replace_asset_class(self) -> None:
        profile = self._base_profile()
        override = ETFOverride(
            as_of=date.today(),
            asset_class=AssetClass.REAL_ASSETS,
        )
        result = apply_override(profile, override)
        assert result.asset_class == AssetClass.REAL_ASSETS
        assert result.provenance["asset_class"].source == "override"

    def test_replace_geography(self) -> None:
        profile = self._base_profile()
        override = ETFOverride(
            as_of=date.today(),
            geography="emerging",
        )
        result = apply_override(profile, override)
        assert result.geography == "emerging"

    def test_stale_override_warns(self) -> None:
        profile = self._base_profile()
        old_date = date.today() - timedelta(days=100)
        override = ETFOverride(
            as_of=old_date,
            asset_class=AssetClass.TIPS,
        )
        result = apply_override(profile, override)
        assert result.asset_class == AssetClass.TIPS
        assert any("days old" in w for w in result.warnings)
        assert result.classification_confidence == Confidence.MEDIUM

    def test_fresh_override_high_confidence(self) -> None:
        profile = self._base_profile()
        override = ETFOverride(
            as_of=date.today(),
            asset_class=AssetClass.TIPS,
        )
        result = apply_override(profile, override)
        assert result.classification_confidence == Confidence.HIGH

    def test_patch_mode_fills_gaps(self) -> None:
        profile = self._base_profile()
        profile.sector_focus = ""
        override = ETFOverride(
            as_of=date.today(),
            mode="patch",
            sector="technology",
        )
        result = apply_override(profile, override)
        assert result.sector_focus == "technology"

    def test_patch_mode_preserves_existing(self) -> None:
        profile = self._base_profile()
        profile.sector_focus = "healthcare"
        profile.duration_bucket = "intermediate"
        override = ETFOverride(
            as_of=date.today(),
            mode="patch",
            sector="technology",
            duration="long",
        )
        result = apply_override(profile, override)
        # Patch should NOT overwrite existing values
        assert result.sector_focus == "healthcare"
        assert result.duration_bucket == "intermediate"


class TestOverrideStore:
    """Tests for persistent override storage."""

    def test_load_empty_when_missing(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        data = store.load()
        assert len(data.overrides) == 0

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "overrides.json"
        store = OverrideStore(path=path)
        override = ETFOverride(
            as_of=date.today(),
            asset_class=AssetClass.TIPS,
        )
        store.set("TIP", override)
        loaded = store.get("TIP")
        assert loaded is not None
        assert loaded.asset_class == AssetClass.TIPS

    def test_ticker_uppercased(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        store.set("tip", ETFOverride(as_of=date.today()))
        assert store.get("TIP") is not None

    def test_remove(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        store.set("SPY", ETFOverride(as_of=date.today()))
        assert store.remove("SPY") is True
        assert store.get("SPY") is None
        assert store.remove("SPY") is False

    def test_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "overrides.json"
        path.write_text("not json!", encoding="utf-8")
        store = OverrideStore(path=path)
        data = store.load()
        assert len(data.overrides) == 0

    def test_schema_version_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "overrides.json"
        store = OverrideStore(path=path)
        store.set("SPY", ETFOverride(as_of=date.today()))
        raw = json.loads(path.read_text())
        assert raw["schema_version"] == 1

    def test_save_calls_fsync(self, tmp_path: Path) -> None:
        """Save must fsync the temp file before replacing target."""
        path = tmp_path / "overrides.json"
        store = OverrideStore(path=path)
        with patch("src.application.data_services.etf_service.os.fsync") as mock_fsync:
            store.set("SPY", ETFOverride(as_of=date.today()))
        assert mock_fsync.call_count >= 1


class TestETFService:
    """Tests for the main service class."""

    def _mock_info(
        self,
        ticker: str = "SPY",
        name: str = "SPDR S&P 500 ETF",
        category: str = "Large Blend",
    ) -> dict:
        return {
            "symbol": ticker,
            "longName": name,
            "category": category,
            "quoteType": "ETF",
            "annualReportExpenseRatio": 0.0009,
            "totalAssets": 500_000_000_000,
            "fundFamily": "SPDR State Street Global Advisors",
        }

    def test_classify_sync_caches(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = self._mock_info()

        _yf = "src.application.data_services.etf_service.yf.Ticker"
        with patch(_yf, return_value=mock_ticker) as yf_mock:
            r1 = service.classify_sync("SPY")
            r2 = service.classify_sync("SPY")

        assert r1.profile.asset_class == AssetClass.US_EQUITY
        assert r1.served_from_cache is False
        assert r2.served_from_cache is True
        yf_mock.assert_called_once_with("SPY")

    def test_classify_sync_applies_override(
        self, tmp_path: Path
    ) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        store.set(
            "XYZ",
            ETFOverride(
                as_of=date.today(),
                asset_class=AssetClass.TIPS,
            ),
        )
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = self._mock_info(
            ticker="XYZ", category="Unknown Category"
        )

        with patch("src.application.data_services.etf_service.yf.Ticker", return_value=mock_ticker):
            result = service.classify_sync("XYZ")

        assert result.profile.asset_class == AssetClass.TIPS

    def test_override_change_reflects_on_cached_profile(
        self, tmp_path: Path
    ) -> None:
        """Overrides applied after caching should be visible immediately."""
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = self._mock_info(ticker="SPY")
        yf_path = "src.application.data_services.etf_service.yf.Ticker"

        with patch(yf_path, return_value=mock_ticker):
            r1 = service.classify_sync("SPY")

        assert r1.profile.asset_class == AssetClass.US_EQUITY

        # Add override after profile is cached
        store.set(
            "SPY",
            ETFOverride(
                as_of=date.today(),
                asset_class=AssetClass.TIPS,
            ),
        )

        with patch(yf_path, return_value=mock_ticker):
            r2 = service.classify_sync("SPY")

        # Override should be visible even on cached result
        assert r2.profile.asset_class == AssetClass.TIPS

    def test_classify_sync_handles_yfinance_failure(
        self, tmp_path: Path
    ) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        with patch(
            "src.application.data_services.etf_service.yf.Ticker",
            side_effect=Exception("network error"),
        ):
            result = service.classify_sync("FAIL")

        assert result.profile.ticker == "FAIL"
        assert len(result.profile.warnings) > 0

    def test_classify_sync_handles_empty_info(
        self, tmp_path: Path
    ) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with patch("src.application.data_services.etf_service.yf.Ticker", return_value=mock_ticker):
            result = service.classify_sync("EMPTY")

        assert result.profile.ticker == "EMPTY"
        assert len(result.profile.warnings) > 0

    def test_rejects_non_etf_quote_type(
        self, tmp_path: Path
    ) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = {
            "symbol": "AAPL",
            "quoteType": "EQUITY",
            "longName": "Apple Inc.",
        }

        _yf = "src.application.data_services.etf_service.yf.Ticker"
        with patch(_yf, return_value=mock_ticker):
            result = service.classify_sync("AAPL")

        assert result.profile.asset_class is None
        assert any("not ETF" in w for w in result.profile.warnings)

    @pytest.mark.asyncio
    async def test_classify_async(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = self._mock_info()

        with patch("src.application.data_services.etf_service.yf.Ticker", return_value=mock_ticker):
            result = await service.classify("SPY")

        assert result.profile.asset_class == AssetClass.US_EQUITY

    @pytest.mark.asyncio
    async def test_classify_multiple(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(override_store=store)

        def make_ticker(symbol: str) -> MagicMock:
            mock = MagicMock()
            if symbol == "SPY":
                mock.info = self._mock_info("SPY", "SPDR S&P 500", "Large Blend")
            elif symbol == "TLT":
                mock.info = self._mock_info("TLT", "iShares 20+ Year Treasury", "Long Government")
            else:
                mock.info = {}
            return mock

        with patch("src.application.data_services.etf_service.yf.Ticker", side_effect=make_ticker):
            results = await service.classify_multiple(["SPY", "TLT"])

        assert results["SPY"].profile.asset_class == AssetClass.US_EQUITY
        assert results["TLT"].profile.asset_class == AssetClass.US_TREASURIES

    def test_cache_expiry(self, tmp_path: Path) -> None:
        store = OverrideStore(path=tmp_path / "overrides.json")
        service = ETFService(cache_ttl=10.0, override_store=store)

        mock_ticker = MagicMock()
        mock_ticker.info = self._mock_info()

        with patch("src.application.data_services.etf_service.yf.Ticker", return_value=mock_ticker):
            service.classify_sync("SPY")

        # Manually expire by manipulating cache entry
        for key in service._cache:
            ts, resp = service._cache[key]
            service._cache[key] = (ts - 20, resp)

        mock_ticker2 = MagicMock()
        mock_ticker2.info = self._mock_info()
        with patch(
            "src.application.data_services.etf_service.yf.Ticker",
            return_value=mock_ticker2,
        ) as yf_mock:
            r2 = service.classify_sync("SPY")
            assert r2.served_from_cache is False
            yf_mock.assert_called_once()


class TestCategoryMapCoverage:
    """Verify the category map has expected coverage."""

    def test_all_asset_classes_represented(self) -> None:
        """Every canonical AssetClass should appear in CATEGORY_MAP."""
        mapped_classes = {v[0] for v in CATEGORY_MAP.values()}
        for ac in AssetClass:
            assert ac in mapped_classes, (
                f"{ac} not represented in CATEGORY_MAP"
            )
