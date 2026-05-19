from kdm_architecture_recovery.autonomic_applicability_gate import (
    AutonomicApplicabilityGate,
)
from kdm_architecture_recovery.rule_based_mapek_role_inferer import (
    RuleBasedMAPEKRoleInferer,
)
from kdm_architecture_recovery.structure_relationship_recoverer import (
    StructureRelationshipRecoverer,
)


class ArchitectureRecoveryEngine:
    """
    Semi-automatic architecture recovery engine for self-adaptive systems.

    Version 4 adds structure relationship recovery.
    """

    COMPONENT_CONFIDENCE_THRESHOLD = 0.60

    MAPEK_CORE_ROLES = {
        "Monitor",
        "Analyzer",
        "Planner",
        "Executor",
        "Knowledge",
    }

    def __init__(self):
        self.gate = AutonomicApplicabilityGate()
        self.role_inferer = RuleBasedMAPEKRoleInferer()
        self.relationship_recoverer = StructureRelationshipRecoverer()

    def enrich_project_model(self, project_model: dict):
        applicability = self.gate.evaluate(project_model)

        architecture_recovery = {
            "recovery_mode": "semi_automatic",
            "architecture_status": "proposed_inferred_architecture",
            "autonomic_applicability": applicability,
        }

        project_model["architecture_recovery"] = architecture_recovery

        if applicability.get("status") != "mapek_recovery_enabled":
            architecture_recovery["mapek_recovery"] = "disabled"
            return project_model

        role_suggestions = self.role_inferer.infer_roles(project_model)
        components = self._build_components(role_suggestions)
        control_loops = self._build_control_loops(components)

        structure_model = {
            "name": "InferredCurrentArchitecture",
            "status": "proposed_inferred_architecture",
            "recovery_mode": "semi_automatic",
            "architecture_family": "self_adaptive_mapek",
            "autonomic_applicability": applicability,
            "software_system": {
                "id": f"software_system:{project_model.get('projectName', 'project')}",
                "name": project_model.get("projectName", "UnknownProject"),
            },
            "architecture_views": [
                {
                    "id": "architecture_view:mapek",
                    "name": "Inferred MAPE-K View",
                    "status": "proposal",
                }
            ],
            "role_suggestions": role_suggestions,
            "components": components,
            "control_loops": control_loops,
            "subsystems": self._build_subsystems(components, control_loops),
            "structure_relationships": [],
        }

        structure_relationships = self.relationship_recoverer.recover(
            project_model=project_model,
            structure_model=structure_model,
        )

        structure_model["structure_relationships"] = structure_relationships
        structure_model["recovery_statistics"] = self._build_recovery_statistics(
            role_suggestions,
            components,
            control_loops,
            structure_relationships,
        )

        project_model["structure_model"] = structure_model
        architecture_recovery["mapek_recovery"] = "enabled"
        architecture_recovery["role_suggestions_count"] = len(role_suggestions)
        architecture_recovery["components_count"] = len(components)
        architecture_recovery["control_loops_count"] = len(control_loops)
        architecture_recovery["structure_relationships_count"] = len(
            structure_relationships
        )

        return project_model

    # ------------------------------------------------------------
    # Component construction
    # ------------------------------------------------------------

    def _build_components(self, role_suggestions: list):
        components = []

        for suggestion in role_suggestions:
            if not self._should_promote_to_component(suggestion):
                continue

            role = suggestion.get("suggested_role")
            code_id = suggestion.get("code_element_id")
            qn = suggestion.get("code_element_qualified_name")
            component_name = self._component_name_from_qualified_name(qn, role)

            component_id = self._build_component_id(
                component_name=component_name,
                role=role,
                code_element_id=code_id,
            )

            components.append(
                {
                    "id": component_id,
                    "name": component_name,
                    "role": role,
                    "implemented_by": [code_id] if code_id else [],
                    "confidence": suggestion.get("confidence"),
                    "evidence": suggestion.get("evidence", []),
                    "source": suggestion.get("source"),
                    "status": suggestion.get("status"),
                    "code_element_type": suggestion.get("code_element_type"),
                    "loop_hint": suggestion.get("loop_hint"),
                }
            )

        return self._deduplicate_components(components)

    def _should_promote_to_component(self, suggestion: dict):
        if suggestion.get("status") == "auto_accepted":
            return True

        if suggestion.get("confidence", 0.0) >= self.COMPONENT_CONFIDENCE_THRESHOLD:
            return True

        return False

    def _build_component_id(
        self,
        component_name: str,
        role: str,
        code_element_id: str = None,
    ):
        base = self._slug(component_name)
        role_slug = self._slug(role)
        candidate = f"component:{base}_{role_slug}"

        if code_element_id:
            suffix = self._slug(code_element_id.split(":")[-1])
            if suffix and suffix != base:
                tail = "_".join(suffix.split("_")[-3:])
                candidate = f"{candidate}_{tail}"

        return candidate

    # ------------------------------------------------------------
    # Control loop construction
    # ------------------------------------------------------------

    def _build_control_loops(self, components: list):
        mapek_components = [
            component
            for component in components
            if component.get("role") in self.MAPEK_CORE_ROLES
        ]

        if not mapek_components:
            return []

        grouped = self._group_components_by_loop_hint(mapek_components)
        control_loops = []

        for loop_key, group_components in grouped.items():
            group_components = self._deduplicate_components_by_id(group_components)

            present_roles = {
                component.get("role")
                for component in group_components
                if component.get("role") in self.MAPEK_CORE_ROLES
            }

            if len(present_roles) < 2:
                continue

            completeness = self._loop_completeness(present_roles)
            missing_roles = sorted(
                {"Monitor", "Analyzer", "Planner", "Executor"} - present_roles
            )

            confidence = self._average_component_confidence(group_components)
            status = "auto_accepted" if confidence >= 0.85 else "needs_review"

            control_loops.append(
                {
                    "id": f"control_loop:{self._slug(loop_key)}",
                    "name": self._readable_loop_name(loop_key),
                    "level": 1,
                    "scope": "flat",
                    "loop_completeness": completeness,
                    "missing_roles": missing_roles,
                    "components": [
                        component.get("id")
                        for component in group_components
                        if component.get("role") in self.MAPEK_CORE_ROLES
                    ],
                    "roles_present": sorted(present_roles),
                    "confidence": confidence,
                    "status": status,
                    "evidence": [
                        "Candidate loop inferred from high-confidence MAPE-K "
                        "components.",
                        f"Roles present: {', '.join(sorted(present_roles))}",
                    ],
                }
            )

        return control_loops

    def _group_components_by_loop_hint(self, mapek_components: list):
        hinted_groups = {}
        shared_knowledge = []
        unhinted = []

        for component in mapek_components:
            loop_hint = component.get("loop_hint")

            if loop_hint:
                hinted_groups.setdefault(loop_hint, []).append(component)
                continue

            if component.get("role") == "Knowledge":
                shared_knowledge.append(component)
            else:
                unhinted.append(component)

        if hinted_groups:
            for loop_key in list(hinted_groups.keys()):
                hinted_groups[loop_key].extend(shared_knowledge)
                hinted_groups[loop_key].extend(unhinted)

            return hinted_groups

        return {
            "main_candidate_loop": mapek_components
        }

    def _loop_completeness(self, present_roles: set):
        complete_roles = {"Monitor", "Analyzer", "Planner", "Executor"}

        if complete_roles.issubset(present_roles):
            return "complete"

        if len(complete_roles.intersection(present_roles)) >= 2:
            return "partial"

        return "weak"

    # ------------------------------------------------------------
    # Subsystem construction
    # ------------------------------------------------------------

    def _build_subsystems(self, components: list, control_loops: list):
        managing_roles = {
            "Monitor",
            "Analyzer",
            "Planner",
            "Executor",
            "Knowledge",
            "LoopManager",
            "ReferenceInput",
            "Alternative",
        }

        managed_roles = {
            "Sensor",
            "Effector",
            "ManagedElement",
        }

        managing_components = [
            component.get("id")
            for component in components
            if component.get("role") in managing_roles
        ]

        managed_components = [
            component.get("id")
            for component in components
            if component.get("role") in managed_roles
        ]

        subsystems = []

        if managing_components:
            subsystems.append(
                {
                    "id": "subsystem:managing_subsystem",
                    "name": "Managing Subsystem",
                    "components": self._unique(managing_components),
                    "control_loops": [
                        loop.get("id") for loop in control_loops
                    ],
                    "confidence": self._average_confidence(
                        components,
                        managing_components,
                    ),
                }
            )

        if managed_components:
            subsystems.append(
                {
                    "id": "subsystem:managed_subsystem",
                    "name": "Managed Subsystem",
                    "components": self._unique(managed_components),
                    "confidence": self._average_confidence(
                        components,
                        managed_components,
                    ),
                }
            )

        return subsystems

    # ------------------------------------------------------------
    # Statistics and helpers
    # ------------------------------------------------------------

    def _build_recovery_statistics(
        self,
        role_suggestions: list,
        components: list,
        control_loops: list,
        structure_relationships: list,
    ):
        weak_suggestions = [
            suggestion
            for suggestion in role_suggestions
            if suggestion.get("status") == "weak_suggestion"
        ]

        auto_accepted = [
            suggestion
            for suggestion in role_suggestions
            if suggestion.get("status") == "auto_accepted"
        ]

        needs_review = [
            suggestion
            for suggestion in role_suggestions
            if suggestion.get("status") == "needs_review"
        ]

        return {
            "role_suggestions": len(role_suggestions),
            "auto_accepted_suggestions": len(auto_accepted),
            "needs_review_suggestions": len(needs_review),
            "weak_suggestions": len(weak_suggestions),
            "promoted_components": len(components),
            "control_loops": len(control_loops),
            "structure_relationships": len(structure_relationships),
            "component_confidence_threshold": self.COMPONENT_CONFIDENCE_THRESHOLD,
        }

    def _average_component_confidence(self, components: list):
        values = [
            component.get("confidence", 0.0)
            for component in components
        ]

        if not values:
            return 0.0

        return round(sum(values) / len(values), 2)

    def _average_confidence(self, components: list, selected_ids: list):
        selected_ids = set(selected_ids)

        values = [
            component.get("confidence", 0.0)
            for component in components
            if component.get("id") in selected_ids
        ]

        if not values:
            return 0.0

        return round(sum(values) / len(values), 2)

    def _component_name_from_qualified_name(self, qualified_name: str, fallback: str):
        if qualified_name and "." in qualified_name:
            return qualified_name.split(".")[-1]

        return qualified_name or fallback or "Component"

    def _readable_loop_name(self, loop_key: str):
        if loop_key == "main_candidate_loop":
            return "Main Candidate Control Loop"

        return str(loop_key).replace("_", " ").title() + " Control Loop"

    def _slug(self, value: str):
        return (
            str(value or "component")
            .replace(":", "_")
            .replace(".", "_")
            .replace("-", "_")
            .replace(" ", "_")
            .lower()
        )

    def _unique(self, values: list):
        seen = set()
        result = []

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    def _deduplicate_components(self, components: list):
        by_key = {}

        for component in components:
            key = (
                component.get("id"),
                component.get("role"),
            )

            current = by_key.get(key)

            if current is None:
                by_key[key] = component
                continue

            if component.get("confidence", 0.0) > current.get("confidence", 0.0):
                by_key[key] = component

        return list(by_key.values())

    def _deduplicate_components_by_id(self, components: list):
        by_id = {}

        for component in components:
            component_id = component.get("id")

            if component_id not in by_id:
                by_id[component_id] = component
                continue

            if component.get("confidence", 0.0) > by_id[component_id].get(
                "confidence",
                0.0,
            ):
                by_id[component_id] = component

        return list(by_id.values())
