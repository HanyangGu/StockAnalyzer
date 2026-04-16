# ============================================================
# scoring/sentiment/news_scorer.py -- News Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call yfinance.
# Receives the standardised dict from analyzers/sentiment/news.py,
# runs GPT multi-dimension analysis on each article,
# then produces a 0-100 news sentiment score.
#
# Scoring pipeline:
#   1. GPT analyses each article across 8 dimensions
#   2. Per-article score = direction × multipliers × time decay
#   3. Cross-article consensus adjustment (if MIN_RELEVANT met)
#   4. Normalise to 0-100 via calibration constant
#
# Per-article dimensions (GPT judged):
#   relevance   : direct / indirect / unrelated (unrelated = score 0)
#   sentiment   : positive / neutral / negative
#   intensity   : strong / moderate / mild
#   impact      : major / normal / minor
#   scope       : company / industry / macro
#   credibility : high / medium / low
#   novelty     : first / followup / repeat
#   surprise    : unexpected / partial / expected
#
# Output contract:
# {
#   "score":          int    0-100
#   "direction":      str    "bullish" | "neutral" | "bearish"
#   "article_count":  int
#   "relevant_count": int
#   "articles":       list[dict]   enriched with GPT judgments
#   "consensus":      float
#   "signals":        list[str]
# }
# ============================================================

from datetime import datetime, timezone

from engine.llm import call_llm
from core.utils import safe_json_loads
from core.weights import (
    NEWS_RELEVANCE_WEIGHTS, NEWS_TIME_DECAY, NEWS_TIME_DECAY_DEFAULT,
    NEWS_TIME_WEIGHT_FLOOR, NEWS_INTENSITY_WEIGHTS, NEWS_IMPACT_WEIGHTS,
    NEWS_SCOPE_WEIGHTS, NEWS_CREDIBILITY_WEIGHTS, NEWS_NOVELTY_WEIGHTS,
    NEWS_SURPRISE_WEIGHTS, NEWS_CONSENSUS_BOOST, NEWS_CONSENSUS_PENALTY,
    NEWS_CALIBRATION_RAW,
)


# ============================================================
# Constants (local aliases)
# ============================================================

MIN_RELEVANT        = 4

RELEVANCE_WEIGHTS   = NEWS_RELEVANCE_WEIGHTS
TIME_DECAY          = NEWS_TIME_DECAY
TIME_DECAY_DEFAULT  = NEWS_TIME_DECAY_DEFAULT
TIME_WEIGHT_FLOOR   = NEWS_TIME_WEIGHT_FLOOR
INTENSITY_WEIGHTS   = NEWS_INTENSITY_WEIGHTS
IMPACT_WEIGHTS      = NEWS_IMPACT_WEIGHTS
SCOPE_WEIGHTS       = NEWS_SCOPE_WEIGHTS
CREDIBILITY_WEIGHTS = NEWS_CREDIBILITY_WEIGHTS
NOVELTY_WEIGHTS     = NEWS_NOVELTY_WEIGHTS
SURPRISE_WEIGHTS    = NEWS_SURPRISE_WEIGHTS
CONSENSUS_BOOST     = NEWS_CONSENSUS_BOOST
CONSENSUS_PENALTY   = NEWS_CONSENSUS_PENALTY
CALIBRATION_RAW     = NEWS_CALIBRATION_RAW


# ============================================================
# LLM prompt
# ============================================================

_NEWS_SYSTEM_PROMPT = """
You are a financial news sentiment analyst.

Given a list of news articles about a stock, analyse each one
and return ONLY a JSON array. No preamble, no markdown, no explanation.

For each article return exactly this structure:
{
  "index":       <int, the article index>,
  "relevance":   "direct" | "indirect" | "unrelated",
  "sentiment":   "positive" | "neutral" | "negative",
  "intensity":   "strong" | "moderate" | "mild",
  "impact":      "major" | "normal" | "minor",
  "scope":       "company" | "industry" | "macro",
  "credibility": "high" | "medium" | "low",
  "novelty":     "first" | "followup" | "repeat",
  "surprise":    "unexpected" | "partial" | "expected",
  "reason":      "<one concise sentence explaining your judgment>"
}

Dimension definitions:
- relevance   : direct=explicitly about this stock's business/price/operations,
                indirect=affects the industry or macro environment that impacts this stock,
                unrelated=about other companies or topics with no bearing on this stock
- sentiment   : effect on this stock's price outlook (neutral if unrelated)
- intensity   : how strongly positive/negative (mild if neutral or unrelated)
- impact      : major=earnings/regulation/M&A/CEO change, normal=products/partnerships, minor=general commentary
- scope       : company=affects only this stock, industry=affects sector, macro=affects all stocks
- credibility : high=Reuters/Bloomberg/WSJ/FT, medium=established outlets, low=unknown/blog
- novelty     : first=new information, followup=additional coverage of same event, repeat=repost/duplicate
- surprise    : unexpected=market had no warning, partial=some rumours existed, expected=widely anticipated

IMPORTANT:
- indirect articles (macro/industry news) still count but at reduced weight
- unrelated articles are fully excluded from scoring
- Be generous with indirect: if the news could plausibly affect this stock, mark indirect not unrelated

Return ONLY the JSON array. No other text.
"""


# ============================================================
# Internal helpers (pure functions)
# ============================================================

def _time_decay_weight(published_ts: int, impact: str = "minor") -> float:
    """
    Calculates time decay weight by article age.
    Major impact articles have a minimum floor weight so they
    stay relevant longer than routine news.
    """
    try:
        now     = datetime.now(timezone.utc).timestamp()
        age_days = (now - published_ts) / 86400

        for max_days, weight in TIME_DECAY:
            if age_days <= max_days:
                floor = TIME_WEIGHT_FLOOR.get(impact, 0.0)
                return max(weight, floor)

        floor = TIME_WEIGHT_FLOOR.get(impact, 0.0)
        return max(TIME_DECAY_DEFAULT, floor)
    except Exception:
        return TIME_DECAY_DEFAULT


def _sentiment_to_direction(sentiment: str) -> int:
    """Converts sentiment label to +1 / 0 / -1."""
    return {"positive": 1, "neutral": 0, "negative": -1}.get(sentiment, 0)


def _calc_article_score(judgment: dict, time_weight: float) -> float:
    """
    Calculates weighted score for a single article.
    Unrelated articles return 0.0 via the relevance multiplier.
    """
    relevance = RELEVANCE_WEIGHTS.get(judgment.get("relevance", "unrelated"), 0.0)
    if relevance == 0.0:
        return 0.0

    direction   = _sentiment_to_direction(judgment.get("sentiment", "neutral"))
    intensity   = INTENSITY_WEIGHTS.get(   judgment.get("intensity",   "mild"),     0.3)
    impact      = IMPACT_WEIGHTS.get(      judgment.get("impact",      "minor"),    0.5)
    scope       = SCOPE_WEIGHTS.get(       judgment.get("scope",       "macro"),    0.6)
    credibility = CREDIBILITY_WEIGHTS.get( judgment.get("credibility", "low"),      0.5)
    novelty     = NOVELTY_WEIGHTS.get(     judgment.get("novelty",     "repeat"),   0.3)
    surprise    = SURPRISE_WEIGHTS.get(    judgment.get("surprise",    "expected"), 0.5)

    return direction * (
        relevance * intensity * impact *
        scope * credibility * novelty * surprise * time_weight
    )


def _calc_consensus(judgments: list) -> float:
    """
    Cross-article consensus multiplier.
    Only activates when MIN_RELEVANT relevant articles are present.
    """
    relevant = [
        j for j in judgments
        if j.get("relevance") in ("direct", "indirect")
    ]
    if len(relevant) < MIN_RELEVANT:
        return 1.0

    sentiments = [j.get("sentiment", "neutral") for j in relevant]
    pos   = sentiments.count("positive")
    neg   = sentiments.count("negative")
    neu   = sentiments.count("neutral")
    total = len(sentiments)

    dominant = max(pos, neg, neu)
    ratio    = dominant / total

    if ratio >= 0.75:
        return CONSENSUS_BOOST
    elif ratio <= 0.45:
        return CONSENSUS_PENALTY
    else:
        return 1.0


def _run_gpt_analysis(articles: list,
                       ticker: str,
                       company_name: str) -> list:
    """
    Sends articles to LLM for multi-dimension sentiment analysis.
    Returns list of judgment dicts.
    Isolated here so swapping engine/llm.py is the only change needed.
    """
    if not articles:
        return []

    article_text = ""
    for i, a in enumerate(articles):
        article_text += (
            f"\n[{i}] Source: {a['source']}\n"
            f"Title: {a['title']}\n"
            f"Summary: {a['summary'][:300]}\n"
        )

    prompt = (
        f"Stock: {ticker} ({company_name})\n"
        f"Analyse these {len(articles)} news articles.\n"
        f"{article_text}"
    )

    raw = call_llm(
        system     = _NEWS_SYSTEM_PROMPT,
        user       = prompt,
        max_tokens = 2500,
        temperature= 0.1,
    )

    if not raw:
        return []

    result = safe_json_loads(raw, default=[])

    # Graceful fallback: if GPT parse failed, return neutral for all articles
    if not result:
        print("  GPT news parse failed -- applying neutral fallback")
        return [
            {
                "index":       i,
                "relevance":   "unrelated",
                "sentiment":   "neutral",
                "intensity":   "mild",
                "impact":      "minor",
                "scope":       "macro",
                "credibility": "medium",
                "novelty":     "followup",
                "surprise":    "expected",
                "reason":      "GPT parse failed -- neutral fallback applied",
            }
            for i in range(len(articles))
        ]

    return result if isinstance(result, list) else []


# ============================================================
# Master scoring function
# ============================================================

def score_news(data: dict,
               ticker:       str = "",
               company_name: str = "") -> dict:
    """
    Scores news article data from fetch_news_data().

    Args:
        data         : standardised dict from analyzers/sentiment/news.py
        ticker       : ticker symbol (used for LLM context only)
        company_name : company name (used for LLM context only)

    Returns:
        Scored sentiment dict (see module docstring for contract).
    """
    articles     = data.get("articles",     [])
    data_quality = data.get("data_quality", "failed")

    if not articles or data_quality == "failed":
        return {
            "score":          50,
            "direction":      "neutral",
            "article_count":  0,
            "relevant_count": 0,
            "articles":       [],
            "consensus":      1.0,
            "signals":        ["No recent news found -- neutral score applied ➡️"],
        }

    # ── LLM analysis ─────────────────────────────────────────
    judgments = _run_gpt_analysis(articles, ticker, company_name)

    if not judgments:
        return {
            "score":          50,
            "direction":      "neutral",
            "article_count":  len(articles),
            "relevant_count": 0,
            "articles":       [],
            "consensus":      1.0,
            "signals":        ["News analysis unavailable -- neutral score applied ➡️"],
        }

    judgment_map = {j["index"]: j for j in judgments if "index" in j}

    # ── Per-article scoring ───────────────────────────────────
    raw_scores = []
    enriched   = []

    for i, article in enumerate(articles):
        judgment    = judgment_map.get(i, {})
        relevance   = judgment.get("relevance", "unrelated")
        impact      = judgment.get("impact",    "minor")
        time_weight = _time_decay_weight(article["published_ts"], impact)
        art_score   = _calc_article_score(judgment, time_weight)
        raw_scores.append(art_score)

        enriched.append({
            "title":        article["title"],
            "source":       article["source"],
            "published_ts": article["published_ts"],
            "time_weight":  time_weight,
            "relevance":    relevance,
            "sentiment":    judgment.get("sentiment",   "neutral"),
            "intensity":    judgment.get("intensity",   "mild"),
            "impact":       impact,
            "scope":        judgment.get("scope",       "macro"),
            "credibility":  judgment.get("credibility", "medium"),
            "novelty":      judgment.get("novelty",     "followup"),
            "surprise":     judgment.get("surprise",    "expected"),
            "reason":       judgment.get("reason",      ""),
            "raw_score":    round(art_score, 4),
        })

    # ── Consensus + normalisation ─────────────────────────────
    consensus    = _calc_consensus(judgments)
    total_raw    = sum(raw_scores)
    adjusted_raw = total_raw * consensus
    norm         = max(-1.0, min(1.0, adjusted_raw / CALIBRATION_RAW))
    score        = max(0, min(100, round(50 + norm * 50)))

    direction = (
        "bullish" if score >= 60 else
        "bearish" if score <= 40 else
        "neutral"
    )

    # ── Signals ───────────────────────────────────────────────
    direct_arts   = [a for a in enriched if a["relevance"] == "direct"]
    indirect_arts = [a for a in enriched if a["relevance"] == "indirect"]
    unrel_arts    = [a for a in enriched if a["relevance"] == "unrelated"]

    pos_count = sum(1 for a in direct_arts + indirect_arts if a["sentiment"] == "positive")
    neg_count = sum(1 for a in direct_arts + indirect_arts if a["sentiment"] == "negative")
    neu_count = sum(1 for a in direct_arts + indirect_arts if a["sentiment"] == "neutral")
    major_pos = [a for a in direct_arts + indirect_arts if a["sentiment"] == "positive" and a["impact"] == "major"]
    major_neg = [a for a in direct_arts + indirect_arts if a["sentiment"] == "negative" and a["impact"] == "major"]

    signals = []
    signals.append(
        f"News: {len(direct_arts)} direct, {len(indirect_arts)} indirect, "
        f"{len(unrel_arts)} unrelated (of {len(enriched)} total)"
    )
    signals.append(
        f"Relevant sentiment: {pos_count} positive, "
        f"{neg_count} negative, {neu_count} neutral"
    )
    if major_pos:
        signals.append(f"Major positive: {major_pos[0]['title'][:60]}... ({major_pos[0]['source']}) ✅")
    if major_neg:
        signals.append(f"Major negative: {major_neg[0]['title'][:60]}... ({major_neg[0]['source']}) ⚠️")
    if consensus >= CONSENSUS_BOOST:
        signals.append("Strong consensus across relevant news ✅")
    elif consensus <= CONSENSUS_PENALTY:
        signals.append("Mixed signals -- high disagreement across news sources ⚠️")
    elif len(direct_arts) + len(indirect_arts) < MIN_RELEVANT:
        signals.append(
            f"Low relevant article count ({len(direct_arts)+len(indirect_arts)}) "
            f"-- sentiment score has low confidence ➡️"
        )

    icon = "✅" if direction == "bullish" else ("⚠️" if direction == "bearish" else "➡️")
    signals.append(f"Overall news tone: {direction} {icon}")

    return {
        "score":          score,
        "direction":      direction,
        "article_count":  len(enriched),
        "relevant_count": len(direct_arts) + len(indirect_arts),
        "articles":       enriched,
        "consensus":      consensus,
        "signals":        signals,
    }
