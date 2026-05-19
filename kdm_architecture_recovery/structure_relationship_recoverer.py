class StructureRelationshipRecoverer:
    """
    Recovers structural relationships between inferred architecture components.

    Version 5 distinguishes technical evidence from architectural relationships
    through the field `relationship_level`.

    Relationship levels:
    - technical:
        Framework or implementation-level evidence, for example Rx/PyMAPE
        subscribe calls.

    - architectural:
        Architecture-level interpretation, for example MAPE-K flow or use of
        shared Knowledge.

    This distinction allows the KDM generator to decide which relationships
    should become AggregatedRelationship objects in the StructureModel.
    """

    ROLE_ORDER = {
        "Monitor": 1,
        "Analyzer": 2,
        "Planner": 3,
        "Executor": 4,
        "Knowledge": 5,
    }

    def recover(self, project_model: dict, structure_model: dict):
        components = structure_model.get("components", [])
        control_loops = structure_model.get("control_loops", [])

        relationships = []

        relationships.extend(
            self._recover_subscription_relationships(
                project_model=project_model,
                components=components,
            )
        )

        relationships.extend(
            self._recover_loop_order_relationships(
                components=components,
                control_loops=control_loops,
            )
        )

        relationships.extend(
            self._recover_knowledge_relationships(
                components=components,
                control_loops=control_loops,
            )
        )

        return self._deduplicate_relationships(relationships)

    # ------------------------------------------------------------
    # Subscription relationships
    # ------------------------------------------------------------

    def _recover_subscription_relationships(
        self,
        project_model: dict,
        components: list,
    ):
        """
        Recovers relationships from calls such as:

            distance.subscribe(pid)
            speed.subscribe(loop.pid)
            pid.subscribe(speed)

        These relationships are technical evidence, not necessarily final
        architectural dependencies. They are useful to justify architectural
        inferences but should be treated carefully when generating a KDM
        StructureModel.
        """

        relationships = []

        component_by_short_name = self._components_by_short_name(components)

        for callable_model in self._iter_callables(project_model):
            caller_qn = callable_model.get("qualified_name")
            caller_name = callable_model.get("name")

            for call in callable_model.get("calls", []):
                call_name = self._call_display_name(call)

                if ".subscribe" not in call_name:
                    continue

                source_name = call_name.split(".subscribe")[0].split(".")[-1]
                target_names = self._extract_candidate_target_names(call)

                source_components = component_by_short_name.get(source_name, [])

                for target_name in target_names:
                    target_components = component_by_short_name.get(target_name, [])

                    for source_component in source_components:
                        for target_component in target_components:
                            if source_component.get("id") == target_component.get("id"):
                                continue

                            relationships.append(
                                {
                                    "id": self._relationship_id(
                                        source_component.get("id"),
                                        target_component.get("id"),
                                        "subscribes_to",
                                    ),
                                    "source": source_component.get("id"),
                                    "target": target_component.get("id"),
                                    "type": "subscribes_to",
                                    "relationship_level": "technical",
                                    "confidence": 0.85,
                                    "source_role": source_component.get("role"),
                                    "target_role": target_component.get("role"),
                                    "derived_from": [
                                        (
                                            f"Call '{call_name}' in "
                                            f"{caller_qn or caller_name}"
                                        )
                                    ],
                                    "status": "auto_accepted",
                                }
                            )

        return relationships

    def _extract_candidate_target_names(self, call: dict):
        """
        Extracts likely target names from a call model.

        The exact JSON shape may vary, so this method checks several common
        fields used by the extractor.
        """

        candidates = []

        for key in [
            "argument_names",
            "args",
            "arguments",
            "argument_values",
            "parameters",
        ]:
            value = call.get(key)

            if isinstance(value, list):
                for item in value:
                    extracted = self._extract_name_from_argument(item)
                    if extracted:
                        candidates.append(extracted)

            elif isinstance(value, str):
                extracted = self._extract_name_from_argument(value)
                if extracted:
                    candidates.append(extracted)

        for key in ["argument", "value", "target", "function_argument"]:
            value = call.get(key)
            extracted = self._extract_name_from_argument(value)
            if extracted:
                candidates.append(extracted)

        return self._unique(candidates)

    def _extract_name_from_argument(self, value):
        if value is None:
            return None

        if isinstance(value, dict):
            for key in [
                "name",
                "id",
                "value",
                "text",
                "expression",
                "qualified_name",
            ]:
                if value.get(key):
                    return self._normalize_reference_name(value.get(key))

            return None

        return self._normalize_reference_name(value)

    def _normalize_reference_name(self, value):
        text = str(value)

        text = text.replace("'", "").replace('"', "")
        text = text.strip()

        if not text:
            return None

        if "." in text:
            text = text.split(".")[-1]

        if ":" in text:
            text = text.split(":")[-1].split(".")[-1]

        if text.endswith("()"):
            text = text[:-2]

        return text

    # ------------------------------------------------------------
    # Loop role-order relationships
    # ------------------------------------------------------------

    def _recover_loop_order_relationships(self, components: list, control_loops: list):
        """
        Adds conservative MAPE-K role-order relationships inside each loop.

        These relationships are architectural interpretations inferred from
        the MAPE-K role ordering. They are marked as `needs_review` because
        they may complement but not always exactly match low-level technical
        calls.
        """

        component_by_id = {
            component.get("id"): component
            for component in components
        }

        relationships = []

        for loop in control_loops:
            loop_components = [
                component_by_id.get(component_id)
                for component_id in loop.get("components", [])
            ]
            loop_components = [
                component for component in loop_components if component is not None
            ]

            ordered = sorted(
                [
                    component
                    for component in loop_components
                    if component.get("role") in self.ROLE_ORDER
                    and component.get("role") != "Knowledge"
                ],
                key=lambda component: self.ROLE_ORDER.get(component.get("role"), 99),
            )

            for source, target in zip(ordered, ordered[1:]):
                if source.get("role") == target.get("role"):
                    continue

                relationships.append(
                    {
                        "id": self._relationship_id(
                            source.get("id"),
                            target.get("id"),
                            "mapek_flow",
                        ),
                        "source": source.get("id"),
                        "target": target.get("id"),
                        "type": "mapek_flow",
                        "relationship_level": "architectural",
                        "confidence": 0.75,
                        "source_role": source.get("role"),
                        "target_role": target.get("role"),
                        "derived_from": [
                            (
                                "Role ordering inside "
                                f"{loop.get('id')}: {source.get('role')} "
                                f"precedes {target.get('role')}"
                            )
                        ],
                        "status": "needs_review",
                    }
                )

        return relationships

    # ------------------------------------------------------------
    # Knowledge relationships
    # ------------------------------------------------------------

    def _recover_knowledge_relationships(self, components: list, control_loops: list):
        """
        Adds architectural relationships from loop components to shared
        Knowledge components.
        """

        component_by_id = {
            component.get("id"): component
            for component in components
        }

        relationships = []

        for loop in control_loops:
            loop_component_ids = loop.get("components", [])
            knowledge_components = [
                component_by_id.get(component_id)
                for component_id in loop_component_ids
                if component_by_id.get(component_id, {}).get("role") == "Knowledge"
            ]

            non_knowledge_components = [
                component_by_id.get(component_id)
                for component_id in loop_component_ids
                if component_by_id.get(component_id, {}).get("role") != "Knowledge"
            ]

            for source_component in non_knowledge_components:
                if source_component is None:
                    continue

                for knowledge_component in knowledge_components:
                    if knowledge_component is None:
                        continue

                    relationships.append(
                        {
                            "id": self._relationship_id(
                                source_component.get("id"),
                                knowledge_component.get("id"),
                                "uses_knowledge",
                            ),
                            "source": source_component.get("id"),
                            "target": knowledge_component.get("id"),
                            "type": "uses_knowledge",
                            "relationship_level": "architectural",
                            "confidence": 0.80,
                            "source_role": source_component.get("role"),
                            "target_role": knowledge_component.get("role"),
                            "derived_from": [
                                (
                                    f"Component belongs to {loop.get('id')} "
                                    "with shared Knowledge component"
                                )
                            ],
                            "status": "auto_accepted",
                        }
                    )

        return relationships

    # ------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------

    def _iter_callables(self, project_model: dict):
        for file_model in project_model.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    yield method

            for func in file_model.get("functions", []):
                yield func

    def _call_display_name(self, call: dict):
        name = call.get("name")

        if name:
            return str(name)

        receiver = call.get("receiver")
        method = call.get("method")

        if receiver and method:
            return f"{receiver}.{method}"

        function = call.get("function")
        if function:
            return str(function)

        return ""

    # ------------------------------------------------------------
    # General helpers
    # ------------------------------------------------------------

    def _components_by_short_name(self, components: list):
        index = {}

        for component in components:
            names = {
                component.get("name"),
            }

            for implemented_id in component.get("implemented_by", []):
                if implemented_id:
                    names.add(str(implemented_id).split(":")[-1].split(".")[-1])

            for name in names:
                if not name:
                    continue

                index.setdefault(str(name), []).append(component)

        return index

    def _relationship_id(self, source: str, target: str, rel_type: str):
        return (
            "relationship:"
            + self._slug(source)
            + "__"
            + rel_type
            + "__"
            + self._slug(target)
        )

    def _slug(self, value: str):
        return (
            str(value or "unknown")
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
            if not value:
                continue

            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    def _deduplicate_relationships(self, relationships: list):
        by_key = {}

        for relationship in relationships:
            key = (
                relationship.get("source"),
                relationship.get("target"),
                relationship.get("type"),
                relationship.get("relationship_level"),
            )

            current = by_key.get(key)

            if current is None:
                by_key[key] = relationship
                continue

            current["derived_from"] = self._unique(
                current.get("derived_from", [])
                + relationship.get("derived_from", [])
            )

            if relationship.get("confidence", 0.0) > current.get("confidence", 0.0):
                current["confidence"] = relationship.get("confidence")
                current["status"] = relationship.get("status")

        return list(by_key.values())
