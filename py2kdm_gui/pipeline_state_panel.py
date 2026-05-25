from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class PipelineStatePanel(QWidget):
    """
    Displays the state of the py2kdm process based on generated artifacts.

    The Path column shows expected paths, but explicitly marks them as EXISTS
    or MISSING to avoid confusion after cleaning outputs.
    """

    STEPS = [
        ("static_extraction", "Static extraction", "python_model.json"),
        (
            "dynamic_analysis",
            "Dynamic analysis",
            "python_model.runtime_enriched.combined.json",
        ),
        ("architecture_recovery", "Architecture recovery", None),
        ("pre_review_agents", "Pre-review agents", None),
        (
            "human_review",
            "Human review export",
            "python_model.reviewed_architecture.json",
        ),
        ("final_kdm", "Final KDM generation", "model.reviewed.kdm.xmi"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Step", "Status", "Artifact", "Path / Availability"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        layout.addWidget(self.table)

    def refresh(
        self,
        output_dir: Path,
        dynamic_enabled: bool,
    ) -> dict[str, str]:
        output_dir = Path(output_dir)
        state = self.compute_state(output_dir=output_dir, dynamic_enabled=dynamic_enabled)
        self._render_state(state)
        self.set_path_values(output_dir=output_dir, dynamic_enabled=dynamic_enabled)
        return state

    def compute_state(
        self,
        output_dir: Path,
        dynamic_enabled: bool,
    ) -> dict[str, str]:
        output_dir = Path(output_dir)

        artifacts = {
            "static_extraction": output_dir / "python_model.json",
            "dynamic_analysis": output_dir / "python_model.runtime_enriched.combined.json",
            "architecture_recovery_runtime": output_dir / "python_model.runtime_enriched.architecture.json",
            "architecture_recovery_static": output_dir / "python_model.architecture.json",
            "pre_review_runtime": output_dir / "python_model.runtime_enriched.ai_architecture.json",
            "pre_review_static": output_dir / "python_model.ai_architecture.json",
            "human_review": output_dir / "python_model.reviewed_architecture.json",
            "final_kdm": output_dir / "model.reviewed.kdm.xmi",
        }

        return {
            "static_extraction": "done" if artifacts["static_extraction"].exists() else "pending",
            "dynamic_analysis": self._dynamic_state(artifacts, dynamic_enabled),
            "architecture_recovery": self._first_existing_state(
                artifacts["architecture_recovery_runtime"],
                artifacts["architecture_recovery_static"],
            ),
            "pre_review_agents": self._first_existing_state(
                artifacts["pre_review_runtime"],
                artifacts["pre_review_static"],
            ),
            "human_review": "done" if artifacts["human_review"].exists() else "pending",
            "final_kdm": "done" if artifacts["final_kdm"].exists() else "pending",
        }

    def _dynamic_state(self, artifacts: dict[str, Path], dynamic_enabled: bool) -> str:
        if not dynamic_enabled:
            return "skipped"

        return "done" if artifacts["dynamic_analysis"].exists() else "pending"

    def _first_existing_state(self, *paths: Path) -> str:
        return "done" if any(path.exists() for path in paths) else "pending"

    def _artifact_for_step(self, output_dir: Path, step_id: str, dynamic_enabled: bool):
        output_dir = Path(output_dir)

        if step_id == "static_extraction":
            return output_dir / "python_model.json"

        if step_id == "dynamic_analysis":
            return output_dir / "python_model.runtime_enriched.combined.json"

        if step_id == "architecture_recovery":
            runtime_path = output_dir / "python_model.runtime_enriched.architecture.json"
            static_path = output_dir / "python_model.architecture.json"
            return runtime_path if runtime_path.exists() or dynamic_enabled else static_path

        if step_id == "pre_review_agents":
            runtime_path = output_dir / "python_model.runtime_enriched.ai_architecture.json"
            static_path = output_dir / "python_model.ai_architecture.json"
            return runtime_path if runtime_path.exists() or dynamic_enabled else static_path

        if step_id == "human_review":
            return output_dir / "python_model.reviewed_architecture.json"

        if step_id == "final_kdm":
            return output_dir / "model.reviewed.kdm.xmi"

        return None

    def _render_state(self, state: dict[str, str]):
        self.table.setRowCount(0)

        for step_id, label, artifact_name in self.STEPS:
            row = self.table.rowCount()
            self.table.insertRow(row)

            status = state.get(step_id, "pending")
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(status))
            self.table.setItem(row, 2, QTableWidgetItem(artifact_name or "runtime/static variant"))
            self.table.setItem(row, 3, QTableWidgetItem(""))

    def set_path_values(self, output_dir: Path, dynamic_enabled: bool):
        output_dir = Path(output_dir)

        for row, (step_id, _, _) in enumerate(self.STEPS):
            path = self._artifact_for_step(output_dir, step_id, dynamic_enabled)

            if path is not None:
                status = "EXISTS" if path.exists() else "MISSING"
                self.table.setItem(row, 3, QTableWidgetItem(f"{status}: {path}"))
