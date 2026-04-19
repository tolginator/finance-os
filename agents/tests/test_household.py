"""Tests for household portfolio model — contracts, service, and math helpers."""

import json
import os
import textwrap
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.contracts.household import (
    Account,
    AccountType,
    AssetClass,
    CashFlowAssumption,
    CashFlowType,
    CashHolding,
    Household,
    ImportPreviewRequest,
    TaxLot,
    UpdateHouseholdRequest,
)
from src.application.household_math import (
    aggregate_lots,
    cost_basis_by_ticker,
    has_complete_lots,
    household_summary,
    liquidity_reserve_cash,
    lot_count,
    total_cash,
    total_cash_household,
    total_cost_basis,
    unique_tickers,
)
from src.application.services.household_service import (
    HouseholdCorruptError,
    HouseholdService,
    StaleRevisionError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_lot() -> TaxLot:
    return TaxLot(
        ticker="VTI",
        shares=Decimal("100"),
        cost_basis_per_share=Decimal("200.50"),
        purchase_date=date(2023, 1, 15),
    )


@pytest.fixture()
def sample_cash() -> CashHolding:
    return CashHolding(
        amount=Decimal("50000"),
        valuation_date=date(2024, 1, 1),
        is_money_market=False,
        counts_toward_liquidity_reserve=True,
    )


@pytest.fixture()
def sample_account(sample_lot: TaxLot, sample_cash: CashHolding) -> Account:
    return Account(
        name="Taxable Brokerage",
        account_type=AccountType.TAXABLE,
        tax_lots=[sample_lot],
        cash_holdings=[sample_cash],
    )


@pytest.fixture()
def sample_household(sample_account: Account) -> Household:
    return Household(
        name="Test Household",
        accounts=[sample_account],
        liquidity_reserve_floor=Decimal("25000"),
    )


@pytest.fixture()
def tmp_household_path(tmp_path: Path) -> Path:
    return tmp_path / "household.json"


@pytest.fixture()
def service(tmp_household_path: Path) -> HouseholdService:
    return HouseholdService(path=tmp_household_path)


# ---------------------------------------------------------------------------
# Contract validation tests
# ---------------------------------------------------------------------------


class TestTaxLot:
    def test_valid_lot(self, sample_lot: TaxLot) -> None:
        assert sample_lot.ticker == "VTI"
        assert sample_lot.shares == Decimal("100")

    def test_ticker_uppercased(self) -> None:
        lot = TaxLot(
            ticker="vti",
            shares=Decimal("10"),
            cost_basis_per_share=Decimal("100"),
            purchase_date=date(2023, 1, 1),
        )
        assert lot.ticker == "VTI"

    def test_negative_shares_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxLot(
                ticker="VTI",
                shares=Decimal("-1"),
                cost_basis_per_share=Decimal("100"),
                purchase_date=date(2023, 1, 1),
            )

    def test_zero_shares_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxLot(
                ticker="VTI",
                shares=Decimal("0"),
                cost_basis_per_share=Decimal("100"),
                purchase_date=date(2023, 1, 1),
            )

    def test_negative_cost_basis_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaxLot(
                ticker="VTI",
                shares=Decimal("10"),
                cost_basis_per_share=Decimal("-5"),
                purchase_date=date(2023, 1, 1),
            )


class TestCashHolding:
    def test_valid_cash(self, sample_cash: CashHolding) -> None:
        assert sample_cash.amount == Decimal("50000")
        assert sample_cash.counts_toward_liquidity_reserve is True

    def test_money_market_with_ticker(self) -> None:
        ch = CashHolding(
            amount=Decimal("100000"),
            valuation_date=date(2024, 6, 1),
            is_money_market=True,
            ticker="VMFXX",
        )
        assert ch.ticker == "VMFXX"
        assert ch.is_money_market is True

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CashHolding(
                amount=Decimal("-100"),
                valuation_date=date(2024, 1, 1),
            )


class TestAccount:
    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Account(name="", account_type=AccountType.TAXABLE)

    def test_valid_account(self, sample_account: Account) -> None:
        assert sample_account.account_type == AccountType.TAXABLE
        assert len(sample_account.tax_lots) == 1
        assert len(sample_account.cash_holdings) == 1


class TestHousehold:
    def test_defaults(self) -> None:
        h = Household(name="Test")
        assert h.schema_version == 1
        assert h.revision == 0
        assert h.accounts == []
        assert h.liquidity_reserve_floor == Decimal("0")

    def test_valid_household(self, sample_household: Household) -> None:
        assert sample_household.name == "Test Household"
        assert len(sample_household.accounts) == 1

    def test_roundtrip_json(self, sample_household: Household) -> None:
        dumped = sample_household.model_dump(mode="json")
        restored = Household.model_validate(dumped)
        assert restored.name == sample_household.name
        assert len(restored.accounts) == len(sample_household.accounts)
        lot = restored.accounts[0].tax_lots[0]
        assert lot.shares == Decimal("100")
        assert lot.cost_basis_per_share == Decimal("200.50")


class TestCashFlowAssumption:
    def test_valid_flow(self) -> None:
        cf = CashFlowAssumption(
            description="Annual savings",
            amount_annual=Decimal("50000"),
            flow_type=CashFlowType.CONTRIBUTION,
            start_year=2024,
            end_year=2044,
        )
        assert cf.inflation_adjusted is True  # default

    def test_start_year_below_minimum(self) -> None:
        with pytest.raises(ValidationError):
            CashFlowAssumption(
                description="Bad year",
                amount_annual=Decimal("1000"),
                flow_type=CashFlowType.WITHDRAWAL,
                start_year=1990,
            )

    def test_end_year_before_start_year(self) -> None:
        with pytest.raises(ValidationError):
            CashFlowAssumption(
                description="Bad range",
                amount_annual=Decimal("1000"),
                flow_type=CashFlowType.WITHDRAWAL,
                start_year=2030,
                end_year=2025,
            )


class TestAssetClassEnum:
    def test_all_nine_classes(self) -> None:
        assert len(AssetClass) == 9

    def test_values(self) -> None:
        assert AssetClass.US_EQUITY.value == "us_equity"
        assert AssetClass.CASH_MONEY_MARKET.value == "cash_money_market"


class TestAccountTypeEnum:
    def test_all_six_types(self) -> None:
        assert len(AccountType) == 6

    def test_401k(self) -> None:
        assert AccountType.FOUR01K.value == "401k"


# ---------------------------------------------------------------------------
# Math helper tests
# ---------------------------------------------------------------------------


class TestHouseholdMath:
    def test_total_cash(self, sample_account: Account) -> None:
        assert total_cash(sample_account) == Decimal("50000")

    def test_total_cash_household(self, sample_household: Household) -> None:
        assert total_cash_household(sample_household) == Decimal("50000")

    def test_liquidity_reserve_cash(self, sample_household: Household) -> None:
        assert liquidity_reserve_cash(sample_household) == Decimal("50000")

    def test_liquidity_reserve_excludes_non_reserve(self) -> None:
        account = Account(
            name="Test",
            account_type=AccountType.TAXABLE,
            cash_holdings=[
                CashHolding(
                    amount=Decimal("10000"),
                    valuation_date=date(2024, 1, 1),
                    counts_toward_liquidity_reserve=True,
                ),
                CashHolding(
                    amount=Decimal("5000"),
                    valuation_date=date(2024, 1, 1),
                    counts_toward_liquidity_reserve=False,
                ),
            ],
        )
        h = Household(name="Test", accounts=[account])
        assert liquidity_reserve_cash(h) == Decimal("10000")

    def test_aggregate_lots(self) -> None:
        lots = [
            TaxLot(
                ticker="VTI",
                shares=Decimal("50"),
                cost_basis_per_share=Decimal("200"),
                purchase_date=date(2023, 1, 1),
            ),
            TaxLot(
                ticker="VTI",
                shares=Decimal("30"),
                cost_basis_per_share=Decimal("210"),
                purchase_date=date(2023, 6, 1),
            ),
            TaxLot(
                ticker="VXUS",
                shares=Decimal("100"),
                cost_basis_per_share=Decimal("55"),
                purchase_date=date(2023, 3, 1),
            ),
        ]
        agg = aggregate_lots(lots)
        assert agg["VTI"] == Decimal("80")
        assert agg["VXUS"] == Decimal("100")

    def test_total_cost_basis(self) -> None:
        lots = [
            TaxLot(
                ticker="VTI",
                shares=Decimal("10"),
                cost_basis_per_share=Decimal("200"),
                purchase_date=date(2023, 1, 1),
            ),
            TaxLot(
                ticker="VTI",
                shares=Decimal("5"),
                cost_basis_per_share=Decimal("210"),
                purchase_date=date(2023, 6, 1),
            ),
        ]
        # 10 * 200 + 5 * 210 = 2000 + 1050 = 3050
        assert total_cost_basis(lots) == Decimal("3050")

    def test_cost_basis_by_ticker(self) -> None:
        lots = [
            TaxLot(
                ticker="VTI",
                shares=Decimal("10"),
                cost_basis_per_share=Decimal("200"),
                purchase_date=date(2023, 1, 1),
            ),
            TaxLot(
                ticker="VXUS",
                shares=Decimal("20"),
                cost_basis_per_share=Decimal("50"),
                purchase_date=date(2023, 3, 1),
            ),
        ]
        basis = cost_basis_by_ticker(lots)
        assert basis["VTI"] == Decimal("2000")
        assert basis["VXUS"] == Decimal("1000")

    def test_household_summary(self, sample_household: Household) -> None:
        summary = household_summary(sample_household)
        assert "Taxable Brokerage" in summary
        acct = summary["Taxable Brokerage"]
        assert acct["VTI"] == Decimal("100")
        assert acct["_cash"] == Decimal("50000")

    def test_lot_count(self, sample_household: Household) -> None:
        assert lot_count(sample_household) == 1

    def test_unique_tickers(self, sample_household: Household) -> None:
        assert unique_tickers(sample_household) == {"VTI"}

    def test_has_complete_lots_true(self, sample_household: Household) -> None:
        assert has_complete_lots(sample_household) is True

    def test_has_complete_lots_false_zero_basis(self) -> None:
        lot = TaxLot(
            ticker="VTI",
            shares=Decimal("10"),
            cost_basis_per_share=Decimal("0"),
            purchase_date=date(2024, 1, 1),
        )
        h = Household(
            name="Test",
            accounts=[Account(name="A", account_type=AccountType.TAXABLE, tax_lots=[lot])],
        )
        assert has_complete_lots(h) is False

    def test_empty_household_math(self) -> None:
        h = Household(name="Empty")
        assert total_cash_household(h) == Decimal("0")
        assert liquidity_reserve_cash(h) == Decimal("0")
        assert lot_count(h) == 0
        assert unique_tickers(h) == set()
        assert has_complete_lots(h) is True  # vacuously true


# ---------------------------------------------------------------------------
# Household service tests
# ---------------------------------------------------------------------------


class TestHouseholdService:
    def test_load_no_file(self, service: HouseholdService) -> None:
        household, exists = service.load()
        assert exists is False
        assert household.name == "My Household"
        assert household.revision == 0

    def test_save_and_load(
        self,
        service: HouseholdService,
        sample_account: Account,
    ) -> None:
        req = UpdateHouseholdRequest(
            name="Acar Family",
            accounts=[sample_account],
            liquidity_reserve_floor=Decimal("25000"),
            expected_revision=0,
        )
        saved, summary = service.save(req)
        assert saved.revision == 1
        assert saved.name == "Acar Family"
        assert "rev 0 → 1" in summary

        loaded, exists = service.load()
        assert exists is True
        assert loaded.name == "Acar Family"
        assert loaded.revision == 1
        assert len(loaded.accounts) == 1
        # Verify Decimal precision round-trips
        lot = loaded.accounts[0].tax_lots[0]
        assert lot.cost_basis_per_share == Decimal("200.50")

    def test_optimistic_concurrency_reject(
        self,
        service: HouseholdService,
        sample_account: Account,
    ) -> None:
        # First save succeeds (revision 0 → 1)
        req1 = UpdateHouseholdRequest(
            name="First",
            accounts=[sample_account],
            expected_revision=0,
        )
        service.save(req1)

        # Second save with stale revision 0 → StaleRevisionError
        req2 = UpdateHouseholdRequest(
            name="Stale",
            accounts=[],
            expected_revision=0,
        )
        with pytest.raises(StaleRevisionError):
            service.save(req2)

    def test_optimistic_concurrency_accept(
        self,
        service: HouseholdService,
        sample_account: Account,
    ) -> None:
        req1 = UpdateHouseholdRequest(
            name="First",
            accounts=[sample_account],
            expected_revision=0,
        )
        service.save(req1)

        req2 = UpdateHouseholdRequest(
            name="Second",
            accounts=[],
            expected_revision=1,
        )
        saved, _ = service.save(req2)
        assert saved.revision == 2
        assert saved.name == "Second"

    def test_journal_written(
        self,
        service: HouseholdService,
        tmp_path: Path,
    ) -> None:
        req = UpdateHouseholdRequest(
            name="Journal Test",
            accounts=[],
            expected_revision=0,
        )
        service.save(req)

        journal_path = tmp_path / "household-journal.jsonl"
        assert journal_path.is_file()
        lines = journal_path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "update"
        assert entry["base_revision"] == 0
        assert entry["new_revision"] == 1

    def test_corrupt_file_preserved(
        self,
        service: HouseholdService,
        tmp_household_path: Path,
    ) -> None:
        tmp_household_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_household_path.write_text("not valid json {{{", encoding="utf-8")

        with pytest.raises(HouseholdCorruptError):
            service.load()

        # Original file renamed to .corrupt.*.json
        corrupt_files = list(tmp_household_path.parent.glob("*.corrupt.*.json"))
        assert len(corrupt_files) == 1

    def test_invalid_schema_preserved(
        self,
        service: HouseholdService,
        tmp_household_path: Path,
    ) -> None:
        tmp_household_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_household_path.write_text(
            json.dumps({"name": 12345}),  # name must be str
            encoding="utf-8",
        )

        with pytest.raises(HouseholdCorruptError):
            service.load()

        corrupt_files = list(tmp_household_path.parent.glob("*.corrupt.*.json"))
        assert len(corrupt_files) == 1

    def test_atomic_write_creates_parent_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "household.json"
        svc = HouseholdService(path=nested)
        req = UpdateHouseholdRequest(
            name="Deep",
            accounts=[],
            expected_revision=0,
        )
        saved, _ = svc.save(req)
        assert nested.is_file()
        assert saved.name == "Deep"

    def test_multiple_accounts_roundtrip(self, service: HouseholdService) -> None:
        accounts = [
            Account(
                name="Taxable",
                account_type=AccountType.TAXABLE,
                tax_lots=[
                    TaxLot(
                        ticker="VTI",
                        shares=Decimal("100"),
                        cost_basis_per_share=Decimal("200"),
                        purchase_date=date(2023, 1, 1),
                    ),
                ],
                cash_holdings=[
                    CashHolding(amount=Decimal("50000"), valuation_date=date(2024, 1, 1)),
                ],
            ),
            Account(
                name="Roth IRA",
                account_type=AccountType.ROTH_IRA,
                tax_lots=[
                    TaxLot(
                        ticker="VXUS",
                        shares=Decimal("200"),
                        cost_basis_per_share=Decimal("55"),
                        purchase_date=date(2022, 6, 1),
                    ),
                ],
            ),
            Account(
                name="Trust",
                account_type=AccountType.TRUST,
                cash_holdings=[
                    CashHolding(
                        amount=Decimal("100000"),
                        valuation_date=date(2024, 1, 1),
                        is_money_market=True,
                        ticker="VMFXX",
                    ),
                ],
            ),
        ]
        req = UpdateHouseholdRequest(
            name="Multi-Account",
            accounts=accounts,
            liquidity_reserve_floor=Decimal("75000"),
            expected_revision=0,
        )
        saved, _ = service.save(req)
        assert len(saved.accounts) == 3

        loaded, _ = service.load()
        assert len(loaded.accounts) == 3
        assert loaded.accounts[1].account_type == AccountType.ROTH_IRA
        assert loaded.accounts[2].cash_holdings[0].ticker == "VMFXX"

    def test_flock_failure_closes_fd(self, tmp_path: Path) -> None:
        """File descriptor must be closed if fcntl.flock() raises."""
        from unittest.mock import patch

        svc = HouseholdService(path=tmp_path / "household.json")
        closed_fds: list[int] = []
        original_close = os.close

        def tracking_close(fd: int) -> None:
            closed_fds.append(fd)
            original_close(fd)

        with (
            patch("src.application.services.household_service.fcntl") as mock_fcntl,
            patch(
                "src.application.services.household_service.os.close",
                side_effect=tracking_close,
            ),
        ):
            mock_fcntl.LOCK_EX = 2
            mock_fcntl.flock.side_effect = OSError("mock flock failure")

            with pytest.raises(OSError, match="mock flock failure"):
                svc.load()

        assert len(closed_fds) == 1


# ---------------------------------------------------------------------------
# CSV import preview tests
# ---------------------------------------------------------------------------


class TestCSVImport:
    def test_valid_lots_and_cash(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date,amount,valuation_date,is_money_market,counts_toward_liquidity_reserve
            Taxable,taxable,lot,VTI,100,200.50,2023-01-15,,,,
            Taxable,taxable,lot,VXUS,50,55.00,2023-03-01,,,,
            Taxable,taxable,cash,,,,,,25000,2024-01-01,false,true
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert len(result.accounts) == 1
        assert len(result.accounts[0].tax_lots) == 2
        assert result.accounts[0].tax_lots[0].ticker == "VTI"
        assert result.position_only is False

    def test_missing_lot_fields_marks_position_only(
        self,
        service: HouseholdService,
    ) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Taxable,taxable,lot,VTI,100,,
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert result.position_only is True
        assert len(result.warnings) > 0

    def test_missing_required_headers(self, service: HouseholdService) -> None:
        csv = "ticker,shares\nVTI,100\n"
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert len(result.accounts) == 0
        assert any("Missing required columns" in w.message for w in result.warnings)

    def test_no_headers(self, service: HouseholdService) -> None:
        result = service.preview_csv_import(ImportPreviewRequest(csv_content="\n"))
        assert len(result.accounts) == 0

    def test_unknown_account_type(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Bad,unknown_type,lot,VTI,100,200,2023-01-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert len(result.accounts) == 0
        assert any("Unknown account_type" in w.message for w in result.warnings)

    def test_unknown_record_type(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Taxable,taxable,bond,VTI,100,200,2023-01-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert any("Unknown record_type" in w.message for w in result.warnings)

    def test_multiple_accounts_from_csv(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Taxable,taxable,lot,VTI,100,200,2023-01-01
            Roth,roth_ira,lot,VXUS,50,55,2023-06-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert len(result.accounts) == 2
        names = {a.name for a in result.accounts}
        assert names == {"Taxable", "Roth"}

    def test_invalid_decimal_in_shares(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Taxable,taxable,lot,VTI,abc,200,2023-01-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert len(result.accounts[0].tax_lots) == 0
        assert any("Invalid shares" in w.message for w in result.warnings)

    def test_conflicting_account_type_warns(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Mixed,taxable,lot,VTI,100,200,2023-01-01
            Mixed,roth_ira,lot,VXUS,50,55,2023-06-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert any("conflicting types" in w.message for w in result.warnings)
        # Second row skipped, only 1 lot from first row
        assert len(result.accounts) == 1
        assert len(result.accounts[0].tax_lots) == 1

    def test_negative_shares_warns(self, service: HouseholdService) -> None:
        csv = textwrap.dedent("""\
            account_name,account_type,record_type,ticker,shares,cost_basis_per_share,purchase_date
            Taxable,taxable,lot,VTI,-10,200,2023-01-01
        """)
        result = service.preview_csv_import(ImportPreviewRequest(csv_content=csv))
        assert any("Invalid lot data" in w.message for w in result.warnings)
        assert len(result.accounts[0].tax_lots) == 0
