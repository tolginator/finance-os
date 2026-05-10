"""Pydantic contracts for multi-dimensional macro regime classification.

The macro regime model classifies the economic environment across independent
dimensions (growth, rates, inflation).  Each dimension carries its own
confidence and freshness metadata.  Global trade is defined but not yet
populated — awaiting IMF/World Bank data services.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from src.application.data_services.base import FreshnessState

# ---------------------------------------------------------------------------
# Regime enums
# ---------------------------------------------------------------------------


class GrowthRegime(StrEnum):
    """Growth dimension classification."""

    EXPANSION = "expansion"
    SLOWING = "slowing"
    CONTRACTION = "contraction"
    RECOVERY = "recovery"


class RateEnvironment(StrEnum):
    """Rate environment classification."""

    RISING = "rising"
    PEAK = "peak"
    FALLING = "falling"
    TROUGH = "trough"


class InflationRegime(StrEnum):
    """Inflation dimension classification."""

    DISINFLATION = "disinflation"
    STABLE = "stable"
    REFLATION = "reflation"
    STAGFLATION = "stagflation"


class GlobalTradeRegime(StrEnum):
    """Global trade dimension classification (future — requires IMF/WB data)."""

    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    DISRUPTED = "disrupted"


class TrendDirection(StrEnum):
    """Trend direction for a regime dimension."""

    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"


# ---------------------------------------------------------------------------
# Dimension classification
# ---------------------------------------------------------------------------


class DimensionClassification(BaseModel):
    """Classification result for a single regime dimension."""

    regime: str = Field(description="Regime enum value for this dimension")
    trend: TrendDirection = Field(
        default=TrendDirection.STABLE,
        description="Direction of recent change",
    )
    confidence: Decimal = Field(
        default=Decimal("0.5"),
        description="Classification confidence in [0, 1]",
    )
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Effective date of the classification",
    )
    freshness: FreshnessState = Field(
        default=FreshnessState.FRESH,
        description="Data freshness state",
    )
    contributing_indicators: list[str] = Field(
        default_factory=list,
        description="FRED series IDs that drove this classification",
    )

    @model_validator(mode="after")
    def _validate_confidence(self) -> Self:
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError("confidence must be in [0, 1]")
        return self


class GrowthClassification(DimensionClassification):
    """Growth dimension with typed regime field."""

    regime: GrowthRegime  # type: ignore[assignment]


class RateClassification(DimensionClassification):
    """Rate environment with typed regime field."""

    regime: RateEnvironment  # type: ignore[assignment]


class InflationClassification(DimensionClassification):
    """Inflation dimension with typed regime field."""

    regime: InflationRegime  # type: ignore[assignment]


class GlobalTradeClassification(DimensionClassification):
    """Global trade dimension with typed regime field."""

    regime: GlobalTradeRegime  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Full regime report
# ---------------------------------------------------------------------------


class MacroRegimeReport(BaseModel):
    """Multi-dimensional macro regime classification report.

    Each dimension is optional to support incremental rollout
    (global_trade requires IMF/WB services not yet available).
    """

    growth: GrowthClassification | None = Field(
        default=None, description="Growth cycle classification",
    )
    rates: RateClassification | None = Field(
        default=None, description="Rate environment classification",
    )
    inflation: InflationClassification | None = Field(
        default=None, description="Inflation regime classification",
    )
    global_trade: GlobalTradeClassification | None = Field(
        default=None, description="Global trade classification (future)",
    )
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Common effective timestamp for this report",
    )

    @property
    def overall_confidence(self) -> Decimal:
        """Average confidence across populated dimensions."""
        populated = [
            d.confidence
            for d in (self.growth, self.rates, self.inflation, self.global_trade)
            if d is not None
        ]
        if not populated:
            return Decimal("0")
        return sum(populated) / len(populated)

    @property
    def legacy_regime(self) -> str:
        """Map to EXPANSION/CONTRACTION/TRANSITION for backward compatibility.

        Uses growth dimension as primary signal, consistent with the
        original binary classifier's GDP-weighted logic.
        """
        if self.growth is None:
            return "TRANSITION"
        mapping = {
            GrowthRegime.EXPANSION: "EXPANSION",
            GrowthRegime.RECOVERY: "EXPANSION",
            GrowthRegime.CONTRACTION: "CONTRACTION",
            GrowthRegime.SLOWING: "TRANSITION",
        }
        return mapping[self.growth.regime]

    @property
    def populated_dimensions(self) -> int:
        """Count of non-None dimensions."""
        return sum(
            1
            for d in (self.growth, self.rates, self.inflation, self.global_trade)
            if d is not None
        )
