"""Policy & goal persistence — load, save, CRUD, drift computation.

Storage location: ~/.config/finance-os/goals.json

Uses OS-level file locking (``fcntl.flock``) to protect against
concurrent writes from Web API, MCP server, and CLI processes.
"""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from src.application.config import CONFIG_DIR
from src.application.contracts.household import AssetClass
from src.application.contracts.policy import (
    AllocationTarget,
    BenchmarkComponent,
    CreateGoalRequest,
    DriftReport,
    DriftRequest,
    DriftResult,
    Goal,
    GoalsFile,
    GoalType,
    InvestmentPolicy,
    RebalancingBand,
    UpdateGoalRequest,
)
from src.core.file_io import FileLockContext, atomic_write

logger = logging.getLogger(__name__)

GOALS_FILE = CONFIG_DIR / "goals.json"
LOCK_FILE = CONFIG_DIR / "goals.lock"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GoalNotFoundError(Exception):
    """Raised when a goal ID does not exist."""


class GoalsCorruptError(Exception):
    """Raised when goals.json cannot be parsed."""


# ---------------------------------------------------------------------------
# Canned goal factories
# ---------------------------------------------------------------------------


def _all_class_allocations(
    targets: dict[AssetClass, tuple[Decimal, Decimal, Decimal]],
) -> dict[AssetClass, AllocationTarget]:
    """Build a complete allocation dict from (target, min, max) tuples.

    Any asset class not in ``targets`` gets a zero allocation.
    """
    result: dict[AssetClass, AllocationTarget] = {}
    for ac in AssetClass:
        if ac in targets:
            t, mn, mx = targets[ac]
            result[ac] = AllocationTarget(
                target_weight=t, min_weight=mn, max_weight=mx,
            )
        else:
            result[ac] = AllocationTarget(
                target_weight=Decimal("0"),
                min_weight=Decimal("0"),
                max_weight=Decimal("0.10"),
            )
    return result


def _default_bands() -> dict[AssetClass, RebalancingBand]:
    return {ac: RebalancingBand() for ac in AssetClass}


def create_retirement_goal(name: str = "Retirement") -> Goal:
    """Conservative allocation: capital preservation + income."""
    alloc = _all_class_allocations({
        AssetClass.US_EQUITY: (Decimal("0.25"), Decimal("0.15"), Decimal("0.35")),
        AssetClass.INTL_DEVELOPED: (Decimal("0.10"), Decimal("0.05"), Decimal("0.15")),
        AssetClass.EMERGING_MARKETS: (Decimal("0.05"), Decimal("0"), Decimal("0.10")),
        AssetClass.US_TREASURIES: (Decimal("0.20"), Decimal("0.10"), Decimal("0.30")),
        AssetClass.IG_CORPORATE: (Decimal("0.15"), Decimal("0.05"), Decimal("0.25")),
        AssetClass.HIGH_YIELD: (Decimal("0"), Decimal("0"), Decimal("0.05")),
        AssetClass.TIPS: (Decimal("0.10"), Decimal("0.05"), Decimal("0.15")),
        AssetClass.REAL_ASSETS: (Decimal("0.05"), Decimal("0"), Decimal("0.10")),
        AssetClass.CASH_MONEY_MARKET: (Decimal("0.10"), Decimal("0.05"), Decimal("0.15")),
    })
    policy = InvestmentPolicy(
        allocations=alloc,
        rebalancing_bands=_default_bands(),
        benchmark_blend=[
            BenchmarkComponent(ticker="VTI", weight=Decimal("0.30")),
            BenchmarkComponent(ticker="VXUS", weight=Decimal("0.10")),
            BenchmarkComponent(ticker="BND", weight=Decimal("0.35")),
            BenchmarkComponent(ticker="TIP", weight=Decimal("0.10")),
            BenchmarkComponent(ticker="VNQ", weight=Decimal("0.05")),
            BenchmarkComponent(ticker="VMFXX", weight=Decimal("0.10")),
        ],
        liquidity_floor=Decimal("0.05"),
    )
    return Goal(
        name=name,
        goal_type=GoalType.RETIREMENT,
        policy=policy,
        horizon_years=30,
        withdrawal_rate=Decimal("0.035"),
        inflation_assumption=Decimal("0.025"),
    )


def create_wealth_building_goal(
    name: str = "Wealth Building",
) -> Goal:
    """Growth-tilted allocation: higher equity, longer horizon."""
    alloc = _all_class_allocations({
        AssetClass.US_EQUITY: (Decimal("0.40"), Decimal("0.30"), Decimal("0.50")),
        AssetClass.INTL_DEVELOPED: (Decimal("0.15"), Decimal("0.10"), Decimal("0.25")),
        AssetClass.EMERGING_MARKETS: (Decimal("0.10"), Decimal("0.05"), Decimal("0.15")),
        AssetClass.US_TREASURIES: (Decimal("0.10"), Decimal("0.05"), Decimal("0.20")),
        AssetClass.IG_CORPORATE: (Decimal("0.05"), Decimal("0"), Decimal("0.15")),
        AssetClass.HIGH_YIELD: (Decimal("0.05"), Decimal("0"), Decimal("0.10")),
        AssetClass.TIPS: (Decimal("0"), Decimal("0"), Decimal("0.10")),
        AssetClass.REAL_ASSETS: (Decimal("0.10"), Decimal("0.05"), Decimal("0.15")),
        AssetClass.CASH_MONEY_MARKET: (Decimal("0.05"), Decimal("0.05"), Decimal("0.10")),
    })
    policy = InvestmentPolicy(
        allocations=alloc,
        rebalancing_bands=_default_bands(),
        benchmark_blend=[
            BenchmarkComponent(ticker="VTI", weight=Decimal("0.40")),
            BenchmarkComponent(ticker="VXUS", weight=Decimal("0.20")),
            BenchmarkComponent(ticker="BND", weight=Decimal("0.15")),
            BenchmarkComponent(ticker="VNQ", weight=Decimal("0.10")),
            BenchmarkComponent(ticker="VWO", weight=Decimal("0.10")),
            BenchmarkComponent(ticker="VMFXX", weight=Decimal("0.05")),
        ],
        liquidity_floor=Decimal("0.05"),
    )
    return Goal(
        name=name,
        goal_type=GoalType.WEALTH_BUILDING,
        policy=policy,
        horizon_years=20,
        inflation_assumption=Decimal("0.025"),
    )


# ---------------------------------------------------------------------------
# Drift computation (pure math)
# ---------------------------------------------------------------------------


def compute_drift(
    policy: InvestmentPolicy,
    current_allocations: dict[AssetClass, Decimal],
) -> DriftReport:
    """Compute per-class drift from target allocation.

    ``current_allocations`` values should sum to ~1.0.
    Missing classes are treated as 0 current weight.
    """
    drifts: list[DriftResult] = []
    for ac in AssetClass:
        target = policy.allocations[ac].target_weight
        current = current_allocations.get(ac, Decimal("0"))
        drift = current - target
        band = (policy.rebalancing_bands or {}).get(ac)
        breaches = abs(drift) > band.threshold if band else False
        drifts.append(DriftResult(
            asset_class=ac,
            target_weight=target,
            current_weight=current,
            drift=drift,
            breaches_band=breaches,
        ))
    total_drift = sum(abs(d.drift) for d in drifts)
    return DriftReport(
        drifts=drifts,
        any_breach=any(d.breaches_band for d in drifts),
        total_drift=total_drift,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PolicyService:
    """Manages goal persistence with OS-level file locking."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or GOALS_FILE
        self._lock_path = (
            path.parent / "goals.lock" if path else LOCK_FILE
        )
        self._cached_data: GoalsFile | None = None
        self._cached_mtime_ns: int = 0

    def _flock(self) -> FileLockContext:
        return FileLockContext(self._lock_path)

    def _load_unlocked(self) -> GoalsFile:
        """Load goals without acquiring lock (caller must hold lock).

        Uses mtime-based caching to avoid redundant disk reads.
        """
        if not self._path.exists():
            return GoalsFile()
        try:
            mtime_ns = self._path.stat().st_mtime_ns
            if self._cached_data is not None and mtime_ns == self._cached_mtime_ns:
                return self._cached_data.model_copy(deep=True)
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            data = GoalsFile.model_validate(raw)
            self._cached_data = data
            self._cached_mtime_ns = mtime_ns
            return data
        except (json.JSONDecodeError, ValidationError, OSError) as exc:
            logger.error("Corrupt goals file %s: %s", self._path, exc)
            raise GoalsCorruptError(str(exc)) from exc

    def _write_atomic(self, data: GoalsFile) -> None:
        """Atomic write with fsync (caller must hold lock)."""
        content = data.model_dump_json(indent=2).encode("utf-8")
        atomic_write(self._path, content)
        # Update mtime cache after successful write
        self._cached_data = data
        try:
            self._cached_mtime_ns = self._path.stat().st_mtime_ns
        except OSError:
            self._cached_mtime_ns = 0

    # -- public API --------------------------------------------------------

    def load(self) -> GoalsFile:
        """Load all goals from disk."""
        with self._flock():
            return self._load_unlocked()

    def list_goals(self) -> list[Goal]:
        """Return all goals sorted by name."""
        data = self.load()
        return sorted(data.goals.values(), key=lambda g: g.name)

    def get_goal(self, goal_id: str) -> Goal:
        """Get a single goal by ID."""
        data = self.load()
        goal = data.goals.get(goal_id)
        if goal is None:
            raise GoalNotFoundError(f"Goal '{goal_id}' not found")
        return goal

    def create_goal(self, request: CreateGoalRequest) -> Goal:
        """Create a new goal and persist."""
        goal = Goal(
            name=request.name,
            goal_type=request.goal_type,
            policy=request.policy,
            horizon_years=request.horizon_years,
            target_amount=request.target_amount,
            withdrawal_rate=request.withdrawal_rate,
            inflation_assumption=request.inflation_assumption,
            notes=request.notes,
        )
        with self._flock():
            data = self._load_unlocked()
            data.goals[goal.id] = goal
            self._write_atomic(data)
        return goal

    def create_from_template(self, goal_type: GoalType) -> Goal:
        """Create a goal from a canned template."""
        if goal_type == GoalType.RETIREMENT:
            goal = create_retirement_goal()
        elif goal_type == GoalType.WEALTH_BUILDING:
            goal = create_wealth_building_goal()
        else:
            raise ValueError(
                f"No template for goal_type '{goal_type}'. "
                "Use 'retirement' or 'wealth_building'."
            )
        with self._flock():
            data = self._load_unlocked()
            data.goals[goal.id] = goal
            self._write_atomic(data)
        return goal

    def update_goal(
        self, goal_id: str, request: UpdateGoalRequest,
    ) -> Goal:
        """Update an existing goal (partial update)."""
        with self._flock():
            data = self._load_unlocked()
            goal = data.goals.get(goal_id)
            if goal is None:
                raise GoalNotFoundError(f"Goal '{goal_id}' not found")

            updates: dict[str, object] = {}
            for field in (
                "name", "policy", "horizon_years", "target_amount",
                "withdrawal_rate", "inflation_assumption", "notes",
            ):
                if field in request.model_fields_set:
                    updates[field] = getattr(request, field)
            updates["updated_at"] = datetime.now(UTC)

            updated = goal.model_copy(update=updates)
            # Re-validate all Goal invariants (including field validators)
            updated = Goal.model_validate(updated.model_dump())
            data.goals[goal_id] = updated
            self._write_atomic(data)
        return updated

    def delete_goal(self, goal_id: str) -> bool:
        """Delete a goal. Raises GoalNotFoundError if missing."""
        with self._flock():
            data = self._load_unlocked()
            if goal_id not in data.goals:
                raise GoalNotFoundError(f"Goal '{goal_id}' not found")
            del data.goals[goal_id]
            self._write_atomic(data)
        return True

    def compute_drift(
        self, goal_id: str, request: DriftRequest,
    ) -> DriftReport:
        """Compute drift for a goal against current allocations."""
        goal = self.get_goal(goal_id)
        return compute_drift(goal.policy, request.current_allocations)
