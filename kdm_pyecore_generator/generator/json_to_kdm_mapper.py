class JsonToKDMMapper:
    def __init__(self, factory, inventory_builder=None):
        self.factory = factory
        self.inventory_builder = inventory_builder
        self.id_index = {}

        # Auxiliary indexes for resolving inheritance
        self.qualified_name_index = {}
        self.class_name_index = {}

        # Project language
        self.language = "unknown"

        # Elements that can receive code::HasType
        self.typable_elements = []

        # Elements that can receive code::HasValue
        self.value_elements = []

        self.storable_index = {}

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

        This is needed when the Segment already contains an InventoryModel
        created before the CodeModel.
        """
        project_name = data.get("projectName", "UnknownProject")
        self.language = data.get("language", "unknown")

        code_model = self.factory.create_code_model(f"{project_name}_CodeModel")
        segment.model.append(code_model)

        for file_model in data.get("files", []):
            self._map_file(code_model, file_model)

        return segment

    def _register(self, json_id: str, kdm_element, model_element: dict = None):
        if json_id:
            self.id_index[json_id] = kdm_element

        if model_element:
            qualified_name = model_element.get("qualified_name")
            name = model_element.get("name")
            element_type = model_element.get("type")

            if qualified_name:
                self.qualified_name_index[qualified_name] = kdm_element

            if element_type == "class" and name:
                self.class_name_index.setdefault(name, []).append(kdm_element)

    def _add_common_metadata(self, kdm_element, model_element: dict):
        """
        Adds only non-physical and non-structural metadata.

        Physical traceability is represented using source::SourceRef
        and source::SourceRegion. Structural information such as name,
        parent, module, and containment is already represented by KDM
        containment and native properties.
        """
        metadata = {
            "original_id": model_element.get("id"),
            "json_type": model_element.get("type"),
            "qualified_name": model_element.get("qualified_name"),
        }

        self.factory.add_attributes_from_dict(kdm_element, metadata)

    def _map_file(self, code_model, file_model: dict):
        unit_name = file_model.get("path", file_model.get("name", "unknown.py"))

        compilation_unit = self.factory.create_compilation_unit(unit_name)
        code_model.codeElement.append(compilation_unit)

        source_file = self._get_source_file(file_model)

        # Physical traceability for the file
        self.factory.add_source_region(
            compilation_unit,
            path=file_model.get("path"),
            language=self.language,
            file_item=source_file,
        )

        # Non-physical metadata
        self._add_common_metadata(compilation_unit, file_model)

        self._register(file_model.get("id"), compilation_unit, file_model)

        for cls in file_model.get("classes", []):
            self._map_class(compilation_unit, cls, file_model)

        for func in file_model.get("functions", []):
            self._map_function(compilation_unit, func, file_model)

    def _map_class(self, parent, cls: dict, file_model: dict):
        class_unit = self.factory.create_class_unit(
            cls.get("name", "AnonymousClass")
        )
        parent.codeElement.append(class_unit)

        source_file = self._get_source_file(file_model)

        # Physical traceability
        self.factory.add_source_region(
            class_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=cls.get("line_start"),
            end_line=cls.get("line_end"),
            file_item=source_file,
        )

        # Non-physical metadata
        self._add_common_metadata(class_unit, cls)

        self._add_decorator_metadata(class_unit, cls)

        self._register(cls.get("id"), class_unit, cls)

        for attr in cls.get("attributes", []):
            self._map_storable(class_unit, attr, file_model)

        for attr in cls.get("instance_attributes", []):
            self._map_storable(class_unit, attr, file_model)

        for method in cls.get("methods", []):
            self._map_method(class_unit, method, file_model)

    def _map_method(self, parent, method: dict, file_model: dict):
        method_unit = self.factory.create_method_unit(
            method.get("name", "anonymous_method")
        )
        parent.codeElement.append(method_unit)

        source_file = self._get_source_file(file_model)

        # Physical traceability
        self.factory.add_source_region(
            method_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=method.get("line_start"),
            end_line=method.get("line_end"),
            file_item=source_file,
        )

        # Non-physical metadata
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

        # Physical traceability
        self.factory.add_source_region(
            callable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=func.get("line_start"),
            end_line=func.get("line_end"),
            file_item=source_file,
        )

        # Non-physical metadata
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
        }

        self.factory.add_attributes_from_dict(storable_unit, metadata)

    # ------------------------------------------------------------
    # Callable and signature metadata
    # ------------------------------------------------------------

    def _add_callable_signature_metadata(self, callable_unit, callable_model: dict):
        """
        Adds lightweight signature metadata to MethodUnit or CallableUnit.

        KDM MethodUnit/CallableUnit and ParameterUnit represent the callable
        structure. The following attributes preserve Python-specific signature
        details that do not have a direct KDM feature in the currently used
        Ecore subset.
        """

        metadata = {
            "method_kind": callable_model.get("method_kind"),
            "is_async": callable_model.get("is_async"),
            "return_annotation": callable_model.get("return_annotation"),
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

    # ------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------

    def _register_typable(self, kdm_element, source_model: dict):
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

        for key in keys:
            self.storable_index[key] = storable_unit
