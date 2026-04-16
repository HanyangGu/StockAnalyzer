# ============================================================
# ui/views.py -- Full Page View Renderers
# ============================================================
# Composes components and dropdowns into complete page views:
#   render_single_analysis   : full single stock analysis
#   render_price_only        : price data panel (8 metrics)
#   render_comparison        : multi-stock comparison table
#   render_backtest_comparison: backtest vs live price validation
# ============================================================

import pandas as pd
import streamlit as st
import yfinance as yf

from scoring.composite import get_composite
from ui.components import (
    get_score_color,
    render_price_line,
    render_score_cards,
    render_event_banner,
    render_decision_panel,
)
from ui.dropdowns import (
    render_technical_dropdown,
    render_fundamental_dropdown,
    render_sentiment_dropdown,
    render_macro_dropdown,
    render_event_dropdown,
)


def render_backtest_comparison(data: dict):
    """
    Fetches current live price and compares to backtest price
    to validate whether the app verdict was correct.
    """
    st.markdown("---")
    st.markdown("#### Backtest Validation")

    try:
        current    = yf.Ticker(data["ticker"]).info
        live_price = (
            current.get("currentPrice") or
            current.get("regularMarketPrice")
        )
        past_price = data["current_price"]

        if live_price and past_price:
            price_change     = round(live_price - past_price, 2)
            price_change_pct = round((price_change / past_price) * 100, 2)
            arrow = "▲" if price_change >= 0 else "▼"

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Price on analysis date", f"${past_price}")
            with col2:
                st.metric("Current price today",    f"${live_price}")
            with col3:
                st.metric(
                    "Actual move since then",
                    f"{arrow} {abs(price_change_pct)}%",
                    delta=f"{price_change_pct}%"
                )

            fund_score = data.get("fundamental", {}).get("score")
            sent_score = data.get("sentiment",   {}).get("score")
            comp       = get_composite(data["overall"]["score"], fund_score, sent_score)
            decision   = comp["quadrant"]
            st.markdown("")

            bullish_decision = decision in ["Strong Buy", "Value Opportunity", "Trader Play"]
            bearish_decision = decision == "Avoid"

            if price_change_pct > 5 and bullish_decision:
                st.success(
                    f"✅ Verdict was CORRECT -- "
                    f"App signaled {decision} and stock "
                    f"rose {price_change_pct}% since then"
                )
            elif price_change_pct < -5 and bearish_decision:
                st.success(
                    f"✅ Verdict was CORRECT -- "
                    f"App signaled {decision} and stock "
                    f"fell {abs(price_change_pct)}% since then"
                )
            elif -5 <= price_change_pct <= 5:
                st.info(
                    f"➡️ Verdict was NEUTRAL -- "
                    f"Stock moved only {price_change_pct}% "
                    f"since analysis date"
                )
            else:
                st.error(
                    f"❌ Verdict was INCORRECT -- "
                    f"App signaled {decision} but stock "
                    f"{'rose' if price_change > 0 else 'fell'} "
                    f"{abs(price_change_pct)}% since then"
                )

    except Exception as e:
        st.warning(f"Could not fetch current price for comparison: {e}")


def render_single_analysis(data: dict, summary: str):
    """Renders full single stock analysis panel."""
    st.markdown("---")

    if data.get("backtest_date") and data["backtest_date"] != "live":
        st.warning(
            f"📅 Backtesting as of: **{data['backtest_date']}** "
            f"-- This is historical analysis not live data"
        )

    ticker = data["ticker"]
    name   = data.get("company", ticker)
    title  = ticker if name == ticker else f"{ticker} — {name}"
    st.subheader(title)
    render_price_line(data)
    st.markdown("")
    render_score_cards(data)
    st.markdown("")
    render_event_banner(data)
    render_decision_panel(data)
    st.markdown("")
    render_technical_dropdown(data)
    render_fundamental_dropdown(data)
    render_sentiment_dropdown(data)
    render_macro_dropdown(data)
    render_event_dropdown(data)
    st.markdown("")

    if data.get("backtest_date") and data["backtest_date"] != "live":
        render_backtest_comparison(data)

    st.info(summary)


def render_price_only(data: dict, summary: str):
    """Renders price data only panel with 8 metrics."""
    st.markdown("---")
    ticker = data["ticker"]
    name   = data["name"]
    title  = ticker if name == ticker else f"{ticker} — {name}"
    st.subheader(title)
    render_price_line(data)

    def fmt_mcap(v):
        if not v:     return "N/A"
        if v >= 1e12: return f"${v/1e12:.2f}T"
        if v >= 1e9:  return f"${v/1e9:.2f}B"
        if v >= 1e6:  return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Open",       f"${data['open']}")
    with col2: st.metric("Day High",   f"${data['day_high']}")
    with col3: st.metric("Day Low",    f"${data['day_low']}")
    with col4: st.metric("Market Cap", fmt_mcap(data["market_cap"]))

    col5, col6, col7, col8 = st.columns(4)
    with col5: st.metric("Volume",   f"{data['volume']:,.0f}" if data["volume"] else "N/A")
    with col6: st.metric("P/E Ratio", round(data["pe_ratio"], 2) if data["pe_ratio"] else "N/A")
    with col7: st.metric("52W High",  f"${data['52w_high']}" if data["52w_high"] else "N/A")
    with col8: st.metric("52W Low",   f"${data['52w_low']}"  if data["52w_low"]  else "N/A")

    st.markdown("")
    st.info(summary)


def render_comparison(data: dict, summary: str):
    """Renders multi-stock comparison panel with table and best picks."""
    st.markdown("---")
    st.subheader("Stock Comparison")

    # Ranking cards
    st.markdown("#### Ranking")
    for r in data["ranking"]:
        color = get_score_color(r["score"])
        st.markdown(f"""
        <div style="
            border: 1px solid {color};
            border-radius: 8px;
            padding: 12px 20px;
            margin: 6px 0;
            display: flex;
            align-items: center;
            gap: 16px;">
            <span style="font-size:24px;">{r["medal"]}</span>
            <span style="font-size:18px;font-weight:700;">{r["ticker"]}</span>
            <span style="color:#aaa;">{r["company"]}</span>
            <span style="margin-left:auto;color:{color};font-weight:700;">
                {r["score"]}/100 -- {r["verdict"]} {r["icon"]}
            </span>
        </div>
        """, unsafe_allow_html=True)

    # Comparison table
    st.markdown("")
    st.markdown("#### Comparison Table")
    table   = data["comparison_table"]
    tickers = list(table.keys())

    rows = {
        "Price":        [f"${table[t]['price']}"                               for t in tickers],
        "Change":       [f"{table[t]['change_pct']}%"                          for t in tickers],
        "Short term":   [f"{table[t]['short_term']}/100"                       for t in tickers],
        "Mid term":     [f"{table[t]['mid_term']}/100"                         for t in tickers],
        "Long term":    [f"{table[t]['long_term']}/100"                        for t in tickers],
        "Overall":      [f"{table[t]['overall']}/100"                          for t in tickers],
        "Fundamentals": [
            f"{table[t]['fundamental']}/100" if table[t]["fundamental"] is not None else "N/A"
            for t in tickers
        ],
        "Sentiment": [
            f"{table[t]['sentiment']}/100" if table[t].get("sentiment") is not None else "N/A"
            for t in tickers
        ],
        "Composite": [
            f"{get_composite(technical=table[t]['overall'], fundamental=table[t]['fundamental'], sentiment=table[t].get('sentiment'), macro=table[t].get('_macro', {}).get('score') if table[t].get('_macro') else None)['score']}/100"
            for t in tickers
        ],
        "Decision": [
            get_composite(technical=table[t]["overall"], fundamental=table[t]["fundamental"], sentiment=table[t].get("sentiment"), macro=table[t].get("_macro", {}).get("score") if table[t].get("_macro") else None)["quadrant"]
            for t in tickers
        ],
        "RSI":          [f"{table[t]['rsi']} {table[t]['rsi_signal']}"         for t in tickers],
        "Stochastic":   [f"{table[t]['stoch']} {table[t]['stoch_signal']}"     for t in tickers],
        "ROC":          [f"{table[t]['roc']}% {table[t]['roc_signal']}"        for t in tickers],
        "MACD":         [f"{table[t]['macd']} {table[t]['macd_signal']}"       for t in tickers],
        "MA20":         [f"${table[t]['ma20']} {table[t]['ma20_signal']}"      for t in tickers],
        "MA50":         [f"${table[t]['ma50']} {table[t]['ma50_signal']}"      for t in tickers],
        "MA200":        [f"${table[t]['ma200']} {table[t]['ma200_signal']}"    for t in tickers],
        "Golden Cross": [f"{table[t]['golden_cross']} {table[t]['golden_signal']}" for t in tickers],
        "Bollinger":    [f"{table[t]['bb_pct']}% {table[t]['bb_signal']}"      for t in tickers],
        "ATR":          [f"${table[t]['atr']} {table[t]['atr_signal']}"        for t in tickers],
        "Volume":       [f"{table[t]['volume']}x {table[t]['volume_signal']}"  for t in tickers],
    }

    df = pd.DataFrame(rows, index=tickers).T
    st.dataframe(df, use_container_width=True)

    # Decision panels per stock
    st.markdown("")
    st.markdown("#### Investment Decision")
    dec_cols = st.columns(len(tickers))
    for i, t in enumerate(tickers):
        comp = get_composite(
            technical      = table[t]["overall"],
            fundamental    = table[t]["fundamental"],
            sentiment      = table[t].get("sentiment"),
            macro          = table[t].get("_macro", {}).get("score") if table[t].get("_macro") else None,
            event          = table[t].get("_event"),
            fund_data      = table[t].get("_fund_data"),
            sentiment_data = table[t].get("_sentiment_data"),
        )
        with dec_cols[i]:
            st.markdown(f"""
            <div style="
                border: 2px solid {comp['q_color']};
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                background: rgba(0,0,0,0.2);">
                <div style="font-size:20px;font-weight:700;color:#fff;margin-bottom:4px;">{t}</div>
                <div style="font-size:13px;color:#aaa;margin-bottom:10px;">
                    Composite: {comp['score']}/100
                </div>
                <div style="font-size:18px;font-weight:700;color:{comp['q_color']};margin-bottom:8px;">
                    {comp['q_icon']} {comp['quadrant']}
                </div>
                <div style="font-size:12px;color:#bbb;line-height:1.5;">
                    {comp['action']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Best picks
    st.markdown("")
    st.markdown("#### Best Picks")
    bp = data["best_picks"]
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1: st.metric("Best Overall",      bp["overall"])
    with col2: st.metric("Best Short term",   bp["short_term"])
    with col3: st.metric("Best Mid term",     bp["mid_term"])
    with col4: st.metric("Best Long term",    bp["long_term"])
    with col5: st.metric("Lowest Risk",       bp["lowest_risk"])
    with col6: st.metric("Best Fundamentals", bp.get("fundamentals", "N/A"))

    st.markdown("")
    st.info(summary)
