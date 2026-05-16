import ast
from pathlib import Path

from extractor.python_ast_visitor import PythonASTVisitor


def extract_file_model(file_path: Path, project_root: Path):
    source_code = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code)

    visitor = PythonASTVisitor(file_path, project_root)
    visitor.visit(tree)

    return visitor.model
