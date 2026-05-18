class ImportResolver:
    """
    Resolves Python import statements as internal or external references.

    This resolver enriches each import model produced by PythonASTVisitor using
    the symbols registered in SymbolTable.

    Supported import forms include:

    - plain imports:
        import json
        import repository.user_repository
        import repository.user_repository as repo

    - from-imports:
        from repository.user_repository import UserRepository
        from services.user_service import validate_user
        from repository import user_repository
        from .repository import UserRepository
        from repository.user_repository import *

    Each import is enriched with:

    - classification: "internal" or "external";
    - resolved: True or False;
    - target_id: id of the resolved internal element;
    - target_qualified_name: qualified name of the resolved element;
    - target_type: "module", "class", "function" or "wildcard";
    - resolved_module_qualified_name when it can be inferred;
    - effective_name, which is the alias if present, otherwise the imported name.

    Imports that cannot be matched against the internal symbol table are marked
    as external, while preserving enough metadata for downstream dependency
    analysis and KDM Imports generation.
    """

    def __init__(self, symbol_table, project_name: str):
        """
        Initializes the import resolver.

        Parameters
        ----------
        symbol_table:
            SymbolTable containing modules, classes, functions and methods
            extracted from the analyzed project.

        project_name:
            Name of the analyzed project. It is used to build candidate
            qualified module names for relative-looking imports.
        """

        self.symbol_table = symbol_table
        self.project_name = project_name

    def resolve_project_imports(self, project_model: dict):
        """
        Resolves all imports in the project model.

        Files that contain extraction errors are skipped.
        """

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for import_model in file_model.get("imports", []):
                self.resolve_import(import_model, file_model=file_model)

        return project_model

    def resolve_import(self, import_model: dict, file_model: dict = None):
        """
        Resolves a single import model.

        Parameters
        ----------
        import_model:
            Import dictionary produced by PythonASTVisitor.

        file_model:
            Current module model. It is optional and is used to resolve
            relative imports when the import model contains a `level` field.
        """

        self._add_common_metadata(import_model)

        import_type = import_model.get("type")

        if import_type == "import":
            self._resolve_plain_import(import_model, file_model=file_model)

        elif import_type == "from_import":
            self._resolve_from_import(import_model, file_model=file_model)

        else:
            self._mark_external(import_model)

    # ------------------------------------------------------------
    # Plain imports
    # ------------------------------------------------------------

    def _resolve_plain_import(self, import_model: dict, file_model: dict = None):
        """
        Resolves plain imports.

        Examples
        --------
        import json
        import repository.user_repository
        import repository.user_repository as repo
        """

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
                    resolved_module_qualified_name=module_symbol.get(
                        "qualified_name"
                    ),
                )
                return

        self._mark_external(import_model)

    # ------------------------------------------------------------
    # From imports
    # ------------------------------------------------------------

    def _resolve_from_import(self, import_model: dict, file_model: dict = None):
        """
        Resolves from-import statements.

        Resolution priority
        -------------------
        1. Wildcard import resolves to the imported module.
        2. Class inside the imported module.
        3. Function inside the imported module.
        4. Imported submodule.
        5. Imported module itself.
        """

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

        import_model["resolution_candidates"] = candidate_module_names

        # from package.module import *
        if name == "*":
            for candidate_module_name in candidate_module_names:
                module_symbol = self.symbol_table.find_module(candidate_module_name)

                if module_symbol is not None:
                    self._mark_internal(
                        import_model,
                        module_symbol,
                        target_type="wildcard",
                        resolved_module_qualified_name=module_symbol.get(
                            "qualified_name"
                        ),
                    )
                    import_model["wildcard"] = True
                    return

            self._mark_external(import_model)
            import_model["wildcard"] = True
            return

        for candidate_module_name in candidate_module_names:
            # 1. Try class:
            # example_project.repository.user_repository.UserRepository
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

            # 2. Try function:
            # example_project.services.user_service.validate_user
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

            # 3. Try imported submodule:
            # from repository import user_repository
            submodule_qn = self._join_qualified_name(candidate_module_name, name)
            module_symbol = self.symbol_table.find_module(submodule_qn)

            if module_symbol is not None:
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module",
                    resolved_module_qualified_name=module_symbol.get(
                        "qualified_name"
                    ),
                )
                return

            # 4. Try imported module itself.
            module_symbol = self.symbol_table.find_module(candidate_module_name)

            if module_symbol is not None and name == module_symbol.get("name"):
                self._mark_internal(
                    import_model,
                    module_symbol,
                    target_type="module",
                    resolved_module_qualified_name=module_symbol.get(
                        "qualified_name"
                    ),
                )
                return

        self._mark_external(import_model)

    # ------------------------------------------------------------
    # Candidate construction
    # ------------------------------------------------------------

    def _candidate_module_names(
        self,
        module_name: str,
        file_model: dict = None,
        level: int = 0,
    ):
        """
        Builds possible internal module qualified names.

        Examples
        --------
        For project_name = "example_project":

            repository.user_repository
            example_project.repository.user_repository

        For a relative import inside example_project.services.user_service:

            from .utils import validators

        possible candidates include:

            example_project.services.utils
            example_project.services.utils.validators
        """

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

        elif self.project_name:
            candidates.append(self.project_name)

        return self._unique(candidates)

    def _relative_candidate_module_names(
        self,
        module_name: str,
        file_model: dict,
        level: int,
    ):
        """
        Builds candidates for relative imports when the AST import model
        provides a level field.
        """

        if file_model is None:
            return []

        current_qn = file_model.get("qualified_name")

        if not current_qn:
            return []

        parts = current_qn.split(".")

        # Remove the current module name to obtain its package.
        package_parts = parts[:-1]

        # Python relative import semantics:
        # level=1 means current package, level=2 means parent package, etc.
        if level > 1:
            package_parts = package_parts[: -(level - 1)]

        if not package_parts:
            return []

        base_package = ".".join(package_parts)

        if module_name:
            return [f"{base_package}.{module_name}"]

        return [base_package]

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

    # ------------------------------------------------------------
    # Marking helpers
    # ------------------------------------------------------------

    def _add_common_metadata(self, import_model: dict):
        """
        Adds normalized names used by later stages.

        These fields are useful for mapping aliases to dependencies and for
        producing readable KDM import metadata.
        """

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
        """
        Marks an import as an internal project reference.
        """

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
        """
        Marks an import as an unresolved external dependency.
        """

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
