"""Pydantic contracts for ticker lookup endpoints."""

from pydantic import BaseModel, Field


class TickerSummary(BaseModel):
    """Company summary from Yahoo Finance."""

    symbol: str = Field(description="Ticker symbol")
    name: str = Field(description="Company name")
    sector: str = Field(default="", description="Company sector")
    industry: str = Field(default="", description="Company industry")
    market_cap: str = Field(default="", description="Market capitalization (decimal string)")
    currency: str = Field(default="USD", description="Quote currency")
    current_price: str = Field(default="", description="Current price (decimal string)")
    previous_close: str = Field(default="", description="Previous close (decimal string)")
    fifty_two_week_high: str = Field(default="", description="52-week high (decimal string)")
    fifty_two_week_low: str = Field(default="", description="52-week low (decimal string)")
    earnings_date: str = Field(default="", description="Next earnings date (ISO 8601)")
    description: str = Field(default="", description="Business description")


class TickerTranscript(BaseModel):
    """Earnings transcript for a ticker (best-effort)."""

    symbol: str = Field(description="Ticker symbol")
    available: bool = Field(description="Whether a transcript was found")
    transcript: str = Field(default="", description="Earnings call transcript text")
    period: str = Field(default="", description="Fiscal period (e.g. 'Q1 2025')")
    source: str = Field(default="yfinance", description="Data source attribution")
