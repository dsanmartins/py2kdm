import ast

from extractor.ast_name_resolver import ASTNameResolver


class CallAnalyzer:
    """
    Builds structured call information from Python ast.Call nodes.

    This component converts raw Python call expressions into JSON-compatible
    dictionaries used by the rest of the extraction pipeline. The generated
    call models are later enriched by CallResolver, which attempts to resolve
    each call to a concrete project element, builtin element or external target.

    The analyzer extracts:

    - call name;
    - call kind;
    - receiver and method name for method calls;
    - function name for function calls;
    - source location;
    - positional arguments;
    - keyword arguments;
    - compact call signature.

    This class intentionally does not import ValueAnalyzer. ValueAnalyzer uses
    CallAnalyzer to describe calls assigned as values. Importing ValueAnalyzer
    here would create a circular dependency.
    """

    def __init__(self):
        """
        Initializes the call analyzer.

        ASTNameResolver is used to convert AST nodes into readable names such
        as ``json.dumps``, ``self.repository.save`` or ``User``.
        """

        self.name_resolver = ASTNameResolver()

    def analyze_call(self, node: ast.Call):
        """
        Converts an ast.Call node into a structured call model.

        Parameters
        ----------
        node:
            Python AST call node.

        Returns
        -------
        dict | None
            JSON-compatible call model, or None when the call target name
            cannot be extracted.

        Returned models contain common resolution fields:

        - resolved: initially False.
        - target_id: initially None.

        These fields are updated later by CallResolver.
        """

        call_name = self.name_resolver.get_name(node.func)

        if call_name is None:
            return None

        base_model = self._base_call_model(node, call_name)

        if isinstance(node.func, ast.Attribute):
            receiver = self.name_resolver.get_name(node.func.value)
            method = node.func.attr

            base_model.update(
                {
                    "kind": "method_call",
                    "receiver": receiver,
                    "method": method,
                }
            )

            return base_model

        if isinstance(node.func, ast.Name):
            base_model.update(
                {
                    "kind": "function_call",
                    "receiver": None,
                    "function": node.func.id,
                }
            )

            return base_model

        base_model.update(
            {
                "kind": "unknown_call",
                "receiver": None,
            }
        )

        return base_model

    def _base_call_model(self, node: ast.Call, call_name: str):
        """
        Builds fields shared by function, method and unknown calls.
        """

        arguments = self._extract_arguments(node)
        keyword_arguments = self._extract_keyword_arguments(node)

        return {
            "name": call_name,
            "line": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
            "arguments": arguments,
            "keyword_arguments": keyword_arguments,
            "argument_count": len(arguments),
            "keyword_argument_count": len(keyword_arguments),
            "call_signature": self._build_call_signature(
                call_name,
                arguments,
                keyword_arguments,
            ),
            "resolved": False,
            "target_id": None,
        }

    def _extract_arguments(self, node: ast.Call):
        """
        Extracts positional arguments from a call.

        Each argument is represented by a compact dictionary containing:

        - position;
        - value;
        - argument_kind;
        - argument_type when it can be locally inferred.
        """

        arguments = []

        for position, argument in enumerate(node.args):
            arguments.append(
                {
                    "position": position,
                    "value": self.name_resolver.get_name(argument),
                    "argument_kind": self._classify_argument(argument),
                    "argument_type": self._infer_literal_type(argument),
                }
            )

        return arguments

    def _extract_keyword_arguments(self, node: ast.Call):
        """
        Extracts keyword arguments from a call.

        Example
        -------
        User(name="Irene", active=True)

        Produces keyword argument entries for name and active.
        """

        keyword_arguments = []

        for keyword in node.keywords:
            keyword_arguments.append(
                {
                    "name": keyword.arg,
                    "value": self.name_resolver.get_name(keyword.value),
                    "argument_kind": self._classify_argument(keyword.value),
                    "argument_type": self._infer_literal_type(keyword.value),
                }
            )

        return keyword_arguments

    def _classify_argument(self, node):
        """
        Classifies a call argument at a lightweight syntactic level.
        """

        if isinstance(node, ast.Constant):
            return "literal"

        if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            return "collection_literal"

        if isinstance(node, ast.Call):
            return "call_result"

        if isinstance(node, ast.Name):
            return "variable_reference"

        if isinstance(node, ast.Attribute):
            return "attribute_reference"

        if isinstance(node, ast.BinOp):
            return "binary_expression"

        if isinstance(node, ast.Compare):
            return "comparison_expression"

        if isinstance(node, ast.BoolOp):
            return "boolean_expression"

        if isinstance(node, ast.UnaryOp):
            return "unary_expression"

        return "expression"

    def _infer_literal_type(self, node):
        """
        Infers a lightweight Python type for literals and collections.
        """

        if isinstance(node, ast.Constant):
            return type(node.value).__name__

        if isinstance(node, ast.List):
            return "list"

        if isinstance(node, ast.Tuple):
            return "tuple"

        if isinstance(node, ast.Set):
            return "set"

        if isinstance(node, ast.Dict):
            return "dict"

        return None

    def _build_call_signature(
        self,
        call_name: str,
        arguments: list,
        keyword_arguments: list,
    ):
        """
        Builds a compact readable call signature.

        The signature is intended for diagnostics and traceability only. It is
        not intended to reconstruct full Python source code.
        """

        argument_values = [
            argument.get("value")
            for argument in arguments
            if argument.get("value") is not None
        ]

        keyword_values = []

        for keyword_argument in keyword_arguments:
            keyword_name = keyword_argument.get("name")
            keyword_value = keyword_argument.get("value")

            if keyword_name is None:
                # Handles **kwargs.
                keyword_values.append(f"**{keyword_value}")
            elif keyword_value is not None:
                keyword_values.append(f"{keyword_name}={keyword_value}")
            else:
                keyword_values.append(keyword_name)

        all_values = argument_values + keyword_values

        return f"{call_name}({', '.join(all_values)})"
