"""Pydantic contracts for the macro outlook agent.

The macro outlook translates a multi-dimensional regime classification
into forward-looking asset-class tilts, bounded by the investment
policy's min/max bands.  Tilts are expressed as signed offsets from the
policy target weight (e.g. +0.03 means overweight by 3 pp).
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from src.application.contracts.household import AssetClass


class TiltDirection(StrEnum):
    """Direction of an asset-class tilt relative to policy target."""

    OVERWEIGHT = "overweight"
    NEUTRAL = "neutral"
    UNDERWEIGHT = "underweight"


class AssetClassTilt(BaseModel):
    """A single asset-class tilt recommendation.

    ``tilt`` is the signed offset from the policy target weight.
    Positive = overweight, negative = underweight, zero = neutral.
    The recommended weight is clamped to [min_weight, max_weight].
    """

    asset_class: AssetClass
    direction: TiltDirection
    tilt: Decimal = Field(
        description="Signed offset from target weight (e.g. 0.03 = +3pp)",
    )
    recommended_weight: Decimal = Field(
        description="Policy target + tilt, clamped to policy bands",
    )
    target_weight: Decimal = Field(
        description="Original policy target weight for reference",
    )
    rationale: str = Field(
        description="Brief reason for this tilt",
    )


class MacroOutlookResponse(BaseModel):
    """Complete macro outlook with per-asset-class tilts.

    Tilts are bounded by the investment policy.  They sum to zero
    (budget-neutral) so the portfolio stays fully invested.
    """

    tilts: list[AssetClassTilt] = Field(
        description="Per-asset-class tilt recommendations",
    )
    regime_summary: str = Field(
        description="One-paragraph regime narrative for the outlook",
    )
    confidence: Decimal = Field(
        description="Overall outlook confidence in [0, 1]",
    )
    as_of: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of this outlook",
    )

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, v: Decimal) -> Decimal:
        if not (Decimal("0") <= v <= Decimal("1")):
            raise ValueError(f"confidence must be in [0, 1], got {v}")
        return v

    @model_validator(mode="after")
    def _tilts_budget_neutral(self) -> Self:
        total = sum(t.tilt for t in self.tilts)
        if abs(total) > Decimal("0.001"):
            raise ValueError(
                f"Tilts must be budget-neutral (sum to 0), got {total}"
            )
        return self

    @property
    def active_tilts(self) -> list[AssetClassTilt]:
        """Return only non-neutral tilts."""
        return [t for t in self.tilts if t.direction != TiltDirection.NEUTRAL]
