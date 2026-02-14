"""yfinance MCP Server: real-time stock data via Yahoo Finance.

Provides tools for:
- get_quote: Current price, volume, market cap
- get_history: Historical OHLCV data
- get_company_info: Company profile, financials, dividends
- get_options_chain: Options data for a given expiry
- search_tickers: Search for tickers by company name
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import yfinance
_yf = None


def _get_yf():
    global _yf
    if _yf is None:
        try:
            import yfinance as yf
            _yf = yf
        except ImportError:
            raise ImportError(
                "yfinance is required for the Stock Agent. "
                "Install with: pip install yfinance"
            )
    return _yf


@dataclass
class StockQuote:
    """Current stock quote snapshot."""
    symbol: str
    price: float
    change: float
    change_pct: float
    volume: int
    market_cap: float | None
    pe_ratio: float | None
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "change": self.change,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "market_cap": self.market_cap,
            "pe_ratio": self.pe_ratio,
            "timestamp": self.timestamp,
        }


class YFinanceMCPServer:
    """MCP Server for Yahoo Finance data.

    Can run as a standalone MCP server or be used as a library
    by the stock agent subagent.
    """

    def __init__(self):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 60  # 1 minute cache

    def _get_cached(self, key: str) -> Any | None:
        """Get cached value if still valid."""
        import time
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return val
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        import time
        self._cache[key] = (time.time(), value)

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get current stock quote.

        Args:
            symbol: Stock ticker (e.g., "AAPL", "MSFT")

        Returns:
            dict with price, change, volume, market cap, etc.
        """
        cache_key = f"quote:{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        yf = _get_yf()
        ticker = yf.Ticker(symbol)
        info = ticker.info

        quote = StockQuote(
            symbol=symbol.upper(),
            price=info.get("currentPrice", info.get("regularMarketPrice", 0.0)),
            change=info.get("regularMarketChange", 0.0),
            change_pct=info.get("regularMarketChangePercent", 0.0),
            volume=info.get("regularMarketVolume", 0),
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            timestamp=datetime.now().isoformat(),
        )

        result = quote.to_dict()
        self._set_cached(cache_key, result)
        return result

    def get_history(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict[str, Any]:
        """Get historical OHLCV data.

        Args:
            symbol: Stock ticker
            period: Data period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: Data interval ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")

        Returns:
            dict with dates and OHLCV arrays
        """
        cache_key = f"history:{symbol}:{period}:{interval}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        yf = _get_yf()
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return {"symbol": symbol, "error": "No data available", "data": []}

        data = []
        for date, row in hist.iterrows():
            data.append({
                "date": str(date.date()) if hasattr(date, "date") else str(date),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        result = {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "data_points": len(data),
            "data": data,
        }
        self._set_cached(cache_key, result)
        return result

    def get_company_info(self, symbol: str) -> dict[str, Any]:
        """Get company profile and financials.

        Args:
            symbol: Stock ticker

        Returns:
            dict with company name, sector, industry, financials, dividends
        """
        cache_key = f"info:{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        yf = _get_yf()
        ticker = yf.Ticker(symbol)
        info = ticker.info

        result = {
            "symbol": symbol.upper(),
            "name": info.get("longName", info.get("shortName", "")),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "country": info.get("country", ""),
            "website": info.get("website", ""),
            "description": info.get("longBusinessSummary", "")[:500],
            "employees": info.get("fullTimeEmployees"),
            "financials": {
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "revenue": info.get("totalRevenue"),
                "gross_profit": info.get("grossProfits"),
                "ebitda": info.get("ebitda"),
                "net_income": info.get("netIncomeToCommon"),
                "eps": info.get("trailingEps"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "debt_to_equity": info.get("debtToEquity"),
                "return_on_equity": info.get("returnOnEquity"),
                "profit_margin": info.get("profitMargins"),
            },
            "dividends": {
                "dividend_rate": info.get("dividendRate"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "ex_dividend_date": str(info.get("exDividendDate", "")),
            },
        }
        self._set_cached(cache_key, result)
        return result

    def get_options_chain(
        self,
        symbol: str,
        expiry: str | None = None,
    ) -> dict[str, Any]:
        """Get options chain data.

        Args:
            symbol: Stock ticker
            expiry: Expiry date string (YYYY-MM-DD). If None, uses nearest expiry.

        Returns:
            dict with calls and puts data
        """
        yf = _get_yf()
        ticker = yf.Ticker(symbol)

        expiries = ticker.options
        if not expiries:
            return {"symbol": symbol, "error": "No options available"}

        target_expiry = expiry if expiry and expiry in expiries else expiries[0]
        chain = ticker.option_chain(target_expiry)

        def df_to_list(df):
            records = []
            for _, row in df.iterrows():
                records.append({
                    "strike": float(row["strike"]),
                    "last_price": float(row["lastPrice"]),
                    "bid": float(row["bid"]),
                    "ask": float(row["ask"]),
                    "volume": int(row["volume"]) if row["volume"] == row["volume"] else 0,
                    "open_interest": int(row["openInterest"]) if row["openInterest"] == row["openInterest"] else 0,
                    "implied_volatility": round(float(row["impliedVolatility"]), 4),
                    "in_the_money": bool(row["inTheMoney"]),
                })
            return records

        return {
            "symbol": symbol.upper(),
            "expiry": target_expiry,
            "available_expiries": list(expiries[:10]),
            "calls": df_to_list(chain.calls),
            "puts": df_to_list(chain.puts),
        }

    def search_tickers(self, query: str, max_results: int = 10) -> list[dict]:
        """Search for tickers by company name or keyword.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of matching tickers with name and exchange
        """
        yf = _get_yf()

        try:
            # Use yfinance search
            results = yf.Tickers(query)
            # Fallback to a simple lookup
            tickers = query.upper().replace(",", " ").split()
            matches = []
            for t in tickers[:max_results]:
                try:
                    ticker = yf.Ticker(t)
                    info = ticker.info
                    if info.get("longName") or info.get("shortName"):
                        matches.append({
                            "symbol": t,
                            "name": info.get("longName", info.get("shortName", "")),
                            "exchange": info.get("exchange", ""),
                            "type": info.get("quoteType", ""),
                        })
                except Exception:
                    continue
            return matches
        except Exception as e:
            logger.warning(f"Ticker search failed: {e}")
            return []

    def get_tools(self) -> list[dict]:
        """Return MCP tool definitions for this server."""
        return [
            {
                "name": "get_quote",
                "description": "Get current stock quote with price, change, volume, and market cap",
                "parameters": [{"name": "symbol", "type": "string", "description": "Stock ticker symbol"}],
            },
            {
                "name": "get_history",
                "description": "Get historical OHLCV price data",
                "parameters": [
                    {"name": "symbol", "type": "string", "description": "Stock ticker symbol"},
                    {"name": "period", "type": "string", "description": "Data period (1d/5d/1mo/3mo/6mo/1y/5y/max)"},
                    {"name": "interval", "type": "string", "description": "Data interval (1d/1wk/1mo)"},
                ],
            },
            {
                "name": "get_company_info",
                "description": "Get company profile, financials, and dividend information",
                "parameters": [{"name": "symbol", "type": "string", "description": "Stock ticker symbol"}],
            },
            {
                "name": "get_options_chain",
                "description": "Get options chain (calls and puts) for a stock",
                "parameters": [
                    {"name": "symbol", "type": "string", "description": "Stock ticker symbol"},
                    {"name": "expiry", "type": "string", "description": "Option expiry date (YYYY-MM-DD)"},
                ],
            },
            {
                "name": "search_tickers",
                "description": "Search for stock tickers by company name",
                "parameters": [{"name": "query", "type": "string", "description": "Search query"}],
            },
        ]
