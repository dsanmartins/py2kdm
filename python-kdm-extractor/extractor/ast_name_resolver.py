import ast


class ASTNameResolver:
    """
    Converts Python AST nodes into readable string representations.
    """

    def get_name(self, node):
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            value = self.get_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr

        if isinstance(node, ast.Constant):
            return repr(node.value)

        if isinstance(node, ast.Subscript):
            return self.get_name(node.value)

        if isinstance(node, ast.Call):
            return self.get_name(node.func)

        if isinstance(node, ast.Compare):
            return self.get_compare_name(node)

        if isinstance(node, ast.BoolOp):
            return self.get_bool_operation_name(node)

        if isinstance(node, ast.UnaryOp):
            return self.get_unary_operation_name(node)

        return None

    def get_compare_name(self, node):
        left = self.get_name(node.left)
        operators = [self.get_operator(op) for op in node.ops]
        comparators = [self.get_name(comp) for comp in node.comparators]

        parts = [left]

        for operator, comparator in zip(operators, comparators):
            parts.append(operator)
            parts.append(comparator)

        return " ".join(part for part in parts if part is not None)

    def get_bool_operation_name(self, node):
        operator = self.get_bool_operator(node.op)
        values = [self.get_name(value) for value in node.values]

        return f" {operator} ".join(
            value for value in values if value is not None
        )

    def get_unary_operation_name(self, node):
        operator = self.get_unary_operator(node.op)
        operand = self.get_name(node.operand)

        if operand is None:
            return operator

        return f"{operator} {operand}"

    def get_operator(self, op):
        if isinstance(op, ast.Eq):
            return "=="
        if isinstance(op, ast.NotEq):
            return "!="
        if isinstance(op, ast.Lt):
            return "<"
        if isinstance(op, ast.LtE):
            return "<="
        if isinstance(op, ast.Gt):
            return ">"
        if isinstance(op, ast.GtE):
            return ">="
        if isinstance(op, ast.Is):
            return "is"
        if isinstance(op, ast.IsNot):
            return "is not"
        if isinstance(op, ast.In):
            return "in"
        if isinstance(op, ast.NotIn):
            return "not in"

        return type(op).__name__

    def get_bool_operator(self, op):
        if isinstance(op, ast.And):
            return "and"
        if isinstance(op, ast.Or):
            return "or"

        return type(op).__name__

    def get_unary_operator(self, op):
        if isinstance(op, ast.Not):
            return "not"
        if isinstance(op, ast.USub):
            return "-"
        if isinstance(op, ast.UAdd):
            return "+"

        return type(op).__name__
