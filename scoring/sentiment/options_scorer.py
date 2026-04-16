# ============================================================
# scoring/sentiment/options_scorer.py -- Options Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call any external API or yfinance.
# Receives the standardised dict from analyzers/sentiment/options.py
# and produces a 0-100 options sentiment score.
#
# No LLM calls in this file. All computation is deterministic.
#
# Scoring breakdown:
#   PCR Volume    : 0-35 pts  (put/call volume ratio)
#   PCR OI        : 0-25 pts  (put/call open interest ratio)
#   Raw total     : 0-60 pts → scaled to 0-100
#   IV Multiplier : ×0.70 to ×1.00 (dampens signal under high volatility)
#
# Informational signals (not scored):
#   Max Pain      : strike price where option sellers face minimum payout
#   Call Wall     : strongest resistance above current price
#   Put Wall      : strongest support below current price
#
# Output contract:
# {
#   "score":         int    0-100
#   "direction":     str    "bullish" | "neutral" | "bearish"
#   "pcr_volume":    float | None
#   "pcr_oi":        float | None
#   "avg_iv":        float | None  (as %, e.g. 45.2 means 45.2% IV)
#   "iv_multiplier": float
#   "expiry":        str | None
#   "days_to_exp":   int | None
#   "max_pain":      float | None
#   "max_pain_dist": float | None  (% distance from current price)
#   "call_wall":     float | None
#   "put_wall":      float | None
#   "signals":       list[str]
# }
# ============================================================

import pandas as pd

from core.weights import (
    OPTIONS_IV_HIGH, OPTIONS_IV_MODERATE,
    OPTIONS_IV_MULT_HIGH, OPTIONS_IV_MULT_MODERATE, OPTIONS_IV_MULT_LOW,
    OPTIONS_PCR_VOL_THRESHOLDS, OPTIONS_PCR_OI_THRESHOLDS,
)


# ============================================================
# Constants
# ============================================================

MIN_VOLUME       = 100

IV_HIGH          = OPTIONS_IV_HIGH
IV_MODERATE      = OPTIONS_IV_MODERATE
IV_MULT_HIGH     = OPTIONS_IV_MULT_HIGH
IV_MULT_MODERATE = OPTIONS_IV_MULT_MODERATE
IV_MULT_LOW      = OPTIONS_IV_MULT_LOW

PCR_VOL_THRESHOLDS = OPTIONS_PCR_VOL_THRESHOLDS
PCR_OI_THRESHOLDS  = OPTIONS_PCR_OI_THRESHOLDS


# ============================================================
# Score components (pure functions)
# ============================================================

def _score_pcr_volume(calls: pd.DataFrame,
                       puts: pd.DataFrame) -> tuple:
    """
    Put/Call volume ratio score (0-35 pts).
    Baseline PCR = 0.7 (equity market historical average).
    Returns (score, pcr_value, signal_str).
    """
    call_vol = calls["volume"].fillna(0).sum()
    put_vol  = puts["volume"].fillna(0).sum()
    total    = call_vol + put_vol

    if total < MIN_VOLUME:
        return 20, None, "PCR volume: insufficient data -- neutral ➡️"

    pcr = round(put_vol / call_vol, 3) if call_vol > 0 else 99

    score = 0
    for threshold, pts in PCR_VOL_THRESHOLDS:
        if pcr <= threshold:
            score = pts
            break

    if pcr <= 0.40:
        label, icon = f"very bullish (PCR {pcr}, heavy call buying)", "✅"
    elif pcr <= 0.55:
        label, icon = f"bullish (PCR {pcr}, calls dominating)", "✅"
    elif pcr <= 0.70:
        label, icon = f"neutral/mildly bullish (PCR {pcr}, near baseline)", "➡️"
    elif pcr <= 0.90:
        label, icon = f"mildly bearish (PCR {pcr}, above baseline)", "⚠️"
    elif pcr <= 1.10:
        label, icon = f"bearish (PCR {pcr}, puts dominating)", "⚠️"
    else:
        label, icon = f"very bearish (PCR {pcr}, heavy put buying)", "⚠️"

    return score, pcr, f"PCR volume: {label} {icon}"


def _score_pcr_oi(calls: pd.DataFrame,
                   puts: pd.DataFrame) -> tuple:
    """
    Put/Call open interest ratio score (0-25 pts).
    OI reflects institutional longer-term positioning.
    Returns (score, oi_pcr, signal_str).
    """
    call_oi = calls["openInterest"].fillna(0).sum()
    put_oi  = puts["openInterest"].fillna(0).sum()
    total   = call_oi + put_oi

    if total < MIN_VOLUME:
        return 12, None, "PCR open interest: insufficient data -- neutral ➡️"

    oi_pcr = round(put_oi / call_oi, 3) if call_oi > 0 else 99

    score = 0
    for threshold, pts in PCR_OI_THRESHOLDS:
        if oi_pcr <= threshold:
            score = pts
            break

    if oi_pcr <= 0.50:
        label, icon = f"very bullish positioning (OI PCR {oi_pcr})", "✅"
    elif oi_pcr <= 0.70:
        label, icon = f"bullish positioning (OI PCR {oi_pcr})", "✅"
    elif oi_pcr <= 0.90:
        label, icon = f"neutral positioning (OI PCR {oi_pcr})", "➡️"
    elif oi_pcr <= 1.10:
        label, icon = f"mildly bearish positioning (OI PCR {oi_pcr})", "⚠️"
    else:
        label, icon = f"bearish positioning (OI PCR {oi_pcr})", "⚠️"

    return score, oi_pcr, f"PCR open interest: {label} {icon}"


def _get_iv_multiplier(avg_iv: float) -> tuple:
    """
    IV-based confidence multiplier and signal string.
    High IV → uncertainty → dampens the directional signal.
    """
    if avg_iv >= IV_HIGH:
        return (
            IV_MULT_HIGH,
            f"High IV ({round(avg_iv*100,1)}%) -- elevated uncertainty, "
            f"signal confidence reduced ⚠️"
        )
    elif avg_iv >= IV_MODERATE:
        return (
            IV_MULT_MODERATE,
            f"Moderate IV ({round(avg_iv*100,1)}%) -- some uncertainty ➡️"
        )
    else:
        return (
            IV_MULT_LOW,
            f"Low IV ({round(avg_iv*100,1)}%) -- calm market, "
            f"signal confidence intact ✅"
        )


def _calc_max_pain(calls_all: pd.DataFrame,
                   puts_all: pd.DataFrame,
                   current_price: float | None) -> dict:
    """
    Max Pain: strike price where option sellers face minimum total payout.
    Informational only -- not included in score.

    For each candidate strike, computes total dollar pain to option holders
    if price expires at that strike. Min pain for sellers = Max Pain strike.
    """
    try:
        calls_oi = calls_all[["strike", "openInterest"]].copy()
        puts_oi  = puts_all[["strike",  "openInterest"]].copy()
        calls_oi.columns = ["strike", "call_oi"]
        puts_oi.columns  = ["strike", "put_oi"]

        merged  = pd.merge(calls_oi, puts_oi, on="strike", how="outer").fillna(0)
        strikes = sorted(merged["strike"].unique())

        if len(strikes) < 3:
            return {"max_pain_strike": None, "distance_pct": None, "signal": "Max Pain: insufficient data ➡️"}

        pain_values = []
        for s in strikes:
            call_pain = merged[merged["strike"] > s].apply(
                lambda r: (r["strike"] - s) * r["call_oi"], axis=1
            ).sum()
            put_pain = merged[merged["strike"] < s].apply(
                lambda r: (s - r["strike"]) * r["put_oi"], axis=1
            ).sum()
            pain_values.append(call_pain + put_pain)

        min_idx         = pain_values.index(min(pain_values))
        max_pain_strike = round(float(strikes[min_idx]), 2)

        if current_price and current_price > 0:
            distance_pct = round((max_pain_strike - current_price) / current_price * 100, 2)
            if distance_pct > 3:
                signal = f"Max Pain ${max_pain_strike} -- price {distance_pct}% below, bullish pull ✅"
            elif distance_pct < -3:
                signal = f"Max Pain ${max_pain_strike} -- price {abs(distance_pct)}% above, bearish pull ⚠️"
            else:
                signal = f"Max Pain ${max_pain_strike} -- price near max pain, neutral ➡️"
        else:
            distance_pct = None
            signal       = f"Max Pain ${max_pain_strike} ➡️"

        return {"max_pain_strike": max_pain_strike, "distance_pct": distance_pct, "signal": signal}

    except Exception as e:
        print(f"  Max Pain calculation error: {e}")
        return {"max_pain_strike": None, "distance_pct": None, "signal": "Max Pain: calculation error ➡️"}


def _calc_walls(calls_all: pd.DataFrame,
                puts_all: pd.DataFrame,
                current_price: float | None) -> dict:
    """
    Call Wall = strike above current price with highest open interest (resistance).
    Put Wall  = strike below current price with highest open interest (support).
    Informational only -- not included in score.
    """
    try:
        call_wall = None
        put_wall  = None

        if not calls_all.empty and current_price:
            above = calls_all[calls_all["strike"] > current_price].copy()
            if not above.empty:
                call_wall = round(float(
                    above.sort_values("openInterest", ascending=False).iloc[0]["strike"]
                ), 2)

        if not puts_all.empty and current_price:
            below = puts_all[puts_all["strike"] < current_price].copy()
            if not below.empty:
                put_wall = round(float(
                    below.sort_values("openInterest", ascending=False).iloc[0]["strike"]
                ), 2)

        parts = []
        if call_wall:
            parts.append(f"Call Wall ${call_wall} (resistance)")
        if put_wall:
            parts.append(f"Put Wall ${put_wall} (support)")

        if call_wall and put_wall and current_price:
            width  = round(((call_wall - put_wall) / current_price) * 100, 1)
            signal = f"{' | '.join(parts)} -- channel width {width}% ➡️"
        elif parts:
            signal = " | ".join(parts) + " ➡️"
        else:
            signal = "Call/Put Walls: insufficient data ➡️"

        return {"call_wall": call_wall, "put_wall": put_wall, "signal": signal}

    except Exception as e:
        print(f"  Wall calculation error: {e}")
        return {"call_wall": None, "put_wall": None, "signal": "Call/Put Walls: calculation error ➡️"}


# ============================================================
# Master scoring function
# ============================================================

def score_options(data: dict) -> dict:
    """
    Scores options chain data from fetch_options_data().

    Args:
        data : standardised dict from analyzers/sentiment/options.py

    Returns:
        Scored sentiment dict (see module docstring for contract).
    """
    data_quality = data.get("data_quality", "failed")

    _empty = {
        "score":         50,
        "direction":     "neutral",
        "pcr_volume":    None,
        "pcr_oi":        None,
        "avg_iv":        None,
        "iv_multiplier": 1.0,
        "expiry":        None,
        "days_to_exp":   None,
        "max_pain":      None,
        "max_pain_dist": None,
        "call_wall":     None,
        "put_wall":      None,
        "signals":       ["No options data available -- neutral score applied ➡️"],
    }

    if data_quality == "failed":
        return _empty

    calls         = data.get("calls",         pd.DataFrame())
    puts          = data.get("puts",          pd.DataFrame())
    calls_all     = data.get("calls_all",     pd.DataFrame())
    puts_all      = data.get("puts_all",      pd.DataFrame())
    expiry        = data.get("expiry")
    dte           = data.get("days_to_exp")
    avg_iv        = data.get("avg_iv", 0.0)
    current_price = data.get("current_price")

    if calls.empty and puts.empty:
        return _empty

    # ── Score components ──────────────────────────────────────
    vol_score, pcr_vol, vol_signal = _score_pcr_volume(calls, puts)
    oi_score,  pcr_oi,  oi_signal  = _score_pcr_oi(calls, puts)
    iv_mult,   iv_signal           = _get_iv_multiplier(avg_iv)

    # ── Informational signals ─────────────────────────────────
    max_pain_data = _calc_max_pain(calls_all, puts_all, current_price)
    walls_data    = _calc_walls(calls_all, puts_all, current_price)

    # ── Score calculation ─────────────────────────────────────
    # Raw score (0-60) → scaled to 0-100 → IV multiplier applied at centre 50
    raw_score   = vol_score + oi_score
    scaled      = round((raw_score / 60) * 100)
    deviation   = scaled - 50
    final_score = max(0, min(100, round(50 + deviation * iv_mult)))

    direction = (
        "bullish" if final_score >= 60 else
        "bearish" if final_score <= 40 else
        "neutral"
    )

    signals = [
        f"Options expiry: {expiry} ({dte} days) 📅",
        vol_signal,
        oi_signal,
        iv_signal,
        max_pain_data["signal"],
        walls_data["signal"],
    ]
    icon = "✅" if direction == "bullish" else ("⚠️" if direction == "bearish" else "➡️")
    signals.append(f"Overall options tone: {direction} {icon}")

    return {
        "score":         final_score,
        "direction":     direction,
        "pcr_volume":    pcr_vol,
        "pcr_oi":        pcr_oi,
        "avg_iv":        round(avg_iv * 100, 1) if avg_iv else None,
        "iv_multiplier": iv_mult,
        "expiry":        expiry,
        "days_to_exp":   dte,
        "max_pain":      max_pain_data["max_pain_strike"],
        "max_pain_dist": max_pain_data["distance_pct"],
        "call_wall":     walls_data["call_wall"],
        "put_wall":      walls_data["put_wall"],
        "signals":       signals,
    }
