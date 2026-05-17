import ast
from pathlib import Path

from extractor.python_ast_visitor import PythonASTVisitor


def extract_file_model(file_path: Path, project_root: Path):
    """
    Extracts the intermediate model for a single Python source file.

    This function is the file-level entry point of the extractor. It reads a
    Python file, parses it into a Python AST, applies PythonASTVisitor, and
    returns the JSON-compatible model produced by the visitor.

    Parameters
    ----------
    file_path:
        Absolute or project-relative path to the Python source file.

    project_root:
        Root directory of the analyzed Python project. It is used to compute
        relative file paths and qualified module names.

    Returns
    -------
    dict
        File-level intermediate model containing information such as imports,
        classes, functions, methods, calls, local variables and body statements.

    Raises
    ------
    SyntaxError
        If the Python file cannot be parsed.

    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    """

    source_code = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code)

    visitor = PythonASTVisitor(file_path, project_root)
    visitor.visit(tree)

    return visitor.model
