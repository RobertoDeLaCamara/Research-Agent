# src/llm.py — LLM factory
#
# Returns the right LangChain chat model based on environment config:
#
#   Local Ollama (default):
#     OLLAMA_BASE_URL=http://localhost:11434
#     OLLAMA_MODEL=qwen2.5:1.5b
#
#   Any OpenAI-compatible API (Groq, Gemini, OpenRouter, LM Studio, Together…):
#     OPENAI_API_KEY=<your-key>
#     OLLAMA_BASE_URL=https://api.groq.com/openai/v1   # or any endpoint
#     OLLAMA_MODEL=llama-3.3-70b-versatile             # or any model name
#
# Free options that work out of the box:
#   Groq      → https://console.groq.com  (llama-3.1-8b-instant, free tier)
#   Gemini    → https://aistudio.google.com (gemini-1.5-flash, free tier)
#   Cerebras  → https://cloud.cerebras.ai  (llama-3.1-8b, free tier)
#   OpenRouter→ https://openrouter.ai      (many free models)

import logging
import os
from .config import settings
from .credentials import get_credential

logger = logging.getLogger(__name__)

# Known OpenAI-compatible base URLs — used to detect cloud mode automatically
_CLOUD_URL_FRAGMENTS = (
    "api.groq.com",
    "generativelanguage.googleapis.com",
    "api.openai.com",
    "openrouter.ai",
    "api.together.xyz",
    "api.cerebras.ai",
    "api.mistral.ai",
)


def _is_cloud_endpoint(base_url: str) -> bool:
    """True when the base URL is a cloud API (not local Ollama)."""
    return any(frag in base_url.lower() for frag in _CLOUD_URL_FRAGMENTS)


def _approx_token_ids(text: str) -> list:
    """Cheap token-count stand-in for ChatOllama.

    ChatOllama has no tokenizer, so LangChain's get_num_tokens() falls back to
    the GPT-2 tokenizer from `transformers` (not installed -> ImportError, e.g.
    in the map_reduce summarize chain). Callers only use the count for size
    thresholds, so ~3 chars/token is enough; it deliberately overestimates for
    English/Spanish so chunks get collapsed early rather than overflow num_ctx.
    """
    return [0] * (len(text) // 3 + 1)


def get_llm(temperature: float = 0, timeout: int = None, tier: str = "heavy", **extra_kwargs):
    """
    Return a LangChain chat model configured from environment variables.

    Resolved at call time through ``get_credential`` so the keys and model a
    visitor entered in the UI apply to their run only (see src/credentials.py).

    Extra keyword arguments (repeat_penalty, num_predict, stop, etc.) are
    forwarded to the underlying ChatOllama / ChatOpenAI constructor.

    ``tier`` selects the hybrid routing. "heavy" (default) is the configured
    main backend (e.g. an OpenAI-compatible cloud API). "light" is for cheap, verifiable steps
    (query expansion, source routing, summarising) and goes to a local Ollama
    model when LIGHT_LLM_MODEL is set (LIGHT_LLM_BASE_URL, default
    http://localhost:11434). With LIGHT_LLM_MODEL unset, "light" behaves
    exactly like "heavy", so the feature is opt-in.
    """
    t = timeout or settings.llm_request_timeout

    if tier == "light":
        light_model = os.environ.get("LIGHT_LLM_MODEL")
        if light_model:
            light_url = os.environ.get("LIGHT_LLM_BASE_URL") or "http://localhost:11434"
            logger.debug(f"LLM: light tier -> ChatOllama base_url={light_url} model={light_model}")
            return _build_ollama(light_url, light_model, temperature, t, extra_kwargs)

    # Per-run overrides (keys/model a visitor entered in the UI) win over the server config
    api_key = get_credential("OPENAI_API_KEY")
    base_url = get_credential("OLLAMA_BASE_URL")
    model = get_credential("OLLAMA_MODEL")

    if api_key or _is_cloud_endpoint(base_url):
        from langchain_openai import ChatOpenAI

        if base_url == "http://localhost:11434":
            base_url = "https://api.openai.com/v1"

        logger.debug(f"LLM: ChatOpenAI base_url={base_url} model={model}")
        return ChatOpenAI(
            api_key=api_key or "ollama",
            base_url=base_url,
            model=model,
            temperature=temperature,
            timeout=t,
            **extra_kwargs,
        )

    else:
        return _build_ollama(base_url, model, temperature, t, extra_kwargs)


def _build_ollama(base_url, model, temperature, t, extra_kwargs):
    """Build a ChatOllama client (shared by the heavy and light tiers)."""
    from langchain_ollama import ChatOllama

    # ChatOllama has no `request_timeout` field and silently drops it;
    # the timeout must go to the underlying httpx client via client_kwargs.
    extra_kwargs.setdefault("client_kwargs", {"timeout": t})
    # Thinking models (qwen3.x) can spend minutes in the reasoning phase,
    # and since langchain-ollama streams internally the httpx timeout
    # never fires. Off by default; set OLLAMA_REASONING=true to enable.
    extra_kwargs.setdefault(
        "reasoning", os.environ.get("OLLAMA_REASONING", "false").lower() == "true"
    )
    extra_kwargs.setdefault("custom_get_token_ids", _approx_token_ids)

    logger.debug(f"LLM: ChatOllama base_url={base_url} model={model}")
    return ChatOllama(
        base_url=base_url,
        model=model,
        temperature=temperature,
        **extra_kwargs,
    )


def invoke_light(messages, temperature: float = 0, timeout: int = None):
    """Invoke the light tier; if it fails and a separate light model is configured, retry on heavy.

    With LIGHT_LLM_MODEL unset the light tier already is the heavy backend, so the error propagates.
    """
    try:
        return get_llm(temperature=temperature, timeout=timeout, tier="light").invoke(messages)
    except Exception as light_err:
        if not os.environ.get("LIGHT_LLM_MODEL"):
            raise
        logger.warning(f"Light LLM failed ({light_err}); falling back to heavy tier")
        return get_llm(temperature=temperature, timeout=timeout, tier="heavy").invoke(messages)
