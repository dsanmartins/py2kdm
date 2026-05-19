class ImportResolver:
    """
    Resolves Python import statements as internal or external references.

    This version correctly resolves package-relative imports such as:

        from . import config as mape_config

    when they appear inside a package __init__.py file. For example, if the
    current file model corresponds to:

        pymape_hierarchical.mape

    then:

        from . import config

    should try:

        pymape_hierarchical.mape.config

    before marking the import as external.
    """

    def __init__(self, symbol_table, project_name: str):
        self.symbol_table = symbol_table
        self.project_name = project_name

    def resolve_project_imports(self, project_model: dict):
        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for import_model in file_model.get("imports", []):
                self.resolve_import(import_model, file_model=file_model)

        return project_model

    def resolve_import(self, import_model: dict, file_model: dict = None):
        self._add_common_metadata(import_model)

        import_type = import_model.get("type")

        if import_type == "import":
            self._resolve_plain_import(import_model, file_model=file_model)

        elif import_type == "from_import":
            self._resolve_from_import(import_model, file_model=file_model)

        else:
            self._mark_external(import_model)

    def _resolve_plain_import(self, import_model: dict, file_model: dict = None):
        module = import_model.get("module")

        if not module:
            self._mark_external(import_model)
            return

        candidate_module_names = self._candidate_module_names(
            module_name=module,
            file_model=file_model,
            level=import_model.get("level", 0),
        )

        import_model["resolution_candidates"] = candidate_module_names

        for candidate_name in candidate_module_names:
            module_symbol = self.symbol_table.find_module(candidate_name)

            if module_symbol is not None:
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module",
                    resolved_module_qualified_name=module_symbol.get("qualified_name"),
                )
                return

        self._mark_external(import_model)

    def _resolve_from_import(self, import_model: dict, file_model: dict = None):
        module = import_model.get("module")
        name = import_model.get("name")

        if not name:
            self._mark_external(import_model)
            return

        if module is None:
            module = ""

        candidate_module_names = self._candidate_module_names(
            module_name=module,
            file_model=file_model,
            level=import_model.get("level", 0),
        )

        import_model["resolution_candidates"] = self._with_imported_name_candidates(
            candidate_module_names,
            name,
        )

        if name == "*":
            for candidate_module_name in candidate_module_names:
                module_symbol = self.symbol_table.find_module(candidate_module_name)

                if module_symbol is not None:
                    self._mark_internal(
                        import_model,
                        module_symbol,
                        target_type="wildcard",
                        resolved_module_qualified_name=module_symbol.get("qualified_name"),
                    )
                    import_model["wildcard"] = True
                    return

            self._mark_external(import_model)
            import_model["wildcard"] = True
            return

        for candidate_module_name in candidate_module_names:
            class_qn = self._join_qualified_name(candidate_module_name, name)
            class_symbol = self.symbol_table.find_class_by_qualified_name(class_qn)

            if class_symbol is not None:
                self._mark_internal(
                    import_model,
                    class_symbol,
                    target_type="class",
                    resolved_module_qualified_name=candidate_module_name,
                )
                return

            function_qn = self._join_qualified_name(candidate_module_name, name)
            function_symbol = self.symbol_table.find_function_by_qualified_name(
                function_qn
            )

            if function_symbol is not None:
                self._mark_internal(
                    import_model,
                    function_symbol,
                    target_type="function",
                    resolved_module_qualified_name=candidate_module_name,
                )
                return

            submodule_qn = self._join_qualified_name(candidate_module_name, name)
            module_symbol = self.symbol_table.find_module(submodule_qn)

            if module_symbol is not None:
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module",
                    resolved_module_qualified_name=module_symbol.get("qualified_name"),
                )
                return

            module_symbol = self.symbol_table.find_module(candidate_module_name)

            if module_symbol is not None and name == module_symbol.get("name"):
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module",
                    resolved_module_qualified_name=module_symbol.get("qualified_name"),
                )
                return

        self._mark_external(import_model)

    def _candidate_module_names(
        self,
        module_name: str,
        file_model: dict = None,
        level: int = 0,
    ):
        candidates = []

        module_name = module_name or ""
        level = level or 0

        if level > 0:
            candidates.extend(
                self._relative_candidate_module_names(
                    module_name=module_name,
                    file_model=file_model,
                    level=level,
                )
            )

        if module_name:
            candidates.append(module_name)

            if not module_name.startswith(f"{self.project_name}."):
                candidates.append(f"{self.project_name}.{module_name}")

        elif self.project_name and level == 0:
            candidates.append(self.project_name)

        return self._unique(candidates)

    def _relative_candidate_module_names(
        self,
        module_name: str,
        file_model: dict,
        level: int,
    ):
        if file_model is None:
            return []

        current_qn = file_model.get("qualified_name")

        if not current_qn:
            return []

        parts = current_qn.split(".")

        if self._is_package_init_file(file_model):
            package_parts = parts
        else:
            package_parts = parts[:-1]

        if level > 1:
            package_parts = package_parts[: -(level - 1)]

        if not package_parts:
            return []

        base_package = ".".join(package_parts)

        if module_name:
            return [f"{base_package}.{module_name}"]

        return [base_package]

    def _is_package_init_file(self, file_model: dict):
        name = file_model.get("name")
        path = str(file_model.get("path", ""))

        return name == "__init__" or path.endswith("__init__.py")

    def _with_imported_name_candidates(self, module_candidates: list, name: str):
        candidates = []

        for candidate in module_candidates:
            candidates.append(candidate)

            if name and name != "*":
                candidates.append(self._join_qualified_name(candidate, name))

        return self._unique(candidates)

    def _join_qualified_name(self, prefix: str, suffix: str):
        if prefix:
            return f"{prefix}.{suffix}"

        return suffix

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

    def _add_common_metadata(self, import_model: dict):
        alias = import_model.get("alias")
        name = import_model.get("name")
        module = import_model.get("module")

        import_model["effective_name"] = alias or name or module
        import_model["imported_module"] = module
        import_model["imported_name"] = name

    def _mark_internal(
        self,
        import_model: dict,
        symbol: dict,
        target_type: str,
        resolved_module_qualified_name: str = None,
    ):
        import_model.update(
            {
                "classification": "internal",
                "resolved": True,
                "target_id": symbol.get("id"),
                "target_qualified_name": symbol.get("qualified_name"),
                "target_type": target_type,
                "resolved_module_qualified_name": (
                    resolved_module_qualified_name
                    or self._module_name_from_qualified_name(
                        symbol.get("qualified_name")
                    )
                ),
            }
        )

    def _mark_external(self, import_model: dict):
        import_model.update(
            {
                "classification": "external",
                "resolved": False,
                "target_id": None,
                "target_qualified_name": None,
                "target_type": None,
                "resolved_module_qualified_name": None,
            }
        )

    def _module_name_from_qualified_name(self, qualified_name: str):
        if not qualified_name:
            return None

        if "." not in qualified_name:
            return qualified_name

        return ".".join(qualified_name.split(".")[:-1])
