# ============================================================
# analyzers/sentiment/news.py -- News Data Fetcher
# ============================================================
# DATA LAYER ONLY. No scoring logic here.
# Fetches news articles from Yahoo Finance and returns a
# standardised list for news_scorer.py to process.
#
# Data sources (yfinance):
#   yf.Ticker(symbol).news   -- general financial news
#   yf.Search(query).news    -- ticker/company-specific news
#
# Fetch strategy:
#   1. Fetch general news (up to MAX_GENERAL articles)
#   2. Fetch specific news by ticker + company name (up to MAX_SPECIFIC)
#   3. Deduplicate by title similarity
#   4. Return combined list (up to MAX_ANALYSE articles)
#
# Output contract (standardised -- data source independent):
# {
#   "articles": list[dict]   raw article records, each:
#     {
#       "title":        str,
#       "source":       str,
#       "summary":      str,
#       "published_ts": int,   unix timestamp
#     }
#   "data_quality": str   "full" | "partial" | "failed"
# }
#
# Future data source migration:
#   Replace only this file. news_scorer.py receives the same
#   standardised dict regardless of the underlying data source.
# ============================================================

import time

import yfinance as yf


# ============================================================
# Constants
# ============================================================

MAX_GENERAL  = 15   # articles from yfinance general news
MAX_SPECIFIC = 10   # articles from yfinance ticker search
MAX_ANALYSE  = 20   # max articles returned to scorer


# ============================================================
# Internal helpers
# ============================================================

def _parse_article(item: dict) -> dict | None:
    """
    Converts a raw yfinance news item to a standardised article dict.
    Returns None if the item is missing required fields.
    """
    title = (item.get("title") or "").strip()
    if not title:
        return None

    # yfinance returns publisher as nested dict or flat string
    publisher = item.get("publisher") or ""
    if isinstance(publisher, dict):
        publisher = publisher.get("name", "")
    source = str(publisher).strip() or "Unknown"

    # Summary may be in "summary" or constructed from title
    summary = (
        item.get("summary") or
        item.get("description") or
        title
    ).strip()

    # Timestamp: yfinance gives providerPublishTime (unix int)
    published_ts = item.get("providerPublishTime") or 0

    return {
        "title":        title,
        "source":       source,
        "summary":      summary[:500],   # truncate for LLM token efficiency
        "published_ts": int(published_ts),
    }


def _fetch_general_news(ticker_symbol: str) -> list:
    """Fetches general financial news from yfinance ticker news feed."""
    try:
        time.sleep(1)
        raw      = yf.Ticker(ticker_symbol).news or []
        articles = []
        for item in raw[:MAX_GENERAL]:
            parsed = _parse_article(item)
            if parsed:
                articles.append(parsed)
        return articles
    except Exception as e:
        print(f"  General news fetch error: {e}")
        return []


def _fetch_specific_news(ticker_symbol: str, company_name: str) -> list:
    """
    Fetches stock-specific news via yfinance Search.
    Searches by both ticker symbol and company name for better coverage.
    """
    articles = []
    seen     = set()
    queries  = [ticker_symbol, company_name] if company_name else [ticker_symbol]

    for query in queries:
        try:
            time.sleep(0.5)
            results = yf.Search(query, news_count=MAX_SPECIFIC).news or []
            for item in results:
                parsed = _parse_article(item)
                if parsed and parsed["title"] not in seen:
                    seen.add(parsed["title"])
                    articles.append(parsed)
        except Exception as e:
            print(f"  Specific news fetch error for '{query}': {e}")

    return articles[:MAX_SPECIFIC]


def _deduplicate(general: list, specific: list) -> list:
    """
    Merges two article lists and removes near-duplicates by title.
    Specific news has priority (higher direct relevance expected).
    """
    merged = []
    seen   = set()

    for article in specific + general:
        key = article["title"].lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            merged.append(article)

    return merged[:MAX_ANALYSE]


# ============================================================
# Main fetch function
# ============================================================

def fetch_news_data(ticker_symbol: str,
                    company_name: str = "") -> dict:
    """
    Fetches all news articles and returns a standardised dict.
    This is the ONLY function called externally from this file.

    See module docstring for full output contract.
    """
    print(f"  Fetching news data for {ticker_symbol}...")

    general  = _fetch_general_news(ticker_symbol)
    specific = _fetch_specific_news(ticker_symbol, company_name)
    articles = _deduplicate(general, specific)

    if not articles:
        data_quality = "failed"
    elif len(articles) < 3:
        data_quality = "partial"
    else:
        data_quality = "full"

    return {
        "articles":     articles,
        "data_quality": data_quality,
    }
