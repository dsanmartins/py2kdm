class TypeRelationResolver:
    def __init__(self, factory, type_resolver):
        self.factory = factory
        self.type_resolver = type_resolver

    def add_type_relations(self, typable_elements: list):
        for item in typable_elements:
            kdm_element = item["kdm_element"]
            source_model = item["source_model"]

            type_id = source_model.get("resolved_type_id")
            qualified_name = source_model.get("resolved_type_qualified_name")

            target_type = self.type_resolver.resolve_type(
                type_id=type_id,
                qualified_name=qualified_name,
            )

            if target_type is None:
                continue

            self._set_native_type_reference(kdm_element, target_type)

            relation = self.factory.create_has_type_relation(target_type)
            kdm_element.codeRelation.append(relation)


    def _set_native_type_reference(self, kdm_element, target_type):
        """
        Sets the native code::DataElement.type reference when the metaclass
        supports it.

        ControlElement.type is intentionally not overwritten here because, for
        MethodUnit and CallableUnit, it should point to code::Signature.
        """

        if kdm_element is None or target_type is None:
            return

        if getattr(kdm_element.eClass, "name", None) in {"MethodUnit", "CallableUnit"}:
            return

        if not self.factory.has_feature(kdm_element, "type"):
            return

        try:
            kdm_element.type = target_type
        except Exception:
            return
