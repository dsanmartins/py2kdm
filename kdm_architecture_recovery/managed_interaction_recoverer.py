class ManagedInteractionRecoverer:
    """
    Recovers candidate architectural interactions between the Managing
    Subsystem and the Managed Subsystem.

    Version 2 avoids Cartesian products such as:

        every Executor -> every Effector

    Instead, it creates role-boundary relationships only when there is
    meaningful name or implementation evidence.

    Supported relationships:

        Executor -> Effector                 acts_through
        Monitor  -> Sensor                   observes_through
        Monitor  -> MeasuredOutput           observes
        Sensor   -> MeasuredOutput           produces_measurement
        Analyzer/Planner -> ReferenceInput   uses_reference_input
        Analyzer/Planner -> MeasuredOutput   evaluates_measured_output

    Strong evidence:
        - the target name appears in the source name;
        - the source name appears in the target name;
        - implementation identifiers share meaningful domain tokens;
        - source and target share a specific domain token.

    Generic tokens such as speed, control, virtual, car, component, etc. are
    ignored to avoid noisy relations.
    """

    GENERIC_TOKENS = {
        "component",
        "control",
        "controller",
        "loop",
        "mape",
        "mapek",
        "system",
        "subsystem",
        "manager",
        "managed",
        "managing",
        "virtual",
        "car",
        "carspeed",
        "ambulance",
        "fixture",
        "fixtures",
        "pymape",
        "hierarchical",
        "cruise",
        "speed",
        "executor",
        "monitor",
        "planner",
        "analyzer",
        "knowledge",
        "sensor",
        "effector",
        "measured",
        "output",
        "reference",
        "input",
    }

    MIN_SHARED_TOKENS = 1

    def recover(self, structure_model: dict):
        components = structure_model.get("components", [])
        control_loops = structure_model.get("control_loops", [])

        relationships = []

        executors = self._components_by_role(components, "Executor")
        monitors = self._components_by_role(components, "Monitor")
        analyzers = self._components_by_role(components, "Analyzer")
        planners = self._components_by_role(components, "Planner")

        sensors = self._components_by_role(components, "Sensor")
        effectors = self._components_by_role(components, "Effector")
        measured_outputs = self._components_by_role(components, "MeasuredOutput")
        reference_inputs = self._components_by_role(components, "ReferenceInput")

        loop_component_ids = self._loop_component_ids(control_loops)

        # Executor -> Effector
        for executor in executors:
            if loop_component_ids and executor.get("id") not in loop_component_ids:
                continue

            for effector in effectors:
                match = self._match_evidence(executor, effector)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=executor,
                        target=effector,
                        rel_type="acts_through",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Executor and Effector were matched by "
                            f"{match['reason']}."
                        ),
                    )
                )

        # Monitor -> Sensor
        for monitor in monitors:
            if loop_component_ids and monitor.get("id") not in loop_component_ids:
                continue

            for sensor in sensors:
                match = self._match_evidence(monitor, sensor)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=monitor,
                        target=sensor,
                        rel_type="observes_through",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Monitor and Sensor were matched by "
                            f"{match['reason']}."
                        ),
                    )
                )

        # Monitor -> MeasuredOutput
        for monitor in monitors:
            if loop_component_ids and monitor.get("id") not in loop_component_ids:
                continue

            for measured_output in measured_outputs:
                match = self._match_evidence(monitor, measured_output)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=monitor,
                        target=measured_output,
                        rel_type="observes",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Monitor and Measured Output were matched by "
                            f"{match['reason']}."
                        ),
                    )
                )

        # Sensor -> MeasuredOutput
        for sensor in sensors:
            for measured_output in measured_outputs:
                match = self._match_evidence(sensor, measured_output)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=sensor,
                        target=measured_output,
                        rel_type="produces_measurement",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Sensor and Measured Output were matched by "
                            f"{match['reason']}."
                        ),
                    )
                )

        # Analyzer/Planner -> ReferenceInput
        decision_components = analyzers + planners

        for decision_component in decision_components:
            if loop_component_ids and decision_component.get("id") not in loop_component_ids:
                continue

            for reference_input in reference_inputs:
                match = self._match_evidence(decision_component, reference_input)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=decision_component,
                        target=reference_input,
                        rel_type="uses_reference_input",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Decision component and Reference Input were "
                            f"matched by {match['reason']}."
                        ),
                    )
                )

        # Analyzer/Planner -> MeasuredOutput
        for decision_component in decision_components:
            if loop_component_ids and decision_component.get("id") not in loop_component_ids:
                continue

            for measured_output in measured_outputs:
                match = self._match_evidence(decision_component, measured_output)

                if not match:
                    continue

                relationships.append(
                    self._relationship(
                        source=decision_component,
                        target=measured_output,
                        rel_type="evaluates_measured_output",
                        confidence=match["confidence"],
                        status=match["status"],
                        derived_from=(
                            "Decision component and Measured Output were "
                            f"matched by {match['reason']}."
                        ),
                    )
                )

        return self._deduplicate(relationships)

    # ------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------

    def _match_evidence(self, source: dict, target: dict):
        source_name_tokens = self._meaningful_tokens(source.get("name", ""))
        target_name_tokens = self._meaningful_tokens(target.get("name", ""))

        source_all_tokens = self._component_tokens(source)
        target_all_tokens = self._component_tokens(target)

        if not source_name_tokens or not target_name_tokens:
            return None

        # Strongest case:
        #   gas_brake -> gas
        #   gas_brake -> brake
        if target_name_tokens.issubset(source_all_tokens):
            return {
                "confidence": 0.85,
                "status": "auto_accepted",
                "reason": (
                    "target name token(s) appearing in the source component "
                    f"evidence: {', '.join(sorted(target_name_tokens))}"
                ),
            }

        # Useful inverse case:
        #   temperature_sensor -> temperature_measured_output
        if source_name_tokens.issubset(target_all_tokens):
            return {
                "confidence": 0.80,
                "status": "needs_review",
                "reason": (
                    "source name token(s) appearing in the target component "
                    f"evidence: {', '.join(sorted(source_name_tokens))}"
                ),
            }

        shared = source_all_tokens.intersection(target_all_tokens)

        if len(shared) >= self.MIN_SHARED_TOKENS:
            return {
                "confidence": 0.70,
                "status": "needs_review",
                "reason": (
                    "shared meaningful domain token(s): "
                    + ", ".join(sorted(shared))
                ),
            }

        return None

    def _component_tokens(self, component: dict):
        tokens = set()

        fields = [
            component.get("id", ""),
            component.get("name", ""),
            component.get("code_element_qualified_name", ""),
        ]

        fields.extend(component.get("implemented_by", []))

        for field in fields:
            tokens.update(self._meaningful_tokens(field))

        return tokens

    def _meaningful_tokens(self, value):
        raw = (
            str(value or "")
            .replace(":", "_")
            .replace(".", "_")
            .replace("/", "_")
            .replace("-", "_")
        )

        parts = []

        for char in raw:
            if char.isalnum() or char == "_":
                parts.append(char.lower())
            else:
                parts.append(" ")

        normalized = "".join(parts).replace("_", " ")
        tokens = {
            token
            for token in normalized.split()
            if len(token) >= 3
            and token not in self.GENERIC_TOKENS
        }

        return tokens

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _components_by_role(self, components, role):
        return [
            component for component in components
            if component.get("role") == role
            and component.get("materialize", True) is not False
        ]

    def _loop_component_ids(self, control_loops):
        ids = set()
        for loop in control_loops:
            for component_id in loop.get("components", []):
                ids.add(component_id)
        return ids

    def _relationship(self, source, target, rel_type, confidence, status, derived_from):
        return {
            "id": self._relationship_id(
                source.get("id"),
                target.get("id"),
                rel_type,
            ),
            "source": source.get("id"),
            "target": target.get("id"),
            "type": rel_type,
            "relationship_level": "architectural",
            "confidence": confidence,
            "source_role": source.get("role"),
            "target_role": target.get("role"),
            "derived_from": [derived_from],
            "status": status,
        }

    def _relationship_id(self, source, target, rel_type):
        return (
            "relationship:"
            + self._slug(source)
            + "__"
            + rel_type
            + "__"
            + self._slug(target)
        )

    def _slug(self, value):
        return (
            str(value or "unknown")
            .replace(":", "_")
            .replace(".", "_")
            .replace("-", "_")
            .replace(" ", "_")
            .lower()
        )

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
