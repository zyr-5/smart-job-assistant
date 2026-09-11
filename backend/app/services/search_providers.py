"""Web search providers: DuckDuckGo (in company.py), Baidu, Bing HTML search."""

import logging
import re
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _clean_text(text: str, max_len: int = 300) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:max_len]


def search_baidu(query: str, max_results: int = 5, timeout: float = 8.0) -> list[dict]:
    """Baidu HTML search — good fallback for Chinese company names."""
    results: list[dict] = []
    try:
        url = f"https://www.baidu.com/s?wd={quote(query)}&rn={max_results}"
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for block in soup.select("div.result, div.c-container"):
                a = block.select_one("h3 a") or block.select_one("a")
                if not a or not a.get("href"):
                    continue
                href = a["href"]
                # Baidu redirect links — keep as-is or try to resolve
                title = _clean_text(a.get_text(), 120)
                snippet_el = block.select_one(".c-abstract, .content-right_8Zs40, span.content-right")
                if not snippet_el:
                    snippet_el = block.select_one("div.c-span-last, .c-color-text")
                snippet = _clean_text(snippet_el.get_text() if snippet_el else "", 300)
                if not title:
                    continue
                # Skip baidu internal links
                if "baidu.com/link" in href or href.startswith("/"):
                    # still usable as search evidence with baidu redirect
                    pass
                results.append({
                    "url": href,
                    "title": title,
                    "snippet": snippet or title,
                    "provider": "baidu",
                    "query": query,
                })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.warning("Baidu search failed for %r: %s", query, e)
    return results


def search_bing(query: str, max_results: int = 5, timeout: float = 8.0) -> list[dict]:
    """Bing HTML search — secondary fallback."""
    results: list[dict] = []
    try:
        url = f"https://www.bing.com/search?q={quote(query)}&ensearch=0"
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return results
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.b_algo"):
                a = li.select_one("h2 a")
                if not a or not a.get("href"):
                    continue
                href = a["href"]
                title = _clean_text(a.get_text(), 120)
                snippet_el = li.select_one(".b_caption p, p")
                snippet = _clean_text(snippet_el.get_text() if snippet_el else "", 300)
                if not title or not href.startswith("http"):
                    continue
                results.append({
                    "url": href,
                    "title": title,
                    "snippet": snippet or title,
                    "provider": "bing",
                    "query": query,
                })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.warning("Bing search failed for %r: %s", query, e)
    return results


def merge_results(
    existing: list[dict],
    new_items: list[dict],
    company_name: str,
    classify_fn,
    seen: set[str],
    max_total: int,
) -> int:
    """Merge new search rows into existing; returns count added."""
    added = 0
    for r in new_items:
        url = r.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        tier, st = classify_fn(url, company_name)
        existing.append({
            "url": url,
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "tier": tier,
            "source_type": st,
            "query": r.get("query", ""),
            "provider": r.get("provider", "unknown"),
        })
        added += 1
        if len(existing) >= max_total:
            break
    return added
