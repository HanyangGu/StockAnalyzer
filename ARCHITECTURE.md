# ARCHITECTURE.md
# Stock Analysis Chatbot — Final V2

## Overview

A real-time stock analysis chatbot built with Python and Streamlit. The user types natural
language queries ("analyze NVDA", "compare AAPL and MSFT", "price of Tesla") and the app
returns technical analysis, fundamental analysis, a composite investment score, and an
AI-generated summary — all powered by Yahoo Finance data and OpenAI GPT.

**Stack:**
- Python 3.10+
- Streamlit (UI framework)
- OpenAI GPT (natural language + tool routing)
- yfinance 1.2.0 (market data)
- pandas / numpy (data processing)

**Entry point:** `app.py`
**Total lines:** ~3,200 across 8 files

---

## File Structure

```
Final V2/
├── app.py            # Streamlit UI — entry point (995 lines)
├── ai.py             # GPT tools, system prompt, StockChatbot class (406 lines)
├── scorer.py         # Technical scoring engine (507 lines)
├── fundamentals.py   # Fundamental data fetch + scoring (380 lines)
├── indicators.py     # 9 technical indicator calculations (329 lines)
├── data.py           # Yahoo Finance data fetching + ticker resolution (321 lines)
├── comparison.py     # Multi-stock comparison logic (158 lines)
├── config.py         # All constants and thresholds (85 lines)
└── ARCHITECTURE.md   # This file
```

---

## Module Dependency Graph

```
app.py
  └── ai.py
        ├── scorer.py
        │     ├── fundamentals.py
        │     │     └── data.py
        │     ├── indicators.py
        │     └── data.py
        ├── comparison.py
        │     └── scorer.py
        └── data.py

config.py  ← imported by all modules (no dependencies itself)
```

Rule: dependencies flow downward only. No circular imports.
`config.py` is a leaf — it imports nothing from this project.

---

## Module Descriptions

### `config.py` — Constants
All numeric thresholds and configuration in one place. No logic.

| Constant | Value | Purpose |
|---|---|---|
| `GPT_MODEL` | `"gpt-4o"` | Default model (overridden by UI selector) |
| `TEMPERATURE` | `0.3` | GPT response consistency |
| `DATA_PERIOD` | `"1y"` | Historical data window for indicators |
| `DATA_INTERVAL` | `"1d"` | Daily candles |
| `MIN_DATA_POINTS` | `30` | Minimum trading days required |
| `RSI_PERIOD` | `14` | RSI lookback window |
| `RSI_OVERSOLD` | `30` | RSI buy threshold |
| `RSI_OVERBOUGHT` | `70` | RSI sell threshold |
| `STOCH_PERIOD` | `14` | Stochastic lookback |
| `STOCH_OVERSOLD` | `20` | Stochastic buy threshold |
| `STOCH_OVERBOUGHT` | `80` | Stochastic sell threshold |
| `ROC_PERIOD` | `10` | Rate of Change lookback |
| `MACD_FAST` | `12` | MACD fast EMA period |
| `MACD_SLOW` | `26` | MACD slow EMA period |
| `MACD_SIGNAL` | `9` | MACD signal line period |
| `MA_SHORT` | `20` | 20-day moving average |
| `MA_MID` | `50` | 50-day moving average |
| `MA_LONG` | `200` | 200-day moving average |
| `BB_PERIOD` | `20` | Bollinger Bands MA window |
| `BB_STD` | `2` | Bollinger Bands standard deviation multiplier |
| `ATR_PERIOD` | `14` | Average True Range lookback |
| `VOLUME_RISING` | `1.1` | Volume ratio threshold for "rising" |
| `VOLUME_FALLING` | `0.9` | Volume ratio threshold for "falling" |
| `VOLUME_LOOKBACK` | `5` | Recent days for volume comparison |
| `MIN_STOCKS` | `2` | Minimum stocks for comparison |
| `MAX_STOCKS` | `3` | Maximum stocks for comparison |

---

### `data.py` — Data Fetching & Ticker Resolution

All Yahoo Finance interaction. Every function adds `time.sleep(1)` to avoid rate limiting.

**Functions:**

`resolve_ticker(company: str) -> str`
- Converts company names or partial tickers to valid Yahoo Finance symbols
- Priority: (1) try input directly as ticker → (2) search by company name → (3) return input uppercased
- Example: `"Apple"` → `"AAPL"`, `"nvidia"` → `"NVDA"`

`validate_companies(companies: list) -> dict`
- Deduplicates and validates a list of companies for comparison
- Enforces MIN_STOCKS (2) and MAX_STOCKS (3) limits
- Returns `{"valid": True, "tickers": [...]}` or `{"valid": False, "error": "..."}`

`fetch_price_data(ticker_symbol: str) -> dict`
- Fetches live price snapshot: current price, change, volume, market cap, P/E, 52W high/low
- Returns `{"error": "..."}` on failure — never raises exceptions to caller

`fetch_price_data_historical(ticker_symbol: str, date: str) -> dict`
- Same structure as `fetch_price_data` but for a specific past date
- Used exclusively by backtest mode
- Finds the closest trading day to the requested date

`fetch_historical_data(ticker_symbol: str, end_date: str = None) -> dict`
- Fetches 1 year of daily OHLCV data for indicator calculation
- If `end_date` provided: fetches data up to that date (backtest mode)
- Returns `{"success": True, "df": DataFrame, "closes": Series}` or `{"success": False, "error": "..."}`

---

### `indicators.py` — Technical Indicators

Pure calculation functions. Each takes pandas Series/DataFrame and returns a dict with
`value`, `signal`, and `icon`. No side effects, no external calls.

**9 indicators grouped by category:**

#### Momentum
| Function | Indicator | Input | Key output |
|---|---|---|---|
| `compute_rsi(closes)` | RSI-14 | Close prices | value (0-100), oversold/overbought signal |
| `compute_stochastic(df)` | Stochastic-14 | OHLC DataFrame | %K value (0-100) |
| `compute_roc(closes)` | Rate of Change-10 | Close prices | % price change over 10 days |

#### Trend
| Function | Indicator | Input | Key output |
|---|---|---|---|
| `compute_macd(closes)` | MACD (12/26/9) | Close prices | histogram, signal_label, crossover direction |
| `compute_moving_averages(closes, price)` | MA20, MA50, MA200 | Close prices + current price | above/below boolean per MA |
| `compute_golden_cross(closes)` | Golden/Death Cross | Close prices | golden (bool), fresh vs active |

#### Volatility
| Function | Indicator | Input | Key output |
|---|---|---|---|
| `compute_bollinger_bands(closes, price)` | BB (20, 2σ) | Close prices + current price | pct position (0-100), clamped |
| `compute_atr(df)` | ATR-14 | OHLC DataFrame | absolute value + % of price |

#### Volume
| Function | Indicator | Input | Key output |
|---|---|---|---|
| `compute_volume_trend(df)` | Volume ratio | OHLC DataFrame | recent/average ratio |

---

### `scorer.py` — Scoring Engine

Orchestrates indicators into scores. The master function `technical_analysis()` calls
everything else and returns a complete serializable result dict.

**Scoring architecture:**

```
technical_analysis(company, backtest_date)
  ├── resolve_ticker()              # data.py
  ├── fetch_price_data()            # data.py (or fetch_price_data_historical in backtest)
  ├── fetch_historical_data()       # data.py
  ├── compute_rsi()                 # indicators.py
  ├── compute_stochastic()          # indicators.py
  ├── compute_roc()                 # indicators.py
  ├── compute_macd()                # indicators.py
  ├── compute_moving_averages()     # indicators.py
  ├── compute_golden_cross()        # indicators.py
  ├── compute_bollinger_bands()     # indicators.py
  ├── compute_atr()                 # indicators.py
  ├── compute_volume_trend()        # indicators.py
  ├── score_short_term()            # internal
  ├── score_mid_term()              # internal
  ├── score_long_term()             # internal
  └── fundamental_analysis()        # fundamentals.py
```

**Time horizon scoring:**

| Horizon | Weight in Overall | Indicators used | Max points |
|---|---|---|---|
| Short term | 30% | RSI (25pts) + Stochastic (20pts) + ROC (20pts) + Bollinger Bands (15pts) | 80pts + penalty |
| Mid term | 35% | MACD (30pts) + MA20 (15pts) + MA50 (20pts) + ATR (10pts) + Volume (15pts) | 90pts + penalty |
| Long term | 35% | MA200 (35pts) + Golden Cross (40pts) + Volume (15pts) | 90pts + penalty |

**Downtrend penalty** (applied to all 3 horizons via `check_downtrend()`):
- Price below MA20 + MA50 + MA200: -30 points (structural downtrend)
- Price below MA200 only: -20 points (long-term breakdown)
- Price below MA20 + MA50 but above MA200: 0 (temporary pullback, no penalty)

**Verdict labels** (all horizons use same scale):

| Score | Label |
|---|---|
| 75-100 | Strong Uptrend |
| 60-74 | Uptrend |
| 40-59 | Neutral |
| 25-39 | Downtrend |
| 0-24 | Strong Downtrend |

**Overall score formula:**
```
overall = round(short * 0.30 + mid * 0.35 + long * 0.35)
```

**Return structure of `technical_analysis()`:**
```python
{
  "ticker":           str,
  "company":          str,
  "current_price":    float,
  "price_change":     float,
  "price_change_pct": float,
  "backtest_date":    str,          # "live" or "YYYY-MM-DD"
  "short_term":       {"score", "verdict", "icon", "signals": []},
  "mid_term":         {"score", "verdict", "icon", "signals": []},
  "long_term":        {"score", "verdict", "icon", "signals": []},
  "overall":          {"score", "verdict", "icon"},
  "indicators": {
    "rsi", "stoch", "roc", "macd", "mas", "golden", "bb", "atr", "volume"
  },
  "fundamental":      {"score", "verdict", "icon", "signals": []},
  "fund_details":     {"valuation", "profitability", "growth", "health", "analyst"},
  "timestamp":        str
}
```

---

### `fundamentals.py` — Fundamental Analysis

Fetches and scores business-quality metrics from `yf.Ticker().info`.
Runs after technical analysis completes. Errors are non-blocking — if
Yahoo Finance returns no fundamental data, `scorer.py` continues with
`fundamental.score = None`.

**`fetch_fundamental_data(ticker_symbol)` — fields fetched:**

| Category | Fields |
|---|---|
| Valuation | trailingPE, forwardPE, priceToBook, priceToSalesTrailing12Months |
| Profitability | grossMargins, profitMargins, returnOnEquity, returnOnAssets |
| Growth | revenueGrowth, earningsGrowth, trailingEps, forwardEps |
| Financial Health | debtToEquity, currentRatio, freeCashflow, totalRevenue |
| Analyst Targets | targetMeanPrice, targetHighPrice, targetLowPrice, recommendationKey, numberOfAnalystOpinions |

**`score_fundamentals(data)` — scoring breakdown (0-100):**

| Category | Max pts | Metrics | Key thresholds |
|---|---|---|---|
| Valuation | 25 | P/E (15pts) + Forward P/E (10pts) | P/E < 15 = undervalued, > 40 = expensive. Negative Forward P/E = 0pts |
| Profitability | 25 | Net Margin (13pts) + ROE (12pts) | Net Margin > 20% = excellent. ROE > 20% = excellent |
| Growth | 25 | Revenue Growth (13pts) + Earnings Growth (12pts) | Revenue > 20% = strong. Earnings growth capped at 3pts if revenue declining |
| Health | 25 | Debt/Equity (13pts) + Current Ratio (12pts) | D/E < 50 = low debt. Current Ratio > 2 = very liquid |

**Fundamental verdict labels:**

| Score | Label |
|---|---|
| 75-100 | Strong Fundamentals |
| 60-74 | Good Fundamentals |
| 40-59 | Mixed Fundamentals |
| 25-39 | Weak Fundamentals |
| 0-24 | Poor Fundamentals |

**Important note on backtest mode:** Fundamental data is always fetched live, even
when backtesting. Yahoo Finance's free API does not provide historical snapshots of
P/E, margins, or growth figures.

---

### `comparison.py` — Multi-Stock Comparison

Compares 2-3 stocks side by side. Calls `technical_analysis()` on each stock,
then ranks and aggregates results.

**`compare_stocks(companies: list) -> dict`**

Steps:
1. Validate input via `validate_companies()` (2-3 stocks, deduped)
2. Run `technical_analysis()` on each stock sequentially
3. Sort by overall score descending
4. Assign medals: 🥇 🥈 🥉
5. Build flat comparison table (all indicators side by side)
6. Identify best picks per dimension

**Best picks identified:**
- Best Overall (highest overall technical score)
- Best Short term
- Best Mid term
- Best Long term
- Lowest Risk (lowest ATR %)
- Best Fundamentals (highest fundamental score)

**Return structure:**
```python
{
  "stocks_analysed":  int,
  "ranking":          [{"rank", "medal", "ticker", "company", "score",
                        "verdict", "icon", "short_score", "mid_score",
                        "long_score", "fund_score", "fund_verdict"}],
  "comparison_table": {ticker: {all 25+ indicator fields}},
  "best_picks":       {"overall", "short_term", "mid_term", "long_term",
                       "lowest_risk", "fundamentals"},
  "partial_failure":  bool,
  "errors":           [],
  "timestamp":        str
}
```

---

### `ai.py` — GPT Integration

Contains the GPT tool definitions, system prompt, tool router, and `StockChatbot` class.

**3 GPT tools defined:**

| Tool name | Triggers when user asks about | Calls |
|---|---|---|
| `fetch_price_data` | Current price, volume, market cap, 52W high/low | `data.fetch_price_data()` |
| `technical_analysis` | Is X a good buy? Analyze X. Show X. Technical outlook for X. | `scorer.technical_analysis()` |
| `compare_stocks` | Compare X and Y. Which is better X or Y. Rank X Y Z. | `comparison.compare_stocks()` |

**System prompt key rules:**
- Always use `technical_analysis` tool for any stock analysis request
- Respond with only a 2-4 sentence summary after tool returns data
- Never reproduce raw numbers or scores in the summary
- Always end with disclaimer
- If no tool called, answer conversationally

**`StockChatbot` class:**

```python
class StockChatbot:
    client: OpenAI
    history: list          # trimmed to last 6 messages
    turn: int
    model: str             # read from session state at init
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_requests: int

    def chat(user_message) -> dict
    def reset()
    def get_history_summary()
```

**`chat()` return types:**
```python
{"type": "single_stock", "data": {...}, "summary": "..."}
{"type": "comparison",   "data": {...}, "summary": "..."}
{"type": "price",        "data": {...}, "summary": "..."}
{"type": "text",                        "summary": "..."}
{"type": "error",                       "summary": "..."}
```

**History trimming:** Keeps last 6 messages (3 user/assistant pairs) to control
token usage. Older context is dropped silently.

**Error handling:**
- Rate limit (429): returns error dict immediately, does not retry
- Quota exceeded: returns billing message
- Tool execution failure: returns error in result dict, does not crash

---

### `app.py` — Streamlit UI

Entry point. All rendering logic. No business logic — delegates everything
to other modules via `StockChatbot.chat()`.

**Session state keys:**

| Key | Type | Purpose |
|---|---|---|
| `bot` | `StockChatbot \| None` | Active chatbot instance |
| `messages` | `list` | Chat history for display |
| `last_result` | `dict \| None` | Most recent analysis result for rendering |
| `selected_model` | `str` | Current GPT model string |
| `current_model` | `str` | Previous model (detects model switches) |
| `api_key` | `str \| None` | OpenAI API key |
| `backtest_mode` | `bool` | Backtest toggle state (persisted) |
| `backtest_date` | `str \| None` | Selected backtest date as "YYYY-MM-DD" |
| `backtest_date_value` | `date` | Date picker value (persisted) |
| `pending_input` | `str` | Input queued from sidebar button click |

**Render function map:**

| Function | Renders | Called by |
|---|---|---|
| `render_score_cards(data)` | 5 score cards (Short/Mid/Long/Overall/Fundamental) | `render_single_analysis` |
| `render_price_line(data)` | Price with colored up/down arrow | `render_single_analysis`, `render_price_only` |
| `render_decision_panel(data)` | Composite score + quadrant decision | `render_single_analysis` |
| `render_signals(data)` | Expandable indicator breakdown (3 columns) | `render_single_analysis` |
| `render_fundamentals(data)` | Expandable fundamental panel (4 columns) | `render_single_analysis` |
| `render_backtest_comparison(data)` | Validation panel (price then vs now) | `render_single_analysis` (backtest only) |
| `render_single_analysis(data, summary)` | Full single-stock panel | `main()` |
| `render_price_only(data, summary)` | 8-metric price panel | `main()` |
| `render_comparison(data, summary)` | Ranking + table + decision cards + best picks | `main()` |

**Composite score formula (in `get_composite()`):**
```
composite = round(technical * 0.60 + fundamental * 0.40)
```

**Investment decision quadrant logic:**

```
THRESHOLD = 50
high_t = technical >= THRESHOLD
high_f = fundamental >= THRESHOLD

if high_t and high_f:     → Strong Buy
if high_t and not high_f: → Trader Play
if not high_t and high_f: → Value Opportunity
if not high_t and high_f: → Avoid
```

**Backtest validation logic:**
- Computes composite decision for the backtest date
- Fetches current live price for comparison
- Marks CORRECT if: bullish decision (Strong Buy / Value Opportunity / Trader Play) + price rose > 5%
- Marks CORRECT if: bearish decision (Avoid) + price fell > 5%
- Marks NEUTRAL if: price moved < 5% in either direction
- Otherwise: marks INCORRECT

---

## Data Flow — Single Stock Analysis

```
User types: "analyze NVDA"
        │
        ▼
StockChatbot.chat()
        │
        ├─ GPT decides to call: technical_analysis(company="NVDA")
        │
        ▼
handle_tool_call("technical_analysis", {"company": "NVDA"})
        │
        ├─ injects backtest_date from session state if set
        │
        ▼
technical_analysis("NVDA", backtest_date=None)
        │
        ├─ resolve_ticker("NVDA")             → "NVDA"
        ├─ fetch_price_data("NVDA")           → {current_price, change, ...}
        ├─ fetch_historical_data("NVDA")      → {df, closes, days}
        │
        ├─ compute_rsi(closes)                → {value, signal, icon}
        ├─ compute_stochastic(df)             → {value, signal, icon}
        ├─ compute_roc(closes)                → {value, signal, icon}
        ├─ compute_macd(closes)               → {macd, signal, histogram, ...}
        ├─ compute_moving_averages(closes, p) → {ma20, ma50, ma200}
        ├─ compute_golden_cross(closes)       → {signal, golden, ...}
        ├─ compute_bollinger_bands(closes, p) → {upper, middle, lower, pct, ...}
        ├─ compute_atr(df)                    → {value, pct, signal, icon}
        ├─ compute_volume_trend(df)           → {ratio, signal, icon}
        │
        ├─ score_short_term(rsi, stoch, roc, bb, mas)
        ├─ score_mid_term(macd, mas, atr, vol)
        ├─ score_long_term(mas, golden, vol)
        ├─ overall = short*0.30 + mid*0.35 + long*0.35
        │
        └─ fundamental_analysis("NVDA")
              ├─ fetch_fundamental_data("NVDA")
              └─ score_fundamentals(data)
        │
        ▼
Result dict returned as JSON to GPT
        │
        ▼
GPT generates 2-4 sentence summary
        │
        ▼
StockChatbot.chat() returns:
  {"type": "single_stock", "data": {...}, "summary": "..."}
        │
        ▼
app.py render_single_analysis(data, summary)
  ├─ render_score_cards()       → 5 score cards
  ├─ render_decision_panel()    → composite score + quadrant
  ├─ render_signals()           → expandable indicator breakdown
  └─ render_fundamentals()      → expandable fundamental panel
```

---

## Data Flow — Comparison

```
User types: "compare NVDA and AAPL"
        │
        ▼
GPT calls: compare_stocks(companies=["NVDA", "AAPL"])
        │
        ▼
compare_stocks(["NVDA", "AAPL"])
        │
        ├─ validate_companies()
        ├─ technical_analysis("NVDA")   ← full flow as above
        ├─ technical_analysis("AAPL")   ← full flow as above
        ├─ sort by overall score
        ├─ assign medals
        ├─ build comparison_table
        └─ identify best picks
        │
        ▼
Result dict returned to GPT → summary generated
        │
        ▼
app.py render_comparison(data, summary)
  ├─ ranking cards (medal + score per stock)
  ├─ comparison table (all indicators side by side)
  ├─ per-stock decision cards (composite + quadrant)
  └─ best picks (6 categories)
```

---

## Query Routing

GPT handles intent detection via tool descriptions. The three tools have
descriptions engineered to avoid overlap:

```
"price of X"          → fetch_price_data       (price/market data only)
"analyze X"           → technical_analysis     (single stock, full analysis)
"compare X and Y"     → compare_stocks         (multiple stocks)
"which is better..."  → compare_stocks         (comparison phrasing)
"what is a golden..."  → no tool               (conversational fallback)
```

If GPT does not call a tool, `StockChatbot.chat()` detects `tool_result is None`
and returns `{"type": "text", "summary": response}` for plain text rendering.

---

## Backtest Mode

When the sidebar toggle is enabled:

1. `st.session_state.backtest_date` is set to `"YYYY-MM-DD"` string
2. On `technical_analysis()` call, `ai.py._run_analysis()` injects this date
3. `scorer.py` passes it to `fetch_price_data_historical()` and `fetch_historical_data(end_date=...)`
4. Historical indicators are computed on data up to that date only
5. Fundamental data is always fetched live (no historical snapshots available)
6. After rendering, `render_backtest_comparison()` fetches current live price for validation

**Date range:** 2021-01-01 to yesterday (limited by Yahoo Finance daily data availability)

---

## Error Handling Strategy

All errors are soft — the app never crashes to a blank screen.

| Layer | Error type | Handling |
|---|---|---|
| `data.py` | Yahoo Finance rate limit | Returns `{"error": "rate limited..."}` |
| `data.py` | Invalid ticker | Returns `{"error": "could not retrieve..."}` |
| `data.py` | Insufficient data | Returns `{"success": False, "error": "..."}` |
| `fundamentals.py` | Any exception | Returns `{"error": str(e)}` |
| `scorer.py` | Fundamental failure | Sets `fundamental.score = None`, continues |
| `comparison.py` | One stock fails | Continues with remaining stocks, sets `partial_failure = True` |
| `ai.py` | OpenAI rate limit (429) | Returns error dict immediately, does not retry |
| `ai.py` | Quota exceeded | Returns billing message |
| `ai.py` | Unknown tool name | Returns `{"error": "Unknown tool..."}` |
| `app.py` | Backtest validation | `try/except` with `st.warning()` |

---

## Known Limitations

### Technical Scorer
- Bear market bottoms are undetectable — trailing indicators are maximally bearish at exact bottoms
- Downtrend penalty (-30pts) suppresses scores broadly during market-wide selloffs
- Golden cross/death cross lag by weeks after the actual trend change
- All 9 indicators are price-based and backward-looking

### Fundamental Scorer
- P/E thresholds are sector-agnostic — P/E 40 is expensive for utilities, normal for growth tech
- Apple's Current Ratio (0.97) flags as "liquidity risk" — Apple intentionally runs low current ratio
- Berkshire Hathaway's Price/Book returns N/A from Yahoo Finance
- Negative ROE (e.g. RIVN) correctly scores 0 but no distinction between "early stage" vs "structurally unprofitable"
- Earnings growth on declining revenue capped at 3pts (GME fix) but still scores positive

### Data
- Backtest fundamental data is always live, not historical
- Historical data availability: reliable from ~2021-01-01
- Futures / commodities return no P/E or Market Cap (handled gracefully with N/A)
- Yahoo Finance rate limits at high usage — 1 second sleep between calls mitigates this

---

## Configuration Reference

To change a threshold, edit `config.py` only — all modules import from there.

To add a new indicator:
1. Add calculation function to `indicators.py`
2. Call it in `scorer.py` inside `technical_analysis()`
3. Add scoring logic to the relevant `score_short_term/mid_term/long_term()` function
4. Add display to `app.py` inside `render_signals()`

To add a new fundamental metric:
1. Add the `yf.Ticker().info` field to `fetch_fundamental_data()` in `fundamentals.py`
2. Add scoring logic to `score_fundamentals()`
3. Add display to `app.py` inside `render_fundamentals()`

---

*Last updated: March 2026 — Final V2 build*
