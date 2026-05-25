from __future__ import annotations

from typing import Any

from kdm_architecture_agents.llm.llm_provider import LLMProvider


class NullLLMProvider(LLMProvider):
    """
    Offline provider used when LLM support is disabled.
    """

    name = "none"

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "enabled": False,
            "provider": self.name,
            "suggestions": [],
            "message": "LLM provider is disabled.",
        }
