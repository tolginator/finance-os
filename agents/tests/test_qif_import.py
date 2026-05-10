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


def test_preview_qif_import_sells_consume_lots_fifo() -> None:
    """Sell transactions consume lots FIFO, reducing shares and cost basis."""
    qif_text = """!Account
NBrokerage
TInvst
^
!Type:Invst
D1/15/2024
NBuy
YVTI
I200.00
Q100
^
D3/01/2024
NBuy
YVTI
I220.00
Q50
^
D6/01/2024
NSell
YVTI
I250.00
Q120
^
!Type:Security
NVTI
SVTI
TStock
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    # Bought 150, sold 120 → 30 remaining (FIFO: 100-lot consumed, 50-lot reduced by 20).
    total_shares = sum(lot.shares for lot in account.tax_lots)
    assert total_shares == Decimal("30")
    assert len(account.tax_lots) == 1
    assert account.tax_lots[0].cost_basis_per_share == Decimal("220.00")
    assert account.tax_lots[0].shares == Decimal("30")


def test_preview_qif_import_sell_all_shares_removes_position() -> None:
    """Selling all shares should result in no tax lots for that ticker."""
    qif_text = """!Account
NBrokerage
TInvst
^
!Type:Invst
D1/15/2024
NBuy
YVTI
I200.00
Q100
^
D6/01/2024
NSell
YVTI
I250.00
Q100
^
!Type:Security
NVTI
SVTI
TStock
^
"""

    result = preview_qif_import(qif_text)

    # No remaining positions → account filtered out as empty.
    assert len(result.accounts) == 0


def test_preview_qif_import_handles_stock_split() -> None:
    """Stock splits multiply shares and divide price across lots."""
    qif_text = """!Account
NBrokerage
TInvst
^
!Type:Invst
D1/15/2024
NBuy
YVTI
I200.00
Q100
^
D3/01/2024
NStkSplit
YVTI
Q20
^
!Type:Security
NVTI
SVTI
TStock
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    # 2:1 split (Q=20 → ratio=2): 100 shares → 200, price $200 → $100.
    assert len(account.tax_lots) == 1
    assert account.tax_lots[0].shares == Decimal("200")
    assert account.tax_lots[0].cost_basis_per_share == Decimal("100.00")


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


def test_preview_qif_import_computes_balance_from_banking_transactions() -> None:
    """When no statement balance exists, sum banking transactions."""
    qif_text = """!Account
NChase Checking
TBank
^
!Type:Bank
D1/15/2024
T5000.00
PDeposit
^
D1/20/2024
T-200.00
PGroceries
^
D2/01/2024
T3000.00
PPaycheck
^
"""

    result = preview_qif_import(qif_text)

    assert len(result.accounts) == 1
    account = result.accounts[0]
    assert account.name == "Chase Checking"
    assert len(account.cash_holdings) == 1
    assert account.cash_holdings[0].amount == Decimal("7800.00")
    assert account.cash_holdings[0].valuation_date == date(2024, 2, 1)
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


def test_infer_account_type_from_name() -> None:
    """Account names with well-known patterns should auto-classify."""
    cases = [
        ("Roth IRA - Tolga", AccountType.ROTH_IRA),
        ("Rollover Roth IRA - Tolga", AccountType.ROTH_IRA),
        ("Rollover IRA - Barcin", AccountType.TRADITIONAL_IRA),
        ("401(k) - Microsoft", AccountType.FOUR01K),
        ("403(b) GSRA - PEBB", AccountType.FOUR01K),
        ("401(a) GRA - PEBB", AccountType.FOUR01K),
        ("Microsoft DCP", AccountType.FOUR01K),
        ("Fidelity HSA", AccountType.HSA),
        ("Health Equity HSA", AccountType.HSA),
        ("529 Fidelity - Lidya", AccountType.TRUST),
        ("UTMA - Lidya", AccountType.TRUST),
        ("Fidelity Investment", AccountType.TAXABLE),  # no pattern match → taxable
        ("Chase Brokerage", AccountType.TAXABLE),
    ]
    for name, expected_type in cases:
        qif_text = (
            f"!Account\nN{name}\nTInvst\n^\n"
            f"!Type:Invst\nD01/01/2024\nNBuy\nYVTI\nQ10\nI100\nT1000\n^\n"
            f"!Type:Security\nNVTI\nSVTI\nTStock\n^\n"
        )
        result = preview_qif_import(qif_text)
        assert len(result.accounts) > 0, f"{name}: no accounts returned"
        assert result.accounts[0].account_type == expected_type, (
            f"{name}: expected {expected_type}, got {result.accounts[0].account_type}"
        )


def test_inferred_accounts_skip_verify_warning() -> None:
    """Accounts with inferred types should not produce 'verify' warnings."""
    qif_text = (
        "!Account\nNRoth IRA - Tolga\nTInvst\n^\n"
        "!Type:Invst\nD01/01/2024\nNBuy\nYVTI\nQ10\nI100\nT1000\n^\n"
        "!Type:Security\nNVTI\nSVTI\nTStock\n^\n"
    )
    result = preview_qif_import(qif_text)
    assert not any("verify" in w.message.lower() for w in result.warnings)


def test_unknown_invst_account_still_warns() -> None:
    """Investment accounts that can't be inferred should still warn."""
    qif_text = (
        "!Account\nNFidelity Investment\nTInvst\n^\n"
        "!Type:Invst\nD01/01/2024\nNBuy\nYVTI\nQ10\nI100\nT1000\n^\n"
        "!Type:Security\nNVTI\nSVTI\nTStock\n^\n"
    )
    result = preview_qif_import(qif_text)
    assert result.accounts[0].account_type == AccountType.TAXABLE
    assert any("verify" in w.message.lower() for w in result.warnings)
