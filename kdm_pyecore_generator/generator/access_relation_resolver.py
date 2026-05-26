import re


class AccessRelationResolver:
    """
    Creates KDM Reads and Writes relations from executable body information.

    This resolver consumes the hierarchical body model produced by
    python_kdm_extractor and enriches ActionElement nodes with access relations.

    It covers:

    - assignment targets as Writes;
    - assignment values as Reads when they reference variables or attributes;
    - call receivers as Reads;
    - positional and keyword call arguments as Reads;
    - return values as Reads;
    - if and while conditions as Reads;
    - for iterables as Reads;
    - for loop targets as Writes.

    The resolver is intentionally conservative: it only creates a Reads/Writes
    relation when a referenced name can be resolved to a known StorableUnit.
    """

    def __init__(
        self,
        factory,
        storable_index,
        action_index,
        statement_action_index=None,
    ):
        self.factory = factory
        self.storable_index = storable_index
        self.action_index = action_index
        self.statement_action_index = statement_action_index or {}

    def _get_value(self, data: dict, *keys, default=None):
        if not isinstance(data, dict):
            return default

        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)

        return default

    def _get_list(self, data: dict, *keys):
        value = self._get_value(data, *keys, default=[])

        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _statement_type(self, statement: dict):
        return self._get_value(statement, "statement_type", "statementType")

    def _control_type(self, statement: dict):
        return self._get_value(statement, "control_type", "controlType")

    def _body_id(self, statement: dict):
        return self._get_value(statement, "id")

    def add_access_relations(self, data: dict):
        """
        Adds Reads and Writes relations for all functions and methods.
        """

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._add_callable_accesses(method)

            for func in file_model.get("functions", []):
                self._add_callable_accesses(func)

        for element in data.get("elements", []):
            for method in element.get("methods", []):
                self._add_callable_accesses(method)

    def _add_callable_accesses(self, callable_model: dict):
        owner_id = callable_model.get("id")

        if owner_id is None:
            return

        for statement in callable_model.get("body", []):
            self._walk_statement(statement, owner_id)

    def _walk_statement(self, statement: dict, owner_id: str):
        """
        Walks body statements recursively.
        """

        statement_type = self._statement_type(statement)
        node_type = statement.get("type")
        control_type = self._control_type(statement)

        if statement_type in {"assignment", "annotated_assignment"}:
            self._handle_assignment(statement, owner_id)

        elif statement_type == "call":
            self._handle_call_statement(statement, owner_id)

        elif statement_type == "return":
            self._handle_return(statement, owner_id)

        elif statement_type == "raise":
            self._handle_raise(statement, owner_id)

        if node_type == "control_structure":
            if control_type in {"if", "while"}:
                self._handle_condition(statement, owner_id)

            elif control_type in {"for", "async_for"}:
                self._handle_for(statement, owner_id)

            elif control_type in {"with", "async_with"}:
                self._handle_with(statement, owner_id)

        for child in self._get_list(statement, "body"):
            self._walk_statement(child, owner_id)

        for child in self._get_list(statement, "orelse", "elseBody"):
            self._walk_statement(child, owner_id)

        for child in self._get_list(statement, "finalbody", "finallyBody"):
            self._walk_statement(child, owner_id)

        for handler in self._get_list(statement, "handlers", "catchClauses"):
            self._walk_statement(handler, owner_id)

        if node_type == "exception_handler":
            for child in self._get_list(statement, "body"):
                self._walk_statement(child, owner_id)

    # ------------------------------------------------------------
    # Statement handlers
    # ------------------------------------------------------------

    def _handle_assignment(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_statement(statement, owner_id)

        if action is None:
            return

        for target_name in self._get_assignment_targets(statement):
            storable = self._resolve_storable(owner_id, target_name)

            if storable is not None:
                self._add_writes_relation(action, storable)

        # Reads from the RHS only when it is a reference-like expression.
        value = statement.get("value")
        value_kind = self._get_value(statement, "value_kind", "valueKind")

        if self._is_reference_like_value(value_kind, value):
            self._add_reads_for_expression(
                action=action,
                owner_id=owner_id,
                expression=value,
            )

        value_call = self._get_value(statement, "value_call", "valueCall")
        if value_call:
            self._add_accesses_from_call(action, owner_id, value_call)

        for call in self._get_list(statement, "value_calls", "valueCalls"):
            call_action = self._resolve_action_from_call(owner_id, call) or action
            self._add_accesses_from_call(call_action, owner_id, call)

    def _handle_call_statement(self, statement: dict, owner_id: str):
        call = self._get_value(statement, "call")
        if not call:
            return

        action = self._resolve_action_from_call(owner_id, call)

        if action is None:
            return

        self._add_accesses_from_call(action, owner_id, call)

    def _handle_return(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_return(statement, owner_id)

        # Return statements without value calls often have their own
        # statement ActionElement. If not, skip safely.
        if action is not None:
            value = statement.get("value")
            if value:
                self._add_reads_for_expression(action, owner_id, value)

        for call in self._get_list(statement, "value_calls", "valueCalls"):
            call_action = self._resolve_action_from_call(owner_id, call)
            if call_action is not None:
                self._add_accesses_from_call(call_action, owner_id, call)

    def _handle_raise(self, statement: dict, owner_id: str):
        for call in self._get_list(statement, "exception_calls", "exceptionCalls"):
            action = self._resolve_action_from_call(owner_id, call)
            if action is not None:
                self._add_accesses_from_call(action, owner_id, call)

    def _handle_condition(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_statement(statement, owner_id)

        if action is None:
            return

        condition = self._get_value(statement, "condition")
        if condition:
            self._add_reads_for_expression(action, owner_id, condition)

        for call in self._get_list(statement, "condition_calls", "conditionCalls"):
            call_action = self._resolve_action_from_call(owner_id, call)
            if call_action is not None:
                self._add_accesses_from_call(call_action, owner_id, call)

    def _handle_for(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_statement(statement, owner_id)

        if action is None:
            return

        target = self._get_value(statement, "target")
        if target:
            storable = self._resolve_storable(owner_id, target)
            if storable is not None:
                self._add_writes_relation(action, storable)

        iterable = self._get_value(statement, "iter", "iterable")
        if iterable:
            self._add_reads_for_expression(action, owner_id, iterable)

        for call in self._get_list(statement, "iter_calls", "iterCalls"):
            call_action = self._resolve_action_from_call(owner_id, call)
            if call_action is not None:
                self._add_accesses_from_call(call_action, owner_id, call)

    def _handle_with(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_statement(statement, owner_id)

        if action is None:
            return

        for item in self._get_list(statement, "items"):
            context_expr = item.get("context_expr")
            optional_vars = item.get("optional_vars")

            if context_expr:
                self._add_reads_for_expression(action, owner_id, context_expr)

            if optional_vars:
                storable = self._resolve_storable(owner_id, optional_vars)
                if storable is not None:
                    self._add_writes_relation(action, storable)

            for call in item.get("context_calls", []):
                call_action = self._resolve_action_from_call(owner_id, call)
                if call_action is not None:
                    self._add_accesses_from_call(call_action, owner_id, call)

    # ------------------------------------------------------------
    # Call accesses
    # ------------------------------------------------------------

    def _add_accesses_from_call(self, action, owner_id: str, call: dict):
        """
        Adds Reads from call receiver and call arguments.
        """

        self._add_receiver_read(action, owner_id, call)
        self._add_argument_reads(action, owner_id, call)

    def _add_receiver_read(self, action, owner_id: str, call: dict):
        receiver = self._get_value(call, "receiver", "scope")

        if not receiver:
            return

        storable = self._resolve_storable(owner_id, receiver)

        if storable is not None:
            self._add_reads_relation(action, storable)

    def _add_argument_reads(self, action, owner_id: str, call: dict):
        for argument in self._get_list(call, "arguments"):
            self._add_argument_read(action, owner_id, argument)

        for keyword_argument in self._get_list(call, "keyword_arguments", "keywordArguments"):
            self._add_argument_read(action, owner_id, keyword_argument)

    def _add_argument_read(self, action, owner_id: str, argument: dict):
        value = argument.get("value")
        argument_kind = argument.get("argument_kind")

        if not self._is_reference_like_value(argument_kind, value):
            return

        self._add_reads_for_expression(action, owner_id, value)

    # ------------------------------------------------------------
    # Reads/Writes creation
    # ------------------------------------------------------------

    def _is_valid_access_target(self, target) -> bool:
        """
        KDM action::Reads and action::Writes must point to code::StorableUnit.

        The global index may also contain ParameterUnit objects because
        parameters are typable and addressable in the JSON model. However,
        ParameterUnit is not a valid target for Reads/Writes in this KDM
        validator. Therefore, parameter accesses are skipped instead of
        producing invalid KDM relations.
        """

        if target is None:
            return False

        try:
            return target.eClass.name == "StorableUnit"
        except AttributeError:
            return False

    def _add_reads_for_expression(self, action, owner_id: str, expression):
        """
        Adds Reads for all resolvable references contained in an expression.
        """

        for reference_name in self._extract_reference_candidates(expression):
            storable = self._resolve_storable(owner_id, reference_name)

            if storable is not None:
                self._add_reads_relation(action, storable)

    def _add_reads_relation(self, action, storable):
        if action is None or not self._is_valid_access_target(storable):
            return

        if self._has_relation(action, "Reads", storable):
            return

        relation = self.factory.create_reads_relation(storable)
        action.actionRelation.append(relation)

    def _add_writes_relation(self, action, storable):
        if action is None or not self._is_valid_access_target(storable):
            return

        if self._has_relation(action, "Writes", storable):
            return

        relation = self.factory.create_writes_relation(storable)
        action.actionRelation.append(relation)

    def _has_relation(self, action, relation_type: str, target) -> bool:
        if not hasattr(action, "actionRelation"):
            return False

        for relation in action.actionRelation:
            if getattr(relation.eClass, "name", None) != relation_type:
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

    # ------------------------------------------------------------
    # Action resolution
    # ------------------------------------------------------------

    def _resolve_action_from_statement(self, statement: dict, owner_id: str):
        statement_id = self._body_id(statement)

        if statement_id and statement_id in self.statement_action_index:
            return self.statement_action_index[statement_id]

        value_call_id = statement.get("value_call_id")
        if value_call_id and value_call_id in self.action_index:
            return self.action_index[value_call_id]

        value_call = self._get_value(statement, "value_call", "valueCall")
        if value_call:
            return self._resolve_action_from_call(owner_id, value_call)

        line = statement.get("line_start")
        actions = self.action_index.get((owner_id, line), [])

        if len(actions) == 1:
            return actions[0]

        return None

    def _resolve_action_from_call(self, owner_id: str, call: dict):
        call_id = call.get("id")

        if call_id and call_id in self.action_index:
            return self.action_index[call_id]

        line = call.get("line")

        candidate_names = [
            call.get("name"),
            call.get("function"),
            call.get("method"),
            call.get("class_name"),
        ]

        for name in candidate_names:
            if name:
                action = self.action_index.get((owner_id, line, str(name)))
                if action is not None:
                    return action

        actions = self.action_index.get((owner_id, line), [])

        if len(actions) == 1:
            return actions[0]

        return None

    def _resolve_action_from_return(self, statement: dict, owner_id: str):
        statement_id = self._body_id(statement)

        if statement_id and statement_id in self.statement_action_index:
            return self.statement_action_index[statement_id]

        line = statement.get("line_start")
        actions = self.action_index.get((owner_id, line), [])

        if len(actions) == 1:
            return actions[0]

        return None

    # ------------------------------------------------------------
    # Storable resolution
    # ------------------------------------------------------------

    def _resolve_storable(self, owner_id: str, name: str):
        if not name:
            return None

        name = str(name).strip()

        candidates = [
            (owner_id, name),
            name,
        ]

        if "." in name:
            parts = name.split(".")

            # Full expression first, then useful fallbacks.
            candidates.append(parts[-1])

            if len(parts) >= 2:
                candidates.append(".".join(parts[:2]))

            # For data["field"] expressions the resolver may have normalized to
            # data. Keep the first part as an additional candidate.
            candidates.append(parts[0])

        for key in candidates:
            if key in self.storable_index:
                return self.storable_index[key]

        return None

    # ------------------------------------------------------------
    # Expression helpers
    # ------------------------------------------------------------

    def _get_assignment_targets(self, statement: dict):
        if "targets" in statement:
            return [
                target
                for target in statement.get("targets", [])
                if target is not None
            ]

        target = self._get_value(statement, "target")
        if target is not None:
            return [target]

        return []

    def _is_reference_like_value(self, value_kind, value) -> bool:
        if value is None:
            return False

        if value_kind in {
            "variable_reference",
            "attribute_reference",
            "call_result",
            "expression",
            "comparison_expression",
            "boolean_expression",
            "binary_expression",
            "unary_expression",
        }:
            return True

        # Backward compatibility for older JSON without value_kind.
        if value_kind is None:
            text = str(value).strip()
            return not self._looks_like_literal(text)

        return False

    def _extract_reference_candidates(self, expression):
        """
        Extracts possible variable/attribute references from a compact textual
        expression.

        The extractor stores expressions as strings such as:

            user
            self.repository
            attempts < self.max_attempts
            role not in self.roles
            user_data
            user_data.get

        This method is heuristic but conservative because every candidate still
        needs to resolve through storable_index before a Reads relation is made.
        """

        if expression is None:
            return []

        text = str(expression).strip()

        if not text or self._looks_like_literal(text):
            return []

        # Keep the complete expression first. This allows exact matches such as
        # self.repository or active_users.
        candidates = [text]

        token_pattern = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"

        for token in re.findall(token_pattern, text):
            if token in self._reserved_words():
                continue

            if token not in candidates:
                candidates.append(token)

            if "." in token:
                parts = token.split(".")

                # For self.repository.save, try self.repository and repository.
                if len(parts) >= 2:
                    prefix = ".".join(parts[:2])
                    if prefix not in candidates:
                        candidates.append(prefix)

                if parts[-1] not in candidates:
                    candidates.append(parts[-1])

                if parts[0] not in candidates:
                    candidates.append(parts[0])

        return candidates

    def _looks_like_literal(self, text: str) -> bool:
        if text in {"None", "True", "False"}:
            return True

        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            return True

        if (
            (text.startswith("'") and text.endswith("'"))
            or (text.startswith('"') and text.endswith('"'))
        ):
            return True

        if text in {"[]", "{}", "()", "set()"}:
            return True

        return False

    def _reserved_words(self):
        return {
            "and",
            "or",
            "not",
            "in",
            "is",
            "None",
            "True",
            "False",
            "if",
            "else",
            "for",
            "while",
            "return",
            "raise",
        }
