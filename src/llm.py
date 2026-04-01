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


def get_llm(temperature: float = 0, timeout: int = None):
    """
    Return a LangChain chat model configured from environment variables.

    Reads os.environ at call time so runtime overrides (e.g. from the
    HF Spaces sidebar key input) take effect without restarting the process.
    """
    t = timeout or settings.llm_request_timeout

    # Read live env vars so runtime sidebar overrides work
    api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    base_url = os.environ.get("OLLAMA_BASE_URL") or settings.ollama_base_url
    model = os.environ.get("OLLAMA_MODEL") or settings.ollama_model

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
        )

    else:
        from langchain_ollama import ChatOllama

        logger.debug(f"LLM: ChatOllama base_url={base_url} model={model}")
        return ChatOllama(
            base_url=base_url,
            model=model,
            temperature=temperature,
            request_timeout=t,
        )
