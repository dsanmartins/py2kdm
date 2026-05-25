from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AISuggestion


class DynamicEvidenceAgent:
    """
    Pre-review agent for dynamic evidence.

    The agent is now runtime-enriched-model aware. It first reads
    relationships[type="runtime_calls"] from the input JSON. If those are not
    available, it can still consume a raw dynamic trace JSON through
    --dynamic-trace for backwards compatibility.

    The agent does not modify structure_model. It only produces reviewable
    architecture suggestions.
    """

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
        trace_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        runtime_relationships = [
            relationship
            for relationship in model.get("relationships", [])
            if relationship.get("type") == "runtime_calls"
        ]

        if runtime_relationships:
            return self._suggest_from_runtime_relationships(
                context=context,
                runtime_relationships=runtime_relationships,
                source_label="runtime_enriched_model",
            )

        if not trace_path:
            return [
                AISuggestion(
                    suggestion_type="dynamic_evidence_not_available",
                    message=(
                        "No runtime_calls relationships or dynamic trace were "
                        "provided. Dynamic evidence enrichment was skipped."
                    ),
                    confidence=1.0,
                    status="informational",
                    source="dynamic_evidence",
                    severity="info",
                    evidence=[
                        "DynamicEvidenceAgent can use "
                        "relationships[type='runtime_calls'] from the model "
                        "or an optional trace JSON."
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
        runtime_relationships = []

        for event in trace.get("events", []):
            if event.get("type") != "call":
                continue

            runtime_relationships.append(
                {
                    "source": event.get("source"),
                    "target": event.get("target"),
                    "scenario": event.get("scenario", "unknown_scenario"),
                    "type": "runtime_calls",
                }
            )

        return self._suggest_from_runtime_relationships(
            context=context,
            runtime_relationships=runtime_relationships,
            source_label="dynamic_trace",
        )

    def _suggest_from_runtime_relationships(
        self,
        context: dict[str, Any],
        runtime_relationships: list[dict[str, Any]],
        source_label: str,
    ) -> list[dict[str, Any]]:
        suggestions = []
        implementation_to_components = context.get(
            "components_by_implementation", {}
        )

        seen = set()

        for relationship in runtime_relationships:
            source_impl = relationship.get("source")
            target_impl = relationship.get("target")
            scenario = relationship.get("scenario", "unknown_scenario")

            source_components = self._find_components_for_runtime_name(
                source_impl,
                implementation_to_components,
            )
            target_components = self._find_components_for_runtime_name(
                target_impl,
                implementation_to_components,
            )

            for source_component in source_components:
                for target_component in target_components:
                    relationship_type = self._relationship_type(
                        source_component.get("role"),
                        target_component.get("role"),
                    )

                    if not relationship_type:
                        continue

                    key = (
                        relationship_type,
                        source_component.get("id"),
                        target_component.get("id"),
                        scenario,
                    )

                    if key in seen:
                        continue

                    seen.add(key)

                    suggestions.append(
                        AISuggestion(
                            suggestion_type="dynamic_relation",
                            message=(
                                f"Runtime evidence suggests "
                                f"{source_component.get('name')} "
                                f"--{relationship_type}--> "
                                f"{target_component.get('name')}."
                            ),
                            confidence=0.90,
                            status="needs_review",
                            source=f"dynamic_evidence:{source_label}",
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

        if not suggestions:
            runtime_summary = context.get("runtime_summary", {})
            total = runtime_summary.get("total_runtime_calls", len(runtime_relationships))

            return [
                AISuggestion(
                    suggestion_type="dynamic_evidence_available",
                    message=(
                        f"Runtime evidence is available ({total} runtime "
                        "calls), but no direct architecture-level relation "
                        "suggestion matched the current component roles."
                    ),
                    confidence=1.0,
                    status="informational",
                    source=f"dynamic_evidence:{source_label}",
                    severity="info",
                    evidence=[
                        "Runtime calls were used as context for later "
                        "architecture reasoning and LLM-assisted suggestions."
                    ],
                ).to_dict()
            ]

        return suggestions

    def _find_components_for_runtime_name(
        self,
        runtime_name: str | None,
        implementation_index: dict,
    ) -> list[dict[str, Any]]:
        if not runtime_name:
            return []

        if runtime_name in implementation_index:
            return implementation_index[runtime_name]

        normalized_runtime_name = self._normalize(runtime_name)
        matches = []

        for implementation, components in implementation_index.items():
            normalized_implementation = self._normalize(implementation)

            if normalized_implementation == normalized_runtime_name:
                matches.extend(components)
                continue

            if normalized_runtime_name.endswith("." + normalized_implementation):
                matches.extend(components)
                continue

            if normalized_implementation.endswith("." + normalized_runtime_name):
                matches.extend(components)
                continue

            runtime_parts = normalized_runtime_name.split(".")
            implementation_parts = normalized_implementation.split(".")

            if len(runtime_parts) >= 2 and len(implementation_parts) >= 2:
                if runtime_parts[-2:] == implementation_parts[-2:]:
                    matches.extend(components)

        seen = set()
        unique = []

        for component in matches:
            component_id = component.get("id")

            if component_id in seen:
                continue

            seen.add(component_id)
            unique.append(component)

        return unique

    def _normalize(self, name: str) -> str:
        return (
            str(name)
            .replace("-", "_")
            .replace("/", ".")
            .replace("\\", ".")
        )

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
