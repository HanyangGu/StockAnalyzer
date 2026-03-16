# 🔧 Setup Guide

Complete step-by-step setup instructions for the Real-Time Stock Analysis Chatbot on Windows, Mac, and Linux.

---

## 📋 Prerequisites

Before you begin, make sure you have:

- [ ] A computer running Windows, Mac, or Linux
- [ ] An internet connection
- [ ] An OpenAI account with API access
- [ ] Basic familiarity with running terminal commands

---

## 🔑 Step 1 — Get Your OpenAI API Key

1. Go to [https://platform.openai.com](https://platform.openai.com)
2. Sign in or create a free account
3. Click **API Keys** in the left sidebar
4. Click **Create new secret key**
5. Copy and save the key somewhere safe

> ⚠️ You will only see the key once. Store it securely.
> Never share your API key or commit it to version control.

### Add Credits to Your Account
1. Go to [https://platform.openai.com/account/billing](https://platform.openai.com/account/billing)
2. Click **Add payment method**
3. Add at least **$5** in credits to get started
4. Set a spending limit to avoid unexpected charges

---

## 💻 Step 2 — Install Python

### Windows

1. Go to [https://python.org/downloads](https://python.org/downloads)
2. Click **Download Python 3.x.x** (latest version)
3. Run the installer
4. ⚠️ **CRITICAL**: Check the box **"Add Python to PATH"** before clicking Install

   ```
   ┌─────────────────────────────────────┐
   │  Install Python 3.x.x               │
   │                                     │
   │  [x] Add Python to PATH  ← CHECK   │
   │                                     │
   │  [ Install Now ]                    │
   └─────────────────────────────────────┘
   ```

5. Click **Install Now**
6. Wait for installation to complete
7. Click **Close**

**Verify installation:**
```bash
# Open Command Prompt and run:
python --version
# Should show: Python 3.x.x

pip --version
# Should show: pip xx.x.x
```

### Mac

```bash
# Install Homebrew first (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python

# Verify
python3 --version
pip3 --version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip -y

# Verify
python3 --version
pip3 --version
```

---

## 📁 Step 3 — Download the Project Files

Download these files and place them all in the **same folder**:

```
my-stock-chatbot/          ← create this folder
  ├── app.py
  ├── requirements.txt
  ├── run.bat              (Windows only)
  ├── README.md
  ├── ARCHITECTURE.md
  └── SETUP.md
```

> 💡 Tip: Create a dedicated folder like `C:\Projects\stock-chatbot\` on Windows
> or `~/Projects/stock-chatbot/` on Mac/Linux

---

## 📦 Step 4 — Install Dependencies

### Windows — Automatic (Recommended)

Simply **double click `run.bat`**

It will automatically:
1. Detect Python installation
2. Install all required packages
3. Launch the app in your browser

### Windows — Manual

```bash
# Open Command Prompt
# Navigate to your project folder
cd C:\Projects\stock-chatbot

# Install all dependencies
pip install -r requirements.txt
```

### Mac / Linux

```bash
# Open Terminal
# Navigate to your project folder
cd ~/Projects/stock-chatbot

# Install all dependencies
pip3 install -r requirements.txt
```

**Expected output:**
```
Successfully installed yfinance-0.2.54 pandas-2.2.3
numpy-1.26.4 openai-1.65.4 streamlit-1.43.2 ...
```

---

## 🚀 Step 5 — Run the Application

### Windows — Double Click
```
Double click run.bat
Browser opens automatically at http://localhost:8501
```

### Windows — Command Prompt
```bash
cd C:\Projects\stock-chatbot
streamlit run app.py
```

### Mac / Linux — Terminal
```bash
cd ~/Projects/stock-chatbot
streamlit run app.py
```

**Expected terminal output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

---

## ⚙️ Step 6 — Configure the App

Once the browser opens at `http://localhost:8501`:

### Enter Your API Key
1. Look at the **left sidebar**
2. Find **"OpenAI API Key"** input
3. Paste your API key (starts with `sk-...`)
4. You should see **"API key set ✅"**

### Choose Your Model
1. Find **"Model Selection"** dropdown in the sidebar
2. Select your preferred model:

   | Model | Recommended For |
   |-------|----------------|
   | GPT-4.1-mini | ✅ Default -- balanced quality and rate limits |
   | GPT-4o-mini | Testing -- highest rate limits |
   | GPT-4o | Production -- best quality |

> 💡 Start with **GPT-4.1-mini** to avoid rate limits while testing

---

## ✅ Step 7 — Test the App

Try these example queries to confirm everything is working:

```
1. Give me real time data for Apple
   → Should show price data and market metrics

2. Run technical analysis on NVDA
   → Should show 4 score cards + indicator breakdown

3. Compare EOG, LULU and TSLA
   → Should show ranking table + comparison + best picks
```

---

## 🛑 How to Stop the App

In the terminal where you ran the app:
```
Press Ctrl + C
```

The browser tab can be closed normally.

---

## 🔄 How to Restart the App

```bash
# Windows
Double click run.bat

# Mac / Linux
streamlit run app.py
```

> 💡 After saving changes to `app.py`, Streamlit shows a
> **"Source file changed"** button in the browser.
> Click **"Rerun"** to apply changes without restarting.

---

## ❗ Troubleshooting

### "Python is not recognized"
```
Problem : Python not found in PATH
Solution:
  1. Reinstall Python from python.org
  2. During install CHECK "Add Python to PATH"
  3. Restart Command Prompt after install
```

### "No module named 'streamlit'"
```
Problem : Dependencies not installed
Solution:
  pip install -r requirements.txt
```

### "No module named 'yfinance'"
```
Problem : yfinance not installed or wrong Python
Solution:
  pip install yfinance
  or
  pip install -r requirements.txt
```

### "ModuleNotFoundError: No module named 'numpy.rec'"
```
Problem : NumPy version conflict
Solution:
  pip uninstall numpy -y
  pip install "numpy==1.26.4"
  Restart the app
```

### "Too Many Requests. Rate limited."
```
Problem : OpenAI API rate limit hit
Solution:
  1. Wait 60 seconds
  2. Switch to GPT-4.1-mini in the model selector
  3. Space out queries by 10-15 seconds
```

### "OpenAIError: The api_key client option must be set"
```
Problem : API key not entered or invalid
Solution:
  1. Check your API key is entered in the sidebar
  2. Make sure it starts with "sk-"
  3. Check platform.openai.com for valid keys
```

### "Could not retrieve data for ticker"
```
Problem : Invalid ticker or market closed
Solution:
  1. Check the ticker symbol is correct
  2. Try the full company name instead
  3. Some stocks may not be available on Yahoo Finance
```

### Browser doesn't open automatically
```
Problem : Auto-launch failed
Solution:
  Manually open your browser and go to:
  http://localhost:8501
```

### Port 8501 already in use
```
Problem : Another Streamlit app is running
Solution:
  streamlit run app.py --server.port 8502
  Then open http://localhost:8502
```

---

## 🔒 Security Best Practices

```
✅ Never hardcode your API key in app.py
✅ Never commit your API key to Git
✅ Add .env to .gitignore
✅ Set a monthly spending limit on OpenAI
✅ Use environment variables for production
✅ Rotate your API key if exposed
```

### Optional: Use a .env file
```bash
# Create .env file in project folder
OPENAI_API_KEY=sk-your-key-here
```

```python
# Add to top of app.py
from dotenv import load_dotenv
load_dotenv()
```

```bash
# Install dotenv
pip install python-dotenv
```

---

## 📊 Verifying Your Setup

Run this quick check in Python to verify all packages:

```python
# Save as check.py and run: python check.py
import sys

packages = [
    "streamlit",
    "yfinance",
    "pandas",
    "numpy",
    "openai",
]

print(f"Python version: {sys.version}")
print()

for pkg in packages:
    try:
        mod = __import__(pkg)
        print(f"✅ {pkg} -- {mod.__version__}")
    except ImportError:
        print(f"❌ {pkg} -- NOT INSTALLED")
    except AttributeError:
        print(f"✅ {pkg} -- installed")
```

**Expected output:**
```
Python version: 3.x.x

✅ streamlit  -- 1.43.2
✅ yfinance   -- 0.2.54
✅ pandas     -- 2.2.3
✅ numpy      -- 1.26.4
✅ openai     -- 1.65.4
```

---

## 📬 Getting Help

If you encounter issues not covered here:

1. Check the **troubleshooting section** above
2. Review the **ARCHITECTURE.md** for technical details
3. Check OpenAI status at [https://status.openai.com](https://status.openai.com)
4. Check Yahoo Finance availability at [https://finance.yahoo.com](https://finance.yahoo.com)

---

## 📄 Related Documents

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Project overview and features |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture and design |
| [SETUP.md](SETUP.md) | This document |

---

*Real-Time Stock Analysis Chatbot -- Setup Guide*
