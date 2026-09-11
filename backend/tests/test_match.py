"""Unit tests for match analysis schema and validation."""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.company import MISSING_INFO_SCORE, MISSING_INFO_SCORE_REASON, _validate_match
from app.services.llm import _mock_match

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _load_sample(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def test_mock_match_has_score_reason():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume, jd)
    assert len(result["dimensions"]) == 8
    for dim in result["dimensions"]:
        assert dim.get("score_reason"), f"{dim['id']} missing score_reason"
        assert isinstance(dim.get("scoring_breakdown", []), list)


def test_mock_match_missing_info_score_reason():
    resume_no_edu = "张明远，Python 后端开发，5年经验，熟悉 FastAPI 和 MySQL，负责订单系统开发。"
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume_no_edu, jd)
    missing_dims = [d for d in result["dimensions"] if d.get("missing_info")]
    assert len(missing_dims) >= 1
    for dim in missing_dims:
        assert dim["score"] == MISSING_INFO_SCORE
        assert "因简历中未提供该维度相关信息" in dim["score_reason"]
        assert "50分" in dim["score_reason"]
        assert "保底" not in dim["score_reason"]
        assert "默认" not in dim["score_reason"]


def test_mock_match_low_score_without_missing_info():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_mismatch.txt")
    result = _mock_match(resume, jd)
    low_dims = [
        d for d in result["dimensions"]
        if not d.get("missing_info") and d["score"] < MISSING_INFO_SCORE
    ]
    assert len(low_dims) >= 1
    for dim in low_dims:
        assert dim["score"] != MISSING_INFO_SCORE


def test_mock_match_backend_vs_mismatch():
    resume = _load_sample("resume_backend.txt")
    jd_match = _load_sample("jd_backend.txt")
    jd_mismatch = _load_sample("jd_mismatch.txt")
    score_match = _mock_match(resume, jd_match)["overall_score"]
    score_mismatch = _mock_match(resume, jd_mismatch)["overall_score"]
    assert score_match > score_mismatch, (
        f"backend+backend ({score_match}) should score higher than backend+mismatch ({score_mismatch})"
    )
    assert score_match - score_mismatch >= 10, (
        f"expected score gap >= 10, got {score_match - score_mismatch}"
    )


def test_mock_match_scores_vary_by_input():
    resume = _load_sample("resume_backend.txt")
    jd_a = _load_sample("jd_backend.txt")
    jd_b = _load_sample("jd_mismatch.txt")
    score_a = _mock_match(resume, jd_a)["overall_score"]
    score_b = _mock_match(resume, jd_b)["overall_score"]
    assert score_a != score_b


def test_validate_match_fills_score_reason():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume, jd)
    for dim in result["dimensions"]:
        dim.pop("score_reason", None)
    _validate_match(result)
    for dim in result["dimensions"]:
        assert dim.get("score_reason")


def test_validate_match_missing_info_forces_score_50():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume, jd)
    missing = next((d for d in result["dimensions"] if d.get("missing_info")), None)
    if missing is None:
        result["dimensions"][4]["missing_info"] = True
        missing = result["dimensions"][4]
    missing["score"] = 30
    missing.pop("score_reason", None)
    _validate_match(result)
    assert missing["score"] == MISSING_INFO_SCORE
    assert missing["level"] == "中"
    assert missing["score_reason"] == MISSING_INFO_SCORE_REASON


def test_mock_match_suggestions_detailed():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_mismatch.txt")
    result = _mock_match(resume, jd)
    suggestions = result["suggestions"]
    assert len(suggestions) >= 5
    for s in suggestions:
        assert s.get("priority") in ("高", "中", "低")
        assert s.get("issue")
        assert s.get("advice")
        assert s.get("example")
        assert len(s.get("action_steps", [])) >= 2
        assert s.get("expected_impact")


def test_validate_match_rejects_incomplete_suggestions():
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume, jd)
    result["suggestions"][0].pop("advice")
    try:
        _validate_match(result)
        assert False, "should raise on missing advice"
    except Exception as e:
        assert "advice" in str(e)


def test_extract_resume_years_common_phrasings():
    """回归用例：'N年后端开发经验' 曾因正则只允许单个 role 词而漏匹配，导致误判为信息缺失。"""
    from app.services.llm import _extract_resume_years

    cases = {
        "5年后端开发经验": 5,
        "3年Python开发经验": 3,
        "4年以上工作经验": 4,
        "拥有 2 年开发经验": 2,
        "经验约 6 年": 6,
        "四年 Python 后端开发经验": 4,
        "十年工作经验": 10,
        "熟悉 Python 与 FastAPI，无年限描述": None,
    }
    for text, expected in cases.items():
        got = _extract_resume_years(text)
        assert got == expected, f"{text!r} -> {got}, 期望 {expected}"


def test_mock_match_detects_years_in_common_phrasing():
    """带年限的简历必须 scored 为有信息（missing_info=False），不能计 50 分缺失分。"""
    resume = _load_sample("resume_backend.txt")
    jd = _load_sample("jd_backend.txt")
    result = _mock_match(resume, jd)
    experience = [d for d in result["dimensions"] if d["id"] == "D2"]
    assert experience, "缺少 D2 工作经验维度"
    assert experience[0]["missing_info"] is False, "简历已写明年限，不应判定为信息缺失"
    assert experience[0]["score"] != MISSING_INFO_SCORE


if __name__ == "__main__":
    try:
        test_mock_match_has_score_reason()
        test_mock_match_missing_info_score_reason()
        test_mock_match_low_score_without_missing_info()
        test_mock_match_backend_vs_mismatch()
        test_mock_match_scores_vary_by_input()
        test_validate_match_fills_score_reason()
        test_validate_match_missing_info_forces_score_50()
        test_mock_match_suggestions_detailed()
        test_validate_match_rejects_incomplete_suggestions()
        test_extract_resume_years_common_phrasings()
        test_mock_match_detects_years_in_common_phrasing()
        print("\n=== ALL MATCH TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== FAILED: {e!r} ===", file=sys.stderr)
        sys.exit(1)
