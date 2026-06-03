"""QIF parser utilities and dataclasses for household import flows."""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

_CP1252_MAP = {
    0x80: 0x20AC,
    0x82: 0x201A,
    0x83: 0x0192,
    0x84: 0x201E,
    0x85: 0x2026,
    0x86: 0x2020,
    0x87: 0x2021,
    0x88: 0x02C6,
    0x89: 0x2030,
    0x8A: 0x0160,
    0x8B: 0x2039,
    0x8C: 0x0152,
    0x8E: 0x017D,
    0x91: 0x2018,
    0x92: 0x2019,
    0x93: 0x201C,
    0x94: 0x201D,
    0x95: 0x2022,
    0x96: 0x2013,
    0x97: 0x2014,
    0x98: 0x02DC,
    0x99: 0x2122,
    0x9A: 0x0161,
    0x9B: 0x203A,
    0x9C: 0x0153,
    0x9E: 0x017E,
    0x9F: 0x0178,
}
_CP1252_RE = re.compile(r"[\x80-\x9F]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F]")
_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_BANKING_SECTION_TYPES = frozenset({"bank", "cash", "ccard", "oth a", "oth l"})
_TRANSACTION_SECTION_TYPES = frozenset(
    {"bank", "cash", "ccard", "oth a", "oth l", "invst", "memorized", "invoice"}
)
_QIF_TYPE_NAMES = {
    "bank": "Bank",
    "cash": "Cash",
    "ccard": "CCard",
    "oth a": "Oth A",
    "oth l": "Oth L",
    "invst": "Invst",
    "cat": "Cat",
    "class": "Class",
    "security": "Security",
    "memorized": "Memorized",
    "invoice": "Invoice",
    "tag": "Tag",
    "prices": "Prices",
}
_ZERO = Decimal("0")


@dataclass(slots=True)
class QifSplit:
    """A split line attached to a banking or investment transaction."""

    category: str
    memo: str = ""
    amount: Decimal = field(default_factory=lambda: _ZERO)
    percent: str = ""


@dataclass(slots=True)
class QifInvestmentTransaction:
    """A single investment transaction from a QIF file."""

    account: str
    date: date | None
    action: str
    security: str
    price: Decimal
    quantity: Decimal
    amount: Decimal
    commission: Decimal
    memo: str
    category: str
    cleared: str = ""
    payee: str = ""
    transfer_amount: Decimal = field(default_factory=lambda: _ZERO)
    splits: list[QifSplit] = field(default_factory=list)


@dataclass(slots=True)
class QifBankingTransaction:
    """A banking transaction (checking, savings, credit card, etc.)."""

    account: str
    date: date | None
    amount: Decimal
    payee: str
    memo: str
    category: str
    cleared: str
    splits: list[QifSplit] = field(default_factory=list)
    check_number: str = ""
    address: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QifSecurity:
    """Security definition from QIF."""

    name: str
    symbol: str
    security_type: str


@dataclass(slots=True)
class QifAccount:
    """Account metadata from QIF."""

    name: str
    account_type: str
    description: str = ""
    credit_limit: str = ""
    statement_balance_date: date | None = None
    statement_balance_amount: Decimal = field(default_factory=lambda: _ZERO)


@dataclass(slots=True)
class QifData:
    """Complete parsed QIF file data."""

    accounts: dict[str, QifAccount] = field(default_factory=dict)
    banking_transactions: list[QifBankingTransaction] = field(default_factory=list)
    investment_transactions: list[QifInvestmentTransaction] = field(default_factory=list)
    securities: list[QifSecurity] = field(default_factory=list)
    has_auto_switch: bool = False
    price_lines: list[str] = field(default_factory=list)


def decode_qif_text(raw: str) -> str:
    """Apply CP1252 fixup to latin1-decoded QIF text.

    Args:
        raw: Latin1-decoded QIF text.

    Returns:
        Unicode text with CP1252 control-range bytes fixed up.

    Raises:
        TypeError: If ``raw`` is not a string.
    """
    if not isinstance(raw, str):
        raise TypeError(f"decode_qif_text requires a string, got {type(raw).__name__}")

    return _CP1252_RE.sub(
        lambda match: chr(_CP1252_MAP.get(ord(match.group(0)), ord(match.group(0)))),
        raw,
    )


def parse_qif_date(s: str) -> date | None:
    """Parse a QIF date string (M/D/YYYY, M/D/YY, M/D'YYYY, D Month YYYY).

    Args:
        s: Raw QIF date string.

    Returns:
        Parsed ``date`` or ``None`` when parsing fails.
    """
    if not s:
        return None

    raw = s.strip()
    if not raw:
        return None

    long_match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", raw)
    if long_match:
        day = int(long_match.group(1))
        month = _MONTH_NAMES.get(long_match.group(2).lower())
        year = _normalize_year(int(long_match.group(3)))
        if month is not None:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    normalized = raw.replace("'", "/").replace("-", "/")
    normalized = re.sub(r"\s+", "", normalized)
    short_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{1,4})", normalized)
    if short_match is None:
        return None

    month = int(short_match.group(1))
    day = int(short_match.group(2))
    year = _normalize_year(int(short_match.group(3)))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_qif_amount(s: str) -> Decimal:
    """Parse QIF amount string to Decimal.

    Args:
        s: Raw QIF amount string.

    Returns:
        Parsed decimal amount, or ``Decimal('0')`` if invalid.
    """
    if not s:
        return Decimal("0")

    cleaned = (
        s.replace("$", "")
        .replace("£", "")
        .replace("¥", "")
        .replace("€", "")
        .replace(",", "")
        .strip()
    )
    if not cleaned:
        return Decimal("0")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def extract_accounts(text: str) -> list[QifAccount]:
    """Extract account definitions from QIF text without a full parse.

    Args:
        text: Decoded QIF content.

    Returns:
        Parsed account metadata in encounter order.
    """
    accounts: list[QifAccount] = []
    seen: set[tuple[str, str]] = set()
    in_account = False
    name = ""
    account_type = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower_line = line.lower()
        if lower_line == "!account":
            in_account = True
            name = ""
            account_type = ""
            continue

        if line.startswith("!"):
            if not accounts and lower_line.startswith("!type:"):
                fallback_type = _canonical_qif_type(lower_line[6:].strip())
                key = ("", fallback_type)
                if key not in seen:
                    seen.add(key)
                    accounts.append(QifAccount(name="", account_type=fallback_type))
            in_account = False
            continue

        if line == "^":
            if in_account and name:
                key = (name, account_type)
                if key not in seen:
                    seen.add(key)
                    accounts.append(QifAccount(name=name, account_type=account_type))
            in_account = False
            name = ""
            account_type = ""
            continue

        if in_account:
            if line[0] == "N":
                name = line[1:]
            elif line[0] == "T":
                account_type = _canonical_qif_type(_strip_control_chars(line[1:]))

    return accounts


def parse_qif(text: str, fallback_account: str = "Unknown") -> QifData:
    """Parse QIF text into structured data.

    Args:
        text: Decoded QIF file content.
        fallback_account: Account name to use when the QIF file omits ``!Account`` blocks.

    Returns:
        Structured QIF data.
    """
    data = QifData()
    current_section: str | None = None
    current_account: str | None = None
    record: dict[str, str] = {}
    splits: list[QifSplit] = []
    addresses: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue

        if line.startswith("!"):
            lower_line = line.lower().strip()
            if lower_line == "!option:autoswitch":
                data.has_auto_switch = True
                current_section = None
                continue
            if lower_line == "!clear:autoswitch":
                continue
            if lower_line == "!account":
                current_section = "account"
                record = {}
                splits = []
                addresses = []
                continue
            if lower_line.startswith("!type:"):
                current_section = _strip_control_chars(line[6:]).strip().lower() or "bank"
                if current_account is not None and current_account in data.accounts:
                    account = data.accounts[current_account]
                    if not account.account_type and (
                        current_section in _BANKING_SECTION_TYPES or current_section == "invst"
                    ):
                        account.account_type = _canonical_qif_type(current_section)
                record = {}
                splits = []
                addresses = []
                continue
            continue

        if line.strip() == "^":
            _finalize_record(
                data=data,
                current_section=current_section,
                current_account=current_account,
                fallback_account=fallback_account,
                record=record,
                splits=splits,
                addresses=addresses,
            )
            if current_section == "account":
                current_account = record.get("N") or "Unknown"
            record = {}
            splits = []
            addresses = []
            continue

        if current_section == "prices":
            record["_raw"] = line
            continue

        code = line[0]
        value = line[1:]

        if current_section in _TRANSACTION_SECTION_TYPES:
            if code == "S":
                splits.append(QifSplit(category=value))
                continue
            if code == "E" and splits:
                splits[-1].memo = value
                continue
            if code == "$" and splits:
                splits[-1].amount = parse_qif_amount(value)
                continue
            if code == "%" and splits:
                splits[-1].percent = value
                continue

        if code == "A":
            addresses.append(value)
            continue

        record[code] = value

    return data


def _finalize_record(
    *,
    data: QifData,
    current_section: str | None,
    current_account: str | None,
    fallback_account: str,
    record: dict[str, str],
    splits: list[QifSplit],
    addresses: list[str],
) -> None:
    if current_section == "account":
        name = record.get("N") or "Unknown"
        data.accounts[name] = QifAccount(
            name=name,
            account_type=_canonical_qif_type(_strip_control_chars(record.get("T", "")).strip()),
            description=record.get("D", ""),
            credit_limit=record.get("L", ""),
            statement_balance_date=parse_qif_date(record.get("/", "")),
            statement_balance_amount=parse_qif_amount(record.get("$", "")),
        )
        return

    if current_section in _BANKING_SECTION_TYPES or current_section == "invoice":
        account_name = current_account or fallback_account or "Unknown"
        data.banking_transactions.append(
            QifBankingTransaction(
                account=account_name,
                date=parse_qif_date(record.get("D", "")),
                amount=parse_qif_amount(record.get("T") or record.get("U") or ""),
                payee=record.get("P", ""),
                memo=record.get("M", ""),
                category=record.get("L", ""),
                cleared=record.get("C", ""),
                splits=[_copy_split(split) for split in splits],
                check_number=record.get("N", ""),
                address=list(addresses),
            )
        )
        return

    if current_section == "invst":
        account_name = current_account or fallback_account or "Unknown"
        data.investment_transactions.append(
            QifInvestmentTransaction(
                account=account_name,
                date=parse_qif_date(record.get("D", "")),
                action=record.get("N", ""),
                security=record.get("Y", ""),
                price=parse_qif_amount(record.get("I", "")),
                quantity=parse_qif_amount(record.get("Q", "")),
                amount=parse_qif_amount(record.get("T") or record.get("U") or ""),
                commission=parse_qif_amount(record.get("O", "")),
                memo=record.get("M", ""),
                category=record.get("L", ""),
                cleared=record.get("C", ""),
                payee=record.get("P", ""),
                transfer_amount=parse_qif_amount(record.get("$", "")),
                splits=[_copy_split(split) for split in splits],
            )
        )
        return

    if current_section == "security":
        data.securities.append(
            QifSecurity(
                name=record.get("N", ""),
                symbol=record.get("S", ""),
                security_type=record.get("T", ""),
            )
        )
        return

    if current_section == "prices" and "_raw" in record:
        data.price_lines.append(record["_raw"])


def _copy_split(split: QifSplit) -> QifSplit:
    return QifSplit(
        category=split.category,
        memo=split.memo,
        amount=split.amount,
        percent=split.percent,
    )


def _normalize_year(year: int) -> int:
    return year + (2000 if year < 50 else 1900) if year < 100 else year


def _strip_control_chars(value: str) -> str:
    return _CONTROL_CHAR_RE.sub("", value)


def _canonical_qif_type(raw_type: str) -> str:
    cleaned = _strip_control_chars(raw_type).strip()
    return _QIF_TYPE_NAMES.get(cleaned.lower(), cleaned)
