from kdm_architecture_recovery.semantic_architecture_rules import (
    SemanticArchitectureRules,
)


class ContainmentRecoverer:
    """
    Builds containment relationships using SemanticArchitectureRules during
    construction.
    """

    LOOP_INTERNAL_ROLES = {
        "Monitor", "Analyzer", "Planner", "Executor", "Knowledge", "ReferenceInput",
    }

    MANAGED_ROLES = {"Sensor", "Effector", "MeasuredOutput"}

    def __init__(self, rules=None):
        self.rules = rules or SemanticArchitectureRules()

    def recover(self, structure_model: dict):
        components = structure_model.get("components", [])
        subsystems = structure_model.get("subsystems", [])
        control_loops = structure_model.get("control_loops", [])

        relationships = []

        managing = self._find_subsystem(subsystems, "managing")
        managed = self._find_subsystem(subsystems, "managed")

        loop_manager_components = [
            component
            for component in components
            if component.get("role") == "LoopManager"
            or component.get("stereotype_name") == "CL Manager"
        ]

        component_by_id = {
            component.get("id"): component
            for component in components
        }

        has_loop_manager = bool(loop_manager_components)

        if managing:
            if loop_manager_components:
                for loop_manager in loop_manager_components:
                    rel = self._guarded_contains(
                        source=managing,
                        source_role="Managing Subsystem",
                        target=loop_manager,
                        target_role="CL Manager",
                        reason="Managing Subsystem contains the CL Manager.",
                        context={"has_loop_manager": has_loop_manager},
                    )
                    if rel:
                        relationships.append(rel)

                for loop_manager in loop_manager_components:
                    for loop in control_loops:
                        rel = self._guarded_contains(
                            source=loop_manager,
                            source_role="CL Manager",
                            target=loop,
                            target_role="Control Loop",
                            reason="CL Manager coordinates one or more Control Loops.",
                            context={"has_loop_manager": has_loop_manager},
                        )
                        if rel:
                            relationships.append(rel)
            else:
                for loop in control_loops:
                    rel = self._guarded_contains(
                        source=managing,
                        source_role="Managing Subsystem",
                        target=loop,
                        target_role="Control Loop",
                        reason=(
                            "Managing Subsystem contains Control Loop because "
                            "no CL Manager was recovered."
                        ),
                        context={"has_loop_manager": has_loop_manager},
                    )
                    if rel:
                        relationships.append(rel)

        for loop in control_loops:
            self.rules.assess_control_loop(loop)

            for component_id in loop.get("components", []):
                component = component_by_id.get(component_id)
                if not component:
                    continue

                role = component.get("role")
                if role not in self.LOOP_INTERNAL_ROLES:
                    continue

                rel = self._guarded_contains(
                    source=loop,
                    source_role="Control Loop",
                    target=component,
                    target_role=role,
                    reason=f"Control Loop contains {role}.",
                    context={"has_loop_manager": has_loop_manager},
                )
                if rel:
                    relationships.append(rel)

        if managed:
            for component in components:
                role = component.get("role")
                if role not in self.MANAGED_ROLES:
                    continue

                rel = self._guarded_contains(
                    source=managed,
                    source_role="Managed Subsystem",
                    target=component,
                    target_role=role,
                    reason=f"Managed Subsystem contains {role}.",
                    context={"has_loop_manager": has_loop_manager},
                )
                if rel:
                    relationships.append(rel)

        self.rules.assess_control_io_presence(components)

        structure_model["containment_relationships"] = self._deduplicate(relationships)
        structure_model["architecture_consistency"] = self.rules.report()

        return structure_model["containment_relationships"]

    def _guarded_contains(self, source, source_role, target, target_role, reason, context):
        source_id = source.get("id")
        target_id = target.get("id")

        if not source_id or not target_id:
            return None

        if not self.rules.can_contain(
            source_id=source_id,
            source_role=source_role,
            target_id=target_id,
            target_role=target_role,
            context=context,
        ):
            return None

        return self._contains(source=source_id, target=target_id, reason=reason)

    def _find_subsystem(self, subsystems, kind):
        for subsystem in subsystems:
            text = f"{subsystem.get('id', '')} {subsystem.get('name', '')}".lower()
            if kind in text:
                return subsystem
        return None

    def _contains(self, source, target, reason):
        return {
            "id": f"containment:{self._safe(source)}__contains__{self._safe(target)}",
            "type": "contains",
            "relationship_level": "architectural",
            "source": source,
            "target": target,
            "confidence": 0.9,
            "status": "auto_accepted",
            "evidence": [reason],
        }

    def _safe(self, value):
        return str(value).replace(":", "_").replace("/", "_").replace(".", "_")

    def _deduplicate(self, relationships):
        seen = set()
        result = []
        for relationship in relationships:
            key = (
                relationship.get("source"),
                relationship.get("type"),
                relationship.get("target"),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(relationship)
        return result
