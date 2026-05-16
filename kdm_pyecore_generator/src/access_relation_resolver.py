class AccessRelationResolver:

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

    def add_access_relations(self, data: dict):
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._add_callable_accesses(method)

            for func in file_model.get("functions", []):
                self._add_callable_accesses(func)

    def _add_callable_accesses(self, callable_model: dict):
        owner_id = callable_model.get("id")

        if owner_id is None:
            return

        for statement in callable_model.get("body", []):
            self._walk_statement(statement, owner_id)

    def _walk_statement(self, statement: dict, owner_id: str):
        statement_type = statement.get("statement_type")
        node_type = statement.get("type")

        if statement_type == "assignment":
            self._handle_assignment(statement, owner_id)

        if statement_type == "call":
            self._handle_call_statement(statement, owner_id)

        # Some return statements also contain value_calls.
        if statement_type == "return":
            self._handle_return(statement, owner_id)

        # Recurse into nested bodies: if, for, while, try, with, handlers, etc.
        for child in statement.get("body", []):
            self._walk_statement(child, owner_id)

        for child in statement.get("orelse", []):
            self._walk_statement(child, owner_id)

        for child in statement.get("finalbody", []):
            self._walk_statement(child, owner_id)

        for handler in statement.get("handlers", []):
            self._walk_statement(handler, owner_id)

        # Exception handler may contain body too.
        if node_type == "exception_handler":
            for child in statement.get("body", []):
                self._walk_statement(child, owner_id)

    def _handle_assignment(self, statement: dict, owner_id: str):
        action = self._resolve_action_from_statement(statement, owner_id)

        if action is None:
            return

        # Writes to assignment targets.
        for target_name in statement.get("targets", []):
            storable = self._resolve_storable(owner_id, target_name)

            if storable is not None:
                relation = self.factory.create_writes_relation(storable)
                action.actionRelation.append(relation)

        # Reads from assigned value if the value is a variable or attribute.
        value = statement.get("value")
        if value:
            read_target = self._resolve_storable(owner_id, value)

            if read_target is not None:
                relation = self.factory.create_reads_relation(read_target)
                action.actionRelation.append(relation)

        # Reads from receiver of the value call.
        value_call = statement.get("value_call")
        if value_call:
            self._add_receiver_read(action, owner_id, value_call)

    def _handle_call_statement(self, statement: dict, owner_id: str):
        call = statement.get("call")
        if not call:
            return

        action = self._resolve_action_from_call(owner_id, call)

        if action is None:
            return

        self._add_receiver_read(action, owner_id, call)

    def _handle_return(self, statement: dict, owner_id: str):
        # Return may have one or several value_calls.
        for call in statement.get("value_calls", []):
            action = self._resolve_action_from_call(owner_id, call)

            if action is not None:
                self._add_receiver_read(action, owner_id, call)

        # Return value may be a variable.
        value = statement.get("value")
        if value:
            action = self._resolve_action_from_return(statement, owner_id)

            if action is not None:
                storable = self._resolve_storable(owner_id, value)

                if storable is not None:
                    relation = self.factory.create_reads_relation(storable)
                    action.actionRelation.append(relation)

    def _add_receiver_read(self, action, owner_id: str, call: dict):
        receiver = call.get("receiver")

        if not receiver:
            return

        storable = self._resolve_storable(owner_id, receiver)

        if storable is None:
            return

        relation = self.factory.create_reads_relation(storable)
        action.actionRelation.append(relation)

    def _resolve_action_from_statement(self, statement: dict, owner_id: str):
        statement_id = statement.get("id")

        if statement_id and statement_id in self.statement_action_index:
            return self.statement_action_index[statement_id]

        value_call_id = statement.get("value_call_id")
        if value_call_id and value_call_id in self.action_index:
            return self.action_index[value_call_id]

        value_call = statement.get("value_call")
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
        line = statement.get("line_start")
        actions = self.action_index.get((owner_id, line), [])

        if len(actions) == 1:
            return actions[0]

        return None

    def _resolve_storable(self, owner_id: str, name: str):
        if not name:
            return None

        candidates = [
            (owner_id, name),
            name,
        ]

        # For expressions like service.repository, try the full expression first,
        # then progressively shorter versions.
        if "." in name:
            parts = name.split(".")
            candidates.append(parts[-1])

            # Keep self.repository as full name.
            if len(parts) >= 2:
                candidates.append(".".join(parts[:2]))

        for key in candidates:
            if key in self.storable_index:
                return self.storable_index[key]

        return None
