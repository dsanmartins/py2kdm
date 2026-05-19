class ContainmentRecoverer:
    """
    Builds architectural containment/composition relationships following the
    Adaptive System Domain hierarchy.

    Correct containment hierarchy:

        Managing Subsystem
          contains CL Manager
              contains Control Loop(s)
                  contains Monitor / Analyzer / Planner / Executor /
                           Knowledge / Reference Input

    If no CL Manager is recovered:

        Managing Subsystem
          contains Control Loop(s)
              contains MAPE-K components

    Managed Subsystem
      contains Sensor / Effector / Measured Output

    Important:
    Managing Subsystem must NOT directly contain the MAPE-K internal elements
    when those elements already belong to a Control Loop. Otherwise the KDM
    contains redundant containment relations.
    """

    LOOP_INTERNAL_ROLES = {
        "Monitor",
        "Analyzer",
        "Planner",
        "Executor",
        "Knowledge",
        "ReferenceInput",
    }

    MANAGED_ROLES = {
        "Sensor",
        "Effector",
        "MeasuredOutput",
    }

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

        # --------------------------------------------------------
        # 1. Managing Subsystem containment
        # --------------------------------------------------------
        # Preferred:
        #   Managing Subsystem -> CL Manager -> Control Loop
        #
        # Fallback if no CL Manager:
        #   Managing Subsystem -> Control Loop
        #
        # We deliberately do NOT add:
        #   Managing Subsystem -> Monitor/Planner/Executor/Knowledge
        # when those components belong to a Control Loop.
        # --------------------------------------------------------

        if managing:
            if loop_manager_components:
                for loop_manager in loop_manager_components:
                    relationships.append(
                        self._contains(
                            source=managing["id"],
                            target=loop_manager["id"],
                            reason="Managing Subsystem contains the CL Manager.",
                        )
                    )

                for loop_manager in loop_manager_components:
                    for loop in control_loops:
                        relationships.append(
                            self._contains(
                                source=loop_manager["id"],
                                target=loop["id"],
                                reason=(
                                    "CL Manager coordinates one or more "
                                    "Control Loops."
                                ),
                            )
                        )
            else:
                for loop in control_loops:
                    relationships.append(
                        self._contains(
                            source=managing["id"],
                            target=loop["id"],
                            reason=(
                                "Managing Subsystem contains Control Loop "
                                "because no CL Manager was recovered."
                            ),
                        )
                    )

        # --------------------------------------------------------
        # 2. Control Loop internal containment
        # --------------------------------------------------------
        # Control Loop -> MAPE-K + Knowledge + ReferenceInput.
        # --------------------------------------------------------

        for loop in control_loops:
            for component_id in loop.get("components", []):
                component = component_by_id.get(component_id)

                if not component:
                    continue

                role = component.get("role")

                if role in self.LOOP_INTERNAL_ROLES:
                    relationships.append(
                        self._contains(
                            source=loop["id"],
                            target=component_id,
                            reason=f"Control Loop contains {role}.",
                        )
                    )

        # --------------------------------------------------------
        # 3. Managed Subsystem containment
        # --------------------------------------------------------
        # Managed Subsystem -> Sensor / Effector / Measured Output.
        # We do not try to reconstruct all managed-system components.
        # --------------------------------------------------------

        if managed:
            for component in components:
                role = component.get("role")

                if role in self.MANAGED_ROLES:
                    relationships.append(
                        self._contains(
                            source=managed["id"],
                            target=component["id"],
                            reason=f"Managed Subsystem contains {role}.",
                        )
                    )

        structure_model["containment_relationships"] = self._deduplicate(
            relationships
        )

        return structure_model["containment_relationships"]

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
