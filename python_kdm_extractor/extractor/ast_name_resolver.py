import ast


class ASTNameResolver:
    """
    Converts Python AST nodes into readable string representations.

    This helper is used throughout the extractor to normalize Python AST
    expressions into simple textual names that can be stored in the
    intermediate JSON model.

    Examples
    --------
    ast.Name("user")                  -> "user"
    ast.Attribute(self, "repository") -> "self.repository"
    ast.Call(User(...))               -> "User"
    ast.Compare(x > 0)                -> "x > 0"
    ast.BoolOp(a and b)               -> "a and b"

    The resolver intentionally produces compact, human-readable names. It does
    not try to reconstruct full Python source code.
    """

    def get_name(self, node):
        """
        Returns a readable name for a supported AST node.

        Parameters
        ----------
        node:
            Python AST node.

        Returns
        -------
        str | None
            Readable string representation, or None if the node type is not
            supported.
        """

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
        """
        Converts a comparison expression into a readable string.

        Examples
        --------
        x > 0        -> "x > 0"
        a <= b < c   -> "a <= b < c"
        item in data -> "item in data"
        """

        left = self.get_name(node.left)
        operators = [self.get_operator(op) for op in node.ops]
        comparators = [self.get_name(comp) for comp in node.comparators]

        parts = [left]

        for operator, comparator in zip(operators, comparators):
            parts.append(operator)
            parts.append(comparator)

        return " ".join(part for part in parts if part is not None)

    def get_bool_operation_name(self, node):
        """
        Converts a boolean operation into a readable string.

        Examples
        --------
        a and b -> "a and b"
        a or b  -> "a or b"
        """

        operator = self.get_bool_operator(node.op)
        values = [self.get_name(value) for value in node.values]

        return f" {operator} ".join(
            value for value in values if value is not None
        )

    def get_unary_operation_name(self, node):
        """
        Converts a unary operation into a readable string.

        Examples
        --------
        not active -> "not active"
        -x         -> "- x"
        +x         -> "+ x"
        """

        operator = self.get_unary_operator(node.op)
        operand = self.get_name(node.operand)

        if operand is None:
            return operator

        return f"{operator} {operand}"

    def get_operator(self, op):
        """
        Returns the textual representation of a comparison operator.
        """

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
        """
        Returns the textual representation of a boolean operator.
        """

        if isinstance(op, ast.And):
            return "and"
        if isinstance(op, ast.Or):
            return "or"

        return type(op).__name__

    def get_unary_operator(self, op):
        """
        Returns the textual representation of a unary operator.
        """

        if isinstance(op, ast.Not):
            return "not"
        if isinstance(op, ast.USub):
            return "-"
        if isinstance(op, ast.UAdd):
            return "+"

        return type(op).__name__
