# ============================================================
# scoring/sentiment/insider_scorer.py -- Insider Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call yfinance.
# Receives the standardised dict from analyzers/sentiment/insider.py,
# runs GPT analysis for 10b5-1 detection and signal quality,
# then produces a 0-100 insider sentiment score.
#
# Scoring breakdown:
#   Net Buy/Sell Ratio  : 0-30 pts  (10b5-1 sales downweighted × 0.3)
#   Buyer/Seller Count  : 0-25 pts  (10b5-1 sellers excluded from count)
#   Transaction Size    : 0-20 pts  (largest single purchase)
#   Position Level      : 0-15 pts  (CEO/CFO buys score higher)
#   Baseline            : 10 pts
#   Total               : 10-100 pts (clamped)
#
# Output contract:
# {
#   "score":             int    0-100
#   "direction":         str    "bullish" | "neutral" | "bearish"
#   "transaction_count": int
#   "transactions":      list[dict]  enriched with GPT signal fields
#   "signals":           list[str]
# }
# ============================================================

from engine.llm import call_llm
from core.utils import safe_json_loads
from core.weights import INSIDER_SIZE_THRESHOLDS


# ============================================================
# Constants
# ============================================================

SIZE_THRESHOLDS = INSIDER_SIZE_THRESHOLDS


# ============================================================
# LLM prompt (10b5-1 detection + signal classification)
# ============================================================

_INSIDER_PROMPT = """
You are an insider trading signal analyst.

Given a list of insider transactions for a stock, analyse each one
and return ONLY a JSON array. No preamble, no markdown, no explanation.

For each transaction return exactly this structure:
{
  "index":         <int, the transaction index>,
  "signal":        "bullish" | "bearish" | "neutral",
  "strength":      "strong" | "moderate" | "weak",
  "likely_10b5_1": true | false,
  "reason":        "<one concise sentence explaining the signal quality>"
}

Signal guidelines:
- bullish  : open market purchase by insider
- bearish  : open market sale by insider (downweight if likely 10b5-1)
- neutral  : ambiguous, small amounts, gifts, or unclear motivation

Strength guidelines:
- strong   : CEO/CFO/President, large amount, clear open market buy
- moderate : mid-level officer or director, meaningful amount
- weak     : small amount, unclear motivation, or routine-looking

10b5-1 detection (set likely_10b5_1 = true if ANY apply):
- Text/description mentions "Rule 10b5-1" or "trading plan"
- Sale is part of a recurring series (same insider selling similar
  amounts on a regular schedule)
- Sale occurs shortly after a major earnings beat (tax diversification)
- Executive retains large position despite selling (wealth management)
- Sale size is small relative to position (< 5% of holdings)

Key considerations:
- Large open market purchases by top executives are the strongest bullish signals
- Sales flagged as likely 10b5-1 are routine wealth management, NOT bearish signals
- Sales NOT flagged as 10b5-1 and large in size are genuine bearish signals
- Very small purchases may be symbolic rather than conviction buys
- Multiple insiders buying simultaneously strengthens the signal

Return ONLY the JSON array. No other text.
"""


# ============================================================
# Internal helpers
# ============================================================

def _transaction_size_score(value: float) -> int:
    """Maps transaction USD value to size score (0-20)."""
    for threshold, score in SIZE_THRESHOLDS:
        if value >= threshold:
            return score
    return 1


def _run_gpt_analysis(transactions: list, ticker: str) -> list:
    """
    Sends parsed transactions to LLM for signal + 10b5-1 analysis.
    Returns list of judgment dicts, or [] on failure.
    Isolated here so swapping engine/llm.py is the only change needed.
    """
    if not transactions:
        return []

    txn_text = ""
    for i, t in enumerate(transactions):
        ownership_str = (
            f"  Ownership%: {t['ownership_pct']}% of shares outstanding\n"
            if t.get("ownership_pct") is not None else ""
        )
        txn_text += (
            f"\n[{i}] {t['insider']} ({t['title']})\n"
            f"  Action: {t['transaction_type']}\n"
            f"  Shares: {t['shares']:,}\n"
            f"  Value:  USD {t['value']:,.0f}\n"
            f"  Date:   {t['date_str']}\n"
            f"{ownership_str}"
            f"  Text:   {t.get('text_snippet', '')}\n"
        )

    raw = call_llm(
        system      = _INSIDER_PROMPT,
        user        = f"Stock: {ticker}\nAnalyse:\n{txn_text}",
        max_tokens  = 2000,
        temperature = 0.1,
    )

    if not raw:
        return []

    result = safe_json_loads(raw, default=[])
    return result if isinstance(result, list) else []


# ============================================================
# Master scoring function
# ============================================================

def score_insider(data: dict, ticker: str = "") -> dict:
    """
    Scores insider transaction data from fetch_insider_data().

    Args:
        data   : standardised dict from analyzers/sentiment/insider.py
        ticker : ticker symbol (used for LLM context only)

    Returns:
        Scored sentiment dict (see module docstring for contract).
    """
    transactions     = data.get("transactions", [])      # GPT-filtered high-signal subset
    all_transactions = data.get("all_transactions") or transactions  # full list for count display
    data_quality     = data.get("data_quality", "failed")

    if not transactions or data_quality in ("failed", "insufficient"):
        msg = (
            "No insider transaction data available -- neutral score applied ➡️"
            if data_quality == "failed"
            else "All insider transactions were non-market (gifts/awards) -- neutral ➡️"
        )
        return {
            "score":             50,
            "direction":         "neutral",
            "transaction_count": 0,
            "transactions":      [],
            "signals":           [msg],
        }

    # ── LLM analysis (10b5-1 + signal quality) ───────────────
    judgments    = _run_gpt_analysis(transactions, ticker)
    judgment_map = {j["index"]: j for j in judgments if "index" in j}

    enriched = []
    for i, t in enumerate(transactions):
        j = judgment_map.get(i, {})
        enriched.append({
            **t,
            "signal":        j.get("signal",        "neutral"),
            "strength":      j.get("strength",      "weak"),
            "likely_10b5_1": j.get("likely_10b5_1", False),
            "reason":        j.get("reason",        ""),
        })

    # ── 10b5-1 Neutral Override ───────────────────────────────
    # When ≥80% of all sell transactions are 10b5-1 scheduled plans
    # AND there are no open-market buyers, the signal has no value.
    sellers_all   = [t for t in enriched if t["is_sell"]]
    buyers_all    = [t for t in enriched if t["is_buy"]]
    n_10b5_total  = sum(1 for t in sellers_all if t.get("likely_10b5_1"))
    plan_ratio    = n_10b5_total / len(sellers_all) if sellers_all else 0.0

    if plan_ratio >= 0.80 and not buyers_all:
        n_sellers_display = len(set(t["insider"] for t in sellers_all))
        signals = [
            f"Insider activity: 0 buyer(s), {n_sellers_display} seller(s) "
            f"of {len(enriched)} total transactions",
            f"📋 Scheduled trading plans: {n_10b5_total}/{len(sellers_all)} sale(s) "
            f"flagged as 10b5-1 ({int(plan_ratio*100)}%) -- "
            f"pre-registered wealth management, not a bearish signal ➡️",
            "Adjusted value flow: no open-market purchases vs plan-only sales "
            "-- signal not meaningful ➡️",
            "Overall insider tone: neutral ➡️",
        ]
        return {
            "score":             50,
            "direction":         "neutral",
            "is_scheduled_only": True,
            "plan_ratio":        round(plan_ratio, 2),
            "cluster_bonus":     0,
            "transaction_count": n_all,
            "transactions":      enriched,
            "signals":           signals,
        }

    # ── Scoring ───────────────────────────────────────────────
    buyers  = buyers_all
    sellers = sellers_all

    def _sell_weight(t: dict) -> float:
        """10b5-1 sales downweighted × 0.3; non-10b5-1 retain full weight."""
        base = t["value"] * t["time_weight"]
        return base * 0.3 if t.get("likely_10b5_1") else base

    buy_value   = sum(t["value"] * t["time_weight"] for t in buyers)
    sell_value  = sum(_sell_weight(t) for t in sellers)
    total_value = buy_value + sell_value

    # 1. Net buy/sell ratio (0-30 pts)
    if total_value > 0:
        net_ratio   = (buy_value - sell_value) / total_value
        ratio_score = max(0, min(30, round(15 + net_ratio * 15)))
    else:
        ratio_score = 15

    # 2. Buyer/seller count (0-25 pts) -- 10b5-1 sellers excluded
    n_buyers          = len(set(t["insider"] for t in buyers))
    genuine_sellers   = [t for t in sellers if not t.get("likely_10b5_1")]
    n_genuine_sellers = len(set(t["insider"] for t in genuine_sellers))
    n_total           = n_buyers + n_genuine_sellers
    count_score       = round((n_buyers / n_total) * 25) if n_total > 0 else 12

    # 3. Largest single purchase (0-20 pts)
    max_buy    = max((t["value"] for t in buyers), default=0)
    size_score = min(20, _transaction_size_score(max_buy)) if buyers else 0

    # 4. Highest-ranked buyer position (0-15 pts)
    if buyers:
        top_pos   = max(t["position_weight"] for t in buyers)
        pos_score = max(0, min(15, round((top_pos - 0.6) / 1.4 * 15)))
    else:
        pos_score = 0

    # 5. Cluster effect bonus
    # Multiple senior executives buying within 7 days = coordinated confidence.
    cluster_bonus  = 0
    cluster_signal = None
    if buyers:
        senior_keys    = {"ceo", "cfo", "coo", "president", "chairman"}
        senior_buyers  = [t for t in buyers if t.get("position_key") in senior_keys]
        if len(senior_buyers) >= 2:
            dates     = [t.get("date_ts") for t in senior_buyers if t.get("date_ts") is not None]
            clustered = False
            for i in range(len(dates)):
                for j in range(i + 1, len(dates)):
                    try:
                        if abs((dates[i] - dates[j]).days) <= 7:
                            clustered = True
                            break
                    except Exception:
                        pass
                if clustered:
                    break
            if clustered:
                titles         = [t["title"] for t in senior_buyers]
                cluster_bonus  = 15
                cluster_signal = (
                    f"Cluster buy signal: {len(senior_buyers)} senior executives "
                    f"({', '.join(titles[:3])}) bought within 7 days -- "
                    f"strong coordinated confidence, +{cluster_bonus}pts ✅"
                )

    # 6. Baseline
    baseline    = 10
    final_score = max(0, min(100,
        ratio_score + count_score + size_score + pos_score + cluster_bonus + baseline
    ))
    direction = (
        "bullish" if final_score >= 60 else
        "bearish" if final_score <= 40 else
        "neutral"
    )

    # ── Signals ───────────────────────────────────────────────
    n_sellers_all  = len(set(t["insider"] for t in sellers))
    n_10b5_sellers = sum(1 for t in sellers if t.get("likely_10b5_1"))

    signals = []
    n_all    = len(all_transactions)
    n_scored = len(enriched)
    filter_note = (f" ({n_all - n_scored} low-signal filtered, {n_scored} analysed)"
                   if n_all > n_scored else "")
    signals.append(
        f"Insider activity: {n_buyers} buyer(s), {n_sellers_all} seller(s) "
        f"of {n_all} total transactions{filter_note}"
    )
    if n_10b5_sellers > 0:
        signals.append(
            f"📋 10b5-1 plan sales: {n_10b5_sellers} sale(s) flagged as scheduled "
            f"trading plan -- downweighted ×0.3 in scoring ➡️"
        )
    if buy_value > 0 or sell_value > 0:
        net_dir = "net buying" if buy_value > sell_value else "net selling"
        icon    = "✅" if buy_value > sell_value else "⚠️"
        signals.append(
            f"Adjusted value flow: USD {buy_value:,.0f} bought vs "
            f"USD {sell_value:,.0f} effective sold -- {net_dir} {icon}"
        )
    if buyers:
        tb = sorted(
            buyers,
            key=lambda x: x["value"] * x["position_weight"],
            reverse=True
        )[0]
        ownership_str = (
            f" ({tb['ownership_pct']}% of shares)" if tb.get("ownership_pct") else ""
        )
        signals.append(
            f"Top purchase: {tb['insider']} ({tb['title']}) "
            f"-- USD {tb['value']:,.0f}{ownership_str} ✅"
        )
    if cluster_signal:
        signals.append(cluster_signal)
    icon = "✅" if direction == "bullish" else ("⚠️" if direction == "bearish" else "➡️")
    signals.append(f"Overall insider tone: {direction} {icon}")

    return {
        "score":             final_score,
        "direction":         direction,
        "is_scheduled_only": False,
        "plan_ratio":        round(plan_ratio, 2),
        "cluster_bonus":     cluster_bonus,
        "transaction_count": n_all,
        "transactions":      enriched,
        "signals":           signals,
    }
