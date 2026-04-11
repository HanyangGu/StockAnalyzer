# ============================================================
# analyzers/sentiment/news.py -- News Data Fetcher
# ============================================================
# v0.6: reads from RawDataBundle instead of calling yfinance.
# Output contract unchanged — news_scorer.py unaffected.
# ============================================================

import time
import yfinance as yf

MAX_GENERAL  = 15
MAX_SPECIFIC = 10
MAX_ANALYSE  = 20


def _parse_article(item: dict) -> dict | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    publisher = item.get("publisher") or ""
    if isinstance(publisher, dict):
        publisher = publisher.get("name", "")
    source       = str(publisher).strip() or "Unknown"
    summary      = (item.get("summary") or item.get("description") or title).strip()
    published_ts = item.get("providerPublishTime") or 0
    return {
        "title":        title,
        "source":       source,
        "summary":      summary[:500],
        "published_ts": int(published_ts),
    }


def _fetch_specific_news(ticker_symbol: str, company_name: str) -> list:
    """Fetch company-specific news via yfinance Search (no bundle equivalent)."""
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
    merged = []
    seen   = set()
    for article in specific + general:
        key = article["title"].lower().strip()[:60]
        if key not in seen:
            seen.add(key)
            merged.append(article)
    return merged[:MAX_ANALYSE]


def fetch_news_data(ticker_symbol: str,
                    company_name: str = "",
                    bundle: dict = None) -> dict:
    """
    Extracts news from RawDataBundle (general feed) and fetches
    specific news via yfinance Search (no bundle equivalent).
    Falls back to full yfinance fetch if bundle not provided.
    """
    print(f"  Fetching/parsing news data for {ticker_symbol}...")

    # General news from bundle
    if bundle is not None:
        raw_news = bundle.get("news") or []
        general  = []
        for item in raw_news[:MAX_GENERAL]:
            parsed = _parse_article(item)
            if parsed:
                general.append(parsed)
    else:
        # Legacy: fetch from yfinance directly
        try:
            time.sleep(1)
            raw_news = yf.Ticker(ticker_symbol).news or []
            general  = []
            for item in raw_news[:MAX_GENERAL]:
                parsed = _parse_article(item)
                if parsed:
                    general.append(parsed)
        except Exception as e:
            print(f"  General news fetch error: {e}")
            general = []

    # Specific news always requires a Search call (not in bundle)
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
