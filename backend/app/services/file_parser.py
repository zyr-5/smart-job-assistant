import uuid
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from app.config import TMP_DIR, settings
from app.services.storage import load_config


class ParseError(Exception):
    pass


def _allowed_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    cfg = load_config()
    allowed = cfg.get("upload", {}).get("allowed_extensions", ["pdf", "docx", "txt"])
    if ext not in allowed:
        raise ParseError(f"不支持的文件格式，仅支持: {', '.join(allowed)}")
    return ext


def parse_txt(content: bytes) -> str:
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return content.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    raise ParseError("无法解码文本文件")


def parse_pdf(content: bytes) -> str:
    import io

    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    text = "\n".join(parts).strip()
    if not text:
        raise ParseError("无法从扫描件提取文字，请上传可复制 PDF 或改用文本输入")
    return text


def parse_docx(content: bytes) -> str:
    import io

    doc = Document(io.BytesIO(content))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(parts).strip()
    if not text:
        raise ParseError("文档内容为空")
    return text


def parse_file(filename: str, content: bytes) -> str:
    max_mb = load_config().get("upload", {}).get("max_size_mb", 10)
    if len(content) > max_mb * 1024 * 1024:
        raise ParseError(f"文件超过 {max_mb}MB 限制")

    ext = _allowed_ext(filename)
    if ext == "txt":
        return parse_txt(content)
    if ext == "pdf":
        return parse_pdf(content)
    if ext == "docx":
        return parse_docx(content)
    raise ParseError("不支持的文件格式")


def save_upload(filename: str, content: bytes) -> tuple[str, str]:
    text = parse_file(filename, content)
    file_id = f"tmp_{uuid.uuid4().hex[:12]}"
    meta_path = TMP_DIR / f"{file_id}.json"
    from app.services.storage import save_json

    save_json(
        meta_path,
        {"file_id": file_id, "file_name": filename, "text": text, "char_count": len(text)},
    )
    return file_id, text
