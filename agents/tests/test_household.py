"""Tests for household portfolio model — contracts, service, and math helpers."""

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
    HouseholdMember,
    ImportPreviewRequest,
    TaxLot,
    WithdrawalRestriction,
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
    HouseholdService,
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
def service() -> HouseholdService:
    return HouseholdService()


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

    def test_account_owner_and_metadata(self) -> None:
        acct = Account(
            name="Roth IRA",
            account_type=AccountType.ROTH_IRA,
            owner="Alice",
            institution="Fidelity",
        )
        assert acct.owner == "Alice"
        assert acct.institution == "Fidelity"
        assert acct.beneficiary is None
        assert acct.withdrawal_restrictions == []

    def test_account_with_withdrawal_restriction(self) -> None:
        acct = Account(
            name="Traditional IRA",
            account_type=AccountType.TRADITIONAL_IRA,
            withdrawal_restrictions=[
                WithdrawalRestriction(
                    description="Early withdrawal penalty",
                    penalty_pct=Decimal("10"),
                    penalty_free_age=59,
                    rmd_start_age=73,
                ),
            ],
        )
        assert len(acct.withdrawal_restrictions) == 1
        assert acct.withdrawal_restrictions[0].rmd_start_age == 73


class TestHouseholdMember:
    def test_age_at(self) -> None:
        member = HouseholdMember(
            name="Alice",
            date_of_birth=date(1980, 6, 15),
            is_primary=True,
        )
        assert member.age_at(date(2025, 6, 14)) == 44
        assert member.age_at(date(2025, 6, 15)) == 45
        assert member.age_at(date(2025, 12, 31)) == 45

    def test_age_at_no_dob(self) -> None:
        member = HouseholdMember(name="Unknown")
        assert member.age_at(date(2025, 1, 1)) is None

    def test_defaults(self) -> None:
        member = HouseholdMember(name="Bob")
        assert member.date_of_birth is None
        assert member.is_primary is False


class TestWithdrawalRestriction:
    def test_valid(self) -> None:
        wr = WithdrawalRestriction(
            description="10% early withdrawal",
            penalty_pct=Decimal("10"),
            penalty_free_age=59,
        )
        assert wr.penalty_pct == Decimal("10")
        assert wr.rmd_start_age is None

    def test_penalty_bounds(self) -> None:
        with pytest.raises(ValidationError):
            WithdrawalRestriction(
                description="Bad",
                penalty_pct=Decimal("101"),
            )


class TestHousehold:
    def test_defaults(self) -> None:
        h = Household(name="Test")
        assert h.schema_version == 2
        assert h.accounts == []
        assert h.members == []
        assert h.liquidity_reserve_floor == Decimal("0")
        assert h.tax_year is None

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

    def test_household_with_members(self) -> None:
        h = Household(
            name="Family",
            members=[
                HouseholdMember(
                    name="Alice",
                    date_of_birth=date(1980, 3, 15),
                    is_primary=True,
                ),
                HouseholdMember(name="Bob", date_of_birth=date(1982, 7, 20)),
            ],
            tax_year=2025,
        )
        assert len(h.members) == 2
        assert h.members[0].is_primary is True
        assert h.tax_year == 2025
        assert h.schema_version == 2

    def test_backward_compat_v1_data(self) -> None:
        """v1 data without members/tax_year still loads correctly."""
        v1_data = {
            "name": "Legacy",
            "accounts": [],
            "liquidity_reserve_floor": "10000",
            "schema_version": 1,
        }
        h = Household.model_validate(v1_data)
        assert h.members == []
        assert h.tax_year is None
        assert h.name == "Legacy"


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
    def test_all_types(self) -> None:
        assert len(AccountType) == 10

    def test_401k(self) -> None:
        assert AccountType.FOUR01K.value == "401k"

    def test_new_types(self) -> None:
        assert AccountType.FIVE29.value == "529"
        assert AccountType.INHERITED_IRA.value == "inherited_ira"
        assert AccountType.INHERITED_ROTH.value == "inherited_roth"
        assert AccountType.CUSTODIAL.value == "custodial"


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
    def test_load_no_qif_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no qif_source_path is configured, load returns defaults."""
        monkeypatch.setattr(
            "src.application.services.household_service.AppConfig",
            lambda: type("C", (), {"qif_source_path": "", "excluded_accounts": []})(),
        )
        svc = HouseholdService()
        household, exists = svc.load()
        assert exists is False
        assert household.name == "My Household"

    def test_load_from_qif_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When qif_source_path points to a valid file, load parses it."""
        qif_file = tmp_path / "portfolio.qif"
        qif_file.write_text(
            "!Account\nNBrokerage\nTInvst\n^\n"
            "!Type:Invst\nD01/15/2024\nNBuy\nYVTI\nQ100\nT20050\nI200.50\n^\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "src.application.services.household_service.AppConfig",
            lambda: type("C", (), {
                "qif_source_path": str(qif_file),
                "excluded_accounts": [],
            })(),
        )
        svc = HouseholdService()
        household, exists = svc.load()
        assert exists is True
        assert len(household.accounts) == 1
        assert household.accounts[0].name == "Brokerage"

    def test_load_excludes_accounts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Accounts in excluded_accounts config are filtered out."""
        qif_file = tmp_path / "portfolio.qif"
        qif_file.write_text(
            "!Account\nNBrokerage\nTInvst\n^\n"
            "!Account\nNRetirement\nTInvst\n^\n"
            "!Type:Invst\nD01/15/2024\nNBuy\nYVTI\nQ100\nI200.50\n^\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "src.application.services.household_service.AppConfig",
            lambda: type("C", (), {
                "qif_source_path": str(qif_file),
                "excluded_accounts": ["Retirement"],
            })(),
        )
        svc = HouseholdService()
        household, exists = svc.load()
        assert exists is True
        acct_names = [a.name for a in household.accounts]
        assert "Retirement" not in acct_names

    def test_load_missing_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When qif_source_path points to a missing file, returns defaults."""
        monkeypatch.setattr(
            "src.application.services.household_service.AppConfig",
            lambda: type("C", (), {
                "qif_source_path": "/nonexistent/file.qif",
                "excluded_accounts": [],
            })(),
        )
        svc = HouseholdService()
        household, exists = svc.load()
        assert exists is False


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

