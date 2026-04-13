"""Digest service — wraps research pipeline for typed digest execution.

When no sources are provided, automatically fetches live data:
- SEC EDGAR filings for each ticker (filing_analyst)
- FRED macro indicators (macro_regime)
"""

from datetime import date
from decimal import Decimal

from src.agents.filing_analyst import Filing, get_company_filings, resolve_cik
from src.agents.macro_regime import (
    MACRO_INDICATORS,
    classify_regime,
    fetch_fred_series,
    parse_observations,
)
from src.application.config import AppConfig
from src.application.contracts.agents import RunDigestRequest, RunDigestResponse
from src.pipelines.research_digest import (
    DataSource,
    PipelineConfig,
    ResearchPipeline,
)


def _filing_sentiment(filing: Filing) -> Decimal:
    """Estimate sentiment from a filing's characteristics.

    10-K and 10-Q filings are neutral by default. Amendments (10-K/A)
    or 8-K filings suggest material events and get a stronger signal.
    """
    form = filing.form_type.upper()
    if "8-K" in form:
        return Decimal("-0.3")
    if "/A" in form:
        return Decimal("-0.2")
    return Decimal("0.1")


def _regime_sentiment(regime: str) -> Decimal:
    """Map macro regime to a sentiment score."""
    mapping = {
        "EXPANSION": Decimal("0.5"),
        "CONTRACTION": Decimal("-0.6"),
        "TRANSITION": Decimal("-0.1"),
    }
    return mapping.get(regime, Decimal("0"))


def _fetch_filing_sources(tickers: list[str]) -> list[DataSource]:
    """Fetch recent filings from EDGAR for each ticker."""
    today = date.today().isoformat()
    sources: list[DataSource] = []

    for ticker in tickers:
        cik = resolve_cik(ticker)
        if not cik:
            continue
        filings = get_company_filings(cik, ["10-K", "10-Q", "8-K"])
        for filing in filings[:3]:
            sources.append(DataSource(
                source_type="edgar",
                ticker=ticker,
                date=filing.filing_date or today,
                content=(
                    f"{filing.form_type} filed {filing.filing_date}: "
                    f"{filing.description or filing.primary_document}"
                ),
                metadata={
                    "form_type": filing.form_type,
                    "accession": filing.accession_number,
                    "cik": cik,
                    "sentiment": str(_filing_sentiment(filing)),
                },
            ))
    return sources


def _fetch_macro_source(fred_api_key: str) -> DataSource | None:
    """Fetch macro regime from FRED and return as a data source."""
    if not fred_api_key:
        return None

    today = date.today().isoformat()
    indicator_ids = list(MACRO_INDICATORS.keys())[:3]
    all_readings = {}

    for series_id in indicator_ids:
        desc = MACRO_INDICATORS.get(series_id, series_id)
        observations = fetch_fred_series(series_id, fred_api_key, limit=6)
        all_readings[series_id] = parse_observations(observations, desc)

    regime = classify_regime(all_readings)
    if not regime:
        return None

    return DataSource(
        source_type="macro",
        ticker="MACRO",
        date=today,
        content=f"Macro regime: {regime}",
        metadata={
            "regime": regime,
            "sentiment": str(_regime_sentiment(regime)),
        },
    )


class DigestService:
    """Runs the research digest pipeline with typed contracts.

    When no sources are provided, automatically fetches live data
    from SEC EDGAR and FRED for each ticker in the request.
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or AppConfig()

    async def run_digest(self, request: RunDigestRequest) -> RunDigestResponse:
        """Execute the research digest pipeline.

        Args:
            request: Digest request with tickers, sources, and config.

        Returns:
            RunDigestResponse with digest summary and metrics.
        """
        pipeline_config = PipelineConfig(
            tickers=request.tickers,
            lookback_days=request.lookback_days,
            alert_threshold=request.alert_threshold,
        )
        pipeline = ResearchPipeline(pipeline_config)

        # Use provided sources or auto-fetch
        if request.sources:
            for source_dict in request.sources:
                source = DataSource(
                    source_type=source_dict.get("source_type", ""),
                    ticker=source_dict.get("ticker", ""),
                    date=source_dict.get("date", ""),
                    content=source_dict.get("content", ""),
                    metadata=source_dict.get("metadata", {}),
                )
                pipeline.add_source(source)
        else:
            self._auto_fetch(pipeline, request.tickers)

        digest = pipeline.run()

        entry_lines = []
        for entry in digest.entries:
            material_tag = " [MATERIAL]" if entry.material else ""
            entry_lines.append(
                f"- {entry.ticker}: {entry.source}{material_tag} "
                f"(sentiment={entry.sentiment:.2f})"
            )

        alert_lines = [f"- [{a.severity}] {a.ticker}: {a.message}" for a in digest.alerts]

        content_parts = [f"Research Digest — {len(digest.entries)} entries"]
        if entry_lines:
            content_parts.append("\n".join(entry_lines))
        if alert_lines:
            content_parts.append(f"\nAlerts ({len(alert_lines)}):")
            content_parts.append("\n".join(alert_lines))

        return RunDigestResponse(
            ticker_count=len(request.tickers),
            entry_count=len(digest.entries),
            alert_count=len(digest.alerts),
            material_count=sum(1 for e in digest.entries if e.material),
            content="\n".join(content_parts),
        )

    def _auto_fetch(
        self, pipeline: ResearchPipeline, tickers: list[str]
    ) -> None:
        """Automatically fetch data sources for tickers."""
        # Fetch EDGAR filings per ticker
        filing_sources = _fetch_filing_sources(tickers)
        pipeline.add_sources(filing_sources)

        # Fetch macro regime (global, not per-ticker)
        macro_source = _fetch_macro_source(self._config.fred_api_key)
        if macro_source:
            pipeline.add_source(macro_source)
