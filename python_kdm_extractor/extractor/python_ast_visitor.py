import ast
from pathlib import Path

from extractor.ast_name_resolver import ASTNameResolver
from extractor.model_id_builder import ModelIdBuilder
from extractor.call_analyzer import CallAnalyzer
from extractor.body_extractor import BodyExtractor


class PythonASTVisitor(ast.NodeVisitor):
    """
    Visits a Python AST and builds a file-level intermediate JSON model.

    This visitor is the main AST traversal component of `python_kdm_extractor`.
    It extracts structural and behavioral information from a Python source file
    and stores it in a JSON-compatible dictionary.

    The visitor extracts:

    - module metadata;
    - imports and from-imports;
    - classes and inheritance information;
    - methods and module-level functions;
    - parameters and type annotations;
    - class attributes;
    - instance attributes;
    - local variables;
    - function and method calls;
    - control structures;
    - executable body nodes through BodyExtractor.

    The resulting model is later enriched by other extractor components such as
    SymbolTable, ImportResolver, CallResolver, BodyCallSynchronizer,
    RelationshipBuilder, ElementBuilder and SummaryBuilder.
    """

    def __init__(self, file_path: Path, project_root: Path):
        """
        Initializes the AST visitor for a single Python source file.

        Parameters
        ----------
        file_path:
            Path to the Python source file being analyzed.

        project_root:
            Root directory of the analyzed Python project. It is used to build
            relative paths, module identifiers and qualified names.
        """

        self.file_path = file_path
        self.project_root = project_root

        self.name_resolver = ASTNameResolver()
        self.id_builder = ModelIdBuilder(project_root, file_path)
        self.call_analyzer = CallAnalyzer()
        self.body_extractor = BodyExtractor()

        self.model = {
            "id": self.id_builder.get_module_id(),
            "path": str(file_path.relative_to(project_root)),
            "name": file_path.stem,
            "qualified_name": self.id_builder.get_module_qualified_name(),
            "type": "module",
            "imports": [],
            "classes": [],
            "functions": [],
        }

        self.current_class = None
        self.current_function = None

    def visit_Import(self, node):
        """
        Extracts standard import statements.

        Example
        -------
        import json
        import pathlib as pl
        """

        for alias in node.names:
            self.model["imports"].append(
                {
                    "type": "import",
                    "module": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """
        Extracts from-import statements.

        Example
        -------
        from services.user_service import UserService
        """

        for alias in node.names:
            self.model["imports"].append(
                {
                    "type": "from_import",
                    "module": node.module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """
        Extracts a Python class definition.

        The class model includes its id, name, qualified name, base classes,
        methods, class attributes, instance attributes and source location.
        """

        class_qualified_name = self.id_builder.get_class_qualified_name(node.name)

        class_model = {
            "id": self.id_builder.get_class_id(node.name),
            "name": node.name,
            "qualified_name": class_qualified_name,
            "type": "class",
            "bases": [
                self.name_resolver.get_name(base)
                for base in node.bases
            ],
            "methods": [],
            "attributes": [],
            "instance_attributes": [],
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
        }

        previous_class = self.current_class
        self.current_class = class_model

        self.generic_visit(node)

        self.model["classes"].append(class_model)
        self.current_class = previous_class

    def visit_FunctionDef(self, node):
        """
        Extracts a Python function or method definition.

        If the visitor is currently inside a class, the function is represented
        as a method. Otherwise, it is represented as a module-level function.

        The function model includes parameters, local variables, calls, control
        structures and executable body nodes.
        """

        if self.current_class is not None:
            function_id = self.id_builder.get_method_id(
                self.current_class["name"],
                node.name,
            )
            qualified_name = self.id_builder.get_method_qualified_name(
                self.current_class["name"],
                node.name,
            )
            function_type = "method"
        else:
            function_id = self.id_builder.get_function_id(node.name)
            qualified_name = self.id_builder.get_function_qualified_name(node.name)
            function_type = "function"

        function_model = {
            "id": function_id,
            "name": node.name,
            "qualified_name": qualified_name,
            "type": function_type,
            "parameters": self._extract_parameters(node),
            "calls": [],
            "local_variables": [],
            "control_structures": [],
            "body": self.body_extractor.extract_body(
                node.body,
                parent_id=function_id,
            ),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
        }

        previous_function = self.current_function
        self.current_function = function_model

        self.generic_visit(node)

        if self.current_class is not None:
            self.current_class["methods"].append(function_model)
        else:
            self.model["functions"].append(function_model)

        self.current_function = previous_function

    def visit_AsyncFunctionDef(self, node):
        """
        Extracts an async function using the same model as a regular function.
        """

        self.visit_FunctionDef(node)

    def visit_Assign(self, node):
        """
        Extracts assignments to class attributes, instance attributes and local
        variables.

        Examples
        --------
        service_name = "user-service"
        self.repository = UserRepository()
        user = User()
        """

        assigned_type = self._get_assigned_type_from_value(node.value)
        assigned_value = self.name_resolver.get_name(node.value)

        for target in node.targets:
            name = self.name_resolver.get_name(target)

            if name is None:
                continue

            # Case 1: class attribute
            if self.current_class is not None and self.current_function is None:
                self.current_class["attributes"].append(
                    {
                        "name": name,
                        "type": "class_attribute",
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type,
                        "line": node.lineno,
                    }
                )

            # Case 2: instance attribute
            elif (
                self.current_class is not None
                and self.current_function is not None
                and name.startswith("self.")
            ):
                attribute_name = name.replace("self.", "", 1)

                self.current_class["instance_attributes"].append(
                    {
                        "name": attribute_name,
                        "full_name": name,
                        "defined_in": self.current_function.get("qualified_name"),
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type,
                        "resolved_type_id": None,
                        "line": node.lineno,
                    }
                )

            # Case 3: local variable
            elif self.current_function is not None:
                self.current_function["local_variables"].append(
                    {
                        "name": name,
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type,
                        "line": node.lineno,
                    }
                )

        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        """
        Extracts annotated assignments.

        Examples
        --------
        name: str = "Irene"
        self.repository: UserRepository = UserRepository()
        """

        name = self.name_resolver.get_name(node.target)
        annotation = self.name_resolver.get_name(node.annotation)
        assigned_type = self._get_assigned_type_from_value(node.value) if node.value else None
        assigned_value = self.name_resolver.get_name(node.value) if node.value else None

        if name is not None:
            # Case 1: class attribute with type annotation
            if self.current_class is not None and self.current_function is None:
                self.current_class["attributes"].append(
                    {
                        "name": name,
                        "type": "class_attribute",
                        "annotation": annotation,
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type,
                        "line": node.lineno,
                    }
                )

            # Case 2: instance attribute with type annotation
            elif (
                self.current_class is not None
                and self.current_function is not None
                and name.startswith("self.")
            ):
                attribute_name = name.replace("self.", "", 1)

                self.current_class["instance_attributes"].append(
                    {
                        "name": attribute_name,
                        "full_name": name,
                        "defined_in": self.current_function.get("qualified_name"),
                        "annotation": annotation,
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type or annotation,
                        "resolved_type_id": None,
                        "line": node.lineno,
                    }
                )

            # Case 3: local variable with annotation
            elif self.current_function is not None:
                self.current_function["local_variables"].append(
                    {
                        "name": name,
                        "annotation": annotation,
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type or annotation,
                        "line": node.lineno,
                    }
                )

        self.generic_visit(node)

    def visit_Call(self, node):
        """
        Extracts a function, method or constructor call inside the current
        function or method.
        """

        if self.current_function is not None:
            call_model = self.call_analyzer.analyze_call(node)

            if call_model is not None:
                self.current_function["calls"].append(call_model)

        self.generic_visit(node)

    def visit_If(self, node):
        """
        Extracts a lightweight summary of an if control structure.
        """

        if self.current_function is not None:
            self.current_function["control_structures"].append(
                {
                    "type": "if",
                    "condition": self.name_resolver.get_name(node.test),
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def visit_For(self, node):
        """
        Extracts a lightweight summary of a for control structure.
        """

        if self.current_function is not None:
            self.current_function["control_structures"].append(
                {
                    "type": "for",
                    "target": self.name_resolver.get_name(node.target),
                    "iter": self.name_resolver.get_name(node.iter),
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        """
        Extracts an async for statement using the same model as a regular for.
        """

        self.visit_For(node)

    def visit_While(self, node):
        """
        Extracts a lightweight summary of a while control structure.
        """

        if self.current_function is not None:
            self.current_function["control_structures"].append(
                {
                    "type": "while",
                    "condition": self.name_resolver.get_name(node.test),
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def visit_Try(self, node):
        """
        Extracts a lightweight summary of a try statement.

        Detailed executable body information for try, except and finally blocks
        is extracted by BodyExtractor. This method keeps a compact
        control-structure summary.
        """

        if self.current_function is not None:
            handlers = []

            for handler in node.handlers:
                handlers.append(
                    {
                        "exception": self.name_resolver.get_name(handler.type)
                        if handler.type else "Exception",
                        "line": handler.lineno,
                    }
                )

            self.current_function["control_structures"].append(
                {
                    "type": "try",
                    "handlers": handlers,
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    def _get_assigned_type_from_value(self, value_node):
        """
        Attempts to infer the assigned type from the right-hand side of an
        assignment.

        Examples
        --------
        self.repository = UserRepository()  -> UserRepository
        self.roles = []                     -> list
        data = {}                           -> dict
        name = "Irene"                      -> str
        active = True                       -> bool
        attempts = 0                        -> int
        ratio = 0.5                         -> float
        """

        if value_node is None:
            return None

        if isinstance(value_node, ast.Call):
            return self.name_resolver.get_name(value_node.func)

        if isinstance(value_node, ast.List):
            return "list"

        if isinstance(value_node, ast.Dict):
            return "dict"

        if isinstance(value_node, ast.Tuple):
            return "tuple"

        if isinstance(value_node, ast.Set):
            return "set"

        if isinstance(value_node, ast.Constant):
            value = value_node.value

            if isinstance(value, bool):
                return "bool"

            if isinstance(value, int):
                return "int"

            if isinstance(value, float):
                return "float"

            if isinstance(value, str):
                return "str"

            if value is None:
                return "NoneType"

        return None

    def _extract_parameters(self, node):
        """
        Extracts function or method parameters with optional type annotations.

        Example
        -------
        def save(self, user: User):
            ...

        Produces
        --------
        [
            {"name": "self", "annotation": null},
            {"name": "user", "annotation": "User"}
        ]
        """

        parameters = []

        for arg in node.args.args:
            parameters.append(
                {
                    "name": arg.arg,
                    "annotation": self.name_resolver.get_name(arg.annotation)
                    if arg.annotation else None,
                    "resolved_type_id": None,
                    "resolved_type_qualified_name": None,
                    "type_resolution": None,
                }
            )

        return parameters
