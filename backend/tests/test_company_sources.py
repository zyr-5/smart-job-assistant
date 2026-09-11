"""Unit tests for company profile sources diversity."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.company import (
    MIN_PROFILE_SOURCES,
    _build_profile_sources,
    _fallback_search_results,
    _mock_search_results,
    _normalize_company_profile,
    _profile_has_content,
    _search_queries,
    research_company,
    search_company,
)


def test_mock_search_results_diverse():
    results = _mock_search_results("阿里巴巴", "https://www.alibaba.com")
    assert len(results) >= 7
    types = {r["source_type"] for r in results}
    assert len(types) >= 4
    print(f"[OK] mock search results: {len(results)} entries, types={types}")


def test_search_company_mock_mode():
    from app.config import settings

    if not settings.use_mock:
        print("[SKIP] search_company mock test (not in mock mode)")
        return
    results = search_company("阿里巴巴", "https://www.alibaba.com")
    assert len(results) >= MIN_PROFILE_SOURCES
    print(f"[OK] search_company mock: {len(results)} results")


def test_build_profile_sources():
    search_results = _mock_search_results("阿里巴巴", "https://www.alibaba.com")
    sources = _build_profile_sources(search_results)
    assert len(sources) >= MIN_PROFILE_SOURCES
    assert all("url" in s and "tier" in s for s in sources)
    print(f"[OK] build profile sources: {len(sources)} sources")


def test_research_company_sources():
    from app.config import settings

    if not settings.use_mock:
        print("[SKIP] research_company sources test (not in mock mode)")
        return
    profile, from_cache = research_company("阿里巴巴", "https://www.alibaba.com", force_refresh=True)
    sources = profile.get("sources", [])
    assert len(sources) >= MIN_PROFILE_SOURCES, f"expected >={MIN_PROFILE_SOURCES}, got {len(sources)}"
    assert not from_cache
    profile_fields = profile.get("profile", {})
    assert "open_positions" not in profile_fields
    print(f"[OK] research_company: {len(sources)} sources")


def test_search_queries_count():
    queries = _search_queries("阿里巴巴")
    assert len(queries) <= 8
    assert queries[0] == "阿里巴巴"
    assert f"阿里巴巴 公司简介" in queries
    assert not any("招聘" in q for q in queries)
    print(f"[OK] search queries consolidated: {len(queries)}")


def test_fallback_search_results_any_company():
    for name in ("腾讯", "字节跳动", "华为", "美团"):
        results = _fallback_search_results(name)
        assert len(results) >= 3, f"{name} fallback too small"
        assert all(r.get("snippet") for r in results)
    print("[OK] fallback search results for multiple companies")


def test_normalize_flat_llm_profile():
    raw = {
        "company_name": "腾讯控股有限公司",
        "company_name_input": "腾讯",
        "profile": {
            "industry": "互联网科技",
            "business": "社交、游戏、金融科技",
            "summary": "腾讯是中国领先的互联网综合服务提供商。",
            "tech_stack": {"value": [], "confidence": "low", "sources": []},
        },
        "sources": [],
    }
    profile = _normalize_company_profile(raw, "腾讯")
    assert _profile_has_content(profile)
    assert profile["profile"]["industry"]["value"] == "互联网科技"
    assert profile["profile"]["summary"]["value"].startswith("腾讯")
    print("[OK] normalize flat LLM profile")


def test_search_company_fallback_when_ddg_fails():
    from app.services import company as company_mod

    with patch.object(company_mod, "settings") as mock_settings:
        mock_settings.use_mock = False
        with patch.object(company_mod, "search_bing", return_value=[]), patch.object(company_mod, "search_baidu", return_value=[]), patch.object(company_mod, "DDGS") as mock_ddgs:
            mock_ddgs.side_effect = RuntimeError("network down")
            results = search_company("华为")
    assert len(results) >= 3
    assert results[0]["query"] == "fallback"
    print(f"[OK] search_company fallback: {len(results)} results")


def test_research_company_multiple_names_mock():
    from app.config import settings

    if not settings.use_mock:
        print("[SKIP] research_company multi-name test (not in mock mode)")
        return
    for name in ("腾讯", "字节跳动", "华为", "美团"):
        profile, from_cache = research_company(name, force_refresh=True)
        assert _profile_has_content(profile), f"{name} profile empty"
        assert len(profile.get("sources") or []) >= MIN_PROFILE_SOURCES, f"{name} sources too few"
        assert profile["profile"]["summary"]["value"]
        assert not from_cache
    print("[OK] research_company mock for 腾讯/字节跳动/华为/美团")


def test_research_company_respects_deadline():
    from unittest.mock import patch
    from app.services import company as company_mod

    mock_results = _mock_search_results("测试公司")
    start = time.monotonic()
    with patch.object(company_mod, "_research_deadline", lambda: time.monotonic() + 0.01), patch.object(
        company_mod, "search_company", return_value=mock_results
    ):
        profile, from_cache = research_company("测试公司", force_refresh=True)
    elapsed = time.monotonic() - start
    assert elapsed < 30, f"research_company took too long: {elapsed:.1f}s"
    assert isinstance(profile, dict)
    assert "sources" in profile
    assert profile.get("partial_result") is True
    print(f"[OK] research_company deadline: elapsed={elapsed:.2f}s, sources={len(profile.get('sources', []))}")


if __name__ == "__main__":
    try:
        test_search_queries_count()
        test_fallback_search_results_any_company()
        test_normalize_flat_llm_profile()
        test_search_company_fallback_when_ddg_fails()
        test_mock_search_results_diverse()
        test_search_company_mock_mode()
        test_build_profile_sources()
        test_research_company_sources()
        test_research_company_multiple_names_mock()
        test_research_company_respects_deadline()
        print("\n=== ALL COMPANY SOURCE TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== FAILED: {e!r} ===", file=sys.stderr)
        sys.exit(1)
