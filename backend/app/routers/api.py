from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.company import research_company
from app.services.file_parser import ParseError, save_upload
from app.services.llm import LLMError
from app.services.match import run_interview, run_match

router = APIRouter()


class MatchRequest(BaseModel):
    resume_source: str = "file"
    resume_file_id: str | None = None
    resume_text: str | None = None
    resume_file_name: str = ""
    jd_source: str = "file"
    jd_file_id: str | None = None
    jd_text: str | None = None
    jd_file_name: str = ""


class CompanyRequest(BaseModel):
    company_name: str
    official_website: str = ""
    position: str = ""
    force_refresh: bool = False


class InterviewRequest(BaseModel):
    question_config: dict[str, int] = {"技术题": 3, "项目题": 3, "行为题": 2}
    company_name: str = ""
    company_profile: dict | None = None
    jd_source: str = "file"
    jd_file_id: str | None = None
    jd_text: str | None = None
    jd_file_name: str = ""
    resume_source: str = "file"
    resume_file_id: str | None = None
    resume_text: str | None = None
    resume_file_name: str = ""


def ok(data):
    return {"code": 0, "message": "success", "data": data}


@router.post("/upload/parse")
async def upload_parse(file: UploadFile = File(...)):
    try:
        content = await file.read()
        file_id, text = save_upload(file.filename or "upload.txt", content)
        return ok({
            "file_id": file_id,
            "file_name": file.filename,
            "text": text,
            "char_count": len(text),
        })
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/match/analyze")
def match_analyze(req: MatchRequest):
    try:
        data = run_match(
            req.resume_source, req.jd_source,
            req.resume_file_id, req.resume_text,
            req.jd_file_id, req.jd_text,
            req.resume_file_name, req.jd_file_name,
        )
        return ok(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=424, detail=str(e)) from e


@router.post("/company/research")
def company_research(req: CompanyRequest):
    try:
        profile, from_cache = research_company(
            req.company_name, req.official_website, req.position, req.force_refresh
        )
        return ok({"company_profile": profile, "from_cache": from_cache})
    except LLMError as e:
        raise HTTPException(status_code=424, detail=str(e)) from e


@router.post("/interview/generate")
def interview_generate(req: InterviewRequest):
    try:
        data = run_interview(
            req.question_config,
            req.jd_source, req.jd_file_id, req.jd_text,
            req.resume_source, req.resume_file_id, req.resume_text,
            req.jd_file_name, req.resume_file_name,
            req.company_name, req.company_profile,
        )
        return ok(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=424, detail=str(e)) from e
