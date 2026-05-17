class ReferenceResolver:
    def __init__(
        self,
        factory,
        id_index,
        external_builder=None,
        qualified_name_index=None,
        class_name_index=None,
        language="unknown",
        inventory_builder=None,
    ):
        self.factory = factory
        self.id_index = id_index
        self.external_builder = external_builder
        self.qualified_name_index = qualified_name_index or {}
        self.class_name_index = class_name_index or {}
        self.language = language
        self.inventory_builder = inventory_builder
        self.action_index = {}

    # ------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------

    def add_call_relations(self, data: dict):
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._add_callable_calls(method, file_model)

            for func in file_model.get("functions", []):
                self._add_callable_calls(func, file_model)

    def _add_callable_calls(self, callable_model: dict, file_model: dict):
        source = self.id_index.get(callable_model.get("id"))

        if source is None:
            return

        for call in callable_model.get("calls", []):
            action = self.factory.create_action_element(
                name=call.get("name", "call"),
                kind=call.get("kind", "call"),
            )

            self._register_action(callable_model, call, action)

            source_file = self._get_source_file(file_model)

            self.factory.add_source_region(
                action,
                path=file_model.get("path"),
                language=self.language,
                start_line=call.get("line"),
                end_line=call.get("line"),
                file_item=source_file,
            )

            self._add_call_traceability_metadata(action, call)

            source.codeElement.append(action)

            target = self._resolve_call_target(call)

            if target is not None:
                if self._is_constructor_call(call):
                    creates_relation = self.factory.create_creates_relation(target)
                    action.actionRelation.append(creates_relation)
                else:
                    calls_relation = self.factory.create_calls_relation(target)
                    action.actionRelation.append(calls_relation)
            else:
                self._add_unresolved_call_metadata(action, call)

    def _is_constructor_call(self, call: dict):
        return (
            call.get("classification") == "constructor"
            or call.get("kind") == "constructor_call"
        )

    def _add_call_traceability_metadata(self, action, call: dict):
        """
        Adds only technical traceability attributes.

        Semantic resolution is represented by action::Calls or action::Creates,
        not by temporary attributes such as resolved or target_id.
        """

        metadata = {
            "original_id": call.get("id"),
            "classification": call.get("classification"),
            "occurrence_index": call.get("occurrence_index"),
        }

        self.factory.add_attributes_from_dict(action, metadata)

    def _add_unresolved_call_metadata(self, action, call: dict):
        """
        Adds explicit unresolved metadata only when the call target could not
        be represented as a KDM relation.
        """

        self.factory.add_attribute(
            action,
            "resolution_status",
            "unresolved",
        )

        self.factory.add_attribute(
            action,
            "unresolved_target_name",
            call.get("name"),
        )

    def _resolve_call_target(self, call: dict):
        target_id = call.get("target_id")

        if target_id in self.id_index:
            return self.id_index[target_id]

        if self._is_external_or_builtin(call):
            if self.external_builder is None:
                return None

            return self.external_builder.get_or_create_external_target(call)

        return None

    def _is_external_or_builtin(self, call: dict):
        classification = call.get("classification")
        target_id = call.get("target_id")

        if classification in {
            "external",
            "external_type_method",
            "builtin",
            "builtin_type_method",
            "constructor",
        }:
            return True

        if target_id and (
            target_id.startswith("builtin:")
            or target_id.startswith("builtin_type:")
            or target_id.startswith("external_type:")
        ):
            return True

        return False

    # ------------------------------------------------------------
    # Extends
    # ------------------------------------------------------------

    def add_extends_relations(self, data: dict):
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                self._add_class_extends(cls, file_model)

    def _add_class_extends(self, cls: dict, file_model: dict):
        source_class = self.id_index.get(cls.get("id"))

        if source_class is None:
            return

        for base_name in cls.get("bases", []):
            target_class = self._resolve_base_class(base_name, file_model)

            if target_class is None:
                continue

            extends_relation = self.factory.create_extends_relation(target_class)
            source_class.codeRelation.append(extends_relation)

    def _resolve_base_class(self, base_name: str, file_model: dict):
        """
        Resolves a base class name to a KDM ClassUnit.

        Examples:
        - BaseService should resolve internally.
        - BaseEntity should resolve internally.
        - Exception should resolve as builtins / Exception.
        """

        # 1. Try same module qualified name
        module_qn = file_model.get("qualified_name")
        if module_qn:
            candidate_qn = f"{module_qn}.{base_name}"
            if candidate_qn in self.qualified_name_index:
                return self.qualified_name_index[candidate_qn]

        # 2. Try by simple class name
        candidates = self.class_name_index.get(base_name, [])

        if len(candidates) == 1:
            return candidates[0]

        if len(candidates) > 1:
            # For now, pick the first candidate.
            # Later this can be improved using imports.
            return candidates[0]

        # 3. Builtin/external base classes
        if self.external_builder is not None:
            return self.external_builder.get_or_create_external_class(
                library_name="builtins",
                class_name=base_name,
            )

        return None

    # ------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------

    def add_import_relations(self, data: dict):
        for file_model in data.get("files", []):
            self._add_file_imports(file_model)

    def _add_file_imports(self, file_model: dict):
        source_unit = self.id_index.get(file_model.get("id"))

        if source_unit is None:
            return

        for import_model in file_model.get("imports", []):
            target = self._resolve_import_target(import_model)

            if target is None:
                continue

            imports_relation = self.factory.create_imports_relation(target)

            source_file = self._get_source_file(file_model)
            self.factory.add_source_region(
                imports_relation,
                path=file_model.get("path"),
                language=self.language,
                start_line=import_model.get("line"),
                end_line=import_model.get("line"),
                file_item=source_file,
            )

            self._add_import_traceability_metadata(imports_relation, import_model)

            source_unit.codeRelation.append(imports_relation)

    def _add_import_traceability_metadata(self, relation, import_model: dict):
        """
        Adds only technical traceability for imports.

        Semantic resolution is represented by code::Imports.
        Therefore, target_id and resolved are not serialized.
        """

        metadata = {
            "classification": import_model.get("classification"),
        }

        self.factory.add_attributes_from_dict(relation, metadata)

    def _resolve_import_target(self, import_model: dict):
        target_id = import_model.get("target_id")

        # Internal resolved import
        if target_id in self.id_index:
            return self.id_index[target_id]

        classification = import_model.get("classification")

        # External import
        if classification == "external":
            if self.external_builder is None:
                return None

            return self.external_builder.get_or_create_external_import_target(
                import_model
            )

        return None

    # ------------------------------------------------------------
    # Indexing helpers
    # ------------------------------------------------------------

    def _get_source_file(self, file_model: dict):
        if self.inventory_builder is None:
            return None

        return self.inventory_builder.get_source_file_by_path(
            file_model.get("path")
        )

    def _register_action(self, callable_model: dict, call: dict, action):
        owner_id = callable_model.get("id")
        line = call.get("line")
        call_id = call.get("id")

        if call_id:
            self.action_index[call_id] = action

        if owner_id is None or line is None:
            return

        candidate_names = {
            call.get("name"),
            call.get("function"),
            call.get("method"),
            call.get("class_name"),
        }

        for name in candidate_names:
            if name:
                self.action_index[(owner_id, line, str(name))] = action

        self.action_index.setdefault((owner_id, line), []).append(action)
