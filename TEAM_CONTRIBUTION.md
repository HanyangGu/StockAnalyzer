# 👥 Team Contributions

This document outlines the general contributions of each team member to the Real-Time Stock Analysis Chatbot project.

---

## 👨‍💻 Team Members & Roles

| Member | Role |
|--------|------|
| A | Project Lead & AI Integration |
| B | Data Engineering |
| C | Technical Analysis & Scoring |
| D | Frontend & User Interface |
| E | Testing & Documentation |

---

## 👤 Member A — Project Lead & AI Integration

- Led overall project architecture and design decisions
- Integrated OpenAI GPT API with tool calling system
- Engineered the system prompt and AI behavior rules
- Built the chatbot conversation management and history system
- Implemented the tool routing logic between GPT and Python functions
- Managed project timeline and team coordination

---

## 👤 Member B — Data Engineering

- Integrated Yahoo Finance API for real-time market data
- Built the ticker resolution system to convert company names to ticker symbols
- Implemented real-time price data fetching and historical OHLCV data pipeline
- Handled data validation, cleaning, and serialization
- Enforced stock comparison limits and duplicate removal

---

## 👤 Member C — Technical Analysis & Scoring

- Implemented all 9 technical indicators across 3 categories:
  - Momentum: RSI, Stochastic Oscillator, Rate of Change
  - Trend: MACD, Moving Averages (MA20/50/200), Golden/Death Cross
  - Volatility & Volume: Bollinger Bands, ATR, Volume Trend
- Designed the 3-horizon scoring system (short, mid, long term)
- Built the structural downtrend detection and penalty system
- Calibrated all scoring weights and verdict thresholds
- Implemented the stock comparison and ranking logic

---

## 👤 Member D — Frontend & User Interface

- Built the Streamlit web application layout and design
- Created the colored score card components
- Implemented the expandable indicator breakdown panel
- Built the horizontal multi-stock comparison table
- Designed the sidebar with API key input, model selector, and example queries
- Handled chat message rendering and session state management

---

## 👤 Member E — Testing & Documentation

- Conducted end-to-end testing and identified bugs across all components
- Validated scoring accuracy across multiple stock types
- Managed all project configuration and environment setup
- Created the Windows launcher (run.bat) and dependency file (requirements.txt)
- Wrote all project documentation:
  - README.md -- Project overview
  - ARCHITECTURE.md -- Technical design
  - SETUP.md -- Installation guide
  - USER_GUIDE.md -- Usage guide
  - TEAM_CONTRIBUTION.md -- This document

---

## 📊 Contribution Summary

```
Member A  --  AI & GPT Integration
Member B  --  Data & Market Feeds
Member C  --  Technical Analysis Engine
Member D  --  Streamlit Frontend
Member E  --  Testing & Documentation
```

---

*Real-Time Stock Analysis Chatbot -- Team Contribution Document*
