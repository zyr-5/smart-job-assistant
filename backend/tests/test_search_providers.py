"""Tests for Baidu/Bing search provider parsers."""

from app.services.search_providers import merge_results, search_baidu, search_bing


def test_merge_results_dedupes():
    seen = set()
    existing = []
    items = [
        {"url": "https://example.com", "title": "A", "snippet": "s", "provider": "baidu", "query": "q"},
        {"url": "https://example.com", "title": "A dup", "snippet": "s", "provider": "baidu", "query": "q"},
    ]

    def classify(url, company):
        return "P1", "news"

    added = merge_results(existing, items, "测试公司", classify, seen, 10)
    assert added == 1
    assert len(existing) == 1
    assert existing[0]["provider"] == "baidu"


def test_baidu_search_returns_list():
    # Live network — may return [] in CI; just ensure no crash
    results = search_baidu("腾讯 公司简介", max_results=3, timeout=5.0)
    assert isinstance(results, list)


def test_bing_search_returns_list():
    results = search_bing("腾讯 公司简介", max_results=3, timeout=5.0)
    assert isinstance(results, list)
