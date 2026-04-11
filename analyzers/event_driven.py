# ============================================================
# analyzers/event_driven.py -- Event-Driven Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches upcoming and recent earnings dates from Yahoo Finance
# and returns a standardised dict for event_scorer.py to process.
#
# Data source (yfinance):
#   yf.Ticker(symbol).calendar       -- next earnings date + estimates
#   yf.Ticker(symbol).earnings_dates -- historical earnings dates
#
# Output contract (standardised -- data source independent):
# {
#   "next_earnings":  dict | None
#     {
#       "date":             str         "YYYY-MM-DD"
#       "days_until":       int
#       "estimate_eps_low": float | None
#       "estimate_eps_high":float | None
#     }
#   "last_earnings":  dict | None
#     {
#       "date":         str         "YYYY-MM-DD"
#       "days_ago":     int
#       "actual_eps":   float | None
#       "estimate_eps": float | None
#       "surprise_pct": float | None
#     }
#   "data_quality":   str   "full" | "partial" | "failed"
# }
#
# All values are guaranteed to be JSON-serializable Python native types.
# No pd.Timestamp, numpy floats, or other non-serializable types in output.
# ============================================================

import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# ============================================================
# Type-safe conversion helpers
# ============================================================

def _to_str_date(val) -> str | None:
    """Converts any date-like value to YYYY-MM-DD string, or None."""
    if val is None:
        return None
    try:
        return pd.Timestamp(val).strftime("%Y-%m-%d")
    except Exception:
        return None


def _to_float(val) -> float | None:
    """Converts any numeric value to Python float, or None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f) else f   # filter NaN
    except Exception:
        return None


def _to_int(val) -> int | None:
    """Converts any numeric value to Python int, or None."""
    if val is None:
        return None
    try:
        return int(val)
    except Exception:
        return None


def _days_from_today(date_str: str) -> int:
    """Returns days from today to a date string (negative = past)."""
    try:
        ts  = pd.Timestamp(date_str)
        ts  = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        now = datetime.now(timezone.utc)
        return int((ts.to_pydatetime() - now).days)
    except Exception:
        return 9999


# ============================================================
# Data fetchers
# ============================================================

def _fetch_next_earnings(ticker_symbol: str) -> dict | None:
    """
    Fetches next earnings date from yfinance calendar.
    All returned values are Python native types (str, int, float, None).
    """
    try:
        time.sleep(0.5)
        cal = yf.Ticker(ticker_symbol).calendar

        if cal is None:
            return None
        if hasattr(cal, "empty") and cal.empty:
            return None

        earnings_date = None
        eps_low       = None
        eps_high      = None

        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            eps_low       = cal.get("EPS Estimate Low")  or cal.get("Earnings Low")
            eps_high      = cal.get("EPS Estimate High") or cal.get("Earnings High")

        elif hasattr(cal, "columns"):
            # DataFrame format -- try to extract row values
            try:
                cal_dict = {}
                for col in cal.columns:
                    cal_dict[col] = cal[col].iloc[0] if not cal[col].empty else None
                earnings_date = cal_dict.get("Earnings Date")
                eps_low       = cal_dict.get("EPS Estimate Low")  or cal_dict.get("Earnings Low")
                eps_high      = cal_dict.get("EPS Estimate High") or cal_dict.get("Earnings High")
            except Exception:
                pass

        elif hasattr(cal, "to_dict"):
            d             = cal.to_dict()
            earnings_date = d.get("Earnings Date") or d.get("Value", {}).get("Earnings Date")
            eps_low       = d.get("EPS Estimate Low")  or d.get("Value", {}).get("Earnings Low")
            eps_high      = d.get("EPS Estimate High") or d.get("Value", {}).get("Earnings High")

        # earnings_date may be a list/tuple of dates (date range)
        if isinstance(earnings_date, (list, tuple)):
            earnings_date = earnings_date[0] if len(earnings_date) > 0 else None

        if earnings_date is None:
            return None

        date_str = _to_str_date(earnings_date)
        if not date_str:
            return None

        days_until = _days_from_today(date_str)

        return {
            "date":              date_str,                  # str
            "days_until":        int(days_until),           # int
            "estimate_eps_low":  _to_float(eps_low),        # float | None
            "estimate_eps_high": _to_float(eps_high),       # float | None
        }

    except Exception as e:
        print(f"  Next earnings fetch error: {e}")
        return None


def _fetch_last_earnings(ticker_symbol: str) -> dict | None:
    """
    Fetches the most recent past earnings from yfinance earnings_dates.
    All returned values are Python native types (str, int, float, None).
    """
    try:
        time.sleep(0.5)
        dates = yf.Ticker(ticker_symbol).earnings_dates

        if dates is None:
            return None
        if hasattr(dates, "empty") and dates.empty:
            return None

        # Normalise index timezone
        now = datetime.now(timezone.utc)
        try:
            if dates.index.tz is not None:
                cutoff = pd.Timestamp(now).tz_convert(dates.index.tz)
            else:
                cutoff = pd.Timestamp(now).tz_localize(None)
            past = dates[dates.index < cutoff]
        except Exception:
            past = dates

        if past.empty:
            return None

        row = past.iloc[0]

        # Convert index (Timestamp) to string immediately
        date_str = _to_str_date(row.name)
        if not date_str:
            return None

        days_ago = abs(_days_from_today(date_str))

        # Find EPS columns (vary by yfinance version)
        actual_col   = next(
            (c for c in ["Reported EPS", "EPS Actual", "actual"] if c in past.columns),
            None
        )
        estimate_col = next(
            (c for c in ["EPS Estimate", "estimate"] if c in past.columns),
            None
        )

        actual_eps   = _to_float(row[actual_col])   if actual_col   else None
        estimate_eps = _to_float(row[estimate_col]) if estimate_col else None

        # Surprise %
        surprise_pct = None
        if actual_eps is not None and estimate_eps is not None and estimate_eps != 0:
            surprise_pct = round(
                (actual_eps - estimate_eps) / abs(estimate_eps) * 100, 2
            )

        return {
            "date":         date_str,                   # str
            "days_ago":     int(days_ago),              # int
            "actual_eps":   actual_eps,                 # float | None
            "estimate_eps": estimate_eps,               # float | None
            "surprise_pct": surprise_pct,               # float | None
        }

    except Exception as e:
        print(f"  Last earnings fetch error: {e}")
        return None


# ============================================================
# Main fetch function
# ============================================================

def fetch_event_data(ticker_symbol: str) -> dict:
    """
    Fetches earnings event data and returns a standardised dict.
    This is the ONLY function called externally from this file.
    All values in the returned dict are JSON-serializable.
    """
    print(f"  Fetching event data for {ticker_symbol}...")

    next_earnings = _fetch_next_earnings(ticker_symbol)
    last_earnings = _fetch_last_earnings(ticker_symbol)

    if next_earnings is None and last_earnings is None:
        data_quality = "failed"
    elif next_earnings is None or last_earnings is None:
        data_quality = "partial"
    else:
        data_quality = "full"

    return {
        "next_earnings": next_earnings,
        "last_earnings": last_earnings,
        "data_quality":  data_quality,
    }
