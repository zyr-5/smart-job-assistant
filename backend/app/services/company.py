import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from app.config import CACHE_DIR, settings
from app.services.search_providers import merge_results, search_baidu, search_bing
from app.services.llm import LLMError, chat_json
from app.services.storage import load_config, load_json, save_json

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _normalize_company(name: str) -> str:
    return re.sub(r"\s+", "", name.strip())


def _cache_path(name: str) -> Path:
    h = hashlib.md5(_normalize_company(name).encode()).hexdigest()
    return CACHE_DIR / f"company_{h}.json"


def _is_expired(cached: dict) -> bool:
    ttl = load_config().get("company", {}).get("cache_ttl_days", settings.company_cache_ttl_days)
    retrieved = cached.get("retrieved_at") or cached.get("company_profile", {}).get("retrieved_at")
    if not retrieved:
        return True
    try:
        dt = datetime.fromisoformat(retrieved)
        return datetime.now(dt.tzinfo or timezone.utc) - dt > timedelta(days=ttl)
    except ValueError:
        return True


def _classify_source(url: str, company: str) -> tuple[str, str]:
    domain = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    company_lower = company.lower()

    wiki_domains = ["baike.baidu.com", "wikipedia.org", "wiki.mbalib.com", "zhihu.com/baike"]
    if any(x in domain or x in url.lower() for x in wiki_domains):
        return "P2", "wiki"

    recruitment_domains = [
        "zhipin.com", "liepin.com", "51job.com", "lagou.com", "maimai.cn",
        "boss.com", "kanzhun.com", "yingjiesheng.com",
    ]
    if any(x in domain for x in recruitment_domains):
        return "P2", "recruitment"

    finance_domains = [
        "eastmoney.com", "xueqiu.com", "cninfo.com.cn", "sse.com.cn",
        "hkexnews.hk", "finance.sina.com.cn", "wallstreetcn.com",
    ]
    if any(x in domain for x in finance_domains) or any(
        k in path for k in ["investor", "financial", "annual-report", "财报", "年报"]
    ):
        return "P1", "finance"

    news_domains = [
        "36kr.com", "ithome.com", "toutiao.com", "ifeng.com", "thepaper.cn",
        "cls.cn", "jiemian.com", "huxiu.com", "geekpark.net",
    ]
    if any(x in domain for x in news_domains):
        return "P1", "news"

    tech_blog_domains = [
        "github.com", "gitee.com", "juejin.cn", "csdn.net", "infoq.cn",
        "segmentfault.com", "oschina.net", "cloud.tencent.com/developer",
    ]
    if any(x in domain for x in tech_blog_domains):
        return "P2", "tech_blog"

    social_domains = ["weibo.com", "xiaohongshu.com", "douyin.com", "bilibili.com"]
    if "zhihu.com" in domain:
        return "P2", "social"
    if any(x in domain for x in social_domains):
        return "P2", "social"

    clean = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", company_lower)
    dom_clean = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    if clean and (clean[:2] in dom_clean or dom_clean in clean):
        return "P0", "official"

    news_keywords = ["news", "xinwen", "article", "media"]
    if any(k in path for k in news_keywords):
        return "P1", "news"

    return "P1", "other"


MIN_PROFILE_SOURCES = 5
MAX_PAGE_FETCHES = 3
PAGE_FETCH_TIMEOUT = 5.0
RESEARCH_TIMEOUT_SECONDS = 150


def _company_config() -> dict:
    return load_config().get("company", {})


def _research_deadline() -> float:
    timeout = _company_config().get("research_timeout_seconds", RESEARCH_TIMEOUT_SECONDS)
    return time.monotonic() + timeout


def _time_remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _timed_out(deadline: float, buffer: float = 0.0) -> bool:
    return _time_remaining(deadline) <= buffer


def _mock_search_results(company_name: str, official_website: str = "") -> list[dict]:
    """Diverse mock search results for offline/mock mode without live DDG calls."""
    official = official_website or f"https://www.{company_name.lower().replace(' ', '')}.com"
    templates = [
        (official, f"{company_name} 官网", "用户提供的官网", "P0", "official", "user_input"),
        (f"https://baike.baidu.com/item/{company_name}", f"{company_name} - 百度百科", "企业百科简介...", "P2", "wiki", "百科"),
        (f"https://36kr.com/p/{company_name}", f"{company_name}相关新闻", "行业动态报道...", "P1", "news", "新闻"),
        (f"https://github.com/{company_name}", f"{company_name}开源项目", "开源技术栈...", "P2", "tech_blog", "技术"),
        (f"https://xueqiu.com/S/{company_name}", f"{company_name}财务信息", "融资与财报摘要...", "P1", "finance", "财报"),
        (f"https://www.zhihu.com/topic/{company_name}", f"{company_name}知乎讨论", "社区讨论与评价...", "P2", "social", "社交"),
        (f"https://www.ithome.com/tag/{company_name}", f"{company_name} IT资讯", "科技媒体报道...", "P1", "news", "新闻"),
        (f"https://www.infoq.cn/topic/{company_name}", f"{company_name} InfoQ", "技术报道与架构分享...", "P2", "tech_blog", "技术"),
        (f"https://juejin.cn/search?query={company_name}", f"{company_name}技术文章", "技术博客与分享...", "P2", "tech_blog", "技术"),
    ]
    return [
        {
            "url": url,
            "title": title,
            "snippet": snippet,
            "tier": tier,
            "source_type": source_type,
            "query": query,
        }
        for url, title, snippet, tier, source_type, query in templates
    ]


def _build_profile_sources(search_results: list[dict], max_sources: int = 12) -> list[dict]:
    """Build profile.sources from search results, preserving diversity up to max_sources."""
    seen_urls: set[str] = set()
    sources: list[dict] = []
    for r in search_results:
        url = r.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append({
            "url": url,
            "title": r.get("title", ""),
            "tier": r.get("tier", "P1"),
            "source_type": r.get("source_type", "other"),
            "provider": r.get("provider", "duckduckgo"),
            "used_in_fields": ["summary"],
            "snippet": (r.get("snippet") or "")[:300],
            "fetched_at": _now_iso(),
        })
        if len(sources) >= max_sources:
            break
    return sources


def _has_sufficient_sources(profile: dict) -> bool:
    return len(profile.get("sources") or []) >= MIN_PROFILE_SOURCES


def _normalize_profile_field(
    field,
    *,
    default_confidence: str = "low",
    default_sources: list | None = None,
) -> dict:
    """Coerce LLM output (plain string or partial dict) into the canonical field schema."""
    sources = list(default_sources or [])
    if field is None:
        return {"value": None, "confidence": default_confidence, "sources": sources, "note": ""}
    if isinstance(field, str):
        value = field.strip() or None
        confidence = "medium" if value else default_confidence
        return {"value": value, "confidence": confidence, "sources": sources, "note": ""}
    if not isinstance(field, dict):
        return {"value": str(field), "confidence": default_confidence, "sources": sources, "note": ""}
    value = field.get("value")
    if isinstance(value, str):
        value = value.strip() or None
    if value is None and field.get("note"):
        value = str(field["note"]).strip() or None
    out_sources = field.get("sources")
    if not isinstance(out_sources, list):
        out_sources = sources
    return {
        "value": value,
        "confidence": field.get("confidence") or (default_confidence if not value else "medium"),
        "sources": out_sources,
        "note": field.get("note") or "",
    }


def _normalize_company_profile(profile: dict, company_name_input: str) -> dict:
    """Ensure profile fields and sources match the schema expected by the frontend."""
    profile = dict(profile or {})
    profile.setdefault("schema_version", "1.0")
    profile["company_name_input"] = company_name_input
    profile.setdefault("company_name", company_name_input)

    raw_profile = profile.get("profile")
    if not isinstance(raw_profile, dict):
        raw_profile = {}
    official = profile.get("official_website") or ""
    default_sources = [official] if official else []

    normalized_profile: dict = {}
    for key in ("summary", "industry", "business", "tech_stack"):
        if key not in raw_profile:
            continue
        confidence = "low" if key == "tech_stack" else "medium"
        normalized_profile[key] = _normalize_profile_field(
            raw_profile.get(key),
            default_confidence=confidence,
            default_sources=default_sources,
        )

    ts = normalized_profile.get("tech_stack")
    if isinstance(ts, dict) and ts.get("value") is None:
        ts["value"] = []

    profile["profile"] = normalized_profile
    if not isinstance(profile.get("sources"), list):
        profile["sources"] = []
    return profile


def _profile_has_content(profile: dict) -> bool:
    p = profile.get("profile") or {}
    for key in ("summary", "industry", "business"):
        field = p.get(key)
        if isinstance(field, dict) and field.get("value"):
            return True
        if isinstance(field, str) and field.strip():
            return True
    return False


def _is_cacheable_profile(profile: dict) -> bool:
    sources = profile.get("sources") or []
    if len(sources) < 1:
        return False
    if profile.get("partial_result") and not _profile_has_content(profile):
        return False
    return True


def _fallback_search_results(company_name: str, official_website: str = "") -> list[dict]:
    """Synthetic search rows when live DDG returns nothing — keeps the LLM pipeline usable."""
    results: list[dict] = []
    if official_website:
        results.append({
            "url": official_website,
            "title": f"{company_name} 官网",
            "snippet": "用户提供的官网",
            "tier": "P0",
            "source_type": "official",
            "query": "fallback",
        })
    templates = [
        (
            f"https://baike.baidu.com/item/{company_name}",
            f"{company_name} - 百度百科",
            f"关于{company_name}的企业百科与公开简介",
            "P2",
            "wiki",
        ),
        (
            f"https://www.zhihu.com/search?type=content&q={company_name}",
            f"{company_name} - 相关讨论",
            f"关于{company_name}的行业讨论与评价",
            "P2",
            "social",
        ),
        (
            f"https://36kr.com/search/articles/{company_name}",
            f"{company_name} - 行业新闻",
            f"关于{company_name}的媒体报道与行业动态",
            "P1",
            "news",
        ),
    ]
    for url, title, snippet, tier, source_type in templates:
        results.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "tier": tier,
            "source_type": source_type,
            "query": "fallback",
        })
    return results


def _minimal_profile_from_name(company_name: str, official_website: str = "", *, partial: bool = False) -> dict:
    """Last-resort profile when search and LLM both yield nothing usable."""
    url = official_website or None
    sources = [url] if url else []
    note = "公开检索暂无结果，以下信息置信度较低"
    summary = (
        f"{company_name}（未能从公开渠道检索到详细信息，建议填写官网后重试，"
        "或结合招聘 JD 自行了解公司业务）"
    )
    disclaimer = "信息来自公开检索，可能存在滞后或不完整，请以官网为准"
    if partial:
        disclaimer += "；部分检索步骤因超时已跳过，结果可能不完整，建议稍后重试"
    return {
        "schema_version": "1.0",
        "company_name": company_name,
        "company_name_input": company_name,
        "official_website": url,
        "profile": {
            "summary": {"value": summary, "confidence": "low", "sources": sources, "note": note},
            "industry": {"value": None, "confidence": "low", "sources": sources, "note": note},
            "business": {"value": None, "confidence": "low", "sources": sources, "note": note},
            "tech_stack": {"value": [], "confidence": "low", "sources": sources, "note": note},
        },
        "sources": _build_profile_sources(_fallback_search_results(company_name, official_website)),
        "disclaimer": disclaimer,
        "partial_result": partial,
        "low_confidence": True,
    }


def _search_queries(company_name: str) -> list[str]:
    """Start with simple queries, then broaden for source diversity."""
    return [
        company_name,
        f"{company_name} 公司简介",
        f"{company_name} 官网",
        f"{company_name} 主营业务",
        f"{company_name} 技术栈 开源 架构",
        f"{company_name} 行业 融资 上市",
        f"{company_name} 新闻 报道",
        f"{company_name} 百度百科",
    ]


def _run_ddg_queries(
    company_name: str,
    queries: list[str],
    per_query: int,
    seen: set[str],
    max_results: int,
    deadline: float | None,
    ddg_timeout: float,
) -> tuple[list[dict], list[str]]:
    """Run DDG with strict limits; return (results, errors)."""
    results: list[dict] = []
    errors: list[str] = []
    regions = [_company_config().get("search_region", "cn-zh"), "wt-wt"]
    max_queries = _company_config().get("max_ddg_queries", 3)
    consecutive_failures = 0
    max_failures = 1

    try:
        with DDGS(timeout=ddg_timeout) as ddgs:
            for region in regions:
                if deadline is not None and _timed_out(deadline, buffer=25):
                    break
                for q in queries[:max_queries]:
                    if deadline is not None and _timed_out(deadline, buffer=25):
                        break
                    if consecutive_failures >= max_failures:
                        return results, errors
                    if len(results) >= max_results:
                        return results, errors
                    try:
                        count = 0
                        for r in ddgs.text(q, region=region, max_results=per_query):
                            url = r.get("href") or r.get("link") or ""
                            if not url or url in seen:
                                continue
                            seen.add(url)
                            tier, st = _classify_source(url, company_name)
                            results.append({
                                "url": url,
                                "title": r.get("title", ""),
                                "snippet": r.get("body", r.get("snippet", "")),
                                "tier": tier,
                                "source_type": st,
                                "query": q,
                                "provider": "duckduckgo",
                            })
                            count += 1
                        consecutive_failures = 0 if count else consecutive_failures + 1
                    except Exception as e:
                        consecutive_failures += 1
                        errors.append(f"{region}/{q}: {e}")
                        logger.warning("DDG query failed for %r (%s): %s", company_name, q, e)
                if consecutive_failures >= max_failures:
                    break
    except Exception as e:
        errors.append(str(e))
        logger.warning("DDG search failed for %r: %s", company_name, e)
    return results, errors


def _run_provider_queries(
    provider_fn,
    provider_name: str,
    queries: list[str],
    per_query: int,
    company_name: str,
    seen: set[str],
    results: list[dict],
    max_results: int,
    deadline: float | None,
    timeout: float,
    min_target: int,
) -> None:
    for q in queries:
        if deadline is not None and _timed_out(deadline, buffer=20):
            break
        if len(results) >= min_target or len(results) >= max_results:
            break
        items = provider_fn(q, max_results=per_query, timeout=timeout)
        merge_results(results, items, company_name, _classify_source, seen, max_results)


def search_company(company_name: str, official_website: str = "", deadline: float | None = None) -> list[dict]:
    queries = _search_queries(company_name)
    per_query = _company_config().get("search_results_per_query", 5)
    max_results = _company_config().get("max_search_results", 30)
    min_before_fallback = _company_config().get("min_results_before_fallback", 3)
    fallback_timeout = _company_config().get("fallback_search_timeout_seconds", 6)
    providers = _company_config().get("search_providers", ["bing", "duckduckgo"])
    seen: set[str] = set()
    results: list[dict] = []

    if official_website:
        results.append({
            "url": official_website,
            "title": f"{company_name} 官网",
            "snippet": "用户提供的官网",
            "tier": "P0",
            "source_type": "official",
            "query": "user_input",
            "provider": "user",
        })
        seen.add(official_website)

    if settings.use_mock:
        return _mock_search_results(company_name, official_website)

    primary_queries = [company_name, f"{company_name} 公司简介", f"{company_name} 官网"]

    # 1) Bing first — fast and reliable in CN
    if "bing" in providers and len(results) < min_before_fallback:
        _run_provider_queries(
            search_bing, "bing", primary_queries, per_query, company_name,
            seen, results, max_results, deadline, fallback_timeout, min_before_fallback,
        )
        if results:
            logger.info("Bing search for %r: %d results", company_name, len(results))

    # 2) DuckDuckGo — limited queries/time budget
    if "duckduckgo" in providers and len(results) < min_before_fallback:
        ddg_timeout = _company_config().get("ddg_timeout_seconds", 4)
        ddg_results, ddg_errors = _run_ddg_queries(
            company_name, queries, per_query, seen, max_results, deadline, ddg_timeout,
        )
        results.extend(ddg_results)
        if ddg_errors and not ddg_results:
            logger.warning("DDG returned 0 for %r: %s", company_name, ddg_errors[:2])

    # 3) Baidu — optional, often blocked; try only if still empty
    if "baidu" in providers and len(results) < min_before_fallback:
        _run_provider_queries(
            search_baidu, "baidu", primary_queries, per_query, company_name,
            seen, results, max_results, deadline, fallback_timeout, min_before_fallback,
        )

    if not results:
        results = _fallback_search_results(company_name, official_website)

    results.sort(key=lambda x: {"P0": 0, "P1": 1, "P2": 2}.get(x.get("tier", "P2"), 3))
    return results[:max_results]


def fetch_page_text(url: str, max_chars: int = 8000, timeout: float = PAGE_FETCH_TIMEOUT) -> str:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 JobAssistant/1.0"})
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return text[:max_chars]
    except Exception:
        return ""


def _fetch_priority_pages(search_results: list[dict], deadline: float, max_pages: int = MAX_PAGE_FETCHES) -> list[dict]:
    """Fetch up to max_pages URLs in parallel; skip slow responses and stop when enough content."""
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for tier in ("P0", "P1", "P2"):
        for r in search_results:
            url = r.get("url", "")
            if not url or r.get("tier") != tier or url in seen_urls:
                continue
            seen_urls.add(url)
            candidates.append(r)
            if len(candidates) >= max_pages:
                break
        if len(candidates) >= max_pages:
            break

    if not candidates or _timed_out(deadline, buffer=8):
        return []

    per_page_timeout = min(
        PAGE_FETCH_TIMEOUT,
        _company_config().get("page_fetch_timeout_seconds", PAGE_FETCH_TIMEOUT),
    )
    remaining = _time_remaining(deadline) - 5
    if remaining <= 0:
        return []

    extracted: list[dict] = []
    workers = min(len(candidates), max_pages)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_page_text, r["url"], 8000, per_page_timeout): r
            for r in candidates[:max_pages]
        }
        try:
            for future in as_completed(futures, timeout=min(remaining, max_pages * per_page_timeout + 2)):
                if _timed_out(deadline, buffer=5):
                    break
                r = futures[future]
                try:
                    text = future.result(timeout=1)
                except Exception:
                    continue
                if text:
                    extracted.append({"url": r["url"], "tier": r["tier"], "text": text[:8000]})
                if len(extracted) >= max_pages:
                    break
        except Exception:
            pass
    return extracted


MISSING_INFO_SCORE = 50
MISSING_INFO_SCORE_REASON = "因简历中未提供该维度相关信息，无法评估，按规则计50分"

MATCH_SYSTEM = """你是求职匹配分析专家。根据简历和JD进行8维度匹配分析。
维度：D1核心技能、D2工作经验、D3项目经历、D4行业domain、D5学历资质、D6职责范围、D7软技能、D8职业发展。
规则：
- missing_info=true 仅当简历中完全没有该维度的相关信息、无法对照评估时使用；JD 信息缺失 alone 不触发 missing_info
- missing_info=true 时：score=50, level=中，score_reason 须说明"因简历中未提供该维度相关信息，无法评估，按规则计50分"（非保底分，仅因简历缺失该维度信息）
- 简历有该维度信息但匹配较差时：missing_info=false，score 可低于 50（如 30、40），须给出具体低分原因
- 简历有信息且匹配良好时：正常评分；不得将 50 分作为不确定时的默认值或最低分（保底）
- 不得虚构简历内容，evidence仅引用输入文本
- 每个维度必须给出 score_reason（1-3句）：明确说明为何给出该分数，格式如"给分70分，因为简历中具备X但缺少Y"
- 可选 scoring_breakdown：评分明细列表，每项含 point（如"+10 具备Python3年经验"）和 type（positive|negative|neutral）
- analysis 为对该维度的综合分析（可与 score_reason 互补，勿重复堆砌）
- 等级：高>=80，中50-79，低<50
- overall_score为8维等权平均（整数）
- suggestions 须输出 5-10 条，覆盖不同维度（D1-D8），每条须针对 JD 与简历的具体差距，引用维度分析中的低分点或 missing_info
- 每条 suggestion 字段：
  - priority: 高|中|低（与差距严重程度对应）
  - issue: 具体问题描述，须标明维度（如 D5学历资质）及差距是什么
  - advice: 详细改进方向，2-4句可执行步骤，说明改什么、怎么改
  - example: 简历改写示例段落或句式，尽量具体、可直接套用
  - action_steps: 2-4 条具体行动步骤的字符串数组，如 ["在项目经历中补充XX", "将技能关键词改为YY"]
  - expected_impact: 可选，说明预期可提升的维度或匹配度（如"预计 D4 行业匹配度可提升 10-15 分"）
输出JSON：{"overall_score":int,"dimensions":[{"id":"D1","name":"","score":int,"level":"高|中|低","score_reason":"","analysis":"","evidence":[],"scoring_breakdown":[{"point":"","type":"positive|negative|neutral"}],"missing_info":bool},...],"suggestions":[{"priority":"高|中|低","issue":"","advice":"","example":"","action_steps":["",""],"expected_impact":""}]}"""


COMPANY_SYSTEM = """你是公司信息整理专家。仅基于提供的检索材料润色并结构化为JSON，禁止臆造事实。
技术栈无可靠来源时 tech_stack.value 为空数组 []。
无法确认填 null。每 profile 字段须有 confidence(high|medium|low) 和 sources(URL数组)。
输出JSON schema_version=1.0，含 company_name, company_name_input, official_website, profile(industry,business,tech_stack,summary), sources[], disclaimer。"""


INTERVIEW_SYSTEM = """你是面试教练。根据岗位JD和候选人简历生成针对性面试题。
用户会通过 question_config 指定每种题型的数量，你必须严格按照配置生成，每种题型数量必须完全一致，不多不少。
题型仅限：技术题、项目题、行为题、公司业务题、HR/综合题。
题目须紧密结合 JD 技能要求与简历中的项目/经历，避免泛泛而谈。
若提供了 company_name 或 company_profile，生成「公司业务题」时应结合公司行业、主营业务、技术栈等信息。
输出JSON：{"questions":[{"id":"","type":"技术题|项目题|行为题|公司业务题|HR/综合题","difficulty":"初|中|高","duration_minutes":int,"question":"","focus":"","thinking":"","reference_answer":"","pitfalls":[],"follow_ups":[]}]}
仅输出 questions 数组，不要输出 flow 或其他字段。"""

VALID_QUESTION_TYPES = ("技术题", "项目题", "行为题", "公司业务题", "HR/综合题")
MAX_QUESTIONS_PER_TYPE = 20
MAX_TOTAL_QUESTIONS = 50


def validate_question_config(config: dict) -> dict:
    if not config or not isinstance(config, dict):
        raise ValueError("请至少选择一种题型并设置数量")
    validated: dict[str, int] = {}
    for qtype, count in config.items():
        if qtype not in VALID_QUESTION_TYPES:
            raise ValueError(f"未知题型: {qtype}")
        if not isinstance(count, int) or isinstance(count, bool):
            raise ValueError(f"{qtype} 数量须为整数")
        if count < 1 or count > MAX_QUESTIONS_PER_TYPE:
            raise ValueError(f"{qtype} 数量须在 1-{MAX_QUESTIONS_PER_TYPE} 之间")
        validated[qtype] = count
    if not validated:
        raise ValueError("请至少选择一种题型并设置数量")
    if sum(validated.values()) > MAX_TOTAL_QUESTIONS:
        raise ValueError(f"题目总数不能超过 {MAX_TOTAL_QUESTIONS}")
    return validated


def _validate_interview_questions(questions: list, question_config: dict) -> None:
    if not isinstance(questions, list):
        raise LLMError("questions 必须为数组")
    type_counts: dict[str, int] = {t: 0 for t in question_config}
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise LLMError(f"questions[{i}] 必须为对象")
        qtype = q.get("type")
        if qtype not in question_config:
            raise LLMError(f"questions[{i}] 题型 {qtype!r} 不在请求配置中")
        type_counts[qtype] += 1
        for field in ("question", "focus", "reference_answer"):
            if not q.get(field):
                raise LLMError(f"questions[{i}] 缺少必填字段 {field}")
    for qtype, expected in question_config.items():
        actual = type_counts.get(qtype, 0)
        if actual != expected:
            raise LLMError(f"{qtype} 数量应为 {expected}，实际为 {actual}")


def analyze_match(resume_text: str, jd_text: str) -> dict:
    user = json_prompt({"resume": resume_text[:12000], "jd": jd_text[:12000]})
    result = chat_json(MATCH_SYSTEM, user, temperature=0.3, task="match")
    _validate_match(result)
    return result


def _validate_match(result: dict) -> None:
    dims = result.get("dimensions", [])
    if len(dims) != 8:
        raise LLMError("维度数量不为8")
    for d in dims:
        if d.get("missing_info"):
            d["score"] = MISSING_INFO_SCORE
            d["level"] = "中"
            if not d.get("score_reason"):
                d["score_reason"] = MISSING_INFO_SCORE_REASON
        elif not d.get("score_reason"):
            if d.get("analysis"):
                d["score_reason"] = d["analysis"]
            else:
                d["score_reason"] = f"给分{d.get('score', 0)}分"
        breakdown = d.get("scoring_breakdown")
        if breakdown is not None and not isinstance(breakdown, list):
            d["scoring_breakdown"] = []
    total = sum(d.get("score", 0) for d in dims)
    result["overall_score"] = round(total / 8)
    _validate_suggestions(result.get("suggestions", []))


def _validate_suggestions(suggestions: list) -> None:
    if not isinstance(suggestions, list):
        raise LLMError("suggestions 必须为数组")
    for i, s in enumerate(suggestions):
        if not isinstance(s, dict):
            raise LLMError(f"suggestions[{i}] 必须为对象")
        for field in ("priority", "issue", "advice", "example"):
            if not s.get(field):
                raise LLMError(f"suggestions[{i}] 缺少必填字段 {field}")
        steps = s.get("action_steps")
        if steps is None:
            s["action_steps"] = []
        elif not isinstance(steps, list):
            s["action_steps"] = []
        elif len(steps) < 2:
            raise LLMError(f"suggestions[{i}] action_steps 至少需要 2 条")


def json_prompt(data: dict) -> str:
    import json
    return json.dumps(data, ensure_ascii=False)


def _search_engine_label(search_results: list[dict]) -> str:
    providers = {r.get("provider") for r in search_results if r.get("provider")}
    if "bing" in providers:
        return "bing"
    if "duckduckgo" in providers:
        return "duckduckgo"
    if "baidu" in providers:
        return "baidu"
    return "fallback"


def research_company(company_name: str, official_website: str = "", position: str = "", force_refresh: bool = False) -> tuple[dict, bool]:
    cache_file = _cache_path(company_name)
    if not force_refresh:
        cached = load_json(cache_file)
        if cached and not _is_expired(cached):
            profile = _normalize_company_profile(
                cached.get("company_profile", cached),
                company_name,
            )
            if _is_cacheable_profile(profile):
                return profile, True

    deadline = _research_deadline()
    partial = False

    search_results = search_company(company_name, official_website, deadline=deadline)
    search_unavailable = all(r.get("query") == "fallback" for r in search_results)
    if (deadline is not None and _timed_out(deadline, buffer=15)):
        partial = True
    extracted: list[dict] = []
    extracted_urls: set[str] = set()
    max_pages = _company_config().get("max_page_fetches", MAX_PAGE_FETCHES)
    skip_page_fetch = _company_config().get("skip_page_fetch_when_search_ok", True)
    min_before_fallback = _company_config().get("min_results_before_fallback", 3)
    has_live_search = not search_unavailable and len(search_results) >= min_before_fallback
    if (
        not settings.use_mock
        and not _timed_out(deadline, buffer=8)
        and not search_unavailable
        and not (skip_page_fetch and has_live_search)
    ):
        extracted = _fetch_priority_pages(search_results, deadline, max_pages=max_pages)
        extracted_urls = {item["url"] for item in extracted}
        if _timed_out(deadline, buffer=5):
            partial = True

    if not extracted:
        for r in search_results[:8]:
            if r["url"] not in extracted_urls:
                extracted.append({"url": r["url"], "tier": r["tier"], "text": r.get("snippet", "")})
                extracted_urls.add(r["url"])

    user_payload = {
        "company_name_input": company_name,
        "position": position,
        "search_results": search_results,
        "extracted_contents": extracted,
        "search_unavailable": search_unavailable,
    }
    try:
        profile = chat_json(COMPANY_SYSTEM, json_prompt(user_payload), temperature=0.3, task="company")
    except LLMError:
        profile = _minimal_profile_from_name(company_name, official_website, partial=partial)
        profile["retrieved_at"] = _now_iso()
        profile["search_engine"] = _search_engine_label(search_results)
        profile["model"] = settings.deepseek_model
        profile["sources"] = _build_profile_sources(search_results)
        if _is_cacheable_profile(profile):
            save_json(cache_file, {"company_profile": profile, "retrieved_at": profile["retrieved_at"]})
        return profile, False

    profile = _normalize_company_profile(profile, company_name)
    profile.setdefault("schema_version", "1.0")
    profile["company_name_input"] = company_name
    profile["retrieved_at"] = _now_iso()
    profile["search_engine"] = _search_engine_label(search_results)
    profile["model"] = settings.deepseek_model
    profile["sources"] = _build_profile_sources(search_results)
    disclaimer = "信息来自公开检索，可能存在滞后或不完整，请以官网为准"
    if search_unavailable:
        disclaimer += "；公开搜索暂不可用或结果不足，以下信息置信度较低"
    if partial:
        disclaimer += "；部分检索步骤因超时已跳过，结果可能不完整，建议稍后重试或使用更简洁的公司名称"
    profile.setdefault("disclaimer", disclaimer)
    profile["partial_result"] = partial
    profile["low_confidence"] = search_unavailable

    if not _profile_has_content(profile):
        fallback = _minimal_profile_from_name(company_name, official_website, partial=partial)
        profile.setdefault("profile", {})
        for key in ("summary", "industry", "business", "tech_stack"):
            if not profile["profile"].get(key, {}).get("value"):
                profile["profile"][key] = fallback["profile"][key]
        profile["low_confidence"] = True

    ts = profile.get("profile", {}).get("tech_stack", {})
    if isinstance(ts, dict) and ts.get("value") is None:
        ts["value"] = []

    if _is_cacheable_profile(profile):
        save_json(cache_file, {"company_profile": profile, "retrieved_at": profile["retrieved_at"]})
    return profile, False


def _compact_company_profile(profile: dict | None) -> dict | None:
    if not profile:
        return None
    p = profile.get("profile") or {}
    compact = {}
    for key in ("summary", "industry", "business", "tech_stack"):
        field = p.get(key) or {}
        value = field.get("value")
        if value:
            compact[key] = value
    if not compact:
        return None
    return compact


def generate_interview(question_config: dict, jd_text: str, resume_text: str,
                       company_name: str = "", company_profile: dict | None = None) -> dict:
    user_payload = {
        "question_config": question_config,
        "jd_text": jd_text[:8000],
        "resume_text": resume_text[:8000],
    }
    name = company_name or (company_profile or {}).get("company_name") or (company_profile or {}).get("company_name_input") or ""
    if name:
        user_payload["company_name"] = name
    compact = _compact_company_profile(company_profile)
    if compact:
        user_payload["company_profile"] = compact
    result = chat_json(INTERVIEW_SYSTEM, json_prompt(user_payload), temperature=0.5, task="interview")
    _validate_interview_questions(result.get("questions", []), question_config)
    return result
