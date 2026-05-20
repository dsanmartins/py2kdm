from pathlib import Path


def find_project_root(start: str | Path | None = None) -> Path:
    current = Path(start or __file__).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (
            (candidate / "run_pipeline.py").exists()
            and (candidate / "kdm_pyecore_generator").exists()
            and (candidate / "python_kdm_extractor").exists()
        ):
            return candidate

    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = find_project_root()


def resolve_from_root(path: str | Path | None) -> Path | None:
    if path is None:
        return None

    path = Path(path)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def ensure_parent(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
