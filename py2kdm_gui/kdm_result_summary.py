from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class KDMGenerationSummary:
    output_path: Path
    exists: bool
    size_bytes: int = 0
    validation_errors: int | None = None
    validation_warnings: int | None = None
    action_calls: int = 0
    runtime_call_labels: int = 0
    structure_components: int = 0
    structure_subsystems: int = 0
    structure_relationships: int = 0
    extension_families: int = 0

    @property
    def validation_status(self) -> str:
        if self.validation_errors is None and self.validation_warnings is None:
            return "unknown"

        if self.validation_errors == 0:
            return "OK"

        return "failed"

    def to_text(self) -> str:
        lines = []
        lines.append("KDM generation summary")
        lines.append("======================")
        lines.append("")
        lines.append(f"Output: {self.output_path}")
        lines.append(f"Exists: {self.exists}")
        lines.append(f"Size: {self.size_bytes} bytes")
        lines.append("")
        lines.append("Validation")
        lines.append("----------")
        lines.append(f"Status: {self.validation_status}")
        lines.append(f"Errors: {self._fmt(self.validation_errors)}")
        lines.append(f"Warnings: {self._fmt(self.validation_warnings)}")
        lines.append("")
        lines.append("Approximate KDM counters")
        lines.append("------------------------")
        lines.append(f"action:Calls: {self.action_calls}")
        lines.append(f"runtime_call labels: {self.runtime_call_labels}")
        lines.append(f"structure:Component: {self.structure_components}")
        lines.append(f"structure:Subsystem: {self.structure_subsystems}")
        lines.append(f"structure:StructureRelationship: {self.structure_relationships}")
        lines.append(f"extensionFamily: {self.extension_families}")

        return "\n".join(lines)

    def _fmt(self, value):
        return "unknown" if value is None else str(value)


def build_kdm_generation_summary(
    *,
    output_path: Path,
    command_output: str = "",
) -> KDMGenerationSummary:
    output_path = Path(output_path)
    exists = output_path.exists()

    summary = KDMGenerationSummary(
        output_path=output_path,
        exists=exists,
        size_bytes=output_path.stat().st_size if exists else 0,
    )

    summary.validation_errors = _extract_count(command_output, r"Errors:\s+(\d+)")
    summary.validation_warnings = _extract_count(command_output, r"Warnings:\s+(\d+)")

    if exists:
        text = output_path.read_text(encoding="utf-8", errors="replace")

        summary.action_calls = text.count('xsi:type="action:Calls"')
        summary.runtime_call_labels = text.count("runtime_call:")
        summary.structure_components = text.count('xsi:type="structure:Component"')
        summary.structure_subsystems = text.count('xsi:type="structure:Subsystem"')
        summary.structure_relationships = text.count(
            'xsi:type="structure:StructureRelationship"'
        )
        summary.extension_families = text.count("extensionFamily")

    return summary


def _extract_count(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text or "")

    if not match:
        return None

    try:
        return int(match.group(1))
    except Exception:
        return None
