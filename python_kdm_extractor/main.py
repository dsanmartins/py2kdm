from pathlib import Path
import argparse
import sys


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_KDM_EXTRACTOR_ROOT = Path(__file__).resolve().parent

for candidate in (PY2KDM_PROJECT_ROOT, PYTHON_KDM_EXTRACTOR_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


from py2kdm_common.paths import ensure_parent, resolve_from_root

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


DEFAULT_OUTPUT_PATH = "output/python_model.json"


def extract_project(project_path: str | Path):
    """
    Extracts an intermediate JSON model from a Python project.
    """

    project_root = Path(project_path).resolve()

    project_model = {
        "projectName": project_root.name,
        "language": "python",
        "files": [],
        "elements": [],
        "relationships": [],
        "symbol_table": {},
        "summary": {},
    }

    python_files = find_python_files(project_root)

    for file_path in python_files:
        try:
            file_model = extract_file_model(file_path, project_root)
            project_model["files"].append(file_model)

        except SyntaxError as error:
            project_model["files"].append(
                {
                    "path": str(file_path.relative_to(project_root)),
                    "error": f"SyntaxError: {error}",
                }
            )

        except UnicodeDecodeError as error:
            project_model["files"].append(
                {
                    "path": str(file_path.relative_to(project_root)),
                    "error": f"UnicodeDecodeError: {error}",
                }
            )

    symbol_table = SymbolTable()
    symbol_table.build_from_project_model(project_model)

    import_resolver = ImportResolver(
        symbol_table,
        project_model["projectName"],
    )
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract an intermediate JSON model from a Python project."
    )

    # Positional path is kept for backward compatibility:
    #   python python_kdm_extractor/main.py examples/my_project
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Python project path. Kept for backward compatibility.",
    )

    parser.add_argument(
        "--input",
        dest="input_path",
        help="Python project path. Preferred explicit form.",
    )

    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output JSON path. Default: {DEFAULT_OUTPUT_PATH}",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    input_path = args.input_path or args.project_path

    if not input_path:
        raise SystemExit(
            "Missing input project path. Use --input <path> or positional <path>."
        )

    project_path = resolve_from_root(input_path)
    output_path = ensure_parent(resolve_from_root(args.output))

    model = extract_project(project_path)

    write_json_model(model, str(output_path))

    summary = model.get("summary", {})

    print(f"Model generated at {output_path}")
    print(f"Project name: {model.get('projectName')}")
    print(f"Python files analyzed: {summary.get('python_files', len(model.get('files', [])))}")
    print(f"Elements: {len(model.get('elements', []))}")
    print(f"Relationships: {len(model.get('relationships', []))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
