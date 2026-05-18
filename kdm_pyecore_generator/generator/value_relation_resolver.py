import ast


class ValueRelationResolver:
    """
    Creates KDM HasValue relations for data elements.

    This resolver consumes value metadata produced by python_kdm_extractor.
    It supports both the older fields:

        assigned_value
        line

    and the newer body/value fields:

        value
        value_kind
        value_type
        value_call
        value_call_id
        line_start

    Supported value kinds in this first robust version:

    - literal:
        x = 10
        name = "Irene"
        active = True

    - collection_literal:
        data = {}
        items = []
        roles = set()

    - call_result:
        user = User()
        result = service.create_user(data)

    For literals and collection literals, HasValue targets a KDM value resolved
    by value_resolver. For call results, HasValue targets the corresponding
    ActionElement when it can be found in action_index.

    Variable references, attribute references and arbitrary expressions are not
    forced into code::Value elements in this version. They can be represented
    later through Reads relations or a more precise expression model.
    """

    SUPPORTED_LITERAL_KINDS = {
        "literal",
        "collection_literal",
    }

    SUPPORTED_ACTION_VALUE_KINDS = {
        "call_result",
    }

    def __init__(self, factory, value_resolver, action_index=None):
        """
        Initializes the value relation resolver.

        Parameters
        ----------
        factory:
            KDMFactory used to create HasValue relations and optional metadata.

        value_resolver:
            Resolver responsible for creating or reusing KDM value elements.

        action_index:
            Index of ActionElement nodes created from calls. It may contain
            entries keyed by call id and by tuples such as
            (owner_id, line, call_name).
        """

        self.factory = factory
        self.value_resolver = value_resolver
        self.action_index = action_index or {}

    def add_value_relations(self, value_elements: list):
        """
        Adds HasValue relations to KDM data elements.

        Parameters
        ----------
        value_elements:
            List of dictionaries. Each item must contain:

            - kdm_element: KDM element that will own the HasValue relation.
            - source_model: JSON element containing value metadata.

            It may also contain:

            - owner_id: id of the owning callable, used to resolve call actions.
        """

        for item in value_elements:
            kdm_element = item.get("kdm_element")
            source_model = item.get("source_model", {})

            if kdm_element is None:
                continue

            value_info = self._extract_value_info(source_model)

            if value_info["raw_value"] is None:
                continue

            target = self._resolve_value_target(item, value_info)

            if target is None:
                continue

            if self._has_has_value_relation(kdm_element, target):
                continue

            relation = self.factory.create_has_value_relation(target)
            kdm_element.codeRelation.append(relation)

            self._attach_value_metadata(
                kdm_element=kdm_element,
                value_info=value_info,
            )

    def _extract_value_info(self, source_model: dict):
        """
        Normalizes old and new JSON value fields into one dictionary.
        """

        raw_value = source_model.get("assigned_value")

        if raw_value is None:
            raw_value = source_model.get("value")

        value_kind = source_model.get("value_kind")
        value_type = source_model.get("value_type")

        value_call = source_model.get("value_call") or {}
        value_call_id = source_model.get("value_call_id") or value_call.get("id")

        line = source_model.get("line")

        if line is None:
            line = source_model.get("line_start")

        return {
            "raw_value": raw_value,
            "value_kind": value_kind,
            "value_type": value_type,
            "value_call": value_call,
            "value_call_id": value_call_id,
            "line": line,
        }

    def _resolve_value_target(self, item: dict, value_info: dict):
        """
        Resolves the target element of the HasValue relation.
        """

        value_kind = value_info.get("value_kind")

        if value_kind in self.SUPPORTED_ACTION_VALUE_KINDS:
            target = self._resolve_action_value(item, value_info)

            if target is not None:
                return target

            # Fallback for old JSON without value_kind or without synchronized
            # value_call_id.
            target = self._resolve_action_value_from_text(
                item,
                value_info.get("raw_value"),
                value_info.get("line"),
            )

            if target is not None:
                return target

            return None

        if value_kind in self.SUPPORTED_LITERAL_KINDS:
            return self.value_resolver.resolve_value(value_info.get("raw_value"))

        # Backward compatibility with older JSON models that do not include
        # value_kind.
        if value_kind is None and self._is_literal_value(value_info.get("raw_value")):
            return self.value_resolver.resolve_value(value_info.get("raw_value"))

        return None

    def _resolve_action_value(self, item: dict, value_info: dict):
        """
        Resolves a call-result value to the corresponding ActionElement.
        """

        value_call_id = value_info.get("value_call_id")

        if value_call_id:
            target = self.action_index.get(value_call_id)

            if target is not None:
                return target

        value_call = value_info.get("value_call") or {}
        call_name = value_call.get("name") or value_info.get("raw_value")
        line = value_call.get("line") or value_info.get("line")

        return self._resolve_action_value_from_text(
            item=item,
            raw_value=call_name,
            line=line,
        )

    def _resolve_action_value_from_text(self, item: dict, raw_value, line):
        """
        Resolves an action value using owner id, source line and call name.
        """

        owner_id = item.get("owner_id")

        if owner_id is None or line is None or raw_value is None:
            return None

        raw_text = str(raw_value).strip()

        # Exact match: assigned value equals call name/function/method/class name.
        target = self.action_index.get((owner_id, line, raw_text))

        if target is not None:
            return target

        # Fallback: if there is a single action on the same line, use it when
        # the assigned value text is compatible with the action name.
        actions_on_line = self.action_index.get((owner_id, line), [])

        if len(actions_on_line) == 1:
            action = actions_on_line[0]
            action_name = getattr(action, "name", "")

            if raw_text == action_name:
                return action

            if raw_text in action_name:
                return action

            if action_name in raw_text:
                return action

        return None

    def _has_has_value_relation(self, kdm_element, target) -> bool:
        """
        Checks whether the element already has a HasValue relation to target.
        """

        if not hasattr(kdm_element, "codeRelation"):
            return False

        for relation in kdm_element.codeRelation:
            relation_type = getattr(relation.eClass, "name", None)

            if relation_type != "HasValue":
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

    def _attach_value_metadata(self, kdm_element, value_info: dict):
        """
        Adds lightweight value metadata to the source KDM element.

        The actual KDM semantics are represented by the HasValue relation.
        Therefore, raw JSON fields such as assigned_value must not be copied
        into the KDM as attributes, because they are considered obsolete by
        the validator.
        """

        value_kind = value_info.get("value_kind")
        value_type = value_info.get("value_type")

        self._add_attribute_once(kdm_element, "value_kind", value_kind)
        self._add_attribute_once(kdm_element, "value_type", value_type)

    def _is_literal_value(self, raw_value):
        """
        Backward-compatible literal detection for older JSON models.
        """

        if raw_value is None:
            return False

        if isinstance(raw_value, (int, float, bool)):
            return True

        text = str(raw_value).strip()

        if text in {"None", "True", "False"}:
            return True

        try:
            ast.literal_eval(text)
            return True
        except Exception:
            return False

    def _has_attribute(self, element, tag: str, value: str) -> bool:
        if value is None:
            return True

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
