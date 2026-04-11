# ============================================================
# analyzers/sentiment/insider.py -- Insider Trading Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches insider transaction data from Yahoo Finance and returns
# a standardised dict for insider_scorer.py to process.
#
# Data source (yfinance):
#   ticker.insider_transactions
#   Confirmed columns (yfinance 1.2.x):
#     Shares, Value, URL, Text, Insider, Position,
#     Transaction, Start Date, Ownership
#   ticker.info  →  sharesOutstanding (for ownership % estimate)
#
# Data strategy:
#   Primary window : last 6 months
#   Fallback       : extend to 12 months if < MIN_TRANSACTIONS
#   Skipped types  : gifts, awards, grants, exercise-and-sell
#
# Output contract (standardised -- data source independent):
# {
#   "transactions": list[dict]  parsed and classified transactions, each:
#     {
#       "insider":          str,
#       "title":            str,
#       "position_key":     str,   "ceo"|"cfo"|"coo"|"president"|...
#       "position_weight":  float, from INSIDER_POSITION_WEIGHTS
#       "transaction_type": str,   raw transaction string
#       "shares":           int,
#       "value":            float, USD
#       "date_str":         str,   "YYYY-MM-DD"
#       "date_ts":          pd.Timestamp (UTC),
#       "time_weight":      float, from INSIDER_TIME_DECAY
#       "is_buy":           bool,
#       "is_sell":          bool,
#       "ownership_pct":    float | None,
#       "text_snippet":     str,
#     }
#   "shares_outstanding": int    0 if unavailable
#   "data_quality":       str    "full" | "partial" | "insufficient" | "failed"
# }
#
# Future data source migration:
#   Replace only this file. insider_scorer.py receives the same
#   standardised dict regardless of the underlying data source.
# ============================================================

import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

from core.weights import (
    INSIDER_POSITION_WEIGHTS,
    INSIDER_TIME_DECAY, INSIDER_TIME_DECAY_DEFAULT,
)


# ============================================================
# Constants
# ============================================================

PRIMARY_MONTHS   = 6
FALLBACK_MONTHS  = 12
MIN_TRANSACTIONS = 3

TIME_DECAY        = INSIDER_TIME_DECAY
TIME_DECAY_DEFAULT = INSIDER_TIME_DECAY_DEFAULT
POSITION_WEIGHTS  = INSIDER_POSITION_WEIGHTS

PURCHASE_KEYWORDS = ["purchase", "buy", "bought", "acquisition"]
SALE_KEYWORDS     = ["sale", "sell", "sold", "disposed"]


# ============================================================
# Internal helpers
# ============================================================

def _time_weight(date_val) -> float:
    """Calculates time decay weight for a transaction by age in months."""
    try:
        now = datetime.now(timezone.utc)
        ts  = pd.Timestamp(date_val)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        age_months = (now - ts.to_pydatetime()).days / 30.0
        for max_months, weight in TIME_DECAY:
            if age_months <= max_months:
                return round(weight, 2)
        return TIME_DECAY_DEFAULT
    except Exception:
        return TIME_DECAY_DEFAULT


def _classify_position(title: str) -> tuple:
    """Classifies insider position → (position_key, weight)."""
    if not title:
        return "other", POSITION_WEIGHTS["other"]
    t = title.lower()
    if "chief executive" in t or t.strip().startswith("ceo"):
        return "ceo",       POSITION_WEIGHTS["ceo"]
    elif "chief financial" in t or t.strip().startswith("cfo"):
        return "cfo",       POSITION_WEIGHTS["cfo"]
    elif "chief operating" in t or t.strip().startswith("coo"):
        return "coo",       POSITION_WEIGHTS["coo"]
    elif "vice president" in t or " vp" in t:
        return "vp",        POSITION_WEIGHTS["vp"]
    elif "president" in t:
        return "president", POSITION_WEIGHTS["president"]
    elif "chairman" in t or "chair" in t:
        return "chairman",  POSITION_WEIGHTS["chairman"]
    elif "director" in t:
        return "director",  POSITION_WEIGHTS["director"]
    elif "officer" in t or "chief" in t:
        return "officer",   POSITION_WEIGHTS["officer"]
    else:
        return "other",     POSITION_WEIGHTS["other"]


def _classify_transaction(txn_str: str,
                           text_str: str,
                           value: float) -> tuple:
    """
    Determines if a transaction is a purchase, sale, or should be skipped.
    Returns (is_buy, is_sell, should_skip).

    Skip logic:
      - Zero-value gifts
      - Awards and grants (not open-market activity)
      - Exercise-and-sell (not conviction)

    Exercise-and-hold is treated as a weak bullish purchase.
    """
    combined  = (str(txn_str) + " " + str(text_str)).lower()
    txn_lower = str(txn_str).lower()

    if value == 0 and "gift" in combined:
        return False, False, True

    if "exercise" in combined:
        if "sell" in combined or "sale" in combined:
            return False, False, True   # exercise-and-sell → skip
        return True, False, False       # exercise-and-hold → weak bullish

    if any(k in combined for k in ("award", "grant", "gift")):
        return False, False, True

    is_buy  = any(k in combined for k in PURCHASE_KEYWORDS)
    is_sell = any(k in combined for k in SALE_KEYWORDS)

    # Conflict: Transaction column takes priority over Text
    if is_buy and is_sell:
        is_buy  = any(k in txn_lower for k in PURCHASE_KEYWORDS)
        is_sell = not is_buy

    return is_buy, is_sell, False


def _estimate_ownership_pct(shares: int,
                              shares_outstanding: int) -> float | None:
    """Estimates transaction as % of total shares outstanding."""
    if shares_outstanding <= 0 or shares <= 0:
        return None
    return round((shares / shares_outstanding) * 100, 4)


# ============================================================
# Main fetch function
# ============================================================

def fetch_insider_data(ticker_symbol: str) -> dict:
    """
    Fetches and parses insider transactions from yfinance.
    This is the ONLY function called externally from this file.

    See module docstring for full output contract.
    """
    print(f"  Fetching insider data for {ticker_symbol}...")

    # ── Shares outstanding (for ownership % estimation) ───────
    shares_outstanding = 0
    try:
        info               = yf.Ticker(ticker_symbol).info
        shares_outstanding = int(info.get("sharesOutstanding") or 0)
    except Exception:
        pass

    # ── Raw transaction fetch ─────────────────────────────────
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_symbol)
        raw   = stock.insider_transactions

        if raw is None or raw.empty:
            return {
                "transactions":      [],
                "shares_outstanding": shares_outstanding,
                "data_quality":      "failed",
            }

        # Parse date column
        raw["_date"] = pd.to_datetime(raw["Start Date"], utc=True, errors="coerce")
        raw = raw.dropna(subset=["_date"])
        raw = raw.sort_values("_date", ascending=False).reset_index(drop=True)

        # Apply time window
        cutoff  = datetime.now(timezone.utc) - timedelta(days=PRIMARY_MONTHS * 30)
        primary = raw[raw["_date"] >= cutoff]
        if len(primary) >= MIN_TRANSACTIONS:
            raw = primary.reset_index(drop=True)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=FALLBACK_MONTHS * 30)
            raw    = raw[raw["_date"] >= cutoff].reset_index(drop=True)

    except Exception as e:
        print(f"  Insider fetch error: {e}")
        return {
            "transactions":       [],
            "shares_outstanding": shares_outstanding,
            "data_quality":       "failed",
        }

    # ── Parse each row into standardised transaction dict ─────
    parsed = []
    for _, row in raw.iterrows():
        txn_str  = str(row.get("Transaction", ""))
        text_str = str(row.get("Text",        ""))
        shares   = abs(float(row.get("Shares", 0) or 0))
        value    = abs(float(row.get("Value",  0) or 0))
        date_ts  = row.get("_date")
        insider  = str(row.get("Insider",  "Unknown")).strip().title()
        title    = str(row.get("Position", "")).strip()

        is_buy, is_sell, skip = _classify_transaction(txn_str, text_str, value)
        if skip:
            continue

        pos_key, pos_weight = _classify_position(title)
        t_weight  = _time_weight(date_ts)
        date_str  = date_ts.strftime("%Y-%m-%d") if date_ts is not None else "Unknown"
        ownership = _estimate_ownership_pct(int(shares), shares_outstanding)

        parsed.append({
            "insider":          insider,
            "title":            title,
            "position_key":     pos_key,
            "position_weight":  pos_weight,
            "transaction_type": txn_str if txn_str else ("Purchase" if is_buy else "Sale"),
            "shares":           int(shares),
            "value":            value,
            "date_str":         date_str,
            "date_ts":          date_ts,
            "time_weight":      t_weight,
            "is_buy":           is_buy,
            "is_sell":          is_sell,
            "ownership_pct":    ownership,
            "text_snippet":     text_str[:200],
        })

    # ── Data quality ──────────────────────────────────────────
    if not parsed:
        data_quality = "insufficient"
    elif len(parsed) < MIN_TRANSACTIONS:
        data_quality = "partial"
    else:
        data_quality = "full"

    return {
        "transactions":       parsed,
        "shares_outstanding": shares_outstanding,
        "data_quality":       data_quality,
    }
