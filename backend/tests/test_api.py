"""Backend integration tests for smart-job-assistant."""
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FIXTURES = Path(__file__).parent / "fixtures"


def test_health():
    r = httpx.get(f"{BASE}/api/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    print("[OK] health", data)


def test_upload_and_match():
    resume = FIXTURES / "resume.txt"
    jd = FIXTURES / "jd.txt"
    with httpx.Client(timeout=120) as client:
        r1 = client.post(f"{BASE}/api/upload/parse", files={"file": ("resume.txt", resume.read_bytes(), "text/plain")})
        assert r1.status_code == 200, r1.text
        resume_data = r1.json()["data"]
        assert resume_data["char_count"] > 50
        print("[OK] upload resume", resume_data["file_id"])

        r2 = client.post(f"{BASE}/api/upload/parse", files={"file": ("jd.txt", jd.read_bytes(), "text/plain")})
        assert r2.status_code == 200, r2.text
        jd_data = r2.json()["data"]
        print("[OK] upload jd", jd_data["file_id"])

        r3 = client.post(f"{BASE}/api/match/analyze", json={
            "resume_source": "file",
            "resume_file_id": resume_data["file_id"],
            "resume_file_name": "resume.txt",
            "jd_source": "file",
            "jd_file_id": jd_data["file_id"],
            "jd_file_name": "jd.txt",
        })
        assert r3.status_code == 200, r3.text
        result = r3.json()["data"]["result"]
        assert len(result["dimensions"]) == 8
        assert "overall_score" in result
        assert len(result["suggestions"]) >= 5
        for s in result["suggestions"]:
            assert s.get("issue") and s.get("advice") and s.get("example")
            assert len(s.get("action_steps", [])) >= 2
        for dim in result["dimensions"]:
            assert dim.get("score_reason"), f"{dim['id']} missing score_reason"
            if dim.get("missing_info"):
                assert dim["score"] == 50
                assert "因简历中未提供该维度相关信息" in dim["score_reason"]
                assert "保底" not in dim["score_reason"]
        # 说明：低分（<50 且非 missing_info）场景由 tests/test_match.py
        # 的 test_mock_match_low_score_without_missing_info 用 jd_mismatch.txt 覆盖；
        # 本用例的 fixtures 为高匹配组合，各维度均不低于 50 分，故此处不再重复断言。
        print("[OK] match analyze", result["overall_score"])


def test_interview():
    resume = FIXTURES / "resume.txt"
    jd = FIXTURES / "jd.txt"
    with httpx.Client(timeout=120) as client:
        r1 = client.post(f"{BASE}/api/upload/parse", files={"file": ("resume.txt", resume.read_bytes(), "text/plain")})
        assert r1.status_code == 200, r1.text
        resume_data = r1.json()["data"]

        r2 = client.post(f"{BASE}/api/upload/parse", files={"file": ("jd.txt", jd.read_bytes(), "text/plain")})
        assert r2.status_code == 200, r2.text
        jd_data = r2.json()["data"]

        question_config = {"技术题": 3, "项目题": 3, "行为题": 2}
        r = client.post(f"{BASE}/api/interview/generate", json={
            "question_config": question_config,
            "resume_source": "file",
            "resume_file_id": resume_data["file_id"],
            "resume_file_name": "resume.txt",
            "jd_source": "file",
            "jd_file_id": jd_data["file_id"],
            "jd_file_name": "jd.txt",
        })
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "flow" not in data
        assert "company_profile" not in data
        assert len(data["questions"]) == sum(question_config.values())
        type_counts = {}
        for q in data["questions"]:
            assert q.get("question") and q.get("reference_answer")
            type_counts[q["type"]] = type_counts.get(q["type"], 0) + 1
        for qtype, count in question_config.items():
            assert type_counts.get(qtype) == count, f"{qtype}: expected {count}, got {type_counts.get(qtype)}"
        print("[OK] interview", len(data["questions"]), "questions")


if __name__ == "__main__":
    try:
        test_health()
        test_upload_and_match()
        test_interview()
        print("\n=== ALL TESTS PASSED ===")
    except Exception as e:
        print(f"\n=== FAILED: {e!r} ===", file=sys.stderr)
        sys.exit(1)
