"""Household portfolio persistence — load, save, journal, import.

Storage location: ~/.config/finance-os/household.json
Journal location: ~/.config/finance-os/household-journal.jsonl

Uses OS-level file locking (``fcntl.flock``) to protect against
concurrent writes from Web API, MCP server, and CLI processes.
"""

import fcntl
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from src.application.config import CONFIG_DIR
from src.application.contracts.household import (
    Account,
    Household,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportWarning,
    UpdateHouseholdRequest,
)

logger = logging.getLogger(__name__)

HOUSEHOLD_FILE = CONFIG_DIR / "household.json"
JOURNAL_FILE = CONFIG_DIR / "household-journal.jsonl"
LOCK_FILE = CONFIG_DIR / "household.lock"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class HouseholdCorruptError(Exception):
    """Raised when household.json exists but cannot be parsed.

    The corrupt file is preserved (renamed with a timestamp suffix) so the
    user can recover manually.
    """


class StaleRevisionError(Exception):
    """Raised when a write's expected_revision doesn't match the current revision.

    Callers should surface this as HTTP 409 Conflict.
    """


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HouseholdService:
    """Manages household portfolio persistence with optimistic concurrency.

    All reads and writes use an OS-level advisory lock (``fcntl.flock``)
    so that Web API, MCP, and CLI processes serialise access to the same
    file.  Inside each process the lock file descriptor is held only for
    the duration of the critical section.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or HOUSEHOLD_FILE
        self._journal_path = path.parent / "household-journal.jsonl" if path else JOURNAL_FILE
        self._lock_path = path.parent / "household.lock" if path else LOCK_FILE

    # -- public API --------------------------------------------------------

    def load(self) -> tuple[Household, bool]:
        """Load the household from disk.

        Returns:
            (household, exists) — ``exists`` is False when no file was
            found and a default household is returned.
        """
        with self._flock():
            return self._load_unlocked()

    def save(self, request: UpdateHouseholdRequest) -> tuple[Household, str]:
        """Persist an updated household, enforcing optimistic concurrency.

        Args:
            request: The update payload including ``expected_revision``.

        Returns:
            (saved_household, journal_summary)

        Raises:
            StaleRevisionError: ``expected_revision`` doesn't match current.
        """
        with self._flock():
            current, _exists = self._load_unlocked()

            if request.expected_revision != current.revision:
                raise StaleRevisionError(
                    f"Expected revision {request.expected_revision}, "
                    f"but current is {current.revision}"
                )

            updated = Household(
                name=request.name,
                accounts=request.accounts,
                cash_flow_assumptions=request.cash_flow_assumptions,
                liquidity_reserve_floor=request.liquidity_reserve_floor,
                schema_version=current.schema_version,
                revision=current.revision + 1,
                updated_at=datetime.now(),
            )

            self._write_atomic(updated)

            summary = (
                f"Updated household '{updated.name}' "
                f"(rev {current.revision} → {updated.revision}, "
                f"{len(updated.accounts)} accounts)"
            )
            self._append_journal(
                action="update",
                base_revision=current.revision,
                new_revision=updated.revision,
                summary=summary,
            )

            return updated, summary

    def preview_csv_import(self, request: ImportPreviewRequest) -> ImportPreviewResponse:
        """Parse CSV content and return proposed accounts without persisting.

        CSV schema (one row per tax lot or cash holding):
            account_name, account_type, record_type, ticker, shares,
            cost_basis_per_share, purchase_date, amount, valuation_date,
            is_money_market, counts_toward_liquidity_reserve

        ``record_type`` is ``lot`` or ``cash``.
        """
        import csv
        import io
        from decimal import Decimal, InvalidOperation

        from src.application.contracts.household import (
            AccountType,
            CashHolding,
            TaxLot,
        )

        warnings: list[ImportWarning] = []
        accounts_map: dict[str, Account] = {}
        position_only = False

        reader = csv.DictReader(io.StringIO(request.csv_content))

        required_headers = {"account_name", "account_type", "record_type"}
        if reader.fieldnames is None:
            return ImportPreviewResponse(
                accounts=[],
                warnings=[ImportWarning(message="CSV has no headers")],
                position_only=True,
            )

        missing = required_headers - set(reader.fieldnames)
        if missing:
            return ImportPreviewResponse(
                accounts=[],
                warnings=[
                    ImportWarning(message=f"Missing required columns: {sorted(missing)}")
                ],
                position_only=True,
            )

        for line_num, row in enumerate(reader, start=2):
            acct_name = row.get("account_name", "").strip()
            acct_type_raw = row.get("account_type", "").strip().lower()
            record_type = row.get("record_type", "").strip().lower()

            if not acct_name:
                warnings.append(ImportWarning(line=line_num, message="Empty account_name"))
                continue

            # Resolve account type
            try:
                acct_type = AccountType(acct_type_raw)
            except ValueError:
                warnings.append(
                    ImportWarning(
                        line=line_num,
                        message=f"Unknown account_type '{acct_type_raw}'",
                    )
                )
                continue

            if acct_name not in accounts_map:
                accounts_map[acct_name] = Account(
                    name=acct_name, account_type=acct_type
                )
            else:
                existing = accounts_map[acct_name]
                if existing.account_type != acct_type:
                    warnings.append(
                        ImportWarning(
                            line=line_num,
                            message=(
                                f"Account '{acct_name}' has conflicting types: "
                                f"'{existing.account_type}' vs '{acct_type}' — skipping row"
                            ),
                        )
                    )
                    continue

            account = accounts_map[acct_name]

            if record_type == "lot":
                ticker = row.get("ticker", "").strip().upper()
                shares_raw = row.get("shares", "").strip()
                basis_raw = row.get("cost_basis_per_share", "").strip()
                date_raw = row.get("purchase_date", "").strip()

                if not ticker or not shares_raw:
                    warnings.append(
                        ImportWarning(line=line_num, message="Lot missing ticker or shares")
                    )
                    continue

                try:
                    shares = Decimal(shares_raw)
                except InvalidOperation:
                    warnings.append(
                        ImportWarning(line=line_num, message=f"Invalid shares '{shares_raw}'")
                    )
                    continue

                # If cost basis or date missing → position-only
                if not basis_raw or not date_raw:
                    position_only = True
                    warnings.append(
                        ImportWarning(
                            line=line_num,
                            message=(
                                f"Lot for {ticker} missing cost_basis or purchase_date "
                                "— imported as position-only"
                            ),
                        )
                    )
                    basis = Decimal("0")
                    pdate = datetime.now().date()
                else:
                    try:
                        basis = Decimal(basis_raw)
                    except InvalidOperation:
                        warnings.append(
                            ImportWarning(
                                line=line_num,
                                message=f"Invalid cost_basis '{basis_raw}'",
                            )
                        )
                        continue
                    try:
                        from datetime import date as date_type

                        pdate = date_type.fromisoformat(date_raw)
                    except ValueError:
                        warnings.append(
                            ImportWarning(
                                line=line_num,
                                message=f"Invalid purchase_date '{date_raw}' (use YYYY-MM-DD)",
                            )
                        )
                        continue

                try:
                    account.tax_lots.append(
                        TaxLot(
                            ticker=ticker,
                            shares=shares,
                            cost_basis_per_share=basis,
                            purchase_date=pdate,
                        )
                    )
                except ValidationError as exc:
                    warnings.append(
                        ImportWarning(
                            line=line_num,
                            message=f"Invalid lot data: {exc.errors()[0]['msg']}",
                        )
                    )

            elif record_type == "cash":
                amount_raw = row.get("amount", "").strip()
                val_date_raw = row.get("valuation_date", "").strip()
                is_mm = row.get("is_money_market", "").strip().lower() in ("true", "1", "yes")
                counts = row.get("counts_toward_liquidity_reserve", "true").strip().lower()
                counts_liq = counts in ("true", "1", "yes", "")

                if not amount_raw:
                    warnings.append(
                        ImportWarning(line=line_num, message="Cash row missing amount")
                    )
                    continue

                try:
                    amount = Decimal(amount_raw)
                except InvalidOperation:
                    warnings.append(
                        ImportWarning(line=line_num, message=f"Invalid amount '{amount_raw}'")
                    )
                    continue

                if val_date_raw:
                    try:
                        from datetime import date as date_type

                        val_date = date_type.fromisoformat(val_date_raw)
                    except ValueError:
                        warnings.append(
                            ImportWarning(
                                line=line_num,
                                message=f"Invalid valuation_date '{val_date_raw}'",
                            )
                        )
                        continue
                else:
                    val_date = datetime.now().date()

                mm_ticker = row.get("ticker", "").strip().upper() or None

                try:
                    account.cash_holdings.append(
                        CashHolding(
                            amount=amount,
                            valuation_date=val_date,
                            is_money_market=is_mm,
                            ticker=mm_ticker if is_mm else None,
                            counts_toward_liquidity_reserve=counts_liq,
                        )
                    )
                except ValidationError as exc:
                    warnings.append(
                        ImportWarning(
                            line=line_num,
                            message=f"Invalid cash data: {exc.errors()[0]['msg']}",
                        )
                    )
            else:
                warnings.append(
                    ImportWarning(
                        line=line_num,
                        message=f"Unknown record_type '{record_type}' (expected 'lot' or 'cash')",
                    )
                )

        return ImportPreviewResponse(
            accounts=list(accounts_map.values()),
            warnings=warnings,
            position_only=position_only,
        )

    # -- internals ---------------------------------------------------------

    def _flock(self) -> "_FileLockContext":
        """Return a context manager that holds an OS-level advisory lock."""
        return _FileLockContext(self._lock_path)

    def _load_unlocked(self) -> tuple[Household, bool]:
        """Load without acquiring the lock (caller must hold it)."""
        if not self._path.is_file():
            return self._default_household(), False

        raw_text = self._path.read_text(encoding="utf-8")
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            self._preserve_corrupt_file()
            raise HouseholdCorruptError(
                f"household.json is not valid JSON: {exc}"
            ) from exc

        try:
            return Household.model_validate(raw), True
        except ValidationError as exc:
            self._preserve_corrupt_file()
            raise HouseholdCorruptError(
                f"household.json has invalid schema: {exc}"
            ) from exc

    def _write_atomic(self, household: Household) -> None:
        """Atomically write household to disk (temp file + rename)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            household.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self._path.parent,
                suffix=".tmp",
                delete=False,
                encoding="utf-8",
            ) as fd:
                temp_path = Path(fd.name)
                fd.write(content)
                fd.flush()
                os.fsync(fd.fileno())
            temp_path.replace(self._path)
        except BaseException:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def _preserve_corrupt_file(self) -> None:
        """Rename a corrupt household.json so the user can recover it."""
        if self._path.is_file():
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            backup = self._path.with_suffix(f".corrupt.{ts}.json")
            self._path.rename(backup)
            logger.error(
                "Corrupt household.json preserved as %s", backup,
            )

    def _append_journal(
        self,
        action: str,
        base_revision: int,
        new_revision: int,
        summary: str,
    ) -> None:
        """Append a line to the change journal (best-effort)."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "base_revision": base_revision,
            "new_revision": new_revision,
            "summary": summary,
        }
        try:
            self._journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self._journal_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            logger.warning("Failed to write household journal entry", exc_info=True)

    @staticmethod
    def _default_household() -> Household:
        return Household(name="My Household")


# ---------------------------------------------------------------------------
# OS-level file lock context manager
# ---------------------------------------------------------------------------

class _FileLockContext:
    """Advisory file lock using ``fcntl.flock``.

    Serialises access across processes (Web API, MCP, CLI) sharing the
    same config directory.
    """

    def __init__(self, lock_path: Path) -> None:
        self._lock_path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> "_FileLockContext":
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_: object) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
