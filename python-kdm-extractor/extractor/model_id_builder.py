from pathlib import Path


class ModelIdBuilder:
    """
    Builds qualified names and stable identifiers for model elements.
    """

    def __init__(self, project_root: Path, file_path: Path):
        self.project_root = project_root
        self.file_path = file_path
        self.module_name = self._build_module_name()

    def _build_module_name(self):
        """
        Converts a Python file path into a module-like qualified name.

        Example:
        example_project/services/user_service.py
        becomes:
        example_project.services.user_service
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
        return self.module_name

    def get_module_id(self):
        return f"module:{self.module_name}"

    def get_class_qualified_name(self, class_name: str):
        return f"{self.module_name}.{class_name}"

    def get_class_id(self, class_name: str):
        return f"class:{self.get_class_qualified_name(class_name)}"

    def get_function_qualified_name(self, function_name: str):
        return f"{self.module_name}.{function_name}"

    def get_function_id(self, function_name: str):
        return f"function:{self.get_function_qualified_name(function_name)}"

    def get_method_qualified_name(self, class_name: str, method_name: str):
        return f"{self.module_name}.{class_name}.{method_name}"

    def get_method_id(self, class_name: str, method_name: str):
        return f"method:{self.get_method_qualified_name(class_name, method_name)}"
