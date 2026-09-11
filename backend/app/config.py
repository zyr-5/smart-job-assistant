import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent

_PLACEHOLDER_KEYS = frozenset({"", "your_api_key_here"})


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in ("true", "1", "yes", "on")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    company_cache_ttl_days: int = 3
    mock_llm: bool = False

    def model_post_init(self, __context: object) -> None:
        """OS environment variables take precedence over backend/.env."""
        key = os.environ.get("DEEPSEEK_API_KEY")
        if key is not None:
            self.deepseek_api_key = key

        base_url = os.environ.get("DEEPSEEK_BASE_URL")
        if base_url is not None:
            self.deepseek_base_url = base_url

        model = os.environ.get("DEEPSEEK_MODEL")
        if model is not None:
            self.deepseek_model = model

        mock_llm = _env_bool("MOCK_LLM")
        if mock_llm is not None:
            self.mock_llm = mock_llm

        ttl = os.environ.get("COMPANY_CACHE_TTL_DAYS")
        if ttl is not None:
            self.company_cache_ttl_days = int(ttl)

    @property
    def has_api_key(self) -> bool:
        return self.deepseek_api_key not in _PLACEHOLDER_KEYS

    @property
    def use_mock(self) -> bool:
        if self.has_api_key:
            return False
        return self.mock_llm or not self.has_api_key


settings = Settings()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# DATA_DIR 可由环境变量覆盖：容器/托管平台通常把持久化目录挂载到 /data 之类的路径，
# 不覆盖的话缓存与上传会写进镜像内，重启即丢失。
_data_dir_env = os.environ.get("DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir_env).expanduser() if _data_dir_env else BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
TMP_DIR = DATA_DIR / "tmp" / "uploads"
CONFIG_FILE = DATA_DIR / "config.json"

for d in [CACHE_DIR, TMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)
