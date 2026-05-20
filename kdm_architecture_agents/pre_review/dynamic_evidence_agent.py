from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AISuggestion


class DynamicEvidenceAgent:
    """
    Pre-review agent for dynamic evidence.

    This first version does not execute the target system by itself. Instead,
    it can consume an optional dynamic trace JSON file. This keeps the agent
    safe and deterministic while preparing the architecture for future dynamic
    instrumentation.

    Expected trace shape:

    {
      "events": [
        {
          "type": "call",
          "source": "function:...",
          "target": "method:...",
          "scenario": "..."
        }
      ]
    }
    """

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
        trace_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        if not trace_path:
            return [
                AISuggestion(
                    suggestion_type="dynamic_evidence_not_available",
                    message=(
                        "No dynamic trace was provided. Dynamic evidence "
                        "enrichment was skipped."
                    ),
                    confidence=1.0,
                    status="informational",
                    source="dynamic_evidence",
                    severity="info",
                    evidence=[
                        "DynamicEvidenceAgent requires an optional trace JSON "
                        "to enrich relationships with runtime evidence."
                    ],
                ).to_dict()
            ]

        trace_path = Path(trace_path)

        if not trace_path.exists():
            return [
                AISuggestion(
                    suggestion_type="dynamic_evidence_missing_trace",
                    message=f"Dynamic trace file does not exist: {trace_path}",
                    confidence=1.0,
                    status="ai_warning",
                    source="dynamic_evidence",
                    severity="warning",
                ).to_dict()
            ]

        with trace_path.open("r", encoding="utf-8") as handle:
            trace = json.load(handle)

        return self._suggest_from_trace(context, trace)

    def _suggest_from_trace(
        self,
        context: dict[str, Any],
        trace: dict[str, Any],
    ) -> list[dict[str, Any]]:
        suggestions = []

        implementation_to_components = context.get(
            "components_by_implementation", {}
        )

        for event in trace.get("events", []):
            if event.get("type") != "call":
                continue

            source_impl = event.get("source")
            target_impl = event.get("target")
            scenario = event.get("scenario", "unknown_scenario")

            source_components = implementation_to_components.get(source_impl, [])
            target_components = implementation_to_components.get(target_impl, [])

            for source_component in source_components:
                for target_component in target_components:
                    relationship_type = self._relationship_type(
                        source_component.get("role"),
                        target_component.get("role"),
                    )

                    if not relationship_type:
                        continue

                    suggestions.append(
                        AISuggestion(
                            suggestion_type="dynamic_relation",
                            message=(
                                f"Runtime trace suggests "
                                f"{source_component.get('name')} "
                                f"--{relationship_type}--> "
                                f"{target_component.get('name')}."
                            ),
                            confidence=0.90,
                            status="needs_review",
                            source="dynamic_evidence",
                            severity="info",
                            affected_elements=[
                                source_component.get("id"),
                                target_component.get("id"),
                            ],
                            proposed_changes=[
                                {
                                    "operation": "add_relationship",
                                    "relationship_type": relationship_type,
                                    "source": source_component.get("id"),
                                    "target": target_component.get("id"),
                                    "relationship_level": "architectural",
                                    "status": "needs_review",
                                    "source_agent": "DynamicEvidenceAgent",
                                }
                            ],
                            evidence=[
                                (
                                    f"During scenario '{scenario}', "
                                    f"{source_impl} called {target_impl}."
                                )
                            ],
                        ).to_dict()
                    )

        return suggestions

    def _relationship_type(self, source_role, target_role):
        if source_role == "Executor" and target_role == "Effector":
            return "acts_through"

        if source_role == "Monitor" and target_role == "Sensor":
            return "observes_through"

        if source_role == "Monitor" and target_role == "MeasuredOutput":
            return "observes"

        if source_role == "Sensor" and target_role == "MeasuredOutput":
            return "produces_measurement"

        if source_role in {"Analyzer", "Planner"} and target_role == "ReferenceInput":
            return "uses_reference_input"

        if source_role in {"Analyzer", "Planner"} and target_role == "MeasuredOutput":
            return "evaluates_measured_output"

        return None
