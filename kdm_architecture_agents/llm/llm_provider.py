from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """
    Abstract provider for optional LLM-based architecture agents.
    """

    name = "abstract"

    @abstractmethod
    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        raise NotImplementedError
