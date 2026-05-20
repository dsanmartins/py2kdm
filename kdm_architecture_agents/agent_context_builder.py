from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


class AgentContextBuilder:
    """
    Builds a compact context used by architecture agents.

    The context is intentionally derived from the architecture JSON instead of
    the KDM XMI. The architecture JSON remains the source of truth before KDM
    generation.
    """

    def build(self, model: dict[str, Any]) -> dict[str, Any]:
        structure_model = model.get("structure_model", {})
        components = structure_model.get("components", [])
        relationships = structure_model.get("structure_relationships", [])
        containment = structure_model.get("containment_relationships", [])
        loops = structure_model.get("control_loops", [])
        subsystems = structure_model.get("subsystems", [])

        materialized_components = [
            component for component in components
            if component.get("materialize", True) is not False
        ]

        by_id = {
            component.get("id"): component
            for component in components
            if component.get("id")
        }

        role_index = defaultdict(list)

        for component in materialized_components:
            role_index[component.get("role")].append(component)

        implementation_index = defaultdict(list)

        for component in materialized_components:
            for implementation in component.get("implemented_by", []) or []:
                implementation_index[implementation].append(component)

        relationship_index = defaultdict(list)

        for relationship in relationships + containment:
            source = relationship.get("source")
            target = relationship.get("target")
            relationship_index[source].append(relationship)
            relationship_index[target].append(relationship)

        loop_summaries = []

        for loop in loops:
            component_ids = loop.get("components", []) or []
            roles = [
                by_id[component_id].get("role")
                for component_id in component_ids
                if component_id in by_id
            ]

            loop_summaries.append(
                {
                    "id": loop.get("id"),
                    "name": loop.get("name"),
                    "roles": sorted(set(roles)),
                    "role_counts": dict(Counter(roles)),
                    "missing_core_roles": sorted(
                        {"Monitor", "Analyzer", "Planner", "Executor"}
                        - set(roles)
                    ),
                    "components": component_ids,
                }
            )

        return {
            "projectName": model.get("projectName"),
            "language": model.get("language"),
            "components": components,
            "relationships": relationships,
            "containment_relationships": containment,
            "control_loops": loops,
            "subsystems": subsystems,
            "component_by_id": by_id,
            "components_by_role": dict(role_index),
            "components_by_implementation": dict(implementation_index),
            "relationships_by_endpoint": dict(relationship_index),
            "loop_summaries": loop_summaries,
            "architecture_consistency": structure_model.get(
                "architecture_consistency", {}
            ),
            "architecture_review": model.get("architecture_review", {}),
        }
