from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class ValidationFinding:
    severity: str
    field: str
    message: str
    suggestion: str = ""


@dataclass
class ProjectSetupValidationReport:
    status: str
    findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [finding for finding in self.findings if finding.severity == "warning"]

    @property
    def infos(self) -> list[ValidationFinding]:
        return [finding for finding in self.findings if finding.severity == "info"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_text(self) -> str:
        lines = []
        lines.append(f"Project setup validation: {self.status}")
        lines.append(f"errors: {len(self.errors)}")
        lines.append(f"warnings: {len(self.warnings)}")
        lines.append(f"info: {len(self.infos)}")
        lines.append("")

        if not self.findings:
            lines.append("No findings.")
            return "\n".join(lines)

        for finding in self.findings:
            lines.append(f"[{finding.severity.upper()}] {finding.field}")
            lines.append(f"  {finding.message}")
            if finding.suggestion:
                lines.append(f"  suggestion: {finding.suggestion}")
            lines.append("")

        return "\n".join(lines).rstrip()


def validate_project_setup(
    *,
    setup_mode: str,
    config_path: Path | None,
    project_root: Path,
    output_dir: Path,
    dynamic_enabled: bool,
    scenarios: Iterable[tuple[bool, str, str, str]],
    llm_provider: str,
    llm_model: str,
) -> ProjectSetupValidationReport:
    findings: list[ValidationFinding] = []

    _validate_setup_mode(
        findings=findings,
        setup_mode=setup_mode,
        config_path=config_path,
    )

    _validate_project_paths(
        findings=findings,
        project_root=project_root,
        output_dir=output_dir,
    )

    _validate_dynamic_scenarios(
        findings=findings,
        project_root=project_root,
        dynamic_enabled=dynamic_enabled,
        scenarios=list(scenarios),
    )

    _validate_llm(
        findings=findings,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )

    status = "valid" if not any(f.severity == "error" for f in findings) else "invalid"
    return ProjectSetupValidationReport(status=status, findings=findings)


def _validate_setup_mode(
    *,
    findings: list[ValidationFinding],
    setup_mode: str,
    config_path: Path | None,
):
    if setup_mode not in {"manual", "config"}:
        findings.append(
            ValidationFinding(
                severity="error",
                field="setup_mode",
                message=f"Unsupported setup mode: {setup_mode}",
                suggestion="Use either manual or config mode.",
            )
        )
        return

    if setup_mode == "config":
        if config_path is None:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field="config_path",
                    message="Config-file mode is active, but no config file has been loaded.",
                    suggestion="Click Load config or switch to Manual setup.",
                )
            )
        elif not Path(config_path).exists():
            findings.append(
                ValidationFinding(
                    severity="error",
                    field="config_path",
                    message=f"Config file does not exist: {config_path}",
                    suggestion="Load an existing config file.",
                )
            )


def _validate_project_paths(
    *,
    findings: list[ValidationFinding],
    project_root: Path,
    output_dir: Path,
):
    if not str(project_root).strip():
        findings.append(
            ValidationFinding(
                severity="error",
                field="project_root",
                message="Project root is empty.",
                suggestion="Select the Python project root.",
            )
        )
    elif not project_root.exists():
        findings.append(
            ValidationFinding(
                severity="error",
                field="project_root",
                message=f"Project root does not exist: {project_root}",
                suggestion="Select an existing project directory.",
            )
        )
    elif not project_root.is_dir():
        findings.append(
            ValidationFinding(
                severity="error",
                field="project_root",
                message=f"Project root is not a directory: {project_root}",
                suggestion="Select a directory.",
            )
        )

    if not str(output_dir).strip():
        findings.append(
            ValidationFinding(
                severity="error",
                field="output_dir",
                message="Output directory is empty.",
                suggestion="Select or define an output directory.",
            )
        )
        return

    if output_dir.exists() and not output_dir.is_dir():
        findings.append(
            ValidationFinding(
                severity="error",
                field="output_dir",
                message=f"Output path exists but is not a directory: {output_dir}",
                suggestion="Choose another output directory.",
            )
        )
        return

    if not output_dir.exists():
        parent = output_dir.parent
        if not parent.exists():
            findings.append(
                ValidationFinding(
                    severity="error",
                    field="output_dir",
                    message=f"Output directory parent does not exist: {parent}",
                    suggestion="Choose an output directory whose parent exists.",
                )
            )
        else:
            findings.append(
                ValidationFinding(
                    severity="info",
                    field="output_dir",
                    message=f"Output directory will be created: {output_dir}",
                )
            )


def _validate_dynamic_scenarios(
    *,
    findings: list[ValidationFinding],
    project_root: Path,
    dynamic_enabled: bool,
    scenarios: list[tuple[bool, str, str, str]],
):
    if not dynamic_enabled:
        findings.append(
            ValidationFinding(
                severity="info",
                field="dynamic_analysis",
                message="Dynamic analysis is disabled.",
            )
        )
        return

    enabled_scenarios = [scenario for scenario in scenarios if scenario[0]]

    if not enabled_scenarios:
        findings.append(
            ValidationFinding(
                severity="error",
                field="dynamic_scenarios",
                message="Dynamic analysis is enabled, but no scenario is enabled.",
                suggestion="Enable at least one scenario or disable dynamic analysis.",
            )
        )
        return

    allowed_modes = {"desktop", "web"}

    seen_names = set()

    for enabled, name, script, mode in enabled_scenarios:
        if not name:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field="dynamic_scenarios.name",
                    message="A scenario has an empty name.",
                    suggestion="Provide a non-empty scenario name.",
                )
            )
        elif name in seen_names:
            findings.append(
                ValidationFinding(
                    severity="warning",
                    field=f"dynamic_scenarios.{name}",
                    message=f"Scenario name is duplicated: {name}",
                    suggestion="Use unique scenario names to avoid overwritten trace files.",
                )
            )
        else:
            seen_names.add(name)

        if not script:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"dynamic_scenarios.{name}.script",
                    message=f"Scenario '{name}' has an empty script path.",
                    suggestion="Select a scenario script.",
                )
            )
            continue

        script_path = Path(script)
        if not script_path.is_absolute():
            script_path = project_root / script_path

        if not script_path.exists():
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"dynamic_scenarios.{name}.script",
                    message=f"Scenario script does not exist: {script_path}",
                    suggestion="Fix the script path or browse for the correct file.",
                )
            )
        elif not script_path.is_file():
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"dynamic_scenarios.{name}.script",
                    message=f"Scenario path is not a file: {script_path}",
                    suggestion="Select a Python script.",
                )
            )
        elif script_path.suffix != ".py":
            findings.append(
                ValidationFinding(
                    severity="warning",
                    field=f"dynamic_scenarios.{name}.script",
                    message=f"Scenario script does not have .py extension: {script_path}",
                    suggestion="Use a Python scenario script.",
                )
            )

        if mode not in allowed_modes:
            findings.append(
                ValidationFinding(
                    severity="error",
                    field=f"dynamic_scenarios.{name}.mode",
                    message=f"Unsupported scenario mode: {mode}",
                    suggestion="Use desktop or web.",
                )
            )


def _validate_llm(
    *,
    findings: list[ValidationFinding],
    llm_provider: str,
    llm_model: str,
):
    provider = (llm_provider or "none").strip().lower()

    if provider == "none":
        findings.append(
            ValidationFinding(
                severity="info",
                field="agents.llm_provider",
                message="LLM provider is disabled. Only deterministic pre-review agents will run.",
            )
        )
        return

    if not llm_model:
        findings.append(
            ValidationFinding(
                severity="warning",
                field="agents.llm_model",
                message="LLM provider is enabled, but no model is specified.",
                suggestion="Specify a model or set provider to none.",
            )
        )

    if provider == "gemini":
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    field="agents.gemini_api_key",
                    message="Gemini provider is selected, but GEMINI_API_KEY/GOOGLE_API_KEY was not detected in the environment.",
                    suggestion="Set GEMINI_API_KEY in .env or in the shell before launching the GUI.",
                )
            )
        return

    if provider == "ollama":
        findings.append(
            ValidationFinding(
                severity="info",
                field="agents.ollama",
                message="Ollama provider selected. The GUI cannot verify here whether the local Ollama server is running.",
                suggestion="Make sure Ollama is running before executing pre-review agents.",
            )
        )
        return

    findings.append(
        ValidationFinding(
            severity="error",
            field="agents.llm_provider",
            message=f"Unsupported LLM provider: {llm_provider}",
            suggestion="Use none, gemini or ollama.",
        )
    )
