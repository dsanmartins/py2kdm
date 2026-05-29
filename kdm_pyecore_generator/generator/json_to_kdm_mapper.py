class JsonToKDMMapper:
    def __init__(self, factory, inventory_builder=None, external_builder=None):
        self.factory = factory
        self.inventory_builder = inventory_builder
        self.external_builder = external_builder

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
        self.package_by_qualified_name = {}

        # Formal KDM extension support for Java annotations and Python decorators.
        self.segment = None
        self.annotation_extension_family = None
        self.annotation_stereotypes = {}

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
        self.segment = segment

        code_model = self.factory.create_code_model(f"{project_name}_CodeModel")
        segment.model.append(code_model)

        # First register source files. For Python, source files are also
        # represented as CompilationUnit containers. For Java, the code model
        # is organized in a MoDisco-like package hierarchy and SourceFile
        # elements remain in the InventoryModel for traceability.
        for file_model in data.get("files", []):
            self._map_file(code_model, file_model)

        # Then map language-independent structural elements.
        for element in data.get("elements", []):
            self._map_generic_element(code_model, element)

        # Java inheritance declarations are often attached directly to class
        # elements rather than emitted as generic relationship objects.  They
        # must be processed after all classes are registered so internal
        # superclass/interface targets can be resolved inside the package
        # hierarchy.
        if self.language == "java":
            self._map_declared_java_inheritance(data)

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

        if element_type in {"class", "interface", "enum", "annotation", "annotation_type"} and name:
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
            "qualified_name": (
                model_element.get("qualified_name")
                or model_element.get("qualifiedName")
            ),
            "package": (
                model_element.get("package_name")
                or model_element.get("packageName")
            ),
        }

        self.factory.add_attributes_from_dict(kdm_element, metadata)

    def _append_code_element(self, parent, child):
        if parent is None or child is None:
            return False

        if self.factory.has_feature(parent, "codeElement"):
            parent.codeElement.append(child)
            return True

        return False

    def _append_code_relation(self, source, relation):
        if source is None or relation is None:
            return False

        if self.factory.has_feature(source, "codeRelation"):
            source.codeRelation.append(relation)
            return True

        return False

    def _append_action_relation(self, source, relation):
        if source is None or relation is None:
            return False

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
        path = file_model.get("path")

        # Java uses a MoDisco-like layout: Package -> ... -> ClassUnit.
        # The physical file is still represented by InventoryModel/SourceFile
        # and every semantic element keeps its SourceRegion. Therefore we do
        # not create a CompilationUnit container for Java source files.
        if self.language == "java":
            source_file = self._get_source_file(file_model)
            if path and source_file is not None:
                self.id_index.setdefault(path, source_file)
            return

        unit_name = file_model.get("path", file_model.get("name", "unknown.py"))

        compilation_unit = self.factory.create_compilation_unit(unit_name)
        code_model.codeElement.append(compilation_unit)

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
        self._add_native_annotations(class_unit, cls)

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
        self._add_native_annotations(method_unit, method)

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
        self._add_native_annotations(callable_unit, func)

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

        if self.factory.has_feature(parent, "parameterUnit"):
            parent.parameterUnit.append(parameter_unit)
        else:
            parent.codeElement.append(parameter_unit)

        self._apply_parameter_native_properties(parameter_unit, param)
        self._add_native_annotations(parameter_unit, param)

        self._register_typable(parameter_unit, param)

        # Keep only metadata that has no native KDM counterpart in this
        # generator. Parameter kind and position are represented by
        # ParameterUnit.kind and ParameterUnit.pos. Type information is
        # represented by native type and HasType.
        metadata = {
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

        self._apply_data_native_properties(
            storable_unit,
            var,
            default_kind="local",
        )
        self._add_native_annotations(storable_unit, var)

        # Keep only metadata that has no reliable native KDM counterpart.
        # declared_type/resolved_type are represented by type and HasType.
        metadata = {
            "full_name": var.get("full_name"),
            "value_kind": var.get("value_kind") or var.get("valueKind"),
            "value_type": var.get("value_type") or var.get("valueType"),
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

        if kind in {"class", "interface", "enum", "annotation", "annotation_type"}:
            parent = self._find_parent_container(code_model, element)
            self._map_generic_class_like(parent, element)
            return

        if kind in {"function", "callable"}:
            parent = self._find_parent_container(code_model, element)
            self._map_generic_function(parent, element)
            return

    def _find_parent_container(self, code_model, element: dict):
        if self.language == "java":
            package_name = self._java_package_name(element)
            if package_name:
                return self._get_or_create_package_hierarchy(code_model, package_name)
            return code_model

        file_path = element.get("filePath") or element.get("file_path")

        if file_path and file_path in self.compilation_unit_by_path:
            return self.compilation_unit_by_path[file_path]

        return code_model

    def _java_package_name(self, element: dict):
        package_name = (
            element.get("packageName")
            or element.get("package_name")
            or element.get("package")
        )

        if package_name:
            return str(package_name).strip()

        qualified_name = (
            element.get("qualifiedName")
            or element.get("qualified_name")
        )

        name = element.get("name")

        if qualified_name and name and str(qualified_name).endswith(f".{name}"):
            return str(qualified_name)[: -(len(str(name)) + 1)]

        if qualified_name and "." in str(qualified_name):
            return str(qualified_name).rsplit(".", 1)[0]

        return None

    def _get_or_create_package_hierarchy(self, code_model, package_name: str):
        parent = code_model
        parts = [part for part in str(package_name).split(".") if part]
        qualified_parts = []

        for part in parts:
            qualified_parts.append(part)
            qualified_package_name = ".".join(qualified_parts)

            package = self.package_by_qualified_name.get(qualified_package_name)

            if package is None:
                package = self.factory.create_package(part)
                self._append_code_element(parent, package)
                self.package_by_qualified_name[qualified_package_name] = package
                self.id_index.setdefault(f"package:{qualified_package_name}", package)
                self.factory.add_attribute(package, "qualified_name", qualified_package_name)

            parent = package

        return parent

    def _generic_file_model(self, element_or_relation: dict):
        path = (
            element_or_relation.get("filePath")
            or element_or_relation.get("file_path")
            or element_or_relation.get("sourceFile")
            or element_or_relation.get("source_file")
            or element_or_relation.get("path")
        )

        return {"path": path} if path else {}

    def _register_java_file_import_source(self, file_model: dict, code_item) -> None:
        """Registers the CodeItem that represents file-scoped Java imports.

        In Java mode, SourceFile remains in the InventoryModel and classes are
        contained under Package elements.  Because code::Imports must be owned
        by a KDM code element, the first class mapped from each file is used as
        the import source for that file.  The mapping is intentionally stored in
        id_index with a synthetic key so ReferenceResolver can attach Imports
        without reintroducing CompilationUnit containers.
        """

        if not isinstance(file_model, dict) or code_item is None:
            return

        path = file_model.get("path")
        if path:
            self.id_index.setdefault(f"file_import_source:{path}", code_item)


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

        # Java no longer uses CompilationUnit as the structural container.
        # Imports are file-scoped, so we register the first ClassUnit mapped
        # from each source file as the KDM CodeItem that receives code::Imports
        # relations for that file.  This preserves import semantics while
        # keeping the MoDisco-like Package -> ClassUnit layout.
        if self.language == "java":
            self._register_java_file_import_source(file_model, class_unit)

        self._apply_class_native_properties(class_unit, element)
        self._add_common_metadata(class_unit, element)
        self._add_native_annotations(class_unit, element)

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

        self._apply_callable_native_properties(callable_unit, element)

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
        self._add_native_annotations(callable_unit, element)

        qualified_signature = (
            element.get("qualifiedSignature")
            or element.get("qualified_signature")
        )

        self._register(
            element.get("id") or qualified_signature,
            callable_unit,
            element,
        )

        signature = self._create_callable_signature(
            owner=callable_unit,
            callable_model=element,
        )

        for param in element.get("parameters", []):
            self._map_generic_parameter(signature, param, element)

        self._map_return_parameter(signature, element)

    def _map_generic_field(self, parent, field: dict, owner_element: dict):
        storable_unit = self.factory.create_storable_unit(
            field.get("name", "field")
        )
        self._append_code_element(parent, storable_unit)

        file_model = self._generic_file_model(owner_element)
        source_file = self._get_source_file(file_model)
        field_line = (
            field.get("line")
            or field.get("lineStart")
            or field.get("line_start")
        )
        field_end_line = (
            field.get("lineEnd")
            or field.get("line_end")
            or field_line
        )

        self.factory.add_source_region(
            storable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=field_line,
            end_line=field_end_line,
            file_item=source_file,
        )

        resolved_type = field.get("resolvedType") or field.get("resolved_type")

        self._apply_data_native_properties(
            storable_unit,
            field,
            default_kind="unknown",
        )
        self._add_native_annotations(storable_unit, field)

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

        self._apply_method_native_properties(method_unit, method)

        file_model = self._generic_file_model(owner_element)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            method_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=method.get("line_start") or method.get("lineStart"),
            end_line=method.get("line_end") or method.get("lineEnd"),
            file_item=source_file,
        )

        self._add_common_metadata(method_unit, method)
        self._add_native_annotations(method_unit, method)

        qualified_signature = (
            method.get("qualifiedSignature")
            or method.get("qualified_signature")
        )

        self._register(
            method.get("id") or qualified_signature,
            method_unit,
            method,
        )

        signature = self._create_callable_signature(
            owner=method_unit,
            callable_model=method,
        )

        for param in method.get("parameters", []):
            self._map_generic_parameter(signature, param, method)

        self._map_return_parameter(signature, method)

        for local_var in (
            method.get("localVariables", [])
            or method.get("local_variables", [])
        ):
            self._map_generic_local_variable(method_unit, local_var, method, owner_element)

    def _map_generic_parameter(self, parent, param: dict, owner_callable: dict = None):
        parameter_unit = self.factory.create_parameter_unit(
            param.get("name", "param")
        )
        self._append_parameter_unit(parent, parameter_unit)

        resolved_type = (
            param.get("resolvedType")
            or param.get("resolved_type")
            or param.get("type")
        )

        self._apply_parameter_native_properties(parameter_unit, param)
        self._add_native_annotations(parameter_unit, param)

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
            # Parameters are intentionally not registered in storable_index:
            # Reads/Writes in this generator are restricted to StorableUnit.
            self.id_index.setdefault((callable_qs, "parameter", param.get("name")), parameter_unit)

    def _map_generic_local_variable(
        self,
        parent,
        local_var: dict,
        owner_callable: dict,
        owner_element: dict = None,
    ):
        """Maps Java/generic localVariables entries to StorableUnit."""

        storable_unit = self.factory.create_storable_unit(
            local_var.get("name", "local_variable")
        )
        self._append_code_element(parent, storable_unit)

        resolved_type = (
            local_var.get("resolvedType")
            or local_var.get("resolved_type")
            or local_var.get("assignedType")
            or local_var.get("assigned_type")
        )

        normalized_var = dict(local_var)
        normalized_var["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_var["resolved_type_qualified_name"] = resolved_type

        self._register_typable(storable_unit, normalized_var)
        self._register_value_element(storable_unit, normalized_var, owner_callable)
        self._register_storable(storable_unit, normalized_var, owner_callable)

        callable_qs = (
            owner_callable.get("qualifiedSignature")
            or owner_callable.get("qualified_signature")
            or owner_callable.get("id")
        )

        if callable_qs and local_var.get("name"):
            self.storable_index.setdefault(
                (callable_qs, local_var.get("name")),
                storable_unit,
            )
            self.id_index.setdefault(
                f"{callable_qs}:local:{local_var.get('name')}",
                storable_unit,
            )

        file_model = self._generic_file_model(owner_element or owner_callable)
        source_file = self._get_source_file(file_model)
        line = local_var.get("line") or local_var.get("lineStart") or local_var.get("line_start")

        self.factory.add_source_region(
            storable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._apply_data_native_properties(
            storable_unit,
            local_var,
            default_kind="local",
        )
        self._add_native_annotations(storable_unit, local_var)



    # ------------------------------------------------------------------
    # Native KDM class/data metadata helpers
    # ------------------------------------------------------------------

    def _apply_class_native_properties(self, class_unit, class_model: dict):
        """
        Maps class-level JSON metadata to native KDM properties when
        available.

        Redundant extractor attributes such as element_kind, modifiers and
        annotations are intentionally not emitted as kdm:Attribute elements.
        """

        modifiers = set(class_model.get("modifiers", []) or [])

        if self.factory.has_feature(class_unit, "export"):
            class_unit.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(class_unit, "isFinal"):
            class_unit.isFinal = "final" in modifiers

        if self.factory.has_feature(class_unit, "isAbstract"):
            class_unit.isAbstract = "abstract" in modifiers

    def _apply_data_native_properties(
        self,
        data_element,
        data_model: dict,
        default_kind: str = "unknown",
    ):
        """
        Maps variable, field and local-variable metadata to native KDM
        properties when supported by the concrete metaclass.

        Type information is handled by TypeRelationResolver through the native
        type reference and HasType. Annotations are represented as kdm:Annotation.
        """

        modifiers = set(data_model.get("modifiers", []) or [])

        if self.factory.has_feature(data_element, "kind"):
            data_element.kind = self._normalize_storable_kind(
                data_model.get("kind") or data_model.get("storableKind") or default_kind
            )

        if self.factory.has_feature(data_element, "export"):
            data_element.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(data_element, "isStatic"):
            data_element.isStatic = "static" in modifiers

        if self.factory.has_feature(data_element, "isFinal"):
            data_element.isFinal = "final" in modifiers

    def _normalize_storable_kind(self, kind):
        if kind in {"global", "local", "external", "register", "unknown"}:
            return kind

        if kind in {"field", "member"}:
            # The current generator still represents fields as StorableUnit.
            # A future, stricter mapping can migrate Java fields to MemberUnit.
            return "unknown"

        return "unknown"


    # ------------------------------------------------------------------
    # Native KDM callable/signature helpers
    # ------------------------------------------------------------------

    def _create_callable_signature(self, owner, callable_model: dict):
        signature_name = (
            callable_model.get("signature")
            or callable_model.get("name")
            or "signature"
        )

        signature = self.factory.create_signature(signature_name)

        self._append_code_element(owner, signature)

        if self.factory.has_feature(owner, "type"):
            owner.type = signature

        # Do not attach SourceRegion directly to Signature.
        # The owning MethodUnit/CallableUnit already carries the source
        # traceability. Creating a second SourceRegion for Signature is fragile
        # in Python generic models because callable entries may not carry a
        # stable file/path context.

        callable_key = (
            callable_model.get("qualifiedSignature")
            or callable_model.get("qualified_signature")
            or callable_model.get("id")
            or callable_model.get("name")
        )

        if callable_key:
            self.id_index.setdefault(f"{callable_key}:signature", signature)

        return signature

    def _map_return_parameter(self, signature, callable_model: dict):
        resolved_return_type = (
            callable_model.get("resolvedReturnType")
            or callable_model.get("resolved_return_type")
            or callable_model.get("returnType")
            or callable_model.get("return_type")
        )

        if not resolved_return_type:
            return

        method_kind = callable_model.get("kind") or callable_model.get("method_kind")

        if method_kind == "constructor":
            return

        return_param = self.factory.create_parameter_unit("return")
        self._append_parameter_unit(signature, return_param)

        if self.factory.has_feature(return_param, "kind"):
            return_param.kind = "return"

        if self.factory.has_feature(return_param, "pos"):
            return_param.pos = 0

        normalized_return = {
            "name": f"{callable_model.get('name', 'callable')}:return",
            "resolved_type_id": self._infer_type_id(resolved_return_type),
            "resolved_type_qualified_name": resolved_return_type,
        }

        self._register_typable(return_param, normalized_return)

    def _append_parameter_unit(self, parent, parameter_unit):
        if parent is None or parameter_unit is None:
            return False

        if self.factory.has_feature(parent, "parameterUnit"):
            parent.parameterUnit.append(parameter_unit)
            return True

        return self._append_code_element(parent, parameter_unit)

    def _apply_method_native_properties(self, method_unit, method: dict):
        method_kind = method.get("kind") or method.get("method_kind") or "method"

        if self.factory.has_feature(method_unit, "kind"):
            method_unit.kind = self._normalize_method_kind(method_kind)

        modifiers = set(method.get("modifiers", []) or [])

        if self.factory.has_feature(method_unit, "export"):
            method_unit.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(method_unit, "isStatic"):
            method_unit.isStatic = "static" in modifiers

        if self.factory.has_feature(method_unit, "isFinal"):
            method_unit.isFinal = "final" in modifiers

        if self.factory.has_feature(method_unit, "isAbstract"):
            method_unit.isAbstract = "abstract" in modifiers

    def _apply_callable_native_properties(self, callable_unit, callable_model: dict):
        callable_kind = (
            callable_model.get("callable_kind")
            or callable_model.get("kind")
            or "regular"
        )

        if self.factory.has_feature(callable_unit, "kind"):
            callable_unit.kind = self._normalize_callable_kind(callable_kind)

        modifiers = set(callable_model.get("modifiers", []) or [])

        if self.factory.has_feature(callable_unit, "isStatic"):
            callable_unit.isStatic = "static" in modifiers

    def _apply_parameter_native_properties(self, parameter_unit, param: dict):
        kind = param.get("kind") or "byValue"

        if self.factory.has_feature(parameter_unit, "kind"):
            parameter_unit.kind = self._normalize_parameter_kind(kind)

        index = param.get("index")

        if index is None:
            index = param.get("position")

        if index is not None and self.factory.has_feature(parameter_unit, "pos"):
            try:
                parameter_unit.pos = int(index) + 1
            except Exception:
                parameter_unit.pos = index

        modifiers = set(param.get("modifiers", []) or [])

        if self.factory.has_feature(parameter_unit, "isFinal"):
            parameter_unit.isFinal = "final" in modifiers

    def _normalize_method_kind(self, kind):
        if kind in {"method", "constructor", "destructor", "operator"}:
            return kind

        return "unknown"

    def _normalize_callable_kind(self, kind):
        if kind in {"regular", "external", "operator", "stored"}:
            return kind

        if kind == "function":
            return "regular"

        return "unknown"

    def _normalize_parameter_kind(self, kind):
        if kind in {
            "byValue",
            "byName",
            "byReference",
            "variadic",
            "return",
            "throws",
            "exception",
            "catchall",
        }:
            return kind

        return "byValue"

    def _visibility_from_modifiers(self, modifiers):
        if "public" in modifiers:
            return "public"

        if "private" in modifiers:
            return "private"

        if "protected" in modifiers:
            return "protected"

        return "unknown"

    def _add_native_annotations(self, kdm_element, model_element: dict):
        """
        Models Java annotations and Python decorators using KDM semantics.

        The primary representation is a native kdm:Annotation attached to the
        annotated element. In addition, when the element is extendable, the
        mapper adds a formal KDM extension:

        - ExtensionFamily: LanguageAnnotations
        - Stereotype: JavaAnnotationUsage or PythonDecoratorUsage
        - TaggedValue entries:
          annotation_name
          annotation_text
          annotation_value
          annotation_language

        This avoids representing annotations as loose kdm:Attribute entries.
        """

        normalized_annotations = self._normalize_annotation_entries(
            model_element.get("annotations", []) or model_element.get("decorators", []) or []
        )

        if not normalized_annotations:
            return

        stereotype, tag_defs = self._get_or_create_annotation_stereotype()

        if stereotype is not None:
            self.factory.add_stereotype_to_element(kdm_element, stereotype)

        for annotation in normalized_annotations:
            text = annotation["text"]
            name = annotation["name"]
            values = annotation.get("values") or {}

            self._add_annotation_text_once(kdm_element, text)

            if stereotype is not None and tag_defs:
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_name"),
                    name,
                )
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_text"),
                    text,
                )
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_language"),
                    self.language,
                )

                for key, value in values.items():
                    self.factory.add_tagged_value(
                        kdm_element,
                        tag_defs.get("annotation_value"),
                        f"{key}={value}",
                    )

    def _add_annotation_text_once(self, kdm_element, text: str):
        if kdm_element is None or not text:
            return None

        if not self.factory.has_feature(kdm_element, "annotation"):
            return None

        for existing in kdm_element.annotation:
            if getattr(existing, "text", None) == text:
                return existing

        if hasattr(self.factory, "add_annotation"):
            return self.factory.add_annotation(kdm_element, text)

        annotation_cls = getattr(self.factory, "Annotation", None)

        if annotation_cls is None:
            return None

        annotation = annotation_cls()

        if self.factory.has_feature(annotation, "text"):
            annotation.text = text

        kdm_element.annotation.append(annotation)
        return annotation

    def _get_or_create_annotation_stereotype(self):
        if self.segment is None:
            return None, None

        stereotype_name = (
            "JavaAnnotationUsage"
            if self.language == "java"
            else "PythonDecoratorUsage"
            if self.language == "python"
            else "SourceAnnotationUsage"
        )

        if stereotype_name in self.annotation_stereotypes:
            return self.annotation_stereotypes[stereotype_name]

        family = self._get_or_create_annotation_extension_family()

        if family is None:
            return None, None

        stereotype = None

        if self.factory.has_feature(family, "stereotype"):
            for existing in family.stereotype:
                if getattr(existing, "name", None) == stereotype_name:
                    stereotype = existing
                    break

        if stereotype is None:
            stereotype = self.factory.create_stereotype(
                stereotype_name,
                "code:CodeItem",
            )

            if self.factory.has_feature(family, "stereotype"):
                family.stereotype.append(stereotype)

        tag_defs = self._ensure_annotation_tag_definitions(stereotype)

        self.annotation_stereotypes[stereotype_name] = (stereotype, tag_defs)
        return stereotype, tag_defs

    def _get_or_create_annotation_extension_family(self):
        if self.annotation_extension_family is not None:
            return self.annotation_extension_family

        if self.segment is None:
            return None

        if not self.factory.has_feature(self.segment, "extensionFamily"):
            return None

        for family in self.segment.extensionFamily:
            if getattr(family, "name", None) == "LanguageAnnotations":
                self.annotation_extension_family = family
                return family

        family = self.factory.create_extension_family("LanguageAnnotations")
        self.segment.extensionFamily.append(family)
        self.annotation_extension_family = family
        return family

    def _ensure_annotation_tag_definitions(self, stereotype):
        if stereotype is None or not self.factory.has_feature(stereotype, "tag"):
            return {}

        required = {
            "annotation_name": "String",
            "annotation_text": "String",
            "annotation_value": "String",
            "annotation_language": "String",
        }

        tag_defs = {}

        for existing in stereotype.tag:
            tag_name = getattr(existing, "tag", None)
            if tag_name in required:
                tag_defs[tag_name] = existing

        for tag_name, value_type in required.items():
            if tag_name in tag_defs:
                continue

            tag_definition = self.factory.create_tag_definition(
                tag_name,
                value_type,
            )
            stereotype.tag.append(tag_definition)
            tag_defs[tag_name] = tag_definition

        return tag_defs

    def _normalize_annotation_entries(self, annotations):
        normalized = []

        for annotation in annotations:
            parsed = self._normalize_single_annotation(annotation)

            if parsed is not None:
                normalized.append(parsed)

        return normalized

    def _normalize_single_annotation(self, annotation):
        if isinstance(annotation, dict):
            name = (
                annotation.get("name")
                or annotation.get("qualifiedName")
                or annotation.get("qualified_name")
                or annotation.get("type")
            )

            values = (
                annotation.get("values")
                or annotation.get("arguments")
                or annotation.get("members")
                or {}
            )

            if isinstance(values, list):
                values = {
                    str(index): value
                    for index, value in enumerate(values)
                }

            if values is None:
                values = {}

            if not isinstance(values, dict):
                values = {"value": values}

            if not name:
                text = str(annotation)
                name = text
            else:
                text = self._format_annotation_text(name, values)

            return {
                "name": str(name).lstrip("@"),
                "text": text,
                "values": {
                    str(key): str(value)
                    for key, value in values.items()
                },
            }

        text = str(annotation).strip()

        if not text:
            return None

        if not text.startswith("@"):
            text = f"@{text}"

        name, values = self._parse_annotation_text(text)

        return {
            "name": name,
            "text": text,
            "values": values,
        }

    def _parse_annotation_text(self, text: str):
        clean_text = text.strip()

        if clean_text.startswith("@"):
            clean_text = clean_text[1:]

        if "(" not in clean_text:
            return clean_text, {}

        name, raw_values = clean_text.split("(", 1)
        raw_values = raw_values.rsplit(")", 1)[0].strip()

        values = {}

        if raw_values:
            parts = self._split_annotation_arguments(raw_values)

            for index, part in enumerate(parts):
                if "=" in part:
                    key, value = part.split("=", 1)
                    values[key.strip()] = value.strip().strip('"')
                else:
                    values[str(index)] = part.strip().strip('"')

        return name.strip(), values

    def _split_annotation_arguments(self, raw_values: str):
        parts = []
        current = []
        depth = 0
        in_string = False
        quote = None

        for char in raw_values:
            if in_string:
                current.append(char)

                if char == quote:
                    in_string = False

                continue

            if char in {"'", '"'}:
                in_string = True
                quote = char
                current.append(char)
                continue

            if char in {"(", "{", "["}:
                depth += 1
                current.append(char)
                continue

            if char in {")", "}", "]"}:
                depth = max(0, depth - 1)
                current.append(char)
                continue

            if char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue

            current.append(char)

        if current:
            parts.append("".join(current).strip())

        return parts

    def _format_annotation_text(self, name: str, values: dict):
        clean_name = str(name).lstrip("@")

        if not values:
            return f"@{clean_name}"

        formatted_values = ", ".join(
            f"{key}={value}"
            for key, value in values.items()
        )

        return f"@{clean_name}({formatted_values})"



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
            elif relation_type == "reads":
                self._map_generic_access_relationship(relationship, access_kind="reads")
            elif relation_type == "writes":
                self._map_generic_access_relationship(relationship, access_kind="writes")
            elif relation_type == "creates":
                self._map_generic_creates_relationship(relationship)
            elif relation_type == "throws":
                self._map_generic_throws_relationship(relationship)

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

        line = (
            relationship.get("line")
            or relationship.get("lineStart")
            or relationship.get("line_start")
        )

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._append_code_element(body_block, action)

        if target is None:
            target = self._get_or_create_external_call_target(
                target_key=target_key,
                relationship=relationship,
            )

        if target is not None:
            calls_relation = self.factory.create_calls_relation(target)
            self._append_action_relation(action, calls_relation)

    def _get_or_create_external_call_target(self, target_key, relationship: dict):
        """
        Creates a conservative external CallableUnit for a call target that is
        outside the analyzed project.

        This avoids storing temporary attributes such as resolution_status or
        unresolved_target_name. If no target key is available, the call remains
        without a Calls relation rather than inventing an unreliable target.
        """

        if not target_key or self.external_builder is None:
            return None

        target_name = str(target_key)

        call_model = {
            "name": target_name,
            "target_id": target_name,
            "classification": "external",
            "kind": "call",
        }

        return self.external_builder.get_or_create_external_target(call_model)

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
        target_ref = relationship.get("target")
        target = self._resolve_java_type_target(target_ref)

        if source is None or target is None:
            return

        self._add_extends_relation(source, target)

    def _map_generic_implements_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))
        target_ref = relationship.get("target")
        target = self._resolve_java_type_target(target_ref)

        if source is None or target is None:
            return

        self._add_implements_relation(source, target)

    def _map_declared_java_inheritance(self, data: dict):
        """
        Maps Java extends/implements clauses declared directly on class
        elements.

        The Java extractor may encode inheritance either as generic
        relationships[] or as properties of each class element.  This method
        handles the second representation after all class units have already
        been created and indexed under the package hierarchy.
        """

        for element in data.get("elements", []) or []:
            self._map_java_inheritance_for_element(element)

        for file_model in data.get("files", []) or []:
            for key in ("classes", "interfaces", "enums"):
                for element in file_model.get(key, []) or []:
                    self._map_java_inheritance_for_element(element)

    def _map_java_inheritance_for_element(self, element: dict):
        if not isinstance(element, dict):
            return

        kind = str(element.get("kind") or element.get("type") or "").lower()
        if kind not in {"class", "interface", "enum", "annotation", "annotation_type"}:
            return

        source = self._resolve_indexed_element(
            element.get("id")
            or element.get("qualifiedName")
            or element.get("qualified_name")
            or element.get("name")
        )

        if source is None:
            return

        for super_ref in self._java_declared_extends(element):
            target = self._resolve_java_type_target(super_ref)
            if target is not None:
                self._add_extends_relation(source, target)

        for interface_ref in self._java_declared_implements(element):
            target = self._resolve_java_type_target(interface_ref)
            if target is not None:
                self._add_implements_relation(source, target)

    def _java_declared_extends(self, element: dict):
        candidates = []
        for key in (
            "extends",
            "extend",
            "superClass",
            "superclass",
            "super_class",
            "parentClass",
            "parent_class",
            "baseClass",
            "base_class",
        ):
            candidates.extend(self._as_list(element.get(key)))

        return self._clean_java_type_refs(candidates)

    def _java_declared_implements(self, element: dict):
        candidates = []
        for key in (
            "implements",
            "interfaces",
            "implementedInterfaces",
            "implemented_interfaces",
            "interfaceNames",
            "interface_names",
        ):
            candidates.extend(self._as_list(element.get(key)))

        return self._clean_java_type_refs(candidates)

    def _as_list(self, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, tuple):
            return list(value)

        return [value]

    def _clean_java_type_refs(self, values):
        cleaned = []
        seen = set()

        for value in values:
            if isinstance(value, dict):
                value = (
                    value.get("qualifiedName")
                    or value.get("qualified_name")
                    or value.get("name")
                    or value.get("type")
                    or value.get("target")
                )

            if value is None:
                continue

            text = str(value).strip()
            if not text:
                continue

            if text.startswith("external_type:"):
                text = text.replace("external_type:", "", 1)

            # Remove generic arguments and array suffixes.
            if "<" in text:
                text = text.split("<", 1)[0]
            while text.endswith("[]"):
                text = text[:-2]
            text = text.rstrip(">")

            if text in {"this", "super", "null", "void"}:
                continue

            if text not in seen:
                cleaned.append(text)
                seen.add(text)

        return cleaned

    def _resolve_java_type_target(self, type_ref):
        if type_ref is None:
            return None

        if isinstance(type_ref, dict):
            type_ref = (
                type_ref.get("qualifiedName")
                or type_ref.get("qualified_name")
                or type_ref.get("name")
                or type_ref.get("type")
                or type_ref.get("target")
            )

        if type_ref is None:
            return None

        raw = str(type_ref).strip()
        if not raw:
            return None

        if raw.startswith("external_type:"):
            raw = raw.replace("external_type:", "", 1)

        if "<" in raw:
            raw = raw.split("<", 1)[0]
        while raw.endswith("[]"):
            raw = raw[:-2]
        raw = raw.rstrip(">")

        target = self._resolve_indexed_element(raw)
        if target is not None:
            return target

        simple_name = raw.rsplit(".", 1)[-1]
        target = self._resolve_indexed_element(simple_name)
        if target is not None:
            return target

        if self.external_builder is None:
            return None

        library_name = self._infer_java_external_library_for_type(raw)
        return self.external_builder.get_or_create_external_class(library_name, simple_name)

    def _infer_java_external_library_for_type(self, type_ref: str) -> str:
        text = str(type_ref or "").strip()

        if "." in text:
            return text.rsplit(".", 1)[0]

        if self.external_builder is not None:
            imported_package = getattr(
                self.external_builder,
                "imported_type_to_package",
                {},
            ).get(text)
            if imported_package:
                return imported_package

        if text in {
            "Object", "String", "StringBuilder", "StringBuffer",
            "Boolean", "Byte", "Short", "Integer", "Long",
            "Float", "Double", "Character", "CharSequence",
            "Class", "Enum", "Exception", "RuntimeException",
            "Throwable", "Error", "System", "Math", "Thread",
            "Runnable", "Iterable", "Comparable",
        }:
            return "java.lang"

        # Unknown Java/Android types are kept in a conservative external
        # library bucket rather than being incorrectly assigned to java.lang.
        return "unknown_external"

    def _add_extends_relation(self, source, target):
        if self._has_code_relation(source, "Extends", target):
            return

        try:
            relation = self.factory.create_extends_relation(target, source=source)
        except Exception:
            return

        self._append_code_relation(source, relation)

    def _add_implements_relation(self, source, target):
        if self._has_code_relation(source, "Implements", target):
            return

        try:
            relation = self.factory.create_implements_relation(target, source=source)
        except Exception:
            return

        self._append_code_relation(source, relation)

    def _has_code_relation(self, source, relation_type: str, target) -> bool:
        for relation in list(getattr(source, "codeRelation", []) or []):
            try:
                current_type = relation.eClass.name
            except Exception:
                current_type = relation.__class__.__name__

            if current_type == relation_type and getattr(relation, "to", None) is target:
                return True

        return False

    def _map_generic_uses_type_relationship(self, relationship: dict):
        """
        uses_type relations are represented mainly through HasType by the
        TypeRelationResolver, based on typable_elements collected while mapping
        fields, parameters and return types.

        This method intentionally avoids registering duplicated typable entries.
        """
        return

    def _map_generic_access_relationship(self, relationship: dict, access_kind: str):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name=access_kind,
            default_kind=access_kind,
        )

        if action is None:
            return

        target = self._resolve_access_target(
            relationship.get("target"),
            relationship.get("source"),
        )

        if target is None:
            return


        # KDM access relations are intentionally restricted by the validator
        # to StorableUnit targets. The generic JSON index may also resolve a
        # reference to ParameterUnit, especially in Python projects where
        # parameters are indexed as addressable elements. Creating Reads/Writes
        # to ParameterUnit makes the KDM invalid, so we skip those generic
        # access relations here. Parameter types are still represented through
        # ParameterUnit + HasType.
        if not self._is_valid_access_target(target):
            return


        if access_kind == "reads":
            relation = self.factory.create_reads_relation(target)
        else:
            relation = self.factory.create_writes_relation(target)

        self._append_action_relation(action, relation)


    def _is_valid_access_target(self, target) -> bool:
        """Return True only for KDM targets valid for Reads/Writes."""

        if target is None:
            return False

        try:
            return target.eClass.name == "StorableUnit"
        except AttributeError:
            return False

    def _is_kdm_datatype(self, element) -> bool:
        """Return True when *element* can be used as the target of Creates.

        In the KDM Code package, the ``Creates.to`` reference is typed as
        ``Datatype``.  The Java extractor can emit generic ``creates``
        relationships whose target is a local variable or field represented as
        ``StorableUnit``.  PyEcore rejects that assignment because a
        ``StorableUnit`` is not a ``Datatype``.

        This guard keeps generic Java relationships from producing invalid KDM
        while still allowing creation targets such as ``ClassUnit`` or other
        Datatype subtypes.
        """

        if element is None:
            return False

        try:
            eclass = element.eClass
        except AttributeError:
            return False

        return self._eclass_is_or_extends(eclass, "Datatype")

    def _eclass_is_or_extends(self, eclass, expected_name: str) -> bool:
        """Return True if an EClass is named *expected_name* or inherits it."""

        if eclass is None:
            return False

        if getattr(eclass, "name", None) == expected_name:
            return True

        for super_type in getattr(eclass, "eSuperTypes", []) or []:
            if self._eclass_is_or_extends(super_type, expected_name):
                return True

        return False

    def _map_generic_creates_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name=self._call_action_name(relationship.get("target")),
            default_kind="constructor",
        )

        if action is None:
            return

        target = self._resolve_indexed_element(relationship.get("target"))

        if target is None:
            # No reliable create target could be resolved. Do not emit
            # temporary resolution attributes.
            return

        if not self._is_kdm_datatype(target):
            # Creates.to must point to a KDM Datatype.  Java generic
            # relationships may resolve to StorableUnit targets such as fields
            # or local variables; these are intentionally skipped.
            return

        creates_relation = self.factory.create_creates_relation(target)
        self._append_action_relation(action, creates_relation)

    def _map_generic_throws_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name="throw",
            default_kind="throw",
        )

        if action is None:
            return

        target = self._resolve_indexed_element(relationship.get("target"))

        if target is None:
            self.factory.add_attributes_from_dict(
                action,
                {
                    "unresolved_throw_target": relationship.get("target"),
                },
            )
            return

        throws_relation = self.factory.create_throws_relation(target)
        self._append_action_relation(action, throws_relation)

    # ------------------------------------------------------------------
    # Callable bodies and calls
    # ------------------------------------------------------------------

    def _get_or_create_relationship_action(
        self,
        source,
        relationship: dict,
        default_name: str,
        default_kind: str,
    ):
        if source is None:
            return None

        try:
            if source.eClass.name == "ActionElement":
                return source
        except AttributeError:
            return None

        body_block = self._get_or_create_callable_body(source)
        if body_block is None:
            return None

        line = (
            relationship.get("line")
            or relationship.get("lineStart")
            or relationship.get("line_start")
        )

        action = self._find_body_action_by_line(body_block, line)

        if action is not None:
            return action

        action = self.factory.create_action_element(
            name=default_name or default_kind or "action",
            kind=default_kind or "action",
        )

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._append_code_element(body_block, action)
        return action

    def _find_body_action_by_line(self, body_block, line):
        if body_block is None or line is None:
            return None

        if not self.factory.has_feature(body_block, "codeElement"):
            return None

        for child in body_block.codeElement:
            if getattr(child.eClass, "name", None) != "ActionElement":
                continue

            for source_ref in getattr(child, "source", []):
                for region in getattr(source_ref, "region", []):
                    if getattr(region, "startLine", None) == line:
                        return child

        return None

    def _resolve_access_target(self, target_name, source_key=None):
        if not target_name:
            return None

        target = self._resolve_indexed_element(target_name)
        if target is not None:
            return target

        if source_key:
            for key in (
                (source_key, target_name),
                f"{source_key}:parameter:{target_name}",
                f"{source_key}:local:{target_name}",
            ):
                target = self.storable_index.get(key) or self.id_index.get(key)
                if target is not None:
                    return target

        simple_target = str(target_name)

        if simple_target.startswith("this."):
            field_name = simple_target.split(".", 1)[1]
            owner_qn = self._owner_qualified_name_from_callable(source_key)
            if owner_qn:
                target = self.storable_index.get(f"{owner_qn}.{field_name}")
                if target is not None:
                    return target
            simple_target = field_name

        return self.storable_index.get(simple_target) or self.id_index.get(simple_target)

    def _owner_qualified_name_from_callable(self, source_key):
        if not source_key or not isinstance(source_key, str):
            return None

        if ".<init>" in source_key:
            return source_key.split(".<init>", 1)[0]

        before_args = source_key.split("(", 1)[0]
        if "." not in before_args:
            return None

        return before_args.rsplit(".", 1)[0]

    def _get_or_create_callable_body(self, callable_unit):
        """
        Returns the body BlockUnit of a MethodUnit or CallableUnit.

        KDM validation requires executable ActionElement nodes to be contained
        in a BlockUnit, not directly inside MethodUnit or CallableUnit.
        Only MethodUnit and CallableUnit can own executable bodies here.
        DataElement/StorableUnit/ParameterUnit may also expose a ``codeElement``
        feature in the KDM metamodel, but their feature is typed for Datatype
        containment and cannot accept BlockUnit.
        """
        if callable_unit is None:
            return None

        try:
            eclass_name = callable_unit.eClass.name
        except AttributeError:
            return None

        if eclass_name not in {"MethodUnit", "CallableUnit"}:
            return None

        if not self.factory.has_feature(callable_unit, "codeElement"):
            return None

        for child in callable_unit.codeElement:
            if getattr(child.eClass, "name", None) == "BlockUnit":
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
        Deprecated compatibility hook.

        Callable and method signatures are represented with native
        code:Signature and code:ParameterUnit elements. Python decorators are
        represented by _add_native_annotations using kdm:Annotation,
        Stereotype and TaggedValue.
        """
        return

    def _add_decorator_metadata(self, kdm_element, model_element: dict):
        """
        Deprecated compatibility hook.

        Do not emit Attribute tag="decorators" or tag="decorator_N".
        Decorators are represented by _add_native_annotations.
        """
        self._add_native_annotations(kdm_element, model_element)


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
