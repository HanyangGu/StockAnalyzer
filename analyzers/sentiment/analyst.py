# ============================================================
# analyzers/sentiment/analyst.py -- Analyst Ratings Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches analyst ratings data from Yahoo Finance and returns
# a standardised dict for analyst_scorer.py to process.
#
# Data sources (yfinance):
#   ticker.upgrades_downgrades    -- historical rating records
#   ticker.recommendations_summary -- current distribution counts
#   ticker.analyst_price_targets  -- mean/high/low/median targets
#   ticker.info                   -- current price
#
# Data strategy:
#   Primary window : last 6 months
#   Fallback       : extend to 12 months if < MIN_RATINGS found
#   Minimum        : if still < MIN_RATINGS, mark data_quality = "insufficient"
#
# Output contract (standardised -- data source independent):
# {
#   "ratings": list[dict]   normalised rating records, each:
#              {
#                "date":   pd.Timestamp (UTC),
#                "firm":   str,
#                "grade":  str,          e.g. "Buy", "Hold", "Sell"
#                "action": str,          "up" | "down" | "init" | "main" | ""
#              }
#   "summary": dict         current distribution counts:
#              {
#                "strong_buy":  int,
#                "buy":         int,
#                "hold":        int,
#                "sell":        int,
#                "strong_sell": int,
#              }
#   "targets": dict         analyst price targets:
#              {
#                "mean":   float | None,
#                "high":   float | None,
#                "low":    float | None,
#                "median": float | None,
#              }
#   "current_price": float | None
#   "data_quality":  str    "full" | "partial" | "insufficient" | "failed"
# }
#
# Future data source migration:
#   Replace only this file. analyst_scorer.py receives the same
#   standardised dict regardless of the underlying data source.
# ============================================================

import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf


# ============================================================
# Constants
# ============================================================

PRIMARY_MONTHS  = 6
FALLBACK_MONTHS = 12
MIN_RATINGS     = 3


# ============================================================
# Internal helpers
# ============================================================

def _fetch_ratings(ticker_symbol: str) -> pd.DataFrame:
    """
    Fetches historical upgrade/downgrade records from yfinance.
    Returns normalised DataFrame with columns:
      date (UTC Timestamp index), firm, grade, action
    or empty DataFrame on failure.
    """
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_symbol)

        # yfinance 1.x: historical records in upgrades_downgrades
        raw = getattr(stock, "upgrades_downgrades", None)
        if raw is None or (hasattr(raw, "empty") and raw.empty):
            raw = getattr(stock, "recommendations", None)

        if raw is None or (hasattr(raw, "empty") and raw.empty):
            return pd.DataFrame()

        # Normalise index to UTC datetime
        raw.index  = pd.to_datetime(raw.index, utc=True)
        raw        = raw.sort_index(ascending=False)
        raw.columns = [c.strip().replace(" ", "") for c in raw.columns]

        # Map to standard column names regardless of yfinance version
        col_map = {
            "Firm":      "firm",
            "firm":      "firm",
            "ToGrade":   "grade",
            "To Grade":  "grade",
            "toGrade":   "grade",
            "Grade":     "grade",
            "Action":    "action",
            "action":    "action",
        }
        raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})

        # Ensure required columns exist
        for col in ("firm", "grade", "action"):
            if col not in raw.columns:
                raw[col] = ""

        raw["firm"]   = raw["firm"].fillna("").astype(str)
        raw["grade"]  = raw["grade"].fillna("").astype(str)
        raw["action"] = raw["action"].fillna("").str.lower()

        # Apply time window
        cutoff  = datetime.now(timezone.utc) - timedelta(days=PRIMARY_MONTHS * 30)
        primary = raw[raw.index >= cutoff]
        if len(primary) >= MIN_RATINGS:
            return primary[["firm", "grade", "action"]]

        # Fallback
        cutoff = datetime.now(timezone.utc) - timedelta(days=FALLBACK_MONTHS * 30)
        return raw[raw.index >= cutoff][["firm", "grade", "action"]]

    except Exception as e:
        print(f"  Analyst ratings fetch error: {e}")
        return pd.DataFrame()


def _fetch_summary(ticker_symbol: str) -> dict:
    """
    Fetches current rating distribution from recommendations_summary.
    Returns standardised dict with int counts per category.
    """
    try:
        time.sleep(0.5)
        summary = yf.Ticker(ticker_symbol).recommendations_summary
        if summary is None or summary.empty:
            return {}
        row = summary.iloc[0]
        return {
            "strong_buy":  int(row.get("strongBuy",  0)),
            "buy":         int(row.get("buy",         0)),
            "hold":        int(row.get("hold",        0)),
            "sell":        int(row.get("sell",        0)),
            "strong_sell": int(row.get("strongSell",  0)),
        }
    except Exception as e:
        print(f"  Analyst summary fetch error: {e}")
        return {}


def _fetch_targets(ticker_symbol: str) -> dict:
    """
    Fetches analyst price targets.
    Returns standardised dict with float | None values.
    """
    try:
        time.sleep(0.5)
        raw = yf.Ticker(ticker_symbol).analyst_price_targets
        if raw is None:
            return {}
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        return {
            "mean":   raw.get("mean"),
            "high":   raw.get("high"),
            "low":    raw.get("low"),
            "median": raw.get("median"),
        }
    except Exception as e:
        print(f"  Analyst targets fetch error: {e}")
        return {}


def _fetch_current_price(ticker_symbol: str) -> float | None:
    """Fetches current stock price for upside calculation."""
    try:
        info = yf.Ticker(ticker_symbol).info
        return info.get("currentPrice") or info.get("regularMarketPrice")
    except Exception:
        return None


# ============================================================
# Main fetch function
# ============================================================

def fetch_analyst_data(ticker_symbol: str) -> dict:
    """
    Fetches all analyst data and returns a standardised dict.
    This is the ONLY function called externally from this file.

    See module docstring for full output contract.
    """
    print(f"  Fetching analyst data for {ticker_symbol}...")

    ratings       = _fetch_ratings(ticker_symbol)
    summary       = _fetch_summary(ticker_symbol)
    targets       = _fetch_targets(ticker_symbol)
    current_price = _fetch_current_price(ticker_symbol)

    rating_count = len(ratings)

    # Determine data quality
    if rating_count == 0 and not summary:
        data_quality = "failed"
    elif rating_count < MIN_RATINGS and not summary:
        data_quality = "insufficient"
    elif rating_count < MIN_RATINGS or not targets:
        data_quality = "partial"
    else:
        data_quality = "full"

    # Serialise ratings to list of dicts for JSON compatibility
    ratings_list = []
    if not ratings.empty:
        for date, row in ratings.iterrows():
            ratings_list.append({
                "date":   date.isoformat(),   # str, ISO format
                "firm":   row["firm"],
                "grade":  row["grade"],
                "action": row["action"],
            })

    return {
        "ratings":       ratings_list,
        "summary":       summary,
        "targets":       targets,
        "current_price": current_price,
        "data_quality":  data_quality,
    }
