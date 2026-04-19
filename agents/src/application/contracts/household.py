"""Pydantic contracts for the household portfolio model.

The household model is the foundational data structure for the portfolio
intelligence system.  It stores accounts, positions (as tax lots), cash
holdings, and cash-flow assumptions for a wealthy-family household.

All monetary values use ``decimal.Decimal`` — never ``float``.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AccountType(StrEnum):
    """Supported brokerage / retirement account types."""

    TAXABLE = "taxable"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    FOUR01K = "401k"
    HSA = "hsa"
    TRUST = "trust"


class AssetClass(StrEnum):
    """Canonical asset classes for allocation decisions."""

    US_EQUITY = "us_equity"
    INTL_DEVELOPED = "intl_developed"
    EMERGING_MARKETS = "emerging_markets"
    US_TREASURIES = "us_treasuries"
    IG_CORPORATE = "ig_corporate"
    HIGH_YIELD = "high_yield"
    TIPS = "tips"
    REAL_ASSETS = "real_assets"
    CASH_MONEY_MARKET = "cash_money_market"


class CashFlowType(StrEnum):
    """Direction of a recurring cash flow."""

    CONTRIBUTION = "contribution"
    WITHDRAWAL = "withdrawal"
    INCOME = "income"


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class TaxLot(BaseModel):
    """A single tax lot within a position.

    Each lot retains its own cost basis and purchase date — lots are never
    merged or averaged.
    """

    ticker: str = Field(description="ETF ticker symbol (uppercase)")
    shares: Decimal = Field(gt=0, description="Number of shares in this lot")
    cost_basis_per_share: Decimal = Field(
        ge=0, description="Per-share cost basis at purchase"
    )
    purchase_date: date = Field(description="Date the lot was acquired")

    @field_validator("ticker", mode="before")
    @classmethod
    def _uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()


class CashHolding(BaseModel):
    """Cash or money-market position within an account.

    Cash is a first-class asset class for allocation math.
    """

    amount: Decimal = Field(ge=0, description="Dollar amount")
    valuation_date: date = Field(description="As-of date for this balance")
    is_money_market: bool = Field(
        default=False,
        description="True if this is a money-market fund, not settled cash",
    )
    ticker: str | None = Field(
        default=None,
        description="Money-market fund ticker (if is_money_market)",
    )
    counts_toward_liquidity_reserve: bool = Field(
        default=True,
        description="Whether this balance counts toward the liquidity reserve",
    )


class Account(BaseModel):
    """A single brokerage or retirement account."""

    name: str = Field(min_length=1, description="Human-readable account label")
    account_type: AccountType
    tax_lots: list[TaxLot] = Field(default_factory=list)
    cash_holdings: list[CashHolding] = Field(default_factory=list)


class CashFlowAssumption(BaseModel):
    """A recurring cash-flow assumption for simulation / planning."""

    description: str = Field(min_length=1)
    amount_annual: Decimal = Field(
        gt=0, description="Annual dollar amount (always positive; direction from type)"
    )
    flow_type: CashFlowType
    account_name: str | None = Field(
        default=None,
        description="Target account name (None = household-level)",
    )
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    end_year: int | None = Field(default=None, ge=2000, le=2100)
    inflation_adjusted: bool = Field(
        default=True,
        description="Whether this amount grows with inflation in simulations",
    )


# ---------------------------------------------------------------------------
# Root household model
# ---------------------------------------------------------------------------

class Household(BaseModel):
    """Root data model for a household's investment portfolio.

    Persisted to ``~/.config/finance-os/household.json``.
    ``schema_version`` tracks file-format migrations.
    ``revision`` is an optimistic-concurrency token incremented on every save.
    """

    name: str = Field(min_length=1, description="Household label")
    accounts: list[Account] = Field(default_factory=list)
    cash_flow_assumptions: list[CashFlowAssumption] = Field(default_factory=list)
    liquidity_reserve_floor: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Minimum cash/short-term balance to maintain (Total NAV basis)",
    )
    schema_version: int = Field(
        default=1,
        description="File-format version for future migrations",
    )
    revision: int = Field(
        default=0,
        description="Optimistic-concurrency token — incremented on every save",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of last persisted change",
    )


# ---------------------------------------------------------------------------
# API request / response contracts
# ---------------------------------------------------------------------------

class GetHouseholdResponse(BaseModel):
    """Response for GET /household."""

    household: Household
    exists: bool = Field(
        default=True,
        description="False when no household.json exists yet (returns defaults)",
    )


class UpdateHouseholdRequest(BaseModel):
    """Request for PUT /household.

    Clients supply the business fields; server owns schema_version,
    revision, and updated_at.  ``expected_revision`` is the concurrency
    check — the server rejects the write if it doesn't match.
    """

    name: str = Field(min_length=1)
    accounts: list[Account]
    cash_flow_assumptions: list[CashFlowAssumption] = Field(default_factory=list)
    liquidity_reserve_floor: Decimal = Field(default=Decimal("0"), ge=0)
    expected_revision: int = Field(
        description="Must match current revision on disk, or 409 Conflict"
    )


class UpdateHouseholdResponse(BaseModel):
    """Response for PUT /household."""

    household: Household
    journal_entry: str = Field(description="Summary written to the change journal")


class ImportPreviewRequest(BaseModel):
    """Request for POST /household/import/csv/preview.

    Parse-only: returns proposed accounts/lots + warnings without mutating
    persisted data.
    """

    csv_content: str = Field(min_length=1, description="Raw CSV file content")


class ImportWarning(BaseModel):
    """A warning generated during import parsing."""

    line: int | None = Field(default=None, description="CSV line number (if applicable)")
    message: str


class ImportPreviewResponse(BaseModel):
    """Preview result from CSV import parsing."""

    accounts: list[Account] = Field(description="Proposed accounts from parsed CSV")
    warnings: list[ImportWarning] = Field(default_factory=list)
    position_only: bool = Field(
        default=False,
        description="True if tax-lot fidelity could not be established",
    )
