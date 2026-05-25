from __future__ import annotations

import json
from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AISuggestion
from kdm_architecture_agents.llm.schema_guard import LLMSchemaGuard


class LLMArchitectureReasoningAgent:
    """
    Optional pre-review LLM agent.

    The agent never modifies structure_model directly. It only produces
    reviewable suggestions.
    """

    def __init__(self, provider):
        self.provider = provider
        self.guard = LLMSchemaGuard()

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if getattr(self.provider, "name", "none") == "none":
            return [
                AISuggestion(
                    suggestion_type="llm_disabled",
                    message=(
                        "LLM-assisted reasoning is disabled. The pipeline is "
                        "running in deterministic/offline mode."
                    ),
                    confidence=1.0,
                    status="informational",
                    source="llm_disabled",
                    severity="info",
                ).to_dict()
            ]

        prompt = self._build_prompt(context)
        payload = self.provider.complete_json(prompt=prompt, schema=None)

        suggestions, warnings = self.guard.normalize_suggestions(
            payload=payload,
            source=f"llm_assisted_enrichment:{getattr(self.provider, 'name', 'unknown')}",
        )

        for warning in warnings:
            suggestions.append(
                AISuggestion(
                    suggestion_type="llm_output_warning",
                    message=warning,
                    confidence=1.0,
                    status="ai_warning",
                    source="llm_schema_guard",
                    severity="warning",
                    metadata={
                        "provider": getattr(self.provider, "name", "unknown"),
                    },
                ).to_dict()
            )

        if payload.get("error"):
            suggestions.append(
                AISuggestion(
                    suggestion_type="llm_provider_error",
                    message=str(payload.get("error")),
                    confidence=1.0,
                    status="ai_warning",
                    source=f"llm_provider:{getattr(self.provider, 'name', 'unknown')}",
                    severity="warning",
                    metadata={
                        "provider_payload": payload,
                    },
                ).to_dict()
            )

        return suggestions

    def _build_prompt(self, context):
        compact_context = {
            "projectName": context.get("projectName"),
            "language": context.get("language"),
            "loop_summaries": context.get("loop_summaries", []),
            "runtime_summary": self._compact_runtime_summary(
                context.get("runtime_summary", {})
            ),
            "components": [
                {
                    "id": component.get("id"),
                    "name": component.get("name"),
                    "role": component.get("role"),
                    "implemented_by": component.get("implemented_by", []),
                    "confidence": component.get("confidence"),
                    "evidence": component.get("evidence", []),
                }
                for component in context.get("components", [])
            ],
            "relationships": [
                {
                    "id": relationship.get("id"),
                    "source": relationship.get("source"),
                    "target": relationship.get("target"),
                    "type": relationship.get("type"),
                    "confidence": relationship.get("confidence"),
                }
                for relationship in context.get("relationships", [])
            ],
        }

        required_format = {
            "suggestions": [
                {
                    "suggestion_type": "missing_abstraction",
                    "message": "Explain the reviewable suggestion.",
                    "confidence": 0.65,
                    "status": "needs_review",
                    "severity": "warning",
                    "affected_elements": [],
                    "evidence": [],
                    "proposed_changes": [],
                }
            ]
        }

        return (
            "You are assisting the py2kdm architecture recovery pipeline.\n"
            "The input is an architecture proposal for a self-adaptive MAPE-K system.\n"
            "The context may include runtime evidence summarized from "
            "relationships[type='runtime_calls']; such evidence was generated "
            "from execution traces and mapped to native KDM action::Calls.\n\n"
            "Rules:\n"
            "- Suggest only reviewable improvements.\n"
            "- Do not modify the architecture directly.\n"
            "- Do not invent explicit code evidence.\n"
            "- Use runtime_summary only as supporting evidence; do not claim "
            "that it proves behavior not present in the summary.\n"
            "- Use status needs_review for uncertain suggestions.\n"
            "- Return JSON only.\n\n"
            "Required output format:\n"
            f"{json.dumps(required_format, indent=2)}\n\n"
            "Architecture context:\n"
            f"{json.dumps(compact_context, indent=2, ensure_ascii=False)}"
        )

    def _compact_runtime_summary(self, runtime_summary: dict[str, Any]):
        if not runtime_summary:
            return {
                "available": False,
                "total_runtime_calls": 0,
            }

        return {
            "available": runtime_summary.get("available", False),
            "total_runtime_calls": runtime_summary.get("total_runtime_calls", 0),
            "runtime_calls_by_scenario": runtime_summary.get(
                "runtime_calls_by_scenario", {}
            ),
            "top_sources": runtime_summary.get("top_sources", [])[:10],
            "top_targets": runtime_summary.get("top_targets", [])[:10],
            "top_component_pairs": runtime_summary.get("top_component_pairs", [])[:10],
            "runtime_calls_unmapped_to_components": runtime_summary.get(
                "runtime_calls_unmapped_to_components", 0
            ),
            "runtime_enrichment_summary": runtime_summary.get(
                "runtime_enrichment_summary", {}
            ),
        }
