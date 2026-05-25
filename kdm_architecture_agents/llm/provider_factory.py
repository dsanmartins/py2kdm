from __future__ import annotations

from kdm_architecture_agents.llm.null_provider import NullLLMProvider
from kdm_architecture_agents.llm.ollama_provider import OllamaLLMProvider
from kdm_architecture_agents.llm.gemini_provider import GeminiLLMProvider


def create_llm_provider(
    provider_name: str = "none",
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: int | None = None,
):
    provider_name = (provider_name or "none").lower()

    if provider_name == "none":
        return NullLLMProvider()

    if provider_name == "ollama":
        return OllamaLLMProvider(
            model=model or "qwen2.5-coder:7b",
            base_url=base_url or "http://localhost:11434",
            timeout_seconds=timeout_seconds or 300,
        )

    if provider_name == "gemini":
        return GeminiLLMProvider(
            model=model or "gemini-2.5-flash-lite",
        )

    raise ValueError(f"Unsupported LLM provider: {provider_name}")
