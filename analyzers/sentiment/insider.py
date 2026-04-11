# ============================================================
# analyzers/sentiment/insider.py -- Insider Trading Data Fetcher
# ============================================================
# v0.6: reads from RawDataBundle instead of calling yfinance.
# Output contract unchanged — insider_scorer.py unaffected.
# ============================================================

from datetime import datetime, timezone, timedelta
import pandas as pd

from core.weights import (
    INSIDER_POSITION_WEIGHTS,
    INSIDER_TIME_DECAY, INSIDER_TIME_DECAY_DEFAULT,
)

PRIMARY_MONTHS    = 6
FALLBACK_MONTHS   = 12
MIN_TRANSACTIONS  = 3

# ── Transaction filtering for GPT analysis ────────────────────
# High-signal positions: always included regardless of value
HIGH_SIGNAL_POSITIONS = {"ceo", "cfo", "coo", "president", "chairman", "director"}
# Lower-level positions: only include if value exceeds threshold
MIN_VALUE_LOWER_POSITIONS = 50_000   # USD
# Maximum transactions sent to GPT scorer
MAX_GPT_TRANSACTIONS = 20

TIME_DECAY         = INSIDER_TIME_DECAY
TIME_DECAY_DEFAULT = INSIDER_TIME_DECAY_DEFAULT
POSITION_WEIGHTS   = INSIDER_POSITION_WEIGHTS

PURCHASE_KEYWORDS = ["purchase", "buy", "bought", "acquisition"]
SALE_KEYWORDS     = ["sale", "sell", "sold", "disposed"]


def _time_weight(date_val) -> float:
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


def _classify_transaction(txn_str, text_str, value) -> tuple:
    combined  = (str(txn_str) + " " + str(text_str)).lower()
    txn_lower = str(txn_str).lower()
    if value == 0 and "gift" in combined:
        return False, False, True
    if "exercise" in combined:
        if "sell" in combined or "sale" in combined:
            return False, False, True
        return True, False, False
    if any(k in combined for k in ("award", "grant", "gift")):
        return False, False, True
    is_buy  = any(k in combined for k in PURCHASE_KEYWORDS)
    is_sell = any(k in combined for k in SALE_KEYWORDS)
    if is_buy and is_sell:
        is_buy  = any(k in txn_lower for k in PURCHASE_KEYWORDS)
        is_sell = not is_buy
    return is_buy, is_sell, False


def _estimate_ownership_pct(shares, shares_outstanding):
    if shares_outstanding <= 0 or shares <= 0:
        return None
    return round((shares / shares_outstanding) * 100, 4)


def fetch_insider_data(ticker_symbol: str,
                        bundle: dict = None) -> dict:
    """
    Extracts insider transaction data from pre-fetched RawDataBundle.
    Falls back to direct yfinance if bundle not provided.
    """
    print(f"  Parsing insider data for {ticker_symbol}...")

    if bundle is not None:
        info               = bundle.get("info", {})
        shares_outstanding = int(info.get("sharesOutstanding") or 0)
        raw                = bundle.get("insider_transactions")
    else:
        import time, yfinance as yf
        shares_outstanding = 0
        try:
            info               = yf.Ticker(ticker_symbol).info
            shares_outstanding = int(info.get("sharesOutstanding") or 0)
        except Exception:
            pass
        try:
            time.sleep(1)
            raw = yf.Ticker(ticker_symbol).insider_transactions
        except Exception:
            raw = None

    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return {
            "transactions":       [],
            "shares_outstanding": shares_outstanding,
            "data_quality":       "failed",
        }

    try:
        raw = raw.copy()
        raw["_date"] = pd.to_datetime(raw["Start Date"], utc=True, errors="coerce")
        raw = raw.dropna(subset=["_date"])
        raw = raw.sort_values("_date", ascending=False).reset_index(drop=True)

        cutoff  = datetime.now(timezone.utc) - timedelta(days=PRIMARY_MONTHS * 30)
        primary = raw[raw["_date"] >= cutoff]
        if len(primary) >= MIN_TRANSACTIONS:
            raw = primary.reset_index(drop=True)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=FALLBACK_MONTHS * 30)
            raw    = raw[raw["_date"] >= cutoff].reset_index(drop=True)
    except Exception as e:
        print(f"  Insider parse error: {e}")
        return {
            "transactions":       [],
            "shares_outstanding": shares_outstanding,
            "data_quality":       "failed",
        }

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

    if not parsed:
        data_quality = "insufficient"
    elif len(parsed) < MIN_TRANSACTIONS:
        data_quality = "partial"
    else:
        data_quality = "full"

    # ── Filter for GPT analysis ───────────────────────────────
    # High-signal: senior executives regardless of amount
    # Low-signal: junior positions only if value > threshold
    # Rationale: a VP selling 200 shares (1k) has near-zero signal value,
    # but a CEO buying any amount is always meaningful.
    # GPT receives filtered list only; UI shows all transactions.
    gpt_transactions = [
        t for t in parsed
        if t["position_key"] in HIGH_SIGNAL_POSITIONS
        or t["value"] >= MIN_VALUE_LOWER_POSITIONS
    ]
    # Sort by date descending, cap at MAX_GPT_TRANSACTIONS
    gpt_transactions = sorted(
        gpt_transactions,
        key=lambda t: t["date_str"],
        reverse=True,
    )[:MAX_GPT_TRANSACTIONS]

    n_filtered = len(parsed) - len(gpt_transactions)
    if n_filtered > 0:
        print(f"  Insider: {len(parsed)} total → {len(gpt_transactions)} sent to GPT ({n_filtered} low-signal filtered)")

    return {
        "transactions":       gpt_transactions,   # GPT-analysed (high-signal)
        "all_transactions":   parsed,              # full list for UI display
        "shares_outstanding": shares_outstanding,
        "data_quality":       data_quality,
    }
