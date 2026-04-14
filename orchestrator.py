# ============================================================
# orchestrator.py -- Master Analysis Orchestrator
# ============================================================
# v0.6: DataBundle architecture.
#
# All yfinance data is fetched ONCE at the top via fetch_raw_bundle().
# Analyzers receive the bundle and extract their data from it.
# HTTP requests reduced from ~18-20 to ~8 per analysis.
#
# Data flow:
#   1. resolve_ticker()
#   2. fetch_raw_bundle()      ← single pass, all endpoints
#   3. build_price_data()      ← extracted from bundle.info
#   4. All analyzers receive bundle → extract their slice
#   5. All scorers run on extracted data (unchanged)
#   6. Composite + return
# ============================================================

import time
import numpy as np
from datetime import datetime

from core.data import (
    fetch_raw_bundle,
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
from analyzers.fundamental  import fetch_fundamental_data
from analyzers.macro        import fetch_macro_data
from analyzers.sentiment.news    import fetch_news_data
from analyzers.sentiment.analyst import fetch_analyst_data
from analyzers.sentiment.insider import fetch_insider_data
from analyzers.sentiment.options import fetch_options_data
from analyzers.event_driven      import fetch_event_data

from scoring.technical_scorer   import (
    score_short_term, score_mid_term, score_long_term, score_technical_overall,
)
from scoring.fundamental_scorer  import score_fundamentals
from scoring.macro_scorer        import score_macro
from scoring.sentiment.news_scorer    import score_news
from scoring.sentiment.analyst_scorer import score_analyst
from scoring.sentiment.insider_scorer import score_insider
from scoring.sentiment.options_scorer import score_options
from scoring.sentiment_scorer    import score_sentiment
from scoring.composite           import get_composite
from scoring.event_scorer        import score_event


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
        try:
            import json
            json.dumps(obj)
        except TypeError:
            print(f"  ⚠️ Non-serializable at {_path}: type={type(obj).__name__}, value={repr(obj)[:100]}")
        return obj


def _build_price_data(ticker: str, bundle: dict,
                      backtest_date: str = None) -> dict:
    """
    Constructs the price_data dict from bundle.info.
    Mirrors the output contract of fetch_price_data().
    """
    info    = bundle.get("info", {})
    history = bundle.get("history")

    current_price = (
        info.get("currentPrice") or
        info.get("regularMarketPrice")
    )

    # Backtest: override current_price with historical close
    if backtest_date and history is not None and not history.empty:
        current_price = round(float(history["Close"].iloc[-1]), 2)
        prev_price    = round(float(history["Close"].iloc[-2]), 2) if len(history) > 1 else current_price
    else:
        prev_price = info.get("previousClose", 0) or 0

    if not current_price:
        return {"error": f"Could not retrieve price data for '{ticker}'."}

    current_price    = round(float(current_price), 2)
    price_change     = round(current_price - float(prev_price), 2)
    price_change_pct = round(
        (price_change / float(prev_price) * 100) if prev_price else 0, 2
    )

    # Recent closes from intraday (live) or history (backtest)
    intraday = bundle.get("intraday")
    if intraday is not None and not intraday.empty:
        recent_closes = intraday["Close"].tail(5).round(2).tolist()
    elif history is not None and not history.empty:
        recent_closes = history["Close"].tail(5).round(2).tolist()
    else:
        recent_closes = []

    return {
        "ticker":            ticker,
        "name":              info.get("longName", ticker),
        "exchange":          info.get("exchange"),
        "sector":            info.get("sector"),
        "industry":          info.get("industry"),
        "currency":          info.get("currency", "USD"),
        "current_price":     current_price,
        "prev_close":        round(float(prev_price), 2),
        "price_change":      price_change,
        "price_change_pct":  price_change_pct,
        "open":              info.get("open"),
        "day_high":          info.get("dayHigh"),
        "day_low":           info.get("dayLow"),
        "recent_closes":     recent_closes,
        "volume":            info.get("volume"),
        "avg_volume":        info.get("averageVolume"),
        "market_cap":        info.get("marketCap"),
        "pe_ratio":          info.get("trailingPE"),
        "52w_high":          info.get("fiftyTwoWeekHigh"),
        "52w_low":           info.get("fiftyTwoWeekLow"),
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# Master Orchestrator
# ============================================================

def run_analysis(company: str, backtest_date: str = None) -> dict:
    """
    Runs full multi-dimension analysis on a stock.

    v0.6 change: all yfinance data is fetched once via
    fetch_raw_bundle() and passed to each analyzer.
    """
    # ── Step 1: Resolve ticker ────────────────────────────────
    ticker = resolve_ticker(company)
    print(f"\n  ▶ run_analysis({ticker}) backtest={backtest_date or 'live'}")

    # ── Step 2: Fetch ALL data in one bundle ──────────────────
    bundle = fetch_raw_bundle(ticker, end_date=backtest_date)

    if bundle.get("data_quality") == "failed" or bundle.get("history") is None:
        err = bundle.get("fetch_errors", {}).get("history", "No data available")
        err_str = str(err).lower()
        if "too many requests" in err_str or "rate limit" in err_str or "429" in err_str:
            return {"error": "Yahoo Finance is temporarily rate limited. Please wait 30-60 seconds and try again."}
        if "empty" in err_str or "no data" in err_str:
            return {"error": (
                f"Yahoo Finance returned no price data for {ticker}. "
                f"The market may be closed, the ticker may be invalid, "
                f"or Yahoo Finance is temporarily unavailable. Please try again in a moment."
            )}
        return {"error": f"Could not fetch data for {ticker}: {err}"}

    # ── Step 3: Build price data from bundle ──────────────────
    price_data = _build_price_data(ticker, bundle, backtest_date)
    if "error" in price_data:
        return {"error": price_data["error"]}

    # ── Step 4: Technical indicators (from bundle.history) ────
    history = bundle["history"]
    df      = history
    closes  = history["Close"]
    current_price = price_data["current_price"]

    rsi    = compute_rsi(closes)
    stoch  = compute_stochastic(df)
    roc    = compute_roc(closes)
    macd   = compute_macd(closes)
    mas    = compute_moving_averages(closes, current_price)
    golden = compute_golden_cross(closes)
    bb     = compute_bollinger_bands(closes, current_price)
    atr    = compute_atr(df)
    vol    = compute_volume_trend(df)

    # ── Step 5: Technical scoring ─────────────────────────────
    short   = score_short_term(rsi, stoch, roc, bb, mas)
    mid     = score_mid_term(macd, mas, atr, vol)
    long    = score_long_term(mas, golden, vol)
    overall = score_technical_overall(short, mid, long)

    # ── Step 6: Fundamental ───────────────────────────────────
    fund_data = fetch_fundamental_data(ticker, bundle=bundle)
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

    # ── Step 7: Sentiment (all from bundle) ───────────────────
    company_name = price_data.get("name", "")

    news_raw     = fetch_news_data(ticker, company_name=company_name, bundle=bundle)
    news_scored  = score_news(news_raw, ticker=ticker, company_name=company_name)

    analyst_raw    = fetch_analyst_data(ticker, bundle=bundle)
    analyst_scored = score_analyst(analyst_raw)

    insider_raw    = fetch_insider_data(ticker, bundle=bundle)
    insider_scored = score_insider(insider_raw, ticker=ticker)

    options_raw    = fetch_options_data(ticker, bundle=bundle)
    options_scored = score_options(options_raw)

    sentiment = score_sentiment(
        news    = news_scored,
        analyst = analyst_scored,
        insider = insider_scored,
        options = options_scored,
    )

    # ── Step 8: Macro (batch yf.download, always separate) ────
    macro_result = None
    if MACRO_ENABLED and not backtest_date:
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

    # ── Step 8b: Event-Driven (from bundle) ───────────────────
    event_raw    = fetch_event_data(ticker, bundle=bundle)
    event_result = score_event(event_raw)

    # ── Step 9: Composite ─────────────────────────────────────
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
        "current_price":    current_price,
        "price_change":     price_data["price_change"],
        "price_change_pct": price_data["price_change_pct"],
        "backtest_date":    backtest_date or "live",
        "sector":           fund_data.get("sector") if "error" not in fund_data else None,

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
