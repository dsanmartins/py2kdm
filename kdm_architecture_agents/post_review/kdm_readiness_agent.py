from __future__ import annotations

from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AIFinding


class KDMReadinessAgent:
    """
    Post-review agent that checks whether the reviewed JSON is ready to be
    passed to the KDM generator.
    """

    REQUIRED_TOP_LEVEL_FIELDS = {
        "projectName",
        "language",
        "files",
        "elements",
        "relationships",
    }

    VALID_ROLES = {
        "Monitor",
        "Analyzer",
        "Planner",
        "Executor",
        "Knowledge",
        "LoopManager",
        "Loop",
        "ReferenceInput",
        "MeasuredOutput",
        "Sensor",
        "Effector",
    }

    VALID_RELATIONSHIP_TYPES = {
        "contains",
        "mapek_flow",
        "uses_knowledge",
        "subscribes_to",
        "depends_on",
        "controls",
        "observes",
        "updates",
        "acts_through",
        "observes_through",
        "produces_measurement",
        "uses_reference_input",
        "evaluates_measured_output",
    }

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings = []

        findings.extend(self._check_top_level_fields(model))
        findings.extend(self._check_structure_model(model))
        findings.extend(self._check_roles(context))
        findings.extend(self._check_relationship_types(context))

        return findings

    def _check_top_level_fields(self, model):
        findings = []
        missing = sorted(
            field for field in self.REQUIRED_TOP_LEVEL_FIELDS
            if field not in model
        )

        if missing:
            findings.append(
                AIFinding(
                    finding_type="kdm_missing_required_fields",
                    message=(
                        "The reviewed JSON is missing required top-level "
                        f"field(s): {', '.join(missing)}."
                    ),
                    severity="blocking",
                    status="ai_blocking_issue",
                    recommendation=(
                        "Export the full reviewed architecture JSON, not only "
                        "review actions."
                    ),
                    metadata={"missing_fields": missing},
                ).to_dict()
            )

        return findings

    def _check_structure_model(self, model):
        if model.get("structure_model"):
            return []

        return [
            AIFinding(
                finding_type="kdm_missing_structure_model",
                message="The reviewed JSON does not contain structure_model.",
                severity="warning",
                recommendation=(
                    "KDM generation can still proceed for code-level models, "
                    "but no architecture StructureModel will be generated."
                ),
            ).to_dict()
        ]

    def _check_roles(self, context):
        findings = []

        for component in context.get("components", []):
            if component.get("materialize", True) is False:
                continue

            role = component.get("role")

            if role not in self.VALID_ROLES:
                findings.append(
                    AIFinding(
                        finding_type="kdm_invalid_architecture_role",
                        message=(
                            f"Component {component.get('id')} has invalid "
                            f"role '{role}'."
                        ),
                        severity="blocking",
                        status="ai_blocking_issue",
                        affected_elements=[component.get("id")],
                        recommendation=(
                            "Change the component role to one supported by "
                            "the Adaptive System Domain."
                        ),
                    ).to_dict()
                )

        return findings

    def _check_relationship_types(self, context):
        findings = []

        for relationship in (
            context.get("relationships", [])
            + context.get("containment_relationships", [])
        ):
            if relationship.get("materialize", True) is False:
                continue

            relationship_type = relationship.get("type")

            if relationship_type not in self.VALID_RELATIONSHIP_TYPES:
                findings.append(
                    AIFinding(
                        finding_type="kdm_invalid_relationship_type",
                        message=(
                            f"Relationship {relationship.get('id')} has "
                            f"invalid type '{relationship_type}'."
                        ),
                        severity="blocking",
                        status="ai_blocking_issue",
                        affected_elements=[
                            relationship.get("source"),
                            relationship.get("target"),
                        ],
                        recommendation=(
                            "Change the relationship type or mark the "
                            "relationship as not materialized."
                        ),
                    ).to_dict()
                )

        return findings
