"""Tests for QIF import preview mapping."""

from datetime import date
from decimal import Decimal

from src.application.contracts.household import AccountType
from src.application.services.household_service import HouseholdService
from src.application.services.qif_import import preview_qif_import


def test_preview_qif_import_builds_tax_lots_from_investment_buys() -> None:
    qif_text = """!Account
NBrokerage
TInvst
^
!Type:Invst
D3/15/2024
NBuy
YVanguard Total Stock Market ETF
I250.10
Q2
^
!Type:Security
NVanguard Total Stock Market ETF
SVTI
TMutual Fund
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    assert account.name == "Brokerage"
    assert account.account_type == AccountType.TAXABLE
    assert len(account.tax_lots) == 1
    assert account.tax_lots[0].ticker == "VTI"
    assert account.tax_lots[0].shares == Decimal("2")
    assert account.tax_lots[0].cost_basis_per_share == Decimal("250.10")
    assert account.tax_lots[0].purchase_date == date(2024, 3, 15)
    assert result.position_only is False


def test_preview_qif_import_maps_banking_balance_to_cash_holding() -> None:
    qif_text = """!Account
NChecking
TBank
/3/31/2024
$1500.25
^
!Type:Bank
D3/30/2024
T-25.00
PGroceries
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    assert account.account_type == AccountType.TAXABLE
    assert len(account.cash_holdings) == 1
    assert account.cash_holdings[0].amount == Decimal("1500.25")
    assert account.cash_holdings[0].valuation_date == date(2024, 3, 31)
    assert account.cash_holdings[0].counts_toward_liquidity_reserve is True


def test_preview_qif_import_warns_and_skips_unsupported_account_types() -> None:
    qif_text = """!Account
NCredit Card
TCCard
^
!Type:CCard
D3/20/2024
T-45.00
PFuel
^
!Account
NLoan
TOth L
^
!Type:Oth L
D3/21/2024
T-100.00
PPayment
^
"""

    result = preview_qif_import(qif_text)

    assert result.accounts == []
    assert len(result.warnings) == 2


def test_preview_qif_import_marks_position_only_when_cost_basis_missing() -> None:
    qif_text = """!Account
NTransferred Holdings
TInvst
^
!Type:Invst
D3/18/2024
NShrsIn
YExisting Fund
Q10
^
!Type:Security
NExisting Fund
SEXF
TMutual Fund
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    assert len(account.tax_lots) == 1
    assert account.tax_lots[0].ticker == "EXF"
    assert account.tax_lots[0].cost_basis_per_share == Decimal("0")
    assert result.position_only is True


def test_preview_qif_import_resolves_security_name_to_ticker() -> None:
    qif_text = """!Account
NLong Term
TInvst
^
!Type:Invst
D4/1/2024
NReinvDiv
YVanguard Total Bond Market ETF
I75.50
Q1.5
^
!Type:Security
NVanguard Total Bond Market ETF
SBND
TETF
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    assert len(result.accounts[0].tax_lots) == 1
    assert result.accounts[0].tax_lots[0].ticker == "BND"
    assert result.position_only is False


def test_preview_qif_import_returns_empty_result_for_empty_qif() -> None:
    result = preview_qif_import("")

    assert result.accounts == []
    assert result.warnings == []
    assert result.position_only is False


def test_household_service_preview_qif_import_delegates() -> None:
    service = HouseholdService()
    qif_text = """!Account
NBrokerage
TInvst
^
!Type:Invst
D3/15/2024
NBuy
YACME ETF
I10.00
Q3
^
"""

    result = service.preview_qif_import(qif_text, household_name="Family")

    assert len(result.accounts) == 1
    assert result.accounts[0].name == "Brokerage"
    assert result.accounts[0].tax_lots[0].ticker == "ACMEETF"
