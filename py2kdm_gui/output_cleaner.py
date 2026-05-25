from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CleanOutputsResult:
    action: str
    output_dir: Path
    backup_dir: Path | None = None
    removed_files: int = 0
    removed_dirs: int = 0

    def to_text(self) -> str:
        lines = []
        lines.append(f"Action: {self.action}")
        lines.append(f"Output directory: {self.output_dir}")

        if self.backup_dir:
            lines.append(f"Backup directory: {self.backup_dir}")

        lines.append(f"Removed files: {self.removed_files}")
        lines.append(f"Removed directories: {self.removed_dirs}")

        return "\n".join(lines)


def backup_and_clean_output_dir(output_dir: Path) -> CleanOutputsResult:
    output_dir = Path(output_dir).expanduser().resolve()
    _assert_safe_output_dir(output_dir)

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return CleanOutputsResult(action="created_empty_output_dir", output_dir=output_dir)

    backup_dir = _backup_dir_for(output_dir)
    backup_dir.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(output_dir, backup_dir)
    removed_files, removed_dirs = _clean_contents(output_dir)

    return CleanOutputsResult(
        action="backup_and_clean",
        output_dir=output_dir,
        backup_dir=backup_dir,
        removed_files=removed_files,
        removed_dirs=removed_dirs,
    )


def clean_output_dir_without_backup(output_dir: Path) -> CleanOutputsResult:
    output_dir = Path(output_dir).expanduser().resolve()
    _assert_safe_output_dir(output_dir)

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return CleanOutputsResult(action="created_empty_output_dir", output_dir=output_dir)

    removed_files, removed_dirs = _clean_contents(output_dir)

    return CleanOutputsResult(
        action="clean_without_backup",
        output_dir=output_dir,
        removed_files=removed_files,
        removed_dirs=removed_dirs,
    )


def _clean_contents(output_dir: Path) -> tuple[int, int]:
    removed_files = 0
    removed_dirs = 0

    for child in output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
            removed_dirs += 1
        else:
            child.unlink()
            removed_files += 1

    return removed_files, removed_dirs


def _backup_dir_for(output_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir.with_name(f"{output_dir.name}_backup_{stamp}")


def _assert_safe_output_dir(output_dir: Path) -> None:
    if not output_dir:
        raise ValueError("Output directory is empty.")

    resolved = output_dir.resolve()

    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        Path.cwd().resolve(),
    }

    if resolved in forbidden:
        raise ValueError(f"Refusing to clean unsafe directory: {resolved}")

    if len(resolved.parts) < 3:
        raise ValueError(f"Refusing to clean very high-level directory: {resolved}")

    dangerous_names = {"src", "source", "project", "examples", "kdm_pyecore_generator"}
    if resolved.name in dangerous_names:
        raise ValueError(
            f"Refusing to clean directory with dangerous project-like name: {resolved}"
        )
