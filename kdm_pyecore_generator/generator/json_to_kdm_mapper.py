class JsonToKDMMapper:
    def __init__(self, factory, inventory_builder=None):
        self.factory = factory
        self.inventory_builder = inventory_builder

        # Generic indexes.
        self.id_index = {}
        self.qualified_name_index = {}
        self.class_name_index = {}

        # Project language.
        self.language = "unknown"

        # Elements that can receive code::HasType.
        self.typable_elements = []

        # Elements that can receive code::HasValue.
        self.value_elements = []

        # StorableUnit index used by access, return and value resolvers.
        self.storable_index = {}

        # Generic model support.
        self.compilation_unit_by_path = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transform_structure(self, data: dict):
        """
        Backward-compatible method.

        Creates a new Segment and maps the CodeModel into it.
        Useful when no InventoryModel is created beforehand.
        """
        project_name = data.get("projectName", "UnknownProject")
        segment = self.factory.create_segment(project_name)

        return self.transform_structure_into_segment(data, segment)

    def transform_structure_into_segment(self, data: dict, segment):
        """
        Maps the JSON structure into an existing Segment.

        Supports both:

        1. The older py2kdm format, where classes and functions are nested
           inside files[].

        2. The generic static model format, where language-specific extractors
           produce:

              files[]
              elements[]
              relationships[]

        This allows Python, Java and future extractors to share the same
        JSON-to-KDM mapper.
        """
        project_name = data.get("projectName", "UnknownProject")
        self.language = data.get("language", "unknown")

        code_model = self.factory.create_code_model(f"{project_name}_CodeModel")
        segment.model.append(code_model)

        # First create CompilationUnit elements for every source file.
        for file_model in data.get("files", []):
            self._map_file(code_model, file_model)

        # Then map language-independent structural elements.
        for element in data.get("elements", []):
            self._map_generic_element(code_model, element)

        # Finally map generic relationships when possible.
        self._map_generic_relationships(data)

        return segment

    # ------------------------------------------------------------------
    # Registration and metadata helpers
    # ------------------------------------------------------------------

    def _register(self, json_id: str, kdm_element, model_element: dict = None):
        if json_id:
            self.id_index[json_id] = kdm_element

        if not model_element:
            return

        qualified_name = (
            model_element.get("qualified_name")
            or model_element.get("qualifiedName")
            or model_element.get("qualifiedSignature")
            or model_element.get("qualified_signature")
        )

        name = model_element.get("name")

        element_type = (
            model_element.get("type")
            or model_element.get("kind")
        )

        if qualified_name:
            self.qualified_name_index[qualified_name] = kdm_element
            self.id_index.setdefault(qualified_name, kdm_element)

        if element_type in {"class", "interface", "enum"} and name:
            self.class_name_index.setdefault(name, []).append(kdm_element)

    def _add_common_metadata(self, kdm_element, model_element: dict):
        """
        Adds non-physical metadata.

        Physical traceability is represented using source::SourceRef and
        source::SourceRegion. Structural information is represented by KDM
        containment and native properties where possible.

        Important:
        Do not add the tag 'kind' as an Attribute. The validator treats it as
        obsolete in this context. Use element_kind or method_kind instead.
        """
        metadata = {
            "original_id": model_element.get("id"),
            "json_type": model_element.get("type") or model_element.get("kind"),
            "qualified_name": (
                model_element.get("qualified_name")
                or model_element.get("qualifiedName")
            ),
            "qualified_signature": (
                model_element.get("qualified_signature")
                or model_element.get("qualifiedSignature")
            ),
            "package": (
                model_element.get("package_name")
                or model_element.get("packageName")
            ),
        }

        self.factory.add_attributes_from_dict(kdm_element, metadata)

    def _append_code_element(self, parent, child):
        if self.factory.has_feature(parent, "codeElement"):
            parent.codeElement.append(child)
            return True

        return False

    def _append_code_relation(self, source, relation):
        if self.factory.has_feature(source, "codeRelation"):
            source.codeRelation.append(relation)
            return True

        return False

    def _append_action_relation(self, source, relation):
        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return True

        return False

    def _safe_join(self, values):
        if not values:
            return None

        return ", ".join(str(value) for value in values)

    # ------------------------------------------------------------------
    # File mapping
    # ------------------------------------------------------------------

    def _map_file(self, code_model, file_model: dict):
        unit_name = file_model.get("path", file_model.get("name", "unknown.py"))

        compilation_unit = self.factory.create_compilation_unit(unit_name)
        code_model.codeElement.append(compilation_unit)

        path = file_model.get("path")
        if path:
            self.compilation_unit_by_path[path] = compilation_unit
            self.id_index.setdefault(path, compilation_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            compilation_unit,
            path=file_model.get("path"),
            language=self.language,
            file_item=source_file,
        )

        self._add_common_metadata(compilation_unit, file_model)

        self._register(
            file_model.get("id") or file_model.get("path"),
            compilation_unit,
            file_model,
        )

        # Backward-compatible mapping for the older nested Python model.
        for cls in file_model.get("classes", []):
            self._map_class(compilation_unit, cls, file_model)

        for func in file_model.get("functions", []):
            self._map_function(compilation_unit, func, file_model)

    # ------------------------------------------------------------------
    # Backward-compatible py2kdm structural mapping
    # ------------------------------------------------------------------

    def _map_class(self, parent, cls: dict, file_model: dict):
        class_unit = self.factory.create_class_unit(
            cls.get("name", "AnonymousClass")
        )
        parent.codeElement.append(class_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            class_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=cls.get("line_start"),
            end_line=cls.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(class_unit, cls)
        self._add_decorator_metadata(class_unit, cls)

        self._register(cls.get("id"), class_unit, cls)

        for attr in cls.get("attributes", []):
            self._map_storable(class_unit, attr, file_model, cls)

        for attr in cls.get("instance_attributes", []):
            self._map_storable(class_unit, attr, file_model, cls)

        for method in cls.get("methods", []):
            self._map_method(class_unit, method, file_model)

    def _map_method(self, parent, method: dict, file_model: dict):
        method_unit = self.factory.create_method_unit(
            method.get("name", "anonymous_method")
        )
        parent.codeElement.append(method_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            method_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=method.get("line_start"),
            end_line=method.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(method_unit, method)
        self._add_callable_signature_metadata(method_unit, method)

        self._register(method.get("id"), method_unit, method)

        for param in method.get("parameters", []):
            self._map_parameter(method_unit, param)

        for var in method.get("local_variables", []):
            self._map_storable(method_unit, var, file_model, method)

        for var in method.get("context_variables", []):
            self._map_storable(method_unit, var, file_model, method)

    def _map_function(self, parent, func: dict, file_model: dict):
        callable_unit = self.factory.create_callable_unit(
            func.get("name", "anonymous_function")
        )
        parent.codeElement.append(callable_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            callable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=func.get("line_start"),
            end_line=func.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(callable_unit, func)
        self._add_callable_signature_metadata(callable_unit, func)

        self._register(func.get("id"), callable_unit, func)

        for param in func.get("parameters", []):
            self._map_parameter(callable_unit, param)

        for var in func.get("local_variables", []):
            self._map_storable(callable_unit, var, file_model, func)

        for var in func.get("context_variables", []):
            self._map_storable(callable_unit, var, file_model, func)

    def _map_parameter(self, parent, param: dict):
        parameter_unit = self.factory.create_parameter_unit(
            param.get("name", "param")
        )
        parent.codeElement.append(parameter_unit)

        self._register_typable(parameter_unit, param)

        metadata = {
            "type_resolution": param.get("type_resolution"),
            "declared_type": param.get("type"),
            "resolved_type": param.get("resolvedType") or param.get("resolved_type"),
            "parameter_kind": param.get("kind"),
            "parameter_index": param.get("index"),
            "default_value": param.get("default_value"),
        }

        self.factory.add_attributes_from_dict(parameter_unit, metadata)

    def _map_storable(
        self,
        parent,
        var: dict,
        file_model: dict,
        owner_model: dict = None,
    ):
        storable_unit = self.factory.create_storable_unit(
            var.get("name", "variable")
        )
        parent.codeElement.append(storable_unit)

        self._register_typable(storable_unit, var)
        self._register_value_element(storable_unit, var, owner_model)
        self._register_storable(storable_unit, var, owner_model)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            storable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=var.get("line"),
            end_line=var.get("line"),
            file_item=source_file,
        )

        metadata = {
            "full_name": var.get("full_name"),
            "type_resolution": var.get("type_resolution"),
            "declared_type": var.get("type"),
            "resolved_type": var.get("resolvedType") or var.get("resolved_type"),
        }

        self.factory.add_attributes_from_dict(storable_unit, metadata)

    # ------------------------------------------------------------------
    # Generic static model mapping
    # ------------------------------------------------------------------

    def _map_generic_element(self, code_model, element: dict):
        """
        Maps a language-independent static model element.

        Expected generic element kinds:

            class | interface | enum | function | callable

        The mapper avoids language-specific branches. Java, Python and future
        extractors should all produce this generic representation.
        """
        kind = element.get("kind") or element.get("type")

        if kind in {"class", "interface", "enum"}:
            parent = self._find_parent_compilation_unit(code_model, element)
            self._map_generic_class_like(parent, element)
            return

        if kind in {"function", "callable"}:
            parent = self._find_parent_compilation_unit(code_model, element)
            self._map_generic_function(parent, element)
            return

    def _find_parent_compilation_unit(self, code_model, element: dict):
        file_path = element.get("filePath") or element.get("file_path")

        if file_path and file_path in self.compilation_unit_by_path:
            return self.compilation_unit_by_path[file_path]

        return code_model

    def _generic_file_model(self, element_or_relation: dict):
        path = (
            element_or_relation.get("filePath")
            or element_or_relation.get("file_path")
            or element_or_relation.get("sourceFile")
            or element_or_relation.get("source_file")
            or element_or_relation.get("path")
        )

        return {"path": path} if path else {}

    def _map_generic_class_like(self, parent, element: dict):
        kind = element.get("kind") or element.get("type")
        name = element.get("name", "AnonymousClass")

        class_unit = self.factory.create_class_unit(name)
        self._append_code_element(parent, class_unit)

        file_model = self._generic_file_model(element)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            class_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=element.get("line_start") or element.get("lineStart"),
            end_line=element.get("line_end") or element.get("lineEnd"),
            file_item=source_file,
        )

        # Do not add qualified_name or package here. They are added by
        # _add_common_metadata. Do not use tag 'kind'; use element_kind.
        self.factory.add_attributes_from_dict(
            class_unit,
            {
                "element_kind": kind,
                "modifiers": self._safe_join(element.get("modifiers", [])),
                "annotations": self._safe_join(element.get("annotations", [])),
                "extends_types": self._safe_join(element.get("extendsTypes", [])),
                "implements_types": self._safe_join(
                    element.get("implementsTypes", [])
                ),
            },
        )

        self._add_common_metadata(class_unit, element)

        self._register(
            element.get("id")
            or element.get("qualifiedName")
            or element.get("qualified_name"),
            class_unit,
            element,
        )

        for field in element.get("fields", []):
            self._map_generic_field(class_unit, field, element)

        for method in element.get("methods", []):
            self._map_generic_method(class_unit, method, element)

    def _map_generic_function(self, parent, element: dict):
        callable_unit = self.factory.create_callable_unit(
            element.get("name", "anonymous_function")
        )
        self._append_code_element(parent, callable_unit)

        file_model = self._generic_file_model(element)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            callable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=element.get("line_start") or element.get("lineStart"),
            end_line=element.get("line_end") or element.get("lineEnd"),
            file_item=source_file,
        )

        self._add_common_metadata(callable_unit, element)
        self._add_callable_signature_metadata(callable_unit, element)

        qualified_signature = (
            element.get("qualifiedSignature")
            or element.get("qualified_signature")
        )

        self._register(
            element.get("id") or qualified_signature,
            callable_unit,
            element,
        )

        for param in element.get("parameters", []):
            self._map_generic_parameter(callable_unit, param, element)

        resolved_return_type = (
            element.get("resolvedReturnType")
            or element.get("resolved_return_type")
        )

        if resolved_return_type and resolved_return_type != "void":
            normalized_return = {
                "name": f"{element.get('name', 'function')}:return",
                "resolved_type_id": self._infer_type_id(resolved_return_type),
                "resolved_type_qualified_name": resolved_return_type,
            }

            self._register_typable(callable_unit, normalized_return)

    def _map_generic_field(self, parent, field: dict, owner_element: dict):
        storable_unit = self.factory.create_storable_unit(
            field.get("name", "field")
        )
        self._append_code_element(parent, storable_unit)

        resolved_type = field.get("resolvedType") or field.get("resolved_type")

        self.factory.add_attributes_from_dict(
            storable_unit,
            {
                "declared_type": field.get("type"),
                "resolved_type": resolved_type,
                "modifiers": self._safe_join(field.get("modifiers", [])),
                "annotations": self._safe_join(field.get("annotations", [])),
            },
        )

        normalized_field = dict(field)
        normalized_field["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_field["resolved_type_qualified_name"] = resolved_type

        self._register_typable(storable_unit, normalized_field)
        self._register_storable(storable_unit, normalized_field, owner_element)

        owner_qn = (
            owner_element.get("qualifiedName")
            or owner_element.get("qualified_name")
            or owner_element.get("name")
        )

        if owner_qn and field.get("name"):
            field_key = f"{owner_qn}.{field.get('name')}"
            self.storable_index[field_key] = storable_unit
            self.id_index.setdefault(field_key, storable_unit)

    def _map_generic_method(self, parent, method: dict, owner_element: dict):
        method_unit = self.factory.create_method_unit(
            method.get("name", "anonymous_method")
        )
        self._append_code_element(parent, method_unit)

        resolved_return_type = (
            method.get("resolvedReturnType")
            or method.get("resolved_return_type")
        )

        qualified_signature = (
            method.get("qualifiedSignature")
            or method.get("qualified_signature")
        )

        # Do not add qualified_signature here. It is added by
        # _add_common_metadata. Do not use tag 'kind'; use method_kind.
        self.factory.add_attributes_from_dict(
            method_unit,
            {
                "method_kind": method.get("kind"),
                "signature": method.get("signature"),
                "return_type": method.get("returnType") or method.get("return_type"),
                "resolved_return_type": resolved_return_type,
                "modifiers": self._safe_join(method.get("modifiers", [])),
                "annotations": self._safe_join(method.get("annotations", [])),
            },
        )

        self._add_common_metadata(method_unit, method)

        self._register(
            method.get("id") or qualified_signature,
            method_unit,
            method,
        )

        for param in method.get("parameters", []):
            self._map_generic_parameter(method_unit, param, method)

        if resolved_return_type and resolved_return_type != "void":
            normalized_return = {
                "name": f"{method.get('name', 'method')}:return",
                "resolved_type_id": self._infer_type_id(resolved_return_type),
                "resolved_type_qualified_name": resolved_return_type,
            }

            self._register_typable(method_unit, normalized_return)

    def _map_generic_parameter(self, parent, param: dict, owner_callable: dict = None):
        parameter_unit = self.factory.create_parameter_unit(
            param.get("name", "param")
        )
        self._append_code_element(parent, parameter_unit)

        resolved_type = param.get("resolvedType") or param.get("resolved_type")

        self.factory.add_attributes_from_dict(
            parameter_unit,
            {
                "declared_type": param.get("type"),
                "resolved_type": resolved_type,
                "parameter_kind": param.get("kind"),
                "parameter_index": param.get("index"),
                "default_value": param.get("default_value"),
            },
        )

        normalized_param = dict(param)
        normalized_param["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_param["resolved_type_qualified_name"] = resolved_type

        self._register_typable(parameter_unit, normalized_param)

        callable_qs = None
        if owner_callable:
            callable_qs = (
                owner_callable.get("qualifiedSignature")
                or owner_callable.get("qualified_signature")
                or owner_callable.get("id")
            )

        if callable_qs and param.get("name"):
            param_key = f"{callable_qs}:parameter:{param.get('name')}"
            self.id_index.setdefault(param_key, parameter_unit)

    # ------------------------------------------------------------------
    # Generic relationships
    # ------------------------------------------------------------------

    def _map_generic_relationships(self, data: dict):
        relationships = data.get("relationships", [])

        if not relationships:
            return

        for relationship in relationships:
            relation_type = relationship.get("type")

            if relation_type == "calls":
                self._map_generic_calls_relationship(relationship)
            elif relation_type == "imports":
                self._map_generic_imports_relationship(relationship)
            elif relation_type == "extends":
                self._map_generic_extends_relationship(relationship)
            elif relation_type == "implements":
                self._map_generic_implements_relationship(relationship)
            elif relation_type == "uses_type":
                self._map_generic_uses_type_relationship(relationship)

    def _map_generic_calls_relationship(self, relationship: dict):
        source_key = relationship.get("source")
        target_key = relationship.get("target")

        source = self._resolve_indexed_element(source_key)
        target = self._resolve_indexed_element(target_key)

        if source is None:
            return

        body_block = self._get_or_create_callable_body(source)

        action = self.factory.create_action_element(
            name=self._call_action_name(target_key),
            kind="call",
        )

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=relationship.get("line"),
            end_line=relationship.get("line"),
            file_item=source_file,
        )

        # Do not add attribute 'target'. It is treated as obsolete by the
        # validator. Use called_signature instead.
        relationship_line = relationship.get("line") or relationship.get("lineStart") or relationship.get("line_start")

        self.factory.add_attributes_from_dict(
            action,
            {
                "original_id": self._generic_relationship_action_id(relationship),
                "call_source": source_key,
                "called_signature": target_key,
                "relationship_type": "calls",
                "source_line": relationship_line,
            },
        )

        self._append_code_element(body_block, action)

        if target is not None:
            calls_relation = self.factory.create_calls_relation(target)
            self._append_action_relation(action, calls_relation)
        else:
            self.factory.add_attributes_from_dict(
                action,
                {
                    "resolution_status": "unresolved",
                    "unresolved_target_name": target_key,
                },
            )

    def _map_generic_imports_relationship(self, relationship: dict):
        source_key = relationship.get("source")
        target_key = relationship.get("target")

        source = self._resolve_indexed_element(source_key)
        target = self._resolve_indexed_element(target_key)

        if source is None or target is None:
            return

        imports_relation = self.factory.create_imports_relation(target)

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            imports_relation,
            path=file_model.get("path"),
            language=self.language,
            start_line=relationship.get("line"),
            end_line=relationship.get("line"),
            file_item=source_file,
        )

        self._append_code_relation(source, imports_relation)

    def _map_generic_extends_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))
        target = self._resolve_indexed_element(relationship.get("target"))

        if source is None or target is None:
            return

        extends_relation = self.factory.create_extends_relation(target)
        self._append_code_relation(source, extends_relation)

    def _map_generic_implements_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))
        target = self._resolve_indexed_element(relationship.get("target"))

        if source is None:
            return

        self.factory.add_attributes_from_dict(
            source,
            {
                "implements_type": relationship.get("target"),
            },
        )

        if target is not None:
            imports_relation = self.factory.create_imports_relation(target)
            self._append_code_relation(source, imports_relation)

    def _map_generic_uses_type_relationship(self, relationship: dict):
        """
        uses_type relations are represented mainly through HasType by the
        TypeRelationResolver, based on typable_elements collected while mapping
        fields, parameters and return types.

        This method intentionally avoids registering duplicated typable entries.
        """
        return

    # ------------------------------------------------------------------
    # Callable bodies and calls
    # ------------------------------------------------------------------

    def _generic_relationship_action_id(self, relationship: dict):
        """
        Builds a stable identifier for an ActionElement created from a generic
        relationship.

        Java models may contain several calls to the same target inside the
        same callable, for example repeated builder.append(...) calls. The KDM
        validator uses traceability identifiers to distinguish valid repeated
        actions. Therefore each generic calls relationship must generate a
        unique original_id based on source, target and source location.
        """

        relation_type = relationship.get("type") or "relationship"
        source = relationship.get("source") or "unknown_source"
        target = relationship.get("target") or "unknown_target"
        source_file = (
            relationship.get("sourceFile")
            or relationship.get("source_file")
            or relationship.get("file")
            or "unknown_file"
        )
        line = (
            relationship.get("line")
            or relationship.get("lineStart")
            or relationship.get("line_start")
            or "unknown_line"
        )

        return f"generic:{relation_type}:{source}:{target}:{source_file}:{line}"

    def _get_or_create_callable_body(self, callable_unit):
        """
        Returns the body BlockUnit of a MethodUnit or CallableUnit.

        KDM validation requires executable ActionElement nodes to be contained
        in a BlockUnit, not directly inside MethodUnit or CallableUnit.
        """
        if not self.factory.has_feature(callable_unit, "codeElement"):
            return callable_unit

        for child in callable_unit.codeElement:
            if child.eClass.name == "BlockUnit":
                return child

        block = self.factory.create_block_unit(name="body", kind="body")

        self.factory.add_attributes_from_dict(
            block,
            {
                "role": "callable_body",
            },
        )

        callable_unit.codeElement.append(block)

        return block

    def _call_action_name(self, target_key: str):
        """
        Extracts the called method name from a qualified signature.

        Example:
            com.example.Repository.findNameById(java.lang.Long)

        must become:
            findNameById

        A naive rsplit('.', 1) fails because parameter types may also contain
        dots, e.g. java.lang.Long.
        """
        if not target_key:
            return "call"

        signature = str(target_key)

        if "(" in signature:
            before_params = signature.split("(", 1)[0]
        else:
            before_params = signature

        method_name = before_params.rsplit(".", 1)[-1]

        return method_name or "call"

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def _resolve_indexed_element(self, key: str):
        if not key:
            return None

        if key in self.id_index:
            return self.id_index[key]

        if key in self.qualified_name_index:
            return self.qualified_name_index[key]

        simple_name = key.split(".")[-1]
        candidates = self.class_name_index.get(simple_name, [])

        if len(candidates) == 1:
            return candidates[0]

        return None

    def _infer_type_id(self, qualified_name: str):
        if not qualified_name:
            return None

        primitive_or_builtin = {
            "int",
            "long",
            "short",
            "byte",
            "float",
            "double",
            "boolean",
            "char",
            "void",
            "str",
            "string",
            "bool",
            "None",
            "NoneType",
        }

        if qualified_name in primitive_or_builtin:
            return f"builtin_type:{qualified_name}"

        if qualified_name.startswith("java.lang."):
            java_name = qualified_name.replace("java.lang.", "")

            if java_name in {
                "String",
                "Integer",
                "Long",
                "Boolean",
                "Float",
                "Double",
                "Short",
                "Byte",
                "Character",
            }:
                return f"external_type:{qualified_name}"

        return f"external_type:{qualified_name}"

    # ------------------------------------------------------------------
    # Callable and signature metadata
    # ------------------------------------------------------------------

    def _add_callable_signature_metadata(self, callable_unit, callable_model: dict):
        """
        Adds lightweight signature metadata to MethodUnit or CallableUnit.

        Do not add qualified_signature here because _add_common_metadata
        already adds it. This avoids duplicate Attribute validation errors.
        """
        metadata = {
            "method_kind": callable_model.get("method_kind"),
            "is_async": callable_model.get("is_async"),
            "return_annotation": callable_model.get("return_annotation"),
            "signature": callable_model.get("signature"),
            "return_type": (
                callable_model.get("returnType")
                or callable_model.get("return_type")
            ),
            "resolved_return_type": (
                callable_model.get("resolvedReturnType")
                or callable_model.get("resolved_return_type")
            ),
        }

        self.factory.add_attributes_from_dict(callable_unit, metadata)
        self._add_decorator_metadata(callable_unit, callable_model)

    def _add_decorator_metadata(self, kdm_element, model_element: dict):
        decorators = model_element.get("decorators", [])

        if not decorators:
            return

        self.factory.add_attribute(
            kdm_element,
            "decorators",
            ", ".join(str(decorator) for decorator in decorators),
        )

        for index, decorator in enumerate(decorators):
            self.factory.add_attribute(
                kdm_element,
                f"decorator_{index}",
                decorator,
            )

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def _register_typable(self, kdm_element, source_model: dict):
        if not source_model:
            return

        self.typable_elements.append(
            {
                "kdm_element": kdm_element,
                "source_model": source_model,
            }
        )

    def _register_value_element(
        self,
        kdm_element,
        source_model: dict,
        owner_model: dict = None,
    ):
        self.value_elements.append(
            {
                "kdm_element": kdm_element,
                "source_model": source_model,
                "owner_id": owner_model.get("id") if owner_model else None,
            }
        )

    def _get_source_file(self, file_model: dict):
        if self.inventory_builder is None:
            return None

        return self.inventory_builder.get_source_file_by_path(
            file_model.get("path")
        )

    def _register_storable(self, storable_unit, var: dict, owner_model: dict = None):
        keys = set()

        name = var.get("name")
        full_name = var.get("full_name")
        defined_in = var.get("defined_in")
        owner_id = owner_model.get("id") if owner_model else None
        owner_qn = None

        if owner_model:
            owner_qn = (
                owner_model.get("qualifiedName")
                or owner_model.get("qualified_name")
                or owner_model.get("qualifiedSignature")
                or owner_model.get("qualified_signature")
            )

        if name:
            keys.add(name)

        if full_name:
            keys.add(full_name)

        if defined_in and name:
            keys.add(f"{defined_in}.{name}")

        if owner_id and name:
            keys.add((owner_id, name))

        if owner_id and full_name:
            keys.add((owner_id, full_name))

        if owner_qn and name:
            keys.add(f"{owner_qn}.{name}")

        for key in keys:
            self.storable_index[key] = storable_unit
            self.id_index.setdefault(key, storable_unit)
