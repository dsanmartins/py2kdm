from __future__ import annotations

import json
import os
from typing import Any

from kdm_architecture_agents.llm.llm_provider import LLMProvider


class GeminiLLMProvider(LLMProvider):
    """
    Gemini provider using the Google Gen AI SDK.

    Requirements:

        pip install google-genai

    API key:

        export GEMINI_API_KEY="..."
        # or
        export GOOGLE_API_KEY="..."

    The provider returns JSON-compatible dictionaries and never modifies the
    architecture model directly.
    """

    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.5-flash-lite",
        api_key: str | None = None,
    ):
        self.model = model
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )

    def complete_json(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if not self.api_key:
            return {
                "provider": self.name,
                "model": self.model,
                "error": (
                    "Missing Gemini API key. Set GEMINI_API_KEY or "
                    "GOOGLE_API_KEY in the environment."
                ),
                "suggestions": [],
            }

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            return {
                "provider": self.name,
                "model": self.model,
                "error": (
                    "Missing dependency google-genai. Install with: "
                    "pip install google-genai"
                ),
                "details": str(exc),
                "suggestions": [],
            }

        try:
            client = genai.Client(api_key=self.api_key)

            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
            )

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            response_text = response.text or ""

        except Exception as exc:
            return {
                "provider": self.name,
                "model": self.model,
                "error": f"Gemini provider error: {exc}",
                "suggestions": [],
            }

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = self._extract_json_object(response_text)

        if not isinstance(parsed, dict):
            return {
                "provider": self.name,
                "model": self.model,
                "error": "Gemini response was not a JSON object.",
                "raw_response": response_text,
                "suggestions": [],
            }

        parsed.setdefault("provider", self.name)
        parsed.setdefault("model", self.model)

        return parsed

    def _extract_json_object(self, text: str) -> dict[str, Any]:
        """
        Best-effort extraction in case the model surrounds JSON with Markdown.
        """

        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return {
                "error": "No JSON object found in Gemini response.",
                "raw_response": text,
                "suggestions": [],
            }

        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            return {
                "error": f"Could not parse JSON object from Gemini response: {exc}",
                "raw_response": text,
                "suggestions": [],
            }
