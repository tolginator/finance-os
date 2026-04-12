"""Digest service — wraps research pipeline for typed digest execution."""

from src.application.contracts.agents import RunDigestRequest, RunDigestResponse
from src.pipelines.research_digest import (
    DataSource,
    PipelineConfig,
    ResearchPipeline,
)


class DigestService:
    """Runs the research digest pipeline with typed contracts."""

    async def run_digest(self, request: RunDigestRequest) -> RunDigestResponse:
        """Execute the research digest pipeline.

        Args:
            request: Digest request with tickers, sources, and config.

        Returns:
            RunDigestResponse with digest summary and metrics.
        """
        config = PipelineConfig(
            tickers=request.tickers,
            lookback_days=request.lookback_days,
            alert_threshold=request.alert_threshold,
        )
        pipeline = ResearchPipeline(config)

        for source_dict in request.sources:
            source = DataSource(
                source_type=source_dict.get("source_type", ""),
                ticker=source_dict.get("ticker", ""),
                date=source_dict.get("date", ""),
                content=source_dict.get("content", ""),
                metadata=source_dict.get("metadata", {}),
            )
            pipeline.add_source(source)

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
