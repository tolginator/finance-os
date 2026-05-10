"""Macro outlook service — maps regime classifications to asset-class tilts.

Deterministic, rule-based engine.  No LLM calls.

The service takes a ``MacroRegimeReport`` and an ``InvestmentPolicy``,
applies regime-driven tilt rules per canonical asset class, then clamps
tilts to the policy bands and re-normalizes to maintain budget neutrality.
"""

from decimal import Decimal

from src.application.contracts.household import AssetClass
from src.application.contracts.outlook import (
    AssetClassTilt,
    MacroOutlookResponse,
    TiltDirection,
)
from src.application.contracts.policy import InvestmentPolicy
from src.application.contracts.regime import (
    GrowthRegime,
    InflationRegime,
    MacroRegimeReport,
    RateEnvironment,
)

# ---------------------------------------------------------------------------
# Tilt rules — per asset class, per regime dimension
# ---------------------------------------------------------------------------
#
# Values are signed Decimal offsets (positive = overweight).
# Each dimension contributes independently; contributions are summed
# then clamped to MAX_TILT_MAGNITUDE before policy-band clamping.

# Maximum raw tilt magnitude before policy-band clamping and
# renormalization.  Final tilts may differ after band clamping
# redistributes weight across asset classes.
MAX_TILT_MAGNITUDE = Decimal("0.05")

# Growth dimension tilts
GROWTH_TILTS: dict[GrowthRegime, dict[AssetClass, Decimal]] = {
    GrowthRegime.EXPANSION: {
        AssetClass.US_EQUITY: Decimal("0.03"),
        AssetClass.INTL_DEVELOPED: Decimal("0.01"),
        AssetClass.EMERGING_MARKETS: Decimal("0.01"),
        AssetClass.US_TREASURIES: Decimal("-0.02"),
        AssetClass.IG_CORPORATE: Decimal("-0.01"),
        AssetClass.HIGH_YIELD: Decimal("0.01"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0.01"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.04"),
    },
    GrowthRegime.SLOWING: {
        AssetClass.US_EQUITY: Decimal("-0.01"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("-0.01"),
        AssetClass.US_TREASURIES: Decimal("0.02"),
        AssetClass.IG_CORPORATE: Decimal("0.01"),
        AssetClass.HIGH_YIELD: Decimal("-0.01"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0"),
    },
    GrowthRegime.CONTRACTION: {
        AssetClass.US_EQUITY: Decimal("-0.03"),
        AssetClass.INTL_DEVELOPED: Decimal("-0.01"),
        AssetClass.EMERGING_MARKETS: Decimal("-0.02"),
        AssetClass.US_TREASURIES: Decimal("0.04"),
        AssetClass.IG_CORPORATE: Decimal("0.01"),
        AssetClass.HIGH_YIELD: Decimal("-0.02"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("-0.01"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0.04"),
    },
    GrowthRegime.RECOVERY: {
        AssetClass.US_EQUITY: Decimal("0.02"),
        AssetClass.INTL_DEVELOPED: Decimal("0.01"),
        AssetClass.EMERGING_MARKETS: Decimal("0.01"),
        AssetClass.US_TREASURIES: Decimal("-0.01"),
        AssetClass.IG_CORPORATE: Decimal("0"),
        AssetClass.HIGH_YIELD: Decimal("0.01"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0.01"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.05"),
    },
}

# Rate dimension tilts
RATE_TILTS: dict[RateEnvironment, dict[AssetClass, Decimal]] = {
    RateEnvironment.RISING: {
        AssetClass.US_EQUITY: Decimal("-0.01"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("-0.01"),
        AssetClass.US_TREASURIES: Decimal("-0.02"),
        AssetClass.IG_CORPORATE: Decimal("-0.01"),
        AssetClass.HIGH_YIELD: Decimal("-0.01"),
        AssetClass.TIPS: Decimal("0.01"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0.05"),
    },
    RateEnvironment.PEAK: {
        AssetClass.US_EQUITY: Decimal("0"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("0"),
        AssetClass.US_TREASURIES: Decimal("0.02"),
        AssetClass.IG_CORPORATE: Decimal("0.01"),
        AssetClass.HIGH_YIELD: Decimal("0"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.03"),
    },
    RateEnvironment.FALLING: {
        AssetClass.US_EQUITY: Decimal("0.01"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("0.01"),
        AssetClass.US_TREASURIES: Decimal("0.02"),
        AssetClass.IG_CORPORATE: Decimal("0.01"),
        AssetClass.HIGH_YIELD: Decimal("0.01"),
        AssetClass.TIPS: Decimal("-0.01"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.05"),
    },
    RateEnvironment.TROUGH: {
        AssetClass.US_EQUITY: Decimal("0.02"),
        AssetClass.INTL_DEVELOPED: Decimal("0.01"),
        AssetClass.EMERGING_MARKETS: Decimal("0.01"),
        AssetClass.US_TREASURIES: Decimal("-0.02"),
        AssetClass.IG_CORPORATE: Decimal("0"),
        AssetClass.HIGH_YIELD: Decimal("0.01"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0.01"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.04"),
    },
}

# Inflation dimension tilts
INFLATION_TILTS: dict[InflationRegime, dict[AssetClass, Decimal]] = {
    InflationRegime.DISINFLATION: {
        AssetClass.US_EQUITY: Decimal("0.01"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("0"),
        AssetClass.US_TREASURIES: Decimal("0.02"),
        AssetClass.IG_CORPORATE: Decimal("0.01"),
        AssetClass.HIGH_YIELD: Decimal("0"),
        AssetClass.TIPS: Decimal("-0.02"),
        AssetClass.REAL_ASSETS: Decimal("-0.01"),
        AssetClass.CASH_MONEY_MARKET: Decimal("-0.01"),
    },
    InflationRegime.STABLE: {
        AssetClass.US_EQUITY: Decimal("0"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("0"),
        AssetClass.US_TREASURIES: Decimal("0"),
        AssetClass.IG_CORPORATE: Decimal("0"),
        AssetClass.HIGH_YIELD: Decimal("0"),
        AssetClass.TIPS: Decimal("0"),
        AssetClass.REAL_ASSETS: Decimal("0"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0"),
    },
    InflationRegime.REFLATION: {
        AssetClass.US_EQUITY: Decimal("-0.01"),
        AssetClass.INTL_DEVELOPED: Decimal("0"),
        AssetClass.EMERGING_MARKETS: Decimal("0"),
        AssetClass.US_TREASURIES: Decimal("-0.02"),
        AssetClass.IG_CORPORATE: Decimal("-0.01"),
        AssetClass.HIGH_YIELD: Decimal("0"),
        AssetClass.TIPS: Decimal("0.02"),
        AssetClass.REAL_ASSETS: Decimal("0.02"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0"),
    },
    InflationRegime.STAGFLATION: {
        AssetClass.US_EQUITY: Decimal("-0.03"),
        AssetClass.INTL_DEVELOPED: Decimal("-0.01"),
        AssetClass.EMERGING_MARKETS: Decimal("-0.02"),
        AssetClass.US_TREASURIES: Decimal("0.01"),
        AssetClass.IG_CORPORATE: Decimal("-0.01"),
        AssetClass.HIGH_YIELD: Decimal("-0.02"),
        AssetClass.TIPS: Decimal("0.03"),
        AssetClass.REAL_ASSETS: Decimal("0.02"),
        AssetClass.CASH_MONEY_MARKET: Decimal("0.03"),
    },
}


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


def compute_tilts(
    report: MacroRegimeReport,
    policy: InvestmentPolicy,
) -> MacroOutlookResponse:
    """Compute asset-class tilts from regime report, bounded by policy.

    Steps:
    1. Sum per-dimension tilt contributions for each asset class.
    2. Scale by regime confidence (lower confidence → smaller tilt).
    3. Clamp each raw tilt to ±MAX_TILT_MAGNITUDE.
    4. Clamp recommended weight to policy [min, max] bands.
    5. Re-derive tilt from clamped weight.
    6. Re-normalize tilts to sum to zero (budget-neutral).
    """
    raw_tilts: dict[AssetClass, Decimal] = {ac: Decimal("0") for ac in AssetClass}

    # Accumulate dimension contributions
    if report.growth is not None:
        _apply_dimension(raw_tilts, GROWTH_TILTS.get(report.growth.regime, {}),
                         report.growth.confidence)
    if report.rates is not None:
        _apply_dimension(raw_tilts, RATE_TILTS.get(report.rates.regime, {}),
                         report.rates.confidence)
    if report.inflation is not None:
        _apply_dimension(raw_tilts, INFLATION_TILTS.get(report.inflation.regime, {}),
                         report.inflation.confidence)

    # Clamp raw tilts to max magnitude
    for ac in AssetClass:
        raw_tilts[ac] = max(-MAX_TILT_MAGNITUDE,
                           min(MAX_TILT_MAGNITUDE, raw_tilts[ac]))

    # Apply policy band clamping
    clamped_weights: dict[AssetClass, Decimal] = {}
    for ac in AssetClass:
        target = policy.allocations[ac].target_weight
        min_w = policy.allocations[ac].min_weight
        max_w = policy.allocations[ac].max_weight
        recommended = max(min_w, min(max_w, target + raw_tilts[ac]))
        clamped_weights[ac] = recommended

    # Re-normalize so weights sum to 1 while respecting bands.
    # Iterative adjustment: distribute excess/deficit equally
    # among asset classes that have room within their bands.
    for _ in range(10):  # converges quickly
        total = sum(clamped_weights.values())
        gap = Decimal("1") - total
        if abs(gap) <= Decimal("0.0001"):
            break
        # Distribute gap equally among classes with band room
        adjustable: list[AssetClass] = []
        for ac in AssetClass:
            min_w = policy.allocations[ac].min_weight
            max_w = policy.allocations[ac].max_weight
            if gap > 0 and clamped_weights[ac] < max_w:
                adjustable.append(ac)
            elif gap < 0 and clamped_weights[ac] > min_w:
                adjustable.append(ac)
        if not adjustable:
            break
        per_class = gap / len(adjustable)
        for ac in adjustable:
            min_w = policy.allocations[ac].min_weight
            max_w = policy.allocations[ac].max_weight
            clamped_weights[ac] = max(
                min_w, min(max_w, clamped_weights[ac] + per_class)
            )

    # Quantize to 4 decimal places
    for ac in AssetClass:
        clamped_weights[ac] = clamped_weights[ac].quantize(Decimal("0.0001"))
    # Fix rounding residual by distributing across classes with band room
    residual = Decimal("1") - sum(clamped_weights.values())
    while residual != 0:
        candidates = []
        for ac in sorted(AssetClass, key=lambda a: clamped_weights[a], reverse=True):
            min_w = policy.allocations[ac].min_weight
            max_w = policy.allocations[ac].max_weight
            if residual > 0 and clamped_weights[ac] < max_w:
                candidates.append(ac)
            elif residual < 0 and clamped_weights[ac] > min_w:
                candidates.append(ac)
        if not candidates:
            break
        step = Decimal("0.0001") if residual > 0 else Decimal("-0.0001")
        for ac in candidates:
            min_w = policy.allocations[ac].min_weight
            max_w = policy.allocations[ac].max_weight
            adjusted = clamped_weights[ac] + step
            if min_w <= adjusted <= max_w:
                clamped_weights[ac] = adjusted
                residual -= step
                if residual == 0:
                    break

    # Build tilt objects
    tilts: list[AssetClassTilt] = []
    for ac in AssetClass:
        target = policy.allocations[ac].target_weight
        tilt = clamped_weights[ac] - target
        if tilt > 0:
            direction = TiltDirection.OVERWEIGHT
        elif tilt < 0:
            direction = TiltDirection.UNDERWEIGHT
        else:
            direction = TiltDirection.NEUTRAL
        tilts.append(AssetClassTilt(
            asset_class=ac,
            direction=direction,
            tilt=tilt,
            recommended_weight=clamped_weights[ac],
            target_weight=target,
            rationale=_rationale(ac, direction, report),
        ))

    # Build regime summary
    summary = _regime_summary(report)

    return MacroOutlookResponse(
        tilts=tilts,
        regime_summary=summary,
        confidence=report.overall_confidence,
        as_of=report.as_of,
    )


def _apply_dimension(
    tilts: dict[AssetClass, Decimal],
    dimension_tilts: dict[AssetClass, Decimal],
    confidence: Decimal,
) -> None:
    """Add confidence-scaled dimension tilts to the accumulator."""
    for ac, value in dimension_tilts.items():
        tilts[ac] += value * confidence


def _rationale(
    ac: AssetClass,
    direction: TiltDirection,
    report: MacroRegimeReport,
) -> str:
    """Generate a brief rationale for the tilt direction."""
    if direction == TiltDirection.NEUTRAL:
        has_signal = any([report.growth, report.rates, report.inflation])
        if has_signal:
            return "Regime signal present but constrained to neutral by policy bands"
        return "No regime signal; hold at policy target"

    parts: list[str] = []
    if report.growth is not None:
        parts.append(f"growth={report.growth.regime.value}")
    if report.rates is not None:
        parts.append(f"rates={report.rates.regime.value}")
    if report.inflation is not None:
        parts.append(f"inflation={report.inflation.regime.value}")

    regime_ctx = ", ".join(parts) if parts else "no regime data"
    verb = "Overweight" if direction == TiltDirection.OVERWEIGHT else "Underweight"
    return f"{verb} {ac.value}: {regime_ctx}"


def _regime_summary(report: MacroRegimeReport) -> str:
    """Build a one-paragraph regime narrative."""
    parts: list[str] = []
    if report.growth is not None:
        parts.append(f"Growth: {report.growth.regime.value} "
                     f"(trend: {report.growth.trend.value})")
    if report.rates is not None:
        parts.append(f"Rates: {report.rates.regime.value} "
                     f"(trend: {report.rates.trend.value})")
    if report.inflation is not None:
        parts.append(f"Inflation: {report.inflation.regime.value} "
                     f"(trend: {report.inflation.trend.value})")
    if not parts:
        return "Insufficient data for regime classification."

    dims = len(parts)
    conf = report.overall_confidence
    return (
        f"Macro regime ({dims} dimension{'s' if dims != 1 else ''}, "
        f"confidence {conf:.0%}): {'; '.join(parts)}."
    )
