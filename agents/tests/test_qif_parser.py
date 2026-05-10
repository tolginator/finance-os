"""Tests for QIF parser behavior."""

from datetime import date
from decimal import Decimal

from src.application.services.qif_parser import (
    decode_qif_text,
    parse_qif,
    parse_qif_amount,
    parse_qif_date,
)


def test_parse_qif_date_supports_known_variants() -> None:
    expected = date(2024, 3, 15)

    assert parse_qif_date("3/15/2024") == expected
    assert parse_qif_date("3/15/24") == expected
    assert parse_qif_date("3/15'2024") == expected
    assert parse_qif_date("15 March 2024") == expected
    assert parse_qif_date("3-15-2024") == expected


def test_parse_qif_date_handles_century_rollover_and_invalid_values() -> None:
    assert parse_qif_date("3/15/49") == date(2049, 3, 15)
    assert parse_qif_date("3/15/50") == date(1950, 3, 15)
    assert parse_qif_date("2/30/2024") is None
    assert parse_qif_date("") is None


def test_parse_qif_amount_strips_symbols_and_grouping() -> None:
    assert parse_qif_amount("123.45") == Decimal("123.45")
    assert parse_qif_amount("-1,234.56") == Decimal("-1234.56")
    assert parse_qif_amount("$2,500.00") == Decimal("2500.00")
    assert parse_qif_amount("€7.89") == Decimal("7.89")
    assert parse_qif_amount("") == Decimal("0")
    assert parse_qif_amount("not-a-number") == Decimal("0")


def test_decode_qif_text_replaces_cp1252_control_range() -> None:
    raw = "Euro \x80 quotes \x93Hello\x94 dash \x97"

    decoded = decode_qif_text(raw)

    assert decoded == "Euro € quotes “Hello” dash —"


def test_parse_qif_handles_accounts_autoswitch_splits_and_securities() -> None:
    qif_text = """!Option:AutoSwitch
!Account
NBrokerage
TInvst
DPrimary account
/3/31/2024
$12345.67
^
!Type:Invst
D3/15/2024
NBuy
YVanguard Total Stock Market ETF
I250.10
Q2
T-504.95
O4.75
MInitial lot
^
!Account
NChecking
TBank
/3/31/2024
$1500.00
^
!Type:Bank
D3/20/2024
T-120.50
PGrocery Store
LGroceries
MWeekly run
SFood:Produce
EFruit
$-20.25
SFood:Pantry
$-100.25
^
!Clear:AutoSwitch
!Type:Security
NVanguard Total Stock Market ETF
SVTI
TMutual Fund
^
"""

    parsed = parse_qif(qif_text)

    assert parsed.has_auto_switch is True
    assert parsed.accounts["Brokerage"].account_type == "Invst"
    assert parsed.accounts["Brokerage"].statement_balance_amount == Decimal("12345.67")
    assert parsed.accounts["Checking"].account_type == "Bank"
    assert len(parsed.investment_transactions) == 1
    assert len(parsed.banking_transactions) == 1
    assert len(parsed.securities) == 1

    investment = parsed.investment_transactions[0]
    assert investment.account == "Brokerage"
    assert investment.date == date(2024, 3, 15)
    assert investment.action == "Buy"
    assert investment.security == "Vanguard Total Stock Market ETF"
    assert investment.price == Decimal("250.10")
    assert investment.quantity == Decimal("2")
    assert investment.amount == Decimal("-504.95")
    assert investment.commission == Decimal("4.75")

    banking = parsed.banking_transactions[0]
    assert banking.account == "Checking"
    assert banking.payee == "Grocery Store"
    assert banking.amount == Decimal("-120.50")
    assert len(banking.splits) == 2
    assert banking.splits[0].category == "Food:Produce"
    assert banking.splits[0].memo == "Fruit"
    assert banking.splits[0].amount == Decimal("-20.25")
    assert banking.splits[1].category == "Food:Pantry"
    assert banking.splits[1].amount == Decimal("-100.25")

    security = parsed.securities[0]
    assert security.name == "Vanguard Total Stock Market ETF"
    assert security.symbol == "VTI"
    assert security.security_type == "Mutual Fund"


def test_parse_qif_uses_fallback_account_without_account_blocks() -> None:
    qif_text = """!Type:Bank
D3/21/2024
T25.00
PInterest
^
"""

    parsed = parse_qif(qif_text, fallback_account="Fallback Cash")

    assert len(parsed.accounts) == 0
    assert len(parsed.banking_transactions) == 1
    assert parsed.banking_transactions[0].account == "Fallback Cash"
    assert parsed.banking_transactions[0].amount == Decimal("25.00")


def test_parse_qif_gracefully_handles_empty_and_malformed_input() -> None:
    malformed = """!Type:Bank
malformed line
D2/30/2024
Tabc
^
!Type:Security
NBad Security
^
"""

    empty = parse_qif("")
    parsed = parse_qif(malformed)

    assert empty.accounts == {}
    assert empty.banking_transactions == []
    assert empty.investment_transactions == []
    assert empty.securities == []
    assert len(parsed.banking_transactions) == 1
    assert parsed.banking_transactions[0].date is None
    assert parsed.banking_transactions[0].amount == Decimal("0")
    assert len(parsed.securities) == 1
    assert parsed.securities[0].symbol == ""
