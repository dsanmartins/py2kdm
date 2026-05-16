import ast

from extractor.ast_name_resolver import ASTNameResolver


class CallAnalyzer:
    """
    Builds structured call information from ast.Call nodes.
    """

    def __init__(self):
        self.name_resolver = ASTNameResolver()

    def analyze_call(self, node: ast.Call):
        """
        Converts an ast.Call node into a structured call model.
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
                "target_id": None
            }

        if isinstance(node.func, ast.Name):
            return {
                "name": call_name,
                "kind": "function_call",
                "receiver": None,
                "function": node.func.id,
                "line": node.lineno,
                "resolved": False,
                "target_id": None
            }

        return {
            "name": call_name,
            "kind": "unknown_call",
            "receiver": None,
            "line": node.lineno,
            "resolved": False,
            "target_id": None
        }
