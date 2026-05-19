class ExternalModelBuilder:
    """
    Builds and reuses KDM elements for external libraries, builtins,
    external types, and unresolved external calls/imports.
    """

    def __init__(self, factory, segment):
        self.factory = factory
        self.segment = segment

        self.external_code_model = None
        self.library_units = {}
        self.external_targets = {}

    def ensure_external_model(self):
        if self.external_code_model is None:
            self.external_code_model = self.factory.create_code_model(
                "ExternalLibraries_CodeModel"
            )
            self.segment.model.append(self.external_code_model)

        return self.external_code_model

    def get_or_create_external_target(self, call: dict):
        """
        Returns a KDM target for an external call.
        If the target does not exist yet, it is created.
        """

        library_name = self._infer_library_name(call)
        target_name = self._infer_target_name(call)
        target_kind = self._infer_target_kind(call)

        key = f"{library_name}:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        if target_kind == "class":
            target = self.factory.create_class_unit(target_name)
        else:
            target = self.factory.create_callable_unit(target_name)

        library_unit.codeElement.append(target)
        self.external_targets[key] = target

        return target

    def _get_or_create_library_unit(self, external_model, library_name: str):
        """
        Creates or reuses the CompilationUnit representing an external library.

        This is the only helper used to place external elements under the
        ExternalLibraries_CodeModel. Do not call a non-existing
        get_or_create_external_library_model method.
        """

        library_name = str(library_name or "unknown_external")

        if library_name in self.library_units:
            return self.library_units[library_name]

        unit = self.factory.create_compilation_unit(library_name)
        external_model.codeElement.append(unit)

        self.library_units[library_name] = unit
        return unit

    def _infer_library_name(self, call: dict):
        classification = call.get("classification")

        if classification in {"builtin", "builtin_type_method"}:
            return "builtins"

        import_source = call.get("import_source")

        if import_source:
            module = import_source.get("module")
            if module:
                return module.split(".")[0]

        receiver = call.get("receiver")
        if receiver:
            return receiver.split(".")[0]

        target_id = call.get("target_id")
        if target_id and target_id.startswith("external_type:"):
            external_name = target_id.replace("external_type:", "")
            return external_name.split(".")[0]

        name = call.get("name", "unknown_external")
        if "." in name:
            return name.split(".")[0]

        return "builtins"

    def _infer_target_name(self, call: dict):
        if call.get("method"):
            return call["method"]

        if call.get("function"):
            return call["function"]

        name = call.get("name", "unknown_external")

        if "." in name:
            return name.split(".")[-1]

        return name

    def _infer_target_kind(self, call: dict):
        kind = call.get("kind")
        classification = call.get("classification")
        name = call.get("name", "")

        if kind == "constructor_call":
            return "class"

        if classification == "builtin" and name in {
            "ValueError",
            "Exception",
            "TypeError",
            "RuntimeError",
        }:
            return "class"

        import_source = call.get("import_source")
        if import_source and import_source.get("name") == "Path":
            return "class"

        return "callable"

    def get_or_create_external_class(self, library_name: str, class_name: str):
        library_name = str(library_name or "unknown_external")
        class_name = str(class_name or "UnknownExternalClass")

        key = f"{library_name}:class:{class_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        target = self.factory.create_class_unit(class_name)
        library_unit.codeElement.append(target)

        self.external_targets[key] = target
        return target

    def get_or_create_external_import_target(self, import_model: dict):
        """
        Creates or reuses an external target for an unresolved import.

        This method is defensive because Python imports can be relative and may
        carry module=None, for example:

            from . import config as mape_config

        Ideally, internal relative imports should be resolved by ImportResolver.
        This method only handles imports that still remain external/unresolved
        after that step.
        """

        module_name = (
            import_model.get("module")
            or import_model.get("imported_module")
            or import_model.get("resolved_module_qualified_name")
            or import_model.get("name")
            or import_model.get("effective_name")
            or "unknown_external"
        )

        module_name = str(module_name or "unknown_external")
        library_name = module_name.split(".")[0] if module_name else "unknown_external"

        target_name = (
            import_model.get("name")
            or import_model.get("effective_name")
            or module_name
            or "unknown_external_import"
        )
        target_name = str(target_name)

        target_kind = self._infer_import_target_kind(import_model)

        key = f"{library_name}:import:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        if target_kind == "class":
            target = self.factory.create_class_unit(target_name)
        elif target_kind == "module":
            target = self.factory.create_compilation_unit(target_name)
        else:
            target = self.factory.create_callable_unit(target_name)

        self.factory.add_attribute(target, "external", "true")
        self.factory.add_attribute(target, "external_kind", "import")
        self.factory.add_attribute(target, "library", library_name)

        if import_model.get("alias"):
            self.factory.add_attribute(target, "alias", import_model.get("alias"))

        if import_model.get("level") is not None:
            self.factory.add_attribute(
                target,
                "relative_import_level",
                import_model.get("level"),
            )

        library_unit.codeElement.append(target)
        self.external_targets[key] = target

        return target

    def _infer_import_target_kind(self, import_model: dict):
        target_type = import_model.get("target_type")
        name = import_model.get("name")
        module = import_model.get("module")

        if target_type in {"class", "function", "module", "wildcard"}:
            if target_type == "function":
                return "callable"

            if target_type == "wildcard":
                return "module"

            return target_type

        if name in {
            "Path",
            "Exception",
            "ValueError",
            "TypeError",
            "RuntimeError",
        }:
            return "class"

        if name and name[:1].isupper():
            return "class"

        # Plain import without imported name is better represented as a module.
        if module and name is None:
            return "module"

        return "callable"
