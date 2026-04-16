# ============================================================
# analyzers/sentiment/options.py -- Options Chain Data Fetcher
# ============================================================
# v0.6: reads from RawDataBundle instead of calling yfinance.
# Output contract unchanged — options_scorer.py unaffected.
# ============================================================

from datetime import datetime, timezone
import pandas as pd

MIN_DTE    = 20
MAX_DTE    = 90
MIN_VOLUME = 100


def fetch_options_data(ticker_symbol: str,
                        bundle: dict = None) -> dict:
    """
    Extracts options chain data from pre-fetched RawDataBundle.
    Falls back to direct yfinance if bundle not provided.
    """
    print(f"  Parsing options data for {ticker_symbol}...")

    import time, yfinance as yf

    if bundle is not None:
        info          = bundle.get("info", {})
        chain         = bundle.get("option_chain")
        selected      = bundle.get("selected_expiry")
        current_price = (
            info.get("currentPrice") or
            info.get("regularMarketPrice") or
            info.get("previousClose")
        )

        if chain is None or selected is None:
            # Bundle fetch failed for options — retry directly
            print(f"  Options not in bundle, retrying direct fetch for {ticker_symbol}...")
            try:
                time.sleep(0.5)
                stock    = yf.Ticker(ticker_symbol)
                expiries = stock.options
                if not expiries:
                    return {"data_quality": "failed"}
                now      = datetime.now(timezone.utc)
                selected = None
                dte_val  = None
                for exp in expiries:
                    exp_dt = pd.Timestamp(exp, tz="UTC")
                    dte    = (exp_dt - now).days
                    if MIN_DTE <= dte <= MAX_DTE:
                        selected = exp
                        dte_val  = dte
                        break
                if not selected:
                    selected = expiries[0]
                    dte_val  = max(1, (pd.Timestamp(selected, tz="UTC") - now).days)
                chain = stock.option_chain(selected)
                print(f"  Options retry succeeded: {selected}")
            except Exception as e:
                print(f"  Options retry failed: {e}")
                return {"data_quality": "failed"}
        else:
            now     = datetime.now(timezone.utc)
            dte_val = max(1, (pd.Timestamp(selected, tz="UTC") - now).days)
    else:
        try:
            time.sleep(1)
            stock    = yf.Ticker(ticker_symbol)
            expiries = stock.options
            if not expiries:
                return {"data_quality": "failed"}
            now      = datetime.now(timezone.utc)
            selected = None
            dte_val  = None
            for exp in expiries:
                exp_dt = pd.Timestamp(exp, tz="UTC")
                dte    = (exp_dt - now).days
                if MIN_DTE <= dte <= MAX_DTE:
                    selected = exp
                    dte_val  = dte
                    break
            if not selected:
                selected = expiries[0]
                dte_val  = max(1, (pd.Timestamp(selected, tz="UTC") - now).days)
            chain = stock.option_chain(selected)
            info  = stock.info
            current_price = (
                info.get("currentPrice") or
                info.get("regularMarketPrice") or
                info.get("previousClose")
            )
        except Exception as e:
            print(f"  Options fetch error: {e}")
            return {"data_quality": "failed"}

    try:
        calls_all = chain.calls.copy()
        puts_all  = chain.puts.copy()

        calls = calls_all[calls_all["volume"].fillna(0) > 0]
        puts  = puts_all[puts_all["volume"].fillna(0) > 0]

        avg_iv_calls = float(calls["impliedVolatility"].mean()) if not calls.empty else 0.0
        avg_iv_puts  = float(puts["impliedVolatility"].mean())  if not puts.empty else 0.0
        avg_iv       = round((avg_iv_calls + avg_iv_puts) / 2, 4)

        total_volume = (
            calls["volume"].fillna(0).sum() +
            puts["volume"].fillna(0).sum()
        )
        data_quality = "partial" if total_volume < MIN_VOLUME else "full"

        return {
            "calls":         calls,
            "puts":          puts,
            "calls_all":     calls_all,
            "puts_all":      puts_all,
            "expiry":        selected,
            "days_to_exp":   dte_val,
            "avg_iv":        avg_iv,
            "current_price": float(current_price) if current_price else None,
            "data_quality":  data_quality,
        }
    except Exception as e:
        print(f"  Options parse error: {e}")
        return {"data_quality": "failed"}
