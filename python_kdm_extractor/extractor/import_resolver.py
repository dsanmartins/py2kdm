class ImportResolver:
    """
    Resolves import statements as internal or external using the symbol table.

    It enriches each import model with:
    - classification: internal or external
    - target_id
    - target_qualified_name
    - target_type
    """

    def __init__(self, symbol_table, project_name: str):
        self.symbol_table = symbol_table
        self.project_name = project_name

    def resolve_project_imports(self, project_model: dict):
        """
        Resolves all imports in all file models.
        """

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for import_model in file_model.get("imports", []):
                self.resolve_import(import_model)

        return project_model

    def resolve_import(self, import_model: dict):
        """
        Resolves a single import model.
        """

        import_type = import_model.get("type")

        if import_type == "import":
            self._resolve_plain_import(import_model)

        elif import_type == "from_import":
            self._resolve_from_import(import_model)

        else:
            self._mark_external(import_model)

    def _resolve_plain_import(self, import_model: dict):
        """
        Resolves imports of the form:

        import json
        import repository.user_repository
        import repository.user_repository as repo
        """

        module = import_model.get("module")

        if not module:
            self._mark_external(import_model)
            return

        candidate_module_names = self._candidate_module_names(module)

        for candidate_name in candidate_module_names:
            module_symbol = self.symbol_table.find_module(candidate_name)

            if module_symbol is not None:
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module"
                )
                return

        self._mark_external(import_model)

    def _resolve_from_import(self, import_model: dict):
        """
        Resolves imports of the form:

        from repository.user_repository import UserRepository
        from services.user_service import validate_user
        """

        module = import_model.get("module")
        name = import_model.get("name")

        if not module or not name:
            self._mark_external(import_model)
            return

        candidate_module_names = self._candidate_module_names(module)

        for candidate_module_name in candidate_module_names:
            # 1. Try class: example_project.repository.user_repository.UserRepository
            class_qn = f"{candidate_module_name}.{name}"
            class_symbol = self.symbol_table.find_class_by_qualified_name(class_qn)

            if class_symbol is not None:
                self._mark_internal(
                    import_model,
                    class_symbol,
                    target_type="class"
                )
                return

            # 2. Try function: example_project.services.user_service.validate_user
            function_qn = f"{candidate_module_name}.{name}"
            function_symbol = self.symbol_table.find_function_by_qualified_name(
                function_qn
            )

            if function_symbol is not None:
                self._mark_internal(
                    import_model,
                    function_symbol,
                    target_type="function"
                )
                return

            # 3. Try module itself
            module_symbol = self.symbol_table.find_module(class_qn)

            if module_symbol is not None:
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module"
                )
                return

        self._mark_external(import_model)

    def _candidate_module_names(self, module_name: str):
        """
        Builds possible internal module qualified names.

        Example:
        module_name = repository.user_repository

        Candidates:
        - repository.user_repository
        - example_project.repository.user_repository
        """

        candidates = []

        if module_name:
            candidates.append(module_name)

        if module_name and not module_name.startswith(f"{self.project_name}."):
            candidates.append(f"{self.project_name}.{module_name}")

        return candidates

    def _mark_internal(self, import_model: dict, symbol: dict, target_type: str):
        """
        Marks an import as internal.
        """

        import_model.update({
            "classification": "internal",
            "resolved": True,
            "target_id": symbol.get("id"),
            "target_qualified_name": symbol.get("qualified_name"),
            "target_type": target_type
        })

    def _mark_external(self, import_model: dict):
        """
        Marks an import as external.
        """

        import_model.update({
            "classification": "external",
            "resolved": False,
            "target_id": None,
            "target_qualified_name": None,
            "target_type": None
        })
