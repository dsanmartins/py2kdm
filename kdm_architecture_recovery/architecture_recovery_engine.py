from kdm_architecture_recovery.autonomic_applicability_gate import (
    AutonomicApplicabilityGate,
)
from kdm_architecture_recovery.rule_based_mapek_role_inferer import (
    RuleBasedMAPEKRoleInferer,
)
from kdm_architecture_recovery.structure_relationship_recoverer import (
    StructureRelationshipRecoverer,
)
from kdm_architecture_recovery.managed_interaction_recoverer import (
    ManagedInteractionRecoverer,
)
from kdm_architecture_recovery.adaptive_stereotype_catalog import (
    architecture_profile,
    stereotype_for_component_role,
    stereotype_for_subsystem,
)
from kdm_architecture_recovery.control_io_recoverer import ControlIORecoverer
from kdm_architecture_recovery.containment_recoverer import ContainmentRecoverer
from kdm_architecture_recovery.semantic_architecture_rules import (
    SemanticArchitectureRules,
)


class ArchitectureRecoveryEngine:
    """
    Semi-automatic architecture recovery engine for self-adaptive systems.

    Version 6 adds:
    - Adaptive System Domain stereotype metadata;
    - Reference Input, Measured Output, Sensor and Effector recovery;
    - containment/composition relationships following the REMEDY/MAPE-K
      hierarchy:
        Managing Subsystem -> Loop Manager -> Control Loop -> MAPE-K roles
        Managed Subsystem  -> Sensor / Effector / Measured Output.

    Notes:
    - Alternative is intentionally not promoted as a structural stereotype.
      Alternatives are considered internal Planner evidence.
    - Control Loop is kept in the `control_loops` section and materialized
      later by the KDM generator as the architectural loop abstraction.
    """

    COMPONENT_CONFIDENCE_THRESHOLD = 0.60

    MAPEK_CORE_ROLES = {
        "Monitor",
        "Analyzer",
        "Planner",
        "Executor",
        "Knowledge",
    }

    LOOP_INTERNAL_ROLES = {
        "Monitor",
        "Analyzer",
        "Planner",
        "Executor",
        "Knowledge",
        "ReferenceInput",
    }

    def __init__(self):
        self.gate = AutonomicApplicabilityGate()
        self.role_inferer = RuleBasedMAPEKRoleInferer()
        self.relationship_recoverer = StructureRelationshipRecoverer()
        self.managed_interaction_recoverer = ManagedInteractionRecoverer()
        self.control_io_recoverer = ControlIORecoverer()
        self.semantic_rules = SemanticArchitectureRules()
        self.containment_recoverer = ContainmentRecoverer(
            rules=self.semantic_rules,
        )

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

        # Add Sensor, Effector, Reference Input and Measured Output candidates.
        control_io_components = self.control_io_recoverer.recover(
            data=project_model,
            existing_components=components,
        )
        components.extend(control_io_components)
        components = self._deduplicate_components(components)

        control_loops = self._build_control_loops(components)
        subsystems = self._build_subsystems(components, control_loops)

        structure_model = {
            "name": "InferredCurrentArchitecture",
            "status": "proposed_inferred_architecture",
            "recovery_mode": "semi_automatic",
            "architecture_family": "self_adaptive_mapek",
            "architecture_profile": architecture_profile(),
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
            "subsystems": subsystems,
            "structure_relationships": [],
            "containment_relationships": [],
        }

        structure_relationships = self.relationship_recoverer.recover(
            project_model=project_model,
            structure_model=structure_model,
        )

        managed_interaction_relationships = (
            self.managed_interaction_recoverer.recover(
                structure_model=structure_model,
            )
        )
        structure_relationships.extend(managed_interaction_relationships)

        containment_relationships = self.containment_recoverer.recover(
            structure_model=structure_model,
        )

        # Keep both views:
        # - structure_relationships: all architectural relationships to be
        #   materialized by the KDM generator.
        # - containment_relationships: explicit subset useful for GUI/review.
        structure_model["structure_relationships"] = self._deduplicate_relationships(
            structure_relationships + containment_relationships
        )
        structure_model["containment_relationships"] = containment_relationships
        structure_model["architecture_consistency"] = self.semantic_rules.report()

        structure_model["recovery_statistics"] = self._build_recovery_statistics(
            role_suggestions=role_suggestions,
            components=components,
            control_loops=control_loops,
            structure_relationships=structure_model["structure_relationships"],
            control_io_components=control_io_components,
            containment_relationships=containment_relationships,
        )

        project_model["structure_model"] = structure_model

        architecture_recovery["mapek_recovery"] = "enabled"
        architecture_recovery["role_suggestions_count"] = len(role_suggestions)
        architecture_recovery["components_count"] = len(components)
        architecture_recovery["control_io_components_count"] = len(
            control_io_components
        )
        architecture_recovery["control_loops_count"] = len(control_loops)
        architecture_recovery["subsystems_count"] = len(subsystems)
        architecture_recovery["structure_relationships_count"] = len(
            structure_model["structure_relationships"]
        )
        architecture_recovery["managed_interaction_relationships_count"] = len(
            managed_interaction_relationships
        )
        architecture_recovery["containment_relationships_count"] = len(
            containment_relationships
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

            # Alternative is not a structural stereotype in this version.
            # It can be retained as Planner evidence by future enrichers.
            if role == "Alternative":
                continue

            code_id = suggestion.get("code_element_id")
            qn = suggestion.get("code_element_qualified_name")
            component_name = self._component_name_from_qualified_name(qn, role)

            component_id = self._build_component_id(
                component_name=component_name,
                role=role,
                code_element_id=code_id,
            )

            component = {
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

            stereotype_info = stereotype_for_component_role(role)

            if stereotype_info:
                component.update(stereotype_info)

            components.append(component)

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
        loop_candidate_components = [
            component
            for component in components
            if component.get("role") in self.LOOP_INTERNAL_ROLES
        ]

        if not loop_candidate_components:
            return []

        mapek_components = [
            component
            for component in loop_candidate_components
            if component.get("role") in self.MAPEK_CORE_ROLES
        ]

        if not mapek_components:
            return []

        grouped = self._group_components_by_loop_hint(loop_candidate_components)
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

            loop_id = f"control_loop:{self._slug(loop_key)}"

            control_loops.append(
                {
                    "id": loop_id,
                    "name": self._readable_loop_name(loop_key),
                    "role": "Loop",
                    "stereotype_name": "Control Loop",
                    "stereotype_domain": "Adaptive System Domain",
                    "stereotype_type": "structure:Component",
                    "level": 1,
                    "scope": "flat",
                    "loop_completeness": completeness,
                    "missing_roles": missing_roles,
                    "components": [
                        component.get("id")
                        for component in group_components
                        if component.get("role") in self.LOOP_INTERNAL_ROLES
                    ],
                    "roles_present": sorted(present_roles),
                    "confidence": confidence,
                    "status": status,
                    "evidence": [
                        "Candidate control loop inferred from high-confidence "
                        "MAPE-K components.",
                        f"Roles present: {', '.join(sorted(present_roles))}",
                    ],
                }
            )

        return control_loops

    def _group_components_by_loop_hint(self, components: list):
        hinted_groups = {}
        shared_knowledge = []
        shared_reference_inputs = []
        unhinted = []

        for component in components:
            loop_hint = component.get("loop_hint")

            if loop_hint:
                hinted_groups.setdefault(loop_hint, []).append(component)
                continue

            if component.get("role") == "Knowledge":
                shared_knowledge.append(component)
            elif component.get("role") == "ReferenceInput":
                shared_reference_inputs.append(component)
            else:
                unhinted.append(component)

        if hinted_groups:
            for loop_key in list(hinted_groups.keys()):
                hinted_groups[loop_key].extend(shared_knowledge)
                hinted_groups[loop_key].extend(shared_reference_inputs)
                hinted_groups[loop_key].extend(unhinted)

            return hinted_groups

        return {
            "main_candidate_loop": components
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
        }

        managed_roles = {
            "Sensor",
            "Effector",
            "MeasuredOutput",
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

        if managing_components or control_loops:
            subsystem = {
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

            stereotype_info = stereotype_for_subsystem(subsystem)
            if stereotype_info:
                subsystem.update(stereotype_info)

            subsystems.append(subsystem)

        if managed_components:
            subsystem = {
                "id": "subsystem:managed_subsystem",
                "name": "Managed Subsystem",
                "components": self._unique(managed_components),
                "confidence": self._average_confidence(
                    components,
                    managed_components,
                ),
            }

            stereotype_info = stereotype_for_subsystem(subsystem)
            if stereotype_info:
                subsystem.update(stereotype_info)

            subsystems.append(subsystem)

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
        control_io_components: list = None,
        containment_relationships: list = None,
    ):
        control_io_components = control_io_components or []
        containment_relationships = containment_relationships or []

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
            "control_io_components": len(control_io_components),
            "control_loops": len(control_loops),
            "structure_relationships": len(structure_relationships),
            "containment_relationships": len(containment_relationships),
            "component_confidence_threshold": self.COMPONENT_CONFIDENCE_THRESHOLD,
        }

    def _average_component_confidence(self, components: list):
        values = [
            component.get("confidence", 0.0)
            for component in components
            if isinstance(component.get("confidence", 0.0), (int, float))
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
            and isinstance(component.get("confidence", 0.0), (int, float))
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

    def _deduplicate_relationships(self, relationships: list):
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
