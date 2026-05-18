import ast


class ValueAnalyzer:
    """
    Classifies Python assignment values for the intermediate JSON model.

    The analyzer enriches assignment nodes with value metadata that can later be
    transformed into KDM HasValue relationships. It does not create KDM
    elements directly.
    """

    def __init__(self, name_resolver, call_analyzer):
        self.name_resolver = name_resolver
        self.call_analyzer = call_analyzer

    def analyze_value(self, node):
        """
        Classifies the value represented by an AST node.

        Returns a dictionary with value, value_kind and value_type. For calls,
        it also returns value_call.
        """

        if node is None:
            return {"value": None, "value_kind": "unknown", "value_type": None}

        if isinstance(node, ast.Constant):
            return {
                "value": repr(node.value),
                "value_kind": "literal",
                "value_type": type(node.value).__name__,
            }

        if isinstance(node, ast.List):
            return {"value": "[]", "value_kind": "collection_literal", "value_type": "list"}

        if isinstance(node, ast.Tuple):
            return {"value": "()", "value_kind": "collection_literal", "value_type": "tuple"}

        if isinstance(node, ast.Set):
            return {"value": "set()", "value_kind": "collection_literal", "value_type": "set"}

        if isinstance(node, ast.Dict):
            return {"value": "{}", "value_kind": "collection_literal", "value_type": "dict"}

        if isinstance(node, ast.Call):
            return {
                "value": self.name_resolver.get_name(node),
                "value_kind": "call_result",
                "value_type": None,
                "value_call": self.call_analyzer.analyze_call(node),
            }

        if isinstance(node, ast.Name):
            return {"value": node.id, "value_kind": "variable_reference", "value_type": None}

        if isinstance(node, ast.Attribute):
            return {
                "value": self.name_resolver.get_name(node),
                "value_kind": "attribute_reference",
                "value_type": None,
            }

        return {
            "value": self.name_resolver.get_name(node),
            "value_kind": "expression",
            "value_type": type(node).__name__,
        }
