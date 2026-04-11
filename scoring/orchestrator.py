# ============================================================
# orchestrator.py -- Master Analysis Orchestrator
# ============================================================
# Coordinates the full analysis pipeline for a single stock:
#   1. Resolve ticker
#   2. Fetch price data (live or historical)
#   3. Fetch historical OHLCV data
#   4. Run all analyzer modules
#   5. Run all scorer modules
#   6. Return complete serializable result
#
# To add a new analysis dimension:
#   1. Add analyzer in analyzers/           (data layer)
#   2. Add scorer in scoring/              (scoring layer)
#   3. Call both here in sequence
#   4. Include result in the return dict
#   5. Update composite.py weights
# ============================================================

import time
import numpy as np
from datetime import datetime

from core.data import (
    fetch_price_data,
    fetch_price_data_historical,
    fetch_historical_data,
    resolve_ticker,
)
from core.weights import MACRO_ENABLED

from analyzers.technical import (
    compute_rsi, compute_stochastic, compute_roc, compute_macd,
    compute_moving_averages, compute_golden_cross,
    compute_bollinger_bands, compute_atr, compute_volume_trend,
)
from analyzers.fundamental import fetch_fundamental_data
from analyzers.macro import fetch_macro_data

# Sentiment: data layer
from analyzers.sentiment.news    import fetch_news_data
from analyzers.sentiment.analyst import fetch_analyst_data
from analyzers.sentiment.insider import fetch_insider_data
from analyzers.sentiment.options import fetch_options_data

from scoring.technical_scorer   import (
    score_short_term, score_mid_term, score_long_term, score_technical_overall,
)
from scoring.fundamental_scorer import score_fundamentals
from scoring.macro_scorer       import score_macro

# Sentiment: scoring layer
from scoring.sentiment.news_scorer    import score_news
from scoring.sentiment.analyst_scorer import score_analyst
from scoring.sentiment.insider_scorer import score_insider
from scoring.sentiment.options_scorer import score_options

from scoring.sentiment_scorer import score_sentiment
from scoring.composite        import get_composite

from analyzers.event_driven import fetch_event_data
from scoring.event_scorer   import score_event


# ============================================================
# Utility
# ============================================================

def make_serializable(obj, _path="root"):
    if isinstance(obj, dict):
        return {k: make_serializable(v, f"{_path}.{k}") for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v, f"{_path}[{i}]") for i, v in enumerate(obj)]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        # Debug: print any non-serializable type
        try:
            import json
            json.dumps(obj)
        except TypeError:
            print(f"  ⚠️ Non-serializable at {_path}: type={type(obj).__name__}, value={repr(obj)[:100]}")
        return obj


# ============================================================
# Master Orchestrator
# ============================================================

def run_analysis(company: str, backtest_date: str = None) -> dict:
    """
    Runs full multi-dimension analysis on a stock.

    Data flow per dimension:
      analyzer (data layer) → scorer (scoring layer) → result dict

    All analyzer outputs are standardised dicts independent of the
    data source. Replacing a data source = replace only the analyzer.
    """
    # ── Step 1: Resolve ticker ────────────────────────────────
    ticker = resolve_ticker(company)
    print(f"  Running analysis for: {ticker}...")

    # ── Step 2: Fetch price data ──────────────────────────────
    if backtest_date:
        price_data = fetch_price_data_historical(ticker, backtest_date)
    else:
        price_data = fetch_price_data(ticker)

    if "error" in price_data:
        if "too many requests" in str(price_data["error"]).lower() or \
           "rate limit"        in str(price_data["error"]).lower():
            return {"error": "Yahoo Finance is temporarily rate limited. Please wait 30 seconds and try again."}
        return {"error": price_data["error"]}

    # ── Step 3: Fetch historical OHLCV ────────────────────────
    time.sleep(1)
    hist_data = fetch_historical_data(ticker, end_date=backtest_date)
    if not hist_data["success"]:
        if "too many requests" in str(hist_data["error"]).lower() or \
           "rate limit"        in str(hist_data["error"]).lower():
            return {"error": "Yahoo Finance is temporarily rate limited. Please wait 30 seconds and try again."}
        return {"error": hist_data["error"]}

    df            = hist_data["df"]
    closes        = hist_data["closes"]
    current_price = price_data["current_price"]

    # ── Step 4: Technical indicators ─────────────────────────
    rsi    = compute_rsi(closes)
    stoch  = compute_stochastic(df)
    roc    = compute_roc(closes)
    macd   = compute_macd(closes)
    mas    = compute_moving_averages(closes, current_price)
    golden = compute_golden_cross(closes)
    bb     = compute_bollinger_bands(closes, current_price)
    atr    = compute_atr(df)
    vol    = compute_volume_trend(df)

    # ── Step 5: Technical scoring ────────────────────────────
    short   = score_short_term(rsi, stoch, roc, bb, mas)
    mid     = score_mid_term(macd, mas, atr, vol)
    long    = score_long_term(mas, golden, vol)
    overall = score_technical_overall(short, mid, long)

    # ── Step 6: Fundamental (data → score) ───────────────────
    fund_data = fetch_fundamental_data(ticker)
    if "error" in fund_data:
        fundamental  = {"score": None, "verdict": "Data unavailable", "icon": "➡️", "signals": []}
        fund_details = {}
        print(f"  Fundamental skipped: {fund_data['error']}")
    else:
        fundamental  = score_fundamentals(fund_data)
        fund_details = {
            "valuation":     {
                "pe_ratio": fund_data["pe_ratio"], "forward_pe": fund_data["forward_pe"],
                "price_to_book": fund_data["price_to_book"], "price_to_sales": fund_data["price_to_sales"],
            },
            "profitability": {
                "gross_margin": fund_data["gross_margin"], "net_margin": fund_data["net_margin"],
                "roe": fund_data["roe"], "roa": fund_data["roa"],
            },
            "growth":        {
                "revenue_growth": fund_data["revenue_growth"], "earnings_growth": fund_data["earnings_growth"],
                "eps": fund_data["eps"], "forward_eps": fund_data["forward_eps"],
            },
            "health":        {
                "debt_to_equity": fund_data["debt_to_equity"], "current_ratio": fund_data["current_ratio"],
                "free_cash_flow": fund_data["free_cash_flow"], "total_revenue": fund_data["total_revenue"],
            },
            "analyst":       {
                "target_price": fund_data["target_price"], "target_high": fund_data["target_high"],
                "target_low": fund_data["target_low"], "recommendation": fund_data["recommendation"],
                "analyst_count": fund_data["analyst_count"], "current_price": fund_data["current_price"],
                "upside_pct": fund_data["upside_pct"],
            },
        }

    # ── Step 7: Sentiment (data → score, per sub-dimension) ──
    # Each sub-dimension: fetch data → score independently
    # score_sentiment() aggregates the four scored sub-dicts

    news_raw     = fetch_news_data(ticker, company_name=price_data.get("name", ""))
    news_scored  = score_news(news_raw, ticker=ticker, company_name=price_data.get("name", ""))

    analyst_raw     = fetch_analyst_data(ticker)
    analyst_scored  = score_analyst(analyst_raw)

    insider_raw     = fetch_insider_data(ticker)
    insider_scored  = score_insider(insider_raw, ticker=ticker)

    options_raw     = fetch_options_data(ticker)
    options_scored  = score_options(options_raw)

    sentiment = score_sentiment(
        news    = news_scored,
        analyst = analyst_scored,
        insider = insider_scored,
        options = options_scored,
    )

    # ── Step 8: Macro (data → score) ─────────────────────────
    # Live-only: historical macro data via yfinance unreliable for backtest
    macro_result = None
    if MACRO_ENABLED and not backtest_date:
        print("  Fetching macro data...")
        raw_macro    = fetch_macro_data()
        macro_result = score_macro(
            macro_data = raw_macro,
            fund_data  = fund_data if "error" not in fund_data else None,
        )
        if not macro_result.get("available"):
            print("  Macro data unavailable -- excluded from composite")
            macro_result = None
    elif backtest_date:
        print("  Macro dimension skipped in backtest mode")

    # ── Step 8b: Event-Driven (data → reliability) ──────────
    # Always run regardless of backtest mode.
    # In backtest mode, date context still applies to the analysis date.
    print("  Fetching event data...")
    event_raw    = fetch_event_data(ticker)
    event_result = score_event(event_raw)

    # ── Step 9: Composite ────────────────────────────────────
    composite = get_composite(
        technical      = overall["score"],
        fundamental    = fundamental["score"],
        sentiment      = sentiment["score"],
        macro          = macro_result["score"] if macro_result else None,
        event          = event_result,
        fund_data      = fund_data if "error" not in fund_data else None,
        sentiment_data = sentiment,
        short_term     = short["score"],
    )

    # ── Step 10: Return ───────────────────────────────────────
    result = {
        "ticker":           ticker,
        "company":          price_data["name"],
        "sector":           fund_data.get("sector") if "error" not in fund_data else None,
        "current_price":    current_price,
        "price_change":     price_data["price_change"],
        "price_change_pct": price_data["price_change_pct"],
        "backtest_date":    backtest_date or "live",

        "short_term":       short,
        "mid_term":         mid,
        "long_term":        long,
        "overall":          overall,

        "indicators": {
            "rsi": rsi, "stoch": stoch, "roc": roc, "macd": macd,
            "mas": mas, "golden": golden, "bb": bb, "atr": atr, "volume": vol,
        },

        "fundamental":  fundamental,
        "fund_details": fund_details,
        "sentiment":    sentiment,
        "macro":        macro_result,
        "event":        event_result,
        "composite":    composite,

        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return make_serializable(result)
