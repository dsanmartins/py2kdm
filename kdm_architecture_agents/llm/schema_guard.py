from __future__ import annotations

from typing import Any


class LLMSchemaGuard:
    """
    Lightweight validation and normalization for LLM suggestion payloads.

    The guard accepts small variations in LLM output, but normalizes the final
    suggestion structure so downstream tools and the GUI can consume it.
    """

    REQUIRED_SUGGESTION_FIELDS = {"suggestion_type", "message"}

    def normalize_suggestions(
        self,
        payload: dict[str, Any],
        source: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        warnings = []
        raw_suggestions = payload.get("suggestions", [])

        if raw_suggestions is None:
            raw_suggestions = []

        if not isinstance(raw_suggestions, list):
            return [], ["LLM payload field 'suggestions' is not a list."]

        suggestions = []

        for index, item in enumerate(raw_suggestions):
            if not isinstance(item, dict):
                warnings.append(f"Suggestion at index {index} is not an object.")
                continue

            missing = sorted(
                field for field in self.REQUIRED_SUGGESTION_FIELDS
                if not item.get(field)
            )

            if missing:
                warnings.append(
                    f"Suggestion at index {index} is missing required field(s): "
                    + ", ".join(missing)
                )
                continue

            normalized = dict(item)
            normalized.setdefault("id", f"llm_suggestion:{index}")
            normalized.setdefault("status", "needs_review")
            normalized.setdefault("source", source)
            normalized.setdefault("severity", "info")
            normalized.setdefault("confidence", 0.50)
            normalized.setdefault("affected_elements", [])
            normalized.setdefault("evidence", [])
            normalized.setdefault("proposed_changes", [])
            normalized.setdefault("metadata", {})

            confidence = normalized.get("confidence")

            if not isinstance(confidence, (int, float)):
                normalized["confidence"] = 0.50
            else:
                normalized["confidence"] = max(0.0, min(1.0, float(confidence)))

            normalized["affected_elements"] = self._ensure_list(
                normalized.get("affected_elements")
            )
            normalized["evidence"] = self._ensure_string_list(
                normalized.get("evidence")
            )

            proposed_changes, proposed_change_warnings = self._normalize_proposed_changes(
                raw_changes=normalized.get("proposed_changes"),
                suggestion=normalized,
                index=index,
            )
            normalized["proposed_changes"] = proposed_changes
            warnings.extend(proposed_change_warnings)

            if not isinstance(normalized.get("metadata"), dict):
                normalized["metadata"] = {
                    "raw_metadata": normalized.get("metadata")
                }

            suggestions.append(normalized)

        return suggestions, warnings

    def _normalize_proposed_changes(
        self,
        raw_changes: Any,
        suggestion: dict[str, Any],
        index: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        warnings = []

        if raw_changes is None:
            return [], warnings

        if not isinstance(raw_changes, list):
            raw_changes = [raw_changes]
            warnings.append(
                f"Suggestion at index {index} had non-list proposed_changes; "
                "it was wrapped as a list."
            )

        normalized_changes = []

        for change_index, change in enumerate(raw_changes):
            if isinstance(change, dict):
                normalized = dict(change)
                normalized.setdefault("status", suggestion.get("status", "needs_review"))
                normalized.setdefault("source_agent", "LLMArchitectureReasoningAgent")
                normalized_changes.append(normalized)
                continue

            if isinstance(change, str):
                normalized_changes.append(
                    self._string_change_to_object(
                        change=change,
                        suggestion=suggestion,
                    )
                )
                warnings.append(
                    f"Suggestion at index {index} proposed_changes[{change_index}] "
                    "was a string and was normalized to an object."
                )
                continue

            normalized_changes.append(
                {
                    "operation": "review_textual_change",
                    "description": str(change),
                    "status": suggestion.get("status", "needs_review"),
                    "source_agent": "LLMArchitectureReasoningAgent",
                }
            )
            warnings.append(
                f"Suggestion at index {index} proposed_changes[{change_index}] "
                "was not an object and was normalized to a textual object."
            )

        return normalized_changes, warnings

    def _string_change_to_object(
        self,
        change: str,
        suggestion: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Converts common textual LLM changes into structured review operations.

        This is intentionally conservative. It does not apply changes; it only
        creates a GUI-friendly object.
        """

        text = change.strip()
        lowered = text.lower()

        affected_elements = suggestion.get("affected_elements", [])
        target = affected_elements[0] if affected_elements else None

        if "analyzer" in lowered and (
            "add" in lowered
            or "new component" in lowered
            or "component" in lowered
        ):
            return {
                "operation": "optional_add_component",
                "role": "Analyzer",
                "target": target,
                "status": suggestion.get("status", "needs_review"),
                "source_agent": "LLMArchitectureReasoningAgent",
                "description": text,
            }

        if "reference input" in lowered and (
            "add" in lowered
            or "component" in lowered
        ):
            return {
                "operation": "optional_add_component",
                "role": "ReferenceInput",
                "target": target,
                "status": suggestion.get("status", "needs_review"),
                "source_agent": "LLMArchitectureReasoningAgent",
                "description": text,
            }

        if "measured output" in lowered and (
            "add" in lowered
            or "component" in lowered
        ):
            return {
                "operation": "optional_add_component",
                "role": "MeasuredOutput",
                "target": target,
                "status": suggestion.get("status", "needs_review"),
                "source_agent": "LLMArchitectureReasoningAgent",
                "description": text,
            }

        return {
            "operation": "review_textual_change",
            "description": text,
            "target": target,
            "status": suggestion.get("status", "needs_review"),
            "source_agent": "LLMArchitectureReasoningAgent",
        }

    def _ensure_list(self, value: Any) -> list[Any]:
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _ensure_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            return [str(item) for item in value]

        return [str(value)]
