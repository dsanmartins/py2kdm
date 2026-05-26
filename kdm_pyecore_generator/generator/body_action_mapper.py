class BodyActionMapper:
    def __init__(
        self,
        factory,
        id_index,
        action_index=None,
        inventory_builder=None,
        language="unknown",
        external_builder=None,
    ):
        self.factory = factory
        self.id_index = id_index
        self.action_index = action_index or {}
        self.inventory_builder = inventory_builder
        self.language = language
        self.external_builder = external_builder

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
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._map_callable_body(method, file_model)

            for func in file_model.get("functions", []):
                self._map_callable_body(func, file_model)

    def _map_callable_body(self, callable_model: dict, file_model: dict):
        """
        Maps the executable body of a method or function.

        Executable actions must not be contained directly in MethodUnit or
        CallableUnit. They must be contained inside an action::BlockUnit that
        represents the callable body.
        """

        callable_kdm = self.id_index.get(callable_model.get("id"))

        if callable_kdm is None:
            return

        body_block = self._get_or_create_callable_body_block(
            callable_model=callable_model,
            file_model=file_model,
            callable_kdm=callable_kdm,
        )

        if body_block is None:
            return

        for statement in callable_model.get("body", []):
            self._map_body_item(
                item=statement,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=body_block,
            )

        self._move_direct_executable_actions_to_body_block(
            callable_kdm=callable_kdm,
            body_block=body_block,
        )

        # Final safety pass: some actions may have been created before body
        # mapping or attached by different resolvers. Collapse duplicate
        # ActionElement children inside the same BlockUnit so the generated
        # KDM remains valid even when the extractor lacks precise line data.
        self._deduplicate_child_actions(body_block)

        # Static constructor fallback:
        # Some Python calls such as Port(...), Subject(...), FastAPI(...),
        # Config(...), etc. may be recognized as constructor-like calls but
        # remain unresolved by the static call resolver. In those cases, create
        # a conservative Creates relation to either an internal ClassUnit or an
        # external ClassUnit.
        self._resolve_unresolved_constructor_creates(body_block)

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

            if self._has_attribute(child, "callable_body_id", callable_id):
                self.callable_body_block_index[callable_id] = child
                return child

            if getattr(child, "name", None) == "body" or getattr(child, "kind", None) == "body":
                self.callable_body_block_index[callable_id] = child
                return child

        body_block = self.factory.create_block_unit(
            name="body",
            kind="body",
        )

        self._add_attribute_once(body_block, "role", "callable_body")
        self._add_attribute_once(body_block, "callable_body_id", callable_id)

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

    def _move_direct_executable_actions_to_body_block(
        self,
        callable_kdm,
        body_block,
    ):
        """
        Moves direct executable actions from MethodUnit/CallableUnit to the
        callable body BlockUnit.

        Some ActionElement objects are created before body mapping, especially
        by call/reference resolution. If they remain directly contained in a
        MethodUnit or CallableUnit, the KDM validator reports errors.
        """

        if callable_kdm is None or body_block is None:
            return

        if not self.factory.has_feature(callable_kdm, "codeElement"):
            return

        if not self.factory.has_feature(body_block, "codeElement"):
            return

        executable_types = {
            "ActionElement",
            "TryUnit",
            "CatchUnit",
            "FinallyUnit",
        }

        movable = []

        for element in list(callable_kdm.codeElement):
            if element is body_block:
                continue

            element_type = getattr(element.eClass, "name", None)

            if element_type in executable_types:
                movable.append(element)

        for element in movable:
            self._attach_action_to_parent(element, body_block)

    def _map_body_item(
        self,
        item: dict,
        callable_model: dict,
        file_model: dict,
        parent_kdm,
    ):
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

        # Option B:
        # condition_calls, value_calls, exception_calls and context_calls
        # are moved under the ActionElement/TryUnit/CatchUnit that owns them.
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

        self.factory.add_attribute(
            action,
            "expression_role",
            expression_role,
        )

        self._attach_action_to_parent(action, parent_kdm)

    def _attach_action_to_parent(self, action, parent_kdm):
        """
        Attaches an executable KDM element to a parent container.

        This method protects PyEcore containment from cycles, avoids duplicate
        containment operations and collapses duplicate ActionElement children
        that have the same effective validation signature. This is important
        for Python models where the static extractor may report repeated calls
        without precise source positions.
        """

        if action is None or parent_kdm is None:
            return

        if action is parent_kdm:
            return

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return

        if self._would_create_containment_cycle(
            child=action,
            parent=parent_kdm,
        ):
            return

        if action in parent_kdm.codeElement:
            return

        duplicate = self._find_equivalent_child_action(parent_kdm, action)

        if duplicate is not None:
            self._merge_action_relations(
                source_action=action,
                target_action=duplicate,
            )
            self._detach_from_current_container(action)
            return

        parent_kdm.codeElement.append(action)

    def _deduplicate_child_actions(self, parent_kdm):
        """
        Removes duplicate ActionElement children from a KDM container.

        The validator considers two child actions duplicated when they have the
        same effective signature: metaclass, name, kind, startLine and endLine.
        In large Python projects, repeated calls sometimes have no precise
        source region and therefore share the same signature. This pass keeps
        the first action and merges relations/attributes from later duplicates.
        """

        if parent_kdm is None:
            return

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return

        # First normalize nested containers, if any.
        for child in list(parent_kdm.codeElement):
            if self.factory.has_feature(child, "codeElement"):
                self._deduplicate_child_actions(child)

        seen = {}

        for child in list(parent_kdm.codeElement):
            if getattr(child.eClass, "name", None) != "ActionElement":
                continue

            signature = self._action_validation_signature(child)
            existing = seen.get(signature)

            if existing is None:
                seen[signature] = child
                continue

            self._merge_action_relations(
                source_action=child,
                target_action=existing,
            )
            self._merge_attributes(
                source_element=child,
                target_element=existing,
            )

            try:
                parent_kdm.codeElement.remove(child)
            except Exception:
                pass

    def _merge_attributes(self, source_element, target_element):
        if source_element is None or target_element is None:
            return

        if not self.factory.has_feature(source_element, "attribute"):
            return

        if not self.factory.has_feature(target_element, "attribute"):
            return

        existing = {
            (getattr(attribute, "tag", None), getattr(attribute, "value", None))
            for attribute in target_element.attribute
        }

        for attribute in list(source_element.attribute):
            key = (getattr(attribute, "tag", None), getattr(attribute, "value", None))

            if key in existing:
                continue

            target_element.attribute.append(attribute)
            existing.add(key)

    def _find_equivalent_child_action(self, parent_kdm, action):
        if action is None or parent_kdm is None:
            return None

        if getattr(action.eClass, "name", None) != "ActionElement":
            return None

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return None

        action_signature = self._action_validation_signature(action)

        for child in parent_kdm.codeElement:
            if child is action:
                continue

            if getattr(child.eClass, "name", None) != "ActionElement":
                continue

            if self._action_validation_signature(child) == action_signature:
                return child

        return None

    def _action_validation_signature(self, action):
        return (
            getattr(action.eClass, "name", None),
            getattr(action, "name", None),
            getattr(action, "kind", None),
            self._first_source_line(action, "startLine"),
            self._first_source_line(action, "endLine"),
        )

    def _first_source_line(self, element, feature_name: str):
        if element is None or not self.factory.has_feature(element, "source"):
            return None

        for source_ref in element.source:
            for region in getattr(source_ref, "region", []):
                if self.factory.has_feature(region, feature_name):
                    value = getattr(region, feature_name, None)
                    if value is not None:
                        return value

        return None

    def _merge_action_relations(self, source_action, target_action):
        if source_action is None or target_action is None:
            return

        if not self.factory.has_feature(source_action, "actionRelation"):
            return

        if not self.factory.has_feature(target_action, "actionRelation"):
            return

        for relation in list(source_action.actionRelation):
            if self._has_equivalent_action_relation(target_action, relation):
                continue
            target_action.actionRelation.append(relation)

    def _has_equivalent_action_relation(self, action, relation) -> bool:
        if action is None or relation is None:
            return False

        if not self.factory.has_feature(action, "actionRelation"):
            return False

        relation_type = getattr(relation.eClass, "name", None)
        relation_target = getattr(relation, "to", None)

        for existing in action.actionRelation:
            if getattr(existing.eClass, "name", None) != relation_type:
                continue

            if getattr(existing, "to", None) is relation_target:
                return True

        return False

    def _detach_from_current_container(self, element):
        if element is None:
            return

        try:
            container = element.eContainer()
        except Exception:
            return

        if container is None:
            return

        if not self.factory.has_feature(container, "codeElement"):
            return

        try:
            if element in container.codeElement:
                container.codeElement.remove(element)
        except Exception:
            return

    def _would_create_containment_cycle(self, child, parent) -> bool:
        """
        Returns True if attaching child below parent would create a containment
        cycle. A cycle occurs when parent is already contained below child.
        """

        current = parent

        while current is not None:
            if current is child:
                return True

            try:
                current = current.eContainer()
            except Exception:
                return False

        return False

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

        metadata = {
            "body_id": item.get("id"),
        }

        # Keep body_type only when it is not already obvious from the KDM metaclass.
        item_type = item.get("type")

        if item_type not in {
            "control_structure",
            "exception_handler",
            "finally_block",
            "statement",
        }:
            metadata["body_type"] = item_type

        self.factory.add_attributes_from_dict(action, metadata)

    def _get_source_file(self, file_model: dict):
        if self.inventory_builder is None:
            return None

        return self.inventory_builder.get_source_file_by_path(
            file_model.get("path")
        )

    def _has_attribute(self, element, tag: str, value) -> bool:
        if value is None:
            return False

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

            self.factory.add_attribute(
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

            self.factory.add_attribute(
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
    # Static constructor Creates fallback
    # ------------------------------------------------------------

    def _resolve_unresolved_constructor_creates(self, parent_kdm):
        """
        Resolves constructor-like ActionElement nodes that do not have a
        Creates relation.

        This is a static fallback. If the constructor target cannot be resolved
        internally, an external ClassUnit is created through ExternalModelBuilder
        and linked through action::Creates.
        """

        if parent_kdm is None:
            return

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return

        for child in list(parent_kdm.codeElement):
            if self.factory.has_feature(child, "codeElement"):
                self._resolve_unresolved_constructor_creates(child)

            if getattr(child.eClass, "name", None) != "ActionElement":
                continue

            if not self._looks_like_constructor_action(child):
                continue

            if self._has_creates_relation(child):
                continue

            constructor_name = getattr(child, "name", None)
            target = self._resolve_constructor_target_static(constructor_name)

            if target is None:
                self._add_attribute_once(child, "resolution_status", "unresolved")
                self._add_attribute_once(child, "unresolved_constructor", constructor_name)
                continue

            creates_relation = self.factory.create_creates_relation(target)

            if creates_relation is not None and self.factory.has_feature(child, "actionRelation"):
                child.actionRelation.append(creates_relation)

            self._add_attribute_once(child, "constructor_resolution", "static_fallback")

            # The action is no longer unresolved once a Creates relation exists.
            self._remove_attribute(child, "resolution_status", "unresolved")

    def _looks_like_constructor_action(self, action):
        """
        Heuristic for constructor-like calls.

        Examples:
            Port(...)
            Subject(...)
            FastAPI(...)
            Config(...)
            ModuleType(...)
        """

        if action is None:
            return False

        if getattr(action, "kind", None) not in {"call", "constructor", "constructor_call"}:
            return False

        name = getattr(action, "name", None)

        if not name:
            return False

        simple_name = self._simple_constructor_name(name)

        if not simple_name:
            return False

        # Conservative heuristic: constructor names usually start with an
        # uppercase letter in the examples that remain unresolved.
        return simple_name[0].isupper()

    def _has_creates_relation(self, action):
        if action is None:
            return False

        if not self.factory.has_feature(action, "actionRelation"):
            return False

        for relation in action.actionRelation:
            if getattr(relation.eClass, "name", None) == "Creates":
                return True

        return False

    def _resolve_constructor_target_static(self, constructor_name: str):
        """
        Resolves a constructor target using static information only.

        Resolution order:
        1. Direct id_index lookup.
        2. ClassUnit with the same simple name.
        3. ClassUnit whose qualified_name ends with .Name.
        4. Existing external target with the same simple name.
        5. New external ClassUnit through ExternalModelBuilder.
        """

        if not constructor_name:
            return None

        simple_name = self._simple_constructor_name(constructor_name)

        candidate_keys = [
            constructor_name,
            simple_name,
            f"class:{simple_name}",
            f"external:{simple_name}",
            f"external_type:{simple_name}",
        ]

        for key in candidate_keys:
            target = self.id_index.get(key)

            if self._is_class_like(target):
                return target

        for element in self.id_index.values():
            if not self._is_class_like(element):
                continue

            if getattr(element, "name", None) == simple_name:
                return element

            qualified_name = self._get_attribute_value(element, "qualified_name")

            if qualified_name and qualified_name.endswith(f".{simple_name}"):
                return element

        if self.external_builder is not None:
            for target in self.external_builder.external_targets.values():
                if self._is_class_like(target) and getattr(target, "name", None) == simple_name:
                    return target

            target = self.external_builder.get_or_create_external_class(
                library_name="unknown_external",
                class_name=simple_name,
            )

            self._add_attribute_once(target, "constructor_target", "true")
            self._add_attribute_once(target, "resolution", "static_fallback")
            self.id_index.setdefault(f"external:{simple_name}", target)

            return target

        return None

    def _simple_constructor_name(self, constructor_name: str):
        """
        Extracts the simple constructor name.

        Examples:
            Port              -> Port
            mape.Port         -> Port
            external:Port     -> Port
            package.Port(...) -> Port
        """

        name = str(constructor_name)

        if "(" in name:
            name = name.split("(", 1)[0]

        if ":" in name:
            name = name.rsplit(":", 1)[-1]

        if "." in name:
            name = name.rsplit(".", 1)[-1]

        return name

    def _is_class_like(self, element):
        if element is None:
            return False

        try:
            return element.eClass.name in {
                "ClassUnit",
                "InterfaceUnit",
                "EnumeratedType",
                "Datatype",
            }
        except AttributeError:
            return False

    def _get_attribute_value(self, element, tag: str):
        if element is None:
            return None

        if not self.factory.has_feature(element, "attribute"):
            return None

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) == tag:
                return getattr(attribute, "value", None)

        return None

    def _remove_attribute(self, element, tag: str, value=None):
        if element is None:
            return

        if not self.factory.has_feature(element, "attribute"):
            return

        for attribute in list(element.attribute):
            if getattr(attribute, "tag", None) != tag:
                continue

            if value is not None and getattr(attribute, "value", None) != str(value):
                continue

            try:
                element.attribute.remove(attribute)
            except Exception:
                pass

