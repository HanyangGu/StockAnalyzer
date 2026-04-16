# ============================================================
# data.py -- Data Fetching & Ticker Resolution
# ============================================================
# Handles all Yahoo Finance data retrieval including:
#   - Ticker resolution (name to symbol)
#   - Company validation
#   - Real-time price data
#   - Historical price data (backtest mode)
#   - Historical OHLCV data for indicators
# ============================================================

import time
from datetime import datetime

import pandas as pd
import yfinance as yf

from core.config import (
    DATA_PERIOD,
    DATA_INTERVAL,
    MIN_DATA_POINTS,
    MIN_STOCKS,
    MAX_STOCKS,
)


# ============================================================
# Ticker Resolution
# ============================================================

def resolve_ticker(company: str) -> str:
    """
    Resolves a company name or ticker symbol into a valid
    Yahoo Finance ticker symbol.

    Priority:
      1. Try input directly as a ticker (fastest path)
      2. Search Yahoo Finance by company name
      3. Fall back to cleaned input if both fail
    """
    candidate = company.upper().strip()

    # Step 1: Try as direct ticker
    try:
        info = yf.Ticker(candidate).info
        # Accept if any price field present, or if quoteType confirms it's a known security
        has_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("previousClose") or
            info.get("quoteType")
        )
        if has_price:
            return candidate
    except Exception:
        pass

    # Step 2: Search by company name
    try:
        results = yf.Search(company, max_results=5).quotes
        if results:
            for r in results:
                if r.get("quoteType") == "EQUITY":
                    return r["symbol"]
            return results[0]["symbol"]
    except Exception:
        pass

    # Step 3: Last resort fallback
    return candidate


def validate_companies(companies: list) -> dict:
    """
    Validates a list of companies for the comparison function.
    Enforces MIN_STOCKS and MAX_STOCKS limits.
    Removes duplicates while preserving order.
    """
    seen   = set()
    unique = []
    for c in companies:
        cleaned = c.strip().upper()
        if cleaned not in seen:
            seen.add(cleaned)
            unique.append(c.strip())

    if len(unique) < MIN_STOCKS:
        return {
            "valid": False,
            "error": f"Please provide at least {MIN_STOCKS} stocks to compare."
        }
    if len(unique) > MAX_STOCKS:
        return {
            "valid": False,
            "error": (
                f"Maximum {MAX_STOCKS} stocks can be compared at once. "
                f"You provided {len(unique)}. Please reduce your selection."
            )
        }

    return {"valid": True, "tickers": unique}


# ============================================================
# Real-Time Price Data
# ============================================================

def fetch_price_data(ticker_symbol: str) -> dict:
    """
    Fetches real-time price and market data for a single stock.
    Includes price, volume, market cap, and other key metrics.
    """
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_symbol)
        info  = stock.info

        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice")
        )
        if not current_price:
            return {
                "error": (
                    f"Could not retrieve price data for "
                    f"'{ticker_symbol}'. Market may be closed "
                    f"or ticker may be invalid."
                )
            }

        prev_close       = info.get("previousClose", 0) or 0
        price_change     = round(current_price - prev_close, 2)
        price_change_pct = round(
            (price_change / prev_close * 100)
            if prev_close else 0, 2
        )

        intraday = stock.history(period="1d", interval="1m")
        recent_closes = (
            intraday["Close"].tail(5).round(2).tolist()
            if not intraday.empty else []
        )

        return {
            "ticker":            ticker_symbol,
            "name":              info.get("longName", ticker_symbol),
            "exchange":          info.get("exchange"),
            "sector":            info.get("sector"),
            "industry":          info.get("industry"),
            "currency":          info.get("currency", "USD"),
            "current_price":     round(current_price, 2),
            "prev_close":        round(prev_close, 2),
            "price_change":      price_change,
            "price_change_pct":  price_change_pct,
            "open":              info.get("open"),
            "day_high":          info.get("dayHigh"),
            "day_low":           info.get("dayLow"),
            "recent_closes":     recent_closes,
            "volume":            info.get("volume"),
            "avg_volume":        info.get("averageVolume"),
            "market_cap":        info.get("marketCap"),
            "pe_ratio":          info.get("trailingPE"),
            "52w_high":          info.get("fiftyTwoWeekHigh"),
            "52w_low":           info.get("fiftyTwoWeekLow"),
            "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception as e:
        error_msg = str(e)
        if "too many requests" in error_msg.lower() or \
           "rate limit" in error_msg.lower():
            return {
                "error": (
                    "Yahoo Finance is temporarily rate limited. "
                    "Please wait 30 seconds and try again."
                )
            }
        return {"error": error_msg}


# ============================================================
# Historical Price Data (Backtest Mode)
# ============================================================

def fetch_price_data_historical(ticker_symbol: str,
                                 date: str) -> dict:
    """
    Fetches price data for a specific historical date.
    Used for backtesting -- returns price as of that date
    instead of current live price.
    """
    try:
        time.sleep(1)
        stock      = yf.Ticker(ticker_symbol)
        end_date   = pd.Timestamp(date)
        start_date = end_date - pd.DateOffset(days=5)

        df = stock.history(
            start    = start_date.strftime("%Y-%m-%d"),
            end      = (end_date + pd.DateOffset(days=1)
                       ).strftime("%Y-%m-%d"),
            interval = "1d"
        )

        if df.empty:
            return {
                "error": (
                    f"No price data found for "
                    f"{ticker_symbol} on {date}"
                )
            }

        # Get the closest trading day to selected date
        row              = df.iloc[-1]
        current_price    = round(float(row["Close"]), 2)
        prev_price       = round(float(df.iloc[-2]["Close"]), 2) \
                           if len(df) > 1 else current_price
        price_change     = round(current_price - prev_price, 2)
        price_change_pct = round(
            (price_change / prev_price * 100)
            if prev_price else 0, 2
        )

        info = stock.info

        return {
            "ticker":           ticker_symbol,
            "name":             info.get("longName", ticker_symbol),
            "exchange":         info.get("exchange"),
            "sector":           info.get("sector"),           # NOTE: current value, not historical
            "industry":         info.get("industry"),         # NOTE: current value, not historical
            "currency":         info.get("currency", "USD"),
            "current_price":    current_price,
            "prev_close":       prev_price,
            "price_change":     price_change,
            "price_change_pct": price_change_pct,
            "open":             round(float(row["Open"]), 2),
            "day_high":         round(float(row["High"]), 2),
            "day_low":          round(float(row["Low"]), 2),
            "recent_closes":    [],
            "volume":           int(row["Volume"]),
            "avg_volume":       None,   # not meaningful in backtest context
            "market_cap":       None,   # not meaningful in backtest context
            "pe_ratio":         None,   # not meaningful in backtest context
            "52w_high":         None,   # not meaningful in backtest context
            "52w_low":          None,   # not meaningful in backtest context
            "timestamp":        str(date),
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# Historical OHLCV Data (For Indicators)
# ============================================================

def fetch_historical_data(ticker_symbol: str,
                          end_date: str = None) -> dict:
    """
    Fetches 1 year of daily OHLCV historical data
    for technical indicator calculation.

    If end_date is provided, fetches data up to that date
    for backtesting purposes.

    Returns:
      {"success": True,  "df": DataFrame, "closes": Series}
      {"success": False, "error": "..."}
    """
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_symbol)

        if end_date:
            # Backtest mode -- fetch data up to selected date
            end   = pd.Timestamp(end_date)
            start = end - pd.DateOffset(years=1)
            df    = stock.history(
                start    = start.strftime("%Y-%m-%d"),
                end      = end.strftime("%Y-%m-%d"),
                interval = DATA_INTERVAL
            )
        else:
            # Normal mode -- fetch latest 1 year of data
            df = stock.history(
                period   = DATA_PERIOD,
                interval = DATA_INTERVAL
            )

        if df.empty:
            return {
                "success": False,
                "error":   f"No historical data found for {ticker_symbol}."
            }

        if len(df) < MIN_DATA_POINTS:
            return {
                "success": False,
                "error": (
                    f"Insufficient data for {ticker_symbol}. "
                    f"Need at least {MIN_DATA_POINTS} trading days."
                )
            }

        return {
            "success": True,
            "df":      df,
            "closes":  df["Close"],
            "days":    len(df),
        }

    except Exception as e:
        error_msg = str(e)
        if "too many requests" in error_msg.lower() or \
           "rate limit" in error_msg.lower():
            return {
                "success": False,
                "error": (
                    "Yahoo Finance is temporarily rate limited. "
                    "Please wait 30 seconds and try again."
                )
            }
        return {"success": False, "error": error_msg}


# ============================================================
# Raw Data Bundle (v0.6 — single-fetch architecture)
# ============================================================

def fetch_raw_bundle(ticker_symbol: str,
                     end_date: str = None) -> dict:
    """
    Fetches ALL data needed for a full analysis in one pass.

    Creates a single yf.Ticker object and calls every endpoint
    once. All analyzers then read from this bundle instead of
    making their own network requests.

    HTTP requests: ~8 total (down from 18-20 per analysis)
      1. ticker.info              (price + fundamentals + metadata)
      2. ticker.history 1y        (OHLCV for technical indicators)
      3. ticker.history 1d 1m     (intraday for price display, live only)
      4. ticker.upgrades_downgrades (analyst ratings history)
      5. ticker.recommendations_summary (analyst distribution)
      6. ticker.analyst_price_targets   (price targets)
      7. ticker.insider_transactions    (insider activity)
      8. ticker.options + option_chain  (one chain, counts as 2)
      9. ticker.news                    (news feed)
     10. ticker.calendar                (next earnings)
     11. ticker.earnings_dates          (historical earnings)
     Macro: 4 separate tickers (VIX/TNX/IRX/GSPC) — always separate

    Args:
        ticker_symbol : validated ticker (e.g. "NVDA")
        end_date      : backtest date string "YYYY-MM-DD" or None for live

    Returns:
        dict with keys:
          "info"                    : dict   (ticker.info)
          "history"                 : DataFrame (1y daily OHLCV)
          "intraday"                : DataFrame | None (1d 1m, live only)
          "upgrades_downgrades"     : DataFrame | None
          "recommendations_summary" : DataFrame | None
          "analyst_price_targets"   : dict | None
          "insider_transactions"    : DataFrame | None
          "options_expiries"        : tuple | None
          "option_chain"            : OptionChain | None
          "selected_expiry"         : str | None
          "news"                    : list
          "calendar"                : dict | DataFrame | None
          "earnings_dates"          : DataFrame | None
          "fetch_errors"            : dict   {field: error_msg}
          "data_quality"            : str    "full"|"partial"|"failed"
    """
    import pandas as pd

    print(f"  [Bundle] Fetching all data for {ticker_symbol} in one pass...")
    t_start = time.time()

    bundle       = {}
    fetch_errors = {}

    # ── Single Ticker object ───────────────────────────────────
    try:
        stock = yf.Ticker(ticker_symbol)
    except Exception as e:
        return {
            "info": {}, "history": None, "intraday": None,
            "upgrades_downgrades": None, "recommendations_summary": None,
            "analyst_price_targets": None, "insider_transactions": None,
            "options_expiries": None, "option_chain": None,
            "selected_expiry": None, "news": [], "calendar": None,
            "earnings_dates": None, "fetch_errors": {"ticker": str(e)},
            "data_quality": "failed",
        }

    # ── 1. info (price + fundamentals + metadata) ─────────────
    try:
        bundle["info"] = stock.info or {}
    except Exception as e:
        bundle["info"] = {}
        fetch_errors["info"] = str(e)

    # ── 2. OHLCV history ──────────────────────────────────────
    # Fallback strategy: try period= first, then explicit date range.
    # yfinance occasionally returns empty DataFrame for period= on some tickers.
    try:
        if end_date:
            end   = pd.Timestamp(end_date)
            start = end - pd.DateOffset(years=1)
            hist  = stock.history(
                start    = start.strftime("%Y-%m-%d"),
                end      = end.strftime("%Y-%m-%d"),
                interval = DATA_INTERVAL,
            )
        else:
            hist = stock.history(
                period   = DATA_PERIOD,
                interval = DATA_INTERVAL,
            )
            # Fallback: if period= returns empty, try explicit date range
            if hist.empty:
                import datetime
                end_dt   = datetime.date.today()
                start_dt = end_dt - datetime.timedelta(days=365)
                hist = stock.history(
                    start    = start_dt.strftime("%Y-%m-%d"),
                    end      = end_dt.strftime("%Y-%m-%d"),
                    interval = DATA_INTERVAL,
                )
                if not hist.empty:
                    print(f"  [Bundle] history fallback to explicit date range succeeded")

        if hist.empty:
            bundle["history"] = None
            fetch_errors["history"] = "Empty DataFrame returned"
        else:
            bundle["history"] = hist
    except Exception as e:
        bundle["history"] = None
        fetch_errors["history"] = str(e)

    # ── 3. Intraday (live only, for recent_closes display) ────
    bundle["intraday"] = None
    if not end_date:
        try:
            bundle["intraday"] = stock.history(period="1d", interval="1m")
        except Exception as e:
            fetch_errors["intraday"] = str(e)

    # ── 4. Analyst ratings history ────────────────────────────
    try:
        raw = getattr(stock, "upgrades_downgrades", None)
        if raw is None or (hasattr(raw, "empty") and raw.empty):
            raw = getattr(stock, "recommendations", None)
        bundle["upgrades_downgrades"] = raw
    except Exception as e:
        bundle["upgrades_downgrades"] = None
        fetch_errors["upgrades_downgrades"] = str(e)

    # ── 5. Analyst summary (distribution counts) ─────────────
    try:
        bundle["recommendations_summary"] = stock.recommendations_summary
    except Exception as e:
        bundle["recommendations_summary"] = None
        fetch_errors["recommendations_summary"] = str(e)

    # ── 6. Analyst price targets ──────────────────────────────
    try:
        raw = stock.analyst_price_targets
        if raw is not None and hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        bundle["analyst_price_targets"] = raw
    except Exception as e:
        bundle["analyst_price_targets"] = None
        fetch_errors["analyst_price_targets"] = str(e)

    # ── 7. Insider transactions ───────────────────────────────
    try:
        bundle["insider_transactions"] = stock.insider_transactions
    except Exception as e:
        bundle["insider_transactions"] = None
        fetch_errors["insider_transactions"] = str(e)

    # ── 8. Options chain ──────────────────────────────────────
    bundle["options_expiries"] = None
    bundle["option_chain"]     = None
    bundle["selected_expiry"]  = None
    try:
        expiries = stock.options
        bundle["options_expiries"] = expiries

        if expiries:
            from datetime import timezone
            now      = datetime.now(timezone.utc)
            selected = None
            for exp in expiries:
                exp_dt = pd.Timestamp(exp, tz="UTC")
                dte    = (exp_dt - now).days
                if 20 <= dte <= 90:
                    selected = exp
                    break
            if not selected:
                selected = expiries[0]

            bundle["selected_expiry"] = selected
            bundle["option_chain"]    = stock.option_chain(selected)
    except Exception as e:
        fetch_errors["options"] = str(e)

    # ── 9. News feed ──────────────────────────────────────────
    try:
        bundle["news"] = stock.news or []
    except Exception as e:
        bundle["news"] = []
        fetch_errors["news"] = str(e)

    # ── 10. Earnings calendar ─────────────────────────────────
    try:
        bundle["calendar"] = stock.calendar
    except Exception as e:
        bundle["calendar"] = None
        fetch_errors["calendar"] = str(e)

    # ── 11. Historical earnings dates ─────────────────────────
    try:
        bundle["earnings_dates"] = stock.earnings_dates
    except Exception as e:
        bundle["earnings_dates"] = None
        fetch_errors["earnings_dates"] = str(e)

    # ── Data quality assessment ───────────────────────────────
    critical_ok = (
        bundle["info"] and
        bundle["history"] is not None and
        not bundle["history"].empty
    )
    if not critical_ok:
        data_quality = "failed"
    elif fetch_errors:
        data_quality = "partial"
    else:
        data_quality = "full"

    bundle["fetch_errors"] = fetch_errors
    bundle["data_quality"] = data_quality

    elapsed = round(time.time() - t_start, 1)
    print(f"  [Bundle] Done in {elapsed}s | quality={data_quality} | errors={list(fetch_errors.keys()) or 'none'}")

    return bundle
