# ============================================================
# analyzers/event_driven.py -- Event-Driven Data Fetcher
# ============================================================
# v0.6: reads from RawDataBundle instead of calling yfinance.
# Output contract unchanged — event_scorer.py unaffected.
# ============================================================

from datetime import datetime, timezone
import pandas as pd


def _to_str_date(val) -> str | None:
    if val is None:
        return None
    try:
        return pd.Timestamp(val).strftime("%Y-%m-%d")
    except Exception:
        return None


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (f != f) else f
    except Exception:
        return None


def _days_from_today(date_str: str) -> int:
    try:
        ts  = pd.Timestamp(date_str)
        ts  = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        now = datetime.now(timezone.utc)
        return int((ts.to_pydatetime() - now).days)
    except Exception:
        return 9999


def _parse_next_earnings(cal) -> dict | None:
    """Parse calendar data from bundle."""
    if cal is None:
        return None
    if hasattr(cal, "empty") and cal.empty:
        return None
    try:
        earnings_date = eps_low = eps_high = None
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            eps_low       = cal.get("EPS Estimate Low")  or cal.get("Earnings Low")
            eps_high      = cal.get("EPS Estimate High") or cal.get("Earnings High")
        elif hasattr(cal, "columns"):
            try:
                cal_dict = {col: (cal[col].iloc[0] if not cal[col].empty else None) for col in cal.columns}
                earnings_date = cal_dict.get("Earnings Date")
                eps_low       = cal_dict.get("EPS Estimate Low")  or cal_dict.get("Earnings Low")
                eps_high      = cal_dict.get("EPS Estimate High") or cal_dict.get("Earnings High")
            except Exception:
                pass
        elif hasattr(cal, "to_dict"):
            d             = cal.to_dict()
            earnings_date = d.get("Earnings Date") or d.get("Value", {}).get("Earnings Date")
            eps_low       = d.get("EPS Estimate Low")  or d.get("Value", {}).get("Earnings Low")
            eps_high      = d.get("EPS Estimate High") or d.get("Value", {}).get("Earnings High")

        if isinstance(earnings_date, (list, tuple)):
            earnings_date = earnings_date[0] if len(earnings_date) > 0 else None
        if earnings_date is None:
            return None
        date_str = _to_str_date(earnings_date)
        if not date_str:
            return None
        return {
            "date":              date_str,
            "days_until":        int(_days_from_today(date_str)),
            "estimate_eps_low":  _to_float(eps_low),
            "estimate_eps_high": _to_float(eps_high),
        }
    except Exception as e:
        print(f"  Next earnings parse error: {e}")
        return None


def _parse_last_earnings(dates_df) -> dict | None:
    """Parse earnings_dates DataFrame from bundle."""
    if dates_df is None or (hasattr(dates_df, "empty") and dates_df.empty):
        return None
    try:
        now = datetime.now(timezone.utc)
        try:
            if dates_df.index.tz is not None:
                cutoff = pd.Timestamp(now).tz_convert(dates_df.index.tz)
            else:
                cutoff = pd.Timestamp(now).tz_localize(None)
            past = dates_df[dates_df.index < cutoff]
        except Exception:
            past = dates_df
        if past.empty:
            return None
        row      = past.iloc[0]
        date_str = _to_str_date(row.name)
        if not date_str:
            return None
        days_ago     = abs(_days_from_today(date_str))
        actual_col   = next((c for c in ["Reported EPS", "EPS Actual", "actual"]   if c in past.columns), None)
        estimate_col = next((c for c in ["EPS Estimate", "estimate"]                if c in past.columns), None)
        actual_eps   = _to_float(row[actual_col])   if actual_col   else None
        estimate_eps = _to_float(row[estimate_col]) if estimate_col else None
        surprise_pct = None
        if actual_eps is not None and estimate_eps is not None and estimate_eps != 0:
            surprise_pct = round((actual_eps - estimate_eps) / abs(estimate_eps) * 100, 2)
        return {
            "date":         date_str,
            "days_ago":     int(days_ago),
            "actual_eps":   actual_eps,
            "estimate_eps": estimate_eps,
            "surprise_pct": surprise_pct,
        }
    except Exception as e:
        print(f"  Last earnings parse error: {e}")
        return None


def fetch_event_data(ticker_symbol: str,
                     bundle: dict = None) -> dict:
    """
    Extracts event data from pre-fetched RawDataBundle.
    Falls back to direct yfinance if bundle not provided.
    """
    print(f"  Parsing event data for {ticker_symbol}...")

    if bundle is not None:
        next_earnings = _parse_next_earnings(bundle.get("calendar"))
        last_earnings = _parse_last_earnings(bundle.get("earnings_dates"))
    else:
        import time, yfinance as yf
        try:
            time.sleep(0.5)
            cal           = yf.Ticker(ticker_symbol).calendar
            next_earnings = _parse_next_earnings(cal)
        except Exception as e:
            print(f"  Next earnings fetch error: {e}")
            next_earnings = None
        try:
            time.sleep(0.5)
            dates         = yf.Ticker(ticker_symbol).earnings_dates
            last_earnings = _parse_last_earnings(dates)
        except Exception as e:
            print(f"  Last earnings fetch error: {e}")
            last_earnings = None

    if next_earnings is None and last_earnings is None:
        data_quality = "failed"
    elif next_earnings is None or last_earnings is None:
        data_quality = "partial"
    else:
        data_quality = "full"

    return {
        "next_earnings": next_earnings,
        "last_earnings": last_earnings,
        "data_quality":  data_quality,
    }
