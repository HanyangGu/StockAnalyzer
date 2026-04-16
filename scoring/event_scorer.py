# ============================================================
# scoring/event_scorer.py -- Event-Driven Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call any external API or yfinance.
# Receives the standardised dict from analyzers/event_driven.py
# and produces a reliability coefficient + event context.
#
# Design philosophy:
#   Event-Driven is NOT a scoring dimension like Technical or
#   Fundamental. It is a RELIABILITY LAYER that answers:
#   "Is right now a good time to trust the other signals?"
#
#   The composite score is NOT changed. Instead, this module
#   outputs a reliability coefficient (0.5 - 1.0) and event
#   context that is used by:
#     1. composite.py  → adds Event Risk entry to risk matrix
#     2. components.py → displays event warning card in UI
#     3. dropdowns.py  → shows full event breakdown
#
#   This mirrors how professional quant desks handle events:
#   models are dampened during event windows, not re-scored.
#
# Time window definitions:
#   POST_EARNINGS_SHOCK   : 0-1 days after  → 0.50 reliability
#   PRE_EARNINGS_IMMINENT : 1-3 days before → 0.65 reliability
#   PRE_EARNINGS_NEAR     : 4-7 days before → 0.80 reliability
#   PRE_EARNINGS_WATCH    : 8-14 days before→ 0.90 reliability
#   POST_EARNINGS_DIGEST  : 2-5 days after  → 0.85 reliability
#   NORMAL                : all other times → 1.00 reliability
#
# Output contract:
# {
#   "reliability":      float   0.50 - 1.00
#   "window":           str     window label (see TIME_WINDOWS)
#   "window_severity":  str     "critical"|"high"|"medium"|"low"|"none"
#   "signals":          list[str]
#   "next_earnings":    dict | None   pass-through from data layer
#   "last_earnings":    dict | None   pass-through from data layer
#   "event_tag":        str     short UI label e.g. "⚠️ Earnings in 3 days"
#   "available":        bool    False if data_quality == "failed"
# }
# ============================================================

from core.weights import (
    EVENT_WINDOW_RELIABILITY,
    EVENT_SURPRISE_BEAT_THRESHOLD,
    EVENT_SURPRISE_MISS_THRESHOLD,
)


# ============================================================
# Time window definitions
# ============================================================
# Each entry: (window_label, severity, reliability, description)
# Evaluated in order -- first match wins.

TIME_WINDOWS = [
    # Post-earnings: most volatile period
    ("POST_EARNINGS_SHOCK",   "critical", 0.50,
     "Earnings just released -- market still digesting, signals unreliable"),

    # Pre-earnings: imminent
    ("PRE_EARNINGS_IMMINENT", "critical", 0.65,
     "Earnings in 1-3 days -- price action driven by event speculation"),

    # Pre-earnings: nearby
    ("PRE_EARNINGS_NEAR",     "high",     0.80,
     "Earnings in 4-7 days -- entering event window, technical signals weakening"),

    # Pre-earnings: on watch
    ("PRE_EARNINGS_WATCH",    "medium",   0.90,
     "Earnings in 8-14 days -- early event awareness, signals mostly valid"),

    # Post-earnings: digestion period
    ("POST_EARNINGS_DIGEST",  "low",      0.85,
     "Recent earnings 2-5 days ago -- market adjusting to new information"),

    # Normal: no nearby event
    ("NORMAL",                "none",     1.00,
     "No imminent earnings event -- signals operating at full reliability"),
]

SEVERITY_COLORS = {
    "critical": "#FF1744",
    "high":     "#FF9800",
    "medium":   "#FFD740",
    "low":      "#69F0AE",
    "none":     "#00C853",
}


# ============================================================
# Window classifier
# ============================================================

def _classify_window(next_earnings: dict | None,
                      last_earnings: dict | None) -> tuple:
    """
    Determines which time window the current date falls into.
    Returns (window_label, severity, reliability, description).
    """
    days_until = next_earnings["days_until"] if next_earnings else None
    days_ago   = last_earnings["days_ago"]   if last_earnings else None

    # Post-earnings shock (0-1 days after)
    if days_ago is not None and days_ago <= 1:
        return TIME_WINDOWS[0]

    # Pre-earnings imminent (1-3 days before)
    if days_until is not None and 1 <= days_until <= 3:
        return TIME_WINDOWS[1]

    # Pre-earnings near (4-7 days before)
    if days_until is not None and 4 <= days_until <= 7:
        return TIME_WINDOWS[2]

    # Pre-earnings watch (8-14 days before)
    if days_until is not None and 8 <= days_until <= 14:
        return TIME_WINDOWS[3]

    # Post-earnings digest (2-5 days after)
    if days_ago is not None and 2 <= days_ago <= 5:
        return TIME_WINDOWS[4]

    # Normal window
    return TIME_WINDOWS[5]


# ============================================================
# Signal builders
# ============================================================

def _build_signals(window_label: str,
                   window_desc:  str,
                   next_earnings: dict | None,
                   last_earnings: dict | None,
                   reliability:  float) -> list:
    """Builds human-readable signal strings for the event context."""
    signals = []

    # Reliability statement
    rel_pct = int(reliability * 100)
    if reliability < 1.0:
        signals.append(
            f"Signal reliability: {rel_pct}% -- {window_desc} ⚠️"
        )
    else:
        signals.append(
            f"Signal reliability: {rel_pct}% -- {window_desc} ✅"
        )

    # Next earnings context
    if next_earnings:
        days_until = next_earnings["days_until"]
        date_str   = next_earnings["date"]

        if days_until > 0:
            eps_range = ""
            if next_earnings.get("estimate_eps_low") and next_earnings.get("estimate_eps_high"):
                eps_range = (
                    f" (EPS estimate: ${next_earnings['estimate_eps_low']:.2f}"
                    f" - ${next_earnings['estimate_eps_high']:.2f})"
                )
            signals.append(
                f"Next earnings: {date_str} ({days_until} days){eps_range} 📅"
            )
        elif days_until == 0:
            signals.append(f"Earnings TODAY ({date_str}) -- extreme caution ⚠️")
        else:
            signals.append(
                f"Earnings date passed ({date_str}) -- awaiting next cycle 📅"
            )

    # Last earnings context
    if last_earnings:
        days_ago     = last_earnings["days_ago"]
        surprise_pct = last_earnings.get("surprise_pct")
        actual_eps   = last_earnings.get("actual_eps")
        estimate_eps = last_earnings.get("estimate_eps")
        date_str     = last_earnings["date"]

        surprise_str = ""
        if surprise_pct is not None:
            if surprise_pct >= EVENT_SURPRISE_BEAT_THRESHOLD:
                icon         = "✅"
                surprise_str = f" -- beat by {surprise_pct:+.1f}% {icon}"
            elif surprise_pct <= EVENT_SURPRISE_MISS_THRESHOLD:
                icon         = "⚠️"
                surprise_str = f" -- missed by {abs(surprise_pct):.1f}% {icon}"
            else:
                icon         = "➡️"
                surprise_str = f" -- in-line ({surprise_pct:+.1f}%) {icon}"

        eps_str = ""
        if actual_eps is not None and estimate_eps is not None:
            eps_str = f" (actual ${actual_eps:.2f} vs. est ${estimate_eps:.2f})"

        signals.append(
            f"Last earnings: {date_str} ({days_ago} days ago){eps_str}{surprise_str}"
        )

    # Window-specific advice
    if window_label == "POST_EARNINGS_SHOCK":
        signals.append(
            "Caution: price action in the 24h post-earnings is highly volatile. "
            "Wait for the dust to settle before entering new positions. ⚠️"
        )
    elif window_label == "PRE_EARNINGS_IMMINENT":
        signals.append(
            "Caution: entering a position now means taking on earnings risk. "
            "Technical and sentiment signals are being distorted by event speculation. ⚠️"
        )
    elif window_label == "PRE_EARNINGS_NEAR":
        signals.append(
            "Note: stock is entering its earnings window. "
            "Consider waiting for post-earnings clarity before adding new exposure. ➡️"
        )
    elif window_label == "POST_EARNINGS_DIGEST":
        signals.append(
            "Note: market is still adjusting to the recent earnings report. "
            "Signals should stabilise within a few days. ➡️"
        )

    return signals


def _build_event_tag(window_label: str,
                     window_severity: str,
                     next_earnings: dict | None,
                     last_earnings: dict | None) -> str:
    """Builds a short UI tag string shown on the score cards."""
    if window_label == "NORMAL":
        if next_earnings and next_earnings["days_until"] > 0:
            return f"📅 Earnings in {next_earnings['days_until']}d"
        return "✅ No event risk"

    icon_map = {
        "critical": "🔴",
        "high":     "🟠",
        "medium":   "🟡",
        "low":      "🟢",
    }
    icon = icon_map.get(window_severity, "➡️")

    if "PRE" in window_label and next_earnings:
        days = next_earnings["days_until"]
        return f"{icon} Earnings in {days}d"
    elif "POST" in window_label and last_earnings:
        days = last_earnings["days_ago"]
        return f"{icon} Post-earnings ({days}d ago)"
    else:
        return f"{icon} Event window active"


# ============================================================
# Master scoring function
# ============================================================

def score_event(data: dict) -> dict:
    """
    Produces event reliability coefficient and context from fetch_event_data().

    Args:
        data : standardised dict from analyzers/event_driven.py

    Returns:
        Event context dict (see module docstring for contract).
    """
    data_quality  = data.get("data_quality",  "failed")
    next_earnings = data.get("next_earnings")
    last_earnings = data.get("last_earnings")

    # Failed: no event data available
    if data_quality == "failed":
        return {
            "reliability":     1.0,
            "window":          "NORMAL",
            "window_severity": "none",
            "signals":         ["Event data unavailable -- reliability unaffected ➡️"],
            "next_earnings":   None,
            "last_earnings":   None,
            "event_tag":       "📅 No event data",
            "available":       False,
        }

    # Classify current time window
    window_label, severity, reliability, description = _classify_window(
        next_earnings, last_earnings
    )

    # Override reliability from weights.py if configured
    reliability = EVENT_WINDOW_RELIABILITY.get(window_label, reliability)

    signals   = _build_signals(
        window_label, description,
        next_earnings, last_earnings,
        reliability
    )
    event_tag = _build_event_tag(
        window_label, severity,
        next_earnings, last_earnings
    )

    return {
        "reliability":     reliability,
        "window":          window_label,
        "window_severity": severity,
        "window_color":    SEVERITY_COLORS.get(severity, "#888888"),
        "window_desc":     description,
        "signals":         signals,
        "next_earnings":   next_earnings,
        "last_earnings":   last_earnings,
        "event_tag":       event_tag,
        "available":       True,
    }
