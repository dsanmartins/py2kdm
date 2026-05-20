from __future__ import annotations

from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AISuggestion


class ArchitectureEnrichmentAgent:
    """
    Pre-review agent that inspects the rule-based architecture proposal and
    generates non-invasive suggestions.

    It does not modify the architecture directly. It adds suggestions for the
    GUI or for a later review step.
    """

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        suggestions = []

        suggestions.extend(self._suggest_missing_abstractions(context))
        suggestions.extend(self._suggest_role_disambiguation(context))
        suggestions.extend(self._suggest_partial_loop_interpretation(context))

        return suggestions

    def _suggest_missing_abstractions(self, context):
        suggestions = []

        role_index = context.get("components_by_role", {})

        required_roles = [
            ("ReferenceInput", "Reference Input"),
            ("MeasuredOutput", "Measured Output"),
            ("Sensor", "Sensor"),
        ]

        for role, label in required_roles:
            if role_index.get(role):
                continue

            suggestions.append(
                AISuggestion(
                    suggestion_type="missing_abstraction",
                    message=(
                        f"No {label} was recovered. This may be acceptable if "
                        "the code does not expose explicit evidence, but the "
                        "reviewer may decide whether the abstraction should be "
                        "added manually."
                    ),
                    confidence=0.70,
                    status="needs_review",
                    source="ai_assisted_enrichment",
                    severity="warning",
                    proposed_changes=[
                        {
                            "operation": "optional_add_component",
                            "role": role,
                            "stereotype_name": label,
                            "status": "needs_review",
                        }
                    ],
                    evidence=[
                        (
                            f"The architecture contains no materialized "
                            f"component with role {role}."
                        )
                    ],
                ).to_dict()
            )

        return suggestions

    def _suggest_role_disambiguation(self, context):
        suggestions = []

        for implementation, components in context.get(
            "components_by_implementation", {}
        ).items():
            roles = sorted(
                {
                    component.get("role")
                    for component in components
                    if component.get("role")
                }
            )

            if len(roles) <= 1:
                continue

            affected = [component.get("id") for component in components]

            suggestions.append(
                AISuggestion(
                    suggestion_type="role_disambiguation",
                    message=(
                        f"Code element {implementation} implements multiple "
                        f"architectural roles: {', '.join(roles)}."
                    ),
                    confidence=0.75,
                    status="needs_review",
                    source="ai_assisted_enrichment",
                    severity="warning",
                    affected_elements=affected,
                    proposed_changes=[
                        {
                            "operation": "review_role_split",
                            "implementation": implementation,
                            "roles": roles,
                            "recommendation": (
                                "Keep separate architecture components if the "
                                "same code element intentionally implements "
                                "multiple responsibilities; otherwise reject "
                                "or rename one of them."
                            ),
                        }
                    ],
                    evidence=[
                        (
                            "Multiple architecture components refer to the "
                            f"same implementation id: {implementation}."
                        )
                    ],
                ).to_dict()
            )

        return suggestions

    def _suggest_partial_loop_interpretation(self, context):
        suggestions = []

        for loop in context.get("loop_summaries", []):
            missing = loop.get("missing_core_roles", [])

            if not missing:
                continue

            if missing == ["Analyzer"]:
                message = (
                    f"Control loop {loop.get('id')} has no explicit Analyzer. "
                    "This can mean that analysis is merged with Planner or "
                    "Monitor in the implementation."
                )
                recommendation = "review_analyzer_absorption"
            else:
                message = (
                    f"Control loop {loop.get('id')} is missing core MAPE "
                    f"roles: {', '.join(missing)}."
                )
                recommendation = "review_partial_control_loop"

            suggestions.append(
                AISuggestion(
                    suggestion_type="partial_control_loop",
                    message=message,
                    confidence=0.70,
                    status="needs_review",
                    source="ai_assisted_enrichment",
                    severity="warning",
                    affected_elements=[loop.get("id")],
                    proposed_changes=[
                        {
                            "operation": recommendation,
                            "missing_roles": missing,
                        }
                    ],
                    evidence=[
                        (
                            "The control loop role summary does not contain "
                            f"the following core role(s): {', '.join(missing)}."
                        )
                    ],
                ).to_dict()
            )

        return suggestions
