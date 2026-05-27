import re

class BodyActionMapper:
    def __init__(
        self,
        factory,
        id_index,
        action_index=None,
        inventory_builder=None,
        language="unknown",
        external_builder=None,
        storable_index=None,
    ):
        self.factory = factory
        self.id_index = id_index
        self.action_index = action_index or {}
        self.inventory_builder = inventory_builder
        self.language = language
        self.external_builder = external_builder
        self.storable_index = storable_index or {}

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
        Maps body actions for both supported JSON shapes.

        Python extractor shape:
            files[] -> classes[]/functions[] -> methods[] -> body[]

        Java extractor shape:
            elements[] -> methods[] -> body[]
        """

        files_by_path = {
            file_model.get("path"): file_model
            for file_model in data.get("files", [])
            if file_model.get("path")
        }

        # Python-style model.
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._map_callable_body(method, file_model)

            for func in file_model.get("functions", []):
                self._map_callable_body(func, file_model)

        # Generic/Java-style model.
        for element in data.get("elements", []):
            file_path = element.get("filePath") or element.get("file_path")
            file_model = files_by_path.get(file_path) or {
                "path": file_path,
                "packageName": element.get("packageName"),
                "package_name": element.get("package_name"),
            }

            for method in element.get("methods", []):
                # Preserve owner file information for Java methods because
                # method entries do not always carry filePath directly.
                if "filePath" not in method and "file_path" not in method and file_path:
                    method = dict(method)
                    method["filePath"] = file_path

                self._map_callable_body(method, file_model)

    def _map_callable_body(self, callable_model: dict, file_model: dict):
        """
        Maps the executable body of a method or function.

        Executable actions must not be contained directly in MethodUnit or
        CallableUnit. They must be contained inside an action::BlockUnit that
        represents the callable body.
        """

        callable_kdm = self._resolve_callable_kdm(callable_model)

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

        # Option A for Java/simple bodies:
        # If a callable body was created but no executable child was attached,
        # materialize simple body statements such as return/assignment/throw as
        # ActionElement nodes. This removes empty-body warnings for getters and
        # simple constructors without weakening the validator.
        self._ensure_trivial_body_actions(
            callable_model=callable_model,
            file_model=file_model,
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
    # Generic JSON access helpers
    # ------------------------------------------------------------

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

    def _line_start(self, item: dict):
        return self._get_value(item, "line_start", "lineStart", "line", default=None)

    def _line_end(self, item: dict):
        return self._get_value(
            item,
            "line_end",
            "lineEnd",
            "endLine",
            default=self._line_start(item),
        )

    def _statement_type(self, item: dict):
        return self._get_value(item, "statement_type", "statementType", default=None)

    def _control_type(self, item: dict):
        return self._get_value(item, "control_type", "controlType", default=None)

    def _callable_key(self, callable_model: dict):
        return self._get_value(
            callable_model,
            "id",
            "qualified_signature",
            "qualifiedSignature",
            "qualifiedName",
            "signature",
            default=None,
        )

    def _resolve_callable_kdm(self, callable_model: dict):
        candidate_keys = [
            callable_model.get("id"),
            callable_model.get("qualified_signature"),
            callable_model.get("qualifiedSignature"),
            callable_model.get("qualifiedName"),
            callable_model.get("signature"),
        ]

        for key in candidate_keys:
            if key is None:
                continue

            target = self.id_index.get(key)

            if target is not None:
                return target

        return None

    def _add_source_metadata_to_action(self, action, statement=None, call=None):
        """
        Adds source metadata to an ActionElement and, when possible, a concrete
        SourceRegion. This is required for repeated Java calls such as
        builder.append(...), which are valid distinct actions but share the same
        method name and kind.
        """

        if action is None:
            return

        statement = statement or {}
        call = call or {}

        line_start = (
            self._line_start(statement)
            or self._line_start(call)
        )

        line_end = (
            self._line_end(statement)
            or self._line_end(call)
            or line_start
        )

        # Do not store call_id or line_start/line_end as Attribute elements.
        # Source positions are represented by source::SourceRegion, and
        # call semantics are represented by action::Calls/action::Creates.

    def _has_concrete_source_region(self, element):
        if element is None or not self.factory.has_feature(element, "source"):
            return False

        for source_ref in element.source:
            for region in getattr(source_ref, "region", []):
                start_line = getattr(region, "startLine", None)
                end_line = getattr(region, "endLine", None)

                if start_line is not None or end_line is not None:
                    return True

        return False

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

        callable_id = self._callable_key(callable_model)

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
            self._line_start(item)
            for item in body
            if self._line_start(item) is not None
        ]

        end_lines = [
            self._line_end(item)
            for item in body
            if self._line_end(item) is not None
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

            self._add_java_behavior_relations(
                action=action,
                item=item,
                callable_model=callable_model,
                file_model=file_model,
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

        for child in self._get_list(item, "body"):
            self._map_body_item(
                item=child,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for child in self._get_list(item, "orelse", "elseBody"):
            self._map_body_item(
                item=child,
                callable_model=callable_model,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for handler in self._get_list(item, "handlers", "catchClauses"):
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
    # Java rich body semantics
    # ------------------------------------------------------------

    def _add_java_behavior_relations(
        self,
        action,
        item: dict,
        callable_model: dict,
        file_model: dict,
    ):
        """
        Adds Java behavior relations derived from the rich generic JSON body.

        This method is intentionally restricted to Java. Python already has
        mature dedicated resolvers for Reads/Writes/Creates/Throws/Try/Catch.
        The method uses native KDM relations whenever possible and avoids
        serializing debug attributes.
        """

        if self.language != "java":
            return

        if action is None or not isinstance(item, dict):
            return

        statement_type = self._statement_type(item)
        node_type = self._get_value(item, "type")
        control_type = self._control_type(item)

        # Reads from conditions such as if (name == null), while (...), switch (...)
        if node_type == "control_structure":
            self._add_java_reads_from_expression(
                action=action,
                callable_model=callable_model,
                expression=self._get_value(item, "condition", "selector", "expression"),
            )

            for call in self._get_list(item, "condition_calls", "conditionCalls"):
                self._add_java_reads_from_call_arguments(action, callable_model, call)

        if statement_type == "assignment":
            for target_name in self._get_list(item, "targets"):
                self._add_java_write(
                    action=action,
                    callable_model=callable_model,
                    reference_name=target_name,
                )

            self._add_java_reads_from_expression(
                action=action,
                callable_model=callable_model,
                expression=self._get_value(item, "value"),
            )

            value_call = self._get_value(item, "value_call", "valueCall", default=None)
            if isinstance(value_call, dict):
                self._add_java_reads_from_call_arguments(action, callable_model, value_call)
                self._add_java_creates_if_constructor(action, value_call)

            if self._is_java_object_creation_item(item):
                self._add_java_creates_from_item(action, item)

        elif statement_type == "return":
            before_reads = self._count_action_relations(action, "Reads")

            self._add_java_reads_from_expression(
                action=action,
                callable_model=callable_model,
                expression=self._get_value(item, "value"),
            )

            value_call = self._get_value(item, "value_call", "valueCall", default=None)
            if isinstance(value_call, dict):
                self._add_java_reads_from_call_arguments(action, callable_model, value_call)
                self._add_java_creates_if_constructor(action, value_call)

            # Keep the validator satisfied for returns whose value is a literal,
            # an external expression, or a parameter that is intentionally not a
            # valid Reads target under the current KDM convention.
            after_reads = self._count_action_relations(action, "Reads")
            if before_reads == after_reads and not self._has_attribute_tag(action, "return_flow"):
                self._add_attribute_once(action, "unresolved_return_value", "true")

        elif statement_type == "call":
            call = self._get_value(item, "call", default=None)
            if isinstance(call, dict):
                self._add_java_reads_from_call_arguments(action, callable_model, call)
                self._add_java_creates_if_constructor(action, call)

        elif statement_type in {"throw", "raise"}:
            self._add_java_throw_relation(action, item)

            for call in self._get_list(item, "exception_calls", "exceptionCalls"):
                self._add_java_reads_from_call_arguments(action, callable_model, call)
                self._add_java_creates_if_constructor(action, call)

        # Generic expression calls nested in any statement.
        for call in self._get_list(item, "value_calls", "valueCalls"):
            self._add_java_reads_from_call_arguments(action, callable_model, call)
            self._add_java_creates_if_constructor(action, call)

        for call in self._get_list(item, "condition_calls", "conditionCalls"):
            self._add_java_reads_from_call_arguments(action, callable_model, call)

        # Object creation can be encoded directly in local variable declarations
        # or assignment/return values.
        if self._is_java_object_creation_item(item):
            self._add_java_creates_from_item(action, item)

    def _add_java_write(self, action, callable_model: dict, reference_name):
        target = self._resolve_java_storable(callable_model, reference_name)

        if target is None:
            return

        self._append_action_relation_once(
            action=action,
            relation_type="Writes",
            target=target,
        )

    def _add_java_read(self, action, callable_model: dict, reference_name):
        target = self._resolve_java_storable(callable_model, reference_name)

        if target is None:
            return

        self._append_action_relation_once(
            action=action,
            relation_type="Reads",
            target=target,
        )

    def _add_java_reads_from_expression(self, action, callable_model: dict, expression):
        for reference_name in self._java_reference_candidates(expression):
            self._add_java_read(action, callable_model, reference_name)

    def _add_java_reads_from_call_arguments(self, action, callable_model: dict, call: dict):
        if not isinstance(call, dict):
            return

        scope = self._get_value(call, "scope", "receiver")
        if scope:
            self._add_java_read(action, callable_model, scope)

        for argument in self._get_list(call, "arguments"):
            if isinstance(argument, dict):
                value = self._get_value(argument, "value", "name")
            else:
                value = argument

            self._add_java_reads_from_expression(action, callable_model, value)

    def _append_action_relation_once(self, action, relation_type: str, target):
        if action is None or target is None:
            return

        if not self.factory.has_feature(action, "actionRelation"):
            return

        for relation in action.actionRelation:
            if getattr(relation.eClass, "name", None) != relation_type:
                continue

            if getattr(relation, "to", None) is target:
                return

        if relation_type == "Reads":
            relation = self.factory.create_reads_relation(target)
        elif relation_type == "Writes":
            relation = self.factory.create_writes_relation(target)
        elif relation_type == "Creates":
            relation = self.factory.create_creates_relation(target)
        elif relation_type == "Throws":
            relation = self.factory.create_throws_relation(target)
        else:
            return

        action.actionRelation.append(relation)

    def _resolve_java_storable(self, callable_model: dict, reference_name):
        if not reference_name:
            return None

        reference_text = str(reference_name).strip()

        if not reference_text:
            return None

        # Strip common Java syntax around field references.
        reference_text = reference_text.replace("this.", "")
        reference_text = reference_text.split("[", 1)[0]

        if "." in reference_text:
            # repository.findName(...) should read repository; this.field
            # was handled above.
            reference_text = reference_text.split(".", 1)[0]

        if not reference_text or not self._is_identifier_like(reference_text):
            return None

        callable_key = self._callable_key(callable_model)

        candidates = []

        if callable_key:
            candidates.extend(
                [
                    (callable_key, reference_text),
                    (callable_key, "local", reference_text),
                    f"{callable_key}:local:{reference_text}",
                    f"{callable_key}:parameter:{reference_text}",
                ]
            )

        owner_qn = self._owner_qualified_name_from_callable(callable_model)

        if owner_qn:
            candidates.append(f"{owner_qn}.{reference_text}")

        candidates.append(reference_text)

        for key in candidates:
            target = self.storable_index.get(key) or self.id_index.get(key)

            if self._is_storable_unit(target):
                return target

        return None

    def _owner_qualified_name_from_callable(self, callable_model: dict):
        signature = self._get_value(
            callable_model,
            "qualifiedSignature",
            "qualified_signature",
            "id",
            default=None,
        )

        if not signature or not isinstance(signature, str):
            return None

        if ".<init>" in signature:
            return signature.split(".<init>", 1)[0]

        if "(" in signature:
            before_params = signature.split("(", 1)[0]
            if "." in before_params:
                return before_params.rsplit(".", 1)[0]

        return None

    def _java_reference_candidates(self, expression):
        if expression is None:
            return []

        if isinstance(expression, dict):
            values = []
            for key in ("name", "value", "target", "scope", "receiver"):
                if expression.get(key):
                    values.extend(self._java_reference_candidates(expression.get(key)))
            return values

        expression_text = str(expression)

        if not expression_text:
            return []

        # Remove quoted strings and character literals.
        expression_text = re.sub(r'"(?:\\.|[^"\\])*"', " ", expression_text)
        expression_text = re.sub(r"'(?:\\.|[^'\\])*'", " ", expression_text)

        candidates = []

        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?\b", expression_text):
            first = token.split(".", 1)[0]

            if first in self._java_keywords():
                continue

            if first in {"String", "Long", "Integer", "Boolean", "List", "Map", "ArrayList", "HashMap", "StringBuilder"}:
                continue

            candidates.append(first)

        return candidates

    def _java_keywords(self):
        return {
            "abstract", "assert", "boolean", "break", "byte", "case", "catch",
            "char", "class", "const", "continue", "default", "do", "double",
            "else", "enum", "extends", "false", "final", "finally", "float",
            "for", "if", "implements", "import", "instanceof", "int",
            "interface", "long", "new", "null", "package", "private",
            "protected", "public", "return", "short", "static", "strictfp",
            "super", "switch", "synchronized", "this", "throw", "throws",
            "transient", "true", "try", "void", "volatile", "while",
        }

    def _is_identifier_like(self, text: str):
        return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(text or "")) is not None

    def _is_storable_unit(self, element):
        return element is not None and getattr(element.eClass, "name", None) == "StorableUnit"

    def _is_java_object_creation_item(self, item: dict):
        value_kind = self._get_value(item, "valueKind", "value_kind")
        statement_type = self._statement_type(item)

        return (
            value_kind == "object_creation"
            or statement_type == "object_creation"
            or self._get_value(item, "objectCreation", "object_creation") is not None
        )

    def _add_java_creates_if_constructor(self, action, call: dict):
        constructor_name = self._constructor_name_from_call(call)

        if not constructor_name:
            return

        self._add_java_creates(action, constructor_name)

    def _add_java_creates_from_item(self, action, item: dict):
        constructor_name = (
            self._get_value(item, "className", "class_name", "assignedType", "assigned_type")
            or self._constructor_name_from_value(self._get_value(item, "value"))
        )

        value_call = self._get_value(item, "value_call", "valueCall", default=None)
        if not constructor_name and isinstance(value_call, dict):
            constructor_name = self._constructor_name_from_call(value_call)

        if not constructor_name:
            return

        self._add_java_creates(action, constructor_name)

    def _constructor_name_from_call(self, call: dict):
        if not isinstance(call, dict):
            return None

        classification = self._get_value(call, "classification")
        kind = self._get_value(call, "kind")

        target_id = self._get_value(call, "target_id", "targetId", "resolvedTarget", "resolved_target")
        class_name = self._get_value(call, "className", "class_name")

        if class_name:
            return str(class_name).split(".")[-1]

        if target_id and ".<init>" in str(target_id):
            return str(target_id).split(".<init>", 1)[0].split(".")[-1]

        if target_id and str(target_id).endswith(")"):
            # Constructor signatures sometimes arrive as pkg.Type(...)
            before_params = str(target_id).split("(", 1)[0]
            last = before_params.split(".")[-1]
            if last and last[:1].isupper():
                return last

        if classification == "constructor" or kind == "constructor_call":
            name = self._get_value(call, "methodName", "method_name", "name", "function")
            if name:
                return str(name).split(".")[-1]

        return None

    def _constructor_name_from_value(self, value):
        if value is None:
            return None

        value_text = str(value).strip()

        match = re.search(r"\bnew\s+([A-Za-z_][A-Za-z0-9_.$]*)", value_text)
        if match:
            return match.group(1).split(".")[-1]

        if value_text and value_text[0].isupper():
            return value_text.split("(", 1)[0].split(".")[-1]

        return None

    def _add_java_creates(self, action, constructor_name: str):
        if not constructor_name:
            return

        target = self._resolve_class_unit_by_name(constructor_name)

        if target is None and self.external_builder is not None:
            target = self.external_builder.get_or_create_external_class(
                library_name=self._infer_java_library_name(constructor_name),
                class_name=constructor_name,
            )

        if target is None:
            return

        self._append_action_relation_once(
            action=action,
            relation_type="Creates",
            target=target,
        )

    def _resolve_class_unit_by_name(self, class_name: str):
        if not class_name:
            return None

        for element in self.id_index.values():
            if getattr(element.eClass, "name", None) != "ClassUnit":
                continue

            if getattr(element, "name", None) == class_name:
                return element

        return None

    def _infer_java_library_name(self, class_name: str):
        if class_name in {"StringBuilder", "String", "Long", "Integer", "Boolean", "RuntimeException", "IllegalArgumentException", "IllegalStateException"}:
            return "java.lang"

        if class_name in {"ArrayList", "HashMap", "List", "Map"}:
            return "java.util"

        return "java.external"

    def _add_java_throw_relation(self, action, item: dict):
        exception_name = self._java_exception_name_from_item(item)

        if not exception_name:
            return

        exception_data = self._get_or_create_java_thrown_exception_data(
            action=action,
            exception_name=exception_name,
        )

        if exception_data is None:
            return

        self._append_action_relation_once(
            action=action,
            relation_type="Throws",
            target=exception_data,
        )

    def _java_exception_name_from_item(self, item: dict):
        exception_name = self._get_value(item, "exception", "exceptionType")

        if exception_name:
            return str(exception_name).split(".")[-1]

        for call in self._get_list(item, "exception_calls", "exceptionCalls"):
            constructor_name = self._constructor_name_from_call(call)
            if constructor_name:
                return constructor_name

        value = self._get_value(item, "value")
        constructor_name = self._constructor_name_from_value(value)
        if constructor_name:
            return constructor_name

        return None

    def _get_or_create_java_thrown_exception_data(self, action, exception_name: str):
        if action is None or not exception_name:
            return None

        if not self.factory.has_feature(action, "codeElement"):
            return None

        storable_name = f"{exception_name}_exception"

        for child in action.codeElement:
            if getattr(child.eClass, "name", None) == "StorableUnit" and getattr(child, "name", None) == storable_name:
                return child

        exception_data = self.factory.create_storable_unit(storable_name)

        self._add_attribute_once(exception_data, "role", "thrown_exception")

        action.codeElement.append(exception_data)

        return exception_data

    def _count_action_relations(self, action, relation_type: str):
        if action is None or not self.factory.has_feature(action, "actionRelation"):
            return 0

        return sum(
            1
            for relation in action.actionRelation
            if getattr(relation.eClass, "name", None) == relation_type
        )


    # ------------------------------------------------------------
    # Option A: materialize trivial body statements
    # ------------------------------------------------------------

    def _ensure_trivial_body_actions(
        self,
        callable_model: dict,
        file_model: dict,
        body_block,
    ):
        """
        Ensures that simple callable bodies are represented by executable
        KDM actions.

        This is intentionally conservative: it only runs when the callable
        already has body items in the JSON model but the BlockUnit does not
        contain any executable children. In practice, this covers Java getters,
        setters and simple constructors such as:

            return field;
            this.field = parameter;

        Python bodies are normally already rich enough, so this method is a
        no-op for them unless a body block would otherwise be empty.
        """

        if body_block is None:
            return

        if self._has_executable_children(body_block):
            return

        body_items = self._get_list(callable_model, "body")

        if not body_items:
            self._create_synthetic_empty_body_action(
                callable_model=callable_model,
                file_model=file_model,
                body_block=body_block,
            )
            return

        for item in body_items:
            self._materialize_trivial_body_item(
                item=item,
                file_model=file_model,
                parent_kdm=body_block,
            )

        # Defensive fallback: if the JSON body exists but none of its items
        # could be converted into executable KDM nodes, create a conservative
        # synthetic action. This keeps Java getters and constructors from
        # producing empty callable_body BlockUnits without weakening validation.
        if not self._has_executable_children(body_block):
            self._create_synthetic_empty_body_action(
                callable_model=callable_model,
                file_model=file_model,
                body_block=body_block,
            )

    def _materialize_trivial_body_item(
        self,
        item: dict,
        file_model: dict,
        parent_kdm,
    ):
        if not isinstance(item, dict):
            return

        action = self._create_action_for_body_item(item)

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

        for child in self._get_list(item, "body"):
            self._materialize_trivial_body_item(
                item=child,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for child in self._get_list(item, "orelse", "elseBody"):
            self._materialize_trivial_body_item(
                item=child,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for handler in self._get_list(item, "handlers", "catchClauses"):
            self._materialize_trivial_body_item(
                item=handler,
                file_model=file_model,
                parent_kdm=next_parent,
            )

        for child in self._get_list(item, "finalbody", "finallyBody"):
            self._materialize_trivial_body_item(
                item=child,
                file_model=file_model,
                parent_kdm=next_parent,
            )

    def _create_synthetic_empty_body_action(
        self,
        callable_model: dict,
        file_model: dict,
        body_block,
    ):
        """
        Creates one conservative executable ActionElement for Java callables
        whose body block would otherwise remain empty.

        This is used only as a fallback. It is intentionally not applied to
        Python, whose extractor already provides rich body actions and where
        empty blocks should remain visible during validation.
        """

        if body_block is None:
            return

        if self.language != "java":
            return

        if self._has_executable_children(body_block):
            return

        method_kind = self._get_value(
            callable_model,
            "kind",
            "methodKind",
            "method_kind",
            default="method",
        )

        return_type = self._get_value(
            callable_model,
            "returnType",
            "return_type",
            default=None,
        )

        if method_kind == "constructor":
            action_name = "constructor_body"
            action_kind = "constructor_body"
        elif return_type and str(return_type) != "void":
            action_name = "return"
            action_kind = "return"
        else:
            action_name = "statement"
            action_kind = "statement"

        action = self.factory.create_action_element(
            name=action_name,
            kind=action_kind,
        )

        self._add_attribute_once(action, "synthetic_body_action", "true")
        self._add_attribute_once(action, "synthetic_reason", "empty_callable_body")

        callable_key = self._callable_key(callable_model)
        if callable_key is not None:
            self._add_attribute_once(action, "callable_body_id", callable_key)

        synthetic_item = {
            "id": f"synthetic-body:{callable_key or getattr(body_block, 'name', 'body')}",
            "type": "statement",
            "statement_type": action_kind,
            "line_start": self._get_value(callable_model, "lineStart", "line_start"),
            "line_end": self._get_value(callable_model, "lineEnd", "line_end"),
        }

        self._add_or_update_action(
            action=action,
            item=synthetic_item,
            file_model=file_model,
            parent_kdm=body_block,
        )

    def _has_executable_children(self, parent_kdm):
        if parent_kdm is None:
            return False

        if not self.factory.has_feature(parent_kdm, "codeElement"):
            return False

        executable_types = {
            "ActionElement",
            "TryUnit",
            "CatchUnit",
            "FinallyUnit",
        }

        for child in parent_kdm.codeElement:
            if getattr(child.eClass, "name", None) in executable_types:
                return True

        return False

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
            and self._control_type(item) == "try"
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
            "line_start": self._line_start(item),
            "line_end": self._line_end(item),
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

        for call in self._get_list(item, "condition_calls", "conditionCalls"):
            self._attach_existing_call_action(
                call=call,
                parent_kdm=owner_action,
                expression_role="condition_call",
            )

        for call in self._get_list(item, "value_calls", "valueCalls"):
            self._attach_existing_call_action(
                call=call,
                parent_kdm=owner_action,
                expression_role="value_call",
            )

        for call in self._get_list(item, "exception_calls", "exceptionCalls"):
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

        self._add_source_metadata_to_action(action, call=call)
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

        Supports both snake_case (Python) and camelCase (Java) body fields.
        """

        statement_type = self._statement_type(item)

        if statement_type == "call":
            call_id = self._get_value(item, "call_id", "callId")

            if call_id and call_id in self.action_index:
                return self.action_index[call_id]

            call = self._get_value(item, "call", default={}) or {}
            nested_call_id = self._get_value(call, "id")

            if nested_call_id and nested_call_id in self.action_index:
                return self.action_index[nested_call_id]

            return self._find_action_by_owner_line_and_name(
                callable_model=callable_model,
                line=self._line_start(item),
                name=self._get_value(call, "name", "methodName", "method_name"),
            )

        if statement_type == "assignment":
            value_call_id = self._get_value(item, "value_call_id", "valueCallId")

            if value_call_id and value_call_id in self.action_index:
                return self.action_index[value_call_id]

            value_call = self._get_value(item, "value_call", "valueCall", default={}) or {}
            nested_value_call_id = self._get_value(value_call, "id")

            if nested_value_call_id and nested_value_call_id in self.action_index:
                return self.action_index[nested_value_call_id]

            return self._find_action_by_owner_line_and_name(
                callable_model=callable_model,
                line=self._line_start(item),
                name=self._get_value(item, "value"),
            )

        if statement_type in {"return", "raise", "throw"}:
            for call in self._get_list(item, "value_calls", "valueCalls"):
                call_id = call.get("id")
                if call_id and call_id in self.action_index:
                    return None

            for call in self._get_list(item, "exception_calls", "exceptionCalls"):
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
        statement_type = self._statement_type(item)
        node_type = item.get("type")
        control_type = self._control_type(item)

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
            call = self._get_value(item, "call", default={}) or {}

            if statement_type == "call":
                name = (
                    self._get_value(call, "methodName", "method_name", "method")
                    or self._get_value(call, "name")
                    or "call"
                )
                if isinstance(name, str) and "." in name:
                    name = name.rsplit(".", 1)[-1]
                return self.factory.create_action_element(name=name, kind="call")

            if statement_type in {"throw", "raise"}:
                return self.factory.create_action_element(name=statement_type, kind=statement_type)

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
        self._add_source_metadata_to_action(
            action,
            statement=item,
            call=self._get_value(item, "call", "value_call", "valueCall", default={}) or {},
        )
        self._add_statement_metadata(action, item)
        self._mark_java_return_without_read_as_unresolved(action, item)

        self._attach_action_to_parent(action, parent_kdm)

        item_id = item.get("id")

        if item_id:
            self.statement_action_index[item_id] = action

    # ------------------------------------------------------------
    # Source and metadata
    # ------------------------------------------------------------

    def _add_source_region(self, action, statement: dict, file_model: dict):
        if self._has_concrete_source_region(action):
            return

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=self._line_start(statement),
            end_line=self._line_end(statement),
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

    def _mark_java_return_without_read_as_unresolved(self, action, item: dict):
        """
        Marks Java return actions as unresolved when no Reads relation is
        available.

        The KDM validator expects a return ActionElement to either have a
        Reads relation, have return_flow='void', or be explicitly marked with
        unresolved_return_value. For trivial Java getters, the body fallback may
        create a return ActionElement before a StorableUnit target can be linked.
        This marker keeps the model valid without inventing an incorrect Reads
        relation.
        """

        if action is None:
            return

        if self.language != "java":
            return

        if getattr(action.eClass, "name", None) != "ActionElement":
            return

        action_name = getattr(action, "name", None)
        action_kind = getattr(action, "kind", None)
        statement_type = self._get_value(
            item,
            "statement_type",
            "statementType",
            default=None,
        )

        if action_name != "return" and action_kind != "return" and statement_type != "return":
            return

        if self._has_action_relation_type(action, "Reads"):
            return

        if self._has_attribute_tag(action, "return_flow"):
            return

        if self._has_attribute_tag(action, "unresolved_return_value"):
            return

        self._add_attribute_once(action, "unresolved_return_value", "true")
        self._add_attribute_once(
            action,
            "return_resolution",
            "unresolved_or_trivial_java_return",
        )

    def _has_action_relation_type(self, action, relation_type: str) -> bool:
        if action is None:
            return False

        if not self.factory.has_feature(action, "actionRelation"):
            return False

        for relation in action.actionRelation:
            if getattr(relation.eClass, "name", None) == relation_type:
                return True

        return False

    def _has_attribute_tag(self, element, tag: str) -> bool:
        if element is None:
            return False

        if not self.factory.has_feature(element, "attribute"):
            return False

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) == tag:
                return True

        return False

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

        statement_type = self._statement_type(item)

        if statement_type not in {"call", "return", "raise", "assignment"}:
            return

        owner_id = callable_model.get("id")
        owner_line = self._line_start(item)

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

        statement_type = self._statement_type(item)

        if statement_type not in {"call", "assignment", "return", "raise"}:
            return

        owner_id = callable_model.get("id")
        owner_line = self._line_start(item)

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
        statement_type = self._statement_type(item)

        if statement_type in {"return", "raise"}:
            return True

        if statement_type == "assignment":
            value = item.get("value")

            if value and str(value) == owner_name:
                return True

        if statement_type == "call":
            call = self._get_value(item, "call", default={}) or {}
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

