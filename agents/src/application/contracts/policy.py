"""Pydantic contracts for investment policy and financial goals.

An investment policy defines target asset-class allocations, rebalancing
bands, a benchmark blend, and risk/liquidity constraints.  Goals embed
a policy and add time-horizon + withdrawal/growth parameters.

All weight values use ``decimal.Decimal`` and represent fractions of 1
(e.g. 0.60 = 60 %).
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from src.application.contracts.household import AssetClass

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

_ALL_ASSET_CLASSES = frozenset(AssetClass)


class GoalType(StrEnum):
    """Supported goal archetypes."""

    RETIREMENT = "retirement"
    WEALTH_BUILDING = "wealth_building"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Allocation primitives
# ---------------------------------------------------------------------------


class AllocationTarget(BaseModel):
    """Per-asset-class allocation target with min/max bands."""

    target_weight: Decimal
    min_weight: Decimal = Decimal("0")
    max_weight: Decimal = Decimal("1")

    @model_validator(mode="after")
    def _ordering(self) -> Self:
        if not (0 <= self.min_weight <= self.target_weight <= self.max_weight <= 1):
            raise ValueError(
                f"Must have 0 <= min ({self.min_weight}) <= target "
                f"({self.target_weight}) <= max ({self.max_weight}) <= 1"
            )
        return self


class RebalancingBand(BaseModel):
    """Drift threshold that triggers rebalancing for one asset class.

    ``threshold`` is in absolute portfolio-weight points (e.g. 0.03 = ±3 pp).
    """

    threshold: Decimal = Decimal("0.05")

    @field_validator("threshold")
    @classmethod
    def positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("threshold must be positive")
        return v


class BenchmarkComponent(BaseModel):
    """One constituent of a synthetic benchmark blend."""

    ticker: str = Field(min_length=1)
    weight: Decimal

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v

    @field_validator("weight")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("weight must be non-negative")
        return v


# ---------------------------------------------------------------------------
# Investment Policy
# ---------------------------------------------------------------------------


class InvestmentPolicy(BaseModel):
    """Target allocation, rebalancing rules, and benchmark definition.

    ``allocations`` must cover all 9 canonical asset classes.  Targets
    must sum to 1.  The min/max feasibility constraint
    ``sum(min) <= 1 <= sum(max)`` is enforced so the policy is
    satisfiable.
    """

    allocations: dict[AssetClass, AllocationTarget]
    rebalancing_bands: dict[AssetClass, RebalancingBand] | None = Field(
        default=None,
    )

    @model_validator(mode="after")
    def _default_bands(self) -> Self:
        """Fill missing rebalancing bands with defaults for all asset classes."""
        default_bands = {ac: RebalancingBand() for ac in AssetClass}
        provided = self.rebalancing_bands or {}
        self.rebalancing_bands = {**default_bands, **provided}
        return self

    benchmark_blend: list[BenchmarkComponent] = Field(default_factory=list)
    risk_budget: Decimal | None = None
    liquidity_floor: Decimal = Decimal("0.05")

    @field_validator("liquidity_floor")
    @classmethod
    def floor_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("liquidity_floor must be non-negative")
        return v

    @model_validator(mode="after")
    def _policy_invariants(self) -> Self:
        # All asset classes required
        missing = _ALL_ASSET_CLASSES - self.allocations.keys()
        if missing:
            names = ", ".join(sorted(m.value for m in missing))
            raise ValueError(f"Missing allocations for: {names}")

        # Targets sum to 1
        total = sum(a.target_weight for a in self.allocations.values())
        if abs(total - 1) > Decimal("0.001"):
            raise ValueError(
                f"Target weights must sum to 1.0, got {total}"
            )

        # Feasibility: sum(min) <= 1 <= sum(max)
        min_sum = sum(a.min_weight for a in self.allocations.values())
        max_sum = sum(a.max_weight for a in self.allocations.values())
        if min_sum > 1:
            raise ValueError(
                f"sum(min_weight) = {min_sum} > 1; infeasible policy"
            )
        if max_sum < 1:
            raise ValueError(
                f"sum(max_weight) = {max_sum} < 1; infeasible policy"
            )

        # Cash floor consistency
        cash = self.allocations.get(AssetClass.CASH_MONEY_MARKET)
        if cash and cash.min_weight < self.liquidity_floor:
            raise ValueError(
                f"CASH_MONEY_MARKET min_weight ({cash.min_weight}) must be "
                f">= liquidity_floor ({self.liquidity_floor})"
            )

        # Benchmark weights sum to 1 (if provided)
        if self.benchmark_blend:
            bw = sum(c.weight for c in self.benchmark_blend)
            if abs(bw - 1) > Decimal("0.001"):
                raise ValueError(
                    f"Benchmark weights must sum to 1.0, got {bw}"
                )
            # Unique tickers
            tickers = [c.ticker for c in self.benchmark_blend]
            if len(tickers) != len(set(tickers)):
                raise ValueError("Benchmark blend has duplicate tickers")

        return self


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------


class Goal(BaseModel):
    """A financial goal with an embedded investment policy."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Goal name must not be blank")
        return v

    goal_type: GoalType
    policy: InvestmentPolicy
    horizon_years: int
    target_amount: Decimal | None = None
    withdrawal_rate: Decimal | None = None
    inflation_assumption: Decimal = Decimal("0.025")
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("horizon_years")
    @classmethod
    def positive_horizon(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("horizon_years must be positive")
        return v

    @field_validator("inflation_assumption")
    @classmethod
    def non_negative_inflation(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("inflation_assumption must be non-negative")
        return v

    @model_validator(mode="after")
    def _goal_type_invariants(self) -> Self:
        if self.goal_type == GoalType.RETIREMENT:
            if self.withdrawal_rate is None:
                raise ValueError(
                    "retirement goals require withdrawal_rate"
                )
            if self.withdrawal_rate <= 0:
                raise ValueError("withdrawal_rate must be positive")
        else:
            if self.withdrawal_rate is not None:
                raise ValueError(
                    f"{self.goal_type.value} goals should not have withdrawal_rate"
                )
        if self.target_amount is not None and self.target_amount < 0:
            raise ValueError("target_amount must be non-negative")
        return self


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


class DriftResult(BaseModel):
    """Per-asset-class drift from target allocation."""

    asset_class: AssetClass
    target_weight: Decimal
    current_weight: Decimal
    drift: Decimal  # current - target (positive = overweight)
    breaches_band: bool


class DriftReport(BaseModel):
    """Full drift analysis for a policy against current allocations."""

    drifts: list[DriftResult]
    any_breach: bool
    total_drift: Decimal  # sum of |drift|


# ---------------------------------------------------------------------------
# Store schema
# ---------------------------------------------------------------------------


class GoalsFile(BaseModel):
    """Schema for goals.json persistence."""

    schema_version: int = 1
    goals: dict[str, Goal] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------


class CreateGoalRequest(BaseModel):
    """Request to create a new goal."""

    name: str = Field(min_length=1)
    goal_type: GoalType
    policy: InvestmentPolicy
    horizon_years: int
    target_amount: Decimal | None = None
    withdrawal_rate: Decimal | None = None
    inflation_assumption: Decimal = Decimal("0.025")
    notes: str = ""

    @model_validator(mode="after")
    def _goal_type_invariants(self) -> Self:
        if self.goal_type == GoalType.RETIREMENT and self.withdrawal_rate is None:
            raise ValueError("Retirement goals require withdrawal_rate")
        if (
            self.goal_type != GoalType.RETIREMENT
            and self.withdrawal_rate is not None
        ):
            raise ValueError(
                f"{self.goal_type.value} goals should not have withdrawal_rate"
            )
        if self.horizon_years is not None and self.horizon_years < 1:
            raise ValueError("horizon_years must be positive")
        return self


class UpdateGoalRequest(BaseModel):
    """Request to update an existing goal."""

    name: str | None = None
    policy: InvestmentPolicy | None = None
    horizon_years: int | None = None
    target_amount: Decimal | None = None
    withdrawal_rate: Decimal | None = None
    inflation_assumption: Decimal | None = None
    notes: str | None = None


class DriftRequest(BaseModel):
    """Request for drift computation."""

    current_allocations: dict[AssetClass, Decimal]

    @model_validator(mode="after")
    def _allocations_valid(self) -> Self:
        for ac, w in self.current_allocations.items():
            if w < 0 or w > 1:
                raise ValueError(
                    f"Allocation for {ac.value} must be in [0, 1], got {w}"
                )
        total = sum(self.current_allocations.values())
        if abs(total - 1) > Decimal("0.01"):
            raise ValueError(
                f"Current allocations must sum to ~1.0, got {total}"
            )
        return self
