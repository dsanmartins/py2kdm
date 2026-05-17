import ast
import hashlib

from extractor.ast_name_resolver import ASTNameResolver
from extractor.call_analyzer import CallAnalyzer


class BodyExtractor:
    """
    Extracts a hierarchical representation of executable Python body statements.

    This component converts Python AST statement nodes into the intermediate
    JSON body model consumed later by `kdm_pyecore_generator`.

    It preserves nested executable structures such as:

    - if / else;
    - for / async for;
    - while;
    - try / except / else / finally;
    - with / async with;
    - return;
    - raise;
    - break, continue and pass;
    - expression statements;
    - assignments and annotated assignments;
    - unknown statements as fallback nodes.

    The generated body model is hierarchical. Nested statements are stored in
    fields such as `body`, `orelse`, `handlers` and `finalbody`.

    Each extracted body element receives a stable synthetic id of the form:

        body:<sha1-prefix>

    These ids are later used by the KDM generator to create and index
    ActionElement, BlockUnit, TryUnit, CatchUnit and FinallyUnit elements.
    """

    def __init__(self):
        """
        Initializes the body extractor.

        ASTNameResolver is used to convert AST expressions into readable names.
        CallAnalyzer is used to extract structured call information from
        ast.Call nodes.
        """

        self.name_resolver = ASTNameResolver()
        self.call_analyzer = CallAnalyzer()

    def extract_body(self, statements: list, parent_id: str):
        """
        Extracts a hierarchical body model from a list of AST statements.

        Parameters
        ----------
        statements:
            List of Python AST statement nodes.

        parent_id:
            Identifier of the parent callable or parent body element. It is
            used to generate stable ids for nested body nodes.

        Returns
        -------
        list
            List of JSON-compatible body statement dictionaries.
        """

        body = []

        for index, statement in enumerate(statements):
            statement_model = self.extract_statement(
                statement,
                parent_id=parent_id,
                index=index,
            )

            if statement_model is not None:
                body.append(statement_model)

        return body

    def extract_statement(self, node, parent_id: str, index: int = 0):
        """
        Dispatches a Python AST statement to the corresponding extractor.

        Unsupported AST statements are represented as `unknown` body nodes
        instead of being discarded.
        """

        if isinstance(node, ast.If):
            return self._extract_if(node, parent_id, index)

        if isinstance(node, ast.For):
            return self._extract_for(node, parent_id, index)

        if isinstance(node, ast.AsyncFor):
            return self._extract_for(node, parent_id, index, async_for=True)

        if isinstance(node, ast.While):
            return self._extract_while(node, parent_id, index)

        if isinstance(node, ast.Try):
            return self._extract_try(node, parent_id, index)

        if isinstance(node, ast.With):
            return self._extract_with(node, parent_id, index)

        if isinstance(node, ast.AsyncWith):
            return self._extract_with(node, parent_id, index, async_with=True)

        if isinstance(node, ast.Return):
            return self._extract_return(node, parent_id, index)

        if isinstance(node, ast.Raise):
            return self._extract_raise(node, parent_id, index)

        if isinstance(node, ast.Break):
            return self._extract_simple_statement(node, parent_id, index, "break")

        if isinstance(node, ast.Continue):
            return self._extract_simple_statement(node, parent_id, index, "continue")

        if isinstance(node, ast.Pass):
            return self._extract_simple_statement(node, parent_id, index, "pass")

        if isinstance(node, ast.Expr):
            return self._extract_expr(node, parent_id, index)

        if isinstance(node, ast.Assign):
            return self._extract_assignment(node, parent_id, index)

        if isinstance(node, ast.AnnAssign):
            return self._extract_annotated_assignment(node, parent_id, index)

        return self._extract_unknown_statement(node, parent_id, index)

    def _extract_if(self, node: ast.If, parent_id: str, index: int):
        """
        Extracts an if statement, including its body, else branch and condition
        calls.
        """

        element_id = self._make_id(parent_id, "if", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "control_structure",
            "control_type": "if",
            "condition": self.name_resolver.get_name(node.test),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
            "body": self.extract_body(node.body, element_id),
            "orelse": self.extract_body(node.orelse, element_id),
        }

        self._attach_calls(statement, "condition_calls", node.test)

        return statement

    def _extract_for(
        self,
        node,
        parent_id: str,
        index: int,
        async_for: bool = False,
    ):
        """
        Extracts a for or async for statement.
        """

        control_type = "async_for" if async_for else "for"
        element_id = self._make_id(parent_id, control_type, node.lineno, index)

        statement = {
            "id": element_id,
            "type": "control_structure",
            "control_type": control_type,
            "target": self.name_resolver.get_name(node.target),
            "iter": self.name_resolver.get_name(node.iter),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
            "body": self.extract_body(node.body, element_id),
            "orelse": self.extract_body(node.orelse, element_id),
        }

        self._attach_calls(statement, "iter_calls", node.iter)

        return statement

    def _extract_while(self, node: ast.While, parent_id: str, index: int):
        """
        Extracts a while statement, including condition calls.
        """

        element_id = self._make_id(parent_id, "while", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "control_structure",
            "control_type": "while",
            "condition": self.name_resolver.get_name(node.test),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
            "body": self.extract_body(node.body, element_id),
            "orelse": self.extract_body(node.orelse, element_id),
        }

        self._attach_calls(statement, "condition_calls", node.test)

        return statement

    def _extract_try(self, node: ast.Try, parent_id: str, index: int):
        """
        Extracts a try statement with handlers, else branch and finalbody.

        The resulting JSON structure is later mapped to KDM TryUnit, CatchUnit,
        FinallyUnit, ExceptionFlow and ExitFlow.
        """

        element_id = self._make_id(parent_id, "try", node.lineno, index)

        handlers = []

        for handler_index, handler in enumerate(node.handlers):
            handler_id = self._make_id(
                element_id,
                "except",
                handler.lineno,
                handler_index,
            )

            handlers.append(
                {
                    "id": handler_id,
                    "type": "exception_handler",
                    "exception": self.name_resolver.get_name(handler.type)
                    if handler.type else "Exception",
                    "line_start": handler.lineno,
                    "line_end": getattr(handler, "end_lineno", None),
                    "body": self.extract_body(handler.body, handler_id),
                }
            )

        return {
            "id": element_id,
            "type": "control_structure",
            "control_type": "try",
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
            "body": self.extract_body(node.body, element_id),
            "handlers": handlers,
            "orelse": self.extract_body(node.orelse, element_id),
            "finalbody": self.extract_body(node.finalbody, element_id),
        }

    def _extract_with(
        self,
        node,
        parent_id: str,
        index: int,
        async_with: bool = False,
    ):
        """
        Extracts a with or async with statement.

        Context-manager calls are stored in `context_calls` when present.
        """

        control_type = "async_with" if async_with else "with"
        element_id = self._make_id(parent_id, control_type, node.lineno, index)

        items = []

        for item in node.items:
            item_model = {
                "context_expr": self.name_resolver.get_name(item.context_expr),
                "optional_vars": self.name_resolver.get_name(item.optional_vars)
                if item.optional_vars else None,
            }

            context_calls = self._extract_calls_from_node(item.context_expr)

            if context_calls:
                item_model["context_calls"] = context_calls

            items.append(item_model)

        return {
            "id": element_id,
            "type": "control_structure",
            "control_type": control_type,
            "items": items,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", None),
            "body": self.extract_body(node.body, element_id),
        }

    def _extract_return(self, node: ast.Return, parent_id: str, index: int):
        """
        Extracts a return statement.

        Calls inside the returned expression are stored in `value_calls`.
        """

        element_id = self._make_id(parent_id, "return", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "statement",
            "statement_type": "return",
            "value": self.name_resolver.get_name(node.value)
            if node.value else None,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

        self._attach_calls(statement, "value_calls", node.value)

        return statement

    def _extract_raise(self, node: ast.Raise, parent_id: str, index: int):
        """
        Extracts a raise statement.

        Calls inside the raised exception expression are stored in
        `exception_calls`.
        """

        element_id = self._make_id(parent_id, "raise", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "statement",
            "statement_type": "raise",
            "exception": self.name_resolver.get_name(node.exc)
            if node.exc else None,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

        self._attach_calls(statement, "exception_calls", node.exc)

        return statement

    def _extract_expr(self, node: ast.Expr, parent_id: str, index: int):
        """
        Extracts expression statements.

        If the expression is a call, it is represented as a call statement.
        Otherwise, it is represented as a generic expression statement.
        """

        if isinstance(node.value, ast.Call):
            call_model = self.call_analyzer.analyze_call(node.value)
            element_id = self._make_id(parent_id, "call", node.lineno, index)

            return {
                "id": element_id,
                "type": "statement",
                "statement_type": "call",
                "call": call_model,
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
            }

        return {
            "id": self._make_id(parent_id, "expr", node.lineno, index),
            "type": "statement",
            "statement_type": "expression",
            "expression": self.name_resolver.get_name(node.value),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

    def _extract_assignment(self, node: ast.Assign, parent_id: str, index: int):
        """
        Extracts a regular assignment statement.

        If the right-hand side is a call, the call is stored in `value_call`.
        Nested calls inside arguments or keyword values are stored in
        `value_calls`.
        """

        element_id = self._make_id(parent_id, "assign", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "statement",
            "statement_type": "assignment",
            "targets": [
                self.name_resolver.get_name(target)
                for target in node.targets
            ],
            "value": self.name_resolver.get_name(node.value),
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

        if isinstance(node.value, ast.Call):
            statement["value_call"] = self.call_analyzer.analyze_call(node.value)

            nested_calls = []

            for arg in node.value.args:
                nested_calls.extend(self._extract_calls_from_node(arg))

            for keyword in node.value.keywords:
                nested_calls.extend(self._extract_calls_from_node(keyword.value))

            if nested_calls:
                statement["value_calls"] = nested_calls
        else:
            value_calls = self._extract_calls_from_node(node.value)

            if value_calls:
                statement["value_calls"] = value_calls

        return statement

    def _extract_annotated_assignment(
        self,
        node: ast.AnnAssign,
        parent_id: str,
        index: int,
    ):
        """
        Extracts an annotated assignment statement.
        """

        element_id = self._make_id(parent_id, "ann_assign", node.lineno, index)

        statement = {
            "id": element_id,
            "type": "statement",
            "statement_type": "annotated_assignment",
            "target": self.name_resolver.get_name(node.target),
            "annotation": self.name_resolver.get_name(node.annotation),
            "value": self.name_resolver.get_name(node.value)
            if node.value else None,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

        if isinstance(node.value, ast.Call):
            statement["value_call"] = self.call_analyzer.analyze_call(node.value)

            nested_calls = []

            for arg in node.value.args:
                nested_calls.extend(self._extract_calls_from_node(arg))

            for keyword in node.value.keywords:
                nested_calls.extend(self._extract_calls_from_node(keyword.value))

            if nested_calls:
                statement["value_calls"] = nested_calls

        else:
            value_calls = self._extract_calls_from_node(node.value)

            if value_calls:
                statement["value_calls"] = value_calls

        return statement

    def _extract_simple_statement(
        self,
        node,
        parent_id: str,
        index: int,
        statement_type: str,
    ):
        """
        Extracts simple statements such as break, continue and pass.
        """

        element_id = self._make_id(parent_id, statement_type, node.lineno, index)

        return {
            "id": element_id,
            "type": "statement",
            "statement_type": statement_type,
            "line_start": node.lineno,
            "line_end": getattr(node, "end_lineno", node.lineno),
        }

    def _extract_unknown_statement(self, node, parent_id: str, index: int):
        """
        Extracts an unsupported AST statement as an unknown body node.

        This preserves traceability instead of silently dropping unsupported
        constructs.
        """

        line = getattr(node, "lineno", 0)
        node_type = type(node).__name__

        element_id = self._make_id(parent_id, node_type, line, index)

        return {
            "id": element_id,
            "type": "statement",
            "statement_type": "unknown",
            "ast_node_type": node_type,
            "line_start": line,
            "line_end": getattr(node, "end_lineno", line),
        }

    def _make_id(self, parent_id: str, node_type: str, line: int, index: int):
        """
        Builds a stable id for a body element.

        The id is based on the parent id, node type, source line and statement
        index. A short SHA1 digest is used to keep ids stable and compact.
        """

        raw_key = f"{parent_id}|{node_type}|{line}|{index}"

        digest = hashlib.sha1(
            raw_key.encode("utf-8")
        ).hexdigest()[:12]

        return f"body:{digest}"

    def _extract_calls_from_node(self, node):
        """
        Extracts all ast.Call nodes contained in a given AST node.
        """

        if node is None:
            return []

        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_model = self.call_analyzer.analyze_call(child)

                if call_model is not None:
                    calls.append(call_model)

        return calls

    def _attach_calls(self, statement: dict, field_name: str, node):
        """
        Extracts calls from a node and attaches them to a statement dictionary.
        """

        calls = self._extract_calls_from_node(node)

        if calls:
            statement[field_name] = calls

        return statement
