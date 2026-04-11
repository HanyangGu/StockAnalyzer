# ============================================================
# technical_scorer.py -- Technical Analysis Scoring Engine
# ============================================================
# Scores all 9 technical indicators across 3 time horizons:
#   Short term  : RSI + Stochastic + ROC + Bollinger Bands
#   Mid term    : MACD + MA20 + MA50 + ATR + Volume
#   Long term   : MA200 + Golden Cross + Volume Trend
#   Overall     : Weighted average (30% / 35% / 35%)
# ============================================================

from core.config import (
    BASELINE_SCORE,
    RSI_OVERSOLD, RSI_OVERBOUGHT,
    STOCH_OVERSOLD, STOCH_OVERBOUGHT,
    VOLUME_RISING, VOLUME_FALLING,
)


# ============================================================
# Utility Functions
# ============================================================

def get_technical_verdict(score: int) -> tuple:
    """
    Converts a numerical score into a momentum verdict label and emoji.
    Labels describe what price is doing, not a direct buy/sell instruction.
    Returns: (verdict_label, emoji)
    """
    if score >= 75:
        return "Strong Uptrend",   "🟢"
    elif score >= 60:
        return "Uptrend",          "🟩"
    elif score >= 40:
        return "Neutral",          "⬜"
    elif score >= 25:
        return "Downtrend",        "🟥"
    else:
        return "Strong Downtrend", "🔴"


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

    # Bollinger Bands (max 15pts) + BB Width squeeze detection
    if bb["pct"] < 20:
        score += 15
    elif bb["pct"] > 80:
        score += 3
    else:
        score += 8

    # BB Width squeeze: narrow bands precede explosive moves (Gemini suggestion)
    width_ratio = bb.get("width_ratio", 1.0)
    bb_signal_str = f"Bollinger Bands ({bb['pct']}%) -- {bb['signal']} {bb['icon']}"
    if width_ratio < 0.75:
        bb_signal_str += (
            f" | BB squeeze (width {bb.get('width_pct', 0):.1f}% of price, "
            f"{int(width_ratio*100)}% of 20d avg) -- breakout approaching ⚡"
        )
    elif width_ratio > 1.25:
        bb_signal_str += (
            f" | BB expansion (width {int(width_ratio*100)}% of 20d avg) -- volatility elevated ⚠️"
        )
    signals.append(bb_signal_str)

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_technical_verdict(score)

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
    MACD (25pts) + MA20 (15pts) + MA50 (25pts)
    + Volume (15pts) + Downtrend penalty
    ATR removed from scoring (volatility != direction signal).
    ATR retained as informational signal only.
    """
    score   = BASELINE_SCORE
    signals = []

    # Moving Average Convergence Divergence (max 25pts)
    if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
        score += 25
    elif macd["histogram"] < 0 and macd["macd"] < macd["signal"]:
        score += 0
    else:
        score += 10
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

    # 50-Day Moving Average (max 25pts)
    if mas["ma50"]["above"] is True:
        score += 25
    elif mas["ma50"]["above"] is False:
        # Partial credit if above MA200 (temporary pullback)
        if mas["ma200"]["above"] is True:
            score += 8
        else:
            score += 0
    signals.append(
        f"MA50 (${mas['ma50']['value']}) -- "
        f"{mas['ma50']['signal']} {mas['ma50']['icon']}"
    )

    # ATR: informational only -- volatility is not a directional signal.
    # High ATR stocks (like NVDA) would be systematically penalised without justification.
    # ATR risk is captured in the Risk Matrix (Volatility entry via Beta).
    signals.append(
        f"ATR (${atr['value']} / {atr['pct']}%) -- "
        f"{atr['signal']} {atr['icon']} (informational)"
    )

    # Volume Trend (max 15pts) + divergence adjustment
    divergence = vol.get("divergence")
    if divergence == "low_volume_rally":
        # Price rising on weak volume -- bullish but fragile
        score += 5
    elif divergence == "high_volume_selloff":
        # Price falling on heavy volume -- distribution, extra penalty
        score += 0
    elif vol["ratio"] > VOLUME_RISING:
        score += 15
    elif vol["ratio"] < VOLUME_FALLING:
        score += 0
    else:
        score += 7

    vol_signal_str = f"Volume ({vol['ratio']}x avg) -- {vol['signal']} {vol['icon']}"
    if divergence == "low_volume_rally":
        vol_signal_str += " ⚠️ low-volume rally -- watch for reversal"
    elif divergence == "high_volume_selloff":
        vol_signal_str += " ⚠️ distribution detected"
    signals.append(vol_signal_str)

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_technical_verdict(score)

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
    + MA slope strength (15pts) + Downtrend penalty

    Volume replaced by MA slope: long-term conviction is better measured
    by whether the MA200 itself is rising (trend healthy) vs flat/falling.
    Short-term 5-day volume is noise at a long-term horizon.
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

    # MA slope strength (max 15pts) -- replaces short-term 5-day volume.
    # Long-term trend quality is measured by whether MA200 is itself rising.
    # A rising MA200 = structural bull trend. Flat/falling = weakening trend.
    ma200_val  = mas["ma200"].get("value")
    ma200_above = mas["ma200"].get("above")
    golden_val = golden.get("value")   # MA50 current value

    # Derive slope signal from golden cross data (MA50 vs MA200 gap)
    if golden_val and ma200_val and ma200_above:
        gap_pct = round((golden_val - ma200_val) / ma200_val * 100, 2)
        if gap_pct > 10:
            score += 15
            ma_slope_sig = f"MA50 {gap_pct:.1f}% above MA200 -- strong long-term trend ✅"
        elif gap_pct > 3:
            score += 10
            ma_slope_sig = f"MA50 {gap_pct:.1f}% above MA200 -- healthy trend ✅"
        elif gap_pct > 0:
            score += 5
            ma_slope_sig = f"MA50 {gap_pct:.1f}% above MA200 -- weak trend ⚠️"
        else:
            score += 0
            ma_slope_sig = f"MA50 below MA200 by {abs(gap_pct):.1f}% -- long-term downtrend ⚠️"
    elif not ma200_above:
        score += 0
        ma_slope_sig = "Price below MA200 -- structural downtrend ⚠️"
    else:
        score += 7
        ma_slope_sig = "MA slope: insufficient data -- neutral ➡️"
    signals.append(ma_slope_sig)

    # Structural downtrend penalty
    is_downtrend, penalty, dt_signal = check_downtrend(mas)
    if penalty != 0:
        score += penalty
        signals.append(f"Trend structure -- {dt_signal}")

    score         = max(0, min(100, score))
    verdict, icon = get_technical_verdict(score)

    return {
        "score":   score,
        "verdict": verdict,
        "icon":    icon,
        "signals": signals,
    }


# ============================================================
# Technical Overall Score
# ============================================================

def score_technical_overall(short: dict, mid: dict,
                             long: dict) -> dict:
    """
    Combines short, mid, long term scores into one technical score.
    Weights: Short 30% | Mid 35% | Long 35%
    """
    overall_score = round(
        (short["score"] * 0.30) +
        (mid["score"]   * 0.35) +
        (long["score"]  * 0.35)
    )
    overall_score         = max(0, min(100, overall_score))
    overall_verdict, icon = get_technical_verdict(overall_score)

    return {
        "score":   overall_score,
        "verdict": overall_verdict,
        "icon":    icon,
    }
