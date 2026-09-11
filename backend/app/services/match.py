from app.config import TMP_DIR
from app.services.company import analyze_match, generate_interview, validate_question_config
from app.services.storage import load_json


def get_upload_text(file_id: str | None, text: str | None) -> str:
    if text and text.strip():
        return text.strip()
    if file_id:
        meta = load_json(TMP_DIR / f"{file_id}.json")
        if meta and meta.get("text"):
            return meta["text"]
    raise ValueError("缺少有效输入")


def run_match(resume_source: str, jd_source: str, resume_file_id: str | None = None,
              resume_text: str | None = None, jd_file_id: str | None = None, jd_text: str | None = None,
              resume_file_name: str = "", jd_file_name: str = "") -> dict:
    resume = get_upload_text(resume_file_id if resume_source == "file" else None, resume_text)
    jd = get_upload_text(jd_file_id if jd_source == "file" else None, jd_text)

    if len(resume) < 50 and resume_source == "text":
        raise ValueError("简历文本至少50字")
    if len(jd) < 30 and jd_source == "text":
        raise ValueError("JD文本至少30字")
    if not resume:
        raise ValueError("简历内容为空")
    if not jd:
        raise ValueError("JD内容为空")

    result = analyze_match(resume, jd)
    return {"result": result}


def run_interview(question_config: dict,
                  jd_source: str = "file", jd_file_id: str | None = None, jd_text: str | None = None,
                  resume_source: str = "file", resume_file_id: str | None = None, resume_text: str | None = None,
                  jd_file_name: str = "", resume_file_name: str = "",
                  company_name: str = "", company_profile: dict | None = None) -> dict:
    validated_config = validate_question_config(question_config)

    jd = get_upload_text(jd_file_id if jd_source == "file" else None, jd_text)
    resume = get_upload_text(resume_file_id if resume_source == "file" else None, resume_text)

    if len(jd) < 30:
        raise ValueError("JD内容过短或为空，请上传或粘贴至少30字的岗位描述")
    if len(resume) < 50:
        raise ValueError("简历内容过短或为空，请上传或粘贴至少50字的简历")

    interview_data = generate_interview(
        validated_config, jd, resume,
        company_name=company_name.strip(),
        company_profile=company_profile,
    )
    return {"questions": interview_data.get("questions", [])}
