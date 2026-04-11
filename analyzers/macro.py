# ============================================================
# analyzers/macro.py -- Macro Environment Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches raw macroeconomic indicators from Yahoo Finance.
#
# Data sources (all via yfinance, no API key required):
#   ^VIX  : CBOE Volatility Index (fear gauge)
#   ^TNX  : 10-Year US Treasury Yield
#   ^IRX  : 13-Week (3-Month) Treasury Bill Yield
#   ^GSPC : S&P 500 Index (market direction proxy)
#
# Output contract (standardised dict for macro_scorer.py):
#   All fields documented below. If a field cannot be fetched,
#   it is set to None and recorded in missing_fields[].
#   data_quality: "full" | "partial" | "failed"
#
# Future data source migration:
#   Replace only this file. macro_scorer.py receives the same
#   standardised dict regardless of the underlying data source.
# ============================================================

import time
import pandas as pd
import yfinance as yf


# ============================================================
# Internal fetch helpers
# ============================================================

def _fetch_series(symbol: str, period: str = "3mo") -> pd.Series | None:
    """
    Fetches closing price series for a symbol.
    Returns None on any failure (weekend gaps, delisted, etc.)
    """
    try:
        time.sleep(0.5)
        df = yf.Ticker(symbol).history(period=period, interval="1d")
        if df.empty or "Close" not in df.columns:
            return None
        return df["Close"].dropna()
    except Exception:
        return None


def _latest(series: pd.Series | None) -> float | None:
    """Returns the most recent value from a series, or None."""
    if series is None or len(series) == 0:
        return None
    return round(float(series.iloc[-1]), 4)


def _change_pct(series: pd.Series | None, lookback: int = 30) -> float | None:
    """
    Returns % change over the last `lookback` trading days.
    Positive = rising, Negative = falling.
    """
    if series is None or len(series) < 2:
        return None
    actual = min(lookback, len(series) - 1)
    start  = float(series.iloc[-(actual + 1)])
    end    = float(series.iloc[-1])
    if start == 0:
        return None
    return round((end - start) / start * 100, 4)


def _rolling_avg(series: pd.Series | None, window: int = 30) -> float | None:
    """Returns rolling average over `window` trading days."""
    if series is None or len(series) < window:
        return None
    return round(float(series.tail(window).mean()), 4)


def _trend_label(change_pct: float | None,
                 rising_threshold: float = 5.0,
                 falling_threshold: float = -5.0) -> str:
    """Converts a % change into a directional trend label."""
    if change_pct is None:
        return "unknown"
    if change_pct > rising_threshold:
        return "rising"
    if change_pct < falling_threshold:
        return "falling"
    return "stable"


# ============================================================
# Main fetch function
# ============================================================

def fetch_macro_data() -> dict:
    """
    Fetches all macro indicators and returns a standardised dict.

    This is the ONLY function called externally from this file.

    Returns:
    {
      # VIX
      "vix":              float | None   current VIX level
      "vix_30d_avg":      float | None   30-day average VIX
      "vix_change_30d":   float | None   % change in VIX over 30 days
      "vix_trend":        str            "rising"|"falling"|"stable"|"unknown"

      # 10-Year Treasury
      "treasury_10y":     float | None   current 10Y yield (%)
      "rate_trend_30d":   float | None   absolute pp change in 10Y over 30 days
      "rate_direction":   str            "tightening"|"easing"|"stable"|"unknown"

      # 3-Month Treasury
      "treasury_3m":      float | None   current 3M yield (%)

      # Yield Curve
      "yield_spread":     float | None   10Y minus 3M (pp). Negative = inverted.
      "yield_curve":      str            "normal"|"flat"|"inverted"|"unknown"

      # S&P 500
      "sp500_trend_30d":  float | None   % change in S&P 500 over 30 days
      "market_regime":    str            "risk_on"|"neutral"|"risk_off"|"unknown"

      # Metadata
      "data_quality":     str            "full"|"partial"|"failed"
      "missing_fields":   list[str]
    }
    """
    missing = []

    # ── VIX ──────────────────────────────────────────────────
    vix_series     = _fetch_series("^VIX", period="3mo")
    vix            = _latest(vix_series)
    vix_30d_avg    = _rolling_avg(vix_series, window=30)
    vix_change_30d = _change_pct(vix_series, lookback=30)
    # VIX moves fast -- use 20% threshold for trend label
    vix_trend      = _trend_label(vix_change_30d,
                                  rising_threshold=20.0,
                                  falling_threshold=-20.0)
    if vix is None:
        missing.append("vix")

    # ── 10-Year Treasury Yield ────────────────────────────────
    tnx_series    = _fetch_series("^TNX", period="3mo")
    treasury_10y  = _latest(tnx_series)

    # Rate trend: absolute change in yield (percentage points, not %)
    # e.g. yield goes from 4.0% to 4.5% → rate_trend_30d = +0.50
    rate_trend_30d = None
    rate_direction = "unknown"
    if tnx_series is not None and len(tnx_series) >= 2:
        actual         = min(30, len(tnx_series) - 1)
        rate_trend_30d = round(
            float(tnx_series.iloc[-1]) - float(tnx_series.iloc[-(actual + 1)]),
            4
        )
        if rate_trend_30d > 0.20:
            rate_direction = "tightening"   # yields rising = tighter financial conditions
        elif rate_trend_30d < -0.20:
            rate_direction = "easing"       # yields falling = easier financial conditions
        else:
            rate_direction = "stable"

    if treasury_10y is None:
        missing.append("treasury_10y")

    # ── 3-Month Treasury Yield ────────────────────────────────
    irx_series  = _fetch_series("^IRX", period="1mo")
    treasury_3m = _latest(irx_series)
    if treasury_3m is None:
        missing.append("treasury_3m")

    # ── Yield Curve (10Y - 3M spread) ────────────────────────
    # Normal:   10Y > 3M (positive spread) -- healthy expansion
    # Flat:     near zero -- slowdown concern
    # Inverted: 3M > 10Y (negative spread) -- historical recession signal
    # Note: inversion leads recession by 12-18 months on average,
    #       so we treat it as elevated risk, not immediate catastrophe.
    yield_spread = None
    yield_curve  = "unknown"
    if treasury_10y is not None and treasury_3m is not None:
        yield_spread = round(treasury_10y - treasury_3m, 4)
        if yield_spread > 0.50:
            yield_curve = "normal"
        elif yield_spread > -0.25:
            yield_curve = "flat"
        else:
            yield_curve = "inverted"

    # ── S&P 500 (Market Regime) ───────────────────────────────
    sp500_series    = _fetch_series("^GSPC", period="3mo")
    sp500_trend_30d = _change_pct(sp500_series, lookback=30)
    market_regime   = "unknown"

    if sp500_trend_30d is not None:
        if sp500_trend_30d > 3.0:
            market_regime = "risk_on"    # broad market rallying, appetite for risk
        elif sp500_trend_30d < -3.0:
            market_regime = "risk_off"   # broad market selling, flight to safety
        else:
            market_regime = "neutral"

    if sp500_trend_30d is None:
        missing.append("sp500")

    # ── Data quality summary ──────────────────────────────────
    # VIX and 10Y are critical -- without these we cannot score
    critical_missing = [f for f in missing if f in ("vix", "treasury_10y")]

    if len(missing) == 0:
        data_quality = "full"
    elif critical_missing:
        data_quality = "failed"
    else:
        data_quality = "partial"

    return {
        "vix":             vix,
        "vix_30d_avg":     vix_30d_avg,
        "vix_change_30d":  vix_change_30d,
        "vix_trend":       vix_trend,

        "treasury_10y":    treasury_10y,
        "rate_trend_30d":  rate_trend_30d,
        "rate_direction":  rate_direction,

        "treasury_3m":     treasury_3m,

        "yield_spread":    yield_spread,
        "yield_curve":     yield_curve,

        "sp500_trend_30d": sp500_trend_30d,
        "market_regime":   market_regime,

        "data_quality":    data_quality,
        "missing_fields":  missing,
    }
