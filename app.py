# ============================================================
# app.py -- Streamlit UI
# ============================================================
# Main entry point for the Stock Analysis Chatbot.
# Handles all rendering and user interaction.
# All business logic is imported from separate modules.
# ============================================================

import os

import pandas as pd
import streamlit as st
import yfinance as yf

from ai import StockChatbot


# ============================================================
# Score Color Helper
# ============================================================

def get_score_color(score: int) -> str:
    if score >= 75:   return "#00C853"
    elif score >= 60: return "#69F0AE"
    elif score >= 40: return "#FFD740"
    elif score >= 25: return "#FF6D00"
    else:             return "#FF1744"


def get_composite(technical: int, fundamental) -> dict:
    """
    Combines technical (60%) + fundamental (40%) into one
    composite investment score with quadrant decision label.
    """
    THRESHOLD = 50

    if fundamental is None:
        comp_score = technical
    else:
        comp_score = round(technical * 0.60 + fundamental * 0.40)
    comp_score = max(0, min(100, comp_score))

    if comp_score >= 75:
        comp_verdict, comp_color = "Strong Uptrend",  "#00C853"
    elif comp_score >= 60:
        comp_verdict, comp_color = "Uptrend",         "#69F0AE"
    elif comp_score >= 40:
        comp_verdict, comp_color = "Neutral",         "#FFD740"
    elif comp_score >= 25:
        comp_verdict, comp_color = "Downtrend",       "#FF6D00"
    else:
        comp_verdict, comp_color = "Strong Downtrend","#FF1744"

    high_t = technical        >= THRESHOLD
    high_f = (fundamental or 0) >= THRESHOLD

    if fundamental is None:
        quadrant = "Technical Only"
        action   = "Fundamental data unavailable -- decision based on technical signals only."
        q_color  = "#888888"
        q_icon   = "⬜"
    elif high_t and high_f:
        quadrant = "Strong Buy"
        action   = "Both technical and fundamental agree -- highest conviction entry."
        q_color  = "#00C853"
        q_icon   = "🟢"
    elif high_t and not high_f:
        quadrant = "Trader Play"
        action   = "Momentum exists but business fundamentals are weak -- short term only, set a tight stop loss."
        q_color  = "#FFD740"
        q_icon   = "🟡"
    elif not high_t and high_f:
        quadrant = "Value Opportunity"
        action   = "Solid business in a technical pullback -- wait for price to stabilize or reverse before entering."
        q_color  = "#69F0AE"
        q_icon   = "🔵"
    else:
        quadrant = "Avoid"
        action   = "Both technical and fundamental are weak -- no clear edge. Stay out."
        q_color  = "#FF1744"
        q_icon   = "🔴"

    return {
        "score":    comp_score,
        "verdict":  comp_verdict,
        "color":    comp_color,
        "quadrant": quadrant,
        "action":   action,
        "q_color":  q_color,
        "q_icon":   q_icon,
    }


# ============================================================
# Render Functions
# ============================================================

def render_score_cards(data: dict):
    """Renders 5 colored score cards: 4 time horizons + fundamental."""
    col1, col2, col3, col4, col5 = st.columns(5)

    fund = data.get("fundamental", {})
    fund_score = fund.get("score")

    horizons = [
        (col1, "Short term",   data["short_term"]),
        (col2, "Mid term",     data["mid_term"]),
        (col3, "Long term",    data["long_term"]),
        (col4, "Overall",      data["overall"]),
    ]
    for col, label, h in horizons:
        color = get_score_color(h["score"])
        with col:
            st.markdown(f"""
            <div style="
                border: 1px solid {color};
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                background: rgba(0,0,0,0.2);">
                <div style="color:#aaa;font-size:13px;">
                    {label}
                </div>
                <div style="
                    color:{color};
                    font-size:42px;
                    font-weight:700;">
                    {h["score"]}
                </div>
                <div style="color:#aaa;font-size:11px;">
                    out of 100
                </div>
                <div style="margin-top:8px;">
                    {h["icon"]} {h["verdict"]}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Fundamental score card
    with col5:
        if fund_score is not None:
            fcolor = get_score_color(fund_score)
            ficon  = fund.get("icon",    "➡️")
            fverdict = fund.get("verdict", "")
        else:
            fcolor   = "#888888"
            ficon    = "➡️"
            fverdict = "No data"
            fund_score = "--"

        st.markdown(f"""
        <div style="
            border: 1px solid {fcolor};
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            background: rgba(0,0,0,0.2);">
            <div style="color:#aaa;font-size:13px;">
                Fundamentals
            </div>
            <div style="
                color:{fcolor};
                font-size:42px;
                font-weight:700;">
                {fund_score}
            </div>
            <div style="color:#aaa;font-size:11px;">
                out of 100
            </div>
            <div style="margin-top:8px;">
                {ficon} {fverdict}
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_price_line(data: dict):
    """Renders price with colored up/down arrow."""
    price  = data["current_price"]
    change = data["price_change"]
    pct    = data["price_change_pct"]
    arrow  = "▲" if change >= 0 else "▼"
    color  = "#00C853" if change >= 0 else "#FF1744"
    st.markdown(f"""
    <div style="font-size:16px;margin:10px 0;">
        <b>Price:</b> ${price}
        <span style="color:{color};">
            {arrow} {abs(change)} ({abs(pct)}%)
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_signals(data: dict):
    """Renders expandable indicator breakdown panel."""
    with st.expander("📊 View Full Indicator Breakdown"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Short term signals**")
            for s in data["short_term"]["signals"]:
                st.markdown(f"- {s}")
        with col2:
            st.markdown("**Mid term signals**")
            for s in data["mid_term"]["signals"]:
                st.markdown(f"- {s}")
        with col3:
            st.markdown("**Long term signals**")
            for s in data["long_term"]["signals"]:
                st.markdown(f"- {s}")


def render_fundamentals(data: dict):
    """Renders expandable fundamental analysis panel."""
    fund    = data.get("fundamental", {})
    details = data.get("fund_details", {})

    if not details:
        return

    with st.expander("🏦 View Fundamental Analysis"):

        # Fundamental signals
        if fund.get("signals"):
            st.markdown("**Fundamental Signals**")
            for s in fund["signals"]:
                st.markdown(f"- {s}")
            st.markdown("")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("**Valuation**")
            v = details.get("valuation", {})
            st.metric("P/E Ratio",      v.get("pe_ratio")       or "N/A")
            st.metric("Forward P/E",    v.get("forward_pe")     or "N/A")
            st.metric("Price/Book",     v.get("price_to_book")  or "N/A")
            st.metric("Price/Sales",    v.get("price_to_sales") or "N/A")

        with col2:
            st.markdown("**Profitability**")
            p = details.get("profitability", {})
            st.metric("Gross Margin",   f"{p.get('gross_margin')}%"  if p.get("gross_margin")  else "N/A")
            st.metric("Net Margin",     f"{p.get('net_margin')}%"    if p.get("net_margin")    else "N/A")
            st.metric("ROE",            f"{p.get('roe')}%"           if p.get("roe")           else "N/A")
            st.metric("ROA",            f"{p.get('roa')}%"           if p.get("roa")           else "N/A")

        with col3:
            st.markdown("**Growth**")
            g = details.get("growth", {})
            st.metric("Revenue Growth", f"{g.get('revenue_growth')}%"  if g.get("revenue_growth")  else "N/A")
            st.metric("Earnings Growth",f"{g.get('earnings_growth')}%" if g.get("earnings_growth") else "N/A")
            st.metric("EPS (TTM)",      g.get("eps")         or "N/A")
            st.metric("Forward EPS",    g.get("forward_eps") or "N/A")

        with col4:
            st.markdown("**Health & Analyst**")
            h = details.get("health", {})
            a = details.get("analyst", {})
            st.metric("Debt/Equity",    h.get("debt_to_equity")  or "N/A")
            st.metric("Current Ratio",  h.get("current_ratio")   or "N/A")
            st.metric("Analyst Target", f"${a.get('target_price')}" if a.get("target_price") else "N/A")
            upside = a.get("upside_pct")
            st.metric(
                "Upside Potential",
                f"{upside}%" if upside is not None else "N/A",
                delta=f"{upside}%" if upside is not None else None
            )


def render_decision_panel(data: dict):
    """
    Renders the composite investment score + quadrant decision panel.
    This is the main 'should I invest?' answer.
    """
    tech_score = data["overall"]["score"]
    fund_score = data.get("fundamental", {}).get("score")
    comp       = get_composite(tech_score, fund_score)

    st.markdown("---")
    st.markdown("#### Investment Decision")

    col_score, col_quad = st.columns([1, 2])

    # Left: Composite score card
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
                Technical 60% + Fundamental 40%
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

    # Right: Quadrant label + action
    with col_quad:
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
                Technical: {tech_score}/100 &nbsp;|&nbsp;
                Fundamental: {fund_score if fund_score is not None else 'N/A'}/100
            </div>
        </div>
        """, unsafe_allow_html=True)


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
            price_change_pct = round(
                (price_change / past_price) * 100, 2
            )
            arrow = "▲" if price_change >= 0 else "▼"

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Price on analysis date",
                    f"${past_price}"
                )
            with col2:
                st.metric(
                    "Current price today",
                    f"${live_price}"
                )
            with col3:
                st.metric(
                    "Actual move since then",
                    f"{arrow} {abs(price_change_pct)}%",
                    delta=f"{price_change_pct}%"
                )

            # Use composite decision for validation -- more accurate than technical alone
            fund_score = data.get("fundamental", {}).get("score")
            comp       = get_composite(data["overall"]["score"], fund_score)
            decision   = comp["quadrant"]  # Strong Buy / Value Opportunity / Trader Play / Avoid
            verdict    = data["overall"]["verdict"]  # kept for display only
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

    # Backtest badge
    if data.get("backtest_date") and \
       data["backtest_date"] != "live":
        st.warning(
            f"📅 Backtesting as of: **{data['backtest_date']}** "
            f"-- This is historical analysis not live data"
        )

    ticker = data['ticker']
    name   = data.get('company', ticker)
    title  = ticker if name == ticker else f"{ticker} -- {name}"
    st.subheader(title)
    render_price_line(data)
    st.markdown("")
    render_score_cards(data)
    st.markdown("")
    render_decision_panel(data)
    st.markdown("")
    render_signals(data)
    render_fundamentals(data)
    st.markdown("")

    # Backtest validation panel
    if data.get("backtest_date") and \
       data["backtest_date"] != "live":
        render_backtest_comparison(data)

    st.info(summary)


def render_price_only(data: dict, summary: str):
    """Renders price data only panel with 8 metrics."""
    st.markdown("---")
    ticker = data['ticker']
    name   = data['name']
    # Avoid "GC=F -- GC=F" when Yahoo returns no longName
    title  = ticker if name == ticker else f"{ticker} -- {name}"
    st.subheader(title)
    render_price_line(data)

    def fmt_mcap(v):
        if not v:      return "N/A"
        if v >= 1e12:  return f"${v/1e12:.2f}T"
        if v >= 1e9:   return f"${v/1e9:.2f}B"
        if v >= 1e6:   return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open",      f"${data['open']}")
    with col2:
        st.metric("Day High",  f"${data['day_high']}")
    with col3:
        st.metric("Day Low",   f"${data['day_low']}")
    with col4:
        st.metric("Market Cap", fmt_mcap(data['market_cap']))

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(
            "Volume",
            f"{data['volume']:,.0f}"
            if data['volume'] else "N/A"
        )
    with col6:
        st.metric("P/E Ratio", round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A")
    with col7:
        st.metric(
            "52W High",
            f"${data['52w_high']}"
            if data['52w_high'] else "N/A"
        )
    with col8:
        st.metric(
            "52W Low",
            f"${data['52w_low']}"
            if data['52w_low'] else "N/A"
        )

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
            <span style="font-size:18px;font-weight:700;">
                {r["ticker"]}
            </span>
            <span style="color:#aaa;">
                {r["company"]}
            </span>
            <span style="
                margin-left:auto;
                color:{color};
                font-weight:700;">
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
            f"{table[t]['fundamental']}/100" if table[t]['fundamental'] is not None
            else "N/A"
            for t in tickers
        ],
        "Composite":    [
            f"{get_composite(table[t]['overall'], table[t]['fundamental'])['score']}/100"
            for t in tickers
        ],
        "Decision":     [
            get_composite(table[t]['overall'], table[t]['fundamental'])['quadrant']
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
        "Bollinger":    [f"{table[t]['bb_pct']}% {table[t]['bb_signal']}"     for t in tickers],
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
            table[t]["overall"],
            table[t]["fundamental"]
        )
        with dec_cols[i]:
            st.markdown(f"""
            <div style="
                border: 2px solid {comp['q_color']};
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                background: rgba(0,0,0,0.2);">
                <div style="font-size:20px;font-weight:700;
                    color:#fff;margin-bottom:4px;">{t}</div>
                <div style="font-size:13px;color:#aaa;
                    margin-bottom:10px;">
                    Composite: {comp['score']}/100
                </div>
                <div style="font-size:18px;font-weight:700;
                    color:{comp['q_color']};margin-bottom:8px;">
                    {comp['q_icon']} {comp['quadrant']}
                </div>
                <div style="font-size:12px;color:#bbb;
                    line-height:1.5;">
                    {comp['action']}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Best picks
    st.markdown("")
    st.markdown("#### Best Picks")
    bp = data["best_picks"]

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Best Overall",       bp["overall"])
    with col2:
        st.metric("Best Short term",    bp["short_term"])
    with col3:
        st.metric("Best Mid term",      bp["mid_term"])
    with col4:
        st.metric("Best Long term",     bp["long_term"])
    with col5:
        st.metric("Lowest Risk",        bp["lowest_risk"])
    with col6:
        st.metric("Best Fundamentals",  bp.get("fundamentals", "N/A"))

    st.markdown("")
    st.info(summary)


# ============================================================
# Main App
# ============================================================

def main():

    st.set_page_config(
        page_title = "Stock Analysis Chatbot",
        page_icon  = "📈",
        layout     = "wide",
    )

    # -- Session state initialization -------------------------
    if "bot" not in st.session_state:
        st.session_state.bot            = None
        st.session_state.messages       = []
        st.session_state.last_result    = None
        st.session_state.selected_model = "gpt-4.1-mini"
        st.session_state.current_model  = None
        st.session_state.api_key        = None
        st.session_state.backtest_date  = None

    # -- Sidebar ----------------------------------------------
    with st.sidebar:
        st.title("📈 Stock Chatbot")
        st.markdown("---")

        # API Key
        st.markdown("#### OpenAI API Key")
        api_key = st.text_input(
            label       = "Enter your API key",
            type        = "password",
            placeholder = "sk-...",
            help        = "Your key is never stored or shared."
        )

        if api_key:
            st.session_state.api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
            st.success("API key set ✅")
        else:
            st.session_state.api_key = None
            st.warning("Please enter your API key to continue.")

        st.markdown("---")

        # Model selector
        st.markdown("#### Model Selection")
        model_options = {
            "GPT-4o (Best quality)":      "gpt-4o",
            "GPT-4.1 (Latest)":           "gpt-4.1",
            "GPT-4.1-mini (Recommended)": "gpt-4.1-mini",
            "GPT-4o-mini (Fast & cheap)": "gpt-4o-mini",
            "GPT-3.5-turbo (Basic)":      "gpt-3.5-turbo",
        }
        selected_model = st.selectbox(
            label   = "Choose AI model",
            options = list(model_options.keys()),
            index   = 2,
            help    = (
                "Higher quality models give better summaries "
                "but have lower rate limits. "
                "Use mini models for testing."
            )
        )
        st.session_state.selected_model = model_options[selected_model]

        if "mini" in st.session_state.selected_model or \
           "turbo" in st.session_state.selected_model:
            st.success("✅ High rate limits -- good for testing")
        else:
            st.warning("⚠️ Lower rate limits -- use sparingly")

        st.markdown("---")

        # Backtesting mode
        st.markdown("#### Backtesting Mode")

        # Initialize backtest toggle state if not set
        if "backtest_mode" not in st.session_state:
            st.session_state.backtest_mode = False

        backtest_mode = st.toggle(
            "Enable backtesting",
            key  = "backtest_mode",
            help = "Analyze a stock as of a specific past date"
        )

        if backtest_mode:
            # Initialize date if not set
            if "backtest_date_value" not in st.session_state:
                st.session_state.backtest_date_value = (
                    pd.Timestamp.now() - pd.DateOffset(months=6)
                ).date()

            backtest_date = st.date_input(
                label     = "Select analysis date",
                value     = st.session_state.backtest_date_value,
                max_value = pd.Timestamp.now() - pd.DateOffset(days=1),
                min_value = pd.Timestamp("2021-01-01"),
                key       = "backtest_date_picker",
                help      = "App will analyze the stock as of this date"
            )
            st.session_state.backtest_date_value = backtest_date
            st.session_state.backtest_date       = str(backtest_date)
            print(f"Backtest date set: {st.session_state.backtest_date}")
            st.info(
                f"Analyzing as of: **{backtest_date}**\n\n"
                f"Compare verdict to actual price movement after this date."
            )
        else:
            st.session_state.backtest_date = None

        st.markdown("---")

        # Example queries
        st.markdown("#### Example Queries")
        examples = [
            "Give me real time data for Apple",
            "Is NVDA a good stock to buy?",
            "Run technical analysis on Tesla",
            "Show full analysis for AMD",
            "Compare NVDA, AMD and Intel",
            "Which of Apple or Microsoft is a better buy?",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.pending_input = ex

        st.markdown("---")

        # Token usage
        st.markdown("#### Session Usage")
        if st.session_state.bot is not None:
            bot = st.session_state.bot
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total tokens",    f"{bot.total_tokens:,}")
                st.metric("Requests",        bot.total_requests)
            with col2:
                st.metric("Prompt tokens",   f"{bot.prompt_tokens:,}")
                st.metric("Response tokens", f"{bot.completion_tokens:,}")

            if bot.total_tokens > 150000:
                st.error(
                    "⚠️ Approaching rate limit! "
                    "Please wait before sending more queries."
                )
            elif bot.total_tokens > 80000:
                st.warning("⚠️ High token usage this session.")
            else:
                st.success("✅ Token usage normal")

            cost = bot.total_tokens * 0.000005
            st.caption(f"Estimated session cost: ~${cost:.4f}")
        else:
            st.caption("No session active yet.")

        st.markdown("---")

        # Reset button
        if st.button("🔄 Reset Conversation",
                     use_container_width=True):
            st.session_state.bot         = None
            st.session_state.messages    = []
            st.session_state.last_result = None
            st.rerun()

        st.caption(
            "Powered by GPT + Yahoo Finance\n\n"
            "Technical analysis is not financial advice."
        )

    # -- Bot creation and model management --------------------
    if st.session_state.get("api_key") and \
       st.session_state.bot is None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        st.session_state.bot           = StockChatbot()
        st.session_state.current_model = st.session_state.selected_model

    if st.session_state.get("api_key") and \
       st.session_state.bot is not None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        if st.session_state.selected_model != \
           st.session_state.current_model:
            st.session_state.bot           = StockChatbot()
            st.session_state.current_model = st.session_state.selected_model
            st.session_state.messages      = []
            st.session_state.last_result   = None

    # -- Main area --------------------------------------------
    st.title("📈 Real-Time Stock Analysis Chatbot")
    st.caption(
        "Ask about any stock -- get real-time data and "
        "technical analysis across 3 time horizons."
    )
    st.markdown("---")

    # -- Chat history -----------------------------------------
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg.get("content", "")
            if msg["role"] == "assistant" and \
               isinstance(content, dict):
                rtype = content.get("type", "text")
                if rtype == "error":
                    st.error(content.get("summary", ""))
                elif rtype == "single_stock":
                    ticker = content["data"]["ticker"]
                    st.markdown(
                        f"Analysis complete for **{ticker}**. "
                        f"See results below."
                    )
                elif rtype == "comparison":
                    tickers = list(
                        content["data"]["comparison_table"].keys()
                    )
                    st.markdown(
                        f"Comparison complete for "
                        f"**{', '.join(tickers)}**. "
                        f"See results below."
                    )
                elif rtype == "price":
                    ticker = content["data"]["ticker"]
                    st.markdown(
                        f"Price data fetched for **{ticker}**. "
                        f"See results below."
                    )
                else:
                    st.markdown(content.get("summary", ""))
            else:
                st.markdown(content)

    # -- Render last analysis result --------------------------
    if st.session_state.last_result:
        result = st.session_state.last_result
        rtype  = result.get("type")

        if rtype == "single_stock":
            render_single_analysis(
                result["data"],
                result["summary"]
            )
        elif rtype == "comparison":
            render_comparison(
                result["data"],
                result["summary"]
            )
        elif rtype == "price":
            render_price_only(
                result["data"],
                result["summary"]
            )

    # -- Process input function -------------------------------
    def process_input(user_input: str):
        print(f"Processing input: {user_input}")
        st.session_state.messages.append({
            "role":    "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Analysing..."):
                result = st.session_state.bot.chat(user_input)
                print(f"Result type   : {result.get('type')}")
                print(f"Result summary: {result.get('summary', '')[:100]}")

            rtype = result.get("type", "text")

            # Handle error
            if rtype == "error":
                st.error(result.get("summary", "Unknown error"))
                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": result
                })
                st.rerun()
                return

            # Store result for rendering
            st.session_state.last_result = result

            # Show confirmation in chat bubble
            if rtype == "single_stock":
                ticker = result["data"]["ticker"]
                st.markdown(
                    f"Analysis complete for **{ticker}**. "
                    f"See results below."
                )
            elif rtype == "comparison":
                tickers = list(
                    result["data"]["comparison_table"].keys()
                )
                st.markdown(
                    f"Comparison complete for "
                    f"**{', '.join(tickers)}**. "
                    f"See results below."
                )
            elif rtype == "price":
                ticker = result["data"]["ticker"]
                st.markdown(
                    f"Price data fetched for **{ticker}**. "
                    f"See results below."
                )
            else:
                st.markdown(result.get("summary", ""))

            st.session_state.messages.append({
                "role":    "assistant",
                "content": result
            })

        st.rerun()

    # -- Handle sidebar button clicks -------------------------
    if "pending_input" in st.session_state:
        user_input = st.session_state.pending_input
        del st.session_state.pending_input
        if st.session_state.get("api_key"):
            process_input(user_input)
        else:
            st.warning("Please enter your API key first.")

    # -- Chat input -------------------------------------------
    if not st.session_state.get("api_key"):
        st.info(
            "👈 Please enter your OpenAI API key "
            "in the sidebar to get started."
        )
    else:
        user_input = st.chat_input("Ask about any stock...")
        if user_input:
            process_input(user_input)


if __name__ == "__main__":
    main()
