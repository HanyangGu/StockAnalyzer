# ============================================================
# ui/dropdowns.py -- Expandable Breakdown Dropdowns
# ============================================================
# Three collapsible analysis breakdown panels:
#   render_technical_dropdown   : short/mid/long score cards + signals
#   render_fundamental_dropdown : valuation/profitability/growth/health
#   render_sentiment_dropdown   : analyst + insider + options + news
# ============================================================

import streamlit as st
from ui.components import get_score_color


def _md_safe(s: str) -> str:
    """
    Escapes dollar signs in signal strings so Streamlit's Markdown
    renderer does not interpret $X...Y$ as LaTeX math (italic/bold).
    Called on every signal string before st.markdown().
    """
    return s.replace("$", r"\$")


def render_technical_dropdown(data: dict):
    """
    Expandable Technical breakdown dropdown.
    Shows three time horizon score cards + signal lists.
    """
    with st.expander("📊 Technical Breakdown"):
        horizons = [
            ("Short term", data["short_term"]),
            ("Mid term",   data["mid_term"]),
            ("Long term",  data["long_term"]),
        ]
        cols = st.columns(3)
        for col, (label, h) in zip(cols, horizons):
            color = get_score_color(h["score"])
            with col:
                st.markdown(f"""
                <div style="
                    border: 1px solid {color};
                    border-radius: 10px;
                    padding: 16px;
                    text-align: center;
                    background: rgba(0,0,0,0.2);
                    margin-bottom: 16px;">
                    <div style="color:#aaa;font-size:12px;">
                        {label}
                    </div>
                    <div style="
                        color:{color};
                        font-size:38px;
                        font-weight:700;
                        line-height:1.1;">
                        {h["score"]}
                    </div>
                    <div style="color:#aaa;font-size:10px;">
                        out of 100
                    </div>
                    <div style="margin-top:6px;font-size:13px;color:{color};">
                        {h["icon"]} {h["verdict"]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        sig_cols = st.columns(3)
        for col, (label, h) in zip(sig_cols, horizons):
            with col:
                st.markdown(f"**{label} signals**")
                for s in h["signals"]:
                    st.markdown(f"- {_md_safe(s)}")


def render_fundamental_dropdown(data: dict):
    """
    Expandable Fundamental breakdown dropdown.
    Shows fundamental signals + four data columns.
    """
    fund    = data.get("fundamental", {})
    details = data.get("fund_details", {})

    if not details:
        return

    with st.expander("🏦 Fundamental Breakdown"):

        if fund.get("signals"):
            st.markdown("**Fundamental Signals**")
            for s in fund["signals"]:
                st.markdown(f"- {_md_safe(s)}")
            st.markdown("")

        # Narrative signals (PEG, Beta, 52w position, analyst target)
        narrative = fund.get("narrative", [])
        if narrative:
            st.markdown("**Business Context**")
            cols_n = st.columns(len(narrative)) if len(narrative) <= 4 else st.columns(4)
            for i, item in enumerate(narrative):
                with cols_n[i % len(cols_n)]:
                    st.info(item)
            st.markdown("")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**Valuation**")
            v = details.get("valuation", {})
            st.metric("P/E Ratio",   v.get("pe_ratio")       or "N/A")
            st.metric("Forward P/E", v.get("forward_pe")     or "N/A")
            st.metric("Price/Book",  v.get("price_to_book")  or "N/A")
            st.metric("Price/Sales", v.get("price_to_sales") or "N/A")

        with col2:
            st.markdown("**Profitability**")
            p = details.get("profitability", {})
            st.metric("Gross Margin", f"{p.get('gross_margin')}%"  if p.get("gross_margin")  else "N/A")
            st.metric("Net Margin",   f"{p.get('net_margin')}%"    if p.get("net_margin")    else "N/A")
            st.metric("ROE",          f"{p.get('roe')}%"           if p.get("roe")           else "N/A")
            st.metric("ROA",          f"{p.get('roa')}%"           if p.get("roa")           else "N/A")

        with col3:
            st.markdown("**Growth**")
            g = details.get("growth", {})
            st.metric("Revenue Growth",  f"{g.get('revenue_growth')}%"  if g.get("revenue_growth")  else "N/A")
            st.metric("Earnings Growth", f"{g.get('earnings_growth')}%" if g.get("earnings_growth") else "N/A")
            st.metric("EPS (TTM)",       g.get("eps")         or "N/A")
            st.metric("Forward EPS",     g.get("forward_eps") or "N/A")

        with col4:
            st.markdown("**Health & Analyst**")
            h = details.get("health", {})
            a = details.get("analyst", {})
            st.metric("Debt/Equity",    h.get("debt_to_equity") or "N/A")
            st.metric("Current Ratio",  h.get("current_ratio")  or "N/A")
            st.metric("Analyst Target", f"${a.get('target_price')}" if a.get("target_price") else "N/A")
            upside = a.get("upside_pct")
            st.metric(
                "Upside Potential",
                f"{upside}%" if upside is not None else "N/A",
                delta=f"{upside}%" if upside is not None else None
            )

        # ── Sector peer reference benchmarks ─────────────────
        # Static industry averages updated quarterly.
        # Full peer comparison module (live data) is on the roadmap.
        _SECTOR_BENCHMARKS = {
            "Technology":             {"fwd_pe": 25, "ps": 6,  "gross_margin": 55, "net_margin": 18, "rev_growth": 12},
            "Semiconductors":         {"fwd_pe": 22, "ps": 7,  "gross_margin": 52, "net_margin": 20, "rev_growth": 15},
            "Consumer Cyclical":      {"fwd_pe": 18, "ps": 1,  "gross_margin": 35, "net_margin": 5,  "rev_growth": 7},
            "Communication Services": {"fwd_pe": 20, "ps": 3,  "gross_margin": 50, "net_margin": 12, "rev_growth": 8},
            "Healthcare":             {"fwd_pe": 17, "ps": 3,  "gross_margin": 58, "net_margin": 14, "rev_growth": 8},
            "Financial Services":     {"fwd_pe": 13, "ps": 2,  "gross_margin": 45, "net_margin": 22, "rev_growth": 6},
            "Energy":                 {"fwd_pe": 12, "ps": 1,  "gross_margin": 30, "net_margin": 8,  "rev_growth": 5},
            "Industrials":            {"fwd_pe": 18, "ps": 2,  "gross_margin": 33, "net_margin": 8,  "rev_growth": 6},
            "Consumer Defensive":     {"fwd_pe": 19, "ps": 1,  "gross_margin": 35, "net_margin": 7,  "rev_growth": 4},
            "Real Estate":            {"fwd_pe": 20, "ps": 5,  "gross_margin": 60, "net_margin": 15, "rev_growth": 5},
            "Basic Materials":        {"fwd_pe": 14, "ps": 1,  "gross_margin": 28, "net_margin": 8,  "rev_growth": 5},
            "Utilities":              {"fwd_pe": 16, "ps": 2,  "gross_margin": 40, "net_margin": 12, "rev_growth": 3},
        }
        # Sector name is stored in fund_details.valuation via orchestrator
        # Attempt multiple lookup paths for robustness
        _sector_name = (
            data.get("sector") or
            data.get("fund_details", {}).get("sector") or
            None
        )
        # Also try from fundamental signals as fallback (not ideal but safe)
        if not _sector_name:
            for sig in data.get("fundamental", {}).get("signals", []):
                if "Technology" in sig or "Healthcare" in sig or "Energy" in sig:
                    for s in _SECTOR_BENCHMARKS:
                        if s in sig:
                            _sector_name = s
                            break
                    break

        bench = _SECTOR_BENCHMARKS.get(_sector_name)
        if bench:
            st.markdown("")
            st.markdown(
                f"**Sector Benchmarks** *({_sector_name} industry averages — updated quarterly)*"
            )
            b1, b2, b3, b4, b5 = st.columns(5)
            with b1: st.metric("Sector Fwd P/E",     f"~{bench['fwd_pe']}x")
            with b2: st.metric("Sector P/S",          f"~{bench['ps']}x")
            with b3: st.metric("Sector Gross Margin", f"~{bench['gross_margin']}%")
            with b4: st.metric("Sector Net Margin",   f"~{bench['net_margin']}%")
            with b5: st.metric("Sector Rev Growth",   f"~{bench['rev_growth']}%")
            st.caption(
                "⚠️ These are broad sector averages. For precise peer comparison "
                "(NVDA vs AMD vs TSMC), a full peer analysis module is on the roadmap."
            )

        # Risk Matrix
        risks = data.get("composite", {}).get("risks", [])
        if risks:
            st.markdown("")
            st.markdown("**Risk Matrix**")
            level_order = {"high": 0, "medium": 1, "low": 2}
            sorted_risks = sorted(risks, key=lambda r: level_order.get(r["level"], 3))
            for r in sorted_risks:
                level  = r["level"].upper()
                color  = r["color"]
                cat    = r["category"]
                signal = r["signal"]
                st.markdown(
                    f"<div style='border-left: 4px solid {color}; padding: 8px 12px; "
                    f"margin-bottom: 8px; background: rgba(0,0,0,0.15); border-radius: 4px;'>"
                    f"<span style='color:{color}; font-weight:700; font-size:12px;'>{level}</span>"
                    f"<span style='color:#aaa; font-size:12px;'> · {cat}</span><br>"
                    f"<span style='color:#ddd; font-size:13px;'>{signal}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )


def render_sentiment_dropdown(data: dict):
    """
    Expandable Sentiment breakdown dropdown.
    Layout:
      1. News signals
      2. Analyst card + signals + distribution + targets
      3. Insider card + signals + transaction list
      4. Options card + signals + PCR metrics
      5. News card + articles
    """
    sent      = data.get("sentiment", {})
    breakdown = sent.get("breakdown", {})
    news      = breakdown.get("news",    {})
    analyst   = breakdown.get("analyst", {})
    insider   = breakdown.get("insider", {})
    options   = breakdown.get("options", {})
    articles  = news.get("articles",      [])
    txns      = insider.get("transactions", [])

    if not sent:
        return

    def _score_card(col, label, score, direction):
        color   = get_score_color(score) if score is not None else "#888888"
        disp    = score if score is not None else "--"
        if score is None:
            icon, verdict = "➡️", "No data"
        else:
            icon    = "✅" if direction == "bullish" else ("⚠️" if direction == "bearish" else "➡️")
            verdict = "Bullish" if direction == "bullish" else ("Bearish" if direction == "bearish" else "Neutral")
        with col:
            st.markdown(
                f"<div style='border:1px solid {color};border-radius:10px;"
                f"padding:16px;text-align:center;background:rgba(0,0,0,0.2);margin-bottom:16px;'>"
                f"<div style='color:#aaa;font-size:12px;'>{label}</div>"
                f"<div style='color:{color};font-size:38px;font-weight:700;line-height:1.1;'>{disp}</div>"
                f"<div style='color:#aaa;font-size:10px;'>out of 100</div>"
                f"<div style='margin-top:6px;font-size:13px;color:{color};'>{icon} {verdict}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    with st.expander("🗞️ Sentiment Breakdown"):

        # -- 2. Analyst section -------------------------------
        st.markdown("---")
        analyst_score = analyst.get("score") if analyst else None
        analyst_dir   = analyst.get("direction", "neutral") if analyst else "neutral"

        col_card, col_detail = st.columns([1, 2])
        _score_card(col_card, "📋 Analyst", analyst_score, analyst_dir)

        with col_detail:
            if analyst and analyst.get("rating_count", 0) > 0:
                for s in analyst.get("signals", []):
                    st.markdown(f"- {_md_safe(s)}")
                st.markdown("")
                summary = analyst.get("summary", {})
                if summary:
                    sb = summary.get("strong_buy",  0)
                    b  = summary.get("buy",         0)
                    h  = summary.get("hold",        0)
                    s  = summary.get("sell",        0)
                    ss = summary.get("strong_sell", 0)
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1: st.metric("Strong Buy",  sb)
                    with c2: st.metric("Buy",         b)
                    with c3: st.metric("Hold",        h)
                    with c4: st.metric("Sell",        s)
                    with c5: st.metric("Strong Sell", ss)
                targets = analyst.get("targets", {})
                if targets.get("mean"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Mean Target", f"${round(targets['mean'], 2)}")
                    with c2:
                        st.metric("High Target", f"${round(targets['high'], 2)}" if targets.get("high") else "N/A")
                    with c3:
                        st.metric("Low Target",  f"${round(targets['low'],  2)}" if targets.get("low")  else "N/A")
            else:
                st.caption("No analyst rating data available.")

        # -- 3. Insider section -------------------------------
        st.markdown("---")
        insider_score = insider.get("score") if insider else None
        insider_dir   = insider.get("direction", "neutral") if insider else "neutral"

        col_card2, col_signals = st.columns([1, 2])
        _score_card(col_card2, "👤 Insider", insider_score, insider_dir)

        with col_signals:
            if insider and insider.get("transaction_count", 0) > 0:
                for s in insider.get("signals", []):
                    st.markdown(f"- {_md_safe(s)}")
            else:
                st.caption("No insider transaction data available.")

        # Transactions table — full width below cards
        if insider and insider.get("transaction_count", 0) > 0 and txns:
            st.markdown("**Transactions**")
            import pandas as pd
            rows = []
            for t in txns:
                is_buy       = t.get("is_buy",        False)
                is_sell      = t.get("is_sell",       False)
                likely_10b5  = t.get("likely_10b5_1", False)
                icon         = "✅" if is_buy else ("⚠️" if is_sell else "➡️")
                plan_tag     = " 📋" if likely_10b5 else ""
                signal       = t.get("signal",        "neutral")
                strength     = t.get("strength",      "weak")
                value        = t.get("value",         0)
                shares       = t.get("shares",        0)
                ownership    = t.get("ownership_pct")
                ownership_str = f"{ownership}%" if ownership is not None else "N/A"
                rows.append({
                    ""          : icon,
                    "Insider"   : t.get("insider", "Unknown"),
                    "Title"     : t.get("title", ""),
                    "Type"      : t.get("transaction_type", "") + plan_tag,
                    "Shares"    : f"{shares:,}" if shares else "N/A",
                    "Value"     : f"USD {value:,.0f}" if value else "N/A",
                    "Holdings%" : ownership_str,
                    "Date"      : t.get("date_str", ""),
                    "Signal"    : f"{signal} ({strength})",
                    "Analysis"  : t.get("reason", ""),
                })
            df = pd.DataFrame(rows)
            st.caption("📋 = likely 10b5-1 scheduled trading plan (downweighted in scoring)")
            st.dataframe(
                df,
                use_container_width = True,
                hide_index          = True,
                column_config       = {
                    ""          : st.column_config.TextColumn("",           width=30),
                    "Insider"   : st.column_config.TextColumn("Insider",    width=130),
                    "Title"     : st.column_config.TextColumn("Title",      width=150),
                    "Type"      : st.column_config.TextColumn("Type",       width=100),
                    "Shares"    : st.column_config.TextColumn("Shares",     width=90),
                    "Value"     : st.column_config.TextColumn("Value",      width=130),
                    "Holdings%" : st.column_config.TextColumn("Holdings%",  width=80),
                    "Date"      : st.column_config.TextColumn("Date",       width=90),
                    "Signal"    : st.column_config.TextColumn("Signal",     width=120),
                    "Analysis"  : st.column_config.TextColumn("Analysis",   width=280),
                }
            )

        # -- 4. Options section -------------------------------
        st.markdown("---")
        options_score = options.get("score") if options else None
        options_dir   = options.get("direction", "neutral") if options else "neutral"

        col_card3, col_opts = st.columns([1, 2])
        _score_card(col_card3, "📈 Options", options_score, options_dir)

        with col_opts:
            if options and options.get("expiry"):
                for s in options.get("signals", []):
                    st.markdown(f"- {_md_safe(s)}")
                st.markdown("")
                pcr_vol    = options.get("pcr_volume")
                pcr_oi     = options.get("pcr_oi")
                avg_iv     = options.get("avg_iv")
                iv_mult    = options.get("iv_multiplier", 1.0)
                max_pain   = options.get("max_pain")
                mp_dist    = options.get("max_pain_dist")
                call_wall  = options.get("call_wall")
                put_wall   = options.get("put_wall")

                # Row 1: PCR + IV metrics
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("PCR Volume", round(pcr_vol, 2) if pcr_vol else "N/A")
                with c2: st.metric("PCR OI",     round(pcr_oi,  2) if pcr_oi  else "N/A")
                with c3: st.metric("Avg IV",     f"{avg_iv}%"      if avg_iv  else "N/A")
                with c4: st.metric("IV Mult",    f"×{iv_mult}")

                # Row 2: Max Pain + Walls
                c5, c6, c7 = st.columns(3)
                with c5:
                    mp_delta = f"{mp_dist:+.1f}% from price" if mp_dist is not None else None
                    st.metric("Max Pain", f"${max_pain}" if max_pain else "N/A", delta=mp_delta)
                with c6:
                    st.metric("Call Wall (Resistance)", f"${call_wall}" if call_wall else "N/A")
                with c7:
                    st.metric("Put Wall (Support)", f"${put_wall}" if put_wall else "N/A")
            else:
                st.caption("No options data available.")

        # -- 5. News articles ---------------------------------
        st.markdown("---")
        news_score = news.get("score", 50)
        news_dir   = news.get("direction", "neutral")

        # Top row: score card + summary signals
        col_card4, col_news_summary = st.columns([1, 2])
        _score_card(col_card4, "🗞️ News", news_score, news_dir)

        with col_news_summary:
            news_signals = news.get("signals", [])
            if news_signals:
                for s in news_signals:
                    st.markdown(f"- {_md_safe(s)}")
            else:
                st.caption("No news signals available.")

        # Bottom: articles in 2 columns
        if articles:
            st.markdown("**News Articles Analysed**")

            def _render_article(a):
                relevance   = a.get("relevance", "unrelated")
                sentiment_a = a.get("sentiment", "neutral")
                if relevance == "unrelated":
                    icon, opacity, rel_tag = "⬜", "0.4", " *(unrelated)*"
                elif relevance == "indirect":
                    icon    = "↗️" if sentiment_a == "positive" else ("↘️" if sentiment_a == "negative" else "➡️")
                    opacity, rel_tag = "0.75", " *(indirect)*"
                else:
                    icon    = "✅" if sentiment_a == "positive" else ("⚠️" if sentiment_a == "negative" else "➡️")
                    opacity, rel_tag = "1.0", ""
                title_a  = a.get("title",       "")[:65]
                source   = a.get("source",      "")
                impact   = a.get("impact",      "normal")
                time_w   = a.get("time_weight", 1.0)
                reason_a = a.get("reason",      "")
                st.markdown(
                    f"<div style='opacity:{opacity};margin-bottom:12px;"
                    f"border-left:2px solid rgba(255,255,255,0.08);padding-left:8px;'>"
                    f"{icon} <b>{title_a}</b>{rel_tag}<br>"
                    f"<span style='color:#888;font-size:11px;'>"
                    f"{source} &nbsp;|&nbsp; {impact} &nbsp;|&nbsp; tw:{time_w}"
                    f"</span><br>"
                    f"<span style='color:#aaa;font-size:11px;font-style:italic;'>{reason_a}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # Split articles into two columns
            mid   = (len(articles) + 1) // 2
            left  = articles[:mid]
            right = articles[mid:]

            col_left, col_right = st.columns(2)
            with col_left:
                for a in left:
                    _render_article(a)
            with col_right:
                for a in right:
                    _render_article(a)
        else:
            st.caption("No news articles available.")



def render_macro_dropdown(data: dict):
    """
    Expandable Macro Environment breakdown dropdown.

    Layout:
      Row 1: Key metrics (VIX / 10Y Yield / Yield Curve / S&P Trend)
      Row 2: Sensitivity context (Beta used / Sector used / Multiplier)
      Section: Signal list
    """
    macro = data.get("macro")

    # Don't render if macro dimension was not run
    if not macro:
        return

    # If macro ran but data failed, show a minimal notice
    if not macro.get("available", True):
        with st.expander("🌐 Macro Environment"):
            st.caption("Macro data could not be fetched for this analysis.")
        return

    score    = macro.get("score")
    env      = macro.get("env_score")
    verdict  = macro.get("verdict",  "")
    icon     = macro.get("icon",     "➡️")
    raw      = macro.get("raw",      {})
    signals  = macro.get("signals",  [])
    sens     = macro.get("sensitivity")
    beta     = macro.get("beta_used")
    sector   = macro.get("sector_used")

    color    = get_score_color(score) if score is not None else "#888888"

    with st.expander("🌐 Macro Environment Breakdown"):

        # ── Score header ──────────────────────────────────────
        col_score, col_env, col_spacer = st.columns([1, 1, 2])
        with col_score:
            st.markdown(
                f"<div style='border:1px solid {color};border-radius:10px;"
                f"padding:16px;text-align:center;background:rgba(0,0,0,0.2);'>"
                f"<div style='color:#aaa;font-size:12px;'>Adjusted Score</div>"
                f"<div style='color:{color};font-size:38px;font-weight:700;"
                f"line-height:1.1;'>{score if score is not None else '--'}</div>"
                f"<div style='color:#aaa;font-size:10px;'>out of 100</div>"
                f"<div style='margin-top:6px;font-size:13px;color:{color};'>"
                f"{icon} {verdict}</div></div>",
                unsafe_allow_html=True
            )
        with col_env:
            env_color = get_score_color(env) if env is not None else "#888888"
            st.markdown(
                f"<div style='border:1px solid {env_color};border-radius:10px;"
                f"padding:16px;text-align:center;background:rgba(0,0,0,0.2);'>"
                f"<div style='color:#aaa;font-size:12px;'>Env Score</div>"
                f"<div style='color:{env_color};font-size:38px;font-weight:700;"
                f"line-height:1.1;'>{env if env is not None else '--'}</div>"
                f"<div style='color:#aaa;font-size:10px;'>pre-adjustment</div>"
                f"<div style='margin-top:6px;font-size:13px;color:#aaa;'>"
                f"×{sens} sensitivity</div></div>",
                unsafe_allow_html=True
            )

        st.markdown("")

        # ── Raw macro metrics ─────────────────────────────────
        st.markdown("**Market Conditions**")

        vix       = raw.get("vix")
        vix_avg   = raw.get("vix_30d_avg")
        vix_trend = raw.get("vix_trend", "unknown")
        tnx       = raw.get("treasury_10y")
        t3m       = raw.get("treasury_3m")
        spread    = raw.get("yield_spread")
        curve     = raw.get("yield_curve", "unknown")
        rate_dir  = raw.get("rate_direction", "unknown")
        sp500     = raw.get("sp500_trend_30d")
        regime    = raw.get("market_regime", "unknown")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            vix_delta = f"30d avg: {vix_avg}" if vix_avg else None
            st.metric("VIX (Fear Index)",
                      f"{vix:.1f}" if vix else "N/A",
                      delta=vix_delta,
                      delta_color="inverse")

        with c2:
            rate_label = f"trend: {rate_dir}"
            st.metric("10Y Treasury Yield",
                      f"{tnx:.2f}%" if tnx else "N/A",
                      delta=rate_label,
                      delta_color="off")

        with c3:
            spread_str = f"{spread:+.2f}pp" if spread is not None else "N/A"
            st.metric("Yield Curve (10Y-3M)",
                      spread_str,
                      delta=curve,
                      delta_color="off")

        with c4:
            sp_color = "normal" if sp500 and sp500 > 0 else "inverse"
            st.metric("S&P 500 (30d)",
                      f"{sp500:+.1f}%" if sp500 is not None else "N/A",
                      delta=regime,
                      delta_color="off")

        st.markdown("")

        # ── Stock sensitivity context ─────────────────────────
        st.markdown("**Stock-Specific Sensitivity**")

        c5, c6, c7 = st.columns(3)
        with c5:
            st.metric("Beta Used",
                      f"{beta:.2f}" if beta is not None else "N/A (default 1.0)")
        with c6:
            st.metric("Sector Used",
                      sector or "Unknown (default)")
        with c7:
            st.metric("Sensitivity Multiplier",
                      f"×{sens}" if sens is not None else "N/A")

        st.caption(
            "Sensitivity multiplier amplifies or dampens the macro environment score "
            "based on how much this specific stock historically responds to macro changes. "
            "Score = 50 + (EnvScore - 50) × Multiplier."
        )

        st.markdown("")

        # ── Signal list ───────────────────────────────────────
        if signals:
            st.markdown("**Macro Signals**")
            for s in signals:
                st.markdown(f"- {_md_safe(s)}")


def render_event_dropdown(data: dict):
    """
    Expandable Event-Driven breakdown dropdown.

    Layout:
      Row 1: Reliability score card + window status
      Row 2: Next earnings metrics
      Row 3: Last earnings metrics + EPS surprise
      Section: Signal list
    """
    event = data.get("event")

    if not event:
        return

    if not event.get("available"):
        with st.expander("📅 Event-Driven"):
            st.caption("Event data could not be fetched for this analysis.")
        return

    reliability  = event.get("reliability",     1.0)
    window       = event.get("window",          "NORMAL")
    severity     = event.get("window_severity", "none")
    window_desc  = event.get("window_desc",     "")
    window_color = event.get("window_color",    "#00C853")
    event_tag    = event.get("event_tag",       "")
    signals      = event.get("signals",         [])
    next_e       = event.get("next_earnings")
    last_e       = event.get("last_earnings")
    rel_pct      = int(reliability * 100)

    rel_color = get_score_color(rel_pct)

    with st.expander("📅 Event-Driven Breakdown"):

        # ── Reliability + window status ───────────────────────
        col_rel, col_win, col_spacer = st.columns([1, 1, 2])

        with col_rel:
            st.markdown(
                f"<div style='border:1px solid {rel_color};border-radius:10px;"
                f"padding:16px;text-align:center;background:rgba(0,0,0,0.2);'>"
                f"<div style='color:#aaa;font-size:12px;'>Signal Reliability</div>"
                f"<div style='color:{rel_color};font-size:38px;font-weight:700;"
                f"line-height:1.1;'>{rel_pct}%</div>"
                f"<div style='color:#aaa;font-size:10px;'>of normal</div>"
                f"<div style='margin-top:6px;font-size:12px;color:{rel_color};'>"
                f"{event_tag}</div></div>",
                unsafe_allow_html=True
            )

        with col_win:
            st.markdown(
                f"<div style='border:1px solid {window_color};border-radius:10px;"
                f"padding:16px;text-align:center;background:rgba(0,0,0,0.2);'>"
                f"<div style='color:#aaa;font-size:12px;'>Window</div>"
                f"<div style='color:{window_color};font-size:15px;font-weight:700;"
                f"line-height:1.4;margin-top:8px;'>{window.replace('_', ' ').title()}</div>"
                f"<div style='color:#aaa;font-size:10px;margin-top:6px;'>"
                f"severity: {severity}</div></div>",
                unsafe_allow_html=True
            )

        st.markdown("")

        # ── Earnings metrics ──────────────────────────────────
        st.markdown("**Earnings Calendar**")

        c1, c2, c3, c4 = st.columns(4)

        if next_e:
            days_until = next_e.get("days_until", 9999)
            with c1:
                st.metric(
                    "Next Earnings",
                    next_e.get("date", "N/A"),
                    delta=f"in {days_until} days" if days_until > 0 else "today / past",
                    delta_color="off"
                )
            with c2:
                eps_low  = next_e.get("estimate_eps_low")
                eps_high = next_e.get("estimate_eps_high")
                if eps_low and eps_high:
                    st.metric("EPS Estimate Range",
                              f"${eps_low:.2f} - ${eps_high:.2f}")
                else:
                    st.metric("EPS Estimate", "N/A")
        else:
            with c1:
                st.metric("Next Earnings", "N/A")

        if last_e:
            days_ago     = last_e.get("days_ago", 0)
            surprise_pct = last_e.get("surprise_pct")
            actual_eps   = last_e.get("actual_eps")
            estimate_eps = last_e.get("estimate_eps")

            with c3:
                st.metric(
                    "Last Earnings",
                    last_e.get("date", "N/A"),
                    delta=f"{days_ago} days ago",
                    delta_color="off"
                )
            with c4:
                if surprise_pct is not None:
                    delta_color = "normal" if surprise_pct >= 0 else "inverse"
                    st.metric(
                        "EPS Surprise",
                        f"${actual_eps:.2f}" if actual_eps else "N/A",
                        delta=f"{surprise_pct:+.1f}% vs est ${estimate_eps:.2f}" if estimate_eps else f"{surprise_pct:+.1f}%",
                        delta_color=delta_color
                    )
                else:
                    st.metric("EPS Surprise", "N/A")
        else:
            with c3:
                st.metric("Last Earnings", "N/A")

        st.markdown("")

        # ── What this means ───────────────────────────────────
        if window != "NORMAL":
            st.markdown("**What this means for your analysis**")
            advice_map = {
                "POST_EARNINGS_SHOCK":   (
                    "🔴 **Avoid new positions today.** "
                    "Price action in the 24h post-earnings is driven by algos and "
                    "emotional reactions, not fundamentals. Wait for the market to settle."
                ),
                "PRE_EARNINGS_IMMINENT": (
                    "🔴 **Earnings event risk is high.** "
                    "All technical and sentiment signals are currently being distorted by "
                    "event speculation. Entering now means betting on the earnings outcome, "
                    "not on the analysis. Consider waiting."
                ),
                "PRE_EARNINGS_NEAR":     (
                    "🟠 **Entering the earnings window.** "
                    "Technical signals are beginning to lose reliability as price action "
                    "is increasingly driven by earnings expectations. "
                    "If bullish, consider sizing down and waiting for post-earnings confirmation."
                ),
                "PRE_EARNINGS_WATCH":    (
                    "🟡 **Mild event awareness.** "
                    "Signals are mostly valid but be aware that earnings are approaching. "
                    "Factor earnings risk into your position sizing."
                ),
                "POST_EARNINGS_DIGEST":  (
                    "🟢 **Market is digesting the recent earnings.** "
                    "Signals should stabilise within a few days as the market "
                    "re-prices the stock based on new information."
                ),
            }
            advice = advice_map.get(window, "")
            if advice:
                st.info(advice)

        # ── Signal list ───────────────────────────────────────
        if signals:
            st.markdown("**Event Signals**")
            for s in signals:
                st.markdown(f"- {_md_safe(s)}")
