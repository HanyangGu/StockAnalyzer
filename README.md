# AI Stock Analysis Chatbot

A multi-dimensional stock analysis platform that scores any publicly traded stock across five analytical dimensions and explains the result through a conversational AI agent. Built in Python with Streamlit, powered by OpenAI GPT (function calling) and live market data from Yahoo Finance.

> **Note:** This tool is for educational purposes only and does not constitute financial advice.

---

## Why I built this

This started as the final project for an analytics course, which only required a single **technical-analysis** module. I had no background in finance — I learned the domain as I went, using AI to help me research indicators, valuation metrics, and market signals while I designed and built the system.

After the course, my professor suggested it had room to grow, so I kept going on my own and independently expanded it from one dimension into a full five-dimension analysis engine with an AI agent on top. The large majority of what's here was built after the course ended.

The project is intentionally paused at its current scope. The main limiting factor is **data**: the free Yahoo Finance API caps how much historical and real-time data is available, which makes rigorous backtesting impractical without a paid data source. Rather than add more dimensions on top of limited data, I treated this as a complete, well-structured build. The natural next step would be integrating a paid data feed, running historical backtests, and using those results to recalibrate the dimension weights.

---

## What it does

Enter a stock ticker (or ask in plain English) and the system returns a single **0–100 composite investment score**, a **decision label**, a **risk matrix**, and a natural-language explanation. Three modes are available:

- **Single analysis** — full five-dimension breakdown for one stock
- **Price only** — quick real-time price and market data
- **Comparison** — analyze and compare multiple stocks side by side

The composite score is split into a decision quadrant such as *Strong Buy*, *Cautious Buy*, *Value Opportunity*, *Trader Play*, *Macro Headwind*, or *Avoid*, derived from how the dimensions interact rather than a simple average.

---

## The five analysis dimensions

Each stock is scored across five independent dimensions, then combined into the composite score using a centrally configured weighting scheme.

| Dimension | What it measures |
|---|---|
| **Technical** | Price/momentum signals: RSI, Stochastic, ROC, MACD, moving averages, golden cross, Bollinger Bands, ATR, volume trend |
| **Fundamental** | Valuation and financial health metrics |
| **Sentiment** | Composed of four sub-signals: **news**, **analyst** ratings/authority, **insider** transactions, and **options** flow |
| **Macro** | Macroeconomic environment, weighted more heavily for high-Beta stocks |
| **Event-driven** | Reliability-windowed analysis of discrete events |

All weights and thresholds live in a single source-of-truth config (`core/weights.py`), so the entire scoring behavior can be tuned — or dimensions toggled on/off — from one place.

---

## The AI agent

The conversational layer (`engine/ai.py`) uses **OpenAI GPT function calling (tool use)**. GPT is given a set of tools — fetch price data, run the full analysis, compare stocks — and decides which to call based on the user's question, then explains the results in natural language. The chatbot tracks token usage and supports multiple selectable models (GPT-4o, GPT-4.1, and mini/turbo variants for higher rate limits during testing).

---

## Architecture

The codebase (~8,800 lines) is organized into clean, separated layers:

```
core/        Config, data layer, centralized weights, utilities
analyzers/   Raw analysis per dimension (technical, fundamental, macro,
             event-driven, and sentiment sub-modules: news/analyst/insider/options)
scoring/     Scorers per dimension + orchestrator + composite synthesis + risk matrix
engine/      LLM wrapper, AI agent (tool calling), stock comparison
ui/          Streamlit views, components, and breakdown dropdowns
app.py       Entry point: sidebar config, session management, chat loop
```

**A note on performance:** a `DataBundle` architecture (`scoring/orchestrator.py`) fetches all Yahoo Finance endpoints once per analysis and passes the bundle to every analyzer, cutting HTTP requests from ~18–20 down to ~8 and avoiding rate-limit issues.

---

## Tech stack

- **Language:** Python
- **Frontend:** Streamlit, Altair
- **AI:** OpenAI GPT (function calling)
- **Data:** Yahoo Finance (`yfinance`), pandas, NumPy

---

## Running locally

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Launch the app
streamlit run app.py
```

You'll be prompted for an OpenAI API key in the sidebar (it is never stored or shared). Enter a ticker or ask a question to get started.

---

## What I'd do next

- Integrate a paid market-data source to enable rigorous **backtesting**
- Use backtest results to **recalibrate dimension weights** empirically
- Expand the event-driven dimension with a broader event taxonomy
