# 📈 Real-Time Stock Analysis Chatbot

An AI-powered stock analysis web application that combines real-time market data from Yahoo Finance with technical analysis and GPT-powered natural language responses.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.43-red)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

### Single Stock Analysis
- Real-time price and market data from Yahoo Finance
- Technical analysis scored across **3 time horizons**
- **9 technical indicators** with individual signals
- Structural downtrend detection and penalty system
- AI-generated summary and insights
- Expandable full indicator breakdown

### Multi Stock Comparison
- Compare **2 to 3 stocks** side by side
- Horizontal comparison table with all 9 indicators
- Ranked by overall technical score 🥇🥈🥉
- Best pick identified per time horizon
- Lowest risk stock identified
- AI-generated comparison summary

### Smart UI
- Clean Streamlit web interface
- Colored score cards per time horizon
- Configurable AI model selector
- Secure API key input
- Example queries in sidebar
- One click reset

---

## 📊 Technical Indicators

| Category | Indicators |
|----------|-----------|
| Momentum | RSI (14), Stochastic Oscillator (14), Rate of Change (10) |
| Trend | MACD (12/26/9), MA20, MA50, MA200, Golden/Death Cross |
| Volatility | Bollinger Bands (20), ATR (14) |
| Confirmation | Volume Trend |

---

## 🏆 Scoring System

Each stock is scored across 3 independent time horizons:

| Horizon | Indicators Used | Weight |
|---------|----------------|--------|
| Short term | RSI + Stochastic + ROC + Bollinger Bands | 30% |
| Mid term | MACD + MA20 + MA50 + ATR + Volume | 35% |
| Long term | MA200 + Golden/Death Cross + Volume Trend | 35% |

| Score | Verdict |
|-------|---------|
| 75 - 100 | Strong Buy 🟢 |
| 60 - 74 | Buy 🟩 |
| 40 - 59 | Neutral ⬜ |
| 25 - 39 | Sell 🟥 |
| 0 - 24 | Strong Sell 🔴 |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| AI | OpenAI GPT (configurable) |
| Market Data | Yahoo Finance (yfinance) |
| Data Processing | Pandas, NumPy |
| Language | Python 3.8+ |

---

## 📋 Prerequisites

- Python 3.8 or higher
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- Internet connection for real-time market data

---

## 🚀 Installation

### Option 1 — Windows Quick Launch

```
1. Install Python from https://python.org/downloads
   ⚠️ IMPORTANT: Check "Add Python to PATH" during install

2. Download all project files into the same folder:
   app.py
   requirements.txt
   run.bat

3. Double click run.bat
   Dependencies install automatically and the app launches

4. Browser opens at http://localhost:8501
```

### Option 2 — Manual (All Platforms)

```bash
# Clone the repository
git clone https://github.com/yourusername/stock-analysis-chatbot
cd stock-analysis-chatbot

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

---

## ⚙️ Configuration

On first launch, enter your **OpenAI API key** in the sidebar.

### Model Selection

The sidebar includes a model selector to balance quality vs rate limits:

| Model | Best For | Rate Limits |
|-------|---------|-------------|
| GPT-4o | Production, best quality | Lower |
| GPT-4.1 | Latest model | Lower |
| GPT-4.1-mini | Recommended, balanced | Higher ✅ |
| GPT-4o-mini | Fast & cheap testing | Higher ✅ |
| GPT-3.5-turbo | Basic use | Highest ✅ |

> 💡 Use `gpt-4.1-mini` for testing to avoid rate limits. Switch to `gpt-4o` for production use.

---

## 💬 Example Queries

### Single Stock
```
Give me real time data for Apple
Is NVDA a good stock to buy right now?
Run technical analysis on Tesla
Show me the full analysis for AMD
Show short term analysis for Microsoft
```

### Multi Stock Comparison
```
Compare NVDA, AMD and Intel
Which of Apple or Microsoft is a better buy?
Rank EOG, LULU and TSLA by performance
```

---

## 📁 Project Structure

```
project/
  ├── app.py                          # Main Streamlit application
  ├── requirements.txt                # Python dependencies
  ├── run.bat                         # Windows one-click launcher
  ├── README.md                       # This file
  └── stock_analysis_backend.ipynb    # Development reference notebook
```

---

## 📦 Dependencies

```txt
yfinance==0.2.54
pandas==2.2.3
numpy==1.26.4
openai==1.65.4
streamlit==1.43.2
python-dateutil==2.9.0
pytz==2024.1
```

---

## 🔒 API Key Security

- Your API key is entered in the UI and **never stored on disk**
- The key is held in memory only for the duration of the session
- Never commit your API key to version control
- Add a `.env` file to `.gitignore` if storing keys locally

---

## 📈 How It Works

```
User types a query
        ↓
GPT decides which tool to call
        ↓
Yahoo Finance fetches real-time data
        ↓
9 technical indicators computed in Python
        ↓
Scored across 3 time horizons (0-100 each)
        ↓
Structural downtrend penalty applied if needed
        ↓
GPT generates natural language summary
        ↓
Streamlit renders structured UI with score cards
```

---

## ⚠️ Disclaimer

This application is for **educational and informational purposes only**.

- Technical analysis is **not financial advice**
- Past price patterns do **not guarantee** future performance
- Always conduct your own research before making investment decisions
- Never invest more than you can afford to lose
- Consult a qualified financial advisor for investment guidance

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

MIT License — free to use and modify for your own projects.

---

*Built with Python · Streamlit · OpenAI GPT · Yahoo Finance*
