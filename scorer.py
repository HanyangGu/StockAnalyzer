# ============================================================
# scorer.py -- Scoring Engine & Technical Analysis
# ============================================================
# Scores all 9 indicators across 3 time horizons:
#   Short term  : RSI + Stochastic + ROC + Bollinger Bands
#   Mid term    : MACD + MA20 + MA50 + ATR + Volume
#   Long term   : MA200 + Golden Cross + Volume Trend
#   Overall     : Weighted average (30% / 35% / 35%)
# ============================================================

import time
import numpy as np
from datetime import datetime

from fundamentals import fundamental_analysis
from config import (
    BASELINE_SCORE,
    RSI_OVERSOLD, RSI_OVERBOUGHT,
    STOCH_OVERSOLD, STOCH_OVERBOUGHT,
    VOLUME_RISING, VOLUME_FALLING,
)
from data import (
    fetch_price_data,
    fetch_price_data_historical,
    fetch_historical_data,
    resolve_ticker,
)
from indicators import (
    compute_rsi,
    compute_stochastic,
    compute_roc,
    compute_macd,
    compute_moving_averages,
    compute_golden_cross,
    compute_bollinger_bands,
    compute_atr,
    compute_volume_trend,
)


# ============================================================
# Utility Functions
# ============================================================

def make_serializable(obj):
    """
    Recursively converts numpy types to native Python types
    so the result can be safely serialized to JSON.
    """
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
    """
    Converts a numerical score into a momentum verdict label and emoji.
    Labels describe what price is doing, not a direct buy/sell instruction.
    Returns: (verdict_label, emoji)
    """
    if score >= 75:
        return "Strong Uptrend",  "🟢"
    elif score >= 60:
        return "Uptrend",         "🟩"
    elif score >= 40:
        return "Neutral",         "⬜"
    elif score >= 25:
        return "Downtrend",       "🟥"
    else:
        return "Strong Downtrend","🔴"


def check_downtrend(mas: dict) -> tuple:
    """
    Checks structural downtrend based on Moving Average positioning.
    MA200 is the key dividing line between structural breakdown
    and temporary pullback.

    Returns: (is_downtrend, penalty, signal_label)
    """
    ma20_below  = mas["ma20"]["above"]  is False
    ma50_below  = mas["ma50"]["above"]  is False
    ma200_below = mas["ma200"]["above"] is False

    # All 3 MAs below -- severe structural downtrend
    if ma20_below and ma50_below and ma200_below:
        return True, -30, \
            "price below MA20+MA50+MA200 -- structural downtrend 🔴"

    # Below MA200 -- long term structural breakdown
    elif ma200_below:
        return True, -20, \
            "price below MA200 -- long term breakdown ⚠️"

    # Below MA20+MA50 but ABOVE MA200 -- temporary pullback
    elif ma20_below and ma50_below and not ma200_below:
        return False, 0, \
            "short term pullback -- long term uptrend intact ✅"

    # Below MA20 only -- minor dip
    elif ma20_below and not ma50_below and not ma200_below:
        return False, 0, \
            "minor pullback -- no structural concern ✅"

    # All above -- confirmed uptrend
    else:
        return False, 0, \
            "price above all MAs -- uptrend confirmed ✅"


# ============================================================
# Time Horizon Scorers
# ============================================================

def score_short_term(rsi: dict, stoch: dict,
                     roc: dict, bb: dict,
                     mas: dict) -> dict:
    """
    Short term score (0-100)
    RSI (25pts) + Stochastic (20pts) + ROC (20pts)
    + Bollinger Bands (15pts) + Downtrend penalty
    """
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
    """
    Mid term score (0-100)
    MACD (30pts) + MA20 (15pts) + MA50 (20pts)
    + ATR (10pts) + Volume (15pts) + Downtrend penalty
    """
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
        # Partial credit if above MA200 (temporary pullback)
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
        # Partial credit if above MA200 (temporary pullback)
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
    """
    Long term score (0-100)
    MA200 (35pts) + Golden/Death Cross (40pts)
    + Volume Trend (15pts) + Downtrend penalty
    """
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


# ============================================================
# Master Orchestrator
# ============================================================

def technical_analysis(company: str,
                        backtest_date: str = None) -> dict:
    """
    Master function -- runs full technical analysis on a stock.

    Steps:
      1. Resolve ticker symbol
      2. Fetch price data (live or historical)
      3. Fetch historical OHLCV data
      4. Compute all 9 indicators
      5. Score across 3 time horizons
      6. Calculate weighted overall score
      7. Return complete serializable result
    """
    # Step 1: Resolve ticker
    ticker = resolve_ticker(company)
    print(f"  Running technical analysis for: {ticker}...")

    # Step 2: Fetch price data
    if backtest_date:
        price_data = fetch_price_data_historical(
            ticker, backtest_date
        )
    else:
        price_data = fetch_price_data(ticker)

    if "error" in price_data:
        if "too many requests" in \
            str(price_data["error"]).lower() or \
           "rate limit" in \
            str(price_data["error"]).lower():
            return {
                "error": (
                    "Yahoo Finance is temporarily rate limited. "
                    "Please wait 30 seconds and try again."
                )
            }
        return {"error": price_data["error"]}

    # Step 3: Fetch historical OHLCV data
    time.sleep(1)
    hist_data = fetch_historical_data(
        ticker,
        end_date=backtest_date
    )
    if not hist_data["success"]:
        if "too many requests" in \
            str(hist_data["error"]).lower() or \
           "rate limit" in \
            str(hist_data["error"]).lower():
            return {
                "error": (
                    "Yahoo Finance is temporarily rate limited. "
                    "Please wait 30 seconds and try again."
                )
            }
        return {"error": hist_data["error"]}

    df            = hist_data["df"]
    closes        = hist_data["closes"]
    current_price = price_data["current_price"]

    # Step 4: Compute all 9 indicators
    rsi    = compute_rsi(closes)
    stoch  = compute_stochastic(df)
    roc    = compute_roc(closes)
    macd   = compute_macd(closes)
    mas    = compute_moving_averages(closes, current_price)
    golden = compute_golden_cross(closes)
    bb     = compute_bollinger_bands(closes, current_price)
    atr    = compute_atr(df)
    vol    = compute_volume_trend(df)

    # Step 5: Score each time horizon
    short = score_short_term(rsi, stoch, roc, bb, mas)
    mid   = score_mid_term(macd, mas, atr, vol)
    long  = score_long_term(mas, golden, vol)

    # Step 6: Calculate overall score (weighted average)
    # Short: 30% | Mid: 35% | Long: 35%
    overall_score = round(
        (short["score"] * 0.30) +
        (mid["score"]   * 0.35) +
        (long["score"]  * 0.35)
    )
    overall_score         = max(0, min(100, overall_score))
    overall_verdict, icon = get_verdict(overall_score)

    # Step 7: Run fundamental analysis (non-blocking -- errors are soft)
    fund_result = fundamental_analysis(ticker)
    if "error" in fund_result:
        fundamental = {
            "score":   None,
            "verdict": "Data unavailable",
            "icon":    "➡️",
            "signals": [],
        }
        fund_details = {}
        print(f"  Fundamental analysis skipped: {fund_result['error']}")
    else:
        fundamental  = fund_result["fundamental"]
        fund_details = {
            "valuation":     fund_result["valuation"],
            "profitability": fund_result["profitability"],
            "growth":        fund_result["growth"],
            "health":        fund_result["health"],
            "analyst":       fund_result["analyst"],
        }

    # Step 8: Build and return result
    result = {
        "ticker":           ticker,
        "company":          price_data["name"],
        "current_price":    current_price,
        "price_change":     price_data["price_change"],
        "price_change_pct": price_data["price_change_pct"],
        "backtest_date":    backtest_date or "live",
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
        "fundamental":      fundamental,
        "fund_details":     fund_details,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return make_serializable(result)
