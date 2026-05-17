from pathlib import Path
import argparse

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


def extract_project(project_path: str):
    """
    Extracts the intermediate JSON model from a Python project.

    This function coordinates the complete extraction pipeline of the
    `python_kdm_extractor` subproject. It scans a Python project, extracts a
    per-file model, builds a symbol table, resolves imports and calls, enriches
    body statements with call information, builds project-level relationships
    and elements, and finally computes a summary.

    The output is not a KDM model yet. It is an intermediate JSON-compatible
    dictionary consumed later by `kdm_pyecore_generator`.

    Parameters
    ----------
    project_path:
        Path to the Python project that will be analyzed.

    Returns
    -------
    dict
        Intermediate project model with the following main sections:

        - projectName: name of the analyzed project.
        - language: source language, currently "python".
        - files: extracted models for each Python source file.
        - elements: normalized project-level elements.
        - relationships: project-level relationships.
        - symbol_table: serializable symbol table representation.
        - summary: aggregate information about the extracted project.
    """

    project_root = Path(project_path).resolve()

    if not project_root.exists():
        raise FileNotFoundError(f"Input project path does not exist: {project_root}")

    if not project_root.is_dir():
        raise NotADirectoryError(f"Input project path is not a directory: {project_root}")

    project_model = {
        "projectName": project_root.name,
        "language": "python",
        "files": [],
        "elements": [],
        "relationships": [],
        "symbol_table": {},
        "summary": {},
    }

    # ------------------------------------------------------------
    # 1. Scan Python files and extract file-level models
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # 2. Build symbol table
    # ------------------------------------------------------------

    symbol_table = SymbolTable()
    symbol_table.build_from_project_model(project_model)

    # ------------------------------------------------------------
    # 3. Resolve imports and calls
    # ------------------------------------------------------------

    import_resolver = ImportResolver(
        symbol_table,
        project_model["projectName"],
    )
    import_resolver.resolve_project_imports(project_model)

    call_resolver = CallResolver(symbol_table)
    call_resolver.resolve_project_calls(project_model)

    # ------------------------------------------------------------
    # 4. Synchronize body statements with call information
    # ------------------------------------------------------------

    body_call_synchronizer = BodyCallSynchronizer()
    body_call_synchronizer.sync_project_body_calls(project_model)

    # ------------------------------------------------------------
    # 5. Build project-level relationships and elements
    # ------------------------------------------------------------

    relationship_builder = RelationshipBuilder()
    relationship_builder.build_relationships(project_model)

    element_builder = ElementBuilder()
    element_builder.build_elements(project_model)

    # ------------------------------------------------------------
    # 6. Build project summary and serialize symbol table
    # ------------------------------------------------------------

    summary_builder = SummaryBuilder()
    summary_builder.build_summary(project_model)

    project_model["symbol_table"] = symbol_table.to_dict()

    return project_model


def write_project_model(model: dict, output_path: str):
    """
    Writes the extracted intermediate JSON model to disk.

    Parameters
    ----------
    model:
        Intermediate project model returned by extract_project.

    output_path:
        Path where the JSON model will be written.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    write_json_model(model, str(output_path))

    return output_path


def parse_args():
    """
    Parses command-line arguments for the extractor.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Extract an intermediate JSON model from a Python project. "
            "The generated JSON can be used as input by kdm_pyecore_generator."
        )
    )

    parser.add_argument(
        "project_path",
        nargs="?",
        help=(
            "Path to the Python project to analyze. "
            "Kept for backward compatibility. Prefer --input."
        ),
    )

    parser.add_argument(
        "--input",
        "-i",
        dest="input_path",
        help="Path to the Python project to analyze.",
    )

    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to the generated intermediate JSON file. Default: {DEFAULT_OUTPUT_PATH}",
    )

    return parser.parse_args()


def main():
    """
    Command-line entry point for the Python intermediate-model extractor.

    Examples
    --------
    Backward-compatible usage:

        python main.py path/to/python/project

    Preferred usage:

        python main.py --input path/to/python/project --output output/python_model.json

    The generated JSON file is intended to be consumed by the
    `kdm_pyecore_generator` subproject.
    """

    args = parse_args()

    project_path = args.input_path or args.project_path

    if not project_path:
        raise SystemExit(
            "Missing input project path. Use either:\n"
            "  python main.py path/to/python/project\n"
            "or:\n"
            "  python main.py --input path/to/python/project --output output/python_model.json"
        )

    model = extract_project(project_path)
    output_path = write_project_model(model, args.output)

    print(f"Model generated at {output_path}")
    print(f"Project name: {model.get('projectName')}")
    print(f"Python files analyzed: {len(model.get('files', []))}")
    print(f"Elements: {len(model.get('elements', []))}")
    print(f"Relationships: {len(model.get('relationships', []))}")


if __name__ == "__main__":
    main()
