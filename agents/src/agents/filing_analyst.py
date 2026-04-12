"""Filing analyst agent — fetches and analyzes SEC filings from EDGAR.

Extracts key changes in risk factors, MD&A, financial statements,
and capex from 10-K/10-Q filings.
"""


import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from src.core.agent import AgentResponse, BaseAgent

# SEC EDGAR requires a User-Agent with app name and contact email
EDGAR_BASE_URL = "https://efts.sec.gov/LATEST"
EDGAR_FILINGS_URL = "https://data.sec.gov/submissions"
EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _edgar_user_agent() -> str:
    """Build the User-Agent string for SEC EDGAR requests.

    SEC requires format: 'AppName (contact@email.com)'.
    Reads email from AppConfig; falls back to a placeholder.
    """
    try:
        from src.application.config import AppConfig
        email = AppConfig().sec_edgar_email
    except Exception:  # noqa: BLE001
        email = ""
    if not email:
        return "finance-os/0.1.0"
    return f"finance-os/0.1.0 ({email})"

# Module-level cache for ticker→CIK mapping
_ticker_cik_cache: dict[str, str] = {}


@dataclass
class Filing:
    """A single SEC filing reference."""

    accession_number: str
    form_type: str
    filing_date: str
    primary_document: str
    description: str


def _load_ticker_map() -> dict[str, str]:
    """Load SEC's ticker→CIK mapping (cached after first call).

    Returns:
        Dict mapping uppercase ticker symbols to CIK strings.
    """
    global _ticker_cik_cache  # noqa: PLW0603
    if _ticker_cik_cache:
        return _ticker_cik_cache

    url = EDGAR_TICKERS_URL
    req = urllib.request.Request(url, headers={"User-Agent": _edgar_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                import gzip
                text = gzip.decompress(raw).decode("utf-8")
            data = json.loads(text)
        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", ""))
            if ticker and cik:
                _ticker_cik_cache[ticker] = cik
    except (urllib.error.URLError, json.JSONDecodeError, AttributeError, OSError):
        pass
    return _ticker_cik_cache


def resolve_cik(ticker: str) -> str:
    """Resolve a stock ticker to its SEC CIK number.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL').

    Returns:
        CIK string if found, empty string otherwise.
    """
    ticker_map = _load_ticker_map()
    return ticker_map.get(ticker.upper(), "")


def search_company(query: str) -> list[dict[str, Any]]:
    """Search for a company by name or ticker on EDGAR.

    Args:
        query: Company name or ticker symbol.

    Returns:
        List of matching company entries with CIK and name.
    """
    encoded_query = urllib.parse.quote(query)
    url = (
        f"{EDGAR_BASE_URL}/search-index"
        f"?q={encoded_query}"
        "&dateRange=custom&startdt=2020-01-01&forms=10-K,10-Q"
    )
    req = urllib.request.Request(url, headers={"User-Agent": _edgar_user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("hits", {}).get("hits", [])
    except (urllib.error.URLError, json.JSONDecodeError):
        return []


def get_company_filings(cik: str, form_types: list[str] | None = None) -> list[Filing]:
    """Fetch recent filings for a company by CIK number.

    Args:
        cik: SEC Central Index Key (zero-padded to 10 digits).
        form_types: Filter to specific form types (e.g., ['10-K', '10-Q']).

    Returns:
        List of Filing objects for recent filings.
    """
    padded_cik = cik.zfill(10)
    url = f"{EDGAR_FILINGS_URL}/CIK{padded_cik}.json"
    req = urllib.request.Request(url, headers={"User-Agent": _edgar_user_agent()})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError):
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    filings: list[Filing] = []
    allowed = set(form_types) if form_types else None

    for i in range(len(forms)):
        if allowed and forms[i] not in allowed:
            continue
        filings.append(Filing(
            accession_number=accessions[i] if i < len(accessions) else "",
            form_type=forms[i],
            filing_date=dates[i] if i < len(dates) else "",
            primary_document=primary_docs[i] if i < len(primary_docs) else "",
            description=descriptions[i] if i < len(descriptions) else "",
        ))
        if len(filings) >= 10:
            break

    return filings


def fetch_filing_text(cik: str, accession_number: str, document: str) -> str:
    """Fetch the text of a specific filing document.

    Args:
        cik: SEC CIK (zero-padded).
        accession_number: Filing accession number.
        document: Primary document filename.

    Returns:
        The filing text content (truncated to ~100K chars for LLM context).
    """
    padded_cik = cik.zfill(10)
    acc_clean = accession_number.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{padded_cik}/{acc_clean}/{document}"
    req = urllib.request.Request(url, headers={"User-Agent": _edgar_user_agent()})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            # Truncate for LLM context window
            if len(content) > 100_000:
                content = content[:100_000] + "\n\n[... truncated ...]"
            return content
    except (urllib.error.URLError, UnicodeDecodeError):
        return ""


class FilingAnalystAgent(BaseAgent):
    """Agent that analyzes SEC filings from EDGAR.

    Specializes in extracting key changes in:
    - Risk factors and risk language shifts
    - Management Discussion & Analysis (MD&A)
    - Capital expenditure and financial commitments
    - Supply chain commentary
    - Revenue/earnings guidance changes
    """

    def __init__(self) -> None:
        super().__init__(
            name="filing_analyst",
            description="Analyzes SEC filings (10-K/10-Q) to extract key changes and risks",
        )

    @property
    def system_prompt(self) -> str:
        """System prompt defining the filing analyst persona."""
        return (
            "You are a senior SEC filing analyst with 20 years of "
            "experience analyzing 10-K and 10-Q filings. "
            "Your role is to:\n\n"
            "1. **Extract Key Changes**: Identify material changes "
            "between filing periods — new risk factors, modified "
            "language, removed disclosures.\n\n"
            "2. **Risk Language Analysis**: Flag shifts in risk factor "
            "wording that signal emerging threats or changing business "
            "conditions.\n\n"
            "3. **MD&A Deep Dive**: Analyze Management Discussion & "
            "Analysis for tone shifts, revised guidance, and "
            "forward-looking statement changes.\n\n"
            "4. **CapEx & Commitments**: Track capital expenditure "
            "plans, contractual obligations, and off-balance-sheet "
            "arrangements.\n\n"
            "5. **Supply Chain**: Identify supplier concentration, "
            "geographic risks, and supply chain disruption "
            "indicators.\n\n"
            "You output structured analysis with:\n"
            "- A severity rating (LOW/MEDIUM/HIGH/CRITICAL) "
            "for each finding\n"
            "- Specific quotes from the filing supporting "
            "each finding\n"
            "- Comparison to prior period where available\n"
            "- Actionable implications for investment thesis\n\n"
            "Be precise. Cite section numbers and page references "
            "when available. Never speculate without evidence from "
            "the filing text."
        )

    async def run(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Execute filing analysis.

        The prompt should specify:
        - Company name or ticker
        - What to look for (risk changes, capex, etc.)
        - Optionally a specific filing accession number

        Args:
            prompt: Analysis request.
            **kwargs: May include 'cik', 'ticker', 'form_type'.

        Returns:
            AgentResponse with structured analysis or filing metadata.
        """
        ticker = kwargs.get("ticker", "")
        cik = kwargs.get("cik", "")
        form_type = kwargs.get("form_type", "10-K")

        # Auto-resolve ticker to CIK if ticker is provided without CIK
        if ticker and not cik:
            cik = resolve_cik(ticker)

        # If we have a CIK, fetch filings directly
        if cik:
            filings = get_company_filings(cik, [form_type])
            if not filings:
                return AgentResponse(
                    content=f"No {form_type} filings found for CIK {cik}.",
                    metadata={"cik": cik, "form_type": form_type},
                )

            # Format filing list
            lines = [f"Found {len(filings)} {form_type} filings for CIK {cik}:\n"]
            for f in filings:
                lines.append(
                    f"- **{f.form_type}** filed {f.filing_date} "
                    f"({f.description or f.primary_document}) "
                    f"[{f.accession_number}]"
                )

            return AgentResponse(
                content="\n".join(lines),
                metadata={
                    "cik": cik,
                    "form_type": form_type,
                    "filing_count": len(filings),
                    "filings": [
                        {
                            "accession": f.accession_number,
                            "form": f.form_type,
                            "date": f.filing_date,
                            "document": f.primary_document,
                        }
                        for f in filings
                    ],
                },
            )

        # If we have a ticker/name, search first
        if ticker or prompt:
            search_query = ticker or prompt.split()[0] if prompt else ""
            results = search_company(search_query)
            if not results:
                return AgentResponse(
                    content=f"No EDGAR results found for '{search_query}'. "
                    "Try providing a CIK number directly.",
                    metadata={"query": search_query},
                )

            lines = [f"EDGAR search results for '{search_query}':\n"]
            for hit in results[:5]:
                source = hit.get("_source", {})
                lines.append(
                    f"- {source.get('entity_name', 'Unknown')} "
                    f"({source.get('file_type', '')}, "
                    f"filed {source.get('file_date', 'N/A')})"
                )

            return AgentResponse(
                content="\n".join(lines),
                metadata={"query": search_query, "result_count": len(results)},
            )

        return AgentResponse(
            content="Please provide a company ticker, name, or CIK number to analyze.",
            metadata={},
        )
