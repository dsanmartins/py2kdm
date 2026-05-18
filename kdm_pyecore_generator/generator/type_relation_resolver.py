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

            relation = self.factory.create_has_type_relation(target_type)
            kdm_element.codeRelation.append(relation)
