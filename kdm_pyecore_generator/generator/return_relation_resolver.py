import re


class ReturnRelationResolver:
    """
    Resolves return-value semantics in the generated KDM model.

    KDM 1.4 does not define a specific Returns relation. Therefore, this
    resolver models returned values as data read by the return ActionElement.

    It creates the following mappings:

    - return x
        -> ActionElement kind="return"
        -> action::Reads -> StorableUnit x

    - return f(...)
        -> ActionElement kind="return"
        -> StorableUnit return_value_of_f
        -> action::Reads -> return_value_of_f

    - return True
        -> ActionElement kind="return"
        -> StorableUnit return_literal_True
        -> Value value_True
        -> return_literal_True --code::HasValue--> value_True
        -> return --action::Reads--> return_literal_True

    - return
        -> ActionElement kind="return"
        -> Attribute return_flow="void"
    """

    def __init__(
        self,
        factory,
        statement_action_index,
        action_index=None,
        storable_index=None,
        id_index=None,
    ):
        """
        Initializes the return relation resolver.

        Parameters
        ----------
        factory:
            KDMFactory used to create KDM elements and relations.

        statement_action_index:
            Dictionary mapping JSON body ids to ActionElement instances created
            by BodyActionMapper.

        action_index:
            Dictionary of call ActionElement nodes created by ReferenceResolver.

        storable_index:
            Dictionary of variables, parameters and fields represented as
            StorableUnit elements.

        id_index:
            Dictionary mapping intermediate JSON ids to generated KDM elements.
        """

        self.factory = factory
        self.statement_action_index = statement_action_index
        self.action_index = action_index or {}
        self.storable_index = storable_index or {}
        self.id_index = id_index or {}


    def _copy_source_region_from(self, source_element, target_element):
        """Copy the first SourceRegion from source_element to target_element.

        Synthetic StorableUnit and Value nodes created for return semantics
        should remain traceable to the return statement that produced them.
        SourceRef/SourceRegion are containment objects, so we must create a
        fresh region instead of reusing the existing one.
        """
        if source_element is None or target_element is None:
            return False

        if not self.factory.has_feature(target_element, "source"):
            return False

        if list(getattr(target_element, "source", []) or []):
            return False

        for source_ref in list(getattr(source_element, "source", []) or []):
            source_language = getattr(source_ref, "language", None)
            for region in list(getattr(source_ref, "region", []) or []):
                self.factory.add_source_region(
                    target_element,
                    path=getattr(region, "path", None),
                    language=getattr(region, "language", None) or source_language,
                    start_line=getattr(region, "startLine", None),
                    end_line=getattr(region, "endLine", None),
                    start_position=getattr(region, "startPosition", None),
                    end_position=getattr(region, "endPosition", None),
                    file_item=getattr(region, "file", None),
                )
                return True

        return False

    def _json_get(self, item: dict, snake_name: str, camel_name: str = None, default=None):
        if item is None:
            return default
        if snake_name in item:
            return item.get(snake_name)
        if camel_name and camel_name in item:
            return item.get(camel_name)
        return default

    def _json_list(self, item: dict, snake_name: str, camel_name: str = None):
        value = self._json_get(item, snake_name, camel_name, [])
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    def _callable_key(self, callable_model: dict):
        return (
            callable_model.get("id")
            or callable_model.get("qualifiedSignature")
            or callable_model.get("qualified_signature")
            or callable_model.get("qualifiedName")
            or callable_model.get("qualified_name")
            or callable_model.get("name")
        )

    def resolve(self, data: dict):
        """
        Resolves return semantics for all functions and methods contained in
        the intermediate JSON model.
        """

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._resolve_callable(method)

            for func in file_model.get("functions", []):
                self._resolve_callable(func)

        for element in data.get("elements", []):
            for method in element.get("methods", []):
                self._resolve_callable(method)

    def _resolve_callable(self, callable_model: dict):
        """
        Resolves return statements inside a single callable body.
        """

        for item in callable_model.get("body", []):
            self._resolve_body_item(item, callable_model)

    def _resolve_body_item(self, item: dict, callable_model: dict):
        """
        Recursively resolves return statements inside a body item.
        """

        if self._json_get(item, "statement_type", "statementType") == "return":
            self._resolve_return(item, callable_model)

        for child in self._json_list(item, "body"):
            self._resolve_body_item(child, callable_model)

        for child in self._json_list(item, "orelse", "elseBody"):
            self._resolve_body_item(child, callable_model)

        for child in self._json_list(item, "finalbody", "finallyBody"):
            self._resolve_body_item(child, callable_model)

        for handler in self._json_list(item, "handlers", "catchClauses"):
            self._resolve_body_item(handler, callable_model)

    # ------------------------------------------------------------
    # Return resolution
    # ------------------------------------------------------------

    def _resolve_return_action(self, item: dict, callable_model: dict):
        item_id = item.get("id")
        if item_id and item_id in self.statement_action_index:
            return self.statement_action_index[item_id]

        owner_key = self._callable_key(callable_model)
        line_start = self._json_get(item, "line_start", "lineStart")
        line_end = self._json_get(item, "line_end", "lineEnd")
        kind = self._json_get(item, "statement_type", "statementType")

        for key in (
            (owner_key, line_start, kind),
            (owner_key, line_start, line_end, kind),
            (owner_key, line_start),
        ):
            if key in self.statement_action_index:
                return self.statement_action_index[key]

        return None

    def _resolve_return(self, item: dict, callable_model: dict):
        """
        Resolves a single return statement.
        """

        return_action = self._resolve_return_action(item, callable_model)

        if return_action is None:
            return

        target = self._find_return_target(
            item=item,
            callable_model=callable_model,
            return_action=return_action,
        )

        if target is None:
            if item.get("value") is None:
                self._add_attribute_once(
                    return_action,
                    "return_flow",
                    "void",
                )
            else:
                target = self._get_or_create_return_expression_value(
                    return_action=return_action,
                    value=item.get("value"),
                )
                self._create_return_relation(
                    source=return_action,
                    target=target,
                )
            return

        self._create_return_relation(
            source=return_action,
            target=target,
        )

    def _find_return_target(
        self,
        item: dict,
        callable_model: dict,
        return_action,
    ):
        """
        Finds the KDM element representing the value returned by a return
        statement.

        Resolution priority:
        1. Return value call: return f(...)
        2. Returned variable or storable: return user
        3. Returned literal: return None, return 1, return "text"
        """

        call_target = self._find_return_call_target(item)

        if call_target is not None:
            return self._get_or_create_return_call_value(
                return_action=return_action,
                call_action=call_target,
            )

        value = item.get("value")

        if value is None:
            return None

        storable_target = self._find_storable_target(
            callable_model=callable_model,
            value=value,
        )

        if storable_target is not None:
            return storable_target

        if self._is_literal_value(value):
            return self._get_or_create_return_literal_value(
                return_action=return_action,
                value=value,
            )

        return None

    def _find_return_call_target(self, item: dict):
        """
        Finds the ActionElement corresponding to a call expression returned by
        a return statement.
        """

        value_call_id = item.get("value_call_id")

        if value_call_id and value_call_id in self.action_index:
            return self.action_index[value_call_id]

        value_call = item.get("value_call") or {}
        nested_value_call_id = value_call.get("id")

        if nested_value_call_id and nested_value_call_id in self.action_index:
            return self.action_index[nested_value_call_id]

        for call in item.get("value_calls", []):
            call_id = call.get("id")

            if call_id and call_id in self.action_index:
                return self.action_index[call_id]

        return None

    def _find_storable_target(self, callable_model: dict, value):
        """
        Attempts to resolve a returned variable or attribute to a StorableUnit.
        """

        if value is None:
            return None

        value_name = str(value)
        callable_id = self._callable_key(callable_model)

        candidate_keys = [
            value_name,
            (callable_id, value_name),
            (callable_id, "local", value_name),
            (callable_id, "parameter", value_name),
            (callable_id, "field", value_name),
        ]

        for key in candidate_keys:
            target = self.storable_index.get(key)

            if self._is_storable_unit(target):
                return target

        for target in self.storable_index.values():
            if not self._is_storable_unit(target):
                continue

            if getattr(target, "name", None) == value_name:
                return target

        return None

    # ------------------------------------------------------------
    # Literal return values
    # ------------------------------------------------------------

    def _is_literal_value(self, value) -> bool:
        """
        Checks whether a returned expression is a simple literal supported by
        the generator.
        """

        if value is None:
            return False

        value_text = str(value).strip()

        if value_text in {"None", "True", "False", "null", "true", "false"}:
            return True

        if re.fullmatch(r"-?\d+", value_text):
            return True

        if re.fullmatch(r"-?\d+\.\d+", value_text):
            return True

        if (
            len(value_text) >= 2
            and value_text[0] in {"'", '"'}
            and value_text[-1] == value_text[0]
        ):
            return True

        return False

    def _get_or_create_return_literal_value(self, return_action, value):
        """
        Creates or reuses a StorableUnit representing a returned literal.

        KDM Reads.to must point to a StorableUnit in this generator.

        Expected structure:

            return ActionElement
              ├── StorableUnit return_literal_None
              │     └── code::HasValue -> Value None
              ├── Value value_None
              └── action::Reads -> return_literal_None
        """

        if return_action is None:
            return None

        value_text = str(value).strip()
        safe_value_name = self._safe_name(value_text)

        storable_name = f"return_literal_{safe_value_name}"
        value_name = f"value_{safe_value_name}"

        if not self.factory.has_feature(return_action, "codeElement"):
            return None

        literal_storable = None

        for child in return_action.codeElement:
            if getattr(child.eClass, "name", None) != "StorableUnit":
                continue

            if self._has_attribute(
                child,
                "role",
                "returned_literal",
            ) and self._has_attribute(
                child,
                "literal_value",
                value_text,
            ):
                literal_storable = child
                break

        if literal_storable is None:
            literal_storable = self.factory.create_storable_unit(
                name=storable_name
            )

            self._add_attribute_once(
                literal_storable,
                "role",
                "returned_literal",
            )

            self._add_attribute_once(
                literal_storable,
                "literal_value",
                value_text,
            )

            self._copy_source_region_from(return_action, literal_storable)
            return_action.codeElement.append(literal_storable)

        value_element = None

        for child in return_action.codeElement:
            if getattr(child.eClass, "name", None) != "Value":
                continue

            if self._has_attribute(
                child,
                "role",
                "literal_value",
            ) and self._has_attribute(
                child,
                "literal_value",
                value_text,
            ):
                value_element = child
                break

        if value_element is None:
            value_element = self.factory.create_value(
                name=value_name,
                value=value_text,
            )

            self._add_attribute_once(
                value_element,
                "role",
                "literal_value",
            )

            self._add_attribute_once(
                value_element,
                "literal_value",
                value_text,
            )

            self._copy_source_region_from(return_action, value_element)
            return_action.codeElement.append(value_element)

        if not self._has_has_value_relation(literal_storable, value_element):
            has_value = self.factory.create_has_value_relation(value_element)

            if (
                has_value is not None
                and self.factory.has_feature(literal_storable, "codeRelation")
            ):
                literal_storable.codeRelation.append(has_value)

        return literal_storable

    # ------------------------------------------------------------
    # Call result return values
    # ------------------------------------------------------------

    def _get_or_create_return_call_value(self, return_action, call_action):
        """
        Creates or reuses a StorableUnit representing the value produced by a
        returned call expression.

        Example:

            return json.dumps(data)

        Produces:

            return
              ├── StorableUnit return_value_of_json_dumps
              │     ├── role = returned_call_result
              │     └── source_call_name = json.dumps
              └── action::Reads -> return_value_of_json_dumps
        """

        if return_action is None or call_action is None:
            return None

        call_name = getattr(call_action, "name", None)

        if not call_name:
            call_name = "call"

        if self.factory.has_feature(return_action, "codeElement"):
            for child in return_action.codeElement:
                if getattr(child.eClass, "name", None) != "StorableUnit":
                    continue

                if self._has_attribute(
                    child,
                    "role",
                    "returned_call_result",
                ) and getattr(child, "name", None) == f"return_value_of_{self._safe_name(call_name)}":
                    return child

        safe_call_name = self._safe_name(call_name)

        return_value = self.factory.create_storable_unit(
            name=f"return_value_of_{safe_call_name}"
        )

        self._add_attribute_once(
            return_value,
            "role",
            "returned_call_result",
        )

        self._copy_source_region_from(return_action, return_value)

        if self.factory.has_feature(return_action, "codeElement"):
            return_action.codeElement.append(return_value)
        else:
            return None

        return return_value

    def _get_or_create_return_expression_value(self, return_action, value):
        if return_action is None or value is None:
            return None
        value_text = str(value).strip()
        safe_value_name = self._safe_name(value_text)
        storable_name = f"return_expression_{safe_value_name}"
        value_name = f"value_{safe_value_name}"
        if not self.factory.has_feature(return_action, "codeElement"):
            return None
        expression_storable = None
        for child in return_action.codeElement:
            if getattr(child.eClass, "name", None) == "StorableUnit" and getattr(child, "name", None) == storable_name:
                expression_storable = child
                break
        if expression_storable is None:
            expression_storable = self.factory.create_storable_unit(storable_name)
            self._add_attribute_once(expression_storable, "role", "returned_expression")
            self._copy_source_region_from(return_action, expression_storable)
            return_action.codeElement.append(expression_storable)
        value_element = None
        for child in return_action.codeElement:
            if getattr(child.eClass, "name", None) == "Value" and getattr(child, "name", None) == value_name:
                value_element = child
                break
        if value_element is None:
            value_element = self.factory.create_value(name=value_name, value=value_text)
            self._copy_source_region_from(return_action, value_element)
            return_action.codeElement.append(value_element)
        if not self._has_has_value_relation(expression_storable, value_element):
            has_value = self.factory.create_has_value_relation(value_element)
            if has_value is not None and self.factory.has_feature(expression_storable, "codeRelation"):
                expression_storable.codeRelation.append(has_value)
        return expression_storable

    # ------------------------------------------------------------
    # Relation creation
    # ------------------------------------------------------------

    def _create_return_relation(self, source, target):
        """
        Creates a Reads relation from a return ActionElement to the returned
        value representation.
        """

        if source is None or target is None:
            return

        # In this generator, action::Reads is restricted to StorableUnit
        # targets. Parameters are represented as ParameterUnit and must not be
        # used as Reads targets. This preserves the validator convention used
        # by both the Python and Java pipelines.
        if not self._is_storable_unit(target):
            return

        if self._has_return_read_relation(source, target):
            return

        relation = self.factory.create_reads_relation(target)

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return

        return

    def _has_return_read_relation(self, source, target) -> bool:
        if not self.factory.has_feature(source, "actionRelation"):
            return False

        for relation in source.actionRelation:
            if relation.eClass.name != "Reads":
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

    def _has_has_value_relation(self, source, target) -> bool:
        if not self.factory.has_feature(source, "codeRelation"):
            return False

        for relation in source.codeRelation:
            if relation.eClass.name != "HasValue":
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

    def _is_storable_unit(self, element) -> bool:
        if element is None:
            return False

        try:
            return getattr(element.eClass, "name", None) == "StorableUnit"
        except Exception:
            return False

    # ------------------------------------------------------------
    # Generic helpers
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

    def _safe_name(self, value) -> str:
        """
        Converts a literal or call name into a safe identifier fragment for
        generated KDM element names.
        """

        value_text = str(value).strip()

        safe = (
            value_text
            .replace("'", "")
            .replace('"', "")
            .replace(".", "_")
            .replace("-", "minus_")
            .replace(" ", "_")
            .replace("(", "_")
            .replace(")", "_")
            .replace("[", "_")
            .replace("]", "_")
            .replace("{", "_")
            .replace("}", "_")
            .replace(",", "_")
            .replace(":", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

        safe = re.sub(r"_+", "_", safe)
        safe = safe.strip("_")

        if safe == "":
            safe = "empty"

        return safe
