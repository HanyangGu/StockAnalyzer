# ============================================================
# fundamental.py -- Fundamental Data Fetcher
# ============================================================
# v0.6: accepts RawDataBundle instead of calling yfinance.
# Scoring logic lives in scoring/fundamental_scorer.py
# ============================================================

from core.utils import safe_get


def fetch_fundamental_data(ticker_symbol: str,
                            bundle: dict = None) -> dict:
    """
    Extracts fundamental data from the pre-fetched RawDataBundle.
    Falls back to direct yfinance fetch if bundle not provided.
    """
    # ── Bundle path (preferred) ───────────────────────────────
    if bundle is not None:
        info = bundle.get("info", {})
    else:
        # Legacy fallback (kept for compatibility / testing)
        import time, yfinance as yf
        time.sleep(1)
        info = yf.Ticker(ticker_symbol).info

    if not info:
        return {"error": "No fundamental data available"}

    current_price = (
        safe_get(info, "currentPrice") or
        safe_get(info, "regularMarketPrice")
    )

    target_price = safe_get(info, "targetMeanPrice")
    upside_pct   = None
    if target_price and current_price:
        upside_pct = round(
            ((target_price - current_price) / current_price) * 100, 2
        )

    def pct(key):
        v = safe_get(info, key)
        return round(v * 100, 2) if v is not None else None

    return {
        "ticker":   ticker_symbol,
        "name":     safe_get(info, "longName",  default=ticker_symbol, cast=str),
        "sector":   safe_get(info, "sector",    default=None,           cast=str),
        "industry": safe_get(info, "industry",  default=None,           cast=str),

        "pe_ratio":        safe_get(info, "trailingPE",                   default=None, cast=lambda v: round(float(v), 2)),
        "forward_pe":      safe_get(info, "forwardPE",                    default=None, cast=lambda v: round(float(v), 2)),
        "price_to_book":   safe_get(info, "priceToBook",                  default=None, cast=lambda v: round(float(v), 2)),
        "price_to_sales":  safe_get(info, "priceToSalesTrailing12Months", default=None, cast=lambda v: round(float(v), 2)),

        "gross_margin":    pct("grossMargins"),
        "net_margin":      pct("profitMargins"),
        "roe":             pct("returnOnEquity"),
        "roa":             pct("returnOnAssets"),

        "revenue_growth":  pct("revenueGrowth"),
        "earnings_growth": pct("earningsGrowth"),
        "eps":             safe_get(info, "trailingEps", default=None, cast=lambda v: round(float(v), 2)),
        "forward_eps":     safe_get(info, "forwardEps",  default=None, cast=lambda v: round(float(v), 2)),

        "debt_to_equity":  safe_get(info, "debtToEquity",  default=None, cast=lambda v: round(float(v), 2)),
        "current_ratio":   safe_get(info, "currentRatio",  default=None, cast=lambda v: round(float(v), 2)),
        "free_cash_flow":  safe_get(info, "freeCashflow",  default=None, cast=lambda v: int(float(v))),
        "total_revenue":   safe_get(info, "totalRevenue",  default=None, cast=lambda v: int(float(v))),

        "target_price":    safe_get(info, "targetMeanPrice", default=None, cast=lambda v: round(float(v), 2)),
        "target_high":     safe_get(info, "targetHighPrice", default=None, cast=lambda v: round(float(v), 2)),
        "target_low":      safe_get(info, "targetLowPrice",  default=None, cast=lambda v: round(float(v), 2)),
        "recommendation":  safe_get(info, "recommendationKey", default=None, cast=str),
        "analyst_count":   safe_get(info, "numberOfAnalystOpinions", default=None, cast=int),
        "current_price":   round(current_price, 2) if current_price else None,
        "upside_pct":      upside_pct,

        "business_summary":   safe_get(info, "longBusinessSummary", default=None, cast=str),
        "employee_count":     safe_get(info, "fullTimeEmployees",    default=None, cast=int),
        "shares_outstanding": safe_get(info, "sharesOutstanding",    default=None, cast=lambda v: int(float(v))),
        "beta":               safe_get(info, "beta",                 default=None, cast=lambda v: round(float(v), 2)),
        "52w_high":           safe_get(info, "fiftyTwoWeekHigh",     default=None, cast=lambda v: round(float(v), 2)),
        "52w_low":            safe_get(info, "fiftyTwoWeekLow",      default=None, cast=lambda v: round(float(v), 2)),
    }
