"""Pydantic contracts for the household portfolio model.

The household model is the foundational data structure for the portfolio
intelligence system.  It stores accounts, positions (as tax lots), cash
holdings, and cash-flow assumptions for a wealthy-family household.

All monetary values use ``decimal.Decimal`` — never ``float``.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, field_validator, model_validator

# Decimal type that always serializes as fixed-point (never scientific notation)
FixedDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda v: format(v, "f"), return_type=str),
]

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
    shares: FixedDecimal = Field(gt=0, description="Number of shares in this lot")
    cost_basis_per_share: FixedDecimal = Field(
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

    amount: FixedDecimal = Field(ge=0, description="Dollar amount")
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
    amount_annual: FixedDecimal = Field(
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

    @model_validator(mode="after")
    def _check_year_range(self) -> "CashFlowAssumption":
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.end_year < self.start_year
        ):
            msg = f"end_year ({self.end_year}) must be >= start_year ({self.start_year})"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Root household model
# ---------------------------------------------------------------------------

class Household(BaseModel):
    """Root data model for a household's investment portfolio.

    Computed on the fly from the read-only QIF source file.
    No persistence — the QIF file is the single source of truth.
    """

    name: str = Field(min_length=1, description="Household label")
    accounts: list[Account] = Field(default_factory=list)
    cash_flow_assumptions: list[CashFlowAssumption] = Field(default_factory=list)
    liquidity_reserve_floor: FixedDecimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Minimum cash/short-term balance to maintain (Total NAV basis)",
    )
    schema_version: int = Field(
        default=1,
        description="File-format version for future migrations",
    )


# ---------------------------------------------------------------------------
# API request / response contracts
# ---------------------------------------------------------------------------

class GetHouseholdResponse(BaseModel):
    """Response for GET /household."""

    household: Household
    exists: bool = Field(
        default=True,
        description="False when no QIF source is configured (returns defaults)",
    )


class ImportPreviewRequest(BaseModel):
    """Request for POST /household/import/csv/preview.

    Parse-only: returns proposed accounts/lots + warnings without mutating
    persisted data.
    """

    csv_content: str = Field(min_length=1, description="Raw CSV file content")


class QifImportPreviewRequest(BaseModel):
    """Request for POST /household/import/qif/preview."""

    qif_content: str = Field(min_length=1, description="Raw QIF file content")
    household_name: str = Field(default="My Household", min_length=1)


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
