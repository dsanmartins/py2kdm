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

    def _get_value(self, data: dict, *keys, default=None):
        if not isinstance(data, dict):
            return default

        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)

        return default

    def _get_list(self, data: dict, *keys):
        value = self._get_value(data, *keys, default=[])

        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _has_rich_body(self, callable_model: dict):
        body = callable_model.get("body") or callable_model.get("statements") or []
        return isinstance(body, list) and len(body) > 0

    def _resolve_callable_source(self, callable_model: dict):
        for key in (
            callable_model.get("id"),
            callable_model.get("qualified_signature"),
            callable_model.get("qualifiedSignature"),
            callable_model.get("signature"),
        ):
            if key and key in self.id_index:
                return self.id_index[key]
        return None

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

        files_by_path = {
            file_model.get("path"): file_model
            for file_model in data.get("files", [])
            if file_model.get("path")
        }

        for element in data.get("elements", []):
            file_path = element.get("filePath") or element.get("file_path")
            file_model = files_by_path.get(file_path) or {
                "path": file_path,
                "packageName": element.get("packageName"),
            }

            for method in element.get("methods", []):
                self._add_callable_calls(method, file_model)

    def _add_callable_calls(self, callable_model: dict, file_model: dict):
        # When the extractor already provides a structured body, calls are
        # mapped by BodyActionMapper inside the callable BlockUnit. Creating
        # call ActionElements here would attach executable actions directly to
        # MethodUnit/CallableUnit before the body mapper runs and may violate
        # KDM containment constraints.
        if self._has_rich_body(callable_model):
            return

        source = self._resolve_callable_source(callable_model)

        if source is None:
            return

        for call in callable_model.get("calls", []):
            action = self.factory.create_action_element(
                name=self._call_action_name(call),
                kind=self._get_value(call, "kind", default="call"),
            )

            self._register_action(callable_model, call, action)

            source_file = self._get_source_file(file_model)

            self.factory.add_source_region(
                action,
                path=file_model.get("path"),
                language=self.language,
                start_line=self._get_value(call, "line", "lineStart"),
                end_line=self._get_value(call, "lineEnd", "line", "lineStart"),
                file_item=source_file,
            )

            source.codeElement.append(action)

            target = self._resolve_call_target(call)

            if target is not None:
                if self._is_constructor_call(call):
                    creates_relation = self.factory.create_creates_relation(target)
                    action.actionRelation.append(creates_relation)
                else:
                    calls_relation = self.factory.create_calls_relation(target)
                    action.actionRelation.append(calls_relation)
            # If no target can be resolved, leave the ActionElement without
            # temporary unresolved_* attributes. The call name and SourceRegion
            # still provide minimal traceability without polluting the KDM.

    def _call_action_name(self, call: dict):
        name = (
            self._get_value(call, "methodName", "method_name", "method")
            or self._get_value(call, "name")
            or "call"
        )

        if isinstance(name, str) and "." in name:
            return name.rsplit(".", 1)[-1]

        return name

    def _is_constructor_call(self, call: dict):
        return (
            self._get_value(call, "classification") == "constructor"
            or self._get_value(call, "kind") == "constructor_call"
        )

    def _add_call_traceability_metadata(self, action, call: dict):
        """Deprecated: call traceability is represented by SourceRegion and Calls/Creates."""
        return

    def _add_unresolved_call_metadata(self, action, call: dict):
        """Deprecated: unresolved calls are not serialized as debug attributes."""
        return

    def _resolve_call_target(self, call: dict):
        target_id = self._get_value(call, "target_id", "targetId", "resolvedTarget", "resolved_target")

        if target_id in self.id_index:
            return self.id_index[target_id]

        if self.external_builder is None:
            return None

        if self._is_external_or_builtin(call):
            return self.external_builder.get_or_create_external_target(call)

        # Java and other statically extracted models may provide a fully
        # qualified target signature even when it is outside the analyzed
        # project, for example java.util.List.size(). Represent this as an
        # external CallableUnit instead of serializing unresolved_* attributes.
        if target_id:
            external_call = dict(call)
            external_call.setdefault("classification", "external")
            external_call["name"] = str(target_id)
            external_call["target_id"] = str(target_id)
            return self.external_builder.get_or_create_external_target(external_call)

        return None

    def _is_external_or_builtin(self, call: dict):
        classification = call.get("classification")
        target_id = self._get_value(call, "target_id", "targetId", "resolvedTarget", "resolved_target")

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
        source_unit = self._resolve_import_source(file_model)

        if source_unit is None or not self.factory.has_feature(source_unit, "codeRelation"):
            return

        for import_model in file_model.get("imports", []):
            normalized_import = self._normalize_import_model(import_model)
            if normalized_import is None:
                continue

            target = self._resolve_import_target(normalized_import)

            if target is None:
                continue

            if self._has_code_relation(source_unit, "Imports", target):
                continue

            imports_relation = self.factory.create_imports_relation(target)

            source_file = self._get_source_file(file_model)
            self.factory.add_source_region(
                imports_relation,
                path=file_model.get("path"),
                language=self.language,
                start_line=normalized_import.get("line"),
                end_line=normalized_import.get("line"),
                file_item=source_file,
            )

            self._add_import_traceability_metadata(imports_relation, normalized_import)

            source_unit.codeRelation.append(imports_relation)

    def _resolve_import_source(self, file_model: dict):
        """Finds the KDM CodeItem that should own imports for a source file.

        Python keeps a CompilationUnit per file, so file_model['id'] normally
        resolves directly.  Java uses a MoDisco-like package hierarchy without
        CompilationUnit containers; JsonToKDMMapper registers the first ClassUnit
        in each file under the synthetic key file_import_source:<path>.
        """

        source_unit = self.id_index.get(file_model.get("id"))

        if source_unit is not None and self.factory.has_feature(source_unit, "codeRelation"):
            return source_unit

        path = file_model.get("path")
        if path:
            source_unit = self.id_index.get(f"file_import_source:{path}")
            if source_unit is not None:
                return source_unit

        return None

    def _normalize_import_model(self, import_model):
        """Normalizes Python/Java import entries to a dictionary.

        Java extractors may encode imports as strings, for example
        'android.app.Activity', or dictionaries.  This method keeps import
        traceability fields when present and derives module/name consistently.
        """

        if isinstance(import_model, str):
            text = import_model.strip()
            if not text:
                return None
            if text.endswith(".*"):
                return {
                    "module": text[:-2],
                    "name": None,
                    "target_type": "module",
                    "classification": "external",
                    "qualifiedName": text,
                }
            if "." in text:
                module, name = text.rsplit(".", 1)
            else:
                module, name = None, text
            return {
                "module": module,
                "name": name,
                "target_type": "class" if name and name[:1].isupper() else "module",
                "classification": "external",
                "qualifiedName": text,
            }

        if not isinstance(import_model, dict):
            return None

        normalized = dict(import_model)
        import_name = (
            normalized.get("qualifiedName")
            or normalized.get("qualified_name")
            or normalized.get("imported")
            or normalized.get("import")
            or normalized.get("module")
        )

        if import_name and isinstance(import_name, str):
            text = import_name.strip()
            if text.endswith(".*"):
                normalized.setdefault("module", text[:-2])
                normalized.setdefault("target_type", "module")
                normalized.setdefault("classification", "external")
            elif "." in text and not normalized.get("name"):
                module, name = text.rsplit(".", 1)
                normalized.setdefault("module", module)
                normalized.setdefault("name", name)
                normalized.setdefault("target_type", "class" if name[:1].isupper() else "module")
                normalized.setdefault("classification", "external")

        return normalized

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
        target_id = self._get_value(
            import_model,
            "target_id",
            "targetId",
            "resolvedTarget",
            "resolved_target",
        )

        # Internal resolved import.
        if target_id in self.id_index:
            return self.id_index[target_id]

        import_qn = (
            import_model.get("qualifiedName")
            or import_model.get("qualified_name")
            or import_model.get("imported")
            or import_model.get("import")
        )

        if import_qn in self.qualified_name_index:
            return self.qualified_name_index[import_qn]

        simple_name = import_model.get("name")
        if not simple_name and isinstance(import_qn, str) and "." in import_qn:
            simple_name = import_qn.rsplit(".", 1)[-1]

        if simple_name:
            candidates = self.class_name_index.get(str(simple_name), [])
            if len(candidates) == 1:
                return candidates[0]

        # External import.  Java imports may not explicitly carry
        # classification=external, so use the external builder whenever a
        # normalized module/name is available.
        if self.external_builder is not None:
            target = self.external_builder.get_or_create_external_import_target(
                import_model
            )
            if target is not None:
                return target

        return None

    def _has_code_relation(self, source, relation_type: str, target) -> bool:
        if source is None or target is None:
            return False

        for relation in list(getattr(source, "codeRelation", []) or []):
            try:
                if relation.eClass.name != relation_type:
                    continue
            except Exception:
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

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
        owner_id = (
            callable_model.get("id")
            or callable_model.get("qualifiedSignature")
            or callable_model.get("qualified_signature")
        )
        line = self._get_value(call, "line", "lineStart")
        call_id = call.get("id")

        if call_id:
            self.action_index[call_id] = action

        if owner_id is None or line is None:
            return

        candidate_names = {
            self._get_value(call, "name", "methodName"),
            self._get_value(call, "function"),
            self._get_value(call, "method", "methodName"),
            self._get_value(call, "class_name", "className"),
        }

        for name in candidate_names:
            if name:
                self.action_index[(owner_id, line, str(name))] = action

        self.action_index.setdefault((owner_id, line), []).append(action)
