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

        runtime_summary = self._build_runtime_summary(
            model=model,
            implementation_index=implementation_index,
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
            "runtime_summary": runtime_summary,
            "architecture_consistency": structure_model.get(
                "architecture_consistency", {}
            ),
            "architecture_review": model.get("architecture_review", {}),
        }

    def _build_runtime_summary(
        self,
        model: dict[str, Any],
        implementation_index: dict,
    ) -> dict[str, Any]:
        runtime_calls = [
            relationship
            for relationship in model.get("relationships", [])
            if relationship.get("type") == "runtime_calls"
        ]

        source_counter = Counter()
        target_counter = Counter()
        scenario_counter = Counter()
        component_pair_counter = Counter()

        unresolved_to_components = 0
        resolved_component_pairs = []

        for relationship in runtime_calls:
            source = relationship.get("source")
            target = relationship.get("target")
            scenario = relationship.get("scenario") or "unknown_scenario"

            if source:
                source_counter[source] += 1

            if target:
                target_counter[target] += 1

            scenario_counter[scenario] += 1

            source_components = self._find_components_for_runtime_name(
                source,
                implementation_index,
            )
            target_components = self._find_components_for_runtime_name(
                target,
                implementation_index,
            )

            if not source_components or not target_components:
                unresolved_to_components += 1
                continue

            for source_component in source_components:
                for target_component in target_components:
                    key = (
                        source_component.get("id"),
                        target_component.get("id"),
                    )
                    component_pair_counter[key] += 1

        component_by_pair_key = {}

        for relationship in runtime_calls:
            source = relationship.get("source")
            target = relationship.get("target")

            source_components = self._find_components_for_runtime_name(
                source,
                implementation_index,
            )
            target_components = self._find_components_for_runtime_name(
                target,
                implementation_index,
            )

            for source_component in source_components:
                for target_component in target_components:
                    key = (
                        source_component.get("id"),
                        target_component.get("id"),
                    )
                    component_by_pair_key[key] = {
                        "source_component": source_component.get("id"),
                        "source_name": source_component.get("name"),
                        "source_role": source_component.get("role"),
                        "target_component": target_component.get("id"),
                        "target_name": target_component.get("name"),
                        "target_role": target_component.get("role"),
                    }

        for key, count in component_pair_counter.most_common(25):
            item = dict(component_by_pair_key.get(key, {}))
            item["runtime_call_count"] = count
            resolved_component_pairs.append(item)

        runtime_enrichment = model.get("runtime_enrichment", {})
        enrichment_summary = runtime_enrichment.get("summary", {})

        return {
            "available": bool(runtime_calls),
            "total_runtime_calls": len(runtime_calls),
            "runtime_calls_by_scenario": dict(scenario_counter),
            "top_sources": [
                {"source": source, "count": count}
                for source, count in source_counter.most_common(20)
            ],
            "top_targets": [
                {"target": target, "count": count}
                for target, count in target_counter.most_common(20)
            ],
            "top_component_pairs": resolved_component_pairs,
            "runtime_calls_unmapped_to_components": unresolved_to_components,
            "runtime_enrichment_summary": enrichment_summary,
            "observed_argument_types": enrichment_summary.get(
                "observed_argument_types"
            ),
            "observed_return_types": enrichment_summary.get(
                "observed_return_types"
            ),
        }

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

        # Remove duplicate components by id while preserving order.
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
