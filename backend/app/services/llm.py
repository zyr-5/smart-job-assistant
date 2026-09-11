import json
import re
from typing import Any

from openai import OpenAI

from app.config import settings
from app.services.storage import load_config


class LLMError(Exception):
    pass


def _client() -> OpenAI:
    cfg = load_config().get("llm", {})
    timeout = cfg.get("timeout_seconds", 120)
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=timeout,
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM 返回非 JSON: {e}") from e


def chat_json(system: str, user: str, temperature: float = 0.3, task: str = "") -> dict:
    """task 用于 Mock 模式精确分发（match/company/interview），避免依赖 system 关键词猜测。"""
    if settings.use_mock:
        return _mock_response(system, user, task)

    client = _client()
    cfg_retries = 1
    last_err = None
    for attempt in range(cfg_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=settings.deepseek_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature if attempt == 0 else 0.1,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return _extract_json(content)
        except Exception as e:
            last_err = e
    raise LLMError(str(last_err))


def _mock_response(system: str, user: str, task: str = "") -> dict:
    # 优先按显式 task 分发；task 缺失时退回关键词猜测（兼容旧调用）
    if task == "match":
        resume, jd = _parse_match_input(user)
        return _mock_match(resume, jd)
    if task == "interview":
        return _mock_interview(user)
    if task == "company":
        return _mock_company(user)

    if "八维" in system or "D1" in system or "dimensions" in system:
        resume, jd = _parse_match_input(user)
        return _mock_match(resume, jd)
    if "公司信息" in system or "tech_stack" in system or "profile" in system:
        return _mock_company(user)
    if "面试" in system or "questions" in system:
        return _mock_interview(user)
    return _mock_company(user)


def _parse_match_input(user: str) -> tuple[str, str]:
    try:
        data = json.loads(user)
        if isinstance(data, dict):
            return str(data.get("resume", "") or ""), str(data.get("jd", "") or "")
    except json.JSONDecodeError:
        pass
    return "", ""


def _text_lower(text: str) -> str:
    return text.lower()


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = _text_lower(text)
    return [kw for kw in keywords if kw.lower() in lower]


def _keyword_overlap_ratio(resume: str, jd: str, keywords: list[str]) -> tuple[float, list[str], list[str]]:
    resume_hits = set(_find_keywords(resume, keywords))
    jd_hits = set(_find_keywords(jd, keywords))
    if not jd_hits:
        return 0.5, sorted(resume_hits), sorted(jd_hits)
    overlap = resume_hits & jd_hits
    ratio = len(overlap) / len(jd_hits)
    return ratio, sorted(overlap), sorted(jd_hits - resume_hits)


_SKILL_KEYWORDS = [
    "python", "java", "go", "golang", "javascript", "typescript",
    "fastapi", "flask", "django", "spring", "spring boot", "spring cloud", "mybatis", "dubbo",
    "mysql", "redis", "mongodb", "oracle", "postgresql", "elasticsearch", "clickhouse", "tidb", "hbase",
    "kafka", "rabbitmq", "celery", "rocketmq", "docker", "kubernetes", "k8s", "nginx", "git",
    "微服务", "分布式", "restful", "jwt", "grpc", "ci/cd", "linux",
]

_LANGUAGE_GROUPS = {
    "python": {"python", "fastapi", "flask", "django", "celery"},
    "java": {"java", "spring", "spring boot", "spring cloud", "mybatis", "dubbo"},
    "frontend": {"vue", "react", "angular", "javascript", "typescript"},
}

_INDUSTRY_KEYWORDS = {
    "金融": ["金融", "银行", "证券", "保险", "fintech", "支付", "交易"],
    "电商": ["电商", "订单", "商城", "零售"],
    "saas": ["saas", "云服务", "平台"],
    "互联网": ["互联网", "科技"],
}

_SOFT_SKILL_KEYWORDS = [
    "沟通", "协作", "团队", "领导", "管理", "学习", "责任心", "抗压", "汇报",
]

_EDUCATION_PATTERNS = [
    (r"博士", "博士"),
    (r"硕士|研究生", "硕士"),
    (r"本科|学士", "本科"),
    (r"大专|专科", "大专"),
]

_EDUCATION_RANK = {"博士": 4, "硕士": 3, "本科": 2, "大专": 1}


def _detect_language_stacks(text: str) -> set[str]:
    lower = _text_lower(text)
    stacks = set()
    for name, kws in _LANGUAGE_GROUPS.items():
        if any(kw in lower for kw in kws):
            stacks.add(name)
    return stacks


_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_number_to_int(text: str) -> int | None:
    """把「四」「十五」「二十」这类中文数字转成整数；仅处理常见 1-99 写法。"""
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = _CN_DIGITS.get(left, 1) if left else 1
        ones = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(text) == 1:
        return _CN_DIGITS.get(text)
    if len(text) == 2 and all(ch in _CN_DIGITS for ch in text):
        return _CN_DIGITS[text[0]] * 10 + _CN_DIGITS[text[1]]
    return None


def _extract_resume_years(resume: str) -> int | None:
    """
    从简历中抽取工作/开发年限。

    覆盖三类写法：
    1. 阿拉伯数字：「5年后端开发经验」「3年Python开发经验」「2年经验」
    2. 中文数字：「四年 Python 后端开发经验」「十年工作经验」
    3. 经验前置：「经验约 6 年」

    年限与"经验"之间可能夹着角色词或英文技术名（「年后端开发」「年 Python 后端开发」），
    因此用「最多 20 个非数字字符」跳过失配内容 —— 否则「5年后端开发经验」这类写法
    会匹配失败，进而被误判为"简历未提供工作年限"而错计 50 分。
    """
    normalized = resume

    # 中文数字先归一化为阿拉伯数字，便于复用同一套正则
    # 年份与"经验"之间允许出现最多 20 个非数字字符（如「年后端开发」「年 Python 后端开发」）。
    # 注意不能用 \s*：\s* 只跳过空白，"年 Python 后端开发经验" 中间夹着英文词时会匹配失败。
    cn_pattern = re.compile(
        r"([零一二两三四五六七八九十]{1,3})\s*年(?:以上|多)?(?:的)?\D{0,20}?(?:经验|经历)"
    )
    for m in list(cn_pattern.finditer(resume)):
        value = _cn_number_to_int(m.group(1))
        if value is not None:
            normalized = normalized.replace(m.group(0), f"{value}" + m.group(0)[len(m.group(1)):], 1)

    patterns = [
        r"(\d+)\s*年(?:以上|多)?(?:的)?\D{0,20}?(?:经验|经历|工作)",
        r"(?:经验|经历|工作)[^\d]{0,6}(\d+)\s*年",
    ]
    years: list[int] = []
    for pat in patterns:
        for m in re.finditer(pat, normalized, re.IGNORECASE):
            years.append(int(m.group(1)))
    return max(years) if years else None


def _extract_jd_year_range(jd: str) -> tuple[int | None, int | None]:
    m = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*年", jd)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*年以上", jd)
    if m:
        return int(m.group(1)), None
    m = re.search(r"(\d+)\s*年", jd)
    if m:
        val = int(m.group(1))
        return val, val
    return None, None


def _detect_education(text: str) -> str | None:
    for pattern, label in _EDUCATION_PATTERNS:
        if re.search(pattern, text):
            return label
    return None


def _detect_industries(text: str) -> set[str]:
    lower = _text_lower(text)
    found = set()
    for industry, kws in _INDUSTRY_KEYWORDS.items():
        if any(kw.lower() in lower for kw in kws):
            found.add(industry)
    return found


def _clamp_score(score: int) -> int:
    return max(15, min(95, score))


def _level_for_score(score: int) -> str:
    if score >= 80:
        return "高"
    if score >= 50:
        return "中"
    return "低"


def _score_skills(resume: str, jd: str) -> dict[str, Any]:
    ratio, overlap, missing = _keyword_overlap_ratio(resume, jd, _SKILL_KEYWORDS)
    resume_stacks = _detect_language_stacks(resume)
    jd_stacks = _detect_language_stacks(jd)
    stack_mismatch = bool(resume_stacks and jd_stacks and not (resume_stacks & jd_stacks))

    if not resume.strip() or not jd.strip():
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "输入文本不足，无法评估核心技能匹配度。",
            "evidence": [], "scoring_breakdown": [],
        }

    score = _clamp_score(35 + int(ratio * 55))
    breakdown: list[dict[str, str]] = []
    if overlap:
        breakdown.append({"point": f"+{min(30, len(overlap) * 5)} 技能关键词重合: {', '.join(overlap[:5])}", "type": "positive"})
    if missing:
        breakdown.append({"point": f"-{min(25, len(missing) * 4)} JD 要求但简历未体现: {', '.join(missing[:4])}", "type": "negative"})
    if stack_mismatch:
        score = _clamp_score(min(score, 35))
        breakdown.append({
            "point": f"-30 技术栈不匹配（简历: {', '.join(resume_stacks)} vs JD: {', '.join(jd_stacks)}）",
            "type": "negative",
        })

    reason = f"给分{score}分，因为简历与 JD 技能关键词重合率约 {int(ratio * 100)}%"
    if stack_mismatch:
        reason += f"，且主技术栈不一致（{', '.join(resume_stacks)} vs {', '.join(jd_stacks)}）"
    elif overlap:
        reason += f"，匹配项包括 {', '.join(overlap[:4])}"
    if missing:
        reason += f"，但缺少 {', '.join(missing[:3])} 等要求"

    return {
        "score": score, "missing": False,
        "score_reason": reason + "。",
        "analysis": "基于技能关键词重合与技术栈一致性进行模拟评估。",
        "evidence": [f"简历技能: {', '.join(overlap[:5]) or '未识别'}", f"JD 要求: {', '.join(_find_keywords(jd, _SKILL_KEYWORDS)[:5]) or '未识别'}"],
        "scoring_breakdown": breakdown,
    }


def _score_experience(resume: str, jd: str) -> dict[str, Any]:
    years = _extract_resume_years(resume)
    min_req, max_req = _extract_jd_year_range(jd)

    if years is None:
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未明确工作年限，无法对照 JD 经验要求。",
            "evidence": [], "scoring_breakdown": [],
        }

    if min_req is None:
        score = 65
        reason = f"给分{score}分，因为简历显示约 {years} 年经验，JD 未明确年限要求。"
    elif years >= min_req and (max_req is None or years <= max_req + 3):
        score = _clamp_score(70 + min(20, (years - min_req) * 5))
        reason = f"给分{score}分，因为简历 {years} 年经验满足 JD 要求的 {min_req}{f'-{max_req}' if max_req else '+'} 年。"
    elif years < min_req:
        score = _clamp_score(30 + int(years / max(min_req, 1) * 30))
        reason = f"给分{score}分，因为简历仅 {years} 年经验，低于 JD 要求的 {min_req} 年以上。"
    else:
        score = _clamp_score(55)
        reason = f"给分{score}分，因为简历 {years} 年经验超出 JD 上限 {max_req} 年，可能存在 overqualified 风险。"

    return {
        "score": score, "missing": False,
        "score_reason": reason,
        "analysis": "基于简历工作年限与 JD 经验要求进行模拟评估。",
        "evidence": [f"简历：约 {years} 年经验", f"JD：要求 {min_req or '未明确'}-{max_req or '未明确'} 年"],
        "scoring_breakdown": [
            {"point": f"+{score - 40} 年限对照", "type": "positive" if score >= 60 else "negative"},
        ],
    }


def _score_projects(resume: str, jd: str) -> dict[str, Any]:
    project_markers = ["项目", "负责", "开发", "设计", "实现", "重构", "优化", "系统"]
    resume_projects = _find_keywords(resume, project_markers)
    jd_projects = _find_keywords(jd, project_markers)

    if not resume_projects and "项目" not in resume:
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历缺少项目经历描述。",
            "evidence": [], "scoring_breakdown": [],
        }

    tech_ratio, overlap, _ = _keyword_overlap_ratio(resume, jd, _SKILL_KEYWORDS)
    has_metrics = bool(re.search(r"\d+\s*[%+万]|qps|p99|延迟|日活", resume, re.IGNORECASE))
    score = _clamp_score(45 + int(tech_ratio * 35) + (15 if has_metrics else 0))
    breakdown = []
    if has_metrics:
        breakdown.append({"point": "+15 项目成果有量化数据", "type": "positive"})
    if overlap:
        breakdown.append({"point": f"+{min(20, len(overlap) * 4)} 项目技术栈与 JD 相关", "type": "positive"})

    return {
        "score": score, "missing": False,
        "score_reason": f"给分{score}分，因为简历有项目经历描述，技术相关度约 {int(tech_ratio * 100)}%" + ("，且包含量化成果。" if has_metrics else "。"),
        "analysis": "基于项目描述丰富度与技术相关度进行模拟评估。",
        "evidence": [f"简历项目关键词: {', '.join(resume_projects[:4])}", f"JD 项目相关: {', '.join(jd_projects[:4])}"],
        "scoring_breakdown": breakdown,
    }


def _score_industry(resume: str, jd: str) -> dict[str, Any]:
    resume_ind = _detect_industries(resume)
    jd_ind = _detect_industries(jd)

    if not resume_ind and not re.search(r"公司|行业|领域", resume):
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未体现行业/domain 信息。",
            "evidence": [], "scoring_breakdown": [],
        }

    if not jd_ind:
        score = 60
        reason = f"给分{score}分，因为 JD 行业指向不明确，简历行业为 {', '.join(resume_ind) or '通用'}。"
    elif resume_ind & jd_ind:
        score = _clamp_score(75 + len(resume_ind & jd_ind) * 5)
        reason = f"给分{score}分，因为简历与 JD 行业领域重合：{', '.join(resume_ind & jd_ind)}。"
    else:
        score = _clamp_score(25 + len(resume_ind) * 5)
        reason = f"给分{score}分，因为简历行业（{', '.join(resume_ind) or '未识别'}）与 JD 行业（{', '.join(jd_ind)}）差异较大。"

    return {
        "score": score, "missing": False,
        "score_reason": reason,
        "analysis": "基于行业关键词重合进行模拟评估。",
        "evidence": [f"简历行业: {', '.join(resume_ind) or '未识别'}", f"JD 行业: {', '.join(jd_ind) or '未识别'}"],
        "scoring_breakdown": [
            {"point": f"{'+' if score >= 60 else '-'}{abs(score - 50)} 行业契合度", "type": "positive" if score >= 60 else "negative"},
        ],
    }


def _score_education(resume: str, jd: str) -> dict[str, Any]:
    resume_edu = _detect_education(resume)
    jd_edu = _detect_education(jd)

    if resume_edu is None:
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未提及学历与专业。",
            "evidence": [], "scoring_breakdown": [],
        }

    resume_rank = _EDUCATION_RANK.get(resume_edu, 2)
    jd_rank = _EDUCATION_RANK.get(jd_edu, 2) if jd_edu else 2

    if resume_rank >= jd_rank:
        score = _clamp_score(70 + (resume_rank - jd_rank) * 8)
        reason = f"给分{score}分，因为简历学历为{resume_edu}，满足 JD {jd_edu or '本科'}及以上要求。"
    else:
        score = _clamp_score(35 + resume_rank * 10)
        reason = f"给分{score}分，因为简历学历为{resume_edu}，低于 JD 要求的{jd_edu}。"

    return {
        "score": score, "missing": False,
        "score_reason": reason,
        "analysis": "基于学历层次对照进行模拟评估。",
        "evidence": [f"简历：{resume_edu}", f"JD：要求 {jd_edu or '本科及以上'}"],
        "scoring_breakdown": [
            {"point": f"{'+' if score >= 60 else '-'}{abs(score - 50)} 学历对照", "type": "positive" if score >= 60 else "negative"},
        ],
    }


def _score_responsibilities(resume: str, jd: str) -> dict[str, Any]:
    resp_keywords = ["开发", "维护", "设计", "架构", "优化", "api", "接口", "测试", "部署", "review", "负责"]
    ratio, overlap, missing = _keyword_overlap_ratio(resume, jd, resp_keywords)

    if not overlap and not _find_keywords(resume, resp_keywords):
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未描述职责范围。",
            "evidence": [], "scoring_breakdown": [],
        }

    score = _clamp_score(40 + int(ratio * 50))
    return {
        "score": score, "missing": False,
        "score_reason": f"给分{score}分，因为职责关键词重合率约 {int(ratio * 100)}%，匹配项: {', '.join(overlap[:4]) or '较少'}。",
        "analysis": "基于岗位职责关键词重合进行模拟评估。",
        "evidence": [f"简历职责: {', '.join(_find_keywords(resume, resp_keywords)[:4])}", f"JD 职责: {', '.join(_find_keywords(jd, resp_keywords)[:4])}"],
        "scoring_breakdown": [
            {"point": f"+{len(overlap) * 5} 职责关键词匹配", "type": "positive"},
            *([{"point": f"-{len(missing) * 4} 职责缺口", "type": "negative"}] if missing else []),
        ],
    }


def _score_soft_skills(resume: str, jd: str) -> dict[str, Any]:
    ratio, overlap, missing = _keyword_overlap_ratio(resume, jd, _SOFT_SKILL_KEYWORDS)
    has_star = bool(re.search(r"降低|提升|推动|协调|带领|组织", resume))

    if not _find_keywords(resume, _SOFT_SKILL_KEYWORDS) and not has_star:
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未体现软技能相关信息。",
            "evidence": [], "scoring_breakdown": [],
        }

    score = _clamp_score(45 + int(ratio * 30) + (12 if has_star else 0))
    return {
        "score": score, "missing": False,
        "score_reason": f"给分{score}分，因为软技能关键词匹配 {', '.join(overlap) or '较少'}" + ("，且有具体协作成果描述。" if has_star else "。"),
        "analysis": "基于软技能关键词与案例描述进行模拟评估。",
        "evidence": [f"简历: {', '.join(_find_keywords(resume, _SOFT_SKILL_KEYWORDS)[:3])}", f"JD: {', '.join(_find_keywords(jd, _SOFT_SKILL_KEYWORDS)[:3])}"],
        "scoring_breakdown": [
            {"point": f"+{int(ratio * 20)} 软技能关键词", "type": "positive"},
            *([{"point": "+12 有具体成果案例", "type": "positive"}] if has_star else []),
        ],
    }


def _score_career_fit(resume: str, jd: str) -> dict[str, Any]:
    title_keywords = ["后端", "前端", "架构师", "工程师", "开发", "python", "java", "全栈"]
    resume_titles = _find_keywords(resume, title_keywords)
    jd_titles = _find_keywords(jd, title_keywords)
    resume_stacks = _detect_language_stacks(resume)
    jd_stacks = _detect_language_stacks(jd)

    if not resume_titles and "求职" not in resume and "意向" not in resume:
        return {
            "score": 50, "missing": True,
            "score_reason": "因简历中未提供该维度相关信息，无法评估，按规则计50分",
            "analysis": "简历未明确求职意向或岗位方向。",
            "evidence": [], "scoring_breakdown": [],
        }

    title_overlap = set(resume_titles) & set(jd_titles)
    stack_match = bool(resume_stacks & jd_stacks) if resume_stacks and jd_stacks else True
    stack_mismatch = bool(resume_stacks and jd_stacks and not stack_match)

    if stack_mismatch:
        score = _clamp_score(25)
        reason = f"给分{score}分，因为求职技术方向（{', '.join(resume_stacks)}）与 JD（{', '.join(jd_stacks)}）不一致。"
    elif title_overlap:
        score = _clamp_score(72 + len(title_overlap) * 5)
        reason = f"给分{score}分，因为求职方向与 JD 岗位关键词重合：{', '.join(title_overlap)}。"
    else:
        score = _clamp_score(50)
        reason = f"给分{score}分，因为岗位方向部分匹配，简历侧重 {', '.join(resume_titles[:3])}，JD 要求 {', '.join(jd_titles[:3])}。"

    return {
        "score": score, "missing": False,
        "score_reason": reason,
        "analysis": "基于求职意向与岗位方向进行模拟评估。",
        "evidence": [f"简历意向: {', '.join(resume_titles[:4])}", f"JD 岗位: {', '.join(jd_titles[:4])}"],
        "scoring_breakdown": [
            {"point": f"{'+' if score >= 60 else '-'}{abs(score - 50)} 职业方向契合", "type": "positive" if score >= 60 else "negative"},
        ],
    }


_DIMENSION_NAMES = [
    "核心技能匹配", "工作经验匹配", "项目经历匹配", "行业/domain 匹配",
    "学历与资质匹配", "职责范围匹配", "软技能与综合素质", "职业发展契合度",
]

_DIMENSION_SCORERS = [
    _score_skills, _score_experience, _score_projects, _score_industry,
    _score_education, _score_responsibilities, _score_soft_skills, _score_career_fit,
]

_SUGGESTION_TEMPLATES = {
    "核心技能匹配": {
        "priority": "高",
        "issue": "D1 核心技能：简历技能与 JD 要求存在差距",
        "advice": "对照 JD 技能清单，在技能栏和项目经历中补充缺失的关键词，并用具体场景说明使用经验。",
        "example": "技术栈：Python, FastAPI, MySQL, Redis, Kafka | 项目：基于 Kafka 实现异步订单处理",
        "action_steps": ["列出 JD 要求但简历未体现的技能", "在技能栏补充 3-5 个关键词", "在项目描述中用一句话说明技术应用场景"],
        "expected_impact": "预计 D1 核心技能匹配度可提升 8-15 分",
    },
    "工作经验匹配": {
        "priority": "高",
        "issue": "D2 工作经验：年限或经验类型与 JD 要求不完全匹配",
        "advice": "突出与岗位相关的年限优势，或在自我评价中说明经验可迁移性。",
        "example": "5 年后端开发经验，具备高并发系统设计与性能优化能力，可快速适应新业务场景",
        "action_steps": ["在自我评价首句突出年限优势", "列举 2-3 个可迁移的技术能力", "表达对目标岗位的理解"],
        "expected_impact": "预计 D2 工作经验匹配度可提升 5-10 分",
    },
    "项目经历匹配": {
        "priority": "中",
        "issue": "D3 项目经历：项目描述与 JD 要求的技术深度或成果量化不足",
        "advice": "补充项目规模、技术难点和量化成果，使项目经历更贴近 JD 的高可用/高性能要求。",
        "example": "系统可用性达 99.95%，核心接口 P99 延迟从 800ms 优化至 120ms，日处理请求 500 万+",
        "action_steps": ["为核心项目补充 2-3 个量化指标", "增加与 JD 相关的技术关键词", "用优化前后对比突出成果"],
        "expected_impact": "预计 D3 项目经历匹配度可提升 5-10 分",
    },
    "行业/domain 匹配": {
        "priority": "高",
        "issue": "D4 行业/domain：简历行业背景与 JD 目标行业差距较大",
        "advice": "不必虚构行业经历，但应提炼可迁移的通用能力，并表达对目标行业的了解与意愿。",
        "example": "电商订单系统（可类比交易场景）：负责支付链路与对账模块，保障资金流转准确性与幂等性",
        "action_steps": ["在项目中补充与目标行业相关的类比描述", "自我评价中表达对目标行业的关注", "列举可迁移的通用技术能力"],
        "expected_impact": "预计 D4 行业匹配度可提升 10-15 分",
    },
    "学历与资质匹配": {
        "priority": "高",
        "issue": "D5 学历资质：简历未提供或未达到 JD 学历要求",
        "advice": "在简历中明确写出最高学历、专业与毕业年份，确保 HR 和 ATS 能快速识别。",
        "example": "教育背景：XX大学 | 计算机科学与技术 | 本科 | 2016.09 - 2020.06",
        "action_steps": ["新增或完善教育背景小节", "写明学历层次与专业", "若正在攻读学位，注明预计毕业时间"],
        "expected_impact": "补齐 D5 信息后可从无法评估转为正常评分，预计提升 5-8 分",
    },
    "职责范围匹配": {
        "priority": "中",
        "issue": "D6 职责范围：简历职责描述与 JD 岗位职责对应不足",
        "advice": "在核心项目中增加与 JD 职责对应的描述，说明你在开发、架构、优化等方面的具体贡献。",
        "example": "主导订单服务模块架构设计：采用领域驱动设计拆分子域，定义 API 规范并通过团队评审",
        "action_steps": ["对照 JD 职责清单逐条检查简历", "补充架构设计或技术选型相关描述", "用动词开头描述个人贡献"],
        "expected_impact": "预计 D6 职责匹配度可提升 6-10 分",
    },
    "软技能与综合素质": {
        "priority": "中",
        "issue": "D7 软技能：简历缺乏具体协作或沟通案例",
        "advice": "选取 1-2 个真实协作场景，用 STAR 法则简要描述跨团队协作成果。",
        "example": "在系统重构中主动与产品、测试对齐需求，组织技术评审推动方案落地，将返工率降低 30%",
        "action_steps": ["选取一个跨部门协作的真实案例", "按情境-行动-结果结构改写", "放在项目经历末尾或核心能力小节"],
        "expected_impact": "预计 D7 软技能维度可提升 5-8 分",
    },
    "职业发展契合度": {
        "priority": "高",
        "issue": "D8 职业发展：求职方向与 JD 岗位不一致",
        "advice": "调整求职意向与自我评价，使技术方向和岗位级别与目标 JD 对齐，避免给 HR 造成方向错配的印象。",
        "example": "求职意向：Python 后端开发工程师 | 期望加入重视技术氛围的团队，深耕后端架构与工程化",
        "action_steps": ["修改求职意向与 JD 岗位名称一致", "自我评价中呼应 JD 核心技术栈", "移除与目标岗位无关的意向描述"],
        "expected_impact": "预计 D8 职业发展契合度可提升 10-20 分",
    },
}


def _generate_suggestions(dims: list[dict]) -> list[dict]:
    weak = sorted(
        [d for d in dims if d.get("missing_info") or d["score"] < 70],
        key=lambda d: (0 if d.get("missing_info") else 1, d["score"]),
    )
    suggestions = []
    for dim in weak[:8]:
        tpl = _SUGGESTION_TEMPLATES.get(dim["name"], _SUGGESTION_TEMPLATES["核心技能匹配"]).copy()
        if dim.get("missing_info"):
            tpl["priority"] = "高"
            tpl["issue"] = f"{dim['id']} {dim['name']}：简历未提供该维度信息，当前按规则计 50 分"
        elif dim["score"] < 50:
            tpl["priority"] = "高"
            tpl["issue"] = f"{dim['id']} {dim['name']}：匹配度仅 {dim['score']} 分，差距显著"
        else:
            tpl["issue"] = f"{dim['id']} {dim['name']}：匹配度 {dim['score']} 分，仍有提升空间"
        suggestions.append(tpl)

    while len(suggestions) < 5:
        fallback = _SUGGESTION_TEMPLATES["项目经历匹配"].copy()
        fallback["priority"] = "低"
        suggestions.append(fallback)

    return suggestions[:10]


def _mock_match(resume: str = "", jd: str = "") -> dict:
    specs = []
    for scorer in _DIMENSION_SCORERS:
        specs.append(scorer(resume, jd))

    dims = []
    for i, spec in enumerate(specs, 1):
        score = spec["score"]
        dims.append({
            "id": f"D{i}",
            "name": _DIMENSION_NAMES[i - 1],
            "score": score,
            "level": _level_for_score(score),
            "score_reason": spec["score_reason"],
            "analysis": spec["analysis"],
            "evidence": spec["evidence"],
            "scoring_breakdown": spec["scoring_breakdown"],
            "missing_info": spec["missing"],
        })

    overall = round(sum(d["score"] for d in dims) / len(dims))
    return {
        "overall_score": overall,
        "dimensions": dims,
        "suggestions": _generate_suggestions(dims),
    }


def _mock_company(user: str) -> dict:
    company = "示例科技公司"
    if "company_name_input" in user:
        import re as r
        m = r.search(r'"company_name_input"\s*:\s*"([^"]+)"', user)
        if m:
            company = m.group(1)
    url = "https://example.com"
    return {
        "schema_version": "1.0",
        "company_name": company,
        "company_name_input": company,
        "official_website": url,
        "search_engine": "duckduckgo",
        "model": "deepseek-chat",
        "profile": {
            "industry": {"value": "互联网/软件", "confidence": "medium", "sources": [url], "note": ""},
            "business": {"value": f"{company}主要从事软件开发与技术服务", "confidence": "medium", "sources": [url], "note": ""},
            "tech_stack": {"value": ["Python", "Vue", "MySQL"], "confidence": "low", "sources": [url], "note": ""},
            "summary": {"value": f"{company}是一家技术服务企业。", "confidence": "medium", "sources": [url], "note": ""},
        },
        "sources": [
            {
                "url": url,
                "title": f"{company}官网",
                "tier": "P0",
                "source_type": "official",
                "used_in_fields": ["business", "summary"],
                "snippet": "公司简介...",
            },
            {
                "url": f"https://baike.baidu.com/item/{company}",
                "title": f"{company} - 百度百科",
                "tier": "P2",
                "source_type": "wiki",
                "used_in_fields": ["industry", "summary"],
                "snippet": "企业百科简介...",
            },
            {
                "url": f"https://www.infoq.cn/topic/{company}",
                "title": f"{company}技术报道",
                "tier": "P2",
                "source_type": "tech_blog",
                "used_in_fields": ["tech_stack"],
                "snippet": "技术架构与工程实践...",
            },
            {
                "url": f"https://36kr.com/p/{company}",
                "title": f"{company}相关新闻",
                "tier": "P1",
                "source_type": "news",
                "used_in_fields": ["summary"],
                "snippet": "行业动态报道...",
            },
            {
                "url": f"https://github.com/{company}",
                "title": f"{company}开源项目",
                "tier": "P2",
                "source_type": "tech_blog",
                "used_in_fields": ["tech_stack"],
                "snippet": "开源技术栈...",
            },
            {
                "url": f"https://xueqiu.com/S/{company}",
                "title": f"{company}财务信息",
                "tier": "P1",
                "source_type": "finance",
                "used_in_fields": ["industry"],
                "snippet": "融资与财报摘要...",
            },
            {
                "url": f"https://www.zhihu.com/topic/{company}",
                "title": f"{company}知乎讨论",
                "tier": "P2",
                "source_type": "social",
                "used_in_fields": ["summary"],
                "snippet": "社区讨论与评价...",
            },
        ],
        "disclaimer": "信息来自公开检索，可能存在滞后或不完整，请以官网为准",
    }


def _mock_interview(user: str) -> dict:
    config = {"技术题": 3, "项目题": 3, "行为题": 2}
    m = re.search(r'"question_config"\s*:\s*(\{[^}]+\})', user)
    if m:
        try:
            config = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    company = "目标公司"
    cm = re.search(r'"company_name"\s*:\s*"([^"]+)"', user)
    if cm:
        company = cm.group(1)

    templates = {
        "技术题": {
            "difficulty": "中", "duration_minutes": 15,
            "question": "请描述 RESTful API 的设计原则",
            "focus": "后端基础", "thinking": "资源、动词、状态码、无状态",
            "reference_answer": "围绕资源命名、HTTP 方法、状态码展开",
            "pitfalls": ["只背概念无实例"], "follow_ups": ["如何处理版本兼容？"],
        },
        "项目题": {
            "difficulty": "中", "duration_minutes": 20,
            "question": "介绍你最有挑战的一个项目",
            "focus": "项目深度", "thinking": "STAR 法则",
            "reference_answer": "背景-任务-行动-结果，量化成果",
            "pitfalls": ["只说团队不说个人贡献"], "follow_ups": ["遇到的最大技术难点？"],
        },
        "行为题": {
            "difficulty": "中", "duration_minutes": 10,
            "question": "描述一次与同事意见不合的经历",
            "focus": "沟通协作", "thinking": "STAR",
            "reference_answer": "客观描述冲突、沟通过程与结果",
            "pitfalls": ["抱怨他人"], "follow_ups": ["如果重来会怎么做？"],
        },
        "公司业务题": {
            "difficulty": "中", "duration_minutes": 10,
            "question": f"你对我们公司（{company}）的业务模式有什么了解？",
            "focus": "业务理解", "thinking": "结合 JD 与公司公开信息",
            "reference_answer": f"简述 {company} 的主营业务、产品定位与竞争优势",
            "pitfalls": ["泛泛而谈无具体信息"], "follow_ups": ["为什么选择这个行业？"],
        },
        "HR/综合题": {
            "difficulty": "初", "duration_minutes": 5,
            "question": "请做一个3分钟的自我介绍",
            "focus": "表达能力与岗位契合", "thinking": "结构：背景-经历-优势-动机",
            "reference_answer": "简明介绍教育、核心项目与求职动机",
            "pitfalls": ["过长无关信息"], "follow_ups": ["为什么选择这个岗位？"],
        },
    }

    questions = []
    qid = 1
    for qtype, count in config.items():
        tpl = templates.get(qtype, templates["技术题"])
        for i in range(count):
            questions.append({
                "id": f"q{qid}",
                "type": qtype,
                "difficulty": tpl["difficulty"],
                "duration_minutes": tpl["duration_minutes"],
                "question": f"[{qtype}] {tpl['question']}" + (f"（第{i + 1}题）" if count > 1 else ""),
                "focus": tpl["focus"],
                "thinking": tpl["thinking"],
                "reference_answer": tpl["reference_answer"],
                "pitfalls": tpl["pitfalls"],
                "follow_ups": tpl["follow_ups"],
            })
            qid += 1
    return {"questions": questions}
