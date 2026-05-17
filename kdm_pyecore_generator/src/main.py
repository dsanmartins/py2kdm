from pathlib import Path
from pyecore.resources import URI

from kdm_loader import KDMLoader
from classifier_resolver import ClassifierResolver
from kdm_factory import KDMFactory
from json_loader import JSONModelLoader
from json_to_kdm_mapper import JsonToKDMMapper
from reference_resolver import ReferenceResolver
from external_model_builder import ExternalModelBuilder
from inventory_builder import InventoryBuilder
from validation import BasicValidator
from type_resolver import TypeResolver
from type_relation_resolver import TypeRelationResolver
from value_resolver import ValueResolver
from value_relation_resolver import ValueRelationResolver
from access_relation_resolver import AccessRelationResolver
from return_relation_resolver import ReturnRelationResolver
from body_action_mapper import BodyActionMapper
from exception_relation_resolver import ExceptionRelationResolver
from kdm_validator import KDMValidator


KDM_ECORE_PATH = "metamodels/kdm_1_4.ecore"
JSON_INPUT_PATH = "input/python_model.json"
OUTPUT_PATH = "output/example_project.kdm.xmi"


def main():
    Path("output").mkdir(exist_ok=True)

    # ------------------------------------------------------------
    # 1. Load KDM 1.4 metamodel
    # ------------------------------------------------------------

    loader = KDMLoader(KDM_ECORE_PATH)
    resource_set, root_package = loader.load()

    resolver = ClassifierResolver(root_package)
    factory = KDMFactory(resolver)

    # ------------------------------------------------------------
    # 2. Load JSON intermediate model
    # ------------------------------------------------------------

    json_loader = JSONModelLoader(JSON_INPUT_PATH)
    data = json_loader.load()

    project_name = data.get("projectName", "UnknownProject")
    language = data.get("language", "unknown")

    # ------------------------------------------------------------
    # 3. Create root Segment
    # ------------------------------------------------------------

    segment = factory.create_segment(project_name)

    # ------------------------------------------------------------
    # 4. Create InventoryModel + SourceFile elements
    # ------------------------------------------------------------

    inventory_builder = InventoryBuilder(
        factory=factory,
        segment=segment,
        language=language,
    )

    inventory_builder.build_from_json(data)

    # ------------------------------------------------------------
    # 5. Create CodeModel and structural KDM elements
    # ------------------------------------------------------------

    mapper = JsonToKDMMapper(
        factory=factory,
        inventory_builder=inventory_builder,
    )

    segment = mapper.transform_structure_into_segment(data, segment)

    internal_code_model = None

    for model in segment.model:
        if (
            model.eClass.name == "CodeModel"
            and model.name == f"{project_name}_CodeModel"
        ):
            internal_code_model = model
            break

    if internal_code_model is None:
        raise RuntimeError("Internal CodeModel was not found in the KDM segment.")

    # ------------------------------------------------------------
    # 6. External libraries model builder
    # ------------------------------------------------------------

    external_builder = ExternalModelBuilder(factory, segment)

    # ------------------------------------------------------------
    # 7. Resolve types using code::HasType
    # ------------------------------------------------------------

    type_resolver = TypeResolver(
        factory=factory,
        id_index=mapper.id_index,
        external_builder=external_builder,
        code_model=internal_code_model,
    )

    type_relation_resolver = TypeRelationResolver(
        factory=factory,
        type_resolver=type_resolver,
    )

    type_relation_resolver.add_type_relations(mapper.typable_elements)

    # ------------------------------------------------------------
    # 8. Resolve Calls and Creates first
    # ------------------------------------------------------------

    reference_resolver = ReferenceResolver(
        factory=factory,
        id_index=mapper.id_index,
        external_builder=external_builder,
        qualified_name_index=mapper.qualified_name_index,
        class_name_index=mapper.class_name_index,
        language=language,
        inventory_builder=inventory_builder,
    )

    # This creates ActionElement nodes and fills reference_resolver.action_index.
    reference_resolver.add_call_relations(data)

    # ------------------------------------------------------------
    # 8b. Map body control structures and non-call statements
    #
    # This step creates:
    # - ActionElement for ordinary statements/control structures
    # - TryUnit for try blocks
    # - CatchUnit for except blocks
    # - FinallyUnit for finalbody blocks
    # ------------------------------------------------------------

    body_action_mapper = BodyActionMapper(
        factory=factory,
        id_index=mapper.id_index,
        action_index=reference_resolver.action_index,
        inventory_builder=inventory_builder,
        language=language,
    )

    body_action_mapper.map_body_actions(data)

    # ------------------------------------------------------------
    # 8c. Create Python builtins model
    #
    # Builtin exceptions such as ValueError or OSError are created here
    # when they are needed by the exception resolver.
    # ------------------------------------------------------------

    builtin_model = factory.create_code_model("PythonBuiltins")
    segment.model.append(builtin_model)

    # ------------------------------------------------------------
    # 8d. Resolve exception semantics
    #
    # This step creates:
    # - raise X(...)  -> action::Throws -> StorableUnit X_exception
    # - X_exception   -> code::HasType  -> ClassUnit X
    # - TryUnit       -> action::ExceptionFlow -> CatchUnit
    # - TryUnit       -> action::ExitFlow      -> FinallyUnit
    # ------------------------------------------------------------

    exception_relation_resolver = ExceptionRelationResolver(
        factory=factory,
        id_index=mapper.id_index,
        statement_action_index=body_action_mapper.statement_action_index,
        builtin_model=builtin_model,
        external_index=external_builder.external_targets,
        finally_action_index=body_action_mapper.finally_action_index,
    )

    exception_relation_resolver.resolve(data)

    # ------------------------------------------------------------
    # 9. Resolve assigned values using code::HasValue
    # ------------------------------------------------------------

    value_resolver = ValueResolver(
        factory=factory,
        code_model=internal_code_model,
    )

    value_relation_resolver = ValueRelationResolver(
        factory=factory,
        value_resolver=value_resolver,
        action_index=reference_resolver.action_index,
    )

    value_relation_resolver.add_value_relations(mapper.value_elements)

    # ------------------------------------------------------------
    # 9b. Resolve Reads and Writes
    # ------------------------------------------------------------

    access_relation_resolver = AccessRelationResolver(
        factory=factory,
        storable_index=mapper.storable_index,
        action_index=reference_resolver.action_index,
        statement_action_index=body_action_mapper.statement_action_index,
    )

    access_relation_resolver.add_access_relations(data)

    # ------------------------------------------------------------
    # 9c. Resolve return values
    #
    # More standard KDM 1.4 modeling:
    # - return x        -> action::Reads -> StorableUnit x
    # - return literal  -> action::Reads -> StorableUnit literal
    #                      and StorableUnit literal -> code::HasValue -> Value
    # - return f(...)   -> action::Reads -> temporary StorableUnit result
    # ------------------------------------------------------------

    return_relation_resolver = ReturnRelationResolver(
        factory=factory,
        statement_action_index=body_action_mapper.statement_action_index,
        action_index=reference_resolver.action_index,
        storable_index=mapper.storable_index,
        id_index=mapper.id_index,
    )

    return_relation_resolver.resolve(data)

    # ------------------------------------------------------------
    # 10. Resolve Extends and Imports
    # ------------------------------------------------------------

    reference_resolver.add_extends_relations(data)
    reference_resolver.add_import_relations(data)

    # ------------------------------------------------------------
    # 11. Validate JSON-level unresolved calls
    # ------------------------------------------------------------

    validator = BasicValidator()
    report = validator.validate_unresolved_calls(data, mapper.id_index)
    report.print_report()

    # ------------------------------------------------------------
    # 12. Validate generated KDM model
    # ------------------------------------------------------------

    kdm_validator = KDMValidator()
    kdm_report = kdm_validator.validate(segment)
    kdm_report.print_report()

    if kdm_report.has_errors():
        raise RuntimeError("KDM validation failed. See validation report above.")

    # ------------------------------------------------------------
    # 13. Save XMI
    # ------------------------------------------------------------

    output_resource = resource_set.create_resource(URI(OUTPUT_PATH))
    output_resource.append(segment)
    output_resource.save()

    # ------------------------------------------------------------
    # 14. Summary
    # ------------------------------------------------------------

    print(f"\nKDM model generated at: {OUTPUT_PATH}")
    print(f"Indexed internal KDM elements: {len(mapper.id_index)}")
    print(f"Typable elements: {len(mapper.typable_elements)}")
    print(f"Value elements: {len(mapper.value_elements)}")

    print(f"Statement/body actions: {len(body_action_mapper.statement_action_index)}")
    print(f"Finally units: {len(body_action_mapper.finally_action_index)}")

    if inventory_builder.inventory_model is not None:
        print("InventoryModel generated.")
        print(f"Source files: {len(inventory_builder.source_files)}")
    else:
        print("No InventoryModel was generated.")

    if external_builder.external_code_model is not None:
        print("ExternalLibraries_CodeModel generated.")
        print(f"External libraries: {len(external_builder.library_units)}")
        print(f"External targets: {len(external_builder.external_targets)}")
    else:
        print("No external model was required.")


if __name__ == "__main__":
    main()
