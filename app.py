# ============================================================
# app.py -- Streamlit App Entry Point
# ============================================================
# Minimal entry point: sidebar config + session management
# + chat loop. All rendering delegated to ui/ modules.
#
#   ui/components.py : score cards, price line, decision panel
#   ui/dropdowns.py  : technical/fundamental/sentiment breakdowns
#   ui/views.py      : single analysis, price only, comparison
# ============================================================

import os

import pandas as pd
import streamlit as st

from engine.ai import StockChatbot
from ui.views import (
    render_single_analysis,
    render_price_only,
    render_comparison,
)


# ============================================================
# Sidebar
# ============================================================

def render_sidebar():
    """Renders the sidebar with API key, model, backtest, examples."""
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
        selected_label = st.selectbox(
            label   = "Choose AI model",
            options = list(model_options.keys()),
            index   = 2,
            help    = "Higher quality models give better summaries but have lower rate limits."
        )
        st.session_state.selected_model = model_options[selected_label]

        if "mini" in st.session_state.selected_model or \
           "turbo" in st.session_state.selected_model:
            st.success("✅ High rate limits -- good for testing")
        else:
            st.warning("⚠️ Lower rate limits -- use sparingly")

        st.markdown("---")

        # Backtesting mode
        st.markdown("#### Backtesting Mode")
        if "backtest_mode" not in st.session_state:
            st.session_state.backtest_mode = False

        backtest_mode = st.toggle(
            "Enable backtesting",
            key  = "backtest_mode",
            help = "Analyze a stock as of a specific past date"
        )

        if backtest_mode:
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
            "Is Microsoft a good long term investment?",
            "What is the technical outlook for Google?",
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
                st.error("⚠️ Approaching rate limit! Please wait before sending more queries.")
            elif bot.total_tokens > 80000:
                st.warning("⚠️ High token usage this session.")
            else:
                st.success("✅ Token usage normal")

            cost = bot.total_tokens * 0.000005
            st.caption(f"Estimated session cost: ~${cost:.4f}")
        else:
            st.caption("No session active yet.")

        st.markdown("---")

        if st.button("🔄 Reset Conversation", use_container_width=True):
            st.session_state.bot         = None
            st.session_state.messages    = []
            st.session_state.last_result = None
            st.rerun()

        st.caption(
            "Powered by GPT + Yahoo Finance\n\n"
            "Technical analysis is not financial advice."
        )


# ============================================================
# Chat Rendering
# ============================================================

def render_chat_history():
    """Renders all previous chat messages."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg.get("content", "")
            if msg["role"] == "assistant" and isinstance(content, dict):
                rtype = content.get("type", "text")
                if rtype == "error":
                    st.error(content.get("summary", ""))
                elif rtype == "single_stock":
                    ticker = content["data"]["ticker"]
                    st.markdown(f"Analysis complete for **{ticker}**. See results below.")
                elif rtype == "comparison":
                    try:
                        tickers = list(content["data"]["comparison_table"].keys())
                        st.markdown(f"Comparison complete for **{', '.join(tickers)}**. See results below.")
                    except (KeyError, TypeError):
                        st.markdown("Comparison complete. See results below.")
                elif rtype == "price":
                    ticker = content["data"]["ticker"]
                    st.markdown(f"Price data fetched for **{ticker}**. See results below.")
                else:
                    st.markdown(content.get("summary", ""))
            else:
                st.markdown(content)


def render_last_result():
    """Renders the most recent analysis result."""
    if not st.session_state.last_result:
        return
    result = st.session_state.last_result
    rtype  = result.get("type")
    if rtype == "single_stock":
        render_single_analysis(result["data"], result["summary"])
    elif rtype == "comparison":
        render_comparison(result["data"], result["summary"])
    elif rtype == "price":
        render_price_only(result["data"], result["summary"])


def process_input(user_input: str):
    """Sends user input to the bot and updates session state."""
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analysing..."):
            result = st.session_state.bot.chat(user_input)

        rtype = result.get("type", "text")

        if rtype == "error":
            st.error(result.get("summary", "Unknown error"))
            st.session_state.messages.append({"role": "assistant", "content": result})
            st.rerun()
            return

        st.session_state.last_result = result

        if rtype == "single_stock":
            ticker = result["data"]["ticker"]
            st.markdown(f"Analysis complete for **{ticker}**. See results below.")
        elif rtype == "comparison":
            tickers = list(result["data"]["comparison_table"].keys())
            st.markdown(f"Comparison complete for **{', '.join(tickers)}**. See results below.")
        elif rtype == "price":
            ticker = result["data"]["ticker"]
            st.markdown(f"Price data fetched for **{ticker}**. See results below.")
        else:
            st.markdown(result.get("summary", ""))

        st.session_state.messages.append({"role": "assistant", "content": result})

    st.rerun()


# ============================================================
# Main
# ============================================================

def main():
    st.set_page_config(
        page_title = "Stock Analysis Chatbot",
        page_icon  = "📈",
        layout     = "wide",
    )

    # Session state init
    if "bot" not in st.session_state:
        st.session_state.bot            = None
        st.session_state.messages       = []
        st.session_state.last_result    = None
        st.session_state.selected_model = "gpt-4.1-mini"
        st.session_state.current_model  = None
        st.session_state.api_key        = None
        st.session_state.backtest_date  = None

    render_sidebar()

    # Bot lifecycle management
    if st.session_state.get("api_key") and st.session_state.bot is None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        st.session_state.bot           = StockChatbot()
        st.session_state.current_model = st.session_state.selected_model

    if st.session_state.get("api_key") and st.session_state.bot is not None:
        os.environ["OPENAI_API_KEY"] = st.session_state.api_key
        if st.session_state.selected_model != st.session_state.current_model:
            st.session_state.bot           = StockChatbot()
            st.session_state.current_model = st.session_state.selected_model
            st.session_state.messages      = []
            st.session_state.last_result   = None

    # Main area
    st.title("📈 Real-Time Stock Analysis Chatbot")
    st.caption("Ask about any stock -- get real-time data and technical analysis across 3 time horizons.")
    st.markdown("---")

    render_chat_history()
    render_last_result()

    # Handle example button clicks
    if "pending_input" in st.session_state:
        pending = st.session_state.pop("pending_input")
        if st.session_state.bot:
            process_input(pending)

    # Chat input
    if prompt := st.chat_input("Ask about a stock..."):
        if not st.session_state.get("api_key"):
            st.error("Please enter your OpenAI API key in the sidebar first.")
        elif st.session_state.bot is None:
            st.error("Bot not initialized. Please check your API key.")
        else:
            process_input(prompt)


if __name__ == "__main__":
    main()
