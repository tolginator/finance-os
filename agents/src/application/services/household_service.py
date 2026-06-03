"""Household portfolio service — QIF file is the single source of truth.

The QIF file is read-only input. Portfolio data is computed fresh from
the QIF file on every request — no intermediate household.json replica.
Config stores only the QIF file path and account exclusion list.
"""

import logging
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from src.application.config import AppConfig
from src.application.contracts.household import (
    Account,
    Household,
    ImportPreviewRequest,
    ImportPreviewResponse,
    ImportWarning,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HouseholdService:
    """Computes household portfolio by parsing the QIF source file.

    No file persistence — the QIF file is the single source of truth.
    Config stores ``qif_source_path`` and ``excluded_accounts``.
    """

    # -- public API --------------------------------------------------------

    def load(self) -> tuple[Household, bool]:
        """Parse the QIF source file and return the computed household.

        Returns:
            (household, exists) — ``exists`` is False when no QIF source
            is configured or the file is missing.
        """
        try:
            cfg = AppConfig()
        except Exception:
            logger.warning("Failed to load config", exc_info=True)
            return self._default_household(), False

        qif_path_str = cfg.qif_source_path
        if not qif_path_str:
            return self._default_household(), False

        qif_path = Path(qif_path_str).expanduser()
        if not qif_path.is_file():
            logger.warning("QIF source path configured but file not found: %s", qif_path)
            return self._default_household(), False

        try:
            from src.application.services.qif_import import preview_qif_import

            qif_content = qif_path.read_text(encoding="utf-8", errors="replace")
            preview = preview_qif_import(qif_content)

            excluded = set(cfg.excluded_accounts)
            accounts = [a for a in preview.accounts if a.name not in excluded]

            household = Household(
                name="My Household",
                accounts=accounts,
            )
            logger.info(
                "Loaded %d accounts from QIF: %s (excluded %d)",
                len(accounts), qif_path, len(excluded),
            )
            return household, True
        except Exception:
            logger.warning("Failed to parse QIF: %s", qif_path, exc_info=True)
            return self._default_household(), False

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
                    pdate = date.today()
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
                    val_date = date.today()

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

    def preview_qif_import(
        self,
        qif_content: str,
        household_name: str = "My Household",
    ) -> ImportPreviewResponse:
        """Parse QIF content and return proposed accounts."""
        from src.application.services.qif_import import preview_qif_import

        return preview_qif_import(qif_content, household_name)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _default_household() -> Household:
        return Household(name="My Household")

