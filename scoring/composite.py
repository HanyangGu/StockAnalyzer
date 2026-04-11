# ============================================================
# composite.py -- Composite Scoring Engine
# ============================================================
# Combines all analysis dimension scores into one final
# composite investment score and decision quadrant.
#
# Current dimension weights (MACRO_ENABLED = True):
#   Technical   : 47%
#   Fundamental : 27%
#   Sentiment   : 21%
#   Macro       : 5%
#
# Fallback weights (MACRO_ENABLED = False or macro unavailable):
#   Technical   : 50%
#   Fundamental : 30%
#   Sentiment   : 20%
#
# To add future dimensions (e.g. Event-Driven):
#   1. Add WEIGHT_X and THRESHOLD_X to core/weights.py
#   2. Add parameter to get_composite() signature
#   3. Add to weight redistribution logic
#   4. Add to composite score calculation
#   5. Add to decision quadrant logic if needed
# ============================================================

from core.weights import (
    MACRO_ENABLED,
    WEIGHT_TECHNICAL,   WEIGHT_FUNDAMENTAL,   WEIGHT_SENTIMENT,   WEIGHT_MACRO,
    WEIGHT_TECHNICAL_3D, WEIGHT_FUNDAMENTAL_3D, WEIGHT_SENTIMENT_3D,
    THRESHOLD_TECHNICAL, THRESHOLD_FUNDAMENTAL, THRESHOLD_SENTIMENT, THRESHOLD_MACRO,
)


# ============================================================
# Risk Matrix Generator
# ============================================================

def generate_risk_matrix(technical: int,
                         fundamental,
                         sentiment=None,
                         macro=None,
                         event=None,
                         fund_data: dict = None,
                         sentiment_data: dict = None) -> list:
    """
    Generates a structured risk matrix from existing dimension scores.
    No new data sources required -- derived entirely from scores and
    sub-signals already computed by the analysis pipeline.

    Each risk entry:
        {
          "category" : str   -- risk category label
          "level"    : str   -- "high" | "medium" | "low"
          "color"    : str   -- hex color
          "signal"   : str   -- human-readable description
        }

    Risk categories evaluated:
        1. Technical Momentum Risk
        2. Valuation Risk
        3. Debt / Financial Health Risk
        4. Sentiment Divergence Risk
        5. Insider Activity Risk
        6. Volatility Risk (Beta)
        7. Analyst Consensus Risk
        8. Macro Environment Risk (new -- when macro data available)
    """
    risks     = []
    fund      = fund_data      or {}
    sent      = sentiment_data or {}
    breakdown = sent.get("breakdown", {})

    # ── 1. Technical Momentum Risk ────────────────────────────
    if technical < 35:
        risks.append({
            "category": "Technical Momentum",
            "level":    "high",
            "color":    "#FF1744",
            "signal":   f"Technical score {technical}/100 -- strong downtrend, high probability of further decline."
        })
    elif technical < 50:
        risks.append({
            "category": "Technical Momentum",
            "level":    "medium",
            "color":    "#FF9800",
            "signal":   f"Technical score {technical}/100 -- below neutral, price trend is weak."
        })
    else:
        risks.append({
            "category": "Technical Momentum",
            "level":    "low",
            "color":    "#00C853",
            "signal":   f"Technical score {technical}/100 -- trend is supportive, momentum intact."
        })

    # ── 2. Valuation Risk ─────────────────────────────────────
    pe      = fund.get("pe_ratio")
    fpe     = fund.get("forward_pe")
    ps      = fund.get("price_to_sales")
    hi52    = fund.get("52w_high")
    current = fund.get("current_price")

    valuation_risk = "low"
    val_signals    = []

    if pe and pe > 50:
        valuation_risk = "high"
        val_signals.append(f"P/E {pe}x (>50x -- stretched)")
    elif pe and pe > 30:
        valuation_risk = max(valuation_risk, "medium") if valuation_risk != "high" else "high"
        val_signals.append(f"P/E {pe}x (30-50x -- elevated)")

    if fpe and fpe > 40:
        valuation_risk = "high"
        val_signals.append(f"Forward P/E {fpe}x (>40x -- expensive on future earnings)")
    elif fpe and fpe < 0:
        valuation_risk = "high"
        val_signals.append("Forward P/E negative (future losses expected)")

    if ps and ps > 20:
        valuation_risk = max(valuation_risk, "medium") if valuation_risk != "high" else "high"
        val_signals.append(f"P/S {ps}x (>20x -- very high sales multiple)")

    if hi52 and current and (current / hi52) > 0.95:
        val_signals.append("Trading near 52-week high -- limited near-term upside")
        valuation_risk = max(valuation_risk, "medium") if valuation_risk != "high" else "high"

    val_color = {"high": "#FF1744", "medium": "#FF9800", "low": "#00C853"}[valuation_risk]
    risks.append({
        "category": "Valuation",
        "level":    valuation_risk,
        "color":    val_color,
        "signal":   " | ".join(val_signals) if val_signals else "Valuation appears reasonable based on available metrics."
    })

    # ── 3. Financial Health Risk ──────────────────────────────
    de  = fund.get("debt_to_equity")
    cr  = fund.get("current_ratio")
    fcf = fund.get("free_cash_flow")

    health_risk    = "low"
    health_signals = []

    if de is not None:
        if de > 200:
            health_risk = "high"
            health_signals.append(f"D/E ratio {de} -- very high leverage, vulnerable to rate rises")
        elif de > 100:
            health_risk = max(health_risk, "medium") if health_risk != "high" else "high"
            health_signals.append(f"D/E ratio {de} -- elevated leverage")

    if cr is not None and cr < 1:
        health_risk = max(health_risk, "medium") if health_risk != "high" else "high"
        health_signals.append(f"Current ratio {cr} -- short-term liquidity risk")

    if fcf is not None and fcf < 0:
        health_risk = max(health_risk, "medium") if health_risk != "high" else "high"
        health_signals.append("Negative free cash flow -- burning cash")

    h_color = {"high": "#FF1744", "medium": "#FF9800", "low": "#00C853"}[health_risk]
    risks.append({
        "category": "Financial Health",
        "level":    health_risk,
        "color":    h_color,
        "signal":   " | ".join(health_signals) if health_signals else "Balance sheet appears healthy based on available metrics."
    })

    # ── 4. Sentiment Divergence Risk ─────────────────────────
    sent_score = sentiment or 50
    divergence = abs(technical - sent_score)

    if divergence > 35 and technical > sent_score:
        risks.append({
            "category": "Sentiment Divergence",
            "level":    "high",
            "color":    "#FF1744",
            "signal":   f"Technical ({technical}) vs Sentiment ({sent_score}) divergence of {divergence}pts -- price momentum not confirmed by sentiment."
        })
    elif divergence > 20:
        risks.append({
            "category": "Sentiment Divergence",
            "level":    "medium",
            "color":    "#FF9800",
            "signal":   f"Technical ({technical}) vs Sentiment ({sent_score}) divergence of {divergence}pts -- monitor for reversal."
        })
    else:
        risks.append({
            "category": "Sentiment Divergence",
            "level":    "low",
            "color":    "#00C853",
            "signal":   f"Technical and sentiment broadly aligned (divergence {divergence}pts)."
        })

    # ── 5. Insider Activity Risk ──────────────────────────────
    insider          = breakdown.get("insider", {})
    insider_score    = insider.get("score", 50)
    insider_dir      = insider.get("direction", "neutral")
    is_scheduled     = insider.get("is_scheduled_only", False)
    plan_ratio       = insider.get("plan_ratio", 0.0)
    n_10b5           = sum(
        1 for t in insider.get("transactions", [])
        if t.get("likely_10b5_1")
    )
    total_txns = insider.get("transaction_count", 0)

    # 10b5-1 override: scheduled plan selling is not a bearish signal
    if is_scheduled or plan_ratio >= 0.80:
        pct_str = f"{int(plan_ratio * 100)}%" if plan_ratio > 0 else "100%"
        risks.append({
            "category": "Insider Activity",
            "level":    "low",
            "color":    "#00C853",
            "signal":   (
                f"Scheduled trading plans ({pct_str} of sales are 10b5-1) -- "
                f"pre-registered wealth management, not a bearish signal. "
                f"Score neutralised to {insider_score}/100."
            )
        })
    elif insider_score <= 25 and insider_dir == "bearish":
        risks.append({
            "category": "Insider Activity",
            "level":    "high",
            "color":    "#FF1744",
            "signal":   f"Strong insider net selling (score {insider_score}/100) -- non-routine activity detected."
        })
    elif insider_score <= 40:
        flag = f" ({n_10b5} of {total_txns} likely 10b5-1 plans)" if n_10b5 > 0 else ""
        risks.append({
            "category": "Insider Activity",
            "level":    "medium",
            "color":    "#FF9800",
            "signal":   f"Net insider selling (score {insider_score}/100){flag} -- monitor for conviction signals."
        })
    else:
        flag = f" ({n_10b5} likely 10b5-1 routine sales)" if n_10b5 > 0 else ""
        risks.append({
            "category": "Insider Activity",
            "level":    "low",
            "color":    "#00C853",
            "signal":   f"Insider activity neutral or positive (score {insider_score}/100){flag}."
        })

    # ── 6. Volatility Risk ────────────────────────────────────
    beta = fund.get("beta")
    if beta is not None:
        if beta > 2.0:
            risks.append({
                "category": "Volatility",
                "level":    "high",
                "color":    "#FF1744",
                "signal":   f"Beta {beta} -- moves 2x+ vs market, high drawdown risk in downturns."
            })
        elif beta > 1.3:
            risks.append({
                "category": "Volatility",
                "level":    "medium",
                "color":    "#FF9800",
                "signal":   f"Beta {beta} -- above-average market sensitivity, expect amplified moves."
            })
        else:
            risks.append({
                "category": "Volatility",
                "level":    "low",
                "color":    "#00C853",
                "signal":   f"Beta {beta} -- volatility in line with or below market average."
            })

    # ── 7. Analyst Consensus Risk — split into Direction + Dispersion ────
    # Direction consensus and target price dispersion are two independent
    # signals. High dispersion often reflects different time horizons among
    # analysts, not disagreement on direction. Show them separately.
    analyst       = breakdown.get("analyst", {})
    analyst_score = analyst.get("score", 50)
    analyst_dir   = analyst.get("direction", "neutral")
    summary       = analyst.get("summary", {})
    targets       = analyst.get("targets", {})
    t_high        = targets.get("high")
    t_low         = targets.get("low")
    t_mean        = targets.get("mean")

    sb    = summary.get("strong_buy", 0)
    b     = summary.get("buy",        0)
    h     = summary.get("hold",       0)
    s     = summary.get("sell",       0)
    ss    = summary.get("strong_sell",0)
    total_ratings = sb + b + h + s + ss
    bull_pct = round((sb + b) / total_ratings * 100) if total_ratings > 0 else None

    # A. Direction consensus
    if bull_pct is not None:
        if bull_pct >= 80:
            risks.append({"category": "Analyst Direction", "level": "low",
                "color": "#00C853",
                "signal": f"Direction consensus: {bull_pct}% of {total_ratings} analysts bullish -- strong agreement ✅"})
        elif bull_pct >= 60:
            risks.append({"category": "Analyst Direction", "level": "low",
                "color": "#69F0AE",
                "signal": f"Direction consensus: {bull_pct}% of {total_ratings} analysts bullish ✅"})
        elif bull_pct >= 40:
            risks.append({"category": "Analyst Direction", "level": "medium",
                "color": "#FF9800",
                "signal": f"Direction consensus: {bull_pct}% of {total_ratings} analysts bullish -- divided ⚠️"})
        else:
            risks.append({"category": "Analyst Direction", "level": "high",
                "color": "#FF1744",
                "signal": f"Direction consensus: only {bull_pct}% of {total_ratings} analysts bullish ⚠️"})
    elif analyst_score < 40:
        risks.append({"category": "Analyst Direction", "level": "medium",
            "color": "#FF9800",
            "signal": f"Analyst sentiment weak (score {analyst_score}/100) -- limited buy-side conviction ⚠️"})

    # B. Target price dispersion (separate entry)
    if t_high and t_low and t_mean and t_mean > 0:
        dispersion = round((t_high - t_low) / t_mean * 100, 1)
        if dispersion > 60:
            risks.append({"category": "Analyst Target Dispersion", "level": "medium",
                "color": "#FF9800",
                "signal": (f"Target range: ${t_low}–${t_high} (dispersion {dispersion}%) -- "
                           f"wide range reflects different time horizons, not necessarily direction disagreement.")})
        elif dispersion > 30:
            risks.append({"category": "Analyst Target Dispersion", "level": "low",
                "color": "#69F0AE",
                "signal": f"Target range: ${t_low}–${t_high} (dispersion {dispersion}%) -- moderate spread ➡️"})
        else:
            risks.append({"category": "Analyst Target Dispersion", "level": "low",
                "color": "#00C853",
                "signal": f"Target range: ${t_low}–${t_high} (dispersion {dispersion}%) -- analysts tightly aligned ✅"})

    # ── 8. Macro Environment Risk (new) ──────────────────────
    if macro is not None:
        if macro < 30:
            risks.append({
                "category": "Macro Environment",
                "level":    "high",
                "color":    "#FF1744",
                "signal":   f"Macro score {macro}/100 -- strong headwinds (VIX elevated, yield curve stressed, or market risk-off)."
            })
        elif macro < 45:
            risks.append({
                "category": "Macro Environment",
                "level":    "medium",
                "color":    "#FF9800",
                "signal":   f"Macro score {macro}/100 -- moderate headwinds, monitor macro conditions."
            })
        else:
            risks.append({
                "category": "Macro Environment",
                "level":    "low",
                "color":    "#00C853",
                "signal":   f"Macro score {macro}/100 -- macro environment broadly supportive."
            })

    # ── 9. Event Risk ─────────────────────────────────────────
    if event and event.get("available"):
        severity    = event.get("window_severity", "none")
        reliability = event.get("reliability", 1.0)
        window_desc = event.get("window_desc", "")
        event_tag   = event.get("event_tag",   "")
        rel_pct     = int(reliability * 100)

        color_map = {
            "critical": "#FF1744",
            "high":     "#FF9800",
            "medium":   "#FFD740",
            "low":      "#69F0AE",
            "none":     "#00C853",
        }
        level_map = {
            "critical": "high",
            "high":     "high",
            "medium":   "medium",
            "low":      "low",
            "none":     "low",
        }

        risks.append({
            "category": "Event Risk",
            "level":    level_map.get(severity, "low"),
            "color":    color_map.get(severity, "#00C853"),
            "signal":   (
                f"{event_tag} -- signal reliability {rel_pct}%. "
                f"{window_desc}."
            ),
        })

    return risks

# ============================================================
# Composite Score
# ============================================================

def get_composite(technical: int,
                  fundamental=None,
                  sentiment=None,
                  macro=None,
                  event=None,
                  fund_data: dict = None,
                  sentiment_data: dict = None,
                  short_term: int = None) -> dict:
    """
    Combines all dimension scores into one composite investment
    score with quadrant decision label and risk matrix.

    Args:
        technical      : Technical overall score (0-100)
        fundamental    : Fundamental score (0-100) or None
        sentiment      : Sentiment score (0-100) or None
        macro          : Macro score (0-100) or None
        fund_data      : Raw fundamental data dict (for risk matrix)
        sentiment_data : Full sentiment result dict (for risk matrix)
        short_term     : Short-term technical score (0-100) or None.
                         When < 40, overrides Strong Buy to Cautious Buy.

    Returns dict with:
        score        : Composite score (0-100)
        verdict      : Trend label
        color        : Hex color for UI
        quadrant     : Decision label
        action       : Explanation text (timing-aware)
        q_color      : Quadrant hex color
        q_icon       : Quadrant emoji
        weight_label : Active weights used (for UI display)
        risks        : List of risk matrix entries
    """
    has_fund  = fundamental is not None
    has_sent  = sentiment   is not None
    has_macro = macro       is not None and MACRO_ENABLED

    # ── Weight selection ──────────────────────────────────────
    # Start with 4-dimension weights if macro is available,
    # otherwise fall back to 3-dimension weights.
    # Then redistribute proportionally for any missing dimension.

    if has_macro:
        base_tech = WEIGHT_TECHNICAL
        base_fund = WEIGHT_FUNDAMENTAL
        base_sent = WEIGHT_SENTIMENT
        base_mac  = WEIGHT_MACRO
    else:
        base_tech = WEIGHT_TECHNICAL_3D
        base_fund = WEIGHT_FUNDAMENTAL_3D
        base_sent = WEIGHT_SENTIMENT_3D
        base_mac  = 0.0

    # Build active weight pool (only dimensions with data)
    active = {}
    active["tech"] = base_tech
    if has_fund:
        active["fund"] = base_fund
    if has_sent:
        active["sent"] = base_sent
    if has_macro:
        active["mac"]  = base_mac

    # Normalise so weights sum to 1.0
    total = sum(active.values())
    if total > 0:
        active = {k: v / total for k, v in active.items()}

    w_tech = active.get("tech", 1.0)
    w_fund = active.get("fund", 0.0)
    w_sent = active.get("sent", 0.0)
    w_mac  = active.get("mac",  0.0)

    # ── Composite score ───────────────────────────────────────
    comp_score = round(
        technical          * w_tech +
        (fundamental or 0) * w_fund +
        (sentiment   or 0) * w_sent +
        (macro       or 0) * w_mac
    )
    comp_score = max(0, min(100, comp_score))

    # ── Composite verdict ─────────────────────────────────────
    if comp_score >= 75:
        comp_verdict, comp_color = "Strong Uptrend",   "#00C853"
    elif comp_score >= 60:
        comp_verdict, comp_color = "Uptrend",          "#69F0AE"
    elif comp_score >= 40:
        comp_verdict, comp_color = "Neutral",          "#FFD740"
    elif comp_score >= 25:
        comp_verdict, comp_color = "Downtrend",        "#FF6D00"
    else:
        comp_verdict, comp_color = "Strong Downtrend", "#FF1744"

    # ── Decision quadrant ─────────────────────────────────────
    high_t = technical          > THRESHOLD_TECHNICAL
    high_f = (fundamental or 0) > THRESHOLD_FUNDAMENTAL
    high_s = (sentiment   or 0) > THRESHOLD_SENTIMENT
    high_m = (macro       or 0) > THRESHOLD_MACRO if has_macro else True
    # When macro is unavailable, treat it as non-blocking (True)
    # so it doesn't downgrade decisions unfairly.

    if not has_fund and not has_sent:
        quadrant = "Technical Only"
        action   = "Only technical data available -- decision based on price signals only."
        q_color  = "#888888"
        q_icon   = "⬜"
    elif high_t and high_f and (not has_sent or high_s) and high_m:
        # If short-term is overbought/weak despite strong overall score,
        # downgrade title to Cautious Buy so the label itself signals timing risk.
        if short_term is not None and short_term < 40:
            quadrant = "Cautious Buy"
            action   = ("Strong fundamentals and mid/long-term technicals confirm quality. "
                        "Short-term is overbought -- wait for a pullback before entering.")
            q_color  = "#69F0AE"
            q_icon   = "🟢"
        else:
            quadrant = "Strong Buy"
            action   = "Technical, fundamental, and sentiment all agree -- highest conviction entry."
            q_color  = "#00C853"
            q_icon   = "🟢"
    elif high_t and high_f and has_sent and not high_s and high_m:
        quadrant = "Cautious Buy"
        action   = "Strong price and business fundamentals but sentiment is weak -- watch for news catalysts."
        q_color  = "#69F0AE"
        q_icon   = "🟢"
    elif high_t and high_f and not high_m:
        quadrant = "Macro Headwind"
        action   = "Strong technicals and fundamentals but macro environment is unfavourable -- reduce position size."
        q_color  = "#FFD740"
        q_icon   = "🟡"
    elif high_t and not high_f:
        quadrant = "Trader Play"
        action   = "Momentum exists but business fundamentals are weak -- short term only, set a tight stop loss."
        q_color  = "#FFD740"
        q_icon   = "🟡"
    elif not high_t and high_f and high_s:
        quadrant = "Value Opportunity"
        action   = "Solid business with positive sentiment in a technical pullback -- wait for price to stabilize."
        q_color  = "#69F0AE"
        q_icon   = "🔵"
    elif not high_t and high_f and not high_s:
        quadrant = "Value Watch"
        action   = "Good fundamentals but weak technicals and sentiment -- not yet time to enter."
        q_color  = "#FF6D00"
        q_icon   = "🟠"
    else:
        quadrant = "Avoid"
        action   = "Technical, fundamental, and sentiment are all weak -- no clear edge. Stay out."
        q_color  = "#FF1744"
        q_icon   = "🔴"

    # ── Weight label for UI ───────────────────────────────────
    parts = [f"Technical {int(round(w_tech*100))}%"]
    if has_fund:
        parts.append(f"Fundamental {int(round(w_fund*100))}%")
    if has_sent:
        parts.append(f"Sentiment {int(round(w_sent*100))}%")
    if has_macro:
        parts.append(f"Macro {int(round(w_mac*100))}%")
    weight_label = " + ".join(parts)

    # ── Risk matrix ───────────────────────────────────────────
    risks = generate_risk_matrix(
        technical      = technical,
        fundamental    = fundamental,
        sentiment      = sentiment,
        macro          = macro,
        event          = event,
        fund_data      = fund_data,
        sentiment_data = sentiment_data,
    )

    return {
        "score":        comp_score,
        "verdict":      comp_verdict,
        "color":        comp_color,
        "quadrant":     quadrant,
        "action":       action,
        "q_color":      q_color,
        "q_icon":       q_icon,
        "weight_label": weight_label,
        "risks":        risks,
    }
