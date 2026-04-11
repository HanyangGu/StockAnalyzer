# ============================================================
# analyzers/sentiment/options.py -- Options Chain Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches options chain data from Yahoo Finance and returns
# a standardised dict for options_scorer.py to process.
#
# Data source (yfinance):
#   yf.Ticker(symbol).options      -- available expiry dates
#   yf.Ticker(symbol).option_chain -- calls + puts DataFrames
#   yf.Ticker(symbol).info         -- current price
#
# Data strategy:
#   Selects the nearest expiry within MIN_DTE to MAX_DTE window.
#   Falls back to nearest available expiry if none in window.
#   Returns both volume-filtered chains (for PCR scoring) and
#   unfiltered chains (for Max Pain / Wall calculations).
#
# Output contract (standardised -- data source independent):
# {
#   "calls":         pd.DataFrame  volume-filtered call options
#   "puts":          pd.DataFrame  volume-filtered put options
#   "calls_all":     pd.DataFrame  all call options (unfiltered)
#   "puts_all":      pd.DataFrame  all put options (unfiltered)
#   "expiry":        str           selected expiry date string
#   "days_to_exp":   int           days to expiration
#   "avg_iv":        float         average implied volatility (0-1 scale)
#   "current_price": float | None  current stock price
#   "data_quality":  str           "full" | "partial" | "failed"
# }
#
# Note: DataFrames are passed directly to options_scorer.py.
# If the data source changes (e.g. Polygon, CBOE), replace this
# file and ensure the scorer receives the same column names:
#   calls/puts: "strike", "volume", "openInterest", "impliedVolatility"
#
# Future data source migration:
#   Replace only this file. options_scorer.py receives the same
#   standardised dict regardless of the underlying data source.
# ============================================================

import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# ============================================================
# Constants
# ============================================================

MIN_DTE    = 20     # minimum days to expiration
MAX_DTE    = 90     # maximum days to expiration
MIN_VOLUME = 100    # minimum total volume to trust PCR signal


# ============================================================
# Main fetch function
# ============================================================

def fetch_options_data(ticker_symbol: str) -> dict:
    """
    Fetches the near-month options chain from yfinance.
    This is the ONLY function called externally from this file.

    See module docstring for full output contract.
    Returns dict with data_quality="failed" on any error.
    """
    print(f"  Fetching options data for {ticker_symbol}...")

    try:
        time.sleep(1)
        stock    = yf.Ticker(ticker_symbol)
        expiries = stock.options

        if not expiries:
            return {"data_quality": "failed"}

        now = datetime.now(timezone.utc)

        # Find nearest expiry in the MIN_DTE to MAX_DTE window
        selected = None
        dte_val  = None
        for exp in expiries:
            exp_dt = pd.Timestamp(exp, tz="UTC")
            dte    = (exp_dt - now).days
            if MIN_DTE <= dte <= MAX_DTE:
                selected = exp
                dte_val  = dte
                break

        # Fallback: nearest expiry regardless of window
        if not selected and expiries:
            selected = expiries[0]
            dte_val  = max(1, (pd.Timestamp(selected, tz="UTC") - now).days)

        if not selected:
            return {"data_quality": "failed"}

        chain     = stock.option_chain(selected)
        calls_all = chain.calls.copy()
        puts_all  = chain.puts.copy()

        # Volume-filtered chains for PCR scoring
        calls = calls_all[calls_all["volume"].fillna(0) > 0]
        puts  = puts_all[puts_all["volume"].fillna(0) > 0]

        # Average IV from volume-filtered chains
        avg_iv_calls = float(calls["impliedVolatility"].mean()) if not calls.empty else 0.0
        avg_iv_puts  = float(puts["impliedVolatility"].mean())  if not puts.empty else 0.0
        avg_iv       = round((avg_iv_calls + avg_iv_puts) / 2, 4)

        # Current price for Max Pain / Wall distance calculations
        info          = stock.info
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("previousClose")
        )

        # Data quality check
        total_volume = (
            calls["volume"].fillna(0).sum() +
            puts["volume"].fillna(0).sum()
        )
        if total_volume < MIN_VOLUME:
            data_quality = "partial"   # illiquid options
        else:
            data_quality = "full"

        return {
            "calls":         calls,
            "puts":          puts,
            "calls_all":     calls_all,
            "puts_all":      puts_all,
            "expiry":        selected,
            "days_to_exp":   dte_val,
            "avg_iv":        avg_iv,
            "current_price": float(current_price) if current_price else None,
            "data_quality":  data_quality,
        }

    except Exception as e:
        print(f"  Options chain fetch error: {e}")
        return {"data_quality": "failed"}
