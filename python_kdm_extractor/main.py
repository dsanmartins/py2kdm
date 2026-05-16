import sys
from pathlib import Path

from extractor.project_scanner import find_python_files
from extractor.file_extractor import extract_file_model
from extractor.json_writer import write_json_model
from extractor.symbol_table import SymbolTable
from extractor.import_resolver import ImportResolver
from extractor.call_resolver import CallResolver
from extractor.relationship_builder import RelationshipBuilder
from extractor.element_builder import ElementBuilder
from extractor.summary_builder import SummaryBuilder
from extractor.body_call_synchronizer import BodyCallSynchronizer


def extract_project(project_path: str):
    """
    Extracts an intermediate model from a Python project.
    """

    project_root = Path(project_path).resolve()

    project_model = {
        "projectName": project_root.name,
        "language": "python",
        "files": [],
        "elements": [],
        "relationships": [],
        "symbol_table": {},
        "summary": {}
    }

    python_files = find_python_files(project_root)

    for file_path in python_files:
        try:
            file_model = extract_file_model(file_path, project_root)
            project_model["files"].append(file_model)

        except SyntaxError as error:
            project_model["files"].append({
                "path": str(file_path.relative_to(project_root)),
                "error": f"SyntaxError: {error}"
            })

        except UnicodeDecodeError as error:
            project_model["files"].append({
                "path": str(file_path.relative_to(project_root)),
                "error": f"UnicodeDecodeError: {error}"
            })

    symbol_table = SymbolTable()
    symbol_table.build_from_project_model(project_model)

    import_resolver = ImportResolver(symbol_table, project_model["projectName"])
    import_resolver.resolve_project_imports(project_model)

    call_resolver = CallResolver(symbol_table)
    call_resolver.resolve_project_calls(project_model)

    body_call_synchronizer = BodyCallSynchronizer()
    body_call_synchronizer.sync_project_body_calls(project_model)

    relationship_builder = RelationshipBuilder()
    relationship_builder.build_relationships(project_model)

    element_builder = ElementBuilder()
    element_builder.build_elements(project_model)

    summary_builder = SummaryBuilder()
    summary_builder.build_summary(project_model)

    project_model["symbol_table"] = symbol_table.to_dict()

    return project_model


def main():
    """
    Entry point of the Python KDM extractor.
    """

    if len(sys.argv) < 2:
        print("Usage: python main.py <python_project_path>")
        sys.exit(1)

    project_path = sys.argv[1]

    model = extract_project(project_path)

    write_json_model(model, "output/python_model.json")

    print("Model generated at output/python_model.json")


if __name__ == "__main__":
    main()
