from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ErrorDiagnostic:
    title: str
    reason: str
    suggestion: str
    details: str = ""

    def to_text(self) -> str:
        lines = [self.title]

        if self.reason:
            lines.extend(["", "Reason:", f"  {self.reason}"])

        if self.suggestion:
            lines.extend(["", "Suggested fix:", f"  {self.suggestion}"])

        if self.details:
            lines.extend(["", "Details:", self.details.strip()])

        return "\n".join(lines)


def diagnose_pipeline_error(step_name: str, output: str, exit_code: int | None = None) -> ErrorDiagnostic:
    output = output or ""
    title = f"Step failed: {step_name}"

    for diagnostic_builder in [
        _diagnose_module_not_found,
        _diagnose_file_not_found,
        _diagnose_json_error,
        _diagnose_kdm_validation,
        _diagnose_import_error,
        _diagnose_qt_error,
    ]:
        diagnostic = diagnostic_builder(step_name, output)
        if diagnostic:
            diagnostic.title = title
            return diagnostic

    return ErrorDiagnostic(
        title=title,
        reason=f"The command exited with code {exit_code}.",
        suggestion="Inspect the log panel for the complete traceback.",
        details=_tail(output),
    )


def _diagnose_module_not_found(step_name: str, output: str) -> ErrorDiagnostic | None:
    match = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", output)
    if not match:
        return None

    module = match.group(1)
    package_hint = _package_hint(module.split(".")[0])
    return ErrorDiagnostic(
        title="",
        reason=f"Missing Python module: {module}",
        suggestion=(
            f"Install the missing dependency, for example: pip install {package_hint}. "
            "If this dependency is optional infrastructure, add a scenario shim or disable "
            "the execution path that requires it."
        ),
        details=_tail(output),
    )


def _diagnose_import_error(step_name: str, output: str) -> ErrorDiagnostic | None:
    match = re.search(r"ImportError:\s+(.*)", output)
    if not match:
        return None

    return ErrorDiagnostic(
        title="",
        reason=match.group(1).strip(),
        suggestion="Check project imports, sys.path setup in the scenario, and package versions.",
        details=_tail(output),
    )


def _diagnose_file_not_found(step_name: str, output: str) -> ErrorDiagnostic | None:
    match = re.search(r"FileNotFoundError:\s+\[Errno 2\].*?['\"]([^'\"]+)['\"]", output)
    if not match:
        match = re.search(r"No such file or directory:\s+['\"]([^'\"]+)['\"]", output)
    if not match:
        return None

    path = match.group(1)
    return ErrorDiagnostic(
        title="",
        reason=f"File or directory not found: {path}",
        suggestion=(
            "Check the configured project root, input JSON, scenario script path, "
            "and output directory."
        ),
        details=_tail(output),
    )


def _diagnose_json_error(step_name: str, output: str) -> ErrorDiagnostic | None:
    for pattern in [r"json\.decoder\.JSONDecodeError:\s+(.*)", r"JSONDecodeError:\s+(.*)"]:
        match = re.search(pattern, output)
        if match:
            return ErrorDiagnostic(
                title="",
                reason=match.group(1).strip(),
                suggestion=(
                    "The input JSON appears to be invalid or incomplete. Regenerate the previous "
                    "pipeline artifact and check that the command finished successfully."
                ),
                details=_tail(output),
            )
    return None


def _diagnose_kdm_validation(step_name: str, output: str) -> ErrorDiagnostic | None:
    if "KDM validation failed" not in output and "VALIDATION REPORT" not in output:
        return None

    errors = _extract_count(output, r"Errors:\s+(\d+)")
    warnings = _extract_count(output, r"Warnings:\s+(\d+)")

    reason_parts = []
    if errors is not None:
        reason_parts.append(f"errors={errors}")
    if warnings is not None:
        reason_parts.append(f"warnings={warnings}")

    reason = "KDM validation failed."
    if reason_parts:
        reason += " " + ", ".join(reason_parts)

    return ErrorDiagnostic(
        title="",
        reason=reason,
        suggestion=(
            "Inspect the validation report above the traceback. Common causes are unresolved "
            "references, missing containment, invalid KDM relation endpoints, or duplicated IDs."
        ),
        details=_tail(output),
    )


def _diagnose_qt_error(step_name: str, output: str) -> ErrorDiagnostic | None:
    if "PySide6" not in output and "Qt" not in output:
        return None

    if "setCheckState" in output and "wrong argument types" in output:
        return ErrorDiagnostic(
            title="",
            reason="Qt received an invalid CheckState argument.",
            suggestion="Use Qt.CheckState.Checked or Qt.CheckState.Unchecked instead of raw integers.",
            details=_tail(output),
        )

    return None


def _extract_count(output: str, pattern: str) -> int | None:
    match = re.search(pattern, output)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _package_hint(module: str) -> str:
    mapping = {
        "simple_pid": "simple-pid",
        "PIL": "pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "yaml": "pyyaml",
        "dotenv": "python-dotenv",
        "bs4": "beautifulsoup4",
        "aiohttp": "aiohttp",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "aioredis": "aioredis",
        "redis": "redis",
        "purse": "purse",
    }
    return mapping.get(module, module)


def _tail(text: str, max_lines: int = 35) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])
