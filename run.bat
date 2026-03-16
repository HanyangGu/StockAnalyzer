@echo off
echo ================================================
echo   Stock Analysis Chatbot
echo ================================================

:: Try running with regular Python first
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo Python found -- installing requirements...
    pip install -r requirements.txt
    echo Starting app...
    streamlit run app.py
    pause
    exit
)

:: Try Anaconda in common locations
if exist "%USERPROFILE%\Anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\Anaconda3\Scripts\activate.bat"
    pip install -r requirements.txt
    streamlit run app.py
    pause
    exit
)

if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
    pip install -r requirements.txt
    streamlit run app.py
    pause
    exit
)

if exist "C:\Anaconda3\Scripts\activate.bat" (
    call "C:\Anaconda3\Scripts\activate.bat"
    pip install -r requirements.txt
    streamlit run app.py
    pause
    exit
)

:: Nothing found
echo ================================================
echo   ERROR: Python not found!
echo   Please install Python from:
echo   https://www.python.org/downloads/
echo   or Anaconda from:
echo   https://www.anaconda.com/download
echo ================================================
pause
```

---

### What this does
```
1. Checks if Python is installed normally
2. Checks common Anaconda locations
3. Checks Miniconda location
4. If nothing found -- shows clear error
          with download links