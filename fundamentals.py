# ============================================================
# fundamentals.py -- Fundamental Analysis
# ============================================================
# Fetches and scores fundamental data from Yahoo Finance:
#   Valuation    : P/E, Forward P/E, P/B, P/S
#   Profitability: Gross Margin, Net Margin, ROE
#   Growth       : Revenue Growth, Earnings Growth, EPS
#   Health       : Debt/Equity, Current Ratio, Free Cash Flow
#   Analyst      : Target Price, Recommendation
# ============================================================

import time
import yfinance as yf

from data import resolve_ticker


# ============================================================
# Data Fetcher
# ============================================================

def fetch_fundamental_data(ticker_symbol: str) -> dict:
    """
    Fetches fundamental data for a single stock from Yahoo Finance.
    All data points are already available in yf.Ticker().info
    so no additional API is needed.
    """
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_symbol)
        info  = stock.info

        # -- Valuation ----------------------------------------
        pe_ratio       = info.get("trailingPE")
        forward_pe     = info.get("forwardPE")
        price_to_book  = info.get("priceToBook")
        price_to_sales = info.get("priceToSalesTrailing12Months")

        # -- Profitability ------------------------------------
        gross_margin   = info.get("grossMargins")
        net_margin     = info.get("profitMargins")
        roe            = info.get("returnOnEquity")
        roa            = info.get("returnOnAssets")

        # -- Growth -------------------------------------------
        revenue_growth  = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")
        eps             = info.get("trailingEps")
        forward_eps     = info.get("forwardEps")

        # -- Financial Health ---------------------------------
        debt_to_equity  = info.get("debtToEquity")
        current_ratio   = info.get("currentRatio")
        free_cash_flow  = info.get("freeCashflow")
        total_revenue   = info.get("totalRevenue")

        # -- Analyst Targets ----------------------------------
        target_price    = info.get("targetMeanPrice")
        target_high     = info.get("targetHighPrice")
        target_low      = info.get("targetLowPrice")
        recommendation  = info.get("recommendationKey")
        analyst_count   = info.get("numberOfAnalystOpinions")
        current_price   = (
            info.get("currentPrice") or
            info.get("regularMarketPrice")
        )

        # Calculate upside potential
        upside_pct = None
        if target_price and current_price:
            upside_pct = round(
                ((target_price - current_price) / current_price) * 100, 2
            )

        return {
            "ticker":          ticker_symbol,
            "name":            info.get("longName", ticker_symbol),
            "sector":          info.get("sector"),
            "industry":        info.get("industry"),

            # Valuation
            "pe_ratio":        round(pe_ratio, 2)      if pe_ratio      else None,
            "forward_pe":      round(forward_pe, 2)    if forward_pe    else None,
            "price_to_book":   round(price_to_book, 2) if price_to_book else None,
            "price_to_sales":  round(price_to_sales, 2) if price_to_sales else None,

            # Profitability
            "gross_margin":    round(gross_margin * 100, 2)  if gross_margin  else None,
            "net_margin":      round(net_margin * 100, 2)    if net_margin    else None,
            "roe":             round(roe * 100, 2)           if roe           else None,
            "roa":             round(roa * 100, 2)           if roa           else None,

            # Growth
            "revenue_growth":  round(revenue_growth * 100, 2)  if revenue_growth  else None,
            "earnings_growth": round(earnings_growth * 100, 2) if earnings_growth else None,
            "eps":             round(eps, 2)         if eps         else None,
            "forward_eps":     round(forward_eps, 2) if forward_eps else None,

            # Financial Health
            "debt_to_equity":  round(debt_to_equity, 2)  if debt_to_equity  else None,
            "current_ratio":   round(current_ratio, 2)   if current_ratio   else None,
            "free_cash_flow":  free_cash_flow,
            "total_revenue":   total_revenue,

            # Analyst Targets
            "target_price":    round(target_price, 2) if target_price else None,
            "target_high":     round(target_high, 2)  if target_high  else None,
            "target_low":      round(target_low, 2)   if target_low   else None,
            "recommendation":  recommendation,
            "analyst_count":   analyst_count,
            "current_price":   round(current_price, 2) if current_price else None,
            "upside_pct":      upside_pct,
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# Fundamental Scorer
# ============================================================

def score_fundamentals(data: dict) -> dict:
    """
    Scores fundamental data on a 0-100 scale.

    Scoring breakdown:
      Valuation    : 25pts  (P/E, Forward P/E)
      Profitability: 25pts  (Net Margin, ROE)
      Growth       : 25pts  (Revenue Growth, Earnings Growth)
      Health       : 25pts  (Debt/Equity, Current Ratio)
    """
    score   = 0
    signals = []

    # -- Valuation (max 25pts) --------------------------------
    pe = data.get("pe_ratio")
    if pe is not None:
        if pe < 15:
            score += 15
            signals.append(f"P/E ({pe}) -- undervalued ✅")
        elif pe < 25:
            score += 12
            signals.append(f"P/E ({pe}) -- fairly valued ✅")
        elif pe < 40:
            score += 7
            signals.append(f"P/E ({pe}) -- slightly expensive ⚠️")
        else:
            score += 2
            signals.append(f"P/E ({pe}) -- expensive ⚠️")
    else:
        signals.append("P/E -- no data ➡️")

    fpe = data.get("forward_pe")
    if fpe is not None:
        if fpe < 0:
            score += 0
            signals.append(f"Forward P/E ({fpe}) -- negative, future losses expected ⚠️")
        elif fpe < 15:
            score += 10
            signals.append(f"Forward P/E ({fpe}) -- cheap ✅")
        elif fpe < 25:
            score += 7
            signals.append(f"Forward P/E ({fpe}) -- reasonable ✅")
        elif fpe < 40:
            score += 3
            signals.append(f"Forward P/E ({fpe}) -- pricey ⚠️")
        else:
            score += 0
            signals.append(f"Forward P/E ({fpe}) -- very expensive ⚠️")
    else:
        signals.append("Forward P/E -- no data ➡️")

    # -- Profitability (max 25pts) ----------------------------
    nm = data.get("net_margin")
    if nm is not None:
        if nm > 20:
            score += 13
            signals.append(f"Net Margin ({nm}%) -- excellent ✅")
        elif nm > 10:
            score += 10
            signals.append(f"Net Margin ({nm}%) -- good ✅")
        elif nm > 0:
            score += 5
            signals.append(f"Net Margin ({nm}%) -- thin ⚠️")
        else:
            score += 0
            signals.append(f"Net Margin ({nm}%) -- losing money ⚠️")
    else:
        signals.append("Net Margin -- no data ➡️")

    roe = data.get("roe")
    if roe is not None:
        if roe > 20:
            score += 12
            signals.append(f"ROE ({roe}%) -- excellent ✅")
        elif roe > 10:
            score += 8
            signals.append(f"ROE ({roe}%) -- good ✅")
        elif roe > 0:
            score += 3
            signals.append(f"ROE ({roe}%) -- weak ⚠️")
        else:
            score += 0
            signals.append(f"ROE ({roe}%) -- negative ⚠️")
    else:
        signals.append("ROE -- no data ➡️")

    # -- Growth (max 25pts) -----------------------------------
    rg = data.get("revenue_growth")
    revenue_declining = rg is not None and rg <= 0

    if rg is not None:
        if rg > 20:
            score += 13
            signals.append(f"Revenue Growth ({rg}%) -- strong ✅")
        elif rg > 10:
            score += 10
            signals.append(f"Revenue Growth ({rg}%) -- good ✅")
        elif rg > 0:
            score += 5
            signals.append(f"Revenue Growth ({rg}%) -- slow ⚠️")
        else:
            score += 0
            signals.append(f"Revenue Growth ({rg}%) -- declining ⚠️")
    else:
        signals.append("Revenue Growth -- no data ➡️")

    eg = data.get("earnings_growth")
    if eg is not None:
        # Cap earnings growth score at 3pts when revenue is declining
        # Earnings growth on a shrinking business is often a one-time anomaly
        if revenue_declining and eg > 0:
            score += 3
            signals.append(
                f"Earnings Growth ({eg}%) -- but revenue declining, "
                f"treat with caution ⚠️"
            )
        elif eg > 20:
            score += 12
            signals.append(f"Earnings Growth ({eg}%) -- strong ✅")
        elif eg > 10:
            score += 8
            signals.append(f"Earnings Growth ({eg}%) -- good ✅")
        elif eg > 0:
            score += 3
            signals.append(f"Earnings Growth ({eg}%) -- slow ⚠️")
        else:
            score += 0
            signals.append(f"Earnings Growth ({eg}%) -- declining ⚠️")
    else:
        signals.append("Earnings Growth -- no data ➡️")

    # -- Financial Health (max 25pts) -------------------------
    de = data.get("debt_to_equity")
    if de is not None:
        if de < 50:
            score += 13
            signals.append(f"Debt/Equity ({de}) -- low debt ✅")
        elif de < 100:
            score += 9
            signals.append(f"Debt/Equity ({de}) -- moderate debt ✅")
        elif de < 200:
            score += 4
            signals.append(f"Debt/Equity ({de}) -- high debt ⚠️")
        else:
            score += 0
            signals.append(f"Debt/Equity ({de}) -- very high debt ⚠️")
    else:
        signals.append("Debt/Equity -- no data ➡️")

    cr = data.get("current_ratio")
    if cr is not None:
        if cr > 2:
            score += 12
            signals.append(f"Current Ratio ({cr}) -- very liquid ✅")
        elif cr > 1.5:
            score += 9
            signals.append(f"Current Ratio ({cr}) -- healthy ✅")
        elif cr > 1:
            score += 5
            signals.append(f"Current Ratio ({cr}) -- adequate ⚠️")
        else:
            score += 0
            signals.append(f"Current Ratio ({cr}) -- liquidity risk ⚠️")
    else:
        signals.append("Current Ratio -- no data ➡️")

    score         = max(0, min(100, score))
    verdict, icon = get_fundamental_verdict(score)

    return {
        "score":   score,
        "verdict": verdict,
        "icon":    icon,
        "signals": signals,
    }


def get_fundamental_verdict(score: int) -> tuple:
    """Converts fundamental score to verdict label."""
    if score >= 75:
        return "Strong Fundamentals",  "🟢"
    elif score >= 60:
        return "Good Fundamentals",    "🟩"
    elif score >= 40:
        return "Mixed Fundamentals",   "⬜"
    elif score >= 25:
        return "Weak Fundamentals",    "🟥"
    else:
        return "Poor Fundamentals",    "🔴"


# ============================================================
# Master Fundamental Analysis Function
# ============================================================

def fundamental_analysis(company: str) -> dict:
    """
    Master function -- fetches and scores fundamental data.
    Returns both raw data and scored signals.
    """
    ticker = resolve_ticker(company)
    print(f"  Running fundamental analysis for: {ticker}...")

    data = fetch_fundamental_data(ticker)
    if "error" in data:
        return {"error": data["error"]}

    score_result = score_fundamentals(data)

    return {
        "ticker":          ticker,
        "company":         data["name"],
        "sector":          data["sector"],
        "industry":        data["industry"],

        # Scored result
        "fundamental": {
            "score":   score_result["score"],
            "verdict": score_result["verdict"],
            "icon":    score_result["icon"],
            "signals": score_result["signals"],
        },

        # Raw data for display
        "valuation": {
            "pe_ratio":       data["pe_ratio"],
            "forward_pe":     data["forward_pe"],
            "price_to_book":  data["price_to_book"],
            "price_to_sales": data["price_to_sales"],
        },
        "profitability": {
            "gross_margin": data["gross_margin"],
            "net_margin":   data["net_margin"],
            "roe":          data["roe"],
            "roa":          data["roa"],
        },
        "growth": {
            "revenue_growth":  data["revenue_growth"],
            "earnings_growth": data["earnings_growth"],
            "eps":             data["eps"],
            "forward_eps":     data["forward_eps"],
        },
        "health": {
            "debt_to_equity": data["debt_to_equity"],
            "current_ratio":  data["current_ratio"],
            "free_cash_flow": data["free_cash_flow"],
            "total_revenue":  data["total_revenue"],
        },
        "analyst": {
            "target_price":   data["target_price"],
            "target_high":    data["target_high"],
            "target_low":     data["target_low"],
            "recommendation": data["recommendation"],
            "analyst_count":  data["analyst_count"],
            "current_price":  data["current_price"],
            "upside_pct":     data["upside_pct"],
        },
    }
