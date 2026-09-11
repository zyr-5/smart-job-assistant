import json
from pathlib import Path
from typing import Any

from app.config import CONFIG_FILE


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config() -> dict:
    default = {
        "schema_version": "1.0",
        "match": {
            "missing_info_default_score": 50,
            "level_thresholds": {"high": 80, "medium": 50},
        },
        "interview": {"questions_per_type": 4},
        "company": {
            "cache_ttl_days": 3,
            "search_language": "zh",
            "search_results_per_query": 5,
            "research_timeout_seconds": 150,
            "max_page_fetches": 3,
            "page_fetch_timeout_seconds": 5,
        },
        "upload": {"max_size_mb": 10, "allowed_extensions": ["pdf", "docx", "txt"]},
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "temperature_match": 0.3,
            "temperature_company": 0.3,
            "temperature_interview": 0.5,
            "timeout_seconds": 120,
            "max_retries": 1,
        },
    }
    if not CONFIG_FILE.exists():
        save_json(CONFIG_FILE, default)
        return default
    return load_json(CONFIG_FILE, default)
