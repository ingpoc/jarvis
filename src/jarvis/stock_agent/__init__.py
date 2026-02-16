"""Jarvis Stock Agent: Phase 2 domain subagent for financial analysis.

Components:
- yfinance MCP: Real-time stock data, historical prices, company info
- SEC filings MCP: 10-K, 10-Q, 8-K filings via EDGAR API
- Technical indicators: Moving averages, RSI, MACD, Bollinger Bands
- Backtesting framework: Strategy validation against historical data
"""

__version__ = "0.1.0"

from jarvis.stock_agent.yfinance_mcp import YFinanceMCPServer
from jarvis.stock_agent.sec_filings_mcp import SECFilingsMCPServer
from jarvis.stock_agent.technical_indicators import TechnicalIndicators
from jarvis.stock_agent.backtesting import BacktestEngine

__all__ = [
    "YFinanceMCPServer",
    "SECFilingsMCPServer",
    "TechnicalIndicators",
    "BacktestEngine",
]
