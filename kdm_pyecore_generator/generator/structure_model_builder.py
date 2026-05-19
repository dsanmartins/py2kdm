class StructureModelBuilder:
    """
    Builds a KDM StructureModel from the architecture recovery JSON section.

    This version adds two important KDM links:

    1. implementation
       Each structure::Component can reference the concrete KDM code entities
       that implement the architectural abstraction.

       Example:
           Component pid_planner
               implementation -> CallableUnit pid

    2. aggregatedRelation
       Each architectural StructureRelationship can also be represented by a
       core::AggregatedRelationship owned by its source KDMEntity.

       Example:
           Component pid_planner
               structureRelationship -> speed_executor
               aggregatedRelation    -> speed_executor

    Notes:
    - Attribute tag="kind" is not used because the current validator treats it
      as obsolete.
    - The builder remains defensive: if a code implementation target cannot be
      found in id_index, it preserves the string id as an attribute.
    """

    def __init__(self, factory, segment, id_index=None):
        self.factory = factory
        self.segment = segment
        self.id_index = id_index or {}

        self.structure_model = None
        self.element_index = {}
        self.component_display_names = {}

    def build(self, structure_model_data: dict):
        if not structure_model_data:
            return None

        self.component_display_names = self._compute_component_display_names(
            structure_model_data.get("components", [])
        )

        self.structure_model = self.factory.create_structure_model(
            structure_model_data.get("name", "InferredCurrentArchitecture")
        )

        self.factory.add_attribute(
            self.structure_model,
            "status",
            structure_model_data.get("status"),
        )
        self.factory.add_attribute(
            self.structure_model,
            "recovery_mode",
            structure_model_data.get("recovery_mode"),
        )
        self.factory.add_attribute(
            self.structure_model,
            "architecture_family",
            structure_model_data.get("architecture_family"),
        )

        self.segment.model.append(self.structure_model)

        self._build_software_system(structure_model_data)
        self._build_architecture_views(structure_model_data)
        self._build_components(structure_model_data)
        self._build_control_loops(structure_model_data)
        self._build_subsystems(structure_model_data)
        self._build_architectural_relationships(structure_model_data)

        return self.structure_model

    # ------------------------------------------------------------
    # Element construction
    # ------------------------------------------------------------

    def _build_software_system(self, structure_model_data: dict):
        software_system = structure_model_data.get("software_system")

        if not software_system:
            return

        element = self.factory.create_software_system(
            software_system.get("name", "SoftwareSystem")
        )

        self._add_common_attributes(
            element=element,
            element_data=software_system,
            structure_kind="software_system",
        )

        self._add_structure_element(element)
        self.element_index[software_system.get("id")] = element

    def _build_architecture_views(self, structure_model_data: dict):
        for view_data in structure_model_data.get("architecture_views", []):
            element = self.factory.create_architecture_view(
                view_data.get("name", "ArchitectureView")
            )

            self._add_common_attributes(
                element=element,
                element_data=view_data,
                structure_kind="architecture_view",
            )

            self._add_structure_element(element)
            self.element_index[view_data.get("id")] = element

    def _build_components(self, structure_model_data: dict):
        for component_data in structure_model_data.get("components", []):
            component_id = component_data.get("id")
            display_name = self.component_display_names.get(
                component_id,
                component_data.get("name", "Component"),
            )

            element = self.factory.create_component(display_name)

            self._add_common_attributes(
                element=element,
                element_data=component_data,
                structure_kind="component",
            )

            self.factory.add_attribute(
                element,
                "role",
                component_data.get("role"),
            )
            self.factory.add_attribute(
                element,
                "confidence",
                component_data.get("confidence"),
            )
            self.factory.add_attribute(
                element,
                "source",
                component_data.get("source"),
            )
            self.factory.add_attribute(
                element,
                "component_status",
                component_data.get("status"),
            )
            self.factory.add_attribute(
                element,
                "code_element_type",
                component_data.get("code_element_type"),
            )
            self.factory.add_attribute(
                element,
                "loop_hint",
                component_data.get("loop_hint"),
            )

            self.factory.add_attribute(
                element,
                "display_name",
                display_name,
            )
            self.factory.add_attribute(
                element,
                "original_component_name",
                component_data.get("name"),
            )

            self._attach_implementation_refs(
                structure_element=element,
                implemented_by_ids=component_data.get("implemented_by", []),
            )

            for evidence in component_data.get("evidence", []):
                self.factory.add_attribute(
                    element,
                    "evidence",
                    evidence,
                )

            self._add_structure_element(element)
            self.element_index[component_id] = element

    def _build_control_loops(self, structure_model_data: dict):
        for loop_data in structure_model_data.get("control_loops", []):
            element = self.factory.create_structure_element(
                loop_data.get("name", "ControlLoop")
            )

            self._add_common_attributes(
                element=element,
                element_data=loop_data,
                structure_kind="control_loop",
            )

            self.factory.add_attribute(
                element,
                "level",
                loop_data.get("level"),
            )
            self.factory.add_attribute(
                element,
                "scope",
                loop_data.get("scope"),
            )
            self.factory.add_attribute(
                element,
                "loop_completeness",
                loop_data.get("loop_completeness"),
            )
            self.factory.add_attribute(
                element,
                "confidence",
                loop_data.get("confidence"),
            )
            self.factory.add_attribute(
                element,
                "control_loop_status",
                loop_data.get("status"),
            )

            for role in loop_data.get("roles_present", []):
                self.factory.add_attribute(
                    element,
                    "roles_present",
                    role,
                )

            for missing_role in loop_data.get("missing_roles", []):
                self.factory.add_attribute(
                    element,
                    "missing_role",
                    missing_role,
                )

            for component_id in loop_data.get("components", []):
                self.factory.add_attribute(
                    element,
                    "component",
                    component_id,
                )

                display_name = self.component_display_names.get(component_id)
                if display_name:
                    self.factory.add_attribute(
                        element,
                        "component_display_name",
                        display_name,
                    )

            for evidence in loop_data.get("evidence", []):
                self.factory.add_attribute(
                    element,
                    "evidence",
                    evidence,
                )

            self._add_structure_element(element)
            self.element_index[loop_data.get("id")] = element

    def _build_subsystems(self, structure_model_data: dict):
        for subsystem_data in structure_model_data.get("subsystems", []):
            element = self.factory.create_subsystem(
                subsystem_data.get("name", "Subsystem")
            )

            self._add_common_attributes(
                element=element,
                element_data=subsystem_data,
                structure_kind="subsystem",
            )

            self.factory.add_attribute(
                element,
                "confidence",
                subsystem_data.get("confidence"),
            )

            for component_id in subsystem_data.get("components", []):
                self.factory.add_attribute(
                    element,
                    "component",
                    component_id,
                )

                display_name = self.component_display_names.get(component_id)
                if display_name:
                    self.factory.add_attribute(
                        element,
                        "component_display_name",
                        display_name,
                    )

            for control_loop_id in subsystem_data.get("control_loops", []):
                self.factory.add_attribute(
                    element,
                    "control_loop",
                    control_loop_id,
                )

            self._add_structure_element(element)
            self.element_index[subsystem_data.get("id")] = element

    # ------------------------------------------------------------
    # Relationship construction
    # ------------------------------------------------------------

    def _build_architectural_relationships(self, structure_model_data: dict):
        for relationship_data in structure_model_data.get("structure_relationships", []):
            if relationship_data.get("relationship_level") != "architectural":
                continue

            source_id = relationship_data.get("source")
            target_id = relationship_data.get("target")

            source = self.element_index.get(source_id)
            target = self.element_index.get(target_id)

            if source is None or target is None:
                continue

            relation = self.factory.create_structure_relationship(source, target)

            self.factory.add_attribute(
                relation,
                "relationship_id",
                relationship_data.get("id"),
            )
            self.factory.add_attribute(
                relation,
                "relationship_type",
                relationship_data.get("type"),
            )
            self.factory.add_attribute(
                relation,
                "relationship_level",
                relationship_data.get("relationship_level"),
            )
            self.factory.add_attribute(
                relation,
                "confidence",
                relationship_data.get("confidence"),
            )
            self.factory.add_attribute(
                relation,
                "source_role",
                relationship_data.get("source_role"),
            )
            self.factory.add_attribute(
                relation,
                "target_role",
                relationship_data.get("target_role"),
            )
            self.factory.add_attribute(
                relation,
                "relationship_status",
                relationship_data.get("status"),
            )

            source_display_name = self.component_display_names.get(source_id)
            if source_display_name:
                self.factory.add_attribute(
                    relation,
                    "source_display_name",
                    source_display_name,
                )

            target_display_name = self.component_display_names.get(target_id)
            if target_display_name:
                self.factory.add_attribute(
                    relation,
                    "target_display_name",
                    target_display_name,
                )

            for evidence in relationship_data.get("derived_from", []):
                self.factory.add_attribute(
                    relation,
                    "derived_from",
                    evidence,
                )

            self._attach_structure_relationship(source, relation)

            aggregated = self.factory.create_aggregated_relationship(
                source=source,
                target=target,
                relations=[relation],
            )

            self.factory.add_attribute(
                aggregated,
                "relationship_type",
                relationship_data.get("type"),
            )
            self.factory.add_attribute(
                aggregated,
                "relationship_level",
                relationship_data.get("relationship_level"),
            )
            self.factory.add_attribute(
                aggregated,
                "source_role",
                relationship_data.get("source_role"),
            )
            self.factory.add_attribute(
                aggregated,
                "target_role",
                relationship_data.get("target_role"),
            )

            self._attach_aggregated_relationship(source, aggregated)

    # ------------------------------------------------------------
    # Implementation traceability
    # ------------------------------------------------------------

    def _attach_implementation_refs(
        self,
        structure_element,
        implemented_by_ids: list,
    ):
        """
        Adds real KDM implementation references when possible.

        If the referenced code element is not available in id_index, the
        original id is preserved as an Attribute for traceability/debugging.
        """

        if not implemented_by_ids:
            return

        if not self.factory.has_feature(structure_element, "implementation"):
            for implemented_by in implemented_by_ids:
                self.factory.add_attribute(
                    structure_element,
                    "implemented_by",
                    implemented_by,
                )
            return

        for implemented_by in implemented_by_ids:
            code_element = self.id_index.get(implemented_by)

            if code_element is not None:
                structure_element.implementation.append(code_element)
                self.factory.add_attribute(
                    structure_element,
                    "implemented_by_id",
                    implemented_by,
                )
            else:
                self.factory.add_attribute(
                    structure_element,
                    "unresolved_implementation_id",
                    implemented_by,
                )

    # ------------------------------------------------------------
    # Name disambiguation
    # ------------------------------------------------------------

    def _compute_component_display_names(self, components: list):
        by_name = {}

        for component in components:
            name = component.get("name", "Component")
            by_name.setdefault(name, []).append(component)

        display_names = {}
        used_names = set()

        for name, group in by_name.items():
            if len(group) == 1:
                component = group[0]
                display_name = str(name)

                if display_name in used_names:
                    display_name = self._unique_display_name(
                        base=display_name,
                        component=component,
                        used_names=used_names,
                    )

                display_names[component.get("id")] = display_name
                used_names.add(display_name)
                continue

            for component in group:
                role = component.get("role")
                base = f"{name}_{str(role).lower()}" if role else str(name)
                display_name = self._unique_display_name(
                    base=base,
                    component=component,
                    used_names=used_names,
                )
                display_names[component.get("id")] = display_name
                used_names.add(display_name)

        return display_names

    def _unique_display_name(self, base: str, component: dict, used_names: set):
        candidate = self._sanitize_name(base)

        if candidate not in used_names:
            return candidate

        component_id = component.get("id", "")
        suffix = component_id.split(":")[-1]

        suffix = suffix.replace(candidate, "").strip("_")
        suffix_parts = [part for part in suffix.split("_") if part]

        if suffix_parts:
            short_suffix = "_".join(suffix_parts[-3:])
            candidate_with_suffix = self._sanitize_name(f"{candidate}_{short_suffix}")

            if candidate_with_suffix not in used_names:
                return candidate_with_suffix

        index = 2
        while f"{candidate}_{index}" in used_names:
            index += 1

        return f"{candidate}_{index}"

    def _sanitize_name(self, value: str):
        return (
            str(value or "Component")
            .replace(" ", "_")
            .replace("-", "_")
            .replace(":", "_")
            .replace(".", "_")
        )

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _add_structure_element(self, element):
        if not self.factory.has_feature(self.structure_model, "structureElement"):
            return

        self.structure_model.structureElement.append(element)

    def _attach_structure_relationship(self, source, relation):
        for feature_name in [
            "structureRelationship",
            "structureRelation",
            "relation",
        ]:
            if self.factory.has_feature(source, feature_name):
                getattr(source, feature_name).append(relation)
                return True

        self.factory.add_attribute(
            source,
            "unattached_structure_relationship_type",
            self._get_attribute_value(relation, "relationship_type"),
        )
        self.factory.add_attribute(
            source,
            "unattached_structure_relationship_target",
            getattr(getattr(relation, "to", None), "name", None),
        )
        return False

    def _attach_aggregated_relationship(self, source, aggregated):
        """
        AggregatedRelationship is owned by the KDMEntity that acts as the
        aggregation from-endpoint, through aggregatedRelation.
        """

        if self.factory.has_feature(source, "aggregatedRelation"):
            source.aggregatedRelation.append(aggregated)
            return True

        self.factory.add_attribute(
            source,
            "unattached_aggregated_relationship_target",
            getattr(getattr(aggregated, "to", None), "name", None),
        )
        return False

    def _add_common_attributes(
        self,
        element,
        element_data: dict,
        structure_kind: str,
    ):
        self.factory.add_attribute(element, "id", element_data.get("id"))

        # Do not use tag="kind"; the validator marks it as obsolete.
        self.factory.add_attribute(element, "structure_kind", structure_kind)

        if element_data.get("status") is not None:
            self.factory.add_attribute(element, "status", element_data.get("status"))

        if element_data.get("name") is not None:
            self.factory.add_attribute(
                element,
                "recovered_name",
                element_data.get("name"),
            )

    def _get_attribute_value(self, element, tag: str):
        if not self.factory.has_feature(element, "attribute"):
            return None

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) == tag:
                return getattr(attribute, "value", None)

        return None
