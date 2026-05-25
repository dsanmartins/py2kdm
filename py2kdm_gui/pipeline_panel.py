from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py2kdm_gui.pipeline_controller import (
    PipelineController,
    PY2KDM_PROJECT_ROOT,
    summarize_json,
)
from py2kdm_gui.pipeline_state_panel import PipelineStatePanel
from py2kdm_gui.project_validator import validate_project_setup
from py2kdm_gui.project_config import (
    AgentConfig,
    DynamicAnalysisConfig,
    DynamicScenarioConfig,
    ProjectConfig,
    load_project_config,
    save_project_config,
)


class PipelinePanel(QWidget):
    """
    Full py2kdm process panel.

    The panel orchestrates the existing command-line modules:
    static extraction, optional dynamic analysis, architecture recovery,
    pre-review agents, human review handoff, and final KDM generation.
    """

    proposal_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.controller = PipelineController(self)
        self._auto_queue = []
        self.current_config_path: Path | None = None
        self.setup_mode = "manual"
        self.reviewed_architecture_path_override: Path | None = None
        self._build_ui()
        self._connect_signals()
        self._set_defaults()
        self.refresh_state()

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(self._project_group())
        layout.addWidget(self._dynamic_group())
        layout.addWidget(self._agents_group())
        layout.addWidget(self._actions_group())

        self.state_panel = PipelineStatePanel()
        layout.addWidget(self._state_group())

        self.setup_validation_report = QTextEdit()
        self.setup_validation_report.setReadOnly(True)
        self.setup_validation_report.setMaximumHeight(150)
        self.setup_validation_report.setPlaceholderText(
            "Press Validate setup to check project paths, scenarios and LLM settings."
        )
        layout.addWidget(self.setup_validation_report)

        self.summary_label = QLabel("No artifact summary loaded.")
        layout.addWidget(self.summary_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        layout.addWidget(self.log)

    def _project_group(self):
        group = QGroupBox("Project setup")
        layout = QGridLayout(group)

        self.project_root_edit = QLineEdit()
        self.output_dir_edit = QLineEdit()
        self.project_name_edit = QLineEdit()
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setReadOnly(True)

        self.manual_setup_radio = QRadioButton("Manual setup")
        self.config_setup_radio = QRadioButton("Config file")
        self.setup_mode_group = QButtonGroup(self)
        self.setup_mode_group.addButton(self.manual_setup_radio)
        self.setup_mode_group.addButton(self.config_setup_radio)
        self.manual_setup_radio.setChecked(True)

        self.browse_project_btn = QPushButton("Browse")
        self.browse_output_btn = QPushButton("Browse")
        self.load_config_btn = QPushButton("Load config")
        self.save_config_btn = QPushButton("Save config")
        self.save_config_as_btn = QPushButton("Save config as")

        layout.addWidget(QLabel("Project root"), 0, 0)
        layout.addWidget(self.project_root_edit, 0, 1)
        layout.addWidget(self.browse_project_btn, 0, 2)

        layout.addWidget(QLabel("Output directory"), 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.browse_output_btn, 1, 2)

        layout.addWidget(QLabel("Project name"), 2, 0)
        layout.addWidget(self.project_name_edit, 2, 1, 1, 2)

        layout.addWidget(QLabel("Config file"), 3, 0)
        layout.addWidget(self.config_path_edit, 3, 1)
        cfg_buttons = QHBoxLayout()
        cfg_buttons.addWidget(self.load_config_btn)
        cfg_buttons.addWidget(self.save_config_btn)
        cfg_buttons.addWidget(self.save_config_as_btn)
        layout.addLayout(cfg_buttons, 3, 2)

        mode_buttons = QHBoxLayout()
        mode_buttons.addWidget(self.manual_setup_radio)
        mode_buttons.addWidget(self.config_setup_radio)
        mode_buttons.addStretch(1)
        layout.addWidget(QLabel("Setup mode"), 4, 0)
        layout.addLayout(mode_buttons, 4, 1, 1, 2)

        return group

    def _dynamic_group(self):
        group = QGroupBox("Dynamic analysis scenarios")
        layout = QVBoxLayout(group)

        self.enable_dynamic_checkbox = QCheckBox("Enable dynamic analysis")
        self.enable_dynamic_checkbox.setChecked(True)
        layout.addWidget(self.enable_dynamic_checkbox)

        self.scenario_table = QTableWidget(0, 4)
        self.scenario_table.setHorizontalHeaderLabels(["Enabled", "Name", "Script", "Mode"])
        self.scenario_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        layout.addWidget(self.scenario_table)

        buttons = QHBoxLayout()
        self.add_scenario_btn = QPushButton("Add scenario")
        self.browse_scenario_btn = QPushButton("Browse script")
        self.remove_scenario_btn = QPushButton("Remove selected")
        self.add_pymape_defaults_btn = QPushButton("Add PyMAPE defaults")
        buttons.addWidget(self.add_scenario_btn)
        buttons.addWidget(self.browse_scenario_btn)
        buttons.addWidget(self.remove_scenario_btn)
        buttons.addWidget(self.add_pymape_defaults_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        return group

    def _agents_group(self):
        group = QGroupBox("Pre-review agents")
        form = QFormLayout(group)

        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.addItems(["none", "gemini", "ollama"])

        self.llm_model_edit = QLineEdit()
        self.llm_timeout_spin = QSpinBox()
        self.llm_timeout_spin.setRange(10, 5000)
        self.llm_timeout_spin.setValue(300)

        self.env_status_label = QLabel()

        form.addRow("LLM provider", self.llm_provider_combo)
        form.addRow("LLM model", self.llm_model_edit)
        form.addRow("LLM timeout", self.llm_timeout_spin)
        form.addRow("Gemini key", self.env_status_label)

        return group

    def _actions_group(self):
        group = QGroupBox("Pipeline actions")
        layout = QVBoxLayout(group)

        manual = QHBoxLayout()

        self.run_static_btn = QPushButton("1. Static extraction")
        self.run_dynamic_btn = QPushButton("2. Dynamic analysis")
        self.run_recovery_btn = QPushButton("3. Architecture recovery")
        self.run_agents_btn = QPushButton("4. Pre-review agents")
        self.load_review_btn = QPushButton("5. Load for review")
        self.generate_kdm_btn = QPushButton("6. Generate final KDM")

        for button in [
            self.run_static_btn,
            self.run_dynamic_btn,
            self.run_recovery_btn,
            self.run_agents_btn,
            self.load_review_btn,
            self.generate_kdm_btn,
        ]:
            manual.addWidget(button)

        layout.addLayout(manual)

        auto = QHBoxLayout()

        self.refresh_state_btn = QPushButton("Refresh state")
        self.validate_setup_btn = QPushButton("Validate setup")
        self.run_until_review_btn = QPushButton("Run until Human Review")
        self.run_pre_review_pipeline_btn = QPushButton("Run full pre-review pipeline")

        auto.addWidget(self.refresh_state_btn)
        auto.addWidget(self.validate_setup_btn)
        auto.addWidget(self.run_until_review_btn)
        auto.addWidget(self.run_pre_review_pipeline_btn)
        auto.addStretch(1)

        layout.addLayout(auto)

        return group

    def _state_group(self):
        group = QGroupBox("Pipeline state")
        layout = QVBoxLayout(group)
        layout.addWidget(self.state_panel)
        return group

    def _connect_signals(self):
        self.browse_project_btn.clicked.connect(self._browse_project)
        self.browse_output_btn.clicked.connect(self._browse_output)
        self.load_config_btn.clicked.connect(self.load_config)
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_as_btn.clicked.connect(self.save_config_as)
        self.manual_setup_radio.toggled.connect(
            lambda checked: self._set_setup_mode("manual") if checked else None
        )
        self.config_setup_radio.toggled.connect(
            lambda checked: self._set_setup_mode("config") if checked else None
        )

        self.add_scenario_btn.clicked.connect(self._add_scenario_dialog)
        self.browse_scenario_btn.clicked.connect(self._browse_scenario_script)
        self.remove_scenario_btn.clicked.connect(self._remove_selected_scenario)
        self.add_pymape_defaults_btn.clicked.connect(self._add_pymape_default_scenarios)

        self.run_static_btn.clicked.connect(self.run_static_extraction)
        self.run_dynamic_btn.clicked.connect(self.run_dynamic_analysis)
        self.run_recovery_btn.clicked.connect(self.run_architecture_recovery)
        self.run_agents_btn.clicked.connect(self.run_pre_review_agents)
        self.load_review_btn.clicked.connect(self.load_for_review)
        self.generate_kdm_btn.clicked.connect(self.generate_final_kdm)

        self.refresh_state_btn.clicked.connect(self.refresh_state)
        self.validate_setup_btn.clicked.connect(self.validate_setup)
        self.run_until_review_btn.clicked.connect(self.run_until_human_review)
        self.run_pre_review_pipeline_btn.clicked.connect(self.run_until_human_review)

        self.llm_provider_combo.currentTextChanged.connect(self._refresh_env_status)
        self.enable_dynamic_checkbox.stateChanged.connect(lambda _: self.refresh_state())
        self.output_dir_edit.textChanged.connect(lambda _: self.refresh_state())

        self.controller.output_received.connect(self._append_log)
        self.controller.step_started.connect(self._on_step_started)
        self.controller.step_finished.connect(self._on_step_finished)
        self.controller.artifact_created.connect(self._on_artifact_created)

    def _set_defaults(self):
        project_root = PY2KDM_PROJECT_ROOT / "examples" / "pymape_hierarchical"
        output_dir = PY2KDM_PROJECT_ROOT / "outputs" / "pymape_hierarchical"

        self.project_root_edit.setText(str(project_root))
        self.output_dir_edit.setText(str(output_dir))
        self.project_name_edit.setText("pymape_hierarchical")
        self.llm_provider_combo.setCurrentText("none")
        self.llm_model_edit.setText("gemini-2.5-flash-lite")
        self._add_pymape_default_scenarios()
        self._refresh_env_status()
        self._refresh_setup_mode()

    # ------------------------------------------------------------
    # Project config
    # ------------------------------------------------------------

    def _build_project_config(self) -> ProjectConfig:
        scenarios = []

        for enabled, name, script, mode in self._scenarios(include_disabled=True):
            scenarios.append(
                DynamicScenarioConfig(
                    name=name,
                    script=script,
                    mode=mode,
                    enabled=enabled,
                )
            )

        return ProjectConfig(
            name=self.project_name_edit.text().strip(),
            root=self.project_root_edit.text().strip(),
            output_dir=self.output_dir_edit.text().strip(),
            dynamic_analysis=DynamicAnalysisConfig(
                enabled=self.enable_dynamic_checkbox.isChecked(),
                scenarios=scenarios,
            ),
            agents=AgentConfig(
                llm_provider=self.llm_provider_combo.currentText(),
                llm_model=self.llm_model_edit.text().strip(),
                llm_timeout=self.llm_timeout_spin.value(),
            ),
        )

    def _apply_project_config(self, config: ProjectConfig):
        self.project_name_edit.setText(config.name)
        self.project_root_edit.setText(config.root)
        self.output_dir_edit.setText(config.output_dir)
        self.enable_dynamic_checkbox.setChecked(config.dynamic_analysis.enabled)

        self.scenario_table.setRowCount(0)

        for scenario in config.dynamic_analysis.scenarios:
            self._add_scenario_row(
                enabled=scenario.enabled,
                name=scenario.name,
                script=scenario.script,
                mode=scenario.mode,
            )

        self.llm_provider_combo.setCurrentText(config.agents.llm_provider)
        self.llm_model_edit.setText(config.agents.llm_model)
        self.llm_timeout_spin.setValue(config.agents.llm_timeout)

        self.refresh_state()

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load py2kdm project config",
            str(PY2KDM_PROJECT_ROOT / "configs"),
            "JSON files (*.json);;All files (*)",
        )

        if not path:
            return

        try:
            config = load_project_config(path)
            self._apply_project_config(config)
        except Exception as exc:
            QMessageBox.critical(self, "Load config failed", str(exc))
            return

        self.current_config_path = Path(path)
        self.config_path_edit.setText(str(self.current_config_path))
        self.config_setup_radio.setChecked(True)
        self._refresh_setup_mode()
        self._append_log(f"Loaded config: {self.current_config_path}")

    def save_config(self):
        if not self.current_config_path:
            self.save_config_as()
            return

        try:
            save_project_config(self._build_project_config(), self.current_config_path)
        except Exception as exc:
            QMessageBox.critical(self, "Save config failed", str(exc))
            return

        self._append_log(f"Saved config: {self.current_config_path}")

    def save_config_as(self):
        default_path = PY2KDM_PROJECT_ROOT / "configs" / f"{self.project_name_edit.text().strip() or 'project'}_gui.json"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save py2kdm project config",
            str(default_path),
            "JSON files (*.json);;All files (*)",
        )

        if not path:
            return

        self.current_config_path = Path(path)
        self.config_path_edit.setText(str(self.current_config_path))
        self.save_config()


    # ------------------------------------------------------------
    # Setup mode
    # ------------------------------------------------------------

    def _set_setup_mode(self, mode: str):
        self.setup_mode = mode
        self._refresh_setup_mode()
        self.refresh_state()

    def _is_setup_ready(self) -> bool:
        if self.setup_mode == "config":
            return self.current_config_path is not None
        return True

    def _refresh_setup_mode(self):
        # The project can be configured either manually or through a config file,
        # but not both at the same time.

        manual_mode = self.manual_setup_radio.isChecked()
        config_mode = self.config_setup_radio.isChecked()
        self.setup_mode = "config" if config_mode else "manual"

        manual_widgets = [
            self.project_root_edit,
            self.output_dir_edit,
            self.project_name_edit,
            self.browse_project_btn,
            self.browse_output_btn,
            self.enable_dynamic_checkbox,
            self.scenario_table,
            self.add_scenario_btn,
            self.browse_scenario_btn,
            self.remove_scenario_btn,
            self.add_pymape_defaults_btn,
            self.llm_provider_combo,
            self.llm_model_edit,
            self.llm_timeout_spin,
        ]

        for widget in manual_widgets:
            widget.setEnabled(manual_mode)

        self.load_config_btn.setEnabled(config_mode)
        self.save_config_btn.setEnabled(manual_mode)
        self.save_config_as_btn.setEnabled(manual_mode)

        if config_mode and self.current_config_path is None:
            self.config_path_edit.setPlaceholderText(
                "Select Load config before running the pipeline."
            )
        elif manual_mode:
            self.config_path_edit.setPlaceholderText(
                "Optional: use Save config as to persist this manual setup."
            )


    # ------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------

    @property
    def project_root(self) -> Path:
        return Path(self.project_root_edit.text()).expanduser().resolve()

    @property
    def output_dir(self) -> Path:
        return Path(self.output_dir_edit.text()).expanduser().resolve()

    @property
    def intermediate_json(self) -> Path:
        return self.output_dir / "python_model.json"

    @property
    def runtime_enriched_json(self) -> Path:
        return self.output_dir / "python_model.runtime_enriched.combined.json"

    @property
    def architecture_json(self) -> Path:
        if self.runtime_enriched_json.exists():
            return self.output_dir / "python_model.runtime_enriched.architecture.json"
        return self.output_dir / "python_model.architecture.json"

    @property
    def ai_architecture_json(self) -> Path:
        if self.runtime_enriched_json.exists():
            return self.output_dir / "python_model.runtime_enriched.ai_architecture.json"
        return self.output_dir / "python_model.ai_architecture.json"

    @property
    def reviewed_architecture_json(self) -> Path:
        if self.reviewed_architecture_path_override is not None:
            return self.reviewed_architecture_path_override
        return self.output_dir / "python_model.reviewed_architecture.json"

    @property
    def final_kdm_xmi(self) -> Path:
        return self.output_dir / "model.reviewed.kdm.xmi"

    def register_reviewed_architecture(self, path: str | Path):
        # Called by the Human Review tab after exporting the reviewed JSON.
        # This makes the Process tab immediately aware of the reviewed artifact,
        # even if the user saved it outside the default output directory.

        self.reviewed_architecture_path_override = Path(path).expanduser().resolve()
        self.generate_kdm_btn.setEnabled(self.reviewed_architecture_json.exists())
        self.refresh_state()

    def _browse_project(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Python project root",
            str(PY2KDM_PROJECT_ROOT),
        )
        if path:
            self.project_root_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            str(PY2KDM_PROJECT_ROOT / "outputs"),
        )
        if path:
            self.output_dir_edit.setText(path)

    # ------------------------------------------------------------
    # Scenario table
    # ------------------------------------------------------------

    def _add_scenario_row(
        self,
        enabled: bool = True,
        name: str = "scenario",
        script: str = "scenarios/scenario.py",
        mode: str = "desktop",
    ):
        row = self.scenario_table.rowCount()
        self.scenario_table.insertRow(row)

        enabled_item = QTableWidgetItem()
        enabled_item.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )

        self.scenario_table.setItem(row, 0, enabled_item)
        self.scenario_table.setItem(row, 1, QTableWidgetItem(name))
        self.scenario_table.setItem(row, 2, QTableWidgetItem(script))
        self.scenario_table.setItem(row, 3, QTableWidgetItem(mode))

    def _add_scenario_dialog(self):
        self._add_scenario_row()

    def _browse_scenario_script(self):
        row = self.scenario_table.currentRow()

        if row < 0:
            self._add_scenario_dialog()
            row = self.scenario_table.rowCount() - 1

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select scenario script",
            str(self.project_root / "scenarios"),
            "Python files (*.py);;All files (*)",
        )

        if not path:
            return

        script_path = Path(path)

        try:
            script_text = str(script_path.relative_to(self.project_root))
        except ValueError:
            script_text = str(script_path)

        self.scenario_table.setItem(row, 2, QTableWidgetItem(script_text))

        name_item = self.scenario_table.item(row, 1)
        if name_item is None or name_item.text() in {"scenario", ""}:
            name = script_path.stem
            if name.endswith("_scenario"):
                name = name[:-9]
            self.scenario_table.setItem(row, 1, QTableWidgetItem(name))

    def _add_pymape_default_scenarios(self):
        if self.scenario_table.rowCount() > 0:
            return

        defaults = [
            ("cruise_control", "scenarios/cruise_control_scenario.py", "desktop"),
            ("hold_distance", "scenarios/hold_distance_scenario.py", "desktop"),
        ]

        for name, script, mode in defaults:
            self._add_scenario_row(
                enabled=True,
                name=name,
                script=script,
                mode=mode,
            )

    def _remove_selected_scenario(self):
        row = self.scenario_table.currentRow()
        if row >= 0:
            self.scenario_table.removeRow(row)

    def _scenarios(self, include_disabled: bool = False):
        scenarios = []

        for row in range(self.scenario_table.rowCount()):
            enabled_item = self.scenario_table.item(row, 0)
            name_item = self.scenario_table.item(row, 1)
            script_item = self.scenario_table.item(row, 2)
            mode_item = self.scenario_table.item(row, 3)

            enabled = (
                enabled_item.checkState() == Qt.CheckState.Checked
                if enabled_item
                else True
            )
            name = name_item.text().strip() if name_item else ""
            script = script_item.text().strip() if script_item else ""
            mode = mode_item.text().strip() if mode_item else "desktop"

            if name and script and (include_disabled or enabled):
                scenarios.append((enabled, name, script, mode or "desktop"))

        return scenarios


    # ------------------------------------------------------------
    # Setup validation
    # ------------------------------------------------------------

    def validate_setup(self, show_message: bool = True) -> bool:
        report = validate_project_setup(
            setup_mode=getattr(self, "setup_mode", "manual"),
            config_path=self.current_config_path,
            project_root=self.project_root,
            output_dir=self.output_dir,
            dynamic_enabled=self.enable_dynamic_checkbox.isChecked(),
            scenarios=self._scenarios(include_disabled=True),
            llm_provider=self.llm_provider_combo.currentText(),
            llm_model=self.llm_model_edit.text().strip(),
        )

        self.setup_validation_report.setPlainText(report.to_text())

        if report.is_valid:
            if show_message:
                QMessageBox.information(
                    self,
                    "Project setup validation",
                    "Project setup is valid.",
                )
            return True

        if show_message:
            QMessageBox.warning(
                self,
                "Project setup validation failed",
                "Project setup has errors. See the validation report in the Process tab.",
            )

        return False


    # ------------------------------------------------------------
    # Pipeline actions
    # ------------------------------------------------------------

    def run_static_extraction(self):
        if not self.validate_setup(show_message=True):
            return

        self._ensure_output_dir()
        self.controller.run_static_extraction(
            project_root=self.project_root,
            intermediate_json=self.intermediate_json,
        )

    def run_dynamic_analysis(self):
        if not self.validate_setup(show_message=True):
            return

        if not self.enable_dynamic_checkbox.isChecked():
            QMessageBox.information(
                self,
                "Dynamic analysis disabled",
                "Enable dynamic analysis first.",
            )
            self._continue_auto_queue()
            return

        if not self.intermediate_json.exists():
            QMessageBox.warning(
                self,
                "Missing intermediate JSON",
                "Run static extraction first.",
            )
            return

        scenarios = self._scenarios()

        if not scenarios:
            QMessageBox.warning(
                self,
                "No scenarios",
                "Add at least one enabled dynamic scenario.",
            )
            return

        self._pending_dynamic_scenarios = [(name, script, mode) for _, name, script, mode in scenarios]
        self._current_dynamic_index = 0
        self._current_dynamic_input = self.intermediate_json
        self._run_next_dynamic_scenario()

    def _run_next_dynamic_scenario(self):
        if self._current_dynamic_index >= len(self._pending_dynamic_scenarios):
            self._append_log("Dynamic analysis completed for all scenarios.")
            self.refresh_state()
            self._update_summary(self.runtime_enriched_json)
            self._continue_auto_queue()
            return

        name, script, mode = self._pending_dynamic_scenarios[self._current_dynamic_index]
        is_last = self._current_dynamic_index == len(self._pending_dynamic_scenarios) - 1

        trace_output = self.output_dir / f"runtime_trace.{name}.json"
        output_json = (
            self.runtime_enriched_json
            if is_last
            else self.output_dir / f"python_model.runtime_enriched.{name}.json"
        )

        self._pending_dynamic_output = output_json

        self.controller.run_dynamic_trace_and_enrich(
            project_root=self.project_root,
            script=script,
            input_json=self._current_dynamic_input,
            trace_output=trace_output,
            output_json=output_json,
            scenario_name=name,
            mode=mode,
        )

    def run_architecture_recovery(self):
        if not self.validate_setup(show_message=True):
            return

        input_json = (
            self.runtime_enriched_json
            if self.runtime_enriched_json.exists()
            else self.intermediate_json
        )

        if not input_json.exists():
            QMessageBox.warning(
                self,
                "Missing input",
                "Run static extraction first, or run dynamic analysis first.",
            )
            return

        self.controller.run_architecture_recovery(
            input_json=input_json,
            architecture_json=self.architecture_json,
        )

    def run_pre_review_agents(self):
        if not self.validate_setup(show_message=True):
            return

        if not self.architecture_json.exists():
            QMessageBox.warning(
                self,
                "Missing architecture JSON",
                "Run architecture recovery first.",
            )
            return

        self.controller.run_pre_review_agents(
            input_json=self.architecture_json,
            output_json=self.ai_architecture_json,
            llm_provider=self.llm_provider_combo.currentText(),
            llm_model=self.llm_model_edit.text().strip() or None,
            llm_timeout=self.llm_timeout_spin.value(),
        )

    def load_for_review(self):
        input_json = (
            self.ai_architecture_json
            if self.ai_architecture_json.exists()
            else self.architecture_json
        )

        if not input_json.exists():
            QMessageBox.warning(
                self,
                "Missing architecture proposal",
                "Run architecture recovery or pre-review agents first.",
            )
            return

        self.proposal_ready.emit(str(input_json))

    def generate_final_kdm(self):
        input_json = self.reviewed_architecture_json

        if not input_json.exists():
            QMessageBox.warning(
                self,
                "Missing reviewed architecture",
                (
                    "Export the reviewed architecture JSON from the Human "
                    "Review tab first."
                ),
            )
            return

        self.controller.run_kdm_generation(
            input_json=input_json,
            output_xmi=self.final_kdm_xmi,
            validate=True,
        )

    # ------------------------------------------------------------
    # Automatic workflow
    # ------------------------------------------------------------

    def run_until_human_review(self):
        if not self.validate_setup(show_message=True):
            return

        if not self._is_setup_ready():
            QMessageBox.warning(
                self,
                "Project setup required",
                "Select or load a project setup first.",
            )
            return

        self._ensure_output_dir()
        self._auto_queue = []

        if not self.intermediate_json.exists():
            self._auto_queue.append("static")

        if self.enable_dynamic_checkbox.isChecked() and not self.runtime_enriched_json.exists():
            self._auto_queue.append("dynamic")

        if not self.architecture_json.exists():
            self._auto_queue.append("recovery")

        if not self.ai_architecture_json.exists():
            self._auto_queue.append("agents")

        self._auto_queue.append("load_review")

        self._append_log("Automatic workflow queued: " + " -> ".join(self._auto_queue))
        self._continue_auto_queue()

    def _continue_auto_queue(self):
        if not self._auto_queue:
            return

        next_step = self._auto_queue.pop(0)

        if next_step == "static":
            self.run_static_extraction()
        elif next_step == "dynamic":
            self.run_dynamic_analysis()
        elif next_step == "recovery":
            self.run_architecture_recovery()
        elif next_step == "agents":
            self.run_pre_review_agents()
        elif next_step == "load_review":
            self.load_for_review()

    # ------------------------------------------------------------
    # State
    # ------------------------------------------------------------

    def refresh_state(self):
        self._ensure_output_dir()
        state = self.state_panel.refresh(
            output_dir=self.output_dir,
            dynamic_enabled=self.enable_dynamic_checkbox.isChecked(),
        )
        self._update_button_state(state)
        self._refresh_env_status()

    def _update_button_state(self, state: dict[str, str]):
        if self.controller.is_running():
            return

        setup_ready = self._is_setup_ready()
        static_done = state.get("static_extraction") == "done"
        dynamic_done_or_skipped = state.get("dynamic_analysis") in {"done", "skipped"}
        recovery_done = state.get("architecture_recovery") == "done"
        agents_done = state.get("pre_review_agents") == "done"
        review_done = (
            state.get("human_review") == "done"
            or self.reviewed_architecture_json.exists()
        )

        self.run_static_btn.setEnabled(setup_ready)
        self.run_dynamic_btn.setEnabled(setup_ready and static_done)
        self.run_recovery_btn.setEnabled(setup_ready and static_done and dynamic_done_or_skipped)
        self.run_agents_btn.setEnabled(setup_ready and recovery_done)
        self.load_review_btn.setEnabled(setup_ready and (recovery_done or agents_done))
        self.generate_kdm_btn.setEnabled(setup_ready and review_done)
        self.run_until_review_btn.setEnabled(setup_ready)
        self.run_pre_review_pipeline_btn.setEnabled(setup_ready)

    # ------------------------------------------------------------
    # Controller feedback
    # ------------------------------------------------------------

    def _on_step_started(self, step_name: str):
        self._set_buttons_enabled(False)
        self._append_log(f"=== {step_name} ===")

    def _on_step_finished(self, step_name: str, success: bool):
        self._set_buttons_enabled(True)
        self.refresh_state()

        if step_name.startswith("Dynamic analysis:"):
            if success:
                self._current_dynamic_input = self._pending_dynamic_output
                self._current_dynamic_index += 1
                self._run_next_dynamic_scenario()
            else:
                self._auto_queue = []
            return

        if success:
            if step_name == "Static extraction":
                self._update_summary(self.intermediate_json)
            elif step_name == "Architecture recovery":
                self._update_summary(self.architecture_json)
            elif step_name == "Pre-review architecture agents":
                self._update_summary(self.ai_architecture_json)
            elif step_name == "Final KDM generation":
                self._append_log(f"Final KDM: {self.final_kdm_xmi}")

            self._continue_auto_queue()
        else:
            self._auto_queue = []
            QMessageBox.warning(
                self,
                "Pipeline step failed",
                f"{step_name} failed. See the log panel for details.",
            )

    def _on_artifact_created(self, label: str, path: str):
        self._append_log(f"{label}: {path}")

    def _append_log(self, text: str):
        self.log.appendPlainText(text)

    def _set_buttons_enabled(self, enabled: bool):
        for button in [
            self.run_static_btn,
            self.run_dynamic_btn,
            self.run_recovery_btn,
            self.run_agents_btn,
            self.load_review_btn,
            self.generate_kdm_btn,
            self.refresh_state_btn,
            self.validate_setup_btn,
            self.run_until_review_btn,
            self.run_pre_review_pipeline_btn,
            self.load_config_btn,
            self.save_config_btn,
            self.save_config_as_btn,
        ]:
            button.setEnabled(enabled)

        if enabled:
            self._refresh_setup_mode()

    def _ensure_output_dir(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _update_summary(self, path: Path):
        if not path.exists():
            return

        try:
            summary = summarize_json(path)
        except Exception as exc:
            self.summary_label.setText(f"Could not summarize {path}: {exc}")
            return

        self.summary_label.setText(
            "Artifact summary: "
            f"{path.name} | "
            f"files={summary.get('files')} | "
            f"relationships={summary.get('relationships')} | "
            f"components={summary.get('components')} | "
            f"loops={summary.get('control_loops')} | "
            f"ai={summary.get('ai_enrichment')}"
        )

    def _refresh_env_status(self):
        provider = self.llm_provider_combo.currentText()

        if provider != "gemini":
            self.env_status_label.setText("Not required")
            return

        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            self.env_status_label.setText("Detected")
        else:
            self.env_status_label.setText(
                "Not detected. Use .env or export GEMINI_API_KEY."
            )
