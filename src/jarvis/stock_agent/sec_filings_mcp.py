"""SEC Filings MCP Server: access SEC EDGAR filings data.

Provides tools for:
- search_filings: Search for filings by company, type, date
- get_filing: Download and parse a specific filing
- get_recent_filings: Get recent filings for a ticker
- get_insider_transactions: Get insider trading data
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

EDGAR_BASE_URL = "https://efts.sec.gov/LATEST/search-index?q="
EDGAR_FILINGS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_FULL_TEXT_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_COMPANY_TICKERS = "https://www.sec.gov/files/company_tickers.json"

# Standard SEC filing types
FILING_TYPES = {
    "10-K": "Annual report",
    "10-Q": "Quarterly report",
    "8-K": "Current report (material events)",
    "DEF 14A": "Proxy statement",
    "S-1": "Registration statement (IPO)",
    "4": "Insider transaction",
    "13F-HR": "Institutional holdings",
    "SC 13D": "Beneficial ownership (>5%)",
}

# User agent required by SEC EDGAR API
SEC_USER_AGENT = "Jarvis/2.0 (autonomous-agent@example.com)"


@dataclass
class SECFiling:
    """Represents a single SEC filing."""
    accession_number: str
    filing_type: str
    filing_date: str
    description: str
    primary_document: str
    company_name: str
    cik: str

    def to_dict(self) -> dict:
        return {
            "accession_number": self.accession_number,
            "filing_type": self.filing_type,
            "filing_date": self.filing_date,
            "description": self.description,
            "primary_document": self.primary_document,
            "company_name": self.company_name,
            "cik": self.cik,
            "url": f"https://www.sec.gov/Archives/edgar/data/{self.cik}/{self.accession_number.replace('-', '')}/{self.primary_document}",
        }


class SECFilingsMCPServer:
    """MCP Server for SEC EDGAR filings data.

    Uses the SEC EDGAR full-text search and submissions APIs.
    Requires no API key — uses public EDGAR endpoints.
    """

    def __init__(self):
        self._ticker_to_cik: dict[str, str] = {}
        self._cik_loaded = False

    async def _ensure_cik_mapping(self) -> None:
        """Load ticker-to-CIK mapping from SEC."""
        if self._cik_loaded:
            return

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    EDGAR_COMPANY_TICKERS,
                    headers={"User-Agent": SEC_USER_AGENT},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for entry in data.values():
                        ticker = entry.get("ticker", "").upper()
                        cik = str(entry.get("cik_str", "")).zfill(10)
                        if ticker:
                            self._ticker_to_cik[ticker] = cik
                    self._cik_loaded = True
                    logger.info(f"Loaded {len(self._ticker_to_cik)} ticker-CIK mappings")
        except Exception as e:
            logger.warning(f"Failed to load CIK mapping: {e}")

    def _get_cik(self, ticker: str) -> str | None:
        """Get CIK number for a ticker."""
        return self._ticker_to_cik.get(ticker.upper())

    async def search_filings(
        self,
        query: str,
        filing_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Search SEC EDGAR for filings.

        Args:
            query: Search query (company name, ticker, or keywords)
            filing_type: Filter by filing type (10-K, 10-Q, 8-K, etc.)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            max_results: Maximum results

        Returns:
            List of filing dicts
        """
        try:
            import httpx

            params: dict[str, str] = {
                "q": query,
                "dateRange": "custom",
                "startdt": date_from or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                "enddt": date_to or datetime.now().strftime("%Y-%m-%d"),
            }
            if filing_type:
                params["forms"] = filing_type

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://efts.sec.gov/LATEST/search-index",
                    params=params,
                    headers={"User-Agent": SEC_USER_AGENT},
                )

                if resp.status_code != 200:
                    logger.warning(f"EDGAR search failed: {resp.status_code}")
                    return []

                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                results = []
                for hit in hits[:max_results]:
                    source = hit.get("_source", {})
                    results.append({
                        "filing_type": source.get("forms", ""),
                        "filing_date": source.get("file_date", ""),
                        "company_name": source.get("entity_name", ""),
                        "description": source.get("display_names", [""])[0] if source.get("display_names") else "",
                        "cik": source.get("entity_id", ""),
                        "accession_number": source.get("file_num", ""),
                    })

                return results

        except ImportError:
            logger.warning("httpx required for SEC filings search")
            return []
        except Exception as e:
            logger.error(f"EDGAR search error: {e}")
            return []

    async def get_recent_filings(
        self,
        ticker: str,
        filing_types: list[str] | None = None,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Get recent filings for a company by ticker.

        Args:
            ticker: Stock ticker symbol
            filing_types: Filter by types (default: ["10-K", "10-Q", "8-K"])
            max_results: Maximum results

        Returns:
            dict with company info and filings list
        """
        await self._ensure_cik_mapping()
        cik = self._get_cik(ticker)

        if not cik:
            return {"ticker": ticker, "error": "CIK not found for ticker"}

        types_filter = filing_types or ["10-K", "10-Q", "8-K"]

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    EDGAR_FILINGS_URL.format(cik=cik),
                    headers={"User-Agent": SEC_USER_AGENT},
                )

                if resp.status_code != 200:
                    return {"ticker": ticker, "error": f"EDGAR API error: {resp.status_code}"}

                data = resp.json()
                company_name = data.get("name", "")
                recent = data.get("filings", {}).get("recent", {})

                forms = recent.get("form", [])
                dates = recent.get("filingDate", [])
                accessions = recent.get("accessionNumber", [])
                primary_docs = recent.get("primaryDocument", [])
                descriptions = recent.get("primaryDocDescription", [])

                filings = []
                for i in range(min(len(forms), len(dates))):
                    if forms[i] in types_filter:
                        filing = SECFiling(
                            accession_number=accessions[i] if i < len(accessions) else "",
                            filing_type=forms[i],
                            filing_date=dates[i],
                            description=descriptions[i] if i < len(descriptions) else "",
                            primary_document=primary_docs[i] if i < len(primary_docs) else "",
                            company_name=company_name,
                            cik=cik,
                        )
                        filings.append(filing.to_dict())

                        if len(filings) >= max_results:
                            break

                return {
                    "ticker": ticker.upper(),
                    "company_name": company_name,
                    "cik": cik,
                    "filings_count": len(filings),
                    "filings": filings,
                }

        except ImportError:
            return {"ticker": ticker, "error": "httpx required"}
        except Exception as e:
            logger.error(f"EDGAR filing fetch error: {e}")
            return {"ticker": ticker, "error": str(e)}

    async def get_filing_content(
        self,
        ticker: str,
        filing_type: str = "10-K",
        max_length: int = 5000,
    ) -> dict[str, Any]:
        """Get the text content of a specific filing.

        Args:
            ticker: Stock ticker
            filing_type: Filing type to retrieve
            max_length: Maximum content length (characters)

        Returns:
            dict with filing metadata and text content
        """
        recent = await self.get_recent_filings(ticker, [filing_type], max_results=1)

        if "error" in recent:
            return recent

        filings = recent.get("filings", [])
        if not filings:
            return {"ticker": ticker, "error": f"No {filing_type} filings found"}

        filing = filings[0]
        url = filing.get("url", "")

        if not url:
            return {"ticker": ticker, "error": "Filing URL not available"}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": SEC_USER_AGENT},
                )

                if resp.status_code != 200:
                    return {"ticker": ticker, "error": f"Failed to fetch filing: {resp.status_code}"}

                content = resp.text

                # Strip HTML if present
                if "<html" in content.lower():
                    content = re.sub(r'<[^>]+>', ' ', content)
                    content = re.sub(r'\s+', ' ', content).strip()

                return {
                    "ticker": ticker.upper(),
                    "filing_type": filing_type,
                    "filing_date": filing.get("filing_date", ""),
                    "content_length": len(content),
                    "content": content[:max_length],
                    "truncated": len(content) > max_length,
                }

        except ImportError:
            return {"ticker": ticker, "error": "httpx required"}
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    async def get_insider_transactions(
        self,
        ticker: str,
        max_results: int = 20,
    ) -> dict[str, Any]:
        """Get recent insider transactions for a company.

        Args:
            ticker: Stock ticker
            max_results: Maximum transactions to return

        Returns:
            dict with insider transaction data
        """
        return await self.get_recent_filings(
            ticker,
            filing_types=["4"],
            max_results=max_results,
        )

    def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "search_filings",
                "description": "Search SEC EDGAR for company filings",
                "parameters": [
                    {"name": "query", "type": "string", "description": "Company name, ticker, or keywords"},
                    {"name": "filing_type", "type": "string", "description": "Filing type (10-K, 10-Q, 8-K)"},
                    {"name": "date_from", "type": "string", "description": "Start date (YYYY-MM-DD)"},
                ],
            },
            {
                "name": "get_recent_filings",
                "description": "Get recent SEC filings for a stock ticker",
                "parameters": [
                    {"name": "ticker", "type": "string", "description": "Stock ticker symbol"},
                    {"name": "filing_types", "type": "array", "description": "Filing types to filter"},
                ],
            },
            {
                "name": "get_filing_content",
                "description": "Get the text content of a specific SEC filing",
                "parameters": [
                    {"name": "ticker", "type": "string", "description": "Stock ticker symbol"},
                    {"name": "filing_type", "type": "string", "description": "Filing type (10-K, 10-Q, 8-K)"},
                ],
            },
            {
                "name": "get_insider_transactions",
                "description": "Get recent insider trading transactions",
                "parameters": [
                    {"name": "ticker", "type": "string", "description": "Stock ticker symbol"},
                ],
            },
        ]
