from __future__ import annotations

from copy import deepcopy
from typing import Any


class SuggestionDeduplicator:
    """
    Deduplicates semantically equivalent architecture suggestions.

    Deterministic suggestions are kept as the primary suggestion. LLM
    suggestions that overlap with deterministic ones are merged as supporting
    evidence instead of being exposed as separate duplicate suggestions.
    """

    LLM_SOURCE_PREFIXES = (
        "llm_assisted_enrichment",
        "llm_provider",
    )

    NON_MERGEABLE_SOURCE_PREFIXES = (
        "llm_schema_guard",
    )

    def deduplicate(self, suggestions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        index: dict[tuple[Any, ...], int] = {}

        for suggestion in suggestions:
            normalized = deepcopy(suggestion)
            key = self._dedup_key(normalized)

            if key is None:
                result.append(normalized)
                continue

            if key not in index:
                index[key] = len(result)
                result.append(normalized)
                continue

            existing = result[index[key]]
            result[index[key]] = self._merge(existing, normalized)

        return result

    def _dedup_key(self, suggestion: dict[str, Any]):
        source = suggestion.get("source", "")

        if source.startswith(self.NON_MERGEABLE_SOURCE_PREFIXES):
            return None

        affected = tuple(sorted(str(item) for item in suggestion.get("affected_elements", []) or []))
        changes = suggestion.get("proposed_changes", []) or []

        operation_keys = []

        for change in changes:
            if not isinstance(change, dict):
                continue

            operation_keys.append(
                (
                    change.get("operation"),
                    change.get("relationship_type"),
                    change.get("role"),
                    change.get("source"),
                    change.get("target"),
                    change.get("implementation"),
                )
            )

        operation_keys = tuple(sorted(operation_keys))

        suggestion_type = suggestion.get("suggestion_type")

        if affected and operation_keys:
            return ("affected+operations", affected, operation_keys)

        if self._is_missing_role_suggestion(suggestion, role="Analyzer"):
            target = self._first_affected_or_target(suggestion)
            return ("missing_role", "Analyzer", target)

        if self._is_missing_role_suggestion(suggestion, role="ReferenceInput"):
            target = self._first_affected_or_target(suggestion)
            return ("missing_role", "ReferenceInput", target)

        if self._is_missing_role_suggestion(suggestion, role="MeasuredOutput"):
            target = self._first_affected_or_target(suggestion)
            return ("missing_role", "MeasuredOutput", target)

        if suggestion_type and affected:
            return ("type+affected", suggestion_type, affected)

        return None

    def _merge(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        existing_is_llm = self._is_llm_suggestion(existing)
        incoming_is_llm = self._is_llm_suggestion(incoming)

        if existing_is_llm and not incoming_is_llm:
            primary = deepcopy(incoming)
            secondary = existing
        else:
            primary = existing
            secondary = incoming

        metadata = primary.setdefault("metadata", {})
        metadata.setdefault("merged_duplicates", [])
        metadata.setdefault("merged_sources", [])
        metadata.setdefault("supporting_messages", [])

        metadata["merged_duplicates"].append(
            {
                "id": secondary.get("id"),
                "source": secondary.get("source"),
                "suggestion_type": secondary.get("suggestion_type"),
                "confidence": secondary.get("confidence"),
                "status": secondary.get("status"),
            }
        )

        source = secondary.get("source")

        if source and source not in metadata["merged_sources"]:
            metadata["merged_sources"].append(source)

        message = secondary.get("message")

        if message and message not in metadata["supporting_messages"]:
            metadata["supporting_messages"].append(message)

        primary["confidence"] = max(
            float(primary.get("confidence", 0.0) or 0.0),
            float(secondary.get("confidence", 0.0) or 0.0),
        )

        primary["evidence"] = self._merge_lists(
            primary.get("evidence", []),
            secondary.get("evidence", []),
        )

        primary["affected_elements"] = self._merge_lists(
            primary.get("affected_elements", []),
            secondary.get("affected_elements", []),
        )

        primary["proposed_changes"] = self._merge_proposed_changes(
            primary.get("proposed_changes", []),
            secondary.get("proposed_changes", []),
        )

        return primary

    def _merge_lists(self, left, right):
        result = []
        seen = set()

        for item in (left or []) + (right or []):
            marker = self._stable_marker(item)

            if marker in seen:
                continue

            seen.add(marker)
            result.append(item)

        return result

    def _merge_proposed_changes(self, left, right):
        result = []
        seen = set()

        for change in (left or []) + (right or []):
            marker = self._stable_marker(change)

            if marker in seen:
                continue

            seen.add(marker)
            result.append(change)

        return result

    def _stable_marker(self, value):
        if isinstance(value, dict):
            return tuple(sorted((key, self._stable_marker(item)) for key, item in value.items()))

        if isinstance(value, list):
            return tuple(self._stable_marker(item) for item in value)

        return value

    def _is_llm_suggestion(self, suggestion: dict[str, Any]) -> bool:
        source = suggestion.get("source", "")
        return source.startswith(self.LLM_SOURCE_PREFIXES)

    def _is_missing_role_suggestion(self, suggestion: dict[str, Any], role: str) -> bool:
        message = str(suggestion.get("message", "")).lower()
        role_lower = role.lower()

        if role_lower not in message:
            return False

        if "missing" in message or "no explicit" in message or "not recovered" in message:
            return True

        for change in suggestion.get("proposed_changes", []) or []:
            if not isinstance(change, dict):
                continue

            if change.get("role") == role:
                return True

            missing_roles = change.get("missing_roles", [])

            if role in missing_roles:
                return True

        return False

    def _first_affected_or_target(self, suggestion: dict[str, Any]):
        affected = suggestion.get("affected_elements", []) or []

        if affected:
            return affected[0]

        for change in suggestion.get("proposed_changes", []) or []:
            if not isinstance(change, dict):
                continue

            target = change.get("target")

            if target:
                return target

        return None
