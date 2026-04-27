"""Tests for policy allocation and goals."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.application.contracts.household import AssetClass
from src.application.contracts.policy import (
    AllocationTarget,
    BenchmarkComponent,
    CreateGoalRequest,
    DriftRequest,
    Goal,
    GoalType,
    InvestmentPolicy,
    RebalancingBand,
    UpdateGoalRequest,
)
from src.application.services.policy_service import (
    GoalNotFoundError,
    GoalsCorruptError,
    PolicyService,
    compute_drift,
    create_retirement_goal,
    create_wealth_building_goal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_D = Decimal


def _zero_alloc(
    target: Decimal = _D("0"),
    mn: Decimal = _D("0"),
    mx: Decimal = _D("0.10"),
) -> AllocationTarget:
    return AllocationTarget(target_weight=target, min_weight=mn, max_weight=mx)


def _full_allocations(
    overrides: dict[AssetClass, tuple[Decimal, Decimal, Decimal]] | None = None,
) -> dict[AssetClass, AllocationTarget]:
    """Build a valid full allocation dict with optional overrides."""
    default_min = _D("0")
    default_max = _D("0.30")
    result: dict[AssetClass, AllocationTarget] = {}
    classes = list(AssetClass)

    # Apply overrides first
    for ac in classes:
        if overrides and ac in overrides:
            t, mn, mx = overrides[ac]
            result[ac] = AllocationTarget(
                target_weight=t, min_weight=mn, max_weight=mx,
            )

    # Remaining classes get equal share of what's left
    override_total = sum(
        a.target_weight for a in result.values()
    )
    remaining = [ac for ac in classes if ac not in result]
    if remaining:
        each = (_D("1") - override_total) / len(remaining)
        for ac in remaining:
            result[ac] = AllocationTarget(
                target_weight=each,
                min_weight=default_min,
                max_weight=default_max,
            )
    return result


def _valid_policy(**kwargs: object) -> InvestmentPolicy:
    defaults: dict[str, object] = {
        "allocations": _full_allocations(),
        "liquidity_floor": _D("0"),
    }
    defaults.update(kwargs)
    return InvestmentPolicy(**defaults)  # type: ignore[arg-type]


def _valid_goal(**kwargs: object) -> Goal:
    defaults: dict[str, object] = {
        "name": "Test Goal",
        "goal_type": GoalType.WEALTH_BUILDING,
        "policy": _valid_policy(),
        "horizon_years": 20,
    }
    defaults.update(kwargs)
    return Goal(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AllocationTarget validation
# ---------------------------------------------------------------------------


class TestAllocationTarget:
    def test_valid(self) -> None:
        at = AllocationTarget(
            target_weight=_D("0.30"),
            min_weight=_D("0.20"),
            max_weight=_D("0.40"),
        )
        assert at.target_weight == _D("0.30")

    def test_min_greater_than_target_rejected(self) -> None:
        with pytest.raises(ValueError, match="min"):
            AllocationTarget(
                target_weight=_D("0.10"),
                min_weight=_D("0.20"),
                max_weight=_D("0.30"),
            )

    def test_target_greater_than_max_rejected(self) -> None:
        with pytest.raises(ValueError, match="max"):
            AllocationTarget(
                target_weight=_D("0.40"),
                min_weight=_D("0.10"),
                max_weight=_D("0.30"),
            )

    def test_negative_min_rejected(self) -> None:
        with pytest.raises(ValueError, match="min"):
            AllocationTarget(
                target_weight=_D("0.10"),
                min_weight=_D("-0.01"),
                max_weight=_D("0.20"),
            )

    def test_max_above_one_rejected(self) -> None:
        with pytest.raises(ValueError, match="max"):
            AllocationTarget(
                target_weight=_D("0.10"),
                min_weight=_D("0"),
                max_weight=_D("1.01"),
            )


# ---------------------------------------------------------------------------
# RebalancingBand validation
# ---------------------------------------------------------------------------


class TestRebalancingBand:
    def test_valid(self) -> None:
        b = RebalancingBand(threshold=_D("0.03"))
        assert b.threshold == _D("0.03")

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RebalancingBand(threshold=_D("0"))

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RebalancingBand(threshold=_D("-0.01"))


# ---------------------------------------------------------------------------
# BenchmarkComponent validation
# ---------------------------------------------------------------------------


class TestBenchmarkComponent:
    def test_ticker_uppercased(self) -> None:
        c = BenchmarkComponent(ticker="spy", weight=_D("0.60"))
        assert c.ticker == "SPY"

    def test_negative_weight_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            BenchmarkComponent(ticker="SPY", weight=_D("-0.01"))


# ---------------------------------------------------------------------------
# InvestmentPolicy validation
# ---------------------------------------------------------------------------


class TestInvestmentPolicy:
    def test_valid_policy(self) -> None:
        p = _valid_policy()
        assert len(p.allocations) == 9

    def test_missing_asset_class_rejected(self) -> None:
        alloc = _full_allocations()
        del alloc[AssetClass.TIPS]
        with pytest.raises(ValueError, match="Missing allocations"):
            InvestmentPolicy(
                allocations=alloc, liquidity_floor=_D("0"),
            )

    def test_weights_not_summing_to_one_rejected(self) -> None:
        alloc = _full_allocations()
        alloc[AssetClass.US_EQUITY] = AllocationTarget(
            target_weight=_D("0.50"),
            min_weight=_D("0"),
            max_weight=_D("0.60"),
        )
        with pytest.raises(ValueError, match="sum to 1.0"):
            InvestmentPolicy(
                allocations=alloc, liquidity_floor=_D("0"),
            )

    def test_infeasible_min_unreachable_with_valid_targets(self) -> None:
        # sum(min) > 1 is impossible with valid AllocationTargets where
        # min<=target and targets sum to 1. Use model_construct on both
        # AllocationTarget and InvestmentPolicy, then call the validator.
        alloc = {
            ac: AllocationTarget.model_construct(
                target_weight=_D("1") / 9,
                min_weight=_D("0.12"),  # 9*0.12=1.08 > 1
                max_weight=_D("0.30"),
            )
            for ac in AssetClass
        }
        policy = InvestmentPolicy.model_construct(
            allocations=alloc,
            rebalancing_bands={},
            benchmark_blend=[],
            risk_budget=None,
            liquidity_floor=_D("0"),
        )
        with pytest.raises(ValueError, match="infeasible"):
            policy._policy_invariants()

    def test_infeasible_max_unreachable_with_valid_targets(self) -> None:
        # sum(max) < 1 is impossible with valid AllocationTargets where
        # target<=max and targets sum to 1. Bypass via model_construct.
        alloc = {
            ac: AllocationTarget.model_construct(
                target_weight=_D("1") / 9,
                min_weight=_D("0"),
                max_weight=_D("0.10"),  # 9*0.10=0.90 < 1
            )
            for ac in AssetClass
        }
        policy = InvestmentPolicy.model_construct(
            allocations=alloc,
            rebalancing_bands={},
            benchmark_blend=[],
            risk_budget=None,
            liquidity_floor=_D("0"),
        )
        with pytest.raises(ValueError, match="infeasible"):
            policy._policy_invariants()

    def test_cash_below_liquidity_floor_rejected(self) -> None:
        alloc = _full_allocations({
            AssetClass.CASH_MONEY_MARKET: (
                _D("0.12"), _D("0.02"), _D("0.20"),
            ),
        })
        with pytest.raises(ValueError, match="liquidity_floor"):
            InvestmentPolicy(
                allocations=alloc,
                liquidity_floor=_D("0.05"),
            )

    def test_benchmark_weights_not_summing_rejected(self) -> None:
        with pytest.raises(ValueError, match="Benchmark weights"):
            _valid_policy(
                benchmark_blend=[
                    BenchmarkComponent(ticker="SPY", weight=_D("0.50")),
                    BenchmarkComponent(ticker="AGG", weight=_D("0.30")),
                ],
            )

    def test_benchmark_duplicate_tickers_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            _valid_policy(
                benchmark_blend=[
                    BenchmarkComponent(ticker="SPY", weight=_D("0.50")),
                    BenchmarkComponent(ticker="SPY", weight=_D("0.50")),
                ],
            )

    def test_valid_benchmark(self) -> None:
        p = _valid_policy(
            benchmark_blend=[
                BenchmarkComponent(ticker="SPY", weight=_D("0.60")),
                BenchmarkComponent(ticker="AGG", weight=_D("0.40")),
            ],
        )
        assert len(p.benchmark_blend) == 2

    def test_default_rebalancing_bands_populated(self) -> None:
        p = _valid_policy()
        assert len(p.rebalancing_bands) == 9
        for ac in AssetClass:
            assert ac in p.rebalancing_bands


# ---------------------------------------------------------------------------
# Goal validation
# ---------------------------------------------------------------------------


class TestGoal:
    def test_valid_wealth_building(self) -> None:
        g = _valid_goal()
        assert g.goal_type == GoalType.WEALTH_BUILDING

    def test_retirement_requires_withdrawal_rate(self) -> None:
        with pytest.raises(ValueError, match="withdrawal_rate"):
            _valid_goal(goal_type=GoalType.RETIREMENT)

    def test_retirement_with_withdrawal_rate(self) -> None:
        g = _valid_goal(
            goal_type=GoalType.RETIREMENT,
            withdrawal_rate=_D("0.04"),
        )
        assert g.withdrawal_rate == _D("0.04")

    def test_wealth_building_rejects_withdrawal_rate(self) -> None:
        with pytest.raises(ValueError, match="should not have"):
            _valid_goal(withdrawal_rate=_D("0.04"))

    def test_zero_horizon_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _valid_goal(horizon_years=0)

    def test_negative_target_amount_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            _valid_goal(target_amount=_D("-1000"))

    def test_negative_inflation_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            _valid_goal(inflation_assumption=_D("-0.01"))

    def test_id_auto_generated(self) -> None:
        g1 = _valid_goal()
        g2 = _valid_goal()
        assert g1.id != g2.id
        assert len(g1.id) == 12


# ---------------------------------------------------------------------------
# Canned goal factories
# ---------------------------------------------------------------------------


class TestCannedGoals:
    def test_retirement_goal(self) -> None:
        g = create_retirement_goal()
        assert g.goal_type == GoalType.RETIREMENT
        assert g.withdrawal_rate == _D("0.035")
        assert g.horizon_years == 30
        total = sum(
            a.target_weight for a in g.policy.allocations.values()
        )
        assert abs(total - 1) < _D("0.001")

    def test_wealth_building_goal(self) -> None:
        g = create_wealth_building_goal()
        assert g.goal_type == GoalType.WEALTH_BUILDING
        assert g.withdrawal_rate is None
        assert g.horizon_years == 20
        total = sum(
            a.target_weight for a in g.policy.allocations.values()
        )
        assert abs(total - 1) < _D("0.001")

    def test_retirement_benchmark_sums_to_one(self) -> None:
        g = create_retirement_goal()
        bw = sum(c.weight for c in g.policy.benchmark_blend)
        assert abs(bw - 1) < _D("0.001")

    def test_wealth_building_benchmark_sums_to_one(self) -> None:
        g = create_wealth_building_goal()
        bw = sum(c.weight for c in g.policy.benchmark_blend)
        assert abs(bw - 1) < _D("0.001")

    def test_retirement_custom_name(self) -> None:
        g = create_retirement_goal(name="My Retirement")
        assert g.name == "My Retirement"


# ---------------------------------------------------------------------------
# Drift computation
# ---------------------------------------------------------------------------


class TestDriftComputation:
    def test_no_drift_when_on_target(self) -> None:
        policy = _valid_policy(
            rebalancing_bands={ac: RebalancingBand() for ac in AssetClass},
        )
        current = {
            ac: policy.allocations[ac].target_weight
            for ac in AssetClass
        }
        report = compute_drift(policy, current)
        assert not report.any_breach
        assert report.total_drift == _D("0")
        for d in report.drifts:
            assert d.drift == _D("0")

    def test_overweight_detected(self) -> None:
        policy = _valid_policy(
            rebalancing_bands={ac: RebalancingBand() for ac in AssetClass},
        )
        current = {
            ac: policy.allocations[ac].target_weight
            for ac in AssetClass
        }
        # Overweight US_EQUITY by 10pp
        current[AssetClass.US_EQUITY] += _D("0.10")
        current[AssetClass.CASH_MONEY_MARKET] -= _D("0.10")
        report = compute_drift(policy, current)
        eq_drift = next(
            d for d in report.drifts
            if d.asset_class == AssetClass.US_EQUITY
        )
        assert eq_drift.drift == _D("0.10")
        assert eq_drift.breaches_band is True
        assert report.any_breach is True

    def test_small_drift_no_breach(self) -> None:
        policy = _valid_policy(
            rebalancing_bands={ac: RebalancingBand() for ac in AssetClass},
        )
        current = {
            ac: policy.allocations[ac].target_weight
            for ac in AssetClass
        }
        # Small drift: 2pp (below default 5pp threshold)
        current[AssetClass.US_EQUITY] += _D("0.02")
        current[AssetClass.CASH_MONEY_MARKET] -= _D("0.02")
        report = compute_drift(policy, current)
        assert not report.any_breach

    def test_missing_class_treated_as_zero(self) -> None:
        policy = _valid_policy(
            rebalancing_bands={ac: RebalancingBand() for ac in AssetClass},
        )
        # Only provide US_EQUITY
        report = compute_drift(
            policy, {AssetClass.US_EQUITY: _D("1.0")},
        )
        assert report.any_breach  # Everything else drifted

    def test_total_drift_sum_of_absolutes(self) -> None:
        policy = _valid_policy(
            rebalancing_bands={ac: RebalancingBand() for ac in AssetClass},
        )
        current = {
            ac: policy.allocations[ac].target_weight
            for ac in AssetClass
        }
        current[AssetClass.US_EQUITY] += _D("0.03")
        current[AssetClass.US_TREASURIES] -= _D("0.03")
        report = compute_drift(policy, current)
        assert report.total_drift >= _D("0.06")

    def test_drift_request_negative_weight_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            DriftRequest(
                current_allocations={AssetClass.US_EQUITY: _D("-0.10")},
            )

    def test_drift_request_weight_above_one_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            DriftRequest(
                current_allocations={AssetClass.US_EQUITY: _D("1.50")},
            )


# ---------------------------------------------------------------------------
# PolicyService persistence
# ---------------------------------------------------------------------------


class TestPolicyService:
    def test_list_goals_empty(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        assert svc.list_goals() == []

    def test_create_and_get(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        req = CreateGoalRequest(
            name="Test",
            goal_type=GoalType.WEALTH_BUILDING,
            policy=_valid_policy(),
            horizon_years=20,
        )
        goal = svc.create_goal(req)
        assert goal.name == "Test"
        retrieved = svc.get_goal(goal.id)
        assert retrieved.id == goal.id

    def test_create_from_template_retirement(
        self, tmp_path: Path,
    ) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        goal = svc.create_from_template(GoalType.RETIREMENT)
        assert goal.goal_type == GoalType.RETIREMENT
        assert goal.withdrawal_rate is not None
        assert svc.get_goal(goal.id).id == goal.id

    def test_create_from_template_wealth(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        goal = svc.create_from_template(GoalType.WEALTH_BUILDING)
        assert goal.goal_type == GoalType.WEALTH_BUILDING

    def test_create_from_template_custom_rejected(
        self, tmp_path: Path,
    ) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        with pytest.raises(ValueError, match="No template"):
            svc.create_from_template(GoalType.CUSTOM)

    def test_update_goal(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        goal = svc.create_from_template(GoalType.WEALTH_BUILDING)
        updated = svc.update_goal(
            goal.id,
            UpdateGoalRequest(name="Updated Name", horizon_years=25),
        )
        assert updated.name == "Updated Name"
        assert updated.horizon_years == 25
        assert updated.updated_at > goal.created_at

    def test_update_nonexistent_raises(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        with pytest.raises(GoalNotFoundError):
            svc.update_goal("nope", UpdateGoalRequest(name="x"))

    def test_delete_goal(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        goal = svc.create_from_template(GoalType.RETIREMENT)
        assert svc.delete_goal(goal.id) is True
        with pytest.raises(GoalNotFoundError):
            svc.get_goal(goal.id)

    def test_delete_nonexistent_raises(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        with pytest.raises(GoalNotFoundError):
            svc.delete_goal("nope")

    def test_persistence_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "goals.json"
        svc = PolicyService(path=path)
        svc.create_from_template(GoalType.RETIREMENT)
        svc.create_from_template(GoalType.WEALTH_BUILDING)

        # Reload from disk
        svc2 = PolicyService(path=path)
        goals = svc2.list_goals()
        assert len(goals) == 2

    def test_corrupt_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "goals.json"
        path.write_text("not json!", encoding="utf-8")
        svc = PolicyService(path=path)
        with pytest.raises(GoalsCorruptError):
            svc.load()

    def test_file_permissions(self, tmp_path: Path) -> None:
        path = tmp_path / "goals.json"
        svc = PolicyService(path=path)
        svc.create_from_template(GoalType.RETIREMENT)
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_compute_drift_via_service(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        goal = svc.create_from_template(GoalType.RETIREMENT)
        current = {
            ac: goal.policy.allocations[ac].target_weight
            for ac in AssetClass
        }
        req = DriftRequest(current_allocations=current)
        report = svc.compute_drift(goal.id, req)
        assert not report.any_breach

    def test_list_goals_sorted_by_name(self, tmp_path: Path) -> None:
        svc = PolicyService(path=tmp_path / "goals.json")
        svc.create_from_template(GoalType.WEALTH_BUILDING)
        svc.create_from_template(GoalType.RETIREMENT)
        goals = svc.list_goals()
        assert goals[0].name < goals[1].name

    def test_schema_version_preserved(self, tmp_path: Path) -> None:
        path = tmp_path / "goals.json"
        svc = PolicyService(path=path)
        svc.create_from_template(GoalType.RETIREMENT)
        raw = json.loads(path.read_text())
        assert raw["schema_version"] == 1
