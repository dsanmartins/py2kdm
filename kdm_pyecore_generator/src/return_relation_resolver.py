import re


class ReturnRelationResolver:
    """
    Resolves return-value semantics in the generated KDM model.

    It creates standard KDM action::Reads relationships:

        return x        -> Reads -> StorableUnit x
        return f(x)     -> Reads -> StorableUnit return_value_of_f
        return None     -> Reads -> StorableUnit return_literal_None
                            and return_literal_None --HasValue--> Value None

    KDM 1.4 does not define a specific Returns relation. Therefore, the
    returned value is modeled as data read by the return ActionElement.
    """

    def __init__(
        self,
        factory,
        statement_action_index,
        action_index=None,
        storable_index=None,
        id_index=None,
    ):
        self.factory = factory
        self.statement_action_index = statement_action_index
        self.action_index = action_index or {}
        self.storable_index = storable_index or {}
        self.id_index = id_index or {}

    def resolve(self, data: dict):
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._resolve_callable(method)

            for func in file_model.get("functions", []):
                self._resolve_callable(func)

    def _resolve_callable(self, callable_model: dict):
        for item in callable_model.get("body", []):
            self._resolve_body_item(item, callable_model)

    def _resolve_body_item(self, item: dict, callable_model: dict):
        if item.get("statement_type") == "return":
            self._resolve_return(item, callable_model)

        for child in item.get("body", []):
            self._resolve_body_item(child, callable_model)

        for child in item.get("orelse", []):
            self._resolve_body_item(child, callable_model)

        for child in item.get("finalbody", []):
            self._resolve_body_item(child, callable_model)

        for handler in item.get("handlers", []):
            self._resolve_body_item(handler, callable_model)

    # ------------------------------------------------------------
    # Return resolution
    # ------------------------------------------------------------

    def _resolve_return(self, item: dict, callable_model: dict):
        return_action = self.statement_action_index.get(item.get("id"))

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
                self._add_attribute_once(
                    return_action,
                    "unresolved_return_value",
                    item.get("value"),
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
        Priority:
        1. Return value call: return f(...)
        2. Returned variable/storable: return user
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
        Handles return expressions involving calls.

        Examples:
            return json.dumps(...)
            return service.create_user(...)
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
        callable_id = callable_model.get("id")

        candidate_keys = [
            value_name,
            (callable_id, value_name),
            (callable_id, "local", value_name),
            (callable_id, "parameter", value_name),
            (callable_id, "field", value_name),
        ]

        for key in candidate_keys:
            target = self.storable_index.get(key)

            if target is not None:
                return target

        for target in self.storable_index.values():
            if getattr(target, "name", None) == value_name:
                return target

        return None

    # ------------------------------------------------------------
    # Literal return values
    # ------------------------------------------------------------

    def _is_literal_value(self, value) -> bool:
        if value is None:
            return False

        value_text = str(value).strip()

        if value_text in {"None", "True", "False"}:
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

        We create:

            return ActionElement
              ├── StorableUnit return_literal_None
              │     └── HasValue -> Value None
              ├── Value value_None
              └── Reads -> return_literal_None
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
        Creates or reuses a StorableUnit representing the value produced
        by a returned call expression.

        Example:
            return json.dumps(data)

        Produces:
            return
              ├── StorableUnit return_value_of_json_dumps
              │     ├── role = returned_call_result
              │     └── source_call_name = json.dumps
              └── Reads -> return_value_of_json_dumps
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
                ) and self._has_attribute(
                    child,
                    "source_call_name",
                    call_name,
                ):
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

        self._add_attribute_once(
            return_value,
            "source_call_name",
            call_name,
        )

        if self.factory.has_feature(return_action, "codeElement"):
            return_action.codeElement.append(return_value)
        else:
            return None

        return return_value

    # ------------------------------------------------------------
    # Relation creation
    # ------------------------------------------------------------

    def _create_return_relation(self, source, target):
        if source is None or target is None:
            return

        if self._has_return_read_relation(source, target):
            return

        relation = self.factory.create_reads_relation(target)

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return

        self._add_attribute_once(
            source,
            "unresolved_return_read",
            getattr(target, "name", None),
        )

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
