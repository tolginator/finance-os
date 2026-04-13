"""Tests for the research digest pipeline."""


from decimal import Decimal

from src.pipelines.research_digest import (
    Alert,
    DataSource,
    DigestEntry,
    PipelineConfig,
    ResearchPipeline,
    build_digest,
    classify_materiality,
    create_alert,
    filter_material_entries,
    generate_digest_summary,
    severity_from_sentiment,
)


def _make_entry(
    ticker: str = "AAPL",
    source: str = "earnings_call",
    summary: str = "Test summary",
    sentiment: Decimal = Decimal("0.6"),
    material: bool = True,
    timestamp: str = "2025-01-01",
) -> DigestEntry:
    return DigestEntry(
        ticker=ticker,
        source=source,
        summary=summary,
        sentiment=sentiment,
        material=material,
        timestamp=timestamp,
    )


# --- classify_materiality ---


class TestClassifyMateriality:
    def test_above_threshold_is_material(self) -> None:
        assert classify_materiality(Decimal("0.7")) is True

    def test_below_threshold_is_not_material(self) -> None:
        assert classify_materiality(Decimal("0.3")) is False

    def test_exactly_at_threshold_is_material(self) -> None:
        assert classify_materiality(Decimal("0.5")) is True

    def test_negative_sentiment_above_threshold(self) -> None:
        assert classify_materiality(Decimal("-0.8")) is True

    def test_custom_threshold(self) -> None:
        assert classify_materiality(Decimal("0.3"), Decimal("0.3")) is True
        assert classify_materiality(Decimal("0.2"), Decimal("0.3")) is False


# --- severity_from_sentiment ---


class TestSeverityFromSentiment:
    def test_high_severity(self) -> None:
        assert severity_from_sentiment(Decimal("0.9")) == "HIGH"
        assert severity_from_sentiment(Decimal("0.8")) == "HIGH"

    def test_medium_severity(self) -> None:
        assert severity_from_sentiment(Decimal("0.5")) == "MEDIUM"
        assert severity_from_sentiment(Decimal("0.7")) == "MEDIUM"

    def test_low_severity(self) -> None:
        assert severity_from_sentiment(Decimal("0.1")) == "LOW"
        assert severity_from_sentiment(Decimal("0.4")) == "LOW"

    def test_negative_sentiment(self) -> None:
        assert severity_from_sentiment(Decimal("-0.9")) == "HIGH"
        assert severity_from_sentiment(Decimal("-0.6")) == "MEDIUM"
        assert severity_from_sentiment(Decimal("-0.2")) == "LOW"


# --- create_alert ---


class TestCreateAlert:
    def test_earnings_category(self) -> None:
        entry = _make_entry(source="earnings_call")
        alert = create_alert(entry)
        assert alert.category == "earnings"

    def test_filing_category(self) -> None:
        entry = _make_entry(source="sec_filing")
        alert = create_alert(entry)
        assert alert.category == "filing"

    def test_filing_category_from_filing_keyword(self) -> None:
        entry = _make_entry(source="quarterly_filing")
        alert = create_alert(entry)
        assert alert.category == "filing"

    def test_macro_category(self) -> None:
        entry = _make_entry(source="macro_analysis")
        alert = create_alert(entry)
        assert alert.category == "macro"

    def test_thesis_category(self) -> None:
        entry = _make_entry(source="thesis_review")
        alert = create_alert(entry)
        assert alert.category == "thesis"

    def test_other_category(self) -> None:
        entry = _make_entry(source="custom_source")
        alert = create_alert(entry)
        assert alert.category == "other"

    def test_alert_inherits_entry_fields(self) -> None:
        entry = _make_entry(ticker="MSFT", sentiment=Decimal("0.9"))
        alert = create_alert(entry)
        assert alert.ticker == "MSFT"
        assert alert.severity == "HIGH"
        assert alert.source_entry is entry


# --- filter_material_entries ---


class TestFilterMaterialEntries:
    def test_keeps_material_entries(self) -> None:
        entries = [
            _make_entry(material=True, sentiment=Decimal("0.1")),
            _make_entry(material=False, sentiment=Decimal("0.1")),
        ]
        result = filter_material_entries(entries)
        assert len(result) == 1
        assert result[0].material is True

    def test_keeps_high_sentiment_even_if_not_flagged(self) -> None:
        entry = _make_entry(material=False, sentiment=Decimal("0.7"))
        result = filter_material_entries([entry])
        assert len(result) == 1

    def test_filters_out_low_sentiment_non_material(self) -> None:
        entry = _make_entry(material=False, sentiment=Decimal("0.2"))
        result = filter_material_entries([entry])
        assert len(result) == 0

    def test_custom_threshold(self) -> None:
        entry = _make_entry(material=False, sentiment=Decimal("0.3"))
        assert len(filter_material_entries([entry], Decimal("0.3"))) == 1
        assert len(filter_material_entries([entry], Decimal("0.4"))) == 0

    def test_material_flag_overrides_low_sentiment(self) -> None:
        """Entry with material=True but low sentiment is still included."""
        entry = _make_entry(material=True, sentiment=Decimal("0.1"))
        result = filter_material_entries([entry])
        assert len(result) == 1
        assert result[0].material is True


# --- generate_digest_summary ---


class TestGenerateDigestSummary:
    def test_correct_counts(self) -> None:
        entries = [
            _make_entry(ticker="AAPL"),
            _make_entry(ticker="MSFT"),
            _make_entry(ticker="AAPL"),
        ]
        alerts = [
            Alert(
                ticker="AAPL",
                category="earnings",
                severity="HIGH",
                message="test",
                source_entry=entries[0],
            ),
            Alert(
                ticker="MSFT",
                category="macro",
                severity="MEDIUM",
                message="test",
                source_entry=entries[1],
            ),
        ]
        summary = generate_digest_summary(entries, alerts)
        assert "3 entries" in summary
        assert "2 tickers" in summary
        assert "2 alerts" in summary
        assert "1 high" in summary
        assert "1 medium" in summary
        assert "0 low" in summary

    def test_empty_inputs(self) -> None:
        summary = generate_digest_summary([], [])
        assert "0 entries" in summary
        assert "0 tickers" in summary
        assert "0 alerts" in summary


# --- build_digest ---


class TestBuildDigest:
    def test_full_pipeline(self) -> None:
        config = PipelineConfig(tickers=["AAPL", "MSFT"])
        sources = [
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="Apple filed 10-K",
            ),
            DataSource(
                source_type="transcript",
                ticker="MSFT",
                date="2025-01-01",
                content="Microsoft earnings call",
            ),
        ]
        digest = build_digest(config, sources)
        assert len(digest.entries) == 2
        assert "AAPL" in digest.tickers_analyzed
        assert "MSFT" in digest.tickers_analyzed
        assert isinstance(digest.summary, str)
        assert digest.date  # non-empty

    def test_empty_sources_produces_empty_digest(self) -> None:
        config = PipelineConfig(tickers=["AAPL"])
        digest = build_digest(config, [])
        assert digest.entries == []
        assert digest.alerts == []
        assert digest.tickers_analyzed == []
        assert "0 entries" in digest.summary

    def test_sources_with_metadata_sentiment(self) -> None:
        """build_digest reads sentiment from metadata when available."""
        config = PipelineConfig(tickers=["AAPL"])
        sources = [
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="Apple 10-K",
                metadata={"sentiment": "0.6"},
            ),
        ]
        digest = build_digest(config, sources)
        assert len(digest.entries) == 1
        assert digest.entries[0].sentiment == Decimal("0.6")
        assert digest.entries[0].material is True

    def test_malformed_sentiment_defaults_to_zero(self) -> None:
        """Malformed sentiment metadata doesn't crash build_digest."""
        config = PipelineConfig(tickers=["AAPL"])
        sources = [
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="Apple filing",
                metadata={"sentiment": "N/A"},
            ),
        ]
        digest = build_digest(config, sources)
        assert len(digest.entries) == 1
        assert digest.entries[0].sentiment == Decimal("0")


# --- ResearchPipeline class ---


class TestResearchPipeline:
    def test_add_source_and_run(self) -> None:
        config = PipelineConfig(tickers=["AAPL"])
        pipeline = ResearchPipeline(config)
        pipeline.add_source(
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="Apple 10-K filing",
            )
        )
        digest = pipeline.run()
        assert len(digest.entries) == 1
        assert digest.entries[0].ticker == "AAPL"

    def test_add_sources_batch(self) -> None:
        config = PipelineConfig(tickers=["AAPL", "MSFT"])
        pipeline = ResearchPipeline(config)
        pipeline.add_sources([
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="Apple filing",
            ),
            DataSource(
                source_type="transcript",
                ticker="MSFT",
                date="2025-01-01",
                content="Microsoft call",
            ),
        ])
        digest = pipeline.run()
        assert len(digest.entries) == 2

    def test_clear_empties_sources(self) -> None:
        config = PipelineConfig(tickers=["AAPL"])
        pipeline = ResearchPipeline(config)
        pipeline.add_source(
            DataSource(
                source_type="edgar",
                ticker="AAPL",
                date="2025-01-01",
                content="test",
            )
        )
        pipeline.clear()
        digest = pipeline.run()
        assert digest.entries == []
