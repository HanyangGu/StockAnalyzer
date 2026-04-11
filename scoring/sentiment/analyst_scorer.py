# ============================================================
# scoring/sentiment/analyst_scorer.py -- Analyst Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call any external API or yfinance.
# Receives the standardised dict from analyzers/sentiment/analyst.py
# and produces a 0-100 analyst sentiment score.
#
# Also calls engine/llm.py once to classify analyst firm authority
# tiers (top / major / general). This is the only external call
# in this file, and it is isolated to _classify_authority().
#
# Scoring breakdown (before consensus multiplier):
#   Rating Distribution : 0-30 pts  (summary counts)
#   Weighted Ratings    : 0-20 pts  (authority × time decay)
#   Rating Momentum     : 0-20 pts  (recent upgrades vs downgrades)
#   Price Target Gap    : 0-20 pts  (mean target vs current price)
#   Target Dispersion   : 0-10 pts  (high/low spread = uncertainty)
#   Total               : 0-100 pts
#   Consensus Multiplier: ×0.85 to ×1.15
#
# Output contract:
# {
#   "score":        int    0-100
#   "direction":    str    "bullish" | "neutral" | "bearish"
#   "rating_count": int
#   "summary":      dict   pass-through from data layer
#   "targets":      dict   pass-through from data layer
#   "signals":      list[str]
# }
# ============================================================

import json
from datetime import datetime, timezone

import pandas as pd

from engine.llm import call_llm
from core.utils import safe_json_loads
from core.weights import (
    ANALYST_AUTHORITY_WEIGHTS,
    ANALYST_TIME_DECAY, ANALYST_TIME_DECAY_DEFAULT,
    ANALYST_CONSENSUS_BOOST, ANALYST_CONSENSUS_PENALTY,
    ANALYST_TARGET_GAP_THRESHOLDS, ANALYST_RATING_SCORES,
)


# ============================================================
# Constants (local aliases for readability)
# ============================================================

MIN_RATINGS       = 3
MIN_FOR_CONSENSUS = 5

RATING_SCORES     = ANALYST_RATING_SCORES
TIME_DECAY        = ANALYST_TIME_DECAY
TIME_DECAY_DEFAULT = ANALYST_TIME_DECAY_DEFAULT
AUTHORITY_WEIGHTS = ANALYST_AUTHORITY_WEIGHTS
TARGET_THRESHOLDS = ANALYST_TARGET_GAP_THRESHOLDS
CONSENSUS_BOOST   = ANALYST_CONSENSUS_BOOST
CONSENSUS_PENALTY = ANALYST_CONSENSUS_PENALTY


# ============================================================
# LLM prompt (authority classification)
# ============================================================

_AUTHORITY_PROMPT = """
You are a financial analyst authority classifier.

Given a list of analyst firm names, classify each one and return
ONLY a JSON array. No preamble, no markdown, no explanation.

For each firm return:
{
  "firm": "<firm name exactly as given>",
  "tier": "top" | "major" | "general"
}

Tier definitions:
- top     : Bulge bracket banks and top-tier research firms
             (Goldman Sachs, Morgan Stanley, JPMorgan, Bank of America,
              Citigroup, Wells Fargo, UBS, Barclays, Deutsche Bank,
              HSBC, Jefferies, Piper Sandler, Needham, Raymond James,
              Oppenheimer, Wedbush, Mizuho, Evercore, Bernstein)
- major   : Well-known regional or mid-tier firms with established track records
- general : Smaller, boutique, or less well-known research firms

Return ONLY the JSON array. No other text.
"""


# ============================================================
# Internal helpers
# ============================================================

def _time_weight(date) -> float:
    """Time decay weight for a rating by age in months."""
    try:
        now = datetime.now(timezone.utc)
        ts  = pd.Timestamp(date)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        age_months = (now - ts.to_pydatetime()).days / 30.0
        for max_months, weight in TIME_DECAY:
            if age_months <= max_months:
                return weight
        return TIME_DECAY_DEFAULT
    except Exception:
        return TIME_DECAY_DEFAULT


def _grade_to_score(grade: str) -> float:
    """Converts rating string to numeric score (-2 to +2)."""
    normalised = grade.lower().strip()
    if normalised in RATING_SCORES:
        return RATING_SCORES[normalised]
    for key, val in RATING_SCORES.items():
        if key in normalised or normalised in key:
            return val
    return 0.0


def _classify_authority(firms: list) -> dict:
    """
    Uses LLM to classify analyst firms by authority tier.
    Returns {firm_name: tier_string} dict.
    Isolated here so swapping engine/llm.py is the only change needed.
    """
    if not firms:
        return {}
    unique = list(set(firms))
    raw    = call_llm(
        system      = _AUTHORITY_PROMPT,
        user        = f"Classify: {json.dumps(unique)}",
        max_tokens  = 800,
        temperature = 0.0,
    )
    if not raw:
        return {}
    results = safe_json_loads(raw, default=[])
    if not isinstance(results, list):
        return {}
    return {r["firm"]: r["tier"] for r in results if "firm" in r and "tier" in r}


# ============================================================
# Score components (pure functions -- easy to unit test)
# ============================================================

def _score_distribution(summary: dict) -> tuple[int, str]:
    """Rating distribution score (0-30 pts)."""
    if not summary:
        return 0, "Rating distribution: no data ➡️"

    sb = summary.get("strong_buy",  0)
    b  = summary.get("buy",         0)
    h  = summary.get("hold",        0)
    s  = summary.get("sell",        0)
    ss = summary.get("strong_sell", 0)
    total = sb + b + h + s + ss

    if total == 0:
        return 0, "Rating distribution: no ratings ➡️"

    bull = (sb * 2.0 + b * 1.0) / total
    bear = (ss * 2.0 + s * 1.0) / total
    net  = bull - bear

    if net >= 1.5:
        score, icon = 30, "✅"
        label = f"overwhelmingly bullish ({sb} Strong Buy, {b} Buy of {total})"
    elif net >= 0.8:
        score, icon = 22, "✅"
        label = f"mostly bullish ({sb} Strong Buy, {b} Buy of {total})"
    elif net >= 0.3:
        score, icon = 15, "✅"
        label = f"mildly bullish ({sb+b} buy-side of {total})"
    elif net >= -0.3:
        score, icon = 10, "➡️"
        label = f"neutral ({h} Hold dominant of {total})"
    elif net >= -0.8:
        score, icon = 4, "⚠️"
        label = f"mildly bearish ({s+ss} sell-side of {total})"
    else:
        score, icon = 0, "⚠️"
        label = f"overwhelmingly bearish ({ss} Strong Sell of {total})"

    return score, f"Rating distribution: {label} {icon}"


def _score_momentum(ratings: list) -> tuple[int, str]:
    """Rating momentum score (0-20 pts) based on recent upgrades vs downgrades."""
    if not ratings:
        return 10, "Rating momentum: no data ➡️"

    cutoff = datetime.now(timezone.utc).timestamp() - 90 * 86400
    recent = [
        r for r in ratings
        if pd.Timestamp(r["date"]).timestamp() >= cutoff
    ]

    ups   = sum(1 for r in recent if r["action"] == "up")
    downs = sum(1 for r in recent if r["action"] == "down")
    inits = sum(1 for r in recent if r["action"] == "init")
    net   = ups - downs + (inits * 0.5)

    if net >= 3:
        score, icon = 20, "✅"
        label = f"strong upgrade momentum ({ups} upgrades, {downs} downgrades)"
    elif net >= 1:
        score, icon = 15, "✅"
        label = f"mild upgrade momentum ({ups} upgrades, {downs} downgrades)"
    elif net >= -0.5:
        score, icon = 10, "➡️"
        label = f"neutral ({ups} upgrades, {downs} downgrades)"
    elif net >= -2:
        score, icon = 5, "⚠️"
        label = f"mild downgrade pressure ({downs} downgrades, {ups} upgrades)"
    else:
        score, icon = 0, "⚠️"
        label = f"strong downgrade pressure ({downs} downgrades, {ups} upgrades)"

    return score, f"Rating momentum: {label} {icon}"


def _score_price_target(targets: dict,
                         current_price: float | None) -> tuple[int, list]:
    """Price target gap + dispersion score (0-30 pts total)."""
    signals = []
    score   = 0

    mean_t = targets.get("mean")
    high_t = targets.get("high")
    low_t  = targets.get("low")

    # Gap score (0-20 pts)
    if mean_t and current_price:
        gap_pct   = (mean_t - current_price) / current_price
        gap_score = 0
        for threshold, pts in TARGET_THRESHOLDS:
            if gap_pct >= threshold:
                gap_score = pts
                break
        score += gap_score
        icon  = "✅" if gap_pct > 0.05 else ("⚠️" if gap_pct < -0.05 else "➡️")
        sign  = "+" if gap_pct >= 0 else ""
        signals.append(
            f"Price target: mean USD {round(mean_t, 2)} "
            f"({sign}{round(gap_pct * 100, 1)}% vs current USD {round(current_price, 2)}) {icon}"
        )
    else:
        signals.append("Price target: no data ➡️")

    # Dispersion score (0-10 pts)
    if high_t and low_t and low_t > 0:
        disp = (high_t - low_t) / low_t
        if disp < 0.15:
            d_score, d_icon = 10, "✅"
            d_label = f"low dispersion (USD {round(low_t,0)}-{round(high_t,0)}) -- high agreement"
        elif disp < 0.35:
            d_score, d_icon = 6, "➡️"
            d_label = f"moderate dispersion (USD {round(low_t,0)}-{round(high_t,0)})"
        elif disp < 0.60:
            d_score, d_icon = 3, "⚠️"
            d_label = f"high dispersion (USD {round(low_t,0)}-{round(high_t,0)}) -- analyst disagreement"
        else:
            d_score, d_icon = 0, "⚠️"
            d_label = f"very high dispersion (USD {round(low_t,0)}-{round(high_t,0)}) -- very uncertain"
        score += d_score
        signals.append(f"Target dispersion: {d_label} {d_icon}")

    return score, signals


def _score_weighted_ratings(ratings: list,
                              authority_map: dict) -> tuple[int, str]:
    """Weighted ratings by authority tier × time decay (0-20 pts)."""
    if not ratings:
        return 10, "Weighted ratings: no data ➡️"

    weighted_sum     = 0.0
    total_weight     = 0.0
    initiation_boost = 0.0

    for r in ratings:
        grade  = r["grade"]
        firm   = r["firm"]
        action = r["action"]

        g_score  = _grade_to_score(grade)
        t_weight = _time_weight(r["date"])
        a_weight = AUTHORITY_WEIGHTS.get(
                       authority_map.get(firm, "general"), 0.7
                   )

        weight         = t_weight * a_weight
        weighted_sum  += g_score * weight
        total_weight  += weight

        if action == "init":
            tier = authority_map.get(firm, "general")
            initiation_boost += 0.3 if tier == "top" else (0.15 if tier == "major" else 0.05)

    if total_weight == 0:
        return 10, "Weighted ratings: insufficient data ➡️"

    avg   = (weighted_sum / total_weight) + initiation_boost
    score = round(10 + avg * 5)
    score = max(0, min(20, score))

    if avg >= 1.0:
        label, icon = "strongly bullish analyst consensus", "✅"
    elif avg >= 0.3:
        label, icon = "mildly bullish analyst consensus", "✅"
    elif avg >= -0.3:
        label, icon = "neutral analyst consensus", "➡️"
    elif avg >= -1.0:
        label, icon = "mildly bearish analyst consensus", "⚠️"
    else:
        label, icon = "strongly bearish analyst consensus", "⚠️"

    if initiation_boost > 0:
        label += f" (+{round(initiation_boost, 2)} initiation boost)"

    return score, f"Weighted ratings: {label} {icon}"


def _score_consensus(summary: dict) -> float:
    """Consensus multiplier (×0.85 to ×1.15) based on analyst agreement."""
    if not summary:
        return 1.0

    sb = summary.get("strong_buy",  0)
    b  = summary.get("buy",         0)
    h  = summary.get("hold",        0)
    s  = summary.get("sell",        0)
    ss = summary.get("strong_sell", 0)
    total = sb + b + h + s + ss

    if total < MIN_FOR_CONSENSUS:
        return 1.0

    dominant = max(sb + b, h, s + ss)
    ratio    = dominant / total

    if ratio >= 0.70:
        return CONSENSUS_BOOST
    elif ratio <= 0.40:
        return CONSENSUS_PENALTY
    else:
        return 1.0


# ============================================================
# Master scoring function
# ============================================================

def score_analyst(data: dict) -> dict:
    """
    Scores analyst data from fetch_analyst_data().

    Args:
        data : standardised dict from analyzers/sentiment/analyst.py

    Returns:
        Scored sentiment dict (see module docstring for contract).
    """
    ratings       = data.get("ratings",       [])
    summary       = data.get("summary",       {})
    targets       = data.get("targets",       {})
    current_price = data.get("current_price")
    data_quality  = data.get("data_quality",  "failed")
    rating_count  = len(ratings)

    # Insufficient / failed data fallback
    if data_quality in ("failed", "insufficient") and not summary:
        return {
            "score":        50,
            "direction":    "neutral",
            "rating_count": rating_count,
            "summary":      summary,
            "targets":      targets,
            "signals": [
                f"Insufficient analyst data ({rating_count} ratings) "
                f"-- neutral score applied ➡️"
            ],
        }

    # LLM authority classification (isolated to this one call)
    firms         = list({r["firm"] for r in ratings if r["firm"]})
    authority_map = _classify_authority(firms) if firms else {}

    # Score each component
    dist_score,   dist_signal   = _score_distribution(summary)
    weight_score, weight_signal = _score_weighted_ratings(ratings, authority_map)
    mom_score,    mom_signal    = _score_momentum(ratings)
    target_score, target_sigs   = _score_price_target(targets, current_price)
    consensus                   = _score_consensus(summary)

    raw_score   = dist_score + weight_score + mom_score + target_score
    raw_score   = max(0, min(100, raw_score))
    final_score = round(raw_score * consensus)
    final_score = max(0, min(100, final_score))

    direction = (
        "bullish" if final_score >= 60 else
        "bearish" if final_score <= 40 else
        "neutral"
    )

    signals = [dist_signal, weight_signal, mom_signal] + target_sigs
    if consensus >= CONSENSUS_BOOST:
        signals.append("Strong analyst consensus -- high agreement ✅")
    elif consensus <= CONSENSUS_PENALTY:
        signals.append("Divided analyst opinions -- reduced confidence ⚠️")
    icon = "✅" if direction == "bullish" else ("⚠️" if direction == "bearish" else "➡️")
    signals.append(f"Overall analyst tone: {direction} {icon}")

    return {
        "score":        final_score,
        "direction":    direction,
        "rating_count": rating_count,
        "summary":      summary,
        "targets":      targets,
        "signals":      signals,
    }
