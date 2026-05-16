from pathlib import Path


IGNORED_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".git",
    ".mypy_cache",
    ".pytest_cache"
}


def find_python_files(project_root: Path):
    python_files = []

    for file_path in project_root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in file_path.parts):
            continue

        python_files.append(file_path)

    return python_files
