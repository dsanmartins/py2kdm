from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from py2kdm_gui.error_diagnostics import diagnose_pipeline_error


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PipelineController(QObject):
    """
    GUI-side orchestrator for the py2kdm process.

    This class does not reimplement extraction, dynamic analysis, architecture
    recovery, agents, or KDM generation. It delegates to the existing command
    line entry points and streams their output back to the GUI.
    """

    output_received = Signal(str)
    step_started = Signal(str)
    step_finished = Signal(str, bool)
    artifact_created = Signal(str, str)
    step_failed_diagnostic = Signal(str, str)
    step_succeeded_output = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self.current_step = None
        self.expected_artifact = None
        self.output_buffer = []

    def is_running(self) -> bool:
        return self.process is not None

    def run_static_extraction(
        self,
        project_root: Path,
        intermediate_json: Path,
    ) -> None:
        command = [
            sys.executable,
            str(PY2KDM_PROJECT_ROOT / "python_kdm_extractor" / "main.py"),
            "--input",
            str(project_root),
            "--output",
            str(intermediate_json),
        ]
        self._run(
            step_name="Static extraction",
            command=command,
            expected_artifact=("Intermediate JSON", intermediate_json),
        )

    def run_dynamic_trace_and_enrich(
        self,
        project_root: Path,
        script: str,
        input_json: Path,
        trace_output: Path,
        output_json: Path,
        scenario_name: str,
        mode: str = "desktop",
    ) -> None:
        command = [
            sys.executable,
            str(PY2KDM_PROJECT_ROOT / "kdm_dynamic_analysis" / "main.py"),
            "trace-and-enrich",
            "--project-root",
            str(project_root),
            "--script",
            script,
            "--input",
            str(input_json),
            "--trace-output",
            str(trace_output),
            "--output",
            str(output_json),
            "--scenario",
            scenario_name,
            "--mode",
            mode,
        ]
        self._run(
            step_name=f"Dynamic analysis: {scenario_name}",
            command=command,
            expected_artifact=("Runtime-enriched JSON", output_json),
        )

    def run_architecture_recovery(
        self,
        input_json: Path,
        architecture_json: Path,
    ) -> None:
        command = [
            sys.executable,
            str(PY2KDM_PROJECT_ROOT / "kdm_architecture_recovery" / "main.py"),
            "--input",
            str(input_json),
            "--output",
            str(architecture_json),
        ]
        self._run(
            step_name="Architecture recovery",
            command=command,
            expected_artifact=("Architecture JSON", architecture_json),
        )

    def run_pre_review_agents(
        self,
        input_json: Path,
        output_json: Path,
        llm_provider: str = "none",
        llm_model: str | None = None,
        llm_timeout: int = 300,
    ) -> None:
        command = [
            sys.executable,
            str(PY2KDM_PROJECT_ROOT / "kdm_architecture_agents" / "main.py"),
            "--mode",
            "pre-review",
            "--input",
            str(input_json),
            "--output",
            str(output_json),
            "--llm-provider",
            llm_provider,
            "--llm-timeout",
            str(llm_timeout),
        ]

        if llm_model:
            command.extend(["--llm-model", llm_model])

        self._run(
            step_name="Pre-review architecture agents",
            command=command,
            expected_artifact=("AI architecture JSON", output_json),
        )

    def run_kdm_generation(
        self,
        input_json: Path,
        output_xmi: Path,
        validate: bool = True,
    ) -> None:
        command = [
            sys.executable,
            str(PY2KDM_PROJECT_ROOT / "kdm_pyecore_generator" / "main.py"),
            "--input",
            str(input_json),
            "--output",
            str(output_xmi),
        ]

        if not validate:
            command.append("--no-validation")

        self._run(
            step_name="Final KDM generation",
            command=command,
            expected_artifact=("KDM XMI", output_xmi),
        )

    def _run(
        self,
        step_name: str,
        command: list[str],
        expected_artifact: tuple[str, Path] | None = None,
    ) -> None:
        if self.process is not None:
            raise RuntimeError(
                f"A pipeline command is already running: {self.current_step}"
            )

        self.current_step = step_name
        self.expected_artifact = expected_artifact
        self.output_buffer = []

        self.output_received.emit("$ " + " ".join(command))
        self.step_started.emit(step_name)

        process = QProcess(self)
        process.setWorkingDirectory(str(PY2KDM_PROJECT_ROOT))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._on_ready_read)
        process.finished.connect(self._on_finished)

        self.process = process
        process.start(command[0], command[1:])

    def _on_ready_read(self) -> None:
        if self.process is None:
            return

        data = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )

        if data:
            self.output_buffer.append(data.rstrip())
            self.output_received.emit(data.rstrip())

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        success = exit_code == 0
        step_name = self.current_step or "unknown"
        expected_artifact = self.expected_artifact

        if success and expected_artifact:
            label, path = expected_artifact

            if Path(path).exists():
                self.artifact_created.emit(label, str(path))

        self.output_received.emit(
            f"[{step_name}] finished with exit code {exit_code}"
        )

        if not success:
            diagnostic = diagnose_pipeline_error(
                step_name=step_name,
                output="\n".join(self.output_buffer),
                exit_code=exit_code,
            )
            self.step_failed_diagnostic.emit(step_name, diagnostic.to_text())
        else:
            self.step_succeeded_output.emit(
                step_name,
                "\n".join(self.output_buffer),
            )

        # Important: clear the running process state before emitting
        # step_finished. Some listeners immediately start the next queued step
        # or the next dynamic scenario inside the step_finished handler.
        # If self.process is still set at that moment, _run() will incorrectly
        # raise "A pipeline command is already running."
        self.process = None
        self.current_step = None
        self.expected_artifact = None

        self.step_finished.emit(step_name, success)


def summarize_json(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    structure_model = data.get("structure_model", {})
    runtime_enrichment = data.get("runtime_enrichment", {})
    ai_enrichment = data.get("ai_enrichment", {})

    return {
        "files": len(data.get("files", [])),
        "relationships": len(data.get("relationships", [])),
        "components": len(structure_model.get("components", [])),
        "subsystems": len(structure_model.get("subsystems", [])),
        "control_loops": len(structure_model.get("control_loops", [])),
        "structure_relationships": len(
            structure_model.get("structure_relationships", [])
        ),
        "runtime_enrichment": runtime_enrichment.get("summary", {}),
        "ai_enrichment": ai_enrichment.get("summary", {}),
    }
