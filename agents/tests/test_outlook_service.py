"""Tests for macro outlook service and contracts."""

from decimal import Decimal

import pytest

from src.application.contracts.household import AssetClass
from src.application.contracts.outlook import (
    AssetClassTilt,
    MacroOutlookResponse,
    TiltDirection,
)
from src.application.contracts.policy import AllocationTarget, InvestmentPolicy
from src.application.contracts.regime import (
    GrowthClassification,
    GrowthRegime,
    InflationClassification,
    InflationRegime,
    MacroRegimeReport,
    RateClassification,
    RateEnvironment,
    TrendDirection,
)
from src.application.services.outlook_service import (
    MAX_TILT_MAGNITUDE,
    compute_tilts,
)

_D = Decimal


def _balanced_policy() -> InvestmentPolicy:
    """Build a balanced 60/40-ish investment policy for testing."""
    return InvestmentPolicy(
        allocations={
            AssetClass.US_EQUITY: AllocationTarget(
                target_weight=_D("0.30"), min_weight=_D("0.20"), max_weight=_D("0.40"),
            ),
            AssetClass.INTL_DEVELOPED: AllocationTarget(
                target_weight=_D("0.10"), min_weight=_D("0.05"), max_weight=_D("0.15"),
            ),
            AssetClass.EMERGING_MARKETS: AllocationTarget(
                target_weight=_D("0.05"), min_weight=_D("0.00"), max_weight=_D("0.10"),
            ),
            AssetClass.US_TREASURIES: AllocationTarget(
                target_weight=_D("0.20"), min_weight=_D("0.10"), max_weight=_D("0.30"),
            ),
            AssetClass.IG_CORPORATE: AllocationTarget(
                target_weight=_D("0.10"), min_weight=_D("0.05"), max_weight=_D("0.15"),
            ),
            AssetClass.HIGH_YIELD: AllocationTarget(
                target_weight=_D("0.05"), min_weight=_D("0.00"), max_weight=_D("0.10"),
            ),
            AssetClass.TIPS: AllocationTarget(
                target_weight=_D("0.05"), min_weight=_D("0.00"), max_weight=_D("0.10"),
            ),
            AssetClass.REAL_ASSETS: AllocationTarget(
                target_weight=_D("0.05"), min_weight=_D("0.00"), max_weight=_D("0.10"),
            ),
            AssetClass.CASH_MONEY_MARKET: AllocationTarget(
                target_weight=_D("0.10"), min_weight=_D("0.05"), max_weight=_D("0.20"),
            ),
        },
    )


def _expansion_report() -> MacroRegimeReport:
    """Build a full expansion regime report."""
    return MacroRegimeReport(
        growth=GrowthClassification(
            regime=GrowthRegime.EXPANSION,
            trend=TrendDirection.IMPROVING,
            confidence=_D("0.8"),
            contributing_indicators=["GDP", "INDPRO"],
        ),
        rates=RateClassification(
            regime=RateEnvironment.FALLING,
            trend=TrendDirection.IMPROVING,
            confidence=_D("0.8"),
            contributing_indicators=["FEDFUNDS", "T10Y2Y"],
        ),
        inflation=InflationClassification(
            regime=InflationRegime.STABLE,
            trend=TrendDirection.STABLE,
            confidence=_D("0.7"),
            contributing_indicators=["CPIAUCSL"],
        ),
    )


def _contraction_report() -> MacroRegimeReport:
    """Build a contraction regime report."""
    return MacroRegimeReport(
        growth=GrowthClassification(
            regime=GrowthRegime.CONTRACTION,
            trend=TrendDirection.DETERIORATING,
            confidence=_D("0.8"),
            contributing_indicators=["GDP", "UNRATE"],
        ),
        rates=RateClassification(
            regime=RateEnvironment.PEAK,
            trend=TrendDirection.STABLE,
            confidence=_D("0.7"),
            contributing_indicators=["FEDFUNDS"],
        ),
        inflation=InflationClassification(
            regime=InflationRegime.STAGFLATION,
            trend=TrendDirection.DETERIORATING,
            confidence=_D("0.6"),
            contributing_indicators=["CPIAUCSL", "UNRATE"],
        ),
    )


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestOutlookContracts:
    def test_budget_neutral_validation(self) -> None:
        """Tilts that don't sum to 0 should fail validation."""
        with pytest.raises(ValueError):
            MacroOutlookResponse(
                tilts=[
                    AssetClassTilt(
                        asset_class=AssetClass.US_EQUITY,
                        direction=TiltDirection.OVERWEIGHT,
                        tilt=_D("0.05"),
                        recommended_weight=_D("0.35"),
                        target_weight=_D("0.30"),
                        rationale="test",
                    ),
                ],
                regime_summary="test",
                confidence=_D("0.8"),
            )

    def test_active_tilts_excludes_neutral(self) -> None:
        """active_tilts should only return non-neutral entries."""
        tilts = [
            AssetClassTilt(
                asset_class=AssetClass.US_EQUITY,
                direction=TiltDirection.OVERWEIGHT,
                tilt=_D("0.02"),
                recommended_weight=_D("0.32"),
                target_weight=_D("0.30"),
                rationale="test",
            ),
            AssetClassTilt(
                asset_class=AssetClass.US_TREASURIES,
                direction=TiltDirection.UNDERWEIGHT,
                tilt=_D("-0.02"),
                recommended_weight=_D("0.18"),
                target_weight=_D("0.20"),
                rationale="test",
            ),
            AssetClassTilt(
                asset_class=AssetClass.CASH_MONEY_MARKET,
                direction=TiltDirection.NEUTRAL,
                tilt=_D("0"),
                recommended_weight=_D("0.10"),
                target_weight=_D("0.10"),
                rationale="no signal",
            ),
        ]
        resp = MacroOutlookResponse(
            tilts=tilts, regime_summary="test", confidence=_D("0.8"),
        )
        assert len(resp.active_tilts) == 2


# ---------------------------------------------------------------------------
# Compute tilts tests
# ---------------------------------------------------------------------------


class TestComputeTilts:
    def test_expansion_overweights_equity(self) -> None:
        """Expansion should overweight equity, underweight cash/treasuries."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        equity_tilt = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert equity_tilt.direction == TiltDirection.OVERWEIGHT
        assert equity_tilt.tilt > 0

    def test_contraction_underweights_equity(self) -> None:
        """Contraction should underweight equity, overweight safety."""
        result = compute_tilts(_contraction_report(), _balanced_policy())
        equity_tilt = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert equity_tilt.direction == TiltDirection.UNDERWEIGHT
        assert equity_tilt.tilt < 0

    def test_contraction_overweights_treasuries(self) -> None:
        """Contraction should overweight treasuries."""
        result = compute_tilts(_contraction_report(), _balanced_policy())
        treas_tilt = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_TREASURIES
        )
        assert treas_tilt.direction == TiltDirection.OVERWEIGHT

    def test_tilts_are_budget_neutral(self) -> None:
        """All tilts must sum to exactly zero."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        total = sum(t.tilt for t in result.tilts)
        assert total == _D("0")

    def test_all_asset_classes_present(self) -> None:
        """Every canonical asset class should have a tilt entry."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        tilt_classes = {t.asset_class for t in result.tilts}
        assert tilt_classes == set(AssetClass)

    def test_recommended_weights_respect_policy_bands(self) -> None:
        """No recommended weight should exceed policy min/max."""
        policy = _balanced_policy()
        result = compute_tilts(_expansion_report(), policy)
        for t in result.tilts:
            alloc = policy.allocations[t.asset_class]
            assert t.recommended_weight >= alloc.min_weight, (
                f"{t.asset_class.value}: {t.recommended_weight} < min {alloc.min_weight}"
            )
            assert t.recommended_weight <= alloc.max_weight, (
                f"{t.asset_class.value}: {t.recommended_weight} > max {alloc.max_weight}"
            )

    def test_recommended_weights_sum_to_one(self) -> None:
        """Recommended weights must sum to exactly 1.0 (fully invested)."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        total = sum(t.recommended_weight for t in result.tilts)
        assert total == _D("1")

    def test_empty_report_returns_neutral(self) -> None:
        """No regime data → all tilts should be neutral (at target)."""
        report = MacroRegimeReport()
        result = compute_tilts(report, _balanced_policy())
        for t in result.tilts:
            assert t.direction == TiltDirection.NEUTRAL
            assert t.tilt == _D("0")

    def test_low_confidence_reduces_tilts(self) -> None:
        """Low confidence should produce smaller tilts than high confidence."""
        high_conf = _expansion_report()
        low_conf = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                confidence=_D("0.3"),
                contributing_indicators=["GDP"],
            ),
        )
        high_result = compute_tilts(high_conf, _balanced_policy())
        low_result = compute_tilts(low_conf, _balanced_policy())

        high_equity = next(
            t for t in high_result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        low_equity = next(
            t for t in low_result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert abs(high_equity.tilt) > abs(low_equity.tilt)

    def test_raw_tilt_magnitude_capped(self) -> None:
        """MAX_TILT_MAGNITUDE caps raw tilts before band/normalization.

        Final tilts may differ slightly after renormalization, but policy
        bands are the hard constraint (tested separately).
        """
        result = compute_tilts(_expansion_report(), _balanced_policy())
        # Expansion raw tilts stay within cap; verify a known case
        eq = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert eq.tilt == _D("0.0296")
        assert eq.tilt <= MAX_TILT_MAGNITUDE

    def test_confidence_propagated(self) -> None:
        """Outlook confidence should match regime report confidence."""
        report = _expansion_report()
        result = compute_tilts(report, _balanced_policy())
        assert result.confidence == report.overall_confidence

    def test_regime_summary_populated(self) -> None:
        """Regime summary should mention all populated dimensions."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        assert "Growth" in result.regime_summary
        assert "Rates" in result.regime_summary
        assert "Inflation" in result.regime_summary

    def test_regime_summary_empty_report(self) -> None:
        """Empty report should produce 'insufficient data' summary."""
        result = compute_tilts(MacroRegimeReport(), _balanced_policy())
        assert "Insufficient" in result.regime_summary

    def test_rationale_includes_regime(self) -> None:
        """Active tilt rationales should include regime context."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        active = result.active_tilts
        assert len(active) > 0
        for t in active:
            assert "expansion" in t.rationale or "falling" in t.rationale \
                or "stable" in t.rationale

    def test_single_dimension_growth_only(self) -> None:
        """Only growth dimension populated → should still produce tilts."""
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.EXPANSION,
                confidence=_D("0.8"),
                contributing_indicators=["GDP"],
            ),
        )
        result = compute_tilts(report, _balanced_policy())
        equity = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert equity.direction == TiltDirection.OVERWEIGHT

    def test_stagflation_overweights_tips(self) -> None:
        """Stagflation should favor TIPS and real assets."""
        result = compute_tilts(_contraction_report(), _balanced_policy())
        tips = next(
            t for t in result.tilts if t.asset_class == AssetClass.TIPS
        )
        assert tips.direction == TiltDirection.OVERWEIGHT

    def test_contraction_budget_neutral(self) -> None:
        """Contraction scenario tilts must also sum to exactly zero."""
        result = compute_tilts(_contraction_report(), _balanced_policy())
        assert sum(t.tilt for t in result.tilts) == _D("0")
        assert sum(t.recommended_weight for t in result.tilts) == _D("1")

    def test_tight_bands_clamp_and_remain_budget_neutral(self) -> None:
        """With tight bands, tilts are clamped but budget neutrality holds."""
        tight_policy = InvestmentPolicy(allocations={
            ac: AllocationTarget(
                target_weight=_D("0.1111"),
                min_weight=_D("0.10"),
                max_weight=_D("0.12"),
            )
            for ac in AssetClass
        })
        # Should not raise — contract validates budget neutrality
        result = compute_tilts(_expansion_report(), tight_policy)
        for t in result.tilts:
            assert t.recommended_weight >= _D("0.10"), (
                f"{t.asset_class.value} below min"
            )
            assert t.recommended_weight <= _D("0.12"), (
                f"{t.asset_class.value} above max"
            )
        assert sum(t.recommended_weight for t in result.tilts) == _D("1")

    def test_recovery_regime_overweights_equity(self) -> None:
        """Recovery growth regime should overweight equity."""
        report = MacroRegimeReport(
            growth=GrowthClassification(
                regime=GrowthRegime.RECOVERY,
                confidence=_D("0.8"),
                contributing_indicators=["GDP"],
            ),
        )
        result = compute_tilts(report, _balanced_policy())
        eq = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert eq.direction == TiltDirection.OVERWEIGHT

    def test_rising_rates_overweights_cash(self) -> None:
        """Rising rates should overweight cash."""
        report = MacroRegimeReport(
            rates=RateClassification(
                regime=RateEnvironment.RISING,
                confidence=_D("0.8"),
                contributing_indicators=["FEDFUNDS"],
            ),
        )
        result = compute_tilts(report, _balanced_policy())
        cash = next(
            t for t in result.tilts
            if t.asset_class == AssetClass.CASH_MONEY_MARKET
        )
        assert cash.direction == TiltDirection.OVERWEIGHT

    def test_reflation_overweights_tips_and_real_assets(self) -> None:
        """Reflation should overweight TIPS and real assets."""
        report = MacroRegimeReport(
            inflation=InflationClassification(
                regime=InflationRegime.REFLATION,
                confidence=_D("0.8"),
                contributing_indicators=["CPIAUCSL"],
            ),
        )
        result = compute_tilts(report, _balanced_policy())
        tips = next(
            t for t in result.tilts if t.asset_class == AssetClass.TIPS
        )
        real = next(
            t for t in result.tilts if t.asset_class == AssetClass.REAL_ASSETS
        )
        assert tips.direction == TiltDirection.OVERWEIGHT
        assert real.direction == TiltDirection.OVERWEIGHT

    def test_expansion_exact_equity_tilt(self) -> None:
        """Verify exact expansion equity tilt to detect regressions."""
        result = compute_tilts(_expansion_report(), _balanced_policy())
        eq = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert eq.tilt == _D("0.0296")
        assert eq.recommended_weight == _D("0.3296")

    def test_contraction_exact_equity_tilt(self) -> None:
        """Verify exact contraction equity tilt to detect regressions."""
        result = compute_tilts(_contraction_report(), _balanced_policy())
        eq = next(
            t for t in result.tilts if t.asset_class == AssetClass.US_EQUITY
        )
        assert eq.tilt == _D("-0.0416")
        assert eq.recommended_weight == _D("0.2584")


# ---------------------------------------------------------------------------
# Agent integration tests
# ---------------------------------------------------------------------------


class TestMacroOutlookAgent:
    @pytest.mark.asyncio
    async def test_agent_run_returns_dashboard(self) -> None:
        """Agent.run() should return formatted dashboard content."""
        from src.agents.macro_outlook import MacroOutlookAgent

        agent = MacroOutlookAgent()
        response = await agent.run(
            "Generate outlook",
            regime_report=_expansion_report(),
            policy=_balanced_policy(),
        )
        assert "Macro Outlook" in response.content
        assert "Asset-Class Tilts" in response.content
        assert response.metadata["tilts"] == len(AssetClass)

    @pytest.mark.asyncio
    async def test_agent_missing_regime_report(self) -> None:
        """Agent should return error when regime_report is missing."""
        from src.agents.macro_outlook import MacroOutlookAgent

        agent = MacroOutlookAgent()
        response = await agent.run(
            "Generate outlook",
            policy=_balanced_policy(),
        )
        assert response.metadata.get("error") == "missing_regime_report"

    @pytest.mark.asyncio
    async def test_agent_missing_policy(self) -> None:
        """Agent should return error when policy is missing."""
        from src.agents.macro_outlook import MacroOutlookAgent

        agent = MacroOutlookAgent()
        response = await agent.run(
            "Generate outlook",
            regime_report=_expansion_report(),
        )
        assert response.metadata.get("error") == "missing_policy"

    @pytest.mark.asyncio
    async def test_agent_accepts_dict_inputs(self) -> None:
        """Agent should coerce dict kwargs into Pydantic models."""
        from src.agents.macro_outlook import MacroOutlookAgent

        agent = MacroOutlookAgent()
        response = await agent.run(
            "Generate outlook",
            regime_report=_expansion_report().model_dump(),
            policy=_balanced_policy().model_dump(),
        )
        assert "Macro Outlook" in response.content
        assert response.metadata["tilts"] == len(AssetClass)
