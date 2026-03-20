# ============================================================
# app.py  –  Stock Analysis Chatbot
# Rate-limit fixes applied:
#   Fix A – Exponential backoff retry on 429 errors
#   Fix B – Conversation history trimmed to last 6 messages
#   Fix C – Analysis JSON slimmed before sending to GPT
#   Fix D – Single GPT call per turn (intent parsed in Python)
#   Fix E – max_tokens capped to 600 (enough for summaries)
# ============================================================

# Standard library
import os
import re
import json
import time
import warnings
from datetime import datetime

# Suppress system warnings
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Data
import numpy as np
import pandas as pd
import yfinance as yf

# AI
from openai import OpenAI, RateLimitError

# Front End
import streamlit as st

# ============================================================
# Constants
# ============================================================
GPT_MODEL        = "gpt-4.1-mini"
MAX_STOCKS       = 3
MIN_STOCKS       = 2
DATA_PERIOD      = "1y"
DATA_INTERVAL    = "1d"
MIN_DATA_POINTS  = 30
BASELINE_SCORE   = 50

# RSI
RSI_PERIOD    = 14
RSI_OVERSOLD  = 30
RSI_OVERBOUGHT = 70

# Stochastic
STOCH_PERIOD    = 14
STOCH_OVERSOLD  = 20
STOCH_OVERBOUGHT = 80

# ROC
ROC_PERIOD = 10

# MACD
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# Moving averages
MA_SHORT = 20
MA_MID   = 50
MA_LONG  = 200

# Bollinger Bands
BB_PERIOD = 20
BB_STD    = 2

# ATR
ATR_PERIOD = 14

# Volume
VOLUME_RISING   = 1.1
VOLUME_FALLING  = 0.9
VOLUME_LOOKBACK = 5

# ============================================================
# Fix A – Retry wrapper with exponential backoff
# ============================================================
def call_openai_with_retry(client, **kwargs):
    """
    Wraps client.chat.completions.create() with exponential
    backoff on RateLimitError (HTTP 429).
    Retries up to 4 times: waits 5s, 10s, 20s, 40s.
    """
    delays = [5, 10, 20, 40]
    for attempt, delay in enumerate(delays, 1):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt == len(delays):
                raise          # re-raise on final attempt
            st.warning(
                f"⏳ OpenAI rate limit hit. Retrying in {delay}s "
                f"(attempt {attempt}/{len(delays)})…"
            )
            time.sleep(delay)


# ============================================================
# Fix B – History trimmer
# ============================================================
def trim_history(messages: list, keep_last: int = 6) -> list:
    """
    Keeps only the system message (index 0) plus the most
    recent `keep_last` user/assistant turns.
    This prevents token count from growing unboundedly.
    """
    if len(messages) <= 1:
        return messages
    system = messages[:1]
    tail   = messages[1:][-keep_last:]
    return system + tail


# ============================================================
# Fix C – Slim analysis dict before sending to GPT
# ============================================================
def slim_analysis(result: dict) -> dict:
    """
    Strips the raw indicator data from the analysis result
    before passing it to GPT.  GPT only needs scores, verdicts,
    signals, and top-level price info – not raw OHLCV arrays.
    Reduces prompt tokens by ~40-60%.
    """
    keys_to_keep = {
        "ticker", "company", "current_price",
        "price_change", "price_change_pct",
        "short_term", "mid_term", "long_term", "overall",
    }
    return {k: v for k, v in result.items() if k in keys_to_keep}


def slim_comparison(results: list) -> list:
    return [slim_analysis(r) for r in results]


# ============================================================
# Ticker Resolution
# ============================================================
def resolve_ticker(company: str) -> str:
    candidate = company.upper().strip()

    try:
        info = yf.Ticker(candidate).info
        if info.get("currentPrice") or info.get("regularMarketPrice"):
            return candidate
    except Exception:
        pass

    try:
        results = yf.Search(company, max_results=5).quotes
        if results:
            for r in results:
                if r.get("quoteType") == "EQUITY":
                    return r["symbol"]
            return results[0]["symbol"]
    except Exception:
        pass

    return candidate


def validate_companies(companies: list) -> dict:
    seen, unique = set(), []
    for c in companies:
        cleaned = c.strip().upper()
        if cleaned not in seen:
            seen.add(cleaned)
            unique.append(c.strip())

    if len(unique) < MIN_STOCKS:
        return {"valid": False,
                "error": f"Please provide at least {MIN_STOCKS} stocks."}
    if len(unique) > MAX_STOCKS:
        return {"valid": False,
                "error": (f"Maximum {MAX_STOCKS} stocks at once. "
                          f"You provided {len(unique)}.")}
    return {"valid": True, "tickers": unique}


# ============================================================
# Data Fetchers
# ============================================================
def fetch_price_data(ticker_symbol: str) -> dict:
    try:
        stock = yf.Ticker(ticker_symbol)
        info  = stock.info

        current_price = (info.get("currentPrice") or
                         info.get("regularMarketPrice"))
        if not current_price:
            return {"error": (f"Could not retrieve price for "
                              f"'{ticker_symbol}'.")}

        prev_close   = info.get("previousClose", 0) or 0
        price_change = round(current_price - prev_close, 2)
        price_change_pct = round(
            (price_change / prev_close * 100) if prev_close else 0, 2)

        intraday = stock.history(period="1d", interval="1m")
        recent_closes = (intraday["Close"].tail(5).round(2).tolist()
                         if not intraday.empty else [])

        return {
            "ticker": ticker_symbol,
            "name": info.get("longName", ticker_symbol),
            "exchange": info.get("exchange"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("currency", "USD"),
            "current_price": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "price_change": price_change,
            "price_change_pct": price_change_pct,
            "open": info.get("open"),
            "day_high": info.get("dayHigh"),
            "day_low": info.get("dayLow"),
            "recent_closes": recent_closes,
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_historical_data(ticker_symbol: str) -> dict:
    try:
        stock = yf.Ticker(ticker_symbol)
        df    = stock.history(period=DATA_PERIOD, interval=DATA_INTERVAL)

        if df.empty:
            return {"success": False,
                    "error": f"No historical data for {ticker_symbol}."}
        if len(df) < MIN_DATA_POINTS:
            return {"success": False,
                    "error": f"Insufficient data for {ticker_symbol}."}

        return {"success": True, "df": df,
                "closes": df["Close"], "days": len(df)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# Technical Indicators
# ============================================================
def compute_rsi(closes: pd.Series) -> dict:
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss  = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs    = gain / loss.replace(0, float("inf"))
    rsi   = round(float((100 - (100 / (1 + rs))).iloc[-1]), 2)

    if rsi < RSI_OVERSOLD:        signal, icon = "oversold -- strong buy",    "✅"
    elif rsi < 45:                signal, icon = "mildly oversold -- buy",    "✅"
    elif rsi > RSI_OVERBOUGHT:    signal, icon = "overbought -- caution",     "⚠️"
    elif rsi > 55:                signal, icon = "mildly overbought -- watch","⚠️"
    else:                         signal, icon = "neutral",                   "➡️"
    return {"value": rsi, "signal": signal, "icon": icon}


def compute_stochastic(df: pd.DataFrame) -> dict:
    low_min   = df["Low"].rolling(STOCH_PERIOD).min()
    high_max  = df["High"].rolling(STOCH_PERIOD).max()
    k_range   = high_max - low_min
    k = round(float(
        (((df["Close"] - low_min) / k_range.replace(0, float("inf"))) * 100).iloc[-1]
    ), 2)

    if k < STOCH_OVERSOLD:     signal, icon = "oversold -- strong buy",     "✅"
    elif k < 35:               signal, icon = "mildly oversold -- buy",     "✅"
    elif k > STOCH_OVERBOUGHT: signal, icon = "overbought -- caution",      "⚠️"
    elif k > 65:               signal, icon = "mildly overbought -- watch", "⚠️"
    else:                      signal, icon = "neutral",                    "➡️"
    return {"value": k, "signal": signal, "icon": icon}


def compute_roc(closes: pd.Series) -> dict:
    roc = round(float(
        ((closes.iloc[-1] - closes.iloc[-ROC_PERIOD]) / closes.iloc[-ROC_PERIOD]) * 100
    ), 2)
    if roc > 5:    signal, icon = "strong positive momentum", "✅"
    elif roc > 0:  signal, icon = "mild positive momentum",   "✅"
    elif roc < -5: signal, icon = "strong negative momentum", "⚠️"
    else:          signal, icon = "mild negative momentum",   "⚠️"
    return {"value": roc, "signal": signal, "icon": icon}


def compute_macd(closes: pd.Series) -> dict:
    ema_fast  = closes.ewm(span=MACD_FAST,   adjust=False).mean()
    ema_slow  = closes.ewm(span=MACD_SLOW,   adjust=False).mean()
    macd      = ema_fast - ema_slow
    signal    = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    histogram = macd - signal

    macd_val   = round(float(macd.iloc[-1]),      4)
    signal_val = round(float(signal.iloc[-1]),    4)
    hist_val   = round(float(histogram.iloc[-1]), 4)

    if hist_val > 0 and macd_val > signal_val:   sig, icon = "bullish crossover", "✅"
    elif hist_val < 0 and macd_val < signal_val: sig, icon = "bearish crossover", "⚠️"
    else:                                         sig, icon = "neutral",           "➡️"

    return {"macd": macd_val, "signal": signal_val,
            "histogram": hist_val, "signal_label": sig, "icon": icon}


def compute_moving_averages(closes: pd.Series, current_price: float) -> dict:
    results = {}
    for period, label in [(MA_SHORT,"ma20"),(MA_MID,"ma50"),(MA_LONG,"ma200")]:
        if len(closes) >= period:
            ma_val = round(float(closes.rolling(period).mean().iloc[-1]), 2)
            above  = current_price > ma_val
            results[label] = {
                "value": ma_val, "above": above,
                "signal": "price above -- bullish" if above else "price below -- bearish",
                "icon":   "✅" if above else "⚠️",
            }
        else:
            results[label] = {"value": None, "above": None,
                               "signal": "insufficient data", "icon": "➡️"}
    return results


def compute_golden_cross(closes: pd.Series) -> dict:
    if len(closes) < MA_LONG:
        return {"value": None, "signal": "insufficient data", "icon": "➡️", "golden": None}

    ma50  = closes.rolling(MA_MID).mean()
    ma200 = closes.rolling(MA_LONG).mean()
    ma50_now,  ma200_now  = ma50.iloc[-1],  ma200.iloc[-1]
    ma50_prev, ma200_prev = ma50.iloc[-2],  ma200.iloc[-2]

    golden_cross = (ma50_prev <= ma200_prev) and (ma50_now > ma200_now)
    death_cross  = (ma50_prev >= ma200_prev) and (ma50_now < ma200_now)

    if ma50_now > ma200_now:
        signal, icon = ("fresh golden cross -- strong buy", "✅") if golden_cross \
                  else ("golden cross active -- bullish",   "✅")
    else:
        signal, icon = ("fresh death cross -- strong sell", "⚠️") if death_cross \
                  else ("death cross active -- bearish",    "⚠️")

    return {"value": round(float(ma50_now), 2), "ma200": round(float(ma200_now), 2),
            "signal": signal, "icon": icon, "golden": ma50_now > ma200_now}


def compute_bollinger_bands(closes: pd.Series, current_price: float) -> dict:
    ma    = closes.rolling(BB_PERIOD).mean()
    std   = closes.rolling(BB_PERIOD).std()
    upper = round(float((ma + BB_STD * std).iloc[-1]), 2)
    mid   = round(float(ma.iloc[-1]),                  2)
    lower = round(float((ma - BB_STD * std).iloc[-1]), 2)

    bb_range = upper - lower
    bb_pct   = round(float((current_price - lower) / bb_range * 100)
                     if bb_range > 0 else 50, 2)

    if bb_pct < 20:   signal, icon = "near lower band -- potential bounce",   "✅"
    elif bb_pct > 80: signal, icon = "near upper band -- potential pullback",  "⚠️"
    else:             signal, icon = "mid band -- neutral",                    "➡️"
    return {"upper": upper, "middle": mid, "lower": lower,
            "pct": bb_pct, "signal": signal, "icon": icon}


def compute_atr(df: pd.DataFrame) -> dict:
    high, low, prev_close = df["High"], df["Low"], df["Close"].shift(1)
    tr  = pd.concat([(high - low),
                     (high - prev_close).abs(),
                     (low  - prev_close).abs()], axis=1).max(axis=1)
    atr = round(float(tr.rolling(ATR_PERIOD).mean().iloc[-1]), 4)
    current_price = round(float(df["Close"].iloc[-1]), 2)
    atr_pct = round((atr / current_price) * 100, 2)

    if atr_pct > 3:    signal, icon = "high volatility",     "⚠️"
    elif atr_pct > 1.5:signal, icon = "moderate volatility", "➡️"
    else:              signal, icon = "low volatility",       "✅"
    return {"value": atr, "pct": atr_pct, "signal": signal, "icon": icon}


def compute_volume_trend(df: pd.DataFrame) -> dict:
    avg_vol    = float(df["Volume"].mean())
    recent_vol = float(df["Volume"].tail(VOLUME_LOOKBACK).mean())
    ratio      = round(recent_vol / avg_vol, 2) if avg_vol > 0 else 1.0

    if ratio > VOLUME_RISING:   signal, icon = "rising -- confirms price move", "✅"
    elif ratio < VOLUME_FALLING:signal, icon = "falling -- weak conviction",    "⚠️"
    else:                       signal, icon = "stable",                        "➡️"
    return {"avg_volume": round(avg_vol, 0), "recent_volume": round(recent_vol, 0),
            "ratio": ratio, "signal": signal, "icon": icon}


# ============================================================
# Scorer
# ============================================================
def make_serializable(obj):
    if isinstance(obj, dict):    return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):  return [make_serializable(v) for v in obj]
    elif isinstance(obj, np.bool_):    return bool(obj)
    elif isinstance(obj, np.integer):  return int(obj)
    elif isinstance(obj, np.floating): return float(obj)
    else: return obj


def get_verdict(score: int) -> tuple:
    if score >= 75:  return "Strong Buy",   "🟢"
    elif score >= 60:return "Buy",          "🟩"
    elif score >= 40:return "Neutral",      "⬜"
    elif score >= 25:return "Sell",         "🟥"
    else:            return "Strong Sell",  "🔴"


def check_downtrend(mas: dict) -> tuple:
    ma20_below  = mas["ma20"]["above"]  is False
    ma50_below  = mas["ma50"]["above"]  is False
    ma200_below = mas["ma200"]["above"] is False

    if ma20_below and ma50_below and ma200_below:
        return True,  -30, "price below MA20+MA50+MA200 -- structural downtrend 🔴"
    elif ma200_below:
        return True,  -20, "price below MA200 -- long term breakdown ⚠️"
    elif ma20_below and ma50_below and not ma200_below:
        return False,   0, "short term pullback -- long term uptrend intact ✅"
    elif ma20_below and not ma50_below and not ma200_below:
        return False,   0, "minor pullback -- no structural concern ✅"
    else:
        return False,   0, "price above all MAs -- uptrend confirmed ✅"


def score_short_term(rsi, stoch, roc, bb, mas) -> dict:
    score, signals = 0, []

    if rsi["value"] < RSI_OVERSOLD:    score += 25
    elif rsi["value"] < 45:            score += 18
    elif rsi["value"] > RSI_OVERBOUGHT:score += 5
    elif rsi["value"] > 55:            score += 8
    else:                              score += 12
    signals.append(f"RSI ({rsi['value']}) -- {rsi['signal']} {rsi['icon']}")

    if stoch["value"] < STOCH_OVERSOLD:    score += 20
    elif stoch["value"] < 35:              score += 14
    elif stoch["value"] > STOCH_OVERBOUGHT:score += 4
    elif stoch["value"] > 65:              score += 7
    else:                                  score += 10
    signals.append(f"Stochastic ({stoch['value']}) -- {stoch['signal']} {stoch['icon']}")

    if roc["value"] > 5:    score += 20
    elif roc["value"] > 0:  score += 12
    elif roc["value"] < -5: score += 0
    else:                   score += 4
    signals.append(f"ROC ({roc['value']}%) -- {roc['signal']} {roc['icon']}")

    if bb["pct"] < 20:   score += 15
    elif bb["pct"] > 80: score += 3
    else:                score += 8
    signals.append(f"Bollinger Bands ({bb['pct']}%) -- {bb['signal']} {bb['icon']}")

    _, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score = max(0, min(100, score))
    verdict, icon = get_verdict(score)
    return {"score": score, "verdict": verdict, "icon": icon, "signals": signals}


def score_mid_term(macd, mas, atr, vol) -> dict:
    score, signals = 0, []

    if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:  score += 30
    elif macd["histogram"] < 0 and macd["macd"] < macd["signal"]:score += 0
    else:                                                          score += 12
    signals.append(f"MACD ({macd['histogram']}) -- {macd['signal_label']} {macd['icon']}")

    if mas["ma20"]["above"] is True:   score += 15
    elif mas["ma20"]["above"] is False:score += (5 if mas["ma200"]["above"] else 0)
    signals.append(f"MA20 (${mas['ma20']['value']}) -- {mas['ma20']['signal']} {mas['ma20']['icon']}")

    if mas["ma50"]["above"] is True:   score += 20
    elif mas["ma50"]["above"] is False:score += (7 if mas["ma200"]["above"] else 0)
    signals.append(f"MA50 (${mas['ma50']['value']}) -- {mas['ma50']['signal']} {mas['ma50']['icon']}")

    if atr["pct"] < 1.5:   score += 10
    elif atr["pct"] < 3:   score += 6
    else:                  score += 2
    signals.append(f"ATR (${atr['value']} / {atr['pct']}%) -- {atr['signal']} {atr['icon']}")

    if vol["ratio"] > VOLUME_RISING:   score += 15
    elif vol["ratio"] < VOLUME_FALLING:score += 0
    else:                              score += 7
    signals.append(f"Volume ({vol['ratio']}x avg) -- {vol['signal']} {vol['icon']}")

    _, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score = max(0, min(100, score))
    verdict, icon = get_verdict(score)
    return {"score": score, "verdict": verdict, "icon": icon, "signals": signals}


def score_long_term(mas, golden, vol) -> dict:
    score, signals = 0, []

    if mas["ma200"]["above"] is True:  score += 35
    elif mas["ma200"]["above"] is False:score += 0
    signals.append(f"MA200 (${mas['ma200']['value']}) -- {mas['ma200']['signal']} {mas['ma200']['icon']}")

    if golden["value"] is not None:
        if golden["golden"] and "fresh" in golden["signal"]:   score += 40
        elif golden["golden"]:                                 score += 28
        elif not golden["golden"] and "fresh" in golden["signal"]:score += 0
        else:                                                  score += 5
    signals.append(f"Golden/Death Cross -- {golden['signal']} {golden['icon']}")

    if vol["ratio"] > VOLUME_RISING:   score += 15
    elif vol["ratio"] < VOLUME_FALLING:score += 0
    else:                              score += 7
    signals.append(f"Volume ({vol['ratio']}x avg) -- {vol['signal']} {vol['icon']}")

    _, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score = max(0, min(100, score))
    verdict, icon = get_verdict(score)
    return {"score": score, "verdict": verdict, "icon": icon, "signals": signals}


# ============================================================
# Master Analysis
# ============================================================
def technical_analysis(company: str) -> dict:
    ticker     = resolve_ticker(company)
    price_data = fetch_price_data(ticker)
    if "error" in price_data:
        return {"error": price_data["error"]}

    hist_data = fetch_historical_data(ticker)
    if not hist_data["success"]:
        return {"error": hist_data["error"]}

    df, closes        = hist_data["df"], hist_data["closes"]
    current_price     = price_data["current_price"]

    rsi    = compute_rsi(closes)
    stoch  = compute_stochastic(df)
    roc    = compute_roc(closes)
    macd   = compute_macd(closes)
    mas    = compute_moving_averages(closes, current_price)
    golden = compute_golden_cross(closes)
    bb     = compute_bollinger_bands(closes, current_price)
    atr    = compute_atr(df)
    vol    = compute_volume_trend(df)

    short = score_short_term(rsi, stoch, roc, bb, mas)
    mid   = score_mid_term(macd, mas, atr, vol)
    long  = score_long_term(mas, golden, vol)

    overall_score = round(short["score"]*0.30 + mid["score"]*0.35 + long["score"]*0.35)
    overall_score = max(0, min(100, overall_score))
    overall_verdict, icon = get_verdict(overall_score)

    result = {
        "ticker": ticker,
        "company": price_data["name"],
        "current_price": current_price,
        "price_change": price_data["price_change"],
        "price_change_pct": price_data["price_change_pct"],
        "short_term": short,
        "mid_term":   mid,
        "long_term":  long,
        "overall": {"score": overall_score, "verdict": overall_verdict, "icon": icon},
        # Raw indicators for UI display only (not sent to GPT)
        "indicators": {
            "rsi": rsi, "stochastic": stoch, "roc": roc,
            "macd": macd, "moving_averages": mas,
            "golden_cross": golden, "bollinger_bands": bb,
            "atr": atr, "volume_trend": vol,
        },
        "price_data": price_data,
    }
    return make_serializable(result)


def compare_stocks(companies: list) -> dict:
    validation = validate_companies(companies)
    if not validation["valid"]:
        return {"error": validation["error"]}

    results = []
    for company in validation["tickers"]:
        result = technical_analysis(company)
        if "error" in result:
            return {"error": f"Failed to analyze {company}: {result['error']}"}
        results.append(result)

    results.sort(key=lambda x: x["overall"]["score"], reverse=True)

    short_best = max(results, key=lambda x: x["short_term"]["score"])
    mid_best   = max(results, key=lambda x: x["mid_term"]["score"])
    long_best  = max(results, key=lambda x: x["long_term"]["score"])
    lowest_risk = min(results, key=lambda x: x["indicators"]["atr"]["pct"])

    return {
        "stocks": results,
        "ranked": [r["ticker"] for r in results],
        "best_short": short_best["ticker"],
        "best_mid":   mid_best["ticker"],
        "best_long":  long_best["ticker"],
        "lowest_risk": lowest_risk["ticker"],
    }


# ============================================================
# Fix D – Intent detection in Python (no GPT call needed)
# ============================================================
def detect_intent(user_message: str) -> dict:
    """
    Parses the user message in Python to decide which tool to call.
    This replaces the first GPT tool-dispatch call, saving one API
    round-trip per user message.

    Returns:
        {"intent": "single",    "company": "AAPL"}
        {"intent": "compare",   "companies": ["NVDA","AMD"]}
        {"intent": "price",     "company": "TSLA"}
        {"intent": "chat"}
    """
    msg = user_message.lower()

    # --- Comparison intent ---
    compare_keywords = ["compare", "vs", "versus", "rank", "which of",
                        "better buy", "between"]
    if any(kw in msg for kw in compare_keywords):
        # Extract potential tickers/names (capitalised words or known patterns)
        tokens = re.findall(r'\b[A-Z]{1,5}\b', user_message)
        names  = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b', user_message)
        candidates = list(dict.fromkeys(tokens + names))  # dedupe, preserve order
        if len(candidates) >= 2:
            return {"intent": "compare", "companies": candidates[:MAX_STOCKS]}

    # --- Price / real-time data intent ---
    price_keywords = ["price", "real time", "real-time", "current price",
                      "how much is", "what is.*trading", "quote"]
    if any(re.search(kw, msg) for kw in price_keywords):
        tokens = re.findall(r'\b[A-Z]{1,5}\b', user_message)
        if tokens:
            return {"intent": "price", "company": tokens[0]}

    # --- Single analysis intent ---
    analysis_keywords = ["analysis", "analyze", "analyse", "technical",
                         "buy", "sell", "good stock", "should i",
                         "indicator", "score", "short term", "long term",
                         "mid term", "breakdown"]
    if any(kw in msg for kw in analysis_keywords):
        tokens = re.findall(r'\b[A-Z]{2,5}\b', user_message)
        if tokens:
            return {"intent": "single", "company": tokens[0]}
        # Try to grab a company name if no ticker found
        words = user_message.split()
        for w in words:
            if w[0].isupper() and len(w) > 2 and w.lower() not in {
                "run","show","give","tell","what","does","the","for","me","is","a"}:
                return {"intent": "single", "company": w}

    # --- Fallback: try to find any ticker and do single analysis ---
    tokens = re.findall(r'\b[A-Z]{2,5}\b', user_message)
    if tokens:
        # Heuristic: if message seems stock-related
        stock_hints = ["stock", "share", "nasdaq", "nyse", "etf",
                       "invest", "trade", "market", "chart"]
        if any(h in msg for h in stock_hints):
            return {"intent": "single", "company": tokens[0]}

    return {"intent": "chat"}


# ============================================================
# GPT Summary Generators  (single call each, slimmed payload)
# ============================================================
def generate_single_summary(client, result: dict, model: str) -> str:
    slim = slim_analysis(result)
    prompt = (
        f"You are a concise stock analyst. Here is the technical analysis result:\n"
        f"{json.dumps(slim, indent=2)}\n\n"
        f"Write a 3-4 sentence summary covering: overall verdict, key bullish/bearish "
        f"signals, and a brief outlook. Be direct and avoid filler phrases."
    )
    response = call_openai_with_retry(
        client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,   # Fix E – capped tokens
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def generate_comparison_summary(client, comparison: dict, model: str) -> str:
    slim = slim_comparison(comparison["stocks"])
    payload = {
        "ranked":      comparison["ranked"],
        "best_short":  comparison["best_short"],
        "best_mid":    comparison["best_mid"],
        "best_long":   comparison["best_long"],
        "lowest_risk": comparison["lowest_risk"],
        "stocks":      slim,
    }
    prompt = (
        f"You are a concise stock analyst. Here is a multi-stock comparison:\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        f"Write a 4-5 sentence comparison summary: which stock ranks best overall, "
        f"which is best for each time horizon, which has lowest risk, and why. "
        f"Be direct and avoid filler phrases."
    )
    response = call_openai_with_retry(
        client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,   # Fix E – capped tokens
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def generate_chat_response(client, messages: list, model: str) -> str:
    trimmed = trim_history(messages, keep_last=6)   # Fix B
    response = call_openai_with_retry(
        client,
        model=model,
        messages=trimmed,
        max_tokens=400,   # Fix E
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ============================================================
# UI Helpers
# ============================================================
def format_market_cap(val):
    if val is None: return "N/A"
    if val >= 1e12: return f"${val/1e12:.2f}T"
    if val >= 1e9:  return f"${val/1e9:.2f}B"
    if val >= 1e6:  return f"${val/1e6:.2f}M"
    return f"${val:,.0f}"


def format_volume(val):
    if val is None: return "N/A"
    if val >= 1e9:  return f"{val/1e9:.2f}B"
    if val >= 1e6:  return f"{val/1e6:.2f}M"
    if val >= 1e3:  return f"{val/1e3:.1f}K"
    return str(int(val))


def score_color(score: int) -> str:
    if score >= 75: return "#22c55e"
    if score >= 60: return "#86efac"
    if score >= 40: return "#d1d5db"
    if score >= 25: return "#fca5a5"
    return "#ef4444"


def render_score_card(label: str, score: int, verdict: str, icon: str):
    color = score_color(score)
    st.markdown(f"""
    <div style="background:{color}22;border:2px solid {color};border-radius:10px;
                padding:12px;text-align:center;margin:4px;">
        <div style="font-size:0.85em;color:#6b7280;font-weight:600">{label}</div>
        <div style="font-size:2em;font-weight:800;color:{color}">{score}</div>
        <div style="font-size:0.9em;font-weight:600">{icon} {verdict}</div>
    </div>
    """, unsafe_allow_html=True)


def render_single_analysis(result: dict, ai_summary: str):
    pd_data = result.get("price_data", {})
    ind     = result.get("indicators", {})

    st.subheader(f"📈 {result['company']} ({result['ticker']})")

    # Price row
    change_color = "#22c55e" if result["price_change"] >= 0 else "#ef4444"
    arrow        = "▲" if result["price_change"] >= 0 else "▼"
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Price",    f"${result['current_price']}")
    col2.metric("Change",   f"{arrow} ${abs(result['price_change'])}",
                delta=f"{result['price_change_pct']}%")
    col3.metric("Volume",   format_volume(pd_data.get("volume")))
    col4.metric("Mkt Cap",  format_market_cap(pd_data.get("market_cap")))

    # Score cards
    st.markdown("#### Technical Scores")
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_score_card("Short Term", result["short_term"]["score"],
                               result["short_term"]["verdict"], result["short_term"]["icon"])
    with c2: render_score_card("Mid Term",   result["mid_term"]["score"],
                               result["mid_term"]["verdict"],   result["mid_term"]["icon"])
    with c3: render_score_card("Long Term",  result["long_term"]["score"],
                               result["long_term"]["verdict"],  result["long_term"]["icon"])
    with c4: render_score_card("Overall",    result["overall"]["score"],
                               result["overall"]["verdict"],    result["overall"]["icon"])

    # AI summary
    if ai_summary:
        st.markdown("#### 🤖 AI Analysis")
        st.info(ai_summary)

    # Expandable indicators
    with st.expander("📊 Full Indicator Breakdown"):
        st.markdown("**Short-term signals:**")
        for sig in result["short_term"]["signals"]:
            st.markdown(f"- {sig}")
        st.markdown("**Mid-term signals:**")
        for sig in result["mid_term"]["signals"]:
            st.markdown(f"- {sig}")
        st.markdown("**Long-term signals:**")
        for sig in result["long_term"]["signals"]:
            st.markdown(f"- {sig}")

        st.markdown("---")
        ma = ind.get("moving_averages", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("MA20",  f"${ma.get('ma20',{}).get('value','N/A')}")
        c2.metric("MA50",  f"${ma.get('ma50',{}).get('value','N/A')}")
        c3.metric("MA200", f"${ma.get('ma200',{}).get('value','N/A')}")

        bb = ind.get("bollinger_bands", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("BB Upper", f"${bb.get('upper','N/A')}")
        c2.metric("BB Middle",f"${bb.get('middle','N/A')}")
        c3.metric("BB Lower", f"${bb.get('lower','N/A')}")


def render_comparison(comparison: dict, ai_summary: str):
    stocks = comparison["stocks"]
    st.subheader("📊 Multi-Stock Comparison")

    # Rankings
    medals = ["🥇","🥈","🥉"]
    for i, s in enumerate(stocks):
        medal = medals[i] if i < 3 else ""
        st.markdown(
            f"{medal} **{s['ticker']}** — Overall: **{s['overall']['score']}** "
            f"{s['overall']['icon']} {s['overall']['verdict']}"
        )

    # Comparison table
    st.markdown("#### Indicator Comparison")
    rows = []
    for s in stocks:
        rows.append({
            "Ticker":      s["ticker"],
            "Price":       f"${s['current_price']}",
            "Short":       f"{s['short_term']['score']} {s['short_term']['icon']}",
            "Mid":         f"{s['mid_term']['score']} {s['mid_term']['icon']}",
            "Long":        f"{s['long_term']['score']} {s['long_term']['icon']}",
            "Overall":     f"{s['overall']['score']} {s['overall']['icon']}",
        })
    st.dataframe(rows, use_container_width=True)

    # Best picks
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Best Short",  comparison["best_short"])
    c2.metric("Best Mid",    comparison["best_mid"])
    c3.metric("Best Long",   comparison["best_long"])
    c4.metric("Lowest Risk", comparison["lowest_risk"])

    # AI summary
    if ai_summary:
        st.markdown("#### 🤖 AI Comparison Summary")
        st.info(ai_summary)


def render_price_data(price_data: dict):
    st.subheader(f"💹 {price_data.get('name')} ({price_data.get('ticker')})")
    arrow = "▲" if price_data.get("price_change", 0) >= 0 else "▼"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", f"${price_data['current_price']}")
    c2.metric("Change",
              f"{arrow} ${abs(price_data['price_change'])}",
              delta=f"{price_data['price_change_pct']}%")
    c3.metric("Volume",     format_volume(price_data.get("volume")))
    c4.metric("Market Cap", format_market_cap(price_data.get("market_cap")))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Day High",  f"${price_data.get('day_high','N/A')}")
    c2.metric("Day Low",   f"${price_data.get('day_low','N/A')}")
    c3.metric("52W High",  f"${price_data.get('52w_high','N/A')}")
    c4.metric("52W Low",   f"${price_data.get('52w_low','N/A')}")
    st.caption(f"As of {price_data.get('timestamp')}")


# ============================================================
# Main Streamlit App
# ============================================================
def main():
    st.set_page_config(
        page_title="📈 Stock Analysis Chatbot",
        page_icon="📈",
        layout="wide",
    )

    st.title("📈 Real-Time Stock Analysis Chatbot")

    # ── Sidebar ───────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input("OpenAI API Key", type="password",
                                placeholder="sk-...")
        model = st.selectbox(
            "Model",
            ["gpt-4.1-mini", "gpt-4o-mini", "gpt-3.5-turbo",
             "gpt-4o", "gpt-4.1"],
            index=0,
            help="gpt-4.1-mini recommended — best balance of quality & rate limits",
        )

        st.markdown("---")
        st.markdown("### 💬 Example Queries")
        examples = [
            "Is NVDA a good buy right now?",
            "Run technical analysis on Tesla",
            "Compare NVDA, AMD and Intel",
            "Give me real-time data for Apple",
            "Which of MSFT or GOOGL is better?",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.pending_input = ex

        st.markdown("---")
        if st.button("🔄 Reset Chat", use_container_width=True):
            st.session_state.messages       = []
            st.session_state.chat_history   = []
            st.session_state.pending_input  = None
            st.rerun()

        st.markdown("---")
        st.caption(
            "ℹ️ Rate limit fixes applied:\n"
            "• Exponential backoff on 429\n"
            "• History trimmed to last 6 turns\n"
            "• Slim JSON sent to GPT\n"
            "• 1 GPT call per query (not 2)\n"
            "• Max 400-500 tokens per response"
        )

    # ── Session state ─────────────────────────────────────
    if "messages"     not in st.session_state: st.session_state.messages      = []
    if "chat_history" not in st.session_state: st.session_state.chat_history  = []
    if "pending_input"not in st.session_state: st.session_state.pending_input = None

    # ── Chat display ──────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and "widget" in msg:
                w = msg["widget"]
                if w["type"] == "single":
                    render_single_analysis(w["result"], w.get("summary",""))
                elif w["type"] == "compare":
                    render_comparison(w["comparison"], w.get("summary",""))
                elif w["type"] == "price":
                    render_price_data(w["price_data"])
            else:
                st.markdown(msg["content"])

    # ── Input ─────────────────────────────────────────────
    user_input = st.chat_input("Ask about a stock…")
    if st.session_state.pending_input:
        user_input = st.session_state.pending_input
        st.session_state.pending_input = None

    if not user_input:
        return

    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        return

    client = OpenAI(api_key=api_key)

    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Add to GPT conversation history
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "system",
            "content": (
                "You are a knowledgeable stock market assistant. "
                "You help users understand technical analysis results "
                "and general investing concepts. Be concise and clear."
            ),
        })
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # ── Intent detection (Python, no GPT call) ────────────
    intent = detect_intent(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing…"):
            try:
                # ── SINGLE STOCK ANALYSIS ─────────────────
                if intent["intent"] == "single":
                    result = technical_analysis(intent["company"])
                    if "error" in result:
                        st.error(result["error"])
                        st.session_state.messages.append(
                            {"role":"assistant","content":result["error"]})
                        return
                    summary = generate_single_summary(client, result, model)
                    render_single_analysis(result, summary)
                    assistant_text = (
                        f"Technical analysis complete for **{result['ticker']}**. "
                        f"Overall score: **{result['overall']['score']}** — "
                        f"{result['overall']['icon']} {result['overall']['verdict']}"
                    )
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": assistant_text,
                        "widget": {"type":"single","result":result,"summary":summary},
                    })
                    st.session_state.chat_history.append(
                        {"role":"assistant","content":assistant_text})

                # ── COMPARISON ────────────────────────────
                elif intent["intent"] == "compare":
                    comparison = compare_stocks(intent["companies"])
                    if "error" in comparison:
                        st.error(comparison["error"])
                        st.session_state.messages.append(
                            {"role":"assistant","content":comparison["error"]})
                        return
                    summary = generate_comparison_summary(client, comparison, model)
                    render_comparison(comparison, summary)
                    tickers = ", ".join(comparison["ranked"])
                    assistant_text = (
                        f"Comparison complete for **{tickers}**. "
                        f"Top pick: **{comparison['ranked'][0]}**"
                    )
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": assistant_text,
                        "widget": {"type":"compare","comparison":comparison,"summary":summary},
                    })
                    st.session_state.chat_history.append(
                        {"role":"assistant","content":assistant_text})

                # ── PRICE DATA ────────────────────────────
                elif intent["intent"] == "price":
                    ticker     = resolve_ticker(intent["company"])
                    price_data = fetch_price_data(ticker)
                    if "error" in price_data:
                        st.error(price_data["error"])
                        st.session_state.messages.append(
                            {"role":"assistant","content":price_data["error"]})
                        return
                    render_price_data(price_data)
                    assistant_text = (
                        f"Real-time data for **{price_data['name']}** "
                        f"({price_data['ticker']}): "
                        f"**${price_data['current_price']}** "
                        f"({price_data['price_change_pct']}%)"
                    )
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": assistant_text,
                        "widget": {"type":"price","price_data":price_data},
                    })
                    st.session_state.chat_history.append(
                        {"role":"assistant","content":assistant_text})

                # ── GENERAL CHAT ──────────────────────────
                else:
                    reply = generate_chat_response(
                        client, st.session_state.chat_history, model)
                    st.markdown(reply)
                    st.session_state.messages.append(
                        {"role":"assistant","content":reply})
                    st.session_state.chat_history.append(
                        {"role":"assistant","content":reply})

            except RateLimitError:
                err = (
                    "⚠️ OpenAI rate limit reached after retries. "
                    "Please wait 60 seconds and try again, or switch "
                    "to **gpt-4.1-mini** or **gpt-3.5-turbo** in the sidebar."
                )
                st.error(err)
                st.session_state.messages.append({"role":"assistant","content":err})

            except Exception as e:
                err = f"❌ Error: {str(e)}"
                st.error(err)
                st.session_state.messages.append({"role":"assistant","content":err})


if __name__ == "__main__":
    main()
