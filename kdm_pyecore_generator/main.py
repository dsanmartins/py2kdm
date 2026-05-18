from pathlib import Path
import argparse

from pyecore.resources import URI

from generator.kdm_loader import KDMLoader
from generator.classifier_resolver import ClassifierResolver
from generator.kdm_factory import KDMFactory
from generator.json_loader import JSONModelLoader
from generator.json_to_kdm_mapper import JsonToKDMMapper
from generator.reference_resolver import ReferenceResolver
from generator.external_model_builder import ExternalModelBuilder
from generator.inventory_builder import InventoryBuilder
from generator.validation import BasicValidator
from generator.type_resolver import TypeResolver
from generator.type_relation_resolver import TypeRelationResolver
from generator.value_resolver import ValueResolver
from generator.value_relation_resolver import ValueRelationResolver
from generator.access_relation_resolver import AccessRelationResolver
from generator.return_relation_resolver import ReturnRelationResolver
from generator.body_action_mapper import BodyActionMapper
from generator.exception_relation_resolver import ExceptionRelationResolver
from generator.kdm_validator import KDMValidator


DEFAULT_KDM_ECORE_PATH = "metamodels/kdm_1_4.ecore"
DEFAULT_JSON_INPUT_PATH = "input/python_model.json"
DEFAULT_OUTPUT_PATH = "output/example_project.kdm.xmi"


def generate_kdm(
    json_input_path: str = DEFAULT_JSON_INPUT_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    kdm_ecore_path: str = DEFAULT_KDM_ECORE_PATH,
    validate: bool = True,
):
    """
    Generates a KDM model from a JSON intermediate model.

    Parameters
    ----------
    json_input_path:
        Path to the JSON input model.

    output_path:
        Path where the generated KDM XMI will be saved.

    kdm_ecore_path:
        Path to the KDM 1.4 Ecore metamodel.

    validate:
        Whether to run JSON-level and KDM-level validations.

    Returns
    -------
    dict
        Summary information about the generated model.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 1. Load KDM 1.4 metamodel
    # ------------------------------------------------------------

    loader = KDMLoader(kdm_ecore_path)
    resource_set, root_package = loader.load()

    resolver = ClassifierResolver(root_package)
    factory = KDMFactory(resolver)

    # ------------------------------------------------------------
    # 2. Load JSON intermediate model
    # ------------------------------------------------------------

    json_loader = JSONModelLoader(json_input_path)
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

    reference_resolver.add_call_relations(data)

    # ------------------------------------------------------------
    # 8b. Map body control structures and non-call statements
    #
    # This creates:
    # - BlockUnit body for each MethodUnit / CallableUnit with a body
    # - ActionElement for ordinary statements
    # - TryUnit for try blocks
    # - CatchUnit for except blocks
    # - FinallyUnit for finally blocks
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
    # ------------------------------------------------------------

    builtin_model = factory.create_code_model("PythonBuiltins")
    segment.model.append(builtin_model)

    # ------------------------------------------------------------
    # 8d. Resolve exception semantics
    #
    # This creates:
    # - raise X(...) -> action::Throws -> StorableUnit X_exception
    # - X_exception  -> code::HasType -> ClassUnit X
    # - TryUnit      -> action::ExceptionFlow -> CatchUnit
    # - TryUnit      -> action::ExitFlow -> FinallyUnit
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
    # - return x       -> action::Reads -> StorableUnit x
    # - return literal -> action::Reads -> StorableUnit literal
    #                     and StorableUnit literal -> code::HasValue -> Value
    # - return f(...)  -> action::Reads -> temporary StorableUnit result
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
    # 11. Validate generated model
    # ------------------------------------------------------------

    if validate:
        validator = BasicValidator()
        report = validator.validate_unresolved_calls(data, mapper.id_index)
        report.print_report()

        kdm_validator = KDMValidator()
        kdm_report = kdm_validator.validate(segment)
        kdm_report.print_report()

        if kdm_report.has_errors():
            raise RuntimeError("KDM validation failed. See validation report above.")

    # ------------------------------------------------------------
    # 12. Save XMI
    # ------------------------------------------------------------

    output_resource = resource_set.create_resource(URI(str(output_path)))
    output_resource.append(segment)
    output_resource.save()

    # ------------------------------------------------------------
    # 13. Summary
    # ------------------------------------------------------------

    summary = {
        "output_path": str(output_path),
        "indexed_internal_elements": len(mapper.id_index),
        "typable_elements": len(mapper.typable_elements),
        "value_elements": len(mapper.value_elements),
        "statement_body_actions": len(body_action_mapper.statement_action_index),
        "callable_body_blocks": len(body_action_mapper.callable_body_block_index),
        "finally_units": len(body_action_mapper.finally_action_index),
        "inventory_model_generated": inventory_builder.inventory_model is not None,
        "source_files": len(inventory_builder.source_files),
        "external_model_generated": external_builder.external_code_model is not None,
        "external_libraries": len(external_builder.library_units),
        "external_targets": len(external_builder.external_targets),
    }

    return summary


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a KDM 1.4 XMI model from a JSON intermediate model."
    )

    parser.add_argument(
        "--input",
        default=DEFAULT_JSON_INPUT_PATH,
        help=f"Path to the JSON input model. Default: {DEFAULT_JSON_INPUT_PATH}",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to the generated KDM XMI file. Default: {DEFAULT_OUTPUT_PATH}",
    )

    parser.add_argument(
        "--metamodel",
        default=DEFAULT_KDM_ECORE_PATH,
        help=f"Path to the KDM 1.4 Ecore metamodel. Default: {DEFAULT_KDM_ECORE_PATH}",
    )

    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Disable JSON-level and KDM-level validation.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    summary = generate_kdm(
        json_input_path=args.input,
        output_path=args.output,
        kdm_ecore_path=args.metamodel,
        validate=not args.no_validation,
    )

    print(f"\nKDM model generated at: {summary['output_path']}")
    print(f"Indexed internal KDM elements: {summary['indexed_internal_elements']}")
    print(f"Typable elements: {summary['typable_elements']}")
    print(f"Value elements: {summary['value_elements']}")
    print(f"Statement/body actions: {summary['statement_body_actions']}")
    print(f"Callable body blocks: {summary['callable_body_blocks']}")
    print(f"Finally units: {summary['finally_units']}")

    if summary["inventory_model_generated"]:
        print("InventoryModel generated.")
        print(f"Source files: {summary['source_files']}")
    else:
        print("No InventoryModel was generated.")

    if summary["external_model_generated"]:
        print("ExternalLibraries_CodeModel generated.")
        print(f"External libraries: {summary['external_libraries']}")
        print(f"External targets: {summary['external_targets']}")
    else:
        print("No external model was required.")


if __name__ == "__main__":
    main()
