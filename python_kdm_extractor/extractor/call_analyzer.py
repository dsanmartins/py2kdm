import ast

from extractor.ast_name_resolver import ASTNameResolver


class CallAnalyzer:
    """
    Builds structured call information from Python ast.Call nodes.

    This component converts raw Python call expressions into JSON-compatible
    dictionaries used by the rest of the extraction pipeline. The generated
    call models are later enriched by CallResolver, which attempts to resolve
    each call to a concrete project element, builtin element or external target.

    The analyzer distinguishes three main cases:

    - method calls:
        service.create_user(...)

    - function calls:
        validate_name(...)

    - unknown calls:
        any call expression that cannot be classified as a simple ast.Name or
        ast.Attribute call target.

    The analyzer does not resolve calls by itself. It only extracts their local
    syntactic information.
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

        if isinstance(node.func, ast.Attribute):
            receiver = self.name_resolver.get_name(node.func.value)
            method = node.func.attr

            return {
                "name": call_name,
                "kind": "method_call",
                "receiver": receiver,
                "method": method,
                "line": node.lineno,
                "resolved": False,
                "target_id": None,
            }

        if isinstance(node.func, ast.Name):
            return {
                "name": call_name,
                "kind": "function_call",
                "receiver": None,
                "function": node.func.id,
                "line": node.lineno,
                "resolved": False,
                "target_id": None,
            }

        return {
            "name": call_name,
            "kind": "unknown_call",
            "receiver": None,
            "line": node.lineno,
            "resolved": False,
            "target_id": None,
        }
