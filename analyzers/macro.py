# ============================================================
# analyzers/macro.py -- Macro Environment Data Fetcher
# ============================================================
# v0.6: fetches all 4 macro tickers in one batch call.
# Macro data cannot be bundled with the stock ticker since
# they are separate Yahoo Finance symbols (^VIX, ^TNX, etc.).
# Output contract unchanged — macro_scorer.py unaffected.
# ============================================================

import time
import pandas as pd
import yfinance as yf


def _latest(series) -> float | None:
    if series is None or len(series) == 0:
        return None
    return round(float(series.iloc[-1]), 4)


def _change_pct(series, lookback: int = 30) -> float | None:
    if series is None or len(series) < 2:
        return None
    actual = min(lookback, len(series) - 1)
    start  = float(series.iloc[-(actual + 1)])
    end    = float(series.iloc[-1])
    if start == 0:
        return None
    return round((end - start) / start * 100, 4)


def _rolling_avg(series, window: int = 30) -> float | None:
    if series is None or len(series) < window:
        return None
    return round(float(series.tail(window).mean()), 4)


def _trend_label(change_pct, rising_threshold=5.0, falling_threshold=-5.0) -> str:
    if change_pct is None:
        return "unknown"
    if change_pct > rising_threshold:
        return "rising"
    if change_pct < falling_threshold:
        return "falling"
    return "stable"


def fetch_macro_data() -> dict:
    """
    Fetches all 4 macro indicators in a single batch download.
    Uses yf.download() which combines all tickers in one HTTP request.
    """
    missing = []

    # ── Single batch download for all 4 macro tickers ─────────
    # yf.download() sends one request instead of 4 separate ones
    print("  [Macro] Batch downloading VIX, TNX, IRX, GSPC...")
    try:
        time.sleep(0.5)
        raw = yf.download(
            tickers  = "^VIX ^TNX ^IRX ^GSPC",
            period   = "3mo",
            interval = "1d",
            auto_adjust = True,
            progress = False,
        )

        def _extract(symbol: str) -> pd.Series | None:
            """Extract Close series for one symbol from multi-ticker download."""
            try:
                if "Close" in raw.columns:
                    if hasattr(raw["Close"], "columns"):
                        # Multi-ticker: columns are (symbol, ...)
                        col = next(
                            (c for c in raw["Close"].columns if symbol in str(c)),
                            None
                        )
                        if col is not None:
                            s = raw["Close"][col].dropna()
                            return s if not s.empty else None
                    else:
                        # Single ticker fallback
                        s = raw["Close"].dropna()
                        return s if not s.empty else None
            except Exception:
                pass
            return None

        vix_series  = _extract("^VIX")
        tnx_series  = _extract("^TNX")
        irx_series  = _extract("^IRX")
        sp500_series = _extract("^GSPC")

    except Exception as e:
        print(f"  [Macro] Batch download failed: {e} — falling back to individual fetches")
        # Fallback: individual fetches
        def _fetch_series(symbol: str, period: str = "3mo") -> pd.Series | None:
            try:
                time.sleep(0.5)
                df = yf.Ticker(symbol).history(period=period, interval="1d")
                if df.empty or "Close" not in df.columns:
                    return None
                return df["Close"].dropna()
            except Exception:
                return None

        vix_series   = _fetch_series("^VIX",  "3mo")
        tnx_series   = _fetch_series("^TNX",  "3mo")
        irx_series   = _fetch_series("^IRX",  "1mo")
        sp500_series = _fetch_series("^GSPC", "3mo")

    # ── VIX ───────────────────────────────────────────────────
    vix            = _latest(vix_series)
    vix_30d_avg    = _rolling_avg(vix_series, window=30)
    vix_change_30d = _change_pct(vix_series, lookback=30)
    vix_trend      = _trend_label(vix_change_30d, rising_threshold=20.0, falling_threshold=-20.0)
    if vix is None:
        missing.append("vix")

    # ── 10Y Treasury ──────────────────────────────────────────
    treasury_10y   = _latest(tnx_series)
    rate_trend_30d = None
    rate_direction = "unknown"
    if tnx_series is not None and len(tnx_series) >= 2:
        actual         = min(30, len(tnx_series) - 1)
        rate_trend_30d = round(
            float(tnx_series.iloc[-1]) - float(tnx_series.iloc[-(actual + 1)]), 4
        )
        if rate_trend_30d > 0.20:
            rate_direction = "tightening"
        elif rate_trend_30d < -0.20:
            rate_direction = "easing"
        else:
            rate_direction = "stable"
    if treasury_10y is None:
        missing.append("treasury_10y")

    # ── 3M Treasury ───────────────────────────────────────────
    treasury_3m = _latest(irx_series)
    if treasury_3m is None:
        missing.append("treasury_3m")

    # ── Yield Curve ───────────────────────────────────────────
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

    # ── S&P 500 ───────────────────────────────────────────────
    sp500_trend_30d = _change_pct(sp500_series, lookback=30)
    market_regime   = "unknown"
    if sp500_trend_30d is not None:
        if sp500_trend_30d > 3.0:
            market_regime = "risk_on"
        elif sp500_trend_30d < -3.0:
            market_regime = "risk_off"
        else:
            market_regime = "neutral"
    if sp500_trend_30d is None:
        missing.append("sp500")

    # ── Data quality ──────────────────────────────────────────
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
