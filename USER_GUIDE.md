# 📖 User Guide

Complete guide to using the Real-Time Stock Analysis Chatbot effectively.

---

## 🖥️ Interface Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER WINDOW                          │
│                                                                 │
│  ┌──────────────┐  ┌───────────────────────────────────────┐   │
│  │   SIDEBAR    │  │            MAIN AREA                  │   │
│  │              │  │                                       │   │
│  │ 🔑 API Key   │  │  📈 Real-Time Stock Analysis Chatbot  │   │
│  │              │  │  ─────────────────────────────────    │   │
│  │ 🤖 Model     │  │                                       │   │
│  │    Selector  │  │  [Chat History]                       │   │
│  │              │  │                                       │   │
│  │ 💬 Example   │  │  ─────────────────────────────────    │   │
│  │    Queries   │  │  [Analysis Panel]                     │   │
│  │              │  │   Score Cards                         │   │
│  │ 🔄 Reset     │  │   Indicator Breakdown                 │   │
│  │              │  │   Comparison Table                    │   │
│  │              │  │   GPT Summary                         │   │
│  │              │  │                                       │   │
│  │              │  │  [ Ask about any stock...         → ] │   │
│  └──────────────┘  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### 1. Enter Your API Key

When you first open the app you will see a warning in the sidebar:

```
⚠️ Please enter your API key to continue.
```

1. Click the **password field** under "OpenAI API Key"
2. Paste your API key (starts with `sk-...`)
3. Press Enter
4. You will see **"API key set ✅"**

The chat input at the bottom will now be active.

---

### 2. Choose Your Model

Under "Model Selection" in the sidebar, choose your preferred model:

| Model | Best For | Speed |
|-------|---------|-------|
| GPT-4.1-mini | ✅ Default -- daily use | Fast |
| GPT-4o-mini | Heavy testing sessions | Fastest |
| GPT-4o | Best quality summaries | Slower |
| GPT-4.1 | Latest capabilities | Moderate |
| GPT-3.5-turbo | Basic use, lowest cost | Fastest |

> 💡 **Recommendation**: Start with **GPT-4.1-mini** for the best balance
> of quality and rate limits.

---

### 3. Type Your First Query

Click the chat input at the bottom of the screen and type:

```
Is Apple a good stock to buy?
```

Press **Enter** or click the **→** button.

The app will:
1. Show **"Analysis complete for AAPL. See results below."**
2. Display **4 score cards** with short, mid, long and overall scores
3. Show the **current price** with change indicator
4. Provide an **AI-generated summary**

---

## 💬 What You Can Ask

### Single Stock Queries

Ask about any publicly traded stock using either the company name or ticker symbol:

```
# Using company name
Is Apple a good stock to buy?
Run technical analysis on Tesla
Analyze Microsoft
Show me Goldman Sachs

# Using ticker symbol
analyze NVDA
show AAPL
is AMD worth buying?
what about TSLA right now?

# Requesting detail
Show me the full analysis for NVDA
Show short term analysis for Apple
Show mid term signals for Tesla
Show long term outlook for EOG
```

### Real-Time Price Data

```
Give me real time data for Apple
What is the current price of NVDA?
Show me Microsoft stock data
What is Tesla trading at?
```

### Multi Stock Comparison

Compare 2 or 3 stocks at once:

```
# Comparing 2 stocks
Compare Apple and Microsoft
Which is better -- AMD or Intel?
Apple vs Microsoft
NVDA vs AMD

# Comparing 3 stocks
Compare NVDA, AMD and Intel
Rank Apple, Microsoft and Google
EOG vs LULU vs TSLA
Which of these should I buy: AAPL, MSFT, GOOGL
```

> ⚠️ Maximum 3 stocks per comparison.
> The app will politely decline if you ask for more.

---

## 📊 Understanding the Results

### Score Cards

After every technical analysis you will see 4 colored score cards:

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Short term │ │  Mid term   │ │  Long term  │ │   Overall   │
│             │ │             │ │             │ │             │
│     88      │ │     65      │ │    100      │ │     84      │
│  out of 100 │ │  out of 100 │ │  out of 100 │ │  out of 100 │
│             │ │             │ │             │ │             │
│ 🟢 Strong   │ │ 🟩 Buy      │ │ 🟢 Strong   │ │ 🟢 Strong   │
│    Buy      │ │             │ │    Buy      │ │    Buy      │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

**Color coding:**

| Color | Score | Verdict |
|-------|-------|---------|
| 🟢 Dark green | 75 - 100 | Strong Buy |
| 🟩 Light green | 60 - 74 | Buy |
| ⬜ White/Gray | 40 - 59 | Neutral |
| 🟥 Orange/Red | 25 - 39 | Sell |
| 🔴 Deep red | 0 - 24 | Strong Sell |

---

### Price Line

Below the title you will see the current price:

```
Price: $180.25 ▼ 2.91 (1.59%)    ← red means falling
Price: $133.60 ▲ 0.56 (0.42%)    ← green means rising
```

---

### View Full Indicator Breakdown

Click **"📊 View Full Indicator Breakdown"** to expand the detailed signals:

```
Short term signals          Mid term signals        Long term signals
──────────────────          ────────────────        ─────────────────
• RSI (39.33)               • MACD (-0.31)          • MA200 ($177.37)
  mildly oversold ✅          bearish crossover ⚠️    price above ✅

• Stochastic (24.44)        • MA20 ($184.95)        • Golden Cross
  mildly oversold ✅          price below ⚠️           active ✅

• ROC (-1.22%)              • MA50 ($185.45)        • Volume (0.82x)
  mild negative ⚠️            price below ⚠️           falling ⚠️

• Bollinger (25.71%)        • ATR ($6.29 / 3.49%)
  mid band neutral ➡️         high volatility ⚠️

                            • Volume (0.82x avg)
                              falling ⚠️
```

**Signal icons:**
```
✅  Bullish signal -- positive for the stock
⚠️  Bearish signal -- negative for the stock
➡️  Neutral signal -- no strong directional bias
🔴  Structural downtrend detected
```

---

### AI Summary

Below the indicator breakdown you will see a blue summary box:

```
┌─────────────────────────────────────────────────────────────┐
│  NVIDIA shows a mixed technical picture. The long-term      │
│  structure remains bullish with an active golden cross      │
│  and price above MA200. However, the mid-term signals       │
│  are bearish with price below MA20 and MA50. The            │
│  short-term oversold conditions suggest a potential         │
│  bounce entry for long-term investors.                      │
│                                                             │
│  Disclaimer: Technical analysis is not financial advice.    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏆 Understanding Comparison Results

### Ranking Section

```
Ranking
────────────────────────────────────────────────
🥇  EOG    EOG Resources, Inc.      65/100 -- Buy 🟩
🥈  LULU   lululemon athletica inc.  9/100 -- Strong Sell 🔴
🥉  TSLA   Tesla, Inc.              4/100 -- Strong Sell 🔴
```

### Comparison Table

Scroll through the table to compare all indicators side by side:

```
Metric          │  EOG      │  LULU     │  TSLA
────────────────┼───────────┼───────────┼──────────
Price           │ $133.60   │ $157.78   │ $391.20
Change          │ +0.42%    │ -0.26%    │ -0.96%
Short term      │ 24/100    │ 30/100    │ 15/100
Mid term        │ 86/100    │ 0/100     │ 0/100
Long term       │ 78/100    │ 0/100     │ 0/100
Overall         │ 65/100    │ 9/100     │ 4/100
RSI             │ 72.01 ⚠️  │ 22.0 ✅   │ 45.44 ➡️
MACD            │ bullish ✅ │ bearish ⚠️│ bearish ⚠️
Golden Cross    │ active ✅  │ inactive ⚠️│ inactive ⚠️
...
```

### Best Picks Section

```
Best Picks
──────────────────────────────────────────────────────────
Best Overall    Best Short    Best Mid    Best Long    Lowest Risk
    EOG            LULU          EOG         EOG          EOG
```

> 💡 **Important**: "Best Short term" might show a Strong Sell stock
> like LULU. This means it has the best short term bounce potential
> among the compared stocks -- not that it is a good investment.

---

## 📈 How to Interpret Scores

### A Stock Can Score High Short Term But Be a Bad Investment

```
Example: LULU scores 30 short term, 0 mid term, 0 long term

Short term 30 means:
  RSI and Stochastic are heavily oversold
  Technical bounce is possible in coming days

Mid/Long 0 means:
  Structural collapse detected
  Death cross active
  Below all moving averages

Conclusion:
  Only suitable for very short term speculative traders
  Not suitable for investors
```

### A Stock Can Score Low Short Term But Be Strong Overall

```
Example: EOG scores 24 short term, 86 mid term, 78 long term

Short term 24 means:
  RSI and Stochastic are overbought
  Stock has run up fast recently
  Short term pullback is likely

Mid/Long high means:
  Strong bullish trend intact
  MACD bullish crossover
  Above all moving averages
  Golden cross active

Conclusion:
  Wait for short term pullback to enter
  Strong candidate for medium and long term holding
```

---

## ⌨️ Sidebar Commands

### Example Query Buttons

Click any button in the sidebar to automatically run that query:

```
Give me real time data for Apple     ← click to run
Is NVDA a good stock to buy?         ← click to run
Run technical analysis on Tesla      ← click to run
Show full analysis for AMD           ← click to run
Compare NVDA, AMD and Intel          ← click to run
Which of Apple or Microsoft is a better buy?  ← click to run
```

### Reset Button

Click **"🔄 Reset Conversation"** to:
- Clear all chat history
- Remove the last analysis panel
- Start a fresh conversation

> 💡 Use reset when switching between very different topics
> to avoid GPT getting confused by old context.

---

## ⚡ Tips for Best Results

### Be Specific With Your Questions

```
❌ Vague:    "tell me about apple"
✅ Better:   "run technical analysis on Apple"
✅ Better:   "is Apple a good buy right now?"
✅ Better:   "show me the full analysis for AAPL"
```

### Use Follow-up Questions

The chatbot remembers your conversation history:

```
You: analyze NVDA
Bot: [shows NVDA analysis]

You: what about AMD?
Bot: [shows AMD analysis -- understands context]

You: compare them
Bot: [compares NVDA and AMD -- remembers both]
```

### Ask for Specific Time Horizons

```
"Show me the short term signals for Tesla"
"What is the long term outlook for Microsoft?"
"Is Apple a good short term trade?"
"Which stock has the best long term score?"
```

### Ask for Explanation

```
"Why is NVDA scored neutral?"
"What does the MACD bearish crossover mean?"
"Explain the golden cross signal for EOG"
"Why is the short term score low for EOG?"
```

---

## ⚠️ Rate Limit Tips

If you see **"Too Many Requests. Rate limited."**:

```
1. Switch to GPT-4.1-mini in the model selector
   (highest rate limits)

2. Wait 60 seconds before trying again

3. Space out your queries
   -- wait 10-15 seconds between requests

4. Avoid running back-to-back comparisons
   -- each comparison = 3 separate analyses
```

---

## 🕐 Market Hours

The app uses real-time data from Yahoo Finance.

| Market | Hours (EST) | Days |
|--------|------------|------|
| US Stock Market | 9:30 AM -- 4:00 PM | Mon -- Fri |
| Pre-market | 4:00 AM -- 9:30 AM | Mon -- Fri |
| After-hours | 4:00 PM -- 8:00 PM | Mon -- Fri |

> 💡 Outside market hours the price shown is the last closing price.
> Technical indicators are always calculated from historical data
> and are available 24/7.

---

## ❓ Frequently Asked Questions

**Q: Can I analyze any stock in the world?**
```
A: The app supports any stock available on Yahoo Finance.
   This includes US stocks, ETFs, and many international stocks.
   Some smaller or newer stocks may not have enough data.
```

**Q: How current is the price data?**
```
A: Price data is fetched live from Yahoo Finance each time you ask.
   During market hours it reflects the latest trade price.
   Outside market hours it shows the last closing price.
```

**Q: Why does the same stock score differently each day?**
```
A: Technical indicators change daily as new price data comes in.
   A stock that was oversold yesterday may be neutral today.
   This is normal and expected behavior.
```

**Q: Why is a stock I know is bad scoring high short term?**
```
A: Heavily beaten-down stocks often show oversold RSI and
   Stochastic readings. The scoring system interprets this
   as a potential short term bounce opportunity.
   Always check the mid and long term scores for the full picture.
```

**Q: Can I compare more than 3 stocks?**
```
A: No. The maximum is 3 stocks per comparison.
   This keeps the analysis fast and the table readable.
   Run multiple comparisons if you need to screen more stocks.
```

**Q: Is this financial advice?**
```
A: No. This app is for educational purposes only.
   Technical analysis is one tool among many.
   Always do your own research before investing.
   Consider consulting a qualified financial advisor.
```

**Q: What does the structural downtrend penalty mean?**
```
A: When a stock is trading below its MA20, MA50 and MA200
   simultaneously, a penalty is applied to all time horizon scores.
   This reflects a confirmed structural breakdown in the stock
   beyond just temporary weakness.
```

**Q: Why does the chatbot sometimes call two tools?**
```
A: For simple price queries GPT calls fetch_price_data().
   For analysis queries GPT calls technical_analysis().
   Sometimes GPT calls both to give you a complete picture.
   This is normal behavior.
```

---

## 📌 Quick Reference

### Query Cheat Sheet

| What You Want | What to Type |
|---------------|-------------|
| Current price | "price of AAPL" |
| Quick analysis | "analyze NVDA" |
| Full breakdown | "show full analysis for TSLA" |
| Short term only | "short term analysis for AMD" |
| Long term only | "long term outlook for MSFT" |
| Compare stocks | "compare NVDA AMD Intel" |
| Best of group | "which of AAPL MSFT GOOGL is best" |
| Explain signal | "what does MACD bearish mean" |

### Score Reference

| Score | Verdict | Action |
|-------|---------|--------|
| 75-100 | Strong Buy 🟢 | Strong bullish signals across indicators |
| 60-74 | Buy 🟩 | More bullish than bearish |
| 40-59 | Neutral ⬜ | Mixed signals -- wait for clarity |
| 25-39 | Sell 🟥 | More bearish than bullish |
| 0-24 | Strong Sell 🔴 | Strong bearish signals -- avoid |

### Indicator Reference

| Indicator | Bullish Signal | Bearish Signal |
|-----------|---------------|----------------|
| RSI | Below 30 (oversold) | Above 70 (overbought) |
| Stochastic | Below 20 (oversold) | Above 80 (overbought) |
| ROC | Positive % | Negative % |
| MACD | Bullish crossover | Bearish crossover |
| MA20/50/200 | Price above | Price below |
| Golden Cross | MA50 above MA200 | MA50 below MA200 |
| Bollinger | Near lower band | Near upper band |
| ATR | Low (stable) | High (volatile) |
| Volume | Rising (confirms) | Falling (weak) |

---

## ⚠️ Disclaimer

This application is for **educational and informational purposes only**.

- Technical analysis is **not financial advice**
- Scores and verdicts are based on historical price patterns only
- Past performance does **not guarantee** future results
- Always conduct your own research before making investment decisions
- Never invest more than you can afford to lose
- Consider consulting a qualified financial advisor

---

*Real-Time Stock Analysis Chatbot -- User Guide*
