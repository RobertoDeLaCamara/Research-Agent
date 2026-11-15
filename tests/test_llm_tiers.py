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


# ── Ollama-style kwargs on an OpenAI-compatible backend ──────────────────────────────────
SYNTHESIS_KWARGS = dict(repeat_penalty=1.15, num_predict=6144, num_ctx=16384, stop=["</report>"])


def _payload(llm):
    from langchain_core.messages import HumanMessage
    return llm._get_request_payload([HumanMessage(content="x")])


def test_ollama_only_kwargs_never_reach_an_openai_compatible_api(monkeypatch):
    _cloud_heavy(monkeypatch)
    p = _payload(llm_mod.get_llm(temperature=0.4, **SYNTHESIS_KWARGS))
    for k in ("num_ctx", "num_predict", "repeat_penalty"):
        assert k not in p
    assert p["stop"] == ["</report>"]


def test_compatible_apis_get_the_classic_max_tokens_field(monkeypatch):
    """Groq/Gemini/DeepSeek...: max_completion_tokens may be ignored (DeepSeek did), max_tokens is not."""
    _cloud_heavy(monkeypatch)
    p = _payload(llm_mod.get_llm(**SYNTHESIS_KWARGS))
    assert p["extra_body"]["max_tokens"] == 6144
    assert "max_completion_tokens" not in p


def test_openai_gets_max_completion_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OLLAMA_MODEL", "gpt-4o-mini")
    p = _payload(llm_mod.get_llm(**SYNTHESIS_KWARGS))
    assert p["max_completion_tokens"] == 6144
    assert "extra_body" not in p and "num_ctx" not in p


def test_ollama_backend_still_gets_its_own_kwargs(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm = llm_mod.get_llm(**SYNTHESIS_KWARGS)
    assert type(llm).__name__ == "ChatOllama"
    assert llm.num_predict == 6144 and llm.num_ctx == 16384 and llm.repeat_penalty == 1.15
