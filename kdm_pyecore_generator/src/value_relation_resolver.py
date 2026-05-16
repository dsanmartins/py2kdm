import ast


class ValueRelationResolver:
    def __init__(self, factory, value_resolver, action_index=None):
        self.factory = factory
        self.value_resolver = value_resolver
        self.action_index = action_index or {}

    def add_value_relations(self, value_elements: list):
        for item in value_elements:
            kdm_element = item["kdm_element"]
            source_model = item["source_model"]

            raw_value = source_model.get("assigned_value")

            if raw_value is None:
                continue

            target = self._resolve_action_value(item, raw_value)

            if target is None and self._is_literal_value(raw_value):
                target = self.value_resolver.resolve_value(raw_value)

            if target is None:
                # Complex expression without a matching ActionElement.
                # We avoid creating code::Value for non-literals.
                continue

            relation = self.factory.create_has_value_relation(target)
            kdm_element.codeRelation.append(relation)

    def _resolve_action_value(self, item: dict, raw_value):
        owner_id = item.get("owner_id")
        source_model = item.get("source_model", {})
        line = source_model.get("line")

        if owner_id is None or line is None:
            return None

        raw_text = str(raw_value).strip()

        # Exact match: assigned_value == call name/function/method/class_name
        target = self.action_index.get((owner_id, line, raw_text))
        if target is not None:
            return target

        # Fallback: if there is a single action on the same line, use it
        # when the assigned value text is compatible with the action name.
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

    def _is_literal_value(self, raw_value):
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
