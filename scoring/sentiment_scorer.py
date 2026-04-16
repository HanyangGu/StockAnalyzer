# ============================================================
# scoring/sentiment_scorer.py -- Sentiment Scoring Engine
# ============================================================
# Aggregates all sentiment sub-dimension scores into one
# overall sentiment score (0-100).
#
# Current weights:
#   News Sentiment   : 55%
#   Analyst Ratings  : 22%
#   Insider Trading  : 13%
#   Options Sentiment: 10%
#
# Future dimensions (macro, events) will be added here.
# ============================================================
from core.weights import (
    WEIGHT_NEWS, WEIGHT_ANALYST, WEIGHT_INSIDER, WEIGHT_OPTIONS,
)




def get_sentiment_verdict(score: int) -> tuple:
    """Converts sentiment score to verdict label and emoji."""
    if score >= 75:
        return "Very Bullish Sentiment",  "🟢"
    elif score >= 60:
        return "Bullish Sentiment",       "🟩"
    elif score >= 40:
        return "Neutral Sentiment",       "⬜"
    elif score >= 25:
        return "Bearish Sentiment",       "🟥"
    else:
        return "Very Bearish Sentiment",  "🔴"


def score_sentiment(news: dict,
                    analyst: dict = None,
                    insider: dict = None,
                    options: dict = None) -> dict:
    """
    Aggregates all active sentiment sub-dimension scores.

    Weights redistribute proportionally if a dimension is unavailable.

    Returns:
        {
          "score"    : 0-100,
          "verdict"  : str,
          "icon"     : emoji,
          "signals"  : [str],
          "breakdown": { news, analyst, insider, options }
        }
    """
    breakdown = {}

    # -- News (55%) -------------------------------------------
    news_score = news.get("score", 50) if news else 50
    breakdown["news"] = {
        "score":         news_score,
        "direction":     news.get("direction",     "neutral") if news else "neutral",
        "article_count": news.get("article_count", 0)        if news else 0,
        "articles":      news.get("articles",      [])        if news else [],
        "signals":       news.get("signals",       [])        if news else [],
    }

    # -- Analyst (22%) ----------------------------------------
    analyst_score = analyst.get("score", 50) if analyst else 50
    breakdown["analyst"] = {
        "score":        analyst_score,
        "direction":    analyst.get("direction",    "neutral") if analyst else "neutral",
        "rating_count": analyst.get("rating_count", 0)        if analyst else 0,
        "summary":      analyst.get("summary",      {})        if analyst else {},
        "targets":      analyst.get("targets",      {})        if analyst else {},
        "signals":      analyst.get("signals",      [])        if analyst else [],
    }

    # -- Insider (13%) ----------------------------------------
    insider_score = insider.get("score", 50) if insider else 50
    breakdown["insider"] = {
        "score":             insider_score,
        "direction":         insider.get("direction",         "neutral") if insider else "neutral",
        "transaction_count": insider.get("transaction_count", 0)        if insider else 0,
        "transactions":      insider.get("transactions",      [])        if insider else [],
        "signals":           insider.get("signals",           [])        if insider else [],
    }

    # -- Options (10%) ----------------------------------------
    options_score = options.get("score", 50) if options else 50
    breakdown["options"] = {
        "score":         options_score,
        "direction":     options.get("direction",     "neutral") if options else "neutral",
        "pcr_volume":    options.get("pcr_volume")               if options else None,
        "pcr_oi":        options.get("pcr_oi")                   if options else None,
        "avg_iv":        options.get("avg_iv")                   if options else None,
        "iv_multiplier": options.get("iv_multiplier", 1.0)       if options else 1.0,
        "expiry":        options.get("expiry")                   if options else None,
        "days_to_exp":   options.get("days_to_exp")              if options else None,
        "max_pain":      options.get("max_pain")                 if options else None,
        "max_pain_dist": options.get("max_pain_dist")            if options else None,
        "call_wall":     options.get("call_wall")                if options else None,
        "put_wall":      options.get("put_wall")                 if options else None,
        "signals":       options.get("signals",       [])        if options else [],
    }

    # -- Weighted aggregate (redistribute if unavailable) -----
    weighted_sum  = 0.0
    active_weight = 0.0

    if news:
        weighted_sum  += news_score * WEIGHT_NEWS
        active_weight += WEIGHT_NEWS

    if analyst:
        weighted_sum  += analyst_score * WEIGHT_ANALYST
        active_weight += WEIGHT_ANALYST

    if insider:
        weighted_sum  += insider_score * WEIGHT_INSIDER
        active_weight += WEIGHT_INSIDER

    if options:
        weighted_sum  += options_score * WEIGHT_OPTIONS
        active_weight += WEIGHT_OPTIONS

    overall_score = round(weighted_sum / active_weight) if active_weight > 0 else 50
    overall_score = max(0, min(100, overall_score))
    verdict, icon = get_sentiment_verdict(overall_score)

    return {
        "score":     overall_score,
        "verdict":   verdict,
        "icon":      icon,
        "signals":   [],
        "breakdown": breakdown,
    }
