from pathlib import Path


class ModelIdBuilder:
    """
    Builds qualified names and stable identifiers for intermediate model elements.

    This helper centralizes the naming convention used by the Python extractor.
    The generated identifiers are later used by the KDM generator to create
    traceable KDM elements and relations.

    Identifier format examples:

        module:example_project.services.user_service
        class:example_project.services.user_service.UserService
        function:example_project.utils.validators.is_valid_name
        method:example_project.services.user_service.UserService.create_user

    Qualified names follow the Python module path plus the element name.
    """

    def __init__(self, project_root: Path, file_path: Path):
        """
        Initializes the id builder for a single Python source file.

        Parameters
        ----------
        project_root:
            Root directory of the analyzed Python project.

        file_path:
            Path to the Python source file for which identifiers are created.
        """

        self.project_root = project_root
        self.file_path = file_path
        self.module_name = self._build_module_name()

    def _build_module_name(self):
        """
        Converts a Python file path into a module-like qualified name.

        Example
        -------
        For a project named ``example_project`` and a file:

            services/user_service.py

        this method produces:

            example_project.services.user_service

        For ``__init__.py`` files, the ``__init__`` suffix is omitted.
        """

        relative_path = self.file_path.relative_to(self.project_root)

        parts = list(relative_path.with_suffix("").parts)

        if parts[-1] == "__init__":
            parts = parts[:-1]

        project_name = self.project_root.name

        if parts:
            return ".".join([project_name] + parts)

        return project_name

    def get_module_qualified_name(self):
        """
        Returns the qualified name of the current Python module.
        """

        return self.module_name

    def get_module_id(self):
        """
        Returns the stable id of the current Python module.
        """

        return f"module:{self.module_name}"

    def get_class_qualified_name(self, class_name: str):
        """
        Returns the qualified name of a class defined in the current module.
        """

        return f"{self.module_name}.{class_name}"

    def get_class_id(self, class_name: str):
        """
        Returns the stable id of a class defined in the current module.
        """

        return f"class:{self.get_class_qualified_name(class_name)}"

    def get_function_qualified_name(self, function_name: str):
        """
        Returns the qualified name of a module-level function.
        """

        return f"{self.module_name}.{function_name}"

    def get_function_id(self, function_name: str):
        """
        Returns the stable id of a module-level function.
        """

        return f"function:{self.get_function_qualified_name(function_name)}"

    def get_method_qualified_name(self, class_name: str, method_name: str):
        """
        Returns the qualified name of a method defined inside a class.
        """

        return f"{self.module_name}.{class_name}.{method_name}"

    def get_method_id(self, class_name: str, method_name: str):
        """
        Returns the stable id of a method defined inside a class.
        """

        return f"method:{self.get_method_qualified_name(class_name, method_name)}"
