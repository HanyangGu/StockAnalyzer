# ============================================================
# analyzers/sentiment/analyst.py -- Analyst Ratings Data Fetcher
# ============================================================
# v0.6: reads from RawDataBundle instead of calling yfinance.
# Output contract unchanged — analyst_scorer.py unaffected.
# ============================================================

from datetime import datetime, timezone, timedelta
import pandas as pd

PRIMARY_MONTHS  = 6
FALLBACK_MONTHS = 12
MIN_RATINGS     = 3


def _parse_ratings(raw, current_price) -> list:
    """Parse upgrades_downgrades DataFrame into standardised rating list."""
    if raw is None or (hasattr(raw, "empty") and raw.empty):
        return []
    try:
        raw = raw.copy()
        raw.index  = pd.to_datetime(raw.index, utc=True)
        raw        = raw.sort_index(ascending=False)
        raw.columns = [c.strip().replace(" ", "") for c in raw.columns]

        col_map = {
            "Firm": "firm", "firm": "firm",
            "ToGrade": "grade", "To Grade": "grade", "toGrade": "grade", "Grade": "grade",
            "Action": "action", "action": "action",
        }
        raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})
        for col in ("firm", "grade", "action"):
            if col not in raw.columns:
                raw[col] = ""
        raw["firm"]   = raw["firm"].fillna("").astype(str)
        raw["grade"]  = raw["grade"].fillna("").astype(str)
        raw["action"] = raw["action"].fillna("").str.lower()

        cutoff  = datetime.now(timezone.utc) - timedelta(days=PRIMARY_MONTHS * 30)
        primary = raw[raw.index >= cutoff]
        if len(primary) >= MIN_RATINGS:
            df = primary[["firm", "grade", "action"]]
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=FALLBACK_MONTHS * 30)
            df = raw[raw.index >= cutoff][["firm", "grade", "action"]]

        ratings_list = []
        for date, row in df.iterrows():
            ratings_list.append({
                "date":   date.isoformat(),
                "firm":   row["firm"],
                "grade":  row["grade"],
                "action": row["action"],
            })
        return ratings_list
    except Exception as e:
        print(f"  Analyst ratings parse error: {e}")
        return []


def _parse_summary(raw_summary) -> dict:
    """Parse recommendations_summary DataFrame."""
    try:
        if raw_summary is None or (hasattr(raw_summary, "empty") and raw_summary.empty):
            return {}
        row = raw_summary.iloc[0]
        return {
            "strong_buy":  int(row.get("strongBuy",  0)),
            "buy":         int(row.get("buy",         0)),
            "hold":        int(row.get("hold",        0)),
            "sell":        int(row.get("sell",        0)),
            "strong_sell": int(row.get("strongSell",  0)),
        }
    except Exception as e:
        print(f"  Analyst summary parse error: {e}")
        return {}


def _parse_targets(raw_targets) -> dict:
    """Parse analyst price targets dict."""
    try:
        if raw_targets is None:
            return {}
        if hasattr(raw_targets, "to_dict"):
            raw_targets = raw_targets.to_dict()
        return {
            "mean":   raw_targets.get("mean"),
            "high":   raw_targets.get("high"),
            "low":    raw_targets.get("low"),
            "median": raw_targets.get("median"),
        }
    except Exception as e:
        print(f"  Analyst targets parse error: {e}")
        return {}


def fetch_analyst_data(ticker_symbol: str,
                        bundle: dict = None) -> dict:
    """
    Extracts analyst data from pre-fetched RawDataBundle.
    Falls back to direct yfinance if bundle not provided.
    """
    print(f"  Parsing analyst data for {ticker_symbol}...")

    if bundle is not None:
        info         = bundle.get("info", {})
        raw_ratings  = bundle.get("upgrades_downgrades")
        raw_summary  = bundle.get("recommendations_summary")
        raw_targets  = bundle.get("analyst_price_targets")
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice")
        )
    else:
        # Legacy fallback
        import time, yfinance as yf
        stock = yf.Ticker(ticker_symbol)
        time.sleep(1)
        raw_ratings   = getattr(stock, "upgrades_downgrades", None) or getattr(stock, "recommendations", None)
        time.sleep(0.5)
        raw_summary   = stock.recommendations_summary
        time.sleep(0.5)
        raw_targets_raw = stock.analyst_price_targets
        raw_targets   = raw_targets_raw.to_dict() if hasattr(raw_targets_raw, "to_dict") else raw_targets_raw
        time.sleep(0.5)
        info          = stock.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    ratings  = _parse_ratings(raw_ratings, current_price)
    summary  = _parse_summary(raw_summary)
    targets  = _parse_targets(raw_targets)

    rating_count = len(ratings)
    if rating_count == 0 and not summary:
        data_quality = "failed"
    elif rating_count < MIN_RATINGS and not summary:
        data_quality = "insufficient"
    elif rating_count < MIN_RATINGS or not targets:
        data_quality = "partial"
    else:
        data_quality = "full"

    return {
        "ratings":       ratings,
        "summary":       summary,
        "targets":       targets,
        "current_price": float(current_price) if current_price else None,
        "data_quality":  data_quality,
    }
