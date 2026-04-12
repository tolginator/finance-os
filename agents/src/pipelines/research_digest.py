"""Research digest pipeline for orchestrating data ingestion and agent analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class PipelineConfig:
    """Configuration for the research pipeline."""

    tickers: list[str]
    lookback_days: int = 7
    alert_threshold: Decimal = Decimal("0.5")


@dataclass
class DataSource:
    """A raw data source ingested into the pipeline."""

    source_type: str  # "edgar", "transcript", "market_data"
    ticker: str
    date: str  # ISO date
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DigestEntry:
    """A single analyzed entry in the research digest."""

    ticker: str
    source: str  # which agent/analysis produced this
    summary: str
    sentiment: Decimal  # -1 to 1
    material: bool  # is this a material change?
    timestamp: str


@dataclass
class Alert:
    """An alert generated from a material digest entry."""

    ticker: str
    category: str  # "earnings", "filing", "macro", "thesis"
    severity: str  # "HIGH", "MEDIUM", "LOW"
    message: str
    source_entry: DigestEntry


@dataclass
class ResearchDigest:
    """Complete research digest output from the pipeline."""

    date: str
    entries: list[DigestEntry]
    alerts: list[Alert]
    tickers_analyzed: list[str]
    summary: str


def classify_materiality(
    sentiment: Decimal,
    threshold: Decimal = Decimal("0.5"),
) -> bool:
    """Determine whether a sentiment value represents a material change.

    Args:
        sentiment: The sentiment score, typically between -1 and 1.
        threshold: Minimum absolute sentiment to consider material.

    Returns:
        True if the absolute sentiment meets or exceeds the threshold.
    """
    return abs(sentiment) >= threshold


def severity_from_sentiment(sentiment: Decimal) -> str:
    """Map a sentiment value to an alert severity level.

    Args:
        sentiment: The sentiment score.

    Returns:
        "HIGH" if abs >= 0.8, "MEDIUM" if abs >= 0.5, else "LOW".
    """
    magnitude = abs(sentiment)
    if magnitude >= Decimal("0.8"):
        return "HIGH"
    if magnitude >= Decimal("0.5"):
        return "MEDIUM"
    return "LOW"


def create_alert(entry: DigestEntry) -> Alert:
    """Create an alert from a material digest entry.

    Args:
        entry: The digest entry to create an alert from.

    Returns:
        An Alert with category inferred from the entry source.
    """
    source_lower = entry.source.lower()
    if "earning" in source_lower:
        category = "earnings"
    elif "filing" in source_lower or "sec" in source_lower:
        category = "filing"
    elif "macro" in source_lower:
        category = "macro"
    elif "thesis" in source_lower:
        category = "thesis"
    else:
        category = "other"

    return Alert(
        ticker=entry.ticker,
        category=category,
        severity=severity_from_sentiment(entry.sentiment),
        message=entry.summary,
        source_entry=entry,
    )


def filter_material_entries(
    entries: list[DigestEntry],
    threshold: Decimal = Decimal("0.5"),
) -> list[DigestEntry]:
    """Filter entries to only those considered material.

    Args:
        entries: List of digest entries to filter.
        threshold: Minimum absolute sentiment for materiality.

    Returns:
        Entries where material is True or abs(sentiment) >= threshold.
    """
    return [
        e
        for e in entries
        if e.material or abs(e.sentiment) >= threshold
    ]


def generate_digest_summary(
    entries: list[DigestEntry],
    alerts: list[Alert],
) -> str:
    """Produce a human-readable summary of the digest.

    Args:
        entries: All digest entries analyzed.
        alerts: Alerts generated from material entries.

    Returns:
        Summary string with entry, ticker, and alert counts.
    """
    tickers = {e.ticker for e in entries}
    high = sum(1 for a in alerts if a.severity == "HIGH")
    medium = sum(1 for a in alerts if a.severity == "MEDIUM")
    low = sum(1 for a in alerts if a.severity == "LOW")
    return (
        f"Analyzed {len(entries)} entries across {len(tickers)} tickers. "
        f"{len(alerts)} alerts generated ({high} high, {medium} medium, {low} low)."
    )


def build_digest(
    config: PipelineConfig,
    sources: list[DataSource],
) -> ResearchDigest:
    """Execute the full research pipeline.

    Args:
        config: Pipeline configuration.
        sources: Raw data sources to process.

    Returns:
        A complete ResearchDigest with entries, alerts, and summary.
    """
    today = date.today().isoformat()

    entries: list[DigestEntry] = []
    for src in sources:
        entry = DigestEntry(
            ticker=src.ticker,
            source=src.source_type,
            summary=src.content,
            sentiment=Decimal("0"),
            material=False,
            timestamp=today,
        )
        entries.append(entry)

    material = filter_material_entries(entries, config.alert_threshold)
    alerts = [create_alert(e) for e in material]
    summary = generate_digest_summary(entries, alerts)
    tickers_analyzed = sorted({e.ticker for e in entries})

    return ResearchDigest(
        date=today,
        entries=entries,
        alerts=alerts,
        tickers_analyzed=tickers_analyzed,
        summary=summary,
    )


class ResearchPipeline:
    """Orchestrates data ingestion and digest generation."""

    def __init__(self, config: PipelineConfig) -> None:
        """Initialize the pipeline with a configuration.

        Args:
            config: Pipeline configuration with tickers and thresholds.
        """
        self.config = config
        self._sources: list[DataSource] = []

    def add_source(self, source: DataSource) -> None:
        """Add a data source to the pipeline.

        Args:
            source: A single data source to ingest.
        """
        self._sources.append(source)

    def add_sources(self, sources: list[DataSource]) -> None:
        """Add multiple data sources.

        Args:
            sources: List of data sources to ingest.
        """
        self._sources.extend(sources)

    def run(self) -> ResearchDigest:
        """Execute the pipeline and produce a digest.

        Returns:
            A complete ResearchDigest from all added sources.
        """
        return build_digest(self.config, self._sources)

    def clear(self) -> None:
        """Clear all sources for next run."""
        self._sources.clear()
