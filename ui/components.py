# ============================================================
# ui/components.py -- Shared UI Primitives
# ============================================================
# Small reusable render functions used across multiple views:
#   get_score_color      : score → hex color
#   render_price_line    : colored price + change display
#   render_score_cards   : four main dimension score cards
#   render_decision_panel: composite score + quadrant decision
# ============================================================

import streamlit as st
from scoring.composite import get_composite


def get_score_color(score: int) -> str:
    if score >= 75:   return "#00C853"
    elif score >= 60: return "#69F0AE"
    elif score >= 40: return "#FFD740"
    elif score >= 25: return "#FF6D00"
    else:             return "#FF1744"


def render_price_line(data: dict):
    """Renders price with colored up/down arrow and data timestamp."""
    price  = data["current_price"]
    change = data["price_change"]
    pct    = data["price_change_pct"]
    arrow  = "▲" if change >= 0 else "▼"
    color  = "#00C853" if change >= 0 else "#FF1744"
    ts     = data.get("timestamp", "")
    ts_str = f"<span style='color:#555;font-size:12px;margin-left:16px;'>Data as of: {ts}</span>" if ts else ""
    st.markdown(f"""
    <div style="font-size:16px;margin:10px 0;">
        <b>Price:</b> ${price}
        <span style="color:{color};">
            {arrow} {abs(change)} ({abs(pct)}%)
        </span>
        {ts_str}
    </div>
    """, unsafe_allow_html=True)


def _score_card_html(label: str, score, icon: str,
                     verdict: str, color: str,
                     subtitle: str = "out of 100") -> str:
    """Returns HTML for a single score card."""
    disp = score if score is not None else "--"
    return f"""
    <div style="
        border: 2px solid {color};
        border-radius: 14px;
        padding: 22px 16px;
        text-align: center;
        background: rgba(0,0,0,0.2);
        height: 100%;">
        <div style="color:#aaa;font-size:13px;margin-bottom:4px;">
            {label}
        </div>
        <div style="
            color:{color};
            font-size:48px;
            font-weight:800;
            line-height:1.1;">
            {disp}
        </div>
        <div style="color:#aaa;font-size:11px;">{subtitle}</div>
        <div style="margin-top:8px;font-size:14px;font-weight:600;color:{color};">
            {icon} {verdict}
        </div>
    </div>
    """


def render_score_cards(data: dict):
    """
    Renders main dimension score cards.
    Shows 4 cards when macro data is available (Tech / Fund / Sent / Macro),
    or 3 cards when macro is absent (Tech / Fund / Sent).
    """
    tech       = data["overall"]
    fund       = data.get("fundamental", {})
    sent       = data.get("sentiment",   {})
    macro      = data.get("macro")

    fund_score = fund.get("score")
    sent_score = sent.get("score")
    mac_score  = macro.get("score") if macro else None
    mac_env    = macro.get("env_score") if macro else None

    tcolor = get_score_color(tech["score"])

    # Determine layout: 4 columns if macro present, 3 otherwise
    has_macro = mac_score is not None
    cols = st.columns(4) if has_macro else st.columns(3)

    # Technical
    cols[0].markdown(
        _score_card_html("📊 Technical", tech["score"],
                         tech["icon"], tech["verdict"], tcolor),
        unsafe_allow_html=True
    )

    # Fundamental
    if fund_score is not None:
        fcolor   = get_score_color(fund_score)
        ficon    = fund.get("icon",    "➡️")
        fverdict = fund.get("verdict", "")
    else:
        fcolor, ficon, fverdict = "#888888", "➡️", "No data"

    cols[1].markdown(
        _score_card_html("🏦 Fundamental", fund_score,
                         ficon, fverdict, fcolor),
        unsafe_allow_html=True
    )

    # Sentiment
    if sent_score is not None:
        scolor   = get_score_color(sent_score)
        sicon    = sent.get("icon",    "➡️")
        sverdict = sent.get("verdict", "")
    else:
        scolor, sicon, sverdict = "#888888", "➡️", "No data"

    cols[2].markdown(
        _score_card_html("🗞️ Sentiment", sent_score,
                         sicon, sverdict, scolor),
        unsafe_allow_html=True
    )

    # Macro (4th card, only when available)
    if has_macro:
        mcolor   = get_score_color(mac_score)
        micon    = macro.get("icon",    "➡️")
        mverdict = macro.get("verdict", "")
        # Show env_score as subtitle context
        subtitle = f"env: {mac_env}/100" if mac_env is not None else "out of 100"
        cols[3].markdown(
            _score_card_html("🌐 Macro", mac_score,
                             micon, mverdict, mcolor,
                             subtitle=subtitle),
            unsafe_allow_html=True
        )



def render_event_banner(data: dict):
    """
    Renders an event warning banner when the stock is in an event window.
    Shown between score cards and investment decision panel.
    Only renders when reliability < 1.0 (i.e. non-normal window).
    """
    event = data.get("event")
    if not event or not event.get("available"):
        return

    reliability = event.get("reliability", 1.0)
    if reliability >= 1.0:
        # Normal window -- show subtle next earnings info only
        tag = event.get("event_tag", "")
        if tag and "No event" not in tag:
            st.caption(f"📅 {tag}")
        return

    # Event window active -- show prominent banner
    severity    = event.get("window_severity", "low")
    window_desc = event.get("window_desc", "")
    event_tag   = event.get("event_tag",   "")
    rel_pct     = int(reliability * 100)
    color       = event.get("window_color", "#FF9800")

    next_e = event.get("next_earnings")
    last_e = event.get("last_earnings")

    detail_parts = []
    if next_e and next_e.get("days_until", 9999) > 0:
        detail_parts.append(f"Next earnings: **{next_e['date']}** ({next_e['days_until']} days)")
    if last_e:
        surprise = last_e.get("surprise_pct")
        surprise_str = f" | EPS surprise: {surprise:+.1f}%" if surprise is not None else ""
        detail_parts.append(f"Last earnings: {last_e['date']}{surprise_str}")

    detail_str = "  ·  ".join(detail_parts)

    st.markdown(
        f"<div style='"
        f"border-left: 4px solid {color};"
        f"background: rgba(255,255,255,0.04);"
        f"border-radius: 6px;"
        f"padding: 12px 16px;"
        f"margin: 8px 0 16px 0;'>"
        f"<span style='color:{color};font-weight:700;font-size:14px;'>"
        f"⚠️ {event_tag}</span>"
        f"<span style='color:#aaa;font-size:13px;margin-left:12px;'>"
        f"Signal reliability: {rel_pct}%</span><br>"
        f"<span style='color:#bbb;font-size:12px;'>{window_desc}</span><br>"
        f"<span style='color:#888;font-size:11px;'>{detail_str}</span>"
        f"</div>",
        unsafe_allow_html=True
    )


def render_decision_panel(data: dict):
    """
    Renders the composite investment score + quadrant decision panel.
    This is the main 'should I invest?' answer.
    """
    tech_score = data["overall"]["score"]
    fund_score = data.get("fundamental", {}).get("score")
    sent_score = data.get("sentiment",   {}).get("score")
    macro_data = data.get("macro")
    mac_score  = macro_data.get("score") if macro_data else None

    comp = get_composite(
        technical   = tech_score,
        fundamental = fund_score,
        sentiment   = sent_score,
        macro       = mac_score,
    )

    st.markdown("---")
    st.markdown("#### Investment Decision")

    col_score, col_quad = st.columns([1, 2])

    with col_score:
        st.markdown(f"""
        <div style="
            border: 2px solid {comp['color']};
            border-radius: 16px;
            padding: 24px 16px;
            text-align: center;
            background: rgba(0,0,0,0.25);">
            <div style="color:#aaa;font-size:13px;margin-bottom:4px;">
                Composite Score
            </div>
            <div style="color:#aaa;font-size:11px;margin-bottom:6px;">
                {comp['weight_label']}
            </div>
            <div style="
                color:{comp['color']};
                font-size:56px;
                font-weight:800;
                line-height:1.1;">
                {comp['score']}
            </div>
            <div style="color:#aaa;font-size:11px;">out of 100</div>
            <div style="
                margin-top:10px;
                font-size:16px;
                font-weight:600;
                color:{comp['color']};">
                {comp['verdict']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_quad:
        # Build dimension breakdown line
        dim_parts = [f"Technical: {tech_score}/100"]
        if fund_score is not None:
            dim_parts.append(f"Fundamental: {fund_score}/100")
        if sent_score is not None:
            dim_parts.append(f"Sentiment: {sent_score}/100")
        if mac_score is not None:
            dim_parts.append(f"Macro: {mac_score}/100")
        dim_line = " &nbsp;|&nbsp; ".join(dim_parts)

        st.markdown(f"""
        <div style="
            border: 2px solid {comp['q_color']};
            border-radius: 16px;
            padding: 24px 20px;
            background: rgba(0,0,0,0.25);
            height: 100%;">
            <div style="color:#aaa;font-size:13px;margin-bottom:8px;">
                Decision
            </div>
            <div style="
                font-size:28px;
                font-weight:700;
                color:{comp['q_color']};
                margin-bottom:12px;">
                {comp['q_icon']} {comp['quadrant']}
            </div>
            <div style="
                color:#ccc;
                font-size:15px;
                line-height:1.6;">
                {comp['action']}
            </div>
            <div style="
                margin-top:16px;
                color:#666;
                font-size:11px;">
                {dim_line}
            </div>
        </div>
        """, unsafe_allow_html=True)
