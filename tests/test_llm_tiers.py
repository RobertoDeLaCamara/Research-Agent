"""Hybrid LLM routing: the 'light' tier goes to local Ollama only when opted in."""
import pytest

from src import llm as llm_mod

CLOUD_URL = "https://api.groq.com/openai/v1"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("LIGHT_LLM_MODEL", "LIGHT_LLM_BASE_URL", "OPENAI_API_KEY",
              "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm_mod.settings, "openai_api_key", None, raising=False)


def _cloud_heavy(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", CLOUD_URL)
    monkeypatch.setenv("OLLAMA_MODEL", "llama-3.3-70b-versatile")


def test_light_tier_uses_local_ollama_even_when_heavy_is_cloud(monkeypatch):
    _cloud_heavy(monkeypatch)
    monkeypatch.setenv("LIGHT_LLM_MODEL", "gpt-oss:20b")
    monkeypatch.setenv("LIGHT_LLM_BASE_URL", "http://host.docker.internal:11434")
    light = llm_mod.get_llm(tier="light")
    assert type(light).__name__ == "ChatOllama"
    assert light.model == "gpt-oss:20b"
    assert light.base_url == "http://host.docker.internal:11434"


def test_heavy_tier_still_uses_cloud(monkeypatch):
    _cloud_heavy(monkeypatch)
    monkeypatch.setenv("LIGHT_LLM_MODEL", "gpt-oss:20b")
    heavy = llm_mod.get_llm()
    assert type(heavy).__name__ == "ChatOpenAI"
    assert heavy.model_name == "llama-3.3-70b-versatile"


def test_light_tier_is_opt_in(monkeypatch):
    _cloud_heavy(monkeypatch)
    light = llm_mod.get_llm(tier="light")  # LIGHT_LLM_MODEL unset -> same as heavy
    assert type(light).__name__ == "ChatOpenAI"


def test_light_tier_default_url(monkeypatch):
    monkeypatch.setenv("LIGHT_LLM_MODEL", "qwen3.5:9b")
    light = llm_mod.get_llm(tier="light")
    assert light.base_url == "http://localhost:11434"
