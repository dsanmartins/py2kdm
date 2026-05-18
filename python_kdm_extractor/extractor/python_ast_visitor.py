import ast
from pathlib import Path

from extractor.ast_name_resolver import ASTNameResolver
from extractor.model_id_builder import ModelIdBuilder
from extractor.call_analyzer import CallAnalyzer
from extractor.body_extractor import BodyExtractor
from extractor.value_analyzer import ValueAnalyzer


class PythonASTVisitor(ast.NodeVisitor):
    """
    Visits a Python AST and builds a file-level intermediate JSON model.

    This visitor is the main AST traversal component of python_kdm_extractor.
    It extracts structural and behavioral information from a Python source file
    and stores it in a JSON-compatible dictionary.

    The visitor extracts:

    - module metadata;
    - imports and from-imports;
    - classes and inheritance information;
    - methods and module-level functions;
    - signatures, parameters, defaults and return annotations;
    - decorators and method kinds;
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
        """

        self.file_path = file_path
        self.project_root = project_root

        self.name_resolver = ASTNameResolver()
        self.id_builder = ModelIdBuilder(project_root, file_path)
        self.call_analyzer = CallAnalyzer()
        self.body_extractor = BodyExtractor()
        self.value_analyzer = ValueAnalyzer(
            self.name_resolver,
            self.call_analyzer,
        )

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

    # ------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------

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
        from .repository import UserRepository
        """

        for alias in node.names:
            self.model["imports"].append(
                {
                    "type": "from_import",
                    "module": node.module,
                    "name": alias.name,
                    "alias": alias.asname,
                    "level": getattr(node, "level", 0),
                    "line": node.lineno,
                }
            )

        self.generic_visit(node)

    # ------------------------------------------------------------
    # Class and callable definitions
    # ------------------------------------------------------------

    def visit_ClassDef(self, node):
        """
        Extracts a Python class definition.

        The class model includes its id, name, qualified name, base classes,
        decorators, methods, class attributes, instance attributes and source
        location.
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
            "decorators": self._extract_decorators(node),
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

        The function model includes signature metadata, parameters, decorators,
        local variables, calls, control structures and executable body nodes.
        """

        self._visit_callable_def(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        """
        Extracts an async function or method definition.
        """

        self._visit_callable_def(node, is_async=True)

    def _visit_callable_def(self, node, is_async: bool):
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

        decorators = self._extract_decorators(node)
        method_kind = self._infer_method_kind(
            node=node,
            function_type=function_type,
            decorators=decorators,
        )

        parameters = self._extract_parameters(node)
        return_annotation = self.name_resolver.get_name(node.returns) if node.returns else None

        function_model = {
            "id": function_id,
            "name": node.name,
            "qualified_name": qualified_name,
            "type": function_type,
            "method_kind": method_kind,
            "is_async": is_async,
            "decorators": decorators,
            "return_annotation": return_annotation,
            "signature": {
                "parameters": parameters,
                "return_annotation": return_annotation,
                "is_async": is_async,
                "method_kind": method_kind,
            },
            "parameters": parameters,
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

    # ------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------

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
        value_info = self.value_analyzer.analyze_value(node.value)
        assigned_value = value_info.get("value")

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
                        "value_kind": value_info.get("value_kind"),
                        "value_type": value_info.get("value_type"),
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
                        "value_kind": value_info.get("value_kind"),
                        "value_type": value_info.get("value_type"),
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
                        "value_kind": value_info.get("value_kind"),
                        "value_type": value_info.get("value_type"),
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
        value_info = self.value_analyzer.analyze_value(node.value)
        assigned_value = value_info.get("value") if node.value else None
        value_kind = value_info.get("value_kind") if node.value else None
        value_type = value_info.get("value_type") if node.value else None

        if name is not None:
            # Case 1: class attribute with type annotation
            if self.current_class is not None and self.current_function is None:
                self.current_class["attributes"].append(
                    {
                        "name": name,
                        "type": "class_attribute",
                        "annotation": annotation,
                        "assigned_value": assigned_value,
                        "assigned_type": assigned_type or annotation,
                        "value_kind": value_kind,
                        "value_type": value_type,
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
                        "value_kind": value_kind,
                        "value_type": value_type,
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
                        "value_kind": value_kind,
                        "value_type": value_type,
                        "line": node.lineno,
                    }
                )

        self.generic_visit(node)

    # ------------------------------------------------------------
    # Calls and control structures
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Type and signature helpers
    # ------------------------------------------------------------

    def _get_assigned_type_from_value(self, value_node):
        """
        Attempts to infer the assigned type from the right-hand side of an
        assignment.
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
        Extracts function or method parameters with annotations, defaults,
        argument kind and source position.

        Supported parameter kinds:

        - positional_only;
        - positional_or_keyword;
        - vararg;
        - keyword_only;
        - kwarg.
        """

        parameters = []

        positional_only_args = list(getattr(node.args, "posonlyargs", []))
        positional_or_keyword_args = list(node.args.args)
        default_values = self._align_defaults(
            positional_only_args + positional_or_keyword_args,
            node.args.defaults,
        )

        for index, arg in enumerate(positional_only_args):
            parameters.append(
                self._build_parameter_model(
                    arg=arg,
                    kind="positional_only",
                    index=index,
                    default_value=default_values.get(id(arg)),
                )
            )

        offset = len(positional_only_args)

        for index, arg in enumerate(positional_or_keyword_args):
            parameters.append(
                self._build_parameter_model(
                    arg=arg,
                    kind="positional_or_keyword",
                    index=offset + index,
                    default_value=default_values.get(id(arg)),
                )
            )

        if node.args.vararg is not None:
            parameters.append(
                self._build_parameter_model(
                    arg=node.args.vararg,
                    kind="vararg",
                    index=len(parameters),
                    default_value=None,
                )
            )

        for index, arg in enumerate(node.args.kwonlyargs):
            default_node = node.args.kw_defaults[index]
            parameters.append(
                self._build_parameter_model(
                    arg=arg,
                    kind="keyword_only",
                    index=len(parameters),
                    default_value=self.name_resolver.get_name(default_node)
                    if default_node is not None
                    else None,
                )
            )

        if node.args.kwarg is not None:
            parameters.append(
                self._build_parameter_model(
                    arg=node.args.kwarg,
                    kind="kwarg",
                    index=len(parameters),
                    default_value=None,
                )
            )

        return parameters

    def _build_parameter_model(
        self,
        arg,
        kind: str,
        index: int,
        default_value,
    ):
        """
        Builds the JSON representation of one parameter.
        """

        return {
            "name": arg.arg,
            "annotation": self.name_resolver.get_name(arg.annotation)
            if arg.annotation
            else None,
            "kind": kind,
            "index": index,
            "default_value": default_value,
            "line": getattr(arg, "lineno", None),
            "resolved_type_id": None,
            "resolved_type_qualified_name": None,
            "type_resolution": None,
        }

    def _align_defaults(self, args: list, defaults: list):
        """
        Aligns Python default values with their corresponding positional args.
        """

        result = {}

        if not args or not defaults:
            return result

        start = len(args) - len(defaults)

        for arg, default_node in zip(args[start:], defaults):
            result[id(arg)] = self.name_resolver.get_name(default_node)

        return result

    def _extract_decorators(self, node):
        """
        Extracts decorators from a class, function or method definition.
        """

        return [
            self.name_resolver.get_name(decorator)
            for decorator in getattr(node, "decorator_list", [])
            if self.name_resolver.get_name(decorator) is not None
        ]

    def _infer_method_kind(
        self,
        node,
        function_type: str,
        decorators: list,
    ):
        """
        Infers the method kind from name and decorators.
        """

        if function_type != "method":
            return "function"

        decorator_names = set(decorators or [])

        if node.name == "__init__":
            return "constructor"

        if "staticmethod" in decorator_names:
            return "staticmethod"

        if "classmethod" in decorator_names:
            return "classmethod"

        if "property" in decorator_names:
            return "property_getter"

        for decorator in decorator_names:
            if decorator.endswith(".setter"):
                return "property_setter"

            if decorator.endswith(".deleter"):
                return "property_deleter"

            if decorator.endswith("abstractmethod"):
                return "abstract_method"

        return "method"
