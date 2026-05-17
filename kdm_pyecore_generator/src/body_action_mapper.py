class BodyActionMapper:
    """
    Maps executable body nodes from the intermediate JSON model to KDM action
    elements.

    This mapper is responsible for building the executable structure inside
    each KDM MethodUnit or CallableUnit. For every callable with a non-empty
    body, it creates a KDM BlockUnit named ``body`` and attaches executable
    actions to that block.

    The expected structure is:

        MethodUnit / CallableUnit
          └── BlockUnit name="body" kind="body"
                ├── ActionElement
                ├── TryUnit
                ├── CatchUnit
                ├── FinallyUnit
                └── nested ActionElement nodes

    The mapper also reuses call ActionElement nodes previously created by
    ReferenceResolver, preserving call relations while nesting them in the
    correct executable context.

    Traceability is preserved through:
    - body_id attributes on generated body actions;
    - callable_body_id attributes on BlockUnit elements;
    - SourceRef / SourceRegion elements.
    """

    def __init__(
        self,
        factory,
        id_index,
        action_index=None,
        inventory_builder=None,
        language="unknown",
    ):
        """
        Initializes the body action mapper.

        Parameters
        ----------
        factory:
            KDMFactory used to create KDM elements and relations.

        id_index:
            Dictionary mapping intermediate JSON ids to generated KDM elements.

        action_index:
            Dictionary of ActionElement nodes already created by
            ReferenceResolver, mainly for calls and constructor calls.

        inventory_builder:
            InventoryBuilder used to resolve SourceFile references for
            SourceRegion traceability.

        language:
            Source language name used in SourceRef / SourceRegion metadata.
        """

        self.factory = factory
        self.id_index = id_index
        self.action_index = action_index or {}
        self.inventory_builder = inventory_builder
        self.language = language

        # Index for statement/control ActionElements.
        # It also stores TryUnit and CatchUnit instances created from body nodes.
        self.statement_action_index = {}

        # Index for synthetic FinallyUnit nodes.
        # Key: try body id
        # Value: FinallyUnit
        self.finally_action_index = {}

        # Index for callable body blocks.
        # Key: callable id
        # Value: BlockUnit
        self.callable_body_block_index = {}

    def map_body_actions(self, data: dict):
        """
        Maps all method and function bodies contained in the intermediate JSON
        model to KDM executable structures.
        """

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._map_callable_body(method, file_model)

            for func in file_model.get("functions", []):
                self._map_callable_body(func, file_model)

    def _map_callable_body(self, callable_model: dict, file_model: dict):
        """
        Maps one callable body to a KDM BlockUnit.

        The callable itself remains a MethodUnit or CallableUnit. Its executable
        statements are placed inside a child BlockUnit named ``body``.
        """

        callable_kdm = self.id_index.get(callable_model.get("id"))

        if callable_kdm is None:
            return

        body = callable_model.get("body", [])

        if not body:
            return

        body_block = self._get_or_create_callable_body_block(
            callable_model=callable_model,
            file_model=file_model,
            callable_kdm=callable_kdm,
        )

        if body_block is None:
            return

        for statement in body:
            self._map_body_item(
                item=statement,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=body_block,
            )

    # ------------------------------------------------------------
    # Callable body BlockUnit
    # ------------------------------------------------------------

    def _get_or_create_callable_body_block(
        self,
        callable_model: dict,
        file_model: dict,
        callable_kdm,
    ):
        """
        Creates or reuses the BlockUnit that represents a callable body.
        """

        callable_id = callable_model.get("id")

        if callable_id in self.callable_body_block_index:
            return self.callable_body_block_index[callable_id]

        if not self.factory.has_feature(callable_kdm, "codeElement"):
            return None

        for child in callable_kdm.codeElement:
            if getattr(child.eClass, "name", None) != "BlockUnit":
                continue

            if self._has_attribute(
                child,
                "callable_body_id",
                callable_id,
            ):
                self.callable_body_block_index[callable_id] = child
                return child

        body_block = self.factory.create_block_unit(
            name="body",
            kind="body",
        )

        self._add_attribute_once(
            body_block,
            "role",
            "callable_body",
        )

        self._add_attribute_once(
            body_block,
            "callable_body_id",
            callable_id,
        )

        self._add_callable_body_source_region(
            body_block=body_block,
            callable_model=callable_model,
            file_model=file_model,
        )

        callable_kdm.codeElement.append(body_block)
        self.callable_body_block_index[callable_id] = body_block

        return body_block

    def _add_callable_body_source_region(
        self,
        body_block,
        callable_model: dict,
        file_model: dict,
    ):
        """
        Adds source traceability to a callable body BlockUnit.

        The source region spans from the first to the last statement in the
        callable body whenever line information is available.
        """

        body = callable_model.get("body", [])

        if not body:
            return

        start_lines = [
            item.get("line_start")
            for item in body
            if item.get("line_start") is not None
        ]

        end_lines = [
            item.get("line_end")
            for item in body
            if item.get("line_end") is not None
        ]

        if not start_lines and not end_lines:
            return

        start_line = min(start_lines) if start_lines else None
        end_line = max(end_lines) if end_lines else start_line

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            body_block,
            path=file_model.get("path"),
            language=self.language,
            start_line=start_line,
            end_line=end_line,
            file_item=source_file,
        )

    def _map_body_item(
        self,
        item: dict,
        callable_model: dict,
        file_model: dict,
        parent_kdm,
    ):
        """
        Maps one JSON body item to a KDM action element and recursively maps
        its nested body items.
        """

        action = self._get_or_create_action_for_body_item(
            item=item,
            callable_model=callable_model,
        )

        if action is not None:
            self._add_or_update_action(
                action=action,
                item=item,
                file_model=file_model,
                parent_kdm=parent_kdm,
            )

            next_parent = action
        else:
            next_parent = parent_kdm

        # Expression-level calls are moved under the element that owns them.
        self._map_expression_calls(item, next_parent)

        # Nested expression calls:
        # calls inside arguments or receivers of another call.
        self._attach_same_line_nested_calls(
            item=item,
            callable_model=callable_model,
            owner_action=next_parent,
        )

        self._attach_same_line_orphan_calls(
            item=item,
            callable_model=callable_model,
            owner_action=next_parent,
        )

        for child in item.get("body", []):
            self._map_body_item(
                item=child,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for child in item.get("orelse", []):
            self._map_body_item(
                item=child,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for handler in item.get("handlers", []):
            self._map_body_item(
                item=handler,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        self._map_finalbody(
            item=item,
            callable_model=callable_model,
            file_model=file_model,
            parent_kdm=next_parent,
        )

    # ------------------------------------------------------------
    # Final body mapping
    # ------------------------------------------------------------

    def _map_finalbody(
        self,
        item: dict,
        callable_model: dict,
        file_model: dict,
        parent_kdm,
    ):
        """
        Maps a JSON finalbody list to a KDM FinallyUnit.

        For try statements, the finalbody is represented by a synthetic
        FinallyUnit. The ExceptionRelationResolver later connects the TryUnit
        to this FinallyUnit using ExitFlow.
        """

        finalbody = item.get("finalbody", [])

        if not finalbody:
            return

        # Only try nodes should own a finalbody in the current JSON model.
        if not (
            item.get("type") == "control_structure"
            and item.get("control_type") == "try"
        ):
            for child in finalbody:
                self._map_body_item(
                    item=child,
                    callable_model=callable_model,
                    file_model=file_model,
                    parent_kdm=parent_kdm,
                )
            return

        finally_action = self.factory.create_finally_unit("finally")

        synthetic_finally_item = {
            "id": f"{item.get('id')}:finally",
            "type": "finally_block",
            "statement_type": None,
            "control_type": "finally",
            "line_start": item.get("line_start"),
            "line_end": item.get("line_end"),
        }

        self._add_or_update_action(
            action=finally_action,
            item=synthetic_finally_item,
            file_model=file_model,
            parent_kdm=parent_kdm,
        )

        if item.get("id"):
            self.finally_action_index[item.get("id")] = finally_action

        for child in finalbody:
            self._map_body_item(
                item=child,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=finally_action,
            )

    # ------------------------------------------------------------
    # Expression call mapping
    # ------------------------------------------------------------

    def _map_expression_calls(self, item: dict, owner_action):
        """
        Moves expression-level calls to the action element that owns them.

        Examples:
        - condition_calls -> if / while
        - value_calls -> return
        - exception_calls -> raise
        - context_calls -> with
        """

        if owner_action is None:
            return

        for call in item.get("condition_calls", []):
            self._attach_existing_call_action(
                call=call,
                parent_kdm=owner_action,
                expression_role="condition_call",
            )

        for call in item.get("value_calls", []):
            self._attach_existing_call_action(
                call=call,
                parent_kdm=owner_action,
                expression_role="value_call",
            )

        for call in item.get("exception_calls", []):
            self._attach_existing_call_action(
                call=call,
                parent_kdm=owner_action,
                expression_role="exception_call",
            )

        for with_item in item.get("items", []):
            for call in with_item.get("context_calls", []):
                self._attach_existing_call_action(
                    call=call,
                    parent_kdm=owner_action,
                    expression_role="context_call",
                )

    def _attach_existing_call_action(
        self,
        call: dict,
        parent_kdm,
        expression_role: str,
    ):
        call_id = call.get("id")

        if not call_id:
            return

        action = self.action_index.get(call_id)

        if action is None:
            return

        self._add_attribute_once(
            action,
            "expression_role",
            expression_role,
        )

        self._attach_action_to_parent(action, parent_kdm)

    def _attach_action_to_parent(self, action, parent_kdm):
        if action is None or parent_kdm is None:
            return

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return

        if action not in parent_kdm.codeElement:
            parent_kdm.codeElement.append(action)

    # ------------------------------------------------------------
    # Action creation / reuse
    # ------------------------------------------------------------

    def _get_or_create_action_for_body_item(
        self,
        item: dict,
        callable_model: dict,
    ):
        existing_action = self._find_existing_action_for_body_item(
            item=item,
            callable_model=callable_model,
        )

        if existing_action is not None:
            return existing_action

        return self._create_action_for_body_item(item)

    def _find_existing_action_for_body_item(
        self,
        item: dict,
        callable_model: dict,
    ):
        """
        Reuses ActionElement nodes already created by ReferenceResolver.

        This is essential for preserving nesting without duplicating call actions.
        """

        statement_type = item.get("statement_type")

        if statement_type == "call":
            call_id = item.get("call_id")

            if call_id and call_id in self.action_index:
                return self.action_index[call_id]

            call = item.get("call") or {}
            nested_call_id = call.get("id")

            if nested_call_id and nested_call_id in self.action_index:
                return self.action_index[nested_call_id]

            return self._find_action_by_owner_line_and_name(
                callable_model=callable_model,
                line=item.get("line_start"),
                name=call.get("name"),
            )

        if statement_type == "assignment":
            value_call_id = item.get("value_call_id")

            if value_call_id and value_call_id in self.action_index:
                return self.action_index[value_call_id]

            value_call = item.get("value_call") or {}
            nested_value_call_id = value_call.get("id")

            if nested_value_call_id and nested_value_call_id in self.action_index:
                return self.action_index[nested_value_call_id]

            return self._find_action_by_owner_line_and_name(
                callable_model=callable_model,
                line=item.get("line_start"),
                name=item.get("value"),
            )

        if statement_type in {"return", "raise"}:
            for call in item.get("value_calls", []):
                call_id = call.get("id")
                if call_id and call_id in self.action_index:
                    return None

            for call in item.get("exception_calls", []):
                call_id = call.get("id")
                if call_id and call_id in self.action_index:
                    return None

        return None

    def _find_action_by_owner_line_and_name(
        self,
        callable_model: dict,
        line,
        name,
    ):
        owner_id = callable_model.get("id")

        if owner_id is None or line is None:
            return None

        if name:
            action = self.action_index.get((owner_id, line, str(name)))
            if action is not None:
                return action

        actions = self.action_index.get((owner_id, line), [])

        if len(actions) == 1:
            return actions[0]

        return None

    def _create_action_for_body_item(self, item: dict):
        """
        Creates a new KDM action element for a JSON body item when no existing
        call action can be reused.
        """

        statement_type = item.get("statement_type")
        node_type = item.get("type")
        control_type = item.get("control_type")

        if node_type == "control_structure" and control_type == "try":
            return self.factory.create_try_unit("try")

        if node_type == "exception_handler":
            return self.factory.create_catch_unit("except")

        if node_type == "finally_block":
            return self.factory.create_finally_unit("finally")

        if node_type == "control_structure":
            name = control_type or "control_structure"
            kind = control_type or "control_structure"
            return self.factory.create_action_element(name=name, kind=kind)

        if statement_type:
            name = statement_type
            kind = statement_type
            return self.factory.create_action_element(name=name, kind=kind)

        return None

    def _add_or_update_action(
        self,
        action,
        item: dict,
        file_model: dict,
        parent_kdm,
    ):
        self._add_source_region(action, item, file_model)
        self._add_statement_metadata(action, item)

        self._attach_action_to_parent(action, parent_kdm)

        item_id = item.get("id")

        if item_id:
            self.statement_action_index[item_id] = action

    # ------------------------------------------------------------
    # Source and metadata
    # ------------------------------------------------------------

    def _add_source_region(self, action, statement: dict, file_model: dict):
        if self.factory.has_feature(action, "source") and len(action.source) > 0:
            return

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=statement.get("line_start"),
            end_line=statement.get("line_end"),
            file_item=source_file,
        )

    def _add_statement_metadata(self, action, item: dict):
        """
        Adds only traceability metadata from the JSON body node.

        Semantic information such as return values, exception flows,
        reads/writes, calls, and types is represented using KDM elements
        and relations, not temporary attributes.
        """

        self._add_attribute_once(
            action,
            "body_id",
            item.get("id"),
        )

    def _get_source_file(self, file_model: dict):
        if self.inventory_builder is None:
            return None

        return self.inventory_builder.get_source_file_by_path(
            file_model.get("path")
        )

    # ------------------------------------------------------------
    # Same-line nested call mapping
    # ------------------------------------------------------------

    def _attach_same_line_orphan_calls(
        self,
        item: dict,
        callable_model: dict,
        owner_action,
    ):
        if owner_action is None:
            return

        statement_type = item.get("statement_type")

        if statement_type not in {"call", "return", "raise", "assignment"}:
            return

        owner_id = callable_model.get("id")
        owner_line = item.get("line_start")

        if owner_id is None or owner_line is None:
            return

        if not self.factory.has_feature(owner_action, "codeElement"):
            return

        same_line_actions = self.action_index.get((owner_id, owner_line), [])

        for action in same_line_actions:
            if action is owner_action:
                continue

            if action in owner_action.codeElement:
                continue

            self._add_attribute_once(
                action,
                "expression_role",
                "nested_expression_call",
            )

            self._attach_action_to_parent(action, owner_action)

    def _attach_same_line_nested_calls(
        self,
        item: dict,
        callable_model: dict,
        owner_action,
    ):
        """
        Moves same-line call actions under the action that semantically owns them.

        Examples:
        - self.logger.warning(str(error))  -> str under self.logger.warning
        - json.dump(user.to_dict(), file)  -> user.to_dict under json.dump
        - super().to_dict()                -> super under super.to_dict
        """

        if owner_action is None:
            return

        statement_type = item.get("statement_type")

        if statement_type not in {"call", "assignment", "return", "raise"}:
            return

        owner_id = callable_model.get("id")
        owner_line = item.get("line_start")

        if owner_id is None or owner_line is None:
            return

        if not self.factory.has_feature(owner_action, "codeElement"):
            return

        same_line_actions = self.action_index.get((owner_id, owner_line), [])

        if not same_line_actions:
            return

        owner_name = getattr(owner_action, "name", None)

        if not owner_name:
            return

        for nested_action in same_line_actions:
            if nested_action is owner_action:
                continue

            if nested_action in owner_action.codeElement:
                continue

            nested_name = getattr(nested_action, "name", None)

            if not nested_name:
                continue

            if nested_name == owner_name:
                continue

            if not self._looks_like_nested_call(
                owner_name=owner_name,
                nested_name=nested_name,
                item=item,
            ):
                continue

            self._add_attribute_once(
                nested_action,
                "expression_role",
                "nested_expression_call",
            )

            self._attach_action_to_parent(nested_action, owner_action)

    def _looks_like_nested_call(
        self,
        owner_name: str,
        nested_name: str,
        item: dict,
    ) -> bool:
        statement_type = item.get("statement_type")

        if statement_type in {"return", "raise"}:
            return True

        if statement_type == "assignment":
            value = item.get("value")

            if value and str(value) == owner_name:
                return True

        if statement_type == "call":
            call = item.get("call") or {}
            call_name = call.get("name")

            if call_name and str(call_name) == owner_name:
                return True

        if owner_name.startswith(f"{nested_name}."):
            return True

        return True

    # ------------------------------------------------------------
    # Attribute helpers
    # ------------------------------------------------------------

    def _has_attribute(self, element, tag: str, value: str) -> bool:
        if not self.factory.has_feature(element, "attribute"):
            return False

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) != tag:
                continue

            if getattr(attribute, "value", None) == str(value):
                return True

        return False

    def _add_attribute_once(self, element, tag: str, value):
        if value is None:
            return

        if self._has_attribute(element, tag, value):
            return

        self.factory.add_attribute(element, tag, value)
