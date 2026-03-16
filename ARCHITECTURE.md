# 🏗️ Architecture Overview

This document describes the technical architecture of the Real-Time Stock Analysis Chatbot, including the system design, data flow, component breakdown, and scoring logic.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     STREAMLIT FRONTEND                       │
│                                                             │
│   Sidebar              Main Area            Analysis Panel  │
│   ─────────────        ─────────────        ───────────────  │
│   API Key Input        Chat History         Score Cards     │
│   Model Selector       Chat Input           Indicator Table │
│   Example Queries      Confirmation Msg     Comparison View │
│   Reset Button         GPT Summary          Rankings        │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                       AI LAYER                               │
│                                                             │
│   StockChatbot                    handle_tool_call()        │
│   ─────────────                   ──────────────────        │
│   chat()                          TOOL_REGISTRY             │
│   history management              tool routing              │
│   tool execution loop             error handling            │
│   model configuration                                       │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     ANALYSIS LAYER                           │
│                                                             │
│   technical_analysis()     compare_stocks()                 │
│   ─────────────────────    ────────────────                 │
│   score_short_term()       validate_companies()             │
│   score_mid_term()         rank by overall score            │
│   score_long_term()        build comparison table           │
│   check_downtrend()        identify best picks              │
│   get_verdict()                                             │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    INDICATOR LAYER                           │
│                                                             │
│   Momentum          Trend              Volatility  Volume   │
│   ─────────         ──────             ──────────  ──────   │
│   compute_rsi()     compute_macd()     compute_bb()         │
│   compute_stoch()   compute_mas()      compute_atr()        │
│   compute_roc()     compute_golden()   compute_vol()        │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│                                                             │
│   fetch_price_data()           fetch_historical_data()      │
│   ─────────────────            ───────────────────────      │
│   real-time snapshot           6 months OHLCV data          │
│   price, volume, market cap    used for all indicators      │
│   1-min intraday data          validated before use         │
│                                                             │
│   resolve_ticker()             validate_companies()         │
│   ────────────────             ───────────────────          │
│   name to ticker               min/max stock limits         │
│   Yahoo Finance search         duplicate removal            │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   EXTERNAL SERVICES                          │
│                                                             │
│   Yahoo Finance API            OpenAI API                   │
│   ────────────────             ──────────                   │
│   Real-time prices             GPT model                    │
│   Historical OHLCV             Tool calling                 │
│   Company metadata             Natural language             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📂 File Structure

```
project/
  ├── app.py                        # Everything in one file
  │   ├── Section 1                 # Imports & Config
  │   ├── Section 2                 # Ticker Resolution
  │   ├── Section 3                 # Data Fetcher
  │   ├── Section 4                 # Technical Indicators
  │   ├── Section 5                 # Scorer
  │   ├── Section 6                 # Stock Comparison
  │   ├── Section 7                 # AI Tools & System Prompt
  │   ├── Section 8                 # Tool Router
  │   ├── Section 9                 # StockChatbot Class
  │   └── Section 10               # Streamlit UI
  │
  ├── requirements.txt              # Python dependencies
  ├── run.bat                       # Windows launcher
  ├── README.md                     # Project overview
  ├── ARCHITECTURE.md               # This file
  └── stock_analysis_backend.ipynb  # Development notebook
```

---

## 🔄 Request Lifecycle

### Single Stock Analysis

```
1. User types "analyze NVDA"
         │
2. StockChatbot.chat()
   adds message to history
         │
3. OpenAI API called
   GPT reads SYSTEM_PROMPT + tools list + history
         │
4. GPT decides to call technical_analysis(company="NVDA")
         │
5. handle_tool_call() routes to technical_analysis()
         │
6. resolve_ticker("NVDA") → "NVDA"
         │
7. fetch_price_data("NVDA")
   → current price, change, market cap, volume
         │
8. fetch_historical_data("NVDA")
   → 1 year of daily OHLCV data (252 trading days)
         │
9. Compute all 9 indicators
   ├── compute_rsi(closes)
   ├── compute_stochastic(df)
   ├── compute_roc(closes)
   ├── compute_macd(closes)
   ├── compute_moving_averages(closes, price)
   ├── compute_golden_cross(closes)
   ├── compute_bollinger_bands(closes, price)
   ├── compute_atr(df)
   └── compute_volume_trend(df)
         │
10. Score each time horizon
    ├── score_short_term(rsi, stoch, roc, bb, mas)
    ├── score_mid_term(macd, mas, atr, vol)
    └── score_long_term(mas, golden, vol)
         │
11. check_downtrend(mas) applied to each horizon
    penalty applied if structural downtrend detected
         │
12. Overall score = weighted average
    Short 30% + Mid 35% + Long 35%
         │
13. make_serializable() converts numpy types
         │
14. Result returned as JSON to GPT
         │
15. GPT generates 2-4 sentence summary
         │
16. chat() returns structured dict
    { type, data, summary }
         │
17. Streamlit renders:
    ├── Score cards (4 colored metric cards)
    ├── Price line with arrow
    ├── Expandable indicator breakdown
    └── GPT summary in blue info box
```

---

### Multi Stock Comparison

```
1. User types "compare NVDA, AMD and Intel"
         │
2. GPT calls compare_stocks(companies=["NVDA","AMD","Intel"])
         │
3. validate_companies() checks:
   ├── Minimum 2 stocks
   ├── Maximum 3 stocks
   └── Remove duplicates
         │
4. For each company:
   └── technical_analysis(company) called
       (full single stock flow above)
         │
5. Results sorted by overall score descending
         │
6. Medals assigned 🥇🥈🥉
         │
7. Comparison table built
   (all indicators side by side)
         │
8. Best picks identified:
   ├── best_overall   (highest overall score)
   ├── best_short     (highest short term score)
   ├── best_mid       (highest mid term score)
   ├── best_long      (highest long term score)
   └── lowest_risk    (lowest ATR percentage)
         │
9. Result returned to GPT
         │
10. GPT generates comparison summary
          │
11. Streamlit renders:
    ├── Ranking cards with medals
    ├── Horizontal comparison dataframe
    ├── Best picks metric cards
    └── GPT summary in blue info box
```

---

## 🧮 Scoring Logic

### Baseline
```
All scoring functions start at 0
Every indicator must earn its score
Maximum possible = 100 per horizon
```

### Short Term Scoring (max 100pts)

```
RSI              max 25pts
  < 30           +25  (oversold -- strong buy)
  < 45           +18  (mildly oversold)
  > 70           +5   (overbought)
  > 55           +8   (mildly overbought)
  else           +12  (neutral)

Stochastic       max 20pts
  < 20           +20  (oversold -- strong buy)
  < 35           +14  (mildly oversold)
  > 80           +4   (overbought)
  > 65           +7   (mildly overbought)
  else           +10  (neutral)

ROC              max 20pts
  > 5%           +20  (strong positive momentum)
  > 0%           +12  (mild positive momentum)
  < -5%          +0   (strong negative momentum)
  else           +4   (mild negative momentum)

Bollinger Bands  max 15pts
  pct < 20%      +15  (near lower band -- bounce)
  pct > 80%      +3   (near upper band -- pullback)
  else           +8   (mid band -- neutral)

Downtrend Penalty (Fix applied to all horizons)
  All 3 MAs below    -30  (structural collapse)
  Below MA200 only   -20  (long term breakdown)
  Below MA20+MA50
  but above MA200     0   (temporary pullback)
  Minor dip           0   (no structural concern)
```

### Mid Term Scoring (max 100pts)

```
MACD             max 30pts
  Bullish cross  +30
  Bearish cross  +0
  Neutral        +12

MA20             max 15pts
  Price above    +15
  Price below
  + above MA200  +5   (partial credit -- pullback)
  Price below
  + below MA200  +0   (structural breakdown)

MA50             max 20pts
  Price above    +20
  Price below
  + above MA200  +7   (partial credit -- pullback)
  Price below
  + below MA200  +0   (structural breakdown)

ATR              max 10pts
  pct < 1.5%     +10  (low volatility)
  pct < 3%       +6   (moderate volatility)
  else           +2   (high volatility)

Volume           max 15pts
  ratio > 1.1    +15  (rising -- confirms move)
  ratio < 0.9    +0   (falling -- weak conviction)
  else           +7   (stable)
```

### Long Term Scoring (max 100pts)

```
MA200            max 35pts
  Price above    +35
  Price below    +0

Golden Cross     max 40pts
  Fresh golden   +40  (MA50 just crossed above MA200)
  Golden active  +28  (MA50 above MA200)
  Fresh death    +0   (MA50 just crossed below MA200)
  Death active   +5   (MA50 below MA200)

Volume Trend     max 15pts
  Rising         +15
  Falling        +0
  Stable         +7
```

### Overall Score Weighting

```
Overall = (Short × 0.30) + (Mid × 0.35) + (Long × 0.35)

Short term carries less weight (30%)
-- faster signals, more noise

Mid and Long term carry more weight (35% each)
-- slower signals, more reliable
```

---

## 🤖 AI Tool Definitions

Three tools are registered with OpenAI:

```python
fetch_price_data(ticker_symbol)
-- Called when: user asks for price, market cap, volume
-- Returns: real-time snapshot dict

technical_analysis(company)
-- Called when: user asks if stock is good to buy,
               requests analysis, asks about outlook
-- Returns: full scored analysis dict

compare_stocks(companies)
-- Called when: user mentions multiple companies,
               asks to compare or rank stocks
-- Returns: ranked comparison dict
```

### Tool Routing

```
GPT returns tool_call
        │
handle_tool_call(name, args)
        │
TOOL_REGISTRY lookup
        │
        ├── "fetch_price_data"   → fetch_price_data(ticker)
        ├── "technical_analysis" → technical_analysis(company)
        └── "compare_stocks"     → compare_stocks(companies)
                │
        json.dumps(result)
                │
        returned to GPT as tool result
```

---

## 💬 Conversation Flow

```
StockChatbot maintains history list:

[
  {"role": "user",      "content": "analyze NVDA"},
  {"role": "assistant", "tool_calls": [...]},
  {"role": "tool",      "content": "{...json...}"},
  {"role": "assistant", "content": "GPT summary"},
  ...
]

Each turn:
1. User message appended to history
2. Full history sent to OpenAI API
3. If tool called: result appended, loop continues
4. If text reply: summary extracted, loop exits
5. Structured dict returned to Streamlit
```

---

## 🔐 Configuration Constants

All configurable values are defined in Section 1:

```python
# AI
GPT_MODEL         = "gpt-4o"        # model string
TEMPERATURE       = 0.3             # response consistency

# Data
DATA_PERIOD       = "1y"            # historical data window
DATA_INTERVAL     = "1d"            # daily candles
MIN_DATA_POINTS   = 30              # minimum trading days

# Stock limits
MIN_STOCKS        = 2               # comparison minimum
MAX_STOCKS        = 3               # comparison maximum

# Scoring
BASELINE_SCORE    = 0               # starts at 0, earn upward

# RSI
RSI_PERIOD        = 14
RSI_OVERSOLD      = 30
RSI_OVERBOUGHT    = 70

# Stochastic
STOCH_PERIOD      = 14
STOCH_OVERSOLD    = 20
STOCH_OVERBOUGHT  = 80

# ROC
ROC_PERIOD        = 10

# MACD
MACD_FAST         = 12
MACD_SLOW         = 26
MACD_SIGNAL       = 9

# Moving Averages
MA_SHORT          = 20
MA_MID            = 50
MA_LONG           = 200

# Bollinger Bands
BB_PERIOD         = 20
BB_STD            = 2

# ATR
ATR_PERIOD        = 14

# Volume
VOLUME_RISING     = 1.1
VOLUME_FALLING    = 0.9
VOLUME_LOOKBACK   = 5
```

---

## 🛡️ Error Handling

```
Level 1 -- Data validation
  fetch_historical_data() checks:
  ├── Empty dataframe
  └── Less than MIN_DATA_POINTS rows

Level 2 -- Input validation
  validate_companies() checks:
  ├── Minimum 2 stocks
  ├── Maximum 3 stocks
  └── Duplicate removal

Level 3 -- Ticker resolution
  resolve_ticker() fallback chain:
  ├── Try direct as ticker
  ├── Search by company name
  └── Return cleaned input as fallback

Level 4 -- JSON serialization
  make_serializable() converts:
  ├── numpy.bool_ → bool
  ├── numpy.integer → int
  └── numpy.floating → float

Level 5 -- API errors
  chat() handles:
  ├── Rate limit errors → retry with backoff
  ├── Max iterations exceeded → error message
  └── General exceptions → error dict returned

Level 6 -- Tool errors
  handle_tool_call() handles:
  ├── Unknown tool name → error with available tools
  ├── Missing arguments → KeyError caught separately
  └── General failures → error message returned
```

---

## 📊 Data Flow Diagram

```
Yahoo Finance
      │
      ├── stock.info          → price, market cap, PE ratio,
      │                         52w high/low, sector, volume
      │
      └── stock.history()     → OHLCV DataFrame
            │
            ├── Close Series  → RSI, ROC, MACD, MAs,
            │                   Golden Cross, Bollinger Bands
            │
            └── Full DataFrame → Stochastic, ATR, Volume Trend
                  │
                  ▼
            9 Indicator Dicts
            { value, signal, icon }
                  │
                  ▼
            3 Score Dicts
            { score, verdict, icon, signals[] }
                  │
                  ▼
            1 Analysis Dict
            { ticker, company, price, short_term,
              mid_term, long_term, overall, indicators }
                  │
                  ▼
            make_serializable()
                  │
                  ▼
            json.dumps() → OpenAI API
                  │
                  ▼
            GPT Summary Text
                  │
                  ▼
            { type, data, summary }
                  │
                  ▼
            Streamlit UI Components
```

---

*Real-Time Stock Analysis Chatbot -- Architecture Document*
