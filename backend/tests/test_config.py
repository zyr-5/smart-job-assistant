"""Unit tests for settings and mock/real LLM selection."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings, _env_bool

_ENV_KEYS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "MOCK_LLM",
    "COMPANY_CACHE_TTL_DAYS",
)


def _clear_llm_env() -> dict[str, str]:
    saved = {k: os.environ[k] for k in _ENV_KEYS if k in os.environ}
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    return saved


def _restore_env(saved: dict[str, str]) -> None:
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    for k, v in saved.items():
        os.environ[k] = v


def test_env_bool():
    assert _env_bool("NONEXISTENT_VAR_XYZ") is None


def test_use_mock_with_api_key_ignores_mock_llm_in_env_file():
    saved = _clear_llm_env()
    try:
        settings = Settings(deepseek_api_key="sk-test-key", mock_llm=True)
        assert settings.has_api_key
        assert settings.use_mock is False
    finally:
        _restore_env(saved)


def test_use_mock_without_key_and_mock_llm_true():
    saved = _clear_llm_env()
    try:
        os.environ["MOCK_LLM"] = "true"
        settings = Settings()
        assert not settings.has_api_key
        assert settings.use_mock is True
    finally:
        _restore_env(saved)


def test_use_mock_without_key_and_mock_llm_false():
    saved = _clear_llm_env()
    try:
        settings = Settings(mock_llm=False)
        assert not settings.has_api_key
        assert settings.use_mock is True
    finally:
        _restore_env(saved)


def test_os_env_overrides_dotenv_key():
    saved = _clear_llm_env()
    try:
        os.environ["DEEPSEEK_API_KEY"] = "sk-from-os-env"
        settings = Settings(deepseek_api_key="from-init")
        assert settings.deepseek_api_key == "sk-from-os-env"
        assert settings.use_mock is False
    finally:
        _restore_env(saved)


def test_placeholder_key_uses_mock():
    saved = _clear_llm_env()
    try:
        settings = Settings(deepseek_api_key="your_api_key_here", mock_llm=False)
        assert not settings.has_api_key
        assert settings.use_mock is True
    finally:
        _restore_env(saved)


if __name__ == "__main__":
    test_env_bool()
    test_use_mock_with_api_key_ignores_mock_llm_in_env_file()
    test_use_mock_without_key_and_mock_llm_true()
    test_use_mock_without_key_and_mock_llm_false()
    test_os_env_overrides_dotenv_key()
    test_placeholder_key_uses_mock()
    print("\n=== ALL CONFIG TESTS PASSED ===")
