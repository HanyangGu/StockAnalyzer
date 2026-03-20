# ============================================================
# REAL-TIME STOCK ANALYSIS CHATBOT
# ============================================================
# A conversational AI powered stock analysis application
# combining Yahoo Finance market data with OpenAI GPT and
# technical analysis across 3 time horizons.
# ============================================================

# ============================================================
# SECTION 1 -- Imports & Configuration
# ============================================================

# Standard library
import os
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
from openai import OpenAI

# Frontend
import streamlit as st

# ============================================================
# CONFIGURATION CONSTANTS
# ============================================================

# AI
GPT_MODEL         = "gpt-4o"
TEMPERATURE       = 0.3

# Data
DATA_PERIOD       = "1y"
DATA_INTERVAL     = "1d"
MIN_DATA_POINTS   = 30

# Stock limits
MIN_STOCKS        = 2
MAX_STOCKS        = 3

# Scoring baseline
BASELINE_SCORE    = 0

# Relative Strength Index
RSI_PERIOD        = 14
RSI_OVERSOLD      = 30
RSI_OVERBOUGHT    = 70

# Stochastic Oscillator
STOCH_PERIOD      = 14
STOCH_OVERSOLD    = 20
STOCH_OVERBOUGHT  = 80

# Rate of Change
ROC_PERIOD        = 10

# Moving Average Convergence Divergence
MACD_FAST         = 12
MACD_SLOW         = 26
MACD_SIGNAL       = 9

# Moving Averages
MA_SHORT          = 20
MA_MID            = 50
MA_LONG           = 200

# Bollinger Bands
BB_PERIOD         = 20
BB_STD            = 2

# Average True Range
ATR_PERIOD        = 14

# Volume
VOLUME_RISING     = 1.1
VOLUME_FALLING    = 0.9
VOLUME_LOOKBACK   = 5


# ============================================================
# SECTION 2 -- Ticker Resolution
# ============================================================

def resolve_ticker(company: str) -> str:
    """
    Resolves a company name or ticker symbol into a valid
    Yahoo Finance ticker symbol.

    Priority:
      1. Try input directly as a ticker (fastest path)
      2. Search Yahoo Finance by company name
      3. Fall back to cleaned input if both fail
    """
    candidate = company.upper().strip()

    # Step 1: Try as direct ticker
    try:
        info = yf.Ticker(candidate).info
        has_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice")
        )
        if has_price:
            return candidate
    except Exception:
        pass

    # Step 2: Search by company name
    try:
        results = yf.Search(company, max_results=5).quotes
        if results:
            for r in results:
                if r.get("quoteType") == "EQUITY":
                    return r["symbol"]
            return results[0]["symbol"]
    except Exception:
        pass

    # Step 3: Last resort fallback
    return candidate


def validate_companies(companies: list) -> dict:
    """
    Validates a list of companies for the comparison function.
    Enforces MIN_STOCKS and MAX_STOCKS limits.
    """
    seen = set()
    unique = []
    for c in companies:
        cleaned = c.strip().upper()
        if cleaned not in seen:
            seen.add(cleaned)
            unique.append(c.strip())

    if len(unique) < MIN_STOCKS:
        return {
            "valid": False,
            "error": f"Please provide at least {MIN_STOCKS} stocks to compare."
        }
    if len(unique) > MAX_STOCKS:
        return {
            "valid": False,
            "error": (
                f"Maximum {MAX_STOCKS} stocks can be compared at once. "
                f"You provided {len(unique)}. Please reduce your selection."
            )
        }

    return {"valid": True, "tickers": unique}


# ============================================================
# SECTION 3 -- Data Fetcher
# ============================================================

def fetch_price_data(ticker_symbol: str) -> dict:
    """
    Fetches real-time price and market data for a single stock.
    """
    try:
        stock  = yf.Ticker(ticker_symbol)
        info   = stock.info

        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice")
        )
        if not current_price:
            return {
                "error": (
                    f"Could not retrieve price data for "
                    f"'{ticker_symbol}'. Market may be closed "
                    f"or ticker may be invalid."
                )
            }

        prev_close       = info.get("previousClose", 0) or 0
        price_change     = round(current_price - prev_close, 2)
        price_change_pct = round(
            (price_change / prev_close * 100)
            if prev_close else 0, 2
        )

        intraday = stock.history(period="1d", interval="1m")
        recent_closes = (
            intraday["Close"].tail(5).round(2).tolist()
            if not intraday.empty else []
        )

        return {
            "ticker":            ticker_symbol,
            "name":              info.get("longName", ticker_symbol),
            "exchange":          info.get("exchange"),
            "sector":            info.get("sector"),
            "industry":          info.get("industry"),
            "currency":          info.get("currency", "USD"),
            "current_price":     round(current_price, 2),
            "prev_close":        round(prev_close, 2),
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

    except Exception as e:
        return {"error": str(e)}


def fetch_historical_data(ticker_symbol: str) -> dict:
    """
    Fetches 1 year of daily OHLCV historical data
    for technical indicator calculation.
    """
    try:
        stock = yf.Ticker(ticker_symbol)
        df    = stock.history(
            period   = DATA_PERIOD,
            interval = DATA_INTERVAL
        )

        if df.empty:
            return {
                "success": False,
                "error":   f"No historical data found for {ticker_symbol}."
            }
        if len(df) < MIN_DATA_POINTS:
            return {
                "success": False,
                "error": (
                    f"Insufficient data for {ticker_symbol}. "
                    f"Need at least {MIN_DATA_POINTS} trading days."
                )
            }

        return {
            "success": True,
            "df":      df,
            "closes":  df["Close"],
            "days":    len(df),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# SECTION 4 -- Technical Indicators
# ============================================================

# -- MOMENTUM -------------------------------------------------

def compute_rsi(closes: pd.Series) -> dict:
    """Relative Strength Index -- momentum indicator 0 to 100."""
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss  = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs    = gain / loss.replace(0, float("inf"))
    rsi   = round(float((100 - (100 / (1 + rs))).iloc[-1]), 2)

    if rsi < RSI_OVERSOLD:
        signal, icon = "oversold -- strong buy", "✅"
    elif rsi < 45:
        signal, icon = "mildly oversold -- buy", "✅"
    elif rsi > RSI_OVERBOUGHT:
        signal, icon = "overbought -- caution", "⚠️"
    elif rsi > 55:
        signal, icon = "mildly overbought -- watch", "⚠️"
    else:
        signal, icon = "neutral", "➡️"

    return {"value": rsi, "signal": signal, "icon": icon}


def compute_stochastic(df: pd.DataFrame) -> dict:
    """Stochastic Oscillator -- momentum indicator 0 to 100."""
    low_min  = df["Low"].rolling(STOCH_PERIOD).min()
    high_max = df["High"].rolling(STOCH_PERIOD).max()
    k_range  = high_max - low_min
    k        = round(float(
        (((df["Close"] - low_min) / k_range.replace(0, float("inf")))
         * 100).iloc[-1]
    ), 2)

    if k < STOCH_OVERSOLD:
        signal, icon = "oversold -- strong buy", "✅"
    elif k < 35:
        signal, icon = "mildly oversold -- buy", "✅"
    elif k > STOCH_OVERBOUGHT:
        signal, icon = "overbought -- caution", "⚠️"
    elif k > 65:
        signal, icon = "mildly overbought -- watch", "⚠️"
    else:
        signal, icon = "neutral", "➡️"

    return {"value": k, "signal": signal, "icon": icon}


def compute_roc(closes: pd.Series) -> dict:
    """Rate of Change -- momentum percentage change over period."""
    roc = round(float(
        ((closes.iloc[-1] - closes.iloc[-ROC_PERIOD])
         / closes.iloc[-ROC_PERIOD]) * 100
    ), 2)

    if roc > 5:
        signal, icon = "strong positive momentum", "✅"
    elif roc > 0:
        signal, icon = "mild positive momentum", "✅"
    elif roc < -5:
        signal, icon = "strong negative momentum", "⚠️"
    else:
        signal, icon = "mild negative momentum", "⚠️"

    return {"value": roc, "signal": signal, "icon": icon}


# -- TREND ----------------------------------------------------

def compute_macd(closes: pd.Series) -> dict:
    """Moving Average Convergence Divergence -- trend indicator."""
    ema_fast  = closes.ewm(span=MACD_FAST,   adjust=False).mean()
    ema_slow  = closes.ewm(span=MACD_SLOW,   adjust=False).mean()
    macd      = ema_fast - ema_slow
    signal    = macd.ewm(span=MACD_SIGNAL,   adjust=False).mean()
    histogram = macd - signal

    macd_val   = round(float(macd.iloc[-1]),      4)
    signal_val = round(float(signal.iloc[-1]),    4)
    hist_val   = round(float(histogram.iloc[-1]), 4)

    if hist_val > 0 and macd_val > signal_val:
        sig, icon = "bullish crossover", "✅"
    elif hist_val < 0 and macd_val < signal_val:
        sig, icon = "bearish crossover", "⚠️"
    else:
        sig, icon = "neutral", "➡️"

    return {
        "macd":         macd_val,
        "signal":       signal_val,
        "histogram":    hist_val,
        "signal_label": sig,
        "icon":         icon,
    }


def compute_moving_averages(closes: pd.Series,
                             current_price: float) -> dict:
    """Simple Moving Averages -- MA20, MA50, MA200."""
    results = {}
    for period, label in [
        (MA_SHORT, "ma20"),
        (MA_MID,   "ma50"),
        (MA_LONG,  "ma200")
    ]:
        if len(closes) >= period:
            ma_val = round(float(
                closes.rolling(period).mean().iloc[-1]
            ), 2)
            above  = current_price > ma_val
            results[label] = {
                "value":  ma_val,
                "above":  above,
                "signal": "price above -- bullish" if above
                          else "price below -- bearish",
                "icon":   "✅" if above else "⚠️",
            }
        else:
            results[label] = {
                "value":  None,
                "above":  None,
                "signal": "insufficient data",
                "icon":   "➡️",
            }
    return results


def compute_golden_cross(closes: pd.Series) -> dict:
    """Golden Cross and Death Cross -- long term trend signal."""
    if len(closes) < MA_LONG:
        return {
            "value":  None,
            "signal": "insufficient data",
            "icon":   "➡️",
            "golden": None,
        }

    ma50  = closes.rolling(MA_MID).mean()
    ma200 = closes.rolling(MA_LONG).mean()

    ma50_now,  ma200_now  = ma50.iloc[-1],  ma200.iloc[-1]
    ma50_prev, ma200_prev = ma50.iloc[-2],  ma200.iloc[-2]

    golden_cross = (ma50_prev <= ma200_prev) and (ma50_now > ma200_now)
    death_cross  = (ma50_prev >= ma200_prev) and (ma50_now < ma200_now)

    if ma50_now > ma200_now:
        if golden_cross:
            signal, icon = "fresh golden cross -- strong buy", "✅"
        else:
            signal, icon = "golden cross active -- bullish", "✅"
    else:
        if death_cross:
            signal, icon = "fresh death cross -- strong sell", "⚠️"
        else:
            signal, icon = "death cross active -- bearish", "⚠️"

    return {
        "value":  round(float(ma50_now), 2),
        "ma200":  round(float(ma200_now), 2),
        "signal": signal,
        "icon":   icon,
        "golden": ma50_now > ma200_now,
    }


# -- VOLATILITY -----------------------------------------------

def compute_bollinger_bands(closes: pd.Series,
                             current_price: float) -> dict:
    """Bollinger Bands -- volatility indicator."""
    ma    = closes.rolling(BB_PERIOD).mean()
    std   = closes.rolling(BB_PERIOD).std()
    upper = round(float((ma + BB_STD * std).iloc[-1]), 2)
    mid   = round(float(ma.iloc[-1]), 2)
    lower = round(float((ma - BB_STD * std).iloc[-1]), 2)

    bb_range = upper - lower
    bb_pct   = round(
        float((current_price - lower) / bb_range * 100)
        if bb_range > 0 else 50, 2
    )

    if bb_pct < 20:
        signal, icon = "near lower band -- potential bounce", "✅"
    elif bb_pct > 80:
        signal, icon = "near upper band -- potential pullback", "⚠️"
    else:
        signal, icon = "mid band -- neutral", "➡️"

    return {
        "upper":  upper,
        "middle": mid,
        "lower":  lower,
        "pct":    bb_pct,
        "signal": signal,
        "icon":   icon,
    }


def compute_atr(df: pd.DataFrame) -> dict:
    """Average True Range -- volatility measure."""
    high       = df["High"]
    low        = df["Low"]
    prev_close = df["Close"].shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs()
    ], axis=1).max(axis=1)

    atr           = round(float(tr.rolling(ATR_PERIOD).mean().iloc[-1]), 4)
    current_price = round(float(df["Close"].iloc[-1]), 2)
    atr_pct       = round((atr / current_price) * 100, 2)

    if atr_pct > 3:
        signal, icon = "high volatility", "⚠️"
    elif atr_pct > 1.5:
        signal, icon = "moderate volatility", "➡️"
    else:
        signal, icon = "low volatility", "✅"

    return {
        "value":  atr,
        "pct":    atr_pct,
        "signal": signal,
        "icon":   icon,
    }


# -- VOLUME ---------------------------------------------------

def compute_volume_trend(df: pd.DataFrame) -> dict:
    """Volume Trend -- confirms price moves with volume conviction."""
    avg_vol    = float(df["Volume"].mean())
    recent_vol = float(df["Volume"].tail(VOLUME_LOOKBACK).mean())
    ratio      = round(recent_vol / avg_vol, 2) if avg_vol > 0 else 1.0

    if ratio > VOLUME_RISING:
        signal, icon = "rising -- confirms price move", "✅"
    elif ratio < VOLUME_FALLING:
        signal, icon = "falling -- weak conviction", "⚠️"
    else:
        signal, icon = "stable", "➡️"

    return {
        "avg_volume":    round(avg_vol, 0),
        "recent_volume": round(recent_vol, 0),
        "ratio":         ratio,
        "signal":        signal,
        "icon":          icon,
    }


# ============================================================
# SECTION 5 -- Scorer
# ============================================================

def make_serializable(obj):
    """Converts numpy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    else:
        return obj


def get_verdict(score: int) -> tuple:
    """Converts a numerical score into a verdict label and emoji."""
    if score >= 75:
        return "Strong Buy",  "🟢"
    elif score >= 60:
        return "Buy",         "🟩"
    elif score >= 40:
        return "Neutral",     "⬜"
    elif score >= 25:
        return "Sell",        "🟥"
    else:
        return "Strong Sell", "🔴"


def check_downtrend(mas: dict) -> tuple:
    """
    Checks structural downtrend based on Moving Average positioning.
    Moving Average 200 is the key dividing line between structural
    breakdown and temporary pullback.
    """
    ma20_below  = mas["ma20"]["above"]  is False
    ma50_below  = mas["ma50"]["above"]  is False
    ma200_below = mas["ma200"]["above"] is False

    if ma20_below and ma50_below and ma200_below:
        return True, -30, \
            "price below MA20+MA50+MA200 -- structural downtrend 🔴"
    elif ma200_below:
        return True, -20, \
            "price below MA200 -- long term breakdown ⚠️"
    elif ma20_below and ma50_below and not ma200_below:
        return False, 0, \
            "short term pullback -- long term uptrend intact ✅"
    elif ma20_below and not ma50_below and not ma200_below:
        return False, 0, \
            "minor pullback -- no structural concern ✅"
    else:
        return False, 0, \
            "price above all MAs -- uptrend confirmed ✅"


def score_short_term(rsi: dict, stoch: dict,
                     roc: dict, bb: dict,
                     mas: dict) -> dict:
    """Short term score using RSI, Stochastic, Rate of Change, Bollinger Bands."""
    score   = BASELINE_SCORE
    signals = []

    # Relative Strength Index (max 25pts)
    if rsi["value"] < RSI_OVERSOLD:
        score += 25
    elif rsi["value"] < 45:
        score += 18
    elif rsi["value"] > RSI_OVERBOUGHT:
        score += 5
    elif rsi["value"] > 55:
        score += 8
    else:
        score += 12
    signals.append(
        f"RSI ({rsi['value']}) -- {rsi['signal']} {rsi['icon']}"
    )

    # Stochastic Oscillator (max 20pts)
    if stoch["value"] < STOCH_OVERSOLD:
        score += 20
    elif stoch["value"] < 35:
        score += 14
    elif stoch["value"] > STOCH_OVERBOUGHT:
        score += 4
    elif stoch["value"] > 65:
        score += 7
    else:
        score += 10
    signals.append(
        f"Stochastic ({stoch['value']}) -- "
        f"{stoch['signal']} {stoch['icon']}"
    )

    # Rate of Change (max 20pts)
    if roc["value"] > 5:
        score += 20
    elif roc["value"] > 0:
        score += 12
    elif roc["value"] < -5:
        score += 0
    else:
        score += 4
    signals.append(
        f"ROC ({roc['value']}%) -- {roc['signal']} {roc['icon']}"
    )

    # Bollinger Bands (max 15pts)
    if bb["pct"] < 20:
        score += 15
    elif bb["pct"] > 80:
        score += 3
    else:
        score += 8
    signals.append(
        f"Bollinger Bands ({bb['pct']}%) -- "
        f"{bb['signal']} {bb['icon']}"
    )

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_verdict(score)

    return {
        "score":   score,
        "verdict": verdict,
        "icon":    icon,
        "signals": signals,
    }


def score_mid_term(macd: dict, mas: dict,
                   atr: dict, vol: dict) -> dict:
    """Mid term score using MACD, Moving Averages, ATR, Volume."""
    score   = BASELINE_SCORE
    signals = []

    # Moving Average Convergence Divergence (max 30pts)
    if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
        score += 30
    elif macd["histogram"] < 0 and macd["macd"] < macd["signal"]:
        score += 0
    else:
        score += 12
    signals.append(
        f"MACD ({macd['histogram']}) -- "
        f"{macd['signal_label']} {macd['icon']}"
    )

    # 20-Day Moving Average (max 15pts)
    if mas["ma20"]["above"] is True:
        score += 15
    elif mas["ma20"]["above"] is False:
        if mas["ma200"]["above"] is True:
            score += 5
        else:
            score += 0
    signals.append(
        f"MA20 (${mas['ma20']['value']}) -- "
        f"{mas['ma20']['signal']} {mas['ma20']['icon']}"
    )

    # 50-Day Moving Average (max 20pts)
    if mas["ma50"]["above"] is True:
        score += 20
    elif mas["ma50"]["above"] is False:
        if mas["ma200"]["above"] is True:
            score += 7
        else:
            score += 0
    signals.append(
        f"MA50 (${mas['ma50']['value']}) -- "
        f"{mas['ma50']['signal']} {mas['ma50']['icon']}"
    )

    # Average True Range (max 10pts)
    if atr["pct"] < 1.5:
        score += 10
    elif atr["pct"] < 3:
        score += 6
    else:
        score += 2
    signals.append(
        f"ATR (${atr['value']} / {atr['pct']}%) -- "
        f"{atr['signal']} {atr['icon']}"
    )

    # Volume Trend (max 15pts)
    if vol["ratio"] > VOLUME_RISING:
        score += 15
    elif vol["ratio"] < VOLUME_FALLING:
        score += 0
    else:
        score += 7
    signals.append(
        f"Volume ({vol['ratio']}x avg) -- "
        f"{vol['signal']} {vol['icon']}"
    )

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_verdict(score)

    return {
        "score":   score,
        "verdict": verdict,
        "icon":    icon,
        "signals": signals,
    }


def score_long_term(mas: dict, golden: dict, vol: dict) -> dict:
    """Long term score using MA200, Golden Cross, Volume Trend."""
    score   = BASELINE_SCORE
    signals = []

    # 200-Day Moving Average (max 35pts)
    if mas["ma200"]["above"] is True:
        score += 35
    elif mas["ma200"]["above"] is False:
        score += 0
    signals.append(
        f"MA200 (${mas['ma200']['value']}) -- "
        f"{mas['ma200']['signal']} {mas['ma200']['icon']}"
    )

    # Golden Cross and Death Cross (max 40pts)
    if golden["value"] is not None:
        if golden["golden"] and "fresh" in golden["signal"]:
            score += 40
        elif golden["golden"]:
            score += 28
        elif not golden["golden"] and "fresh" in golden["signal"]:
            score += 0
        else:
            score += 5
    signals.append(
        f"Golden/Death Cross -- "
        f"{golden['signal']} {golden['icon']}"
    )

    # Volume Trend (max 15pts)
    if vol["ratio"] > VOLUME_RISING:
        score += 15
    elif vol["ratio"] < VOLUME_FALLING:
        score += 0
    else:
        score += 7
    signals.append(
        f"Volume ({vol['ratio']}x avg) -- "
        f"{vol['signal']} {vol['icon']}"
    )

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_verdict(score)

    return {
        "score":   score,
        "verdict": verdict,
        "icon":    icon,
        "signals": signals,
    }


def technical_analysis(company: str) -> dict:
    """
    Master function -- runs full technical analysis on a stock.
    Orchestrates data fetching, indicator computation, and scoring.
    """
    ticker = resolve_ticker(company)
    print(f"  Running technical analysis for: {ticker}...")

    price_data = fetch_price_data(ticker)
    if "error" in price_data:
        return {"error": price_data["error"]}

    hist_data = fetch_historical_data(ticker)
    if not hist_data["success"]:
        return {"error": hist_data["error"]}

    df            = hist_data["df"]
    closes        = hist_data["closes"]
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

    short = score_short_term(rsi, stoch, roc, bb, mas)
    mid   = score_mid_term(macd, mas, atr, vol)
    long  = score_long_term(mas, golden, vol)

    overall_score = round(
        (short["score"] * 0.30) +
        (mid["score"]   * 0.35) +
        (long["score"]  * 0.35)
    )
    overall_score         = max(0, min(100, overall_score))
    overall_verdict, icon = get_verdict(overall_score)

    result = {
        "ticker":           ticker,
        "company":          price_data["name"],
        "current_price":    current_price,
        "price_change":     price_data["price_change"],
        "price_change_pct": price_data["price_change_pct"],
        "short_term":       short,
        "mid_term":         mid,
        "long_term":        long,
        "overall": {
            "score":   overall_score,
            "verdict": overall_verdict,
            "icon":    icon,
        },
        "indicators": {
            "rsi":    rsi,
            "stoch":  stoch,
            "roc":    roc,
            "macd":   macd,
            "mas":    mas,
            "golden": golden,
            "bb":     bb,
            "atr":    atr,
            "volume": vol,
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return make_serializable(result)


# ============================================================
# SECTION 6 -- Stock Comparison
# ============================================================

def compare_stocks(companies: list) -> dict:
    """Compares 2-3 stocks side by side using technical analysis."""
    validation = validate_companies(companies)
    if not validation["valid"]:
        return {"error": validation["error"]}

    results = []
    errors  = []

    for company in validation["tickers"]:
        print(f"  Analysing {company}...")
        analysis = technical_analysis(company)
        if "error" in analysis:
            errors.append(f"{company}: {analysis['error']}")
        else:
            results.append(analysis)

    if not results:
        return {
            "error": "Could not retrieve data for any of the requested stocks.",
            "details": errors,
        }

    partial_failure = len(errors) > 0

    results.sort(
        key=lambda x: x["overall"]["score"],
        reverse=True
    )

    medals  = ["🥇", "🥈", "🥉"]
    ranking = []
    for i, r in enumerate(results):
        ranking.append({
            "rank":        i + 1,
            "medal":       medals[i],
            "ticker":      r["ticker"],
            "company":     r["company"],
            "score":       r["overall"]["score"],
            "verdict":     r["overall"]["verdict"],
            "icon":        r["overall"]["icon"],
            "short_score": r["short_term"]["score"],
            "mid_score":   r["mid_term"]["score"],
            "long_score":  r["long_term"]["score"],
        })

    comparison_table = {}
    for r in results:
        ticker = r["ticker"]
        comparison_table[ticker] = {
            "price":         r["current_price"],
            "change":        r["price_change"],
            "change_pct":    r["price_change_pct"],
            "short_term":    r["short_term"]["score"],
            "mid_term":      r["mid_term"]["score"],
            "long_term":     r["long_term"]["score"],
            "overall":       r["overall"]["score"],
            "verdict":       r["overall"]["verdict"],
            "icon":          r["overall"]["icon"],
            "rsi":           r["indicators"]["rsi"]["value"],
            "rsi_signal":    r["indicators"]["rsi"]["icon"],
            "stoch":         r["indicators"]["stoch"]["value"],
            "stoch_signal":  r["indicators"]["stoch"]["icon"],
            "roc":           r["indicators"]["roc"]["value"],
            "roc_signal":    r["indicators"]["roc"]["icon"],
            "macd":          r["indicators"]["macd"]["signal_label"],
            "macd_signal":   r["indicators"]["macd"]["icon"],
            "ma20":          r["indicators"]["mas"]["ma20"]["value"],
            "ma20_signal":   r["indicators"]["mas"]["ma20"]["icon"],
            "ma50":          r["indicators"]["mas"]["ma50"]["value"],
            "ma50_signal":   r["indicators"]["mas"]["ma50"]["icon"],
            "ma200":         r["indicators"]["mas"]["ma200"]["value"],
            "ma200_signal":  r["indicators"]["mas"]["ma200"]["icon"],
            "golden_cross":  r["indicators"]["golden"]["signal"],
            "golden_signal": r["indicators"]["golden"]["icon"],
            "bb_pct":        r["indicators"]["bb"]["pct"],
            "bb_signal":     r["indicators"]["bb"]["icon"],
            "atr":           r["indicators"]["atr"]["value"],
            "atr_signal":    r["indicators"]["atr"]["icon"],
            "volume":        r["indicators"]["volume"]["ratio"],
            "volume_signal": r["indicators"]["volume"]["icon"],
        }

    best_overall  = ranking[0]["ticker"]
    best_short    = max(results, key=lambda x: x["short_term"]["score"])["ticker"]
    best_mid      = max(results, key=lambda x: x["mid_term"]["score"])["ticker"]
    best_long     = max(results, key=lambda x: x["long_term"]["score"])["ticker"]
    lowest_risk   = min(results, key=lambda x: x["indicators"]["atr"]["pct"])["ticker"]

    return {
        "stocks_analysed":  len(results),
        "ranking":          ranking,
        "comparison_table": comparison_table,
        "best_picks": {
            "overall":     best_overall,
            "short_term":  best_short,
            "mid_term":    best_mid,
            "long_term":   best_long,
            "lowest_risk": lowest_risk,
        },
        "partial_failure": partial_failure,
        "errors":          errors if partial_failure else [],
        "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# SECTION 7 -- AI Tools & System Prompt
# ============================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_price_data",
            "description": (
                "Fetches real-time price and market data for a single stock. "
                "Use this when the user asks for current price, market cap, "
                "volume, 52 week high or low, or any other real-time market data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker_symbol": {
                        "type": "string",
                        "description": "The stock ticker symbol e.g. AAPL, NVDA, MSFT."
                    }
                },
                "required": ["ticker_symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "technical_analysis",
            "description": (
                "Runs a full technical analysis on a single stock using 9 indicators "
                "across 3 time horizons. Returns short term, mid term, long term and "
                "overall scores (0-100) with verdicts. "
                "Use this when the user asks: "
                "is a stock good to buy, "
                "should I invest in X, "
                "run analysis on X, "
                "show X, "
                "what is the technical outlook for X, "
                "or any question about a single stock performance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company name or ticker symbol e.g. Apple, NVDA, Microsoft"
                    }
                },
                "required": ["company"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": (
                "Compares 2 to 3 stocks side by side using technical analysis scores "
                "across all time horizons. Ranks stocks and identifies the best pick "
                "overall, per time horizon, and by lowest risk. "
                "Use this when the user mentions multiple companies or asks to compare, "
                "rank, or choose between stocks. Maximum 3 stocks only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "companies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2 to 3 company names or ticker symbols.",
                        "minItems": 2,
                        "maxItems": 3,
                    }
                },
                "required": ["companies"]
            }
        }
    },
]


SYSTEM_PROMPT = """
You are an expert stock market analyst assistant.

Your job is to analyze stock data and provide insights.

When tools return data, your response must be ONLY a
short 2-4 sentence summary covering:
- Overall technical picture
- Strongest and weakest time horizon
- Any conflicts between horizons
- Optimal entry context if relevant

For comparisons, your summary must cover:
- Who leads and why
- Best pick for different investor profiles
- Key risks to watch

Rules:
- Never reproduce the raw numbers in your summary
- Never include scores or prices in your summary
- Write in plain natural language
- Always end with: Disclaimer: Technical analysis is not financial advice.
- If no tool was called, answer the question conversationally
"""


# ============================================================
# SECTION 8 -- Tool Router
# ============================================================

TOOL_REGISTRY = {
    "fetch_price_data":   lambda args: fetch_price_data(
                              args["ticker_symbol"]
                          ),
    "technical_analysis": lambda args: technical_analysis(
                              args["company"]
                          ),
    "compare_stocks":     lambda args: compare_stocks(
                              args["companies"]
                          ),
}


def handle_tool_call(name: str, args: dict) -> str:
    """Routes a GPT tool call to the correct Python function."""
    try:
        if name not in TOOL_REGISTRY:
            return json.dumps({
                "error": (
                    f"Unknown tool '{name}'. "
                    f"Available tools: {list(TOOL_REGISTRY.keys())}"
                )
            })

        print(f"  Calling tool: {name}...")
        result = TOOL_REGISTRY[name](args)

        if not isinstance(result, dict):
            return json.dumps({
                "error": f"Tool '{name}' returned invalid result."
            })

        return json.dumps(result)

    except KeyError as e:
        return json.dumps({
            "error": f"Missing required argument for tool '{name}': {str(e)}"
        })
    except Exception as e:
        return json.dumps({
            "error": f"Tool '{name}' failed with error: {str(e)}"
        })


# ============================================================
# SECTION 9 -- Chatbot Class
# ============================================================

class StockChatbot:

    def __init__(self):
        self.client  = OpenAI()
        self.history = []
        self.turn    = 0
        self.model   = st.session_state.get(
            "selected_model", GPT_MODEL
        )
        print(f"Bot created with model: {self.model}")

    def chat(self, user_message: str) -> dict:
        """
        Sends user message to GPT, executes tools,
        and returns a structured dict for Streamlit to render.
        """
        self.turn += 1
        self.history.append({
            "role":    "user",
            "content": user_message
        })

        tool_name   = None
        tool_result = None

        max_iterations = 5
        iterations     = 0

        while iterations < max_iterations:
            iterations += 1

            try:
                print(f"Using model: {self.model}")
                response = self.client.chat.completions.create(
                    model       = self.model,
                    messages    = [
                        {
                            "role":    "system",
                            "content": SYSTEM_PROMPT
                        }
                    ] + self.history,
                    tools       = tools,
                    tool_choice = "auto",
                    temperature = TEMPERATURE,
                )
            except Exception as e:
                error_msg = str(e)
                if "rate limit" in error_msg.lower() or \
                   "too many requests" in error_msg.lower() or \
                   "429" in error_msg:
                    print("Rate limited -- waiting 30 seconds...")
                    time.sleep(30)
                    continue
                return {
                    "type":    "error",
                    "summary": f"API Error: {error_msg}"
                }

            message = response.choices[0].message

            if message.tool_calls:
                self.history.append(message)

                for tool_call in message.tool_calls:
                    args   = json.loads(tool_call.function.arguments)
                    name   = tool_call.function.name
                    result = handle_tool_call(name, args)

                    tool_name   = name
                    tool_result = json.loads(result)

                    self.history.append({
                        "role":         "tool",
                        "tool_call_id": tool_call.id,
                        "content":      result,
                    })

            else:
                summary = message.content
                self.history.append({
                    "role":    "assistant",
                    "content": summary
                })

                if tool_result is None:
                    return {
                        "type":    "text",
                        "summary": summary
                    }

                if "error" in tool_result:
                    return {
                        "type":    "error",
                        "summary": tool_result["error"]
                    }

                if tool_name == "technical_analysis":
                    return {
                        "type":    "single_stock",
                        "data":    tool_result,
                        "summary": summary
                    }
                elif tool_name == "compare_stocks":
                    return {
                        "type":    "comparison",
                        "data":    tool_result,
                        "summary": summary
                    }
                elif tool_name == "fetch_price_data":
                    return {
                        "type":    "price",
                        "data":    tool_result,
                        "summary": summary
                    }
                else:
                    return {
                        "type":    "text",
                        "summary": summary
                    }

        return {
            "type":    "error",
            "summary": "Analysis took too many steps. Please try again."
        }

    def reset(self):
        self.history = []
        self.turn    = 0
        print("Conversation reset.")

    def get_history_summary(self):
        if not self.history:
            print("No conversation history yet.")
            return
        print(f"Total turns   : {self.turn}")
        print(f"Total messages: {len(self.history)}")


# ============================================================
# SECTION 10 -- Streamlit UI
# ============================================================

def get_score_color(score: int) -> str:
    if score >= 75:   return "#00C853"
    elif score >= 60: return "#69F0AE"
    elif score >= 40: return "#FFD740"
    elif score >= 25: return "#FF6D00"
    else:             return "#FF1744"


def render_score_cards(data: dict):
    col1, col2, col3, col4 = st.columns(4)
    horizons = [
        (col1, "Short term",  data["short_term"]),
        (col2, "Mid term",    data["mid_term"]),
        (col3, "Long term",   data["long_term"]),
        (col4, "Overall",     data["overall"]),
    ]
    for col, label, h in horizons:
        color = get_score_color(h["score"])
        with col:
            st.markdown(f"""
            <div style="
                border: 1px solid {color};
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                background: rgba(0,0,0,0.2);">
                <div style="color:#aaa;font-size:13px;">
                    {label}
                </div>
                <div style="
                    color:{color};
                    font-size:42px;
                    font-weight:700;">
                    {h["score"]}
                </div>
                <div style="color:#aaa;font-size:11px;">
                    out of 100
                </div>
                <div style="margin-top:8px;">
                    {h["icon"]} {h["verdict"]}
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_price_line(data: dict):
    price  = data["current_price"]
    change = data["price_change"]
    pct    = data["price_change_pct"]
    arrow  = "▲" if change >= 0 else "▼"
    color  = "#00C853" if change >= 0 else "#FF1744"
    st.markdown(f"""
    <div style="font-size:16px;margin:10px 0;">
        <b>Price:</b> ${price}
        <span style="color:{color};">
            {arrow} {abs(change)} ({abs(pct)}%)
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_signals(data: dict):
    with st.expander("📊 View Full Indicator Breakdown"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Short term signals**")
            for s in data["short_term"]["signals"]:
                st.markdown(f"- {s}")
        with col2:
            st.markdown("**Mid term signals**")
            for s in data["mid_term"]["signals"]:
                st.markdown(f"- {s}")
        with col3:
            st.markdown("**Long term signals**")
            for s in data["long_term"]["signals"]:
                st.markdown(f"- {s}")


def render_single_analysis(data: dict, summary: str):
    st.markdown("---")
    st.subheader(f"{data['ticker']} -- {data['company']}")
    render_price_line(data)
    st.markdown("")
    render_score_cards(data)
    st.markdown("")
    render_signals(data)
    st.markdown("")
    st.info(summary)


def render_price_only(data: dict, summary: str):
    st.markdown("---")
    st.subheader(f"{data['ticker']} -- {data['name']}")
    render_price_line(data)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open",      f"${data['open']}")
    with col2:
        st.metric("Day High",  f"${data['day_high']}")
    with col3:
        st.metric("Day Low",   f"${data['day_low']}")
    with col4:
        st.metric("Market Cap",
                  f"${data['market_cap']:,.0f}"
                  if data['market_cap'] else "N/A")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Volume",
                  f"{data['volume']:,.0f}"
                  if data['volume'] else "N/A")
    with col6:
        st.metric("P/E Ratio", data['pe_ratio'] or "N/A")
    with col7:
        st.metric("52W High",
                  f"${data['52w_high']}"
                  if data['52w_high'] else "N/A")
    with col8:
        st.metric("52W Low",
                  f"${data['52w_low']}"
                  if data['52w_low'] else "N/A")

    st.markdown("")
    st.info(summary)


def render_comparison(data: dict, summary: str):
    st.markdown("---")
    st.subheader("Stock Comparison")

    st.markdown("#### Ranking")
    for r in data["ranking"]:
        color = get_score_color(r["score"])
        st.markdown(f"""
        <div style="
            border: 1px solid {color};
            border-radius: 8px;
            padding: 12px 20px;
            margin: 6px 0;
            display: flex;
            align-items: center;
            gap: 16px;">
            <span style="font-size:24px;">{r["medal"]}</span>
            <span style="font-size:18px;font-weight:700;">
                {r["ticker"]}
            </span>
            <span style="color:#aaa;">
                {r["company"]}
            </span>
            <span style="
                margin-left:auto;
                color:{color};
                font-weight:700;">
                {r["score"]}/100 -- {r["verdict"]} {r["icon"]}
            </span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    st.markdown("#### Comparison Table")

    table   = data["comparison_table"]
    tickers = list(table.keys())

    rows = {
        "Price":         [f"${table[t]['price']}"           for t in tickers],
        "Change":        [f"{table[t]['change_pct']}%"      for t in tickers],
        "Short term":    [f"{table[t]['short_term']}/100"   for t in tickers],
        "Mid term":      [f"{table[t]['mid_term']}/100"     for t in tickers],
        "Long term":     [f"{table[t]['long_term']}/100"    for t in tickers],
        "Overall":       [f"{table[t]['overall']}/100"      for t in tickers],
        "RSI":           [f"{table[t]['rsi']} {table[t]['rsi_signal']}"         for t in tickers],
        "Stochastic":    [f"{table[t]['stoch']} {table[t]['stoch_signal']}"     for t in tickers],
        "ROC":           [f"{table[t]['roc']}% {table[t]['roc_signal']}"        for t in tickers],
        "MACD":          [f"{table[t]['macd']} {table[t]['macd_signal']}"       for t in tickers],
        "MA20":          [f"${table[t]['ma20']} {table[t]['ma20_signal']}"      for t in tickers],
        "MA50":          [f"${table[t]['ma50']} {table[t]['ma50_signal']}"      for t in tickers],
        "MA200":         [f"${table[t]['ma200']} {table[t]['ma200_signal']}"    for t in tickers],
        "Golden Cross":  [f"{table[t]['golden_cross']} {table[t]['golden_signal']}" for t in tickers],
        "Bollinger":     [f"{table[t]['bb_pct']}% {table[t]['bb_signal']}"     for t in tickers],
        "ATR":           [f"${table[t]['atr']} {table[t]['atr_signal']}"        for t in tickers],
        "Volume":        [f"{table[t]['volume']}x {table[t]['volume_signal']}"  for t in tickers],
    }

    df = pd.DataFrame(rows, index=tickers).T
    st.dataframe(df, use_container_width=True)

    st.markdown("")
    st.markdown("#### Best Picks")
    bp = data["best_picks"]

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Best Overall",    bp["overall"])
    with col2:
        st.metric("Best Short term", bp["short_term"])
    with col3:
        st.metric("Best Mid term",   bp["mid_term"])
    with col4:
        st.metric("Best Long term",  bp["long_term"])
    with col5:
        st.metric("Lowest Risk",     bp["lowest_risk"])

    st.markdown("")
    st.info(summary)


# ============================================================
# MAIN STREAMLIT APP
# ============================================================

def main():

    st.set_page_config(
        page_title = "Stock Analysis Chatbot",
        page_icon  = "📈",
        layout     = "wide",
    )

    # Session state initialization
    if "bot" not in st.session_state:
        st.session_state.bot            = None
        st.session_state.messages       = []
        st.session_state.last_result    = None
        st.session_state.selected_model = "gpt-4.1-mini"
        st.session_state.current_model  = None
        st.session_state.api_key        = None

    # Sidebar
    with st.sidebar:
        st.title("📈 Stock Chatbot")
        st.markdown("---")

        # API Key input
        st.markdown("#### OpenAI API Key")
        api_key = st.text_input(
            label       = "Enter your API key",
            type        = "password",
            placeholder = "sk-...",
            help        = "Your key is never stored or shared."
        )

        if api_key:
            st.session_state.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
            st.success("API key set ✅")
        else:
            st.session_state.api_key = None
            st.warning("Please enter your API key to continue.")

        st.markdown("---")

        # Model selection
        st.markdown("#### Model Selection")
        model_options = {
            "GPT-4o (Best quality)":      "gpt-4o",
            "GPT-4.1 (Latest)":           "gpt-4.1",
            "GPT-4.1-mini (Recommended)": "gpt-4.1-mini",
            "GPT-4o-mini (Fast & cheap)": "gpt-4o-mini",
            "GPT-3.5-turbo (Basic)":      "gpt-3.5-turbo",
        }
        selected_model = st.selectbox(
            label   = "Choose AI model",
            options = list(model_options.keys()),
            index   = 2,
            help    = (
                "Higher quality models give better summaries "
                "but have lower rate limits. "
                "Use mini models for testing."
            )
        )
        st.session_state.selected_model = model_options[selected_model]

        if "mini" in st.session_state.selected_model or \
           "turbo" in st.session_state.selected_model:
            st.success("✅ High rate limits -- good for testing")
        else:
            st.warning("⚠️ Lower rate limits -- use sparingly")

        st.markdown("---")

        # Example queries
        st.markdown("#### Example Queries")
        examples = [
            "Give me real time data for Apple",
            "Is NVDA a good stock to buy?",
            "Run technical analysis on Tesla",
            "Show full analysis for AMD",
            "Compare NVDA, AMD and Intel",
            "Which of Apple or Microsoft is a better buy?",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.pending_input = ex

        st.markdown("---")

        if st.button("🔄 Reset Conversation",
                     use_container_width=True):
            st.session_state.bot         = None
            st.session_state.messages    = []
            st.session_state.last_result = None
            st.rerun()

        st.markdown("---")
        st.caption(
            "Powered by GPT + Yahoo Finance\n\n"
            "Technical analysis is not financial advice."
        )

    # Bot creation and model management
    if st.session_state.get("api_key") and \
       st.session_state.bot is None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        st.session_state.bot = StockChatbot()
        st.session_state.current_model = st.session_state.selected_model

    if st.session_state.get("api_key") and \
       st.session_state.bot is not None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        if st.session_state.selected_model != \
           st.session_state.current_model:
            st.session_state.bot = StockChatbot()
            st.session_state.current_model  = st.session_state.selected_model
            st.session_state.messages       = []
            st.session_state.last_result    = None

    # Main area
    st.title("📈 Real-Time Stock Analysis Chatbot")
    st.caption(
        "Ask about any stock -- get real-time data and "
        "technical analysis across 3 time horizons."
    )
    st.markdown("---")

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg.get("content", "")
            if msg["role"] == "assistant" and \
               isinstance(content, dict):
                rtype = content.get("type", "text")
                if rtype == "single_stock":
                    ticker = content["data"]["ticker"]
                    st.markdown(
                        f"Analysis complete for **{ticker}**. "
                        f"See results below."
                    )
                elif rtype == "comparison":
                    tickers = list(
                        content["data"]["comparison_table"].keys()
                    )
                    st.markdown(
                        f"Comparison complete for "
                        f"**{', '.join(tickers)}**. "
                        f"See results below."
                    )
                elif rtype == "price":
                    ticker = content["data"]["ticker"]
                    st.markdown(
                        f"Price data fetched for **{ticker}**. "
                        f"See results below."
                    )
                else:
                    st.markdown(content.get("summary", ""))
            else:
                st.markdown(content)

    # Render last analysis result
    if st.session_state.last_result:
        result = st.session_state.last_result
        rtype  = result.get("type")

        if rtype == "single_stock":
            render_single_analysis(
                result["data"],
                result["summary"]
            )
        elif rtype == "comparison":
            render_comparison(
                result["data"],
                result["summary"]
            )
        elif rtype == "price":
            render_price_only(
                result["data"],
                result["summary"]
            )

    # Process input function
    def process_input(user_input: str):
        st.session_state.messages.append({
            "role":    "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Analysing..."):
                result = st.session_state.bot.chat(user_input)

            st.session_state.last_result = result

            rtype = result.get("type", "text")
            if rtype == "single_stock":
                ticker = result["data"]["ticker"]
                st.markdown(
                    f"Analysis complete for **{ticker}**. "
                    f"See results below."
                )
            elif rtype == "comparison":
                tickers = list(
                    result["data"]["comparison_table"].keys()
                )
                st.markdown(
                    f"Comparison complete for "
                    f"**{', '.join(tickers)}**. "
                    f"See results below."
                )
            elif rtype == "price":
                ticker = result["data"]["ticker"]
                st.markdown(
                    f"Price data fetched for **{ticker}**. "
                    f"See results below."
                )
            else:
                st.markdown(result.get("summary", ""))

            st.session_state.messages.append({
                "role":    "assistant",
                "content": result
            })

        st.rerun()

    # Handle sidebar button clicks
    if "pending_input" in st.session_state:
        user_input = st.session_state.pending_input
        del st.session_state.pending_input
        if st.session_state.get("api_key"):
            process_input(user_input)
        else:
            st.warning("Please enter your API key first.")

    # Chat input
    if not st.session_state.get("api_key"):
        st.info(
            "👈 Please enter your OpenAI API key "
            "in the sidebar to get started."
        )
    else:
        user_input = st.chat_input("Ask about any stock...")
        if user_input:
            process_input(user_input)


if __name__ == "__main__":
    main()
