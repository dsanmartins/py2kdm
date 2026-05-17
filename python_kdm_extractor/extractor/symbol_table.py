class SymbolTable:
    """
    Stores internal symbols extracted from the intermediate project model.

    The symbol table is built after the file-level extraction phase. It indexes
    modules, classes, functions and methods so that later components can resolve
    imports, calls and type references.

    The table keeps both qualified-name indexes and simple-name indexes.

    Qualified-name indexes map one name to one symbol:

        example_project.services.user_service.UserService -> UserService symbol

    Simple-name indexes map one name to a list of symbols:

        UserService -> [UserService symbol, other UserService symbol, ...]

    This avoids overwriting symbols when different modules define elements with
    the same simple name.
    """

    def __init__(self):
        """
        Initializes all symbol indexes.
        """

        self.modules_by_qualified_name = {}

        self.classes_by_qualified_name = {}
        self.classes_by_name = {}

        self.functions_by_qualified_name = {}
        self.functions_by_name = {}

        self.methods_by_qualified_name = {}
        self.methods_by_name = {}
        self.methods_by_class_and_name = {}

    def build_from_project_model(self, project_model: dict):
        """
        Builds the symbol table from the full intermediate project model.

        Parameters
        ----------
        project_model:
            Project-level intermediate model produced by the extractor.

        Notes
        -----
        Files containing extraction errors are ignored.
        """

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            self.register_module(file_model)

            for class_model in file_model.get("classes", []):
                self.register_class(class_model)

                for method_model in class_model.get("methods", []):
                    self.register_method(class_model, method_model)

            for function_model in file_model.get("functions", []):
                self.register_function(function_model)

    def _add_to_list_index(self, index: dict, key: str, symbol: dict):
        """
        Adds a symbol to an index whose values are lists.

        This helper is used for simple-name indexes, where several elements can
        share the same name.
        """

        if not key:
            return

        if key not in index:
            index[key] = []

        index[key].append(symbol)

    def register_module(self, module_model: dict):
        """
        Registers a Python module by qualified name.
        """

        qualified_name = module_model.get("qualified_name")

        if not qualified_name:
            return

        symbol = {
            "id": module_model.get("id"),
            "name": module_model.get("name"),
            "qualified_name": qualified_name,
            "path": module_model.get("path"),
            "type": "module",
        }

        self.modules_by_qualified_name[qualified_name] = symbol

    def register_class(self, class_model: dict):
        """
        Registers a class by qualified name and by simple name.
        """

        name = class_model.get("name")
        qualified_name = class_model.get("qualified_name")

        if not name or not qualified_name:
            return

        symbol = {
            "id": class_model.get("id"),
            "name": name,
            "qualified_name": qualified_name,
            "type": "class",
            "bases": class_model.get("bases", []),
        }

        self.classes_by_qualified_name[qualified_name] = symbol
        self._add_to_list_index(self.classes_by_name, name, symbol)

    def register_function(self, function_model: dict):
        """
        Registers a module-level function by qualified name and by simple name.
        """

        name = function_model.get("name")
        qualified_name = function_model.get("qualified_name")

        if not name or not qualified_name:
            return

        symbol = {
            "id": function_model.get("id"),
            "name": name,
            "qualified_name": qualified_name,
            "type": "function",
        }

        self.functions_by_qualified_name[qualified_name] = symbol
        self._add_to_list_index(self.functions_by_name, name, symbol)

    def register_method(self, class_model: dict, method_model: dict):
        """
        Registers a method by qualified name, by method name and by class.method.

        The method is indexed using:

        - its fully qualified method name;
        - its simple method name;
        - ClassName.methodName;
        - QualifiedClassName.methodName, when available.
        """

        method_name = method_model.get("name")
        method_qualified_name = method_model.get("qualified_name")
        class_name = class_model.get("name")
        class_qualified_name = class_model.get("qualified_name")

        if not method_name or not method_qualified_name or not class_name:
            return

        symbol = {
            "id": method_model.get("id"),
            "name": method_name,
            "qualified_name": method_qualified_name,
            "class_name": class_name,
            "class_qualified_name": class_qualified_name,
            "type": "method",
        }

        self.methods_by_qualified_name[method_qualified_name] = symbol

        self._add_to_list_index(
            self.methods_by_name,
            method_name,
            symbol,
        )

        self._add_to_list_index(
            self.methods_by_class_and_name,
            f"{class_name}.{method_name}",
            symbol,
        )

        if class_qualified_name:
            self._add_to_list_index(
                self.methods_by_class_and_name,
                f"{class_qualified_name}.{method_name}",
                symbol,
            )

    def find_module(self, qualified_name: str):
        """
        Finds a module by qualified name.
        """

        return self.modules_by_qualified_name.get(qualified_name)

    def find_class_by_qualified_name(self, qualified_name: str):
        """
        Finds a class by qualified name.
        """

        return self.classes_by_qualified_name.get(qualified_name)

    def find_classes_by_name(self, name: str):
        """
        Finds all classes with the given simple name.
        """

        return self.classes_by_name.get(name, [])

    def find_function_by_qualified_name(self, qualified_name: str):
        """
        Finds a module-level function by qualified name.
        """

        return self.functions_by_qualified_name.get(qualified_name)

    def find_functions_by_name(self, name: str):
        """
        Finds all module-level functions with the given simple name.
        """

        return self.functions_by_name.get(name, [])

    def find_method_by_qualified_name(self, qualified_name: str):
        """
        Finds a method by qualified name.
        """

        return self.methods_by_qualified_name.get(qualified_name)

    def find_methods_by_name(self, name: str):
        """
        Finds all methods with the given simple name.
        """

        return self.methods_by_name.get(name, [])

    def find_methods_by_class_and_name(self, class_and_method_name: str):
        """
        Finds all methods matching either ClassName.methodName or
        QualifiedClassName.methodName.
        """

        return self.methods_by_class_and_name.get(class_and_method_name, [])

    def to_dict(self):
        """
        Returns the symbol table as a JSON-serializable dictionary.
        """

        return {
            "modules_by_qualified_name": self.modules_by_qualified_name,
            "classes_by_qualified_name": self.classes_by_qualified_name,
            "classes_by_name": self.classes_by_name,
            "functions_by_qualified_name": self.functions_by_qualified_name,
            "functions_by_name": self.functions_by_name,
            "methods_by_qualified_name": self.methods_by_qualified_name,
            "methods_by_name": self.methods_by_name,
            "methods_by_class_and_name": self.methods_by_class_and_name,
        }
