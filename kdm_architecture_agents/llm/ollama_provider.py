from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from kdm_architecture_agents.llm.llm_provider import LLMProvider


class OllamaLLMProvider(LLMProvider):
    """
    Local LLM provider using Ollama's HTTP API.

    This provider is free to use locally and does not require a paid API key.
    It assumes that Ollama is running, for example:

        ollama serve
        ollama pull qwen2.5-coder:7b
    """

    name = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 120,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
            },
        }

        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            return {
                "provider": self.name,
                "model": self.model,
                "error": f"Could not connect to Ollama: {exc}",
                "suggestions": [],
            }

        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                "provider": self.name,
                "model": self.model,
                "error": f"Ollama returned invalid JSON envelope: {exc}",
                "raw": raw,
                "suggestions": [],
            }

        response_text = envelope.get("response", "")

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = self._extract_json_object(response_text)

        if not isinstance(parsed, dict):
            return {
                "provider": self.name,
                "model": self.model,
                "error": "Ollama response was not a JSON object.",
                "raw_response": response_text,
                "suggestions": [],
            }

        parsed.setdefault("provider", self.name)
        parsed.setdefault("model", self.model)

        return parsed

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return {
                "error": "No JSON object found in model response.",
                "raw_response": text,
                "suggestions": [],
            }

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            return {
                "error": f"Could not parse JSON object from model response: {exc}",
                "raw_response": text,
                "suggestions": [],
            }
