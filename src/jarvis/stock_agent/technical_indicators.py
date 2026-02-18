"""Technical indicators for stock analysis.

Implements common technical analysis indicators:
- Moving averages (SMA, EMA, WMA)
- Momentum (RSI, MACD, Stochastic)
- Volatility (Bollinger Bands, ATR)
- Volume (OBV, VWAP)
- Trend (ADX)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """Result of a technical indicator calculation."""
    name: str
    values: list[float | None]
    signal: str  # "bullish", "bearish", "neutral"
    description: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "latest_value": self.values[-1] if self.values else None,
            "signal": self.signal,
            "description": self.description,
            "data_points": len(self.values),
        }


class TechnicalIndicators:
    """Technical analysis indicator calculations.

    All methods accept lists of price data (floats) and return
    IndicatorResult objects.
    """

    # --- Moving Averages ---

    @staticmethod
    def sma(prices: list[float], period: int = 20) -> IndicatorResult:
        """Simple Moving Average."""
        if len(prices) < period:
            return IndicatorResult("SMA", [], "neutral", f"Insufficient data (need {period})")

        values: list[float | None] = [None] * (period - 1)
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1: i + 1]
            values.append(sum(window) / period)

        # Signal: price above SMA = bullish
        latest_price = prices[-1]
        latest_sma = values[-1]
        if latest_sma is not None:
            signal = "bullish" if latest_price > latest_sma else "bearish"
            desc = f"SMA({period}) = {latest_sma:.2f}, price {'above' if signal == 'bullish' else 'below'}"
        else:
            signal = "neutral"
            desc = "Insufficient data"

        return IndicatorResult(f"SMA({period})", values, signal, desc)

    @staticmethod
    def ema(prices: list[float], period: int = 20) -> IndicatorResult:
        """Exponential Moving Average."""
        if len(prices) < period:
            return IndicatorResult("EMA", [], "neutral", f"Insufficient data (need {period})")

        multiplier = 2 / (period + 1)
        values: list[float | None] = [None] * (period - 1)

        # Seed EMA with SMA
        initial_sma = sum(prices[:period]) / period
        values.append(initial_sma)

        for i in range(period, len(prices)):
            prev_ema = values[-1]
            if prev_ema is not None:
                ema_val = (prices[i] - prev_ema) * multiplier + prev_ema
                values.append(ema_val)

        latest_price = prices[-1]
        latest_ema = values[-1]
        if latest_ema is not None:
            signal = "bullish" if latest_price > latest_ema else "bearish"
            desc = f"EMA({period}) = {latest_ema:.2f}"
        else:
            signal = "neutral"
            desc = "Insufficient data"

        return IndicatorResult(f"EMA({period})", values, signal, desc)

    # --- Momentum ---

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> IndicatorResult:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return IndicatorResult("RSI", [], "neutral", f"Insufficient data (need {period + 1})")

        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

        gains = [max(0, c) for c in changes]
        losses = [max(0, -c) for c in changes]

        values: list[float | None] = [None] * period

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            values.append(100 - (100 / (1 + rs)))

        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                values.append(100 - (100 / (1 + rs)))

        latest_rsi = values[-1]
        if latest_rsi is not None:
            if latest_rsi > 70:
                signal = "bearish"
                desc = f"RSI({period}) = {latest_rsi:.1f} — OVERBOUGHT"
            elif latest_rsi < 30:
                signal = "bullish"
                desc = f"RSI({period}) = {latest_rsi:.1f} — OVERSOLD"
            else:
                signal = "neutral"
                desc = f"RSI({period}) = {latest_rsi:.1f}"
        else:
            signal = "neutral"
            desc = "Insufficient data"

        return IndicatorResult(f"RSI({period})", values, signal, desc)

    @staticmethod
    def macd(
        prices: list[float],
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ) -> dict[str, IndicatorResult]:
        """Moving Average Convergence Divergence.

        Returns dict with 'macd', 'signal', and 'histogram' results.
        """
        if len(prices) < slow:
            empty = IndicatorResult("MACD", [], "neutral", f"Insufficient data (need {slow})")
            return {"macd": empty, "signal": empty, "histogram": empty}

        # Calculate fast and slow EMAs
        fast_ema = TechnicalIndicators.ema(prices, fast)
        slow_ema = TechnicalIndicators.ema(prices, slow)

        # MACD line = fast EMA - slow EMA
        macd_values: list[float | None] = []
        for f, s in zip(fast_ema.values, slow_ema.values):
            if f is not None and s is not None:
                macd_values.append(f - s)
            else:
                macd_values.append(None)

        # Signal line = EMA of MACD line
        valid_macd = [v for v in macd_values if v is not None]
        if len(valid_macd) >= signal_period:
            signal_ema = TechnicalIndicators.ema(valid_macd, signal_period)
            signal_values = [None] * (len(macd_values) - len(signal_ema.values)) + signal_ema.values
        else:
            signal_values = [None] * len(macd_values)

        # Histogram = MACD - Signal
        histogram_values: list[float | None] = []
        for m, s in zip(macd_values, signal_values):
            if m is not None and s is not None:
                histogram_values.append(m - s)
            else:
                histogram_values.append(None)

        # Signal determination
        latest_hist = histogram_values[-1] if histogram_values else None
        if latest_hist is not None:
            if latest_hist > 0:
                sig = "bullish"
                desc = f"MACD histogram positive ({latest_hist:.4f}) — bullish momentum"
            else:
                sig = "bearish"
                desc = f"MACD histogram negative ({latest_hist:.4f}) — bearish momentum"
        else:
            sig = "neutral"
            desc = "Insufficient data"

        return {
            "macd": IndicatorResult("MACD", macd_values, sig, desc),
            "signal": IndicatorResult("Signal", signal_values, sig, desc),
            "histogram": IndicatorResult("Histogram", histogram_values, sig, desc),
        }

    @staticmethod
    def stochastic(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        k_period: int = 14,
        d_period: int = 3,
    ) -> dict[str, IndicatorResult]:
        """Stochastic Oscillator (%K and %D)."""
        if len(closes) < k_period:
            empty = IndicatorResult("Stochastic", [], "neutral", "Insufficient data")
            return {"k": empty, "d": empty}

        k_values: list[float | None] = [None] * (k_period - 1)

        for i in range(k_period - 1, len(closes)):
            high_window = highs[i - k_period + 1: i + 1]
            low_window = lows[i - k_period + 1: i + 1]
            highest = max(high_window)
            lowest = min(low_window)

            if highest == lowest:
                k_values.append(50.0)
            else:
                k_values.append(((closes[i] - lowest) / (highest - lowest)) * 100)

        # %D = SMA of %K
        valid_k = [v for v in k_values if v is not None]
        d_values: list[float | None] = [None] * (len(k_values) - len(valid_k))
        for i in range(len(valid_k)):
            if i < d_period - 1:
                d_values.append(None)
            else:
                window = valid_k[i - d_period + 1: i + 1]
                d_values.append(sum(window) / d_period)

        latest_k = k_values[-1]
        if latest_k is not None:
            if latest_k > 80:
                sig = "bearish"
            elif latest_k < 20:
                sig = "bullish"
            else:
                sig = "neutral"
        else:
            sig = "neutral"

        return {
            "k": IndicatorResult(f"%K({k_period})", k_values, sig, f"%K = {latest_k:.1f}" if latest_k else "N/A"),
            "d": IndicatorResult(f"%D({d_period})", d_values, sig, f"%D = {d_values[-1]:.1f}" if d_values[-1] else "N/A"),
        }

    # --- Volatility ---

    @staticmethod
    def bollinger_bands(
        prices: list[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> dict[str, IndicatorResult]:
        """Bollinger Bands (upper, middle, lower)."""
        if len(prices) < period:
            empty = IndicatorResult("BB", [], "neutral", "Insufficient data")
            return {"upper": empty, "middle": empty, "lower": empty}

        middle_result = TechnicalIndicators.sma(prices, period)
        upper_values: list[float | None] = []
        lower_values: list[float | None] = []

        for i, mid in enumerate(middle_result.values):
            if mid is None:
                upper_values.append(None)
                lower_values.append(None)
            else:
                start = max(0, i - period + 1)
                window = prices[start: i + 1]
                mean = sum(window) / len(window)
                variance = sum((x - mean) ** 2 for x in window) / len(window)
                sd = math.sqrt(variance)
                upper_values.append(mid + std_dev * sd)
                lower_values.append(mid - std_dev * sd)

        latest_price = prices[-1]
        upper = upper_values[-1]
        lower = lower_values[-1]

        if upper is not None and lower is not None:
            if latest_price > upper:
                sig = "bearish"
                desc = f"Price above upper band ({upper:.2f}) — overbought"
            elif latest_price < lower:
                sig = "bullish"
                desc = f"Price below lower band ({lower:.2f}) — oversold"
            else:
                sig = "neutral"
                band_width = upper - lower
                desc = f"Price within bands, width = {band_width:.2f}"
        else:
            sig = "neutral"
            desc = "Insufficient data"

        return {
            "upper": IndicatorResult(f"BB Upper({period})", upper_values, sig, desc),
            "middle": IndicatorResult(f"BB Middle({period})", middle_result.values, sig, desc),
            "lower": IndicatorResult(f"BB Lower({period})", lower_values, sig, desc),
        }

    @staticmethod
    def atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> IndicatorResult:
        """Average True Range (volatility indicator)."""
        if len(closes) < period + 1:
            return IndicatorResult("ATR", [], "neutral", "Insufficient data")

        true_ranges: list[float] = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        values: list[float | None] = [None] * period
        atr_val = sum(true_ranges[:period]) / period
        values.append(atr_val)

        for i in range(period, len(true_ranges)):
            atr_val = (atr_val * (period - 1) + true_ranges[i]) / period
            values.append(atr_val)

        latest_atr = values[-1]
        desc = f"ATR({period}) = {latest_atr:.2f}" if latest_atr else "N/A"

        return IndicatorResult(f"ATR({period})", values, "neutral", desc)

    # --- Volume ---

    @staticmethod
    def obv(closes: list[float], volumes: list[int]) -> IndicatorResult:
        """On-Balance Volume."""
        if len(closes) < 2:
            return IndicatorResult("OBV", [], "neutral", "Insufficient data")

        values: list[float | None] = [float(volumes[0])]
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                values.append(values[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                values.append(values[-1] - volumes[i])
            else:
                values.append(values[-1])

        # Trend detection via OBV slope
        if len(values) >= 5:
            recent = [v for v in values[-5:] if v is not None]
            if len(recent) >= 2:
                slope = recent[-1] - recent[0]
                if slope > 0:
                    sig = "bullish"
                    desc = f"OBV trending up (slope: {slope:,.0f})"
                else:
                    sig = "bearish"
                    desc = f"OBV trending down (slope: {slope:,.0f})"
            else:
                sig = "neutral"
                desc = "OBV flat"
        else:
            sig = "neutral"
            desc = "Insufficient data for trend"

        return IndicatorResult("OBV", values, sig, desc)

    @staticmethod
    def vwap(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[int],
    ) -> IndicatorResult:
        """Volume Weighted Average Price."""
        if not closes:
            return IndicatorResult("VWAP", [], "neutral", "No data")

        values: list[float | None] = []
        cumulative_tp_vol = 0.0
        cumulative_vol = 0

        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_tp_vol += typical_price * volumes[i]
            cumulative_vol += volumes[i]

            if cumulative_vol > 0:
                values.append(cumulative_tp_vol / cumulative_vol)
            else:
                values.append(None)

        latest_vwap = values[-1]
        latest_price = closes[-1]
        if latest_vwap is not None:
            sig = "bullish" if latest_price > latest_vwap else "bearish"
            desc = f"VWAP = {latest_vwap:.2f}, price {'above' if sig == 'bullish' else 'below'}"
        else:
            sig = "neutral"
            desc = "N/A"

        return IndicatorResult("VWAP", values, sig, desc)

    # --- Composite Analysis ---

    @classmethod
    def full_analysis(
        cls,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[int],
    ) -> dict[str, Any]:
        """Run all indicators and produce a composite analysis.

        Returns a summary with individual indicator results and
        an overall signal consensus.
        """
        results = {}

        # Moving averages
        results["sma_20"] = cls.sma(closes, 20).to_dict()
        results["sma_50"] = cls.sma(closes, 50).to_dict()
        results["ema_12"] = cls.ema(closes, 12).to_dict()

        # Momentum
        results["rsi_14"] = cls.rsi(closes, 14).to_dict()
        macd_result = cls.macd(closes)
        results["macd"] = macd_result["macd"].to_dict()

        # Volatility
        bb = cls.bollinger_bands(closes)
        results["bollinger_upper"] = bb["upper"].to_dict()
        results["bollinger_lower"] = bb["lower"].to_dict()
        results["atr_14"] = cls.atr(highs, lows, closes, 14).to_dict()

        # Volume
        results["obv"] = cls.obv(closes, volumes).to_dict()
        results["vwap"] = cls.vwap(highs, lows, closes, volumes).to_dict()

        # Consensus
        signals = [r["signal"] for r in results.values()]
        bullish = signals.count("bullish")
        bearish = signals.count("bearish")
        total = bullish + bearish

        if total == 0:
            consensus = "neutral"
            strength = 0.0
        elif bullish > bearish:
            consensus = "bullish"
            strength = bullish / total
        else:
            consensus = "bearish"
            strength = bearish / total

        return {
            "indicators": results,
            "consensus": {
                "signal": consensus,
                "strength": round(strength, 2),
                "bullish_count": bullish,
                "bearish_count": bearish,
                "neutral_count": signals.count("neutral"),
            },
        }
