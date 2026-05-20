from __future__ import annotations

from typing import Any

from kdm_architecture_agents.ai_suggestion_model import AIFinding


class ReviewConsistencyAgent:
    """
    Post-review agent that checks whether user decisions created semantic
    inconsistencies in the reviewed architecture JSON.
    """

    def run(
        self,
        model: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings = []

        findings.extend(self._check_executor_effector_balance(context))
        findings.extend(self._check_monitor_observation_balance(context))
        findings.extend(self._check_knowledge_usage(context))
        findings.extend(self._check_materialized_relationships(context))

        return findings

    def _check_executor_effector_balance(self, context):
        findings = []

        executors = context.get("components_by_role", {}).get("Executor", [])
        effectors = context.get("components_by_role", {}).get("Effector", [])

        if executors and not effectors:
            findings.append(
                AIFinding(
                    finding_type="executor_without_effector",
                    message=(
                        "The reviewed architecture contains Executor "
                        "components but no materialized Effector."
                    ),
                    severity="warning",
                    affected_elements=[c.get("id") for c in executors],
                    recommendation=(
                        "Review whether at least one Effector should remain "
                        "materialized or whether the Executor role should be "
                        "reconsidered."
                    ),
                ).to_dict()
            )

        return findings

    def _check_monitor_observation_balance(self, context):
        findings = []

        monitors = context.get("components_by_role", {}).get("Monitor", [])
        sensors = context.get("components_by_role", {}).get("Sensor", [])
        measured_outputs = context.get("components_by_role", {}).get(
            "MeasuredOutput", []
        )

        if monitors and not sensors and not measured_outputs:
            findings.append(
                AIFinding(
                    finding_type="monitor_without_observation_abstraction",
                    message=(
                        "The reviewed architecture contains Monitor "
                        "components but no Sensor or Measured Output."
                    ),
                    severity="warning",
                    affected_elements=[c.get("id") for c in monitors],
                    recommendation=(
                        "This may be acceptable if monitoring is implemented "
                        "directly in code, but the reviewer should confirm the "
                        "absence of explicit observation abstractions."
                    ),
                ).to_dict()
            )

        return findings

    def _check_knowledge_usage(self, context):
        findings = []

        knowledge_components = context.get("components_by_role", {}).get(
            "Knowledge", []
        )
        relationships = context.get("relationships", [])

        used_knowledge_targets = {
            relationship.get("target")
            for relationship in relationships
            if relationship.get("type") == "uses_knowledge"
            and relationship.get("materialize", True) is not False
        }

        for knowledge in knowledge_components:
            if knowledge.get("id") not in used_knowledge_targets:
                findings.append(
                    AIFinding(
                        finding_type="knowledge_without_usage",
                        message=(
                            f"Knowledge component {knowledge.get('name')} "
                            "has no materialized uses_knowledge relationship."
                        ),
                        severity="warning",
                        affected_elements=[knowledge.get("id")],
                        recommendation=(
                            "Review whether components should be linked to "
                            "Knowledge or whether the Knowledge component "
                            "should remain as a container-like abstraction."
                        ),
                    ).to_dict()
                )

        return findings

    def _check_materialized_relationships(self, context):
        findings = []

        component_by_id = context.get("component_by_id", {})
        all_node_ids = set(component_by_id.keys())
        all_node_ids.update(
            loop.get("id") for loop in context.get("control_loops", [])
        )
        all_node_ids.update(
            subsystem.get("id") for subsystem in context.get("subsystems", [])
        )

        for relationship in (
            context.get("relationships", [])
            + context.get("containment_relationships", [])
        ):
            if relationship.get("materialize", True) is False:
                continue

            source = relationship.get("source")
            target = relationship.get("target")

            if source not in all_node_ids or target not in all_node_ids:
                findings.append(
                    AIFinding(
                        finding_type="relationship_endpoint_missing",
                        message=(
                            "A materialized relationship references a missing "
                            "source or target element."
                        ),
                        severity="blocking",
                        status="ai_blocking_issue",
                        affected_elements=[
                            item for item in [source, target] if item
                        ],
                        recommendation=(
                            "Reject or repair the relationship before KDM "
                            "generation."
                        ),
                        metadata={
                            "relationship_id": relationship.get("id"),
                            "relationship_type": relationship.get("type"),
                            "source": source,
                            "target": target,
                        },
                    ).to_dict()
                )

        return findings
