from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py2kdm_gui.artifact_panel import ArtifactPanel
from py2kdm_gui.pipeline_panel import PipelinePanel
from py2kdm_gui.review_widgets.ai_suggestions_panel import AISuggestionsPanel
from py2kdm_gui.review_widgets.graph_view import ArchitectureGraphView
from py2kdm_gui.review_widgets.properties_panel import PropertiesPanel
from py2kdm_gui.review_widgets.review_session import ReviewSession
from py2kdm_gui.review_widgets.review_export_summary import (
    ReviewExportSummaryDialog,
    build_review_export_summary,
)
from py2kdm_gui.review_widgets.traceability_panel import TraceabilityPanel
from py2kdm_gui.review_widgets.validation_panel import ValidationPanel


class MainWindow(QMainWindow):
    """
    Full py2kdm GUI.

    The Process tab orchestrates extraction, optional dynamic analysis,
    architecture recovery, pre-review agents and final KDM generation.
    The Human Review tab reuses architecture review widgets.

    Review-only actions are intentionally placed inside the Human Review tab
    instead of a global toolbar.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("py2kdm Workbench")
        self.session = ReviewSession()
        self.review_validated = False

        self.pipeline_panel = PipelinePanel()
        self.artifact_panel = ArtifactPanel()

        self.review_widget = self._build_review_widget()

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self.pipeline_panel.get_configuration_widget(), "Configuration")
        self.main_tabs.addTab(self.pipeline_panel, "Process")
        self.main_tabs.addTab(self.review_widget, "Human Review")
        self.main_tabs.addTab(self.artifact_panel, "Artifacts")

        self.setCentralWidget(self.main_tabs)
        self._signals()

    def _build_review_widget(self):
        self.component_list = QListWidget()
        self.relationship_list = QListWidget()
        self.ai_suggestions_panel = AISuggestionsPanel()

        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(self.component_list, "Components")
        self.left_tabs.addTab(self.relationship_list, "Relationships")
        self.left_tabs.addTab(self.ai_suggestions_panel, "AI Suggestions")

        self.graph_view = ArchitectureGraphView()
        self.properties_panel = PropertiesPanel(self.session)
        self.validation_panel = ValidationPanel()
        self.traceability_panel = TraceabilityPanel(self.session)

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.properties_panel)
        right.addWidget(self.validation_panel)
        right.addWidget(self.traceability_panel)
        right.setSizes([360, 260, 260])

        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(self.left_tabs)
        main.addWidget(self.graph_view)
        main.addWidget(right)
        main.setSizes([280, 760, 360])

        self.load_for_review_btn = QPushButton("Load for review")
        self.run_pre_review_btn = QPushButton("Pre-review agents")
        self.validate_btn = QPushButton("Validate")
        self.export_reviewed_btn = QPushButton("Export reviewed JSON")
        self.export_reviewed_btn.setEnabled(False)
        self.generate_reviewed_kdm_btn = QPushButton("Generate reviewed KDM")
        self.export_actions_btn = QPushButton("Export review actions")
        self.open_proposal_btn = QPushButton("Open proposal file")

        self.load_for_review_btn.setToolTip("Load the current architecture or AI architecture JSON into Human Review.")
        self.run_pre_review_btn.setToolTip("Run deterministic/LLM pre-review and load the AI architecture JSON for review.")
        self.open_proposal_btn.setToolTip("Open an architecture proposal JSON for human review.")
        self.validate_btn.setToolTip("Validate the current reviewed architecture. Export reviewed JSON is enabled only after validation.")
        self.export_reviewed_btn.setToolTip("Export is enabled after pressing Validate. If there are FORBIDDEN findings, the GUI asks for confirmation.")
        self.generate_reviewed_kdm_btn.setToolTip("Generate model.reviewed.kdm.xmi from the exported reviewed architecture JSON.")
        self.export_actions_btn.setToolTip("Export only the review decisions and overrides, not the full reviewed architecture.")

        self.review_busy_label = QLabel("Ready.")
        self.review_busy_label.setWordWrap(True)
        self.review_busy_bar = QProgressBar()
        self.review_busy_bar.setRange(0, 0)
        self.review_busy_bar.setVisible(False)
        self.review_busy_bar.setMaximumWidth(180)

        review_actions = QHBoxLayout()
        review_actions.addWidget(self.load_for_review_btn)
        review_actions.addWidget(self.run_pre_review_btn)
        review_actions.addWidget(self.validate_btn)
        review_actions.addWidget(self.export_reviewed_btn)
        review_actions.addWidget(self.generate_reviewed_kdm_btn)
        review_actions.addWidget(self.export_actions_btn)
        review_actions.addWidget(self.open_proposal_btn)
        review_actions.addWidget(self.review_busy_bar)
        review_actions.addWidget(self.review_busy_label)
        review_actions.addStretch(1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addLayout(review_actions)
        layout.addWidget(main)

        return container

    def _signals(self):
        self.load_for_review_btn.clicked.connect(self.load_current_for_review)
        self.run_pre_review_btn.clicked.connect(self.run_pre_review_and_load)
        self.open_proposal_btn.clicked.connect(self.open_proposal)
        self.validate_btn.clicked.connect(self.validate_model)
        self.export_reviewed_btn.clicked.connect(self.export_reviewed)
        self.generate_reviewed_kdm_btn.clicked.connect(self.pipeline_panel.generate_final_kdm)
        self.export_actions_btn.clicked.connect(self.export_review_actions)

        self.component_list.currentItemChanged.connect(self._component_selected)
        self.relationship_list.currentItemChanged.connect(self._relationship_selected)
        self.properties_panel.component_changed.connect(self._model_changed)
        self.properties_panel.relationship_changed.connect(self._model_changed)

        self.pipeline_panel.proposal_ready.connect(self.load_proposal_from_path)
        self.pipeline_panel.output_dir_edit.textChanged.connect(
            lambda text: self.artifact_panel.set_output_dir(text)
        )
        self.pipeline_panel.outputs_cleaned.connect(
            self._handle_outputs_cleaned
        )
        self.pipeline_panel.controller.step_started.connect(
            self._handle_pipeline_step_started
        )
        self.pipeline_panel.controller.step_finished.connect(
            self._handle_pipeline_step_finished
        )
        self.pipeline_panel.controller.step_succeeded_output.connect(
            self._handle_pipeline_step_success
        )
        self.artifact_panel.set_output_dir(self.pipeline_panel.output_dir_edit.text())
        self.ai_suggestions_panel.suggestion_action_requested.connect(
            self._handle_ai_suggestion_action
        )


    def _handle_ai_suggestion_action(self, action, suggestion_index):
        if not self.session.model:
            QMessageBox.warning(self, "No model", "Load a proposal first.")
            return

        if action == "accept":
            ok, message = self.session.apply_ai_suggestion(suggestion_index)
            if ok:
                self.statusBar().showMessage(
                    "Suggestion accepted and applied to the model. Press Validate before exporting."
                )
            else:
                self.session.set_ai_suggestion_decision(
                    suggestion_index,
                    decision="accepted",
                    status="user_accepted",
                    note=message,
                )
                self.statusBar().showMessage(
                    "Suggestion accepted. No structured change was applied. Press Validate before exporting."
                )
        elif action == "reject":
            self.session.set_ai_suggestion_decision(
                suggestion_index,
                decision="rejected",
                status="user_rejected",
            )
            self.statusBar().showMessage("AI suggestion rejected. Press Validate before exporting.")
        elif action == "reviewed":
            self.session.set_ai_suggestion_decision(
                suggestion_index,
                decision="reviewed",
                status="user_reviewed",
            )
            self.statusBar().showMessage("AI suggestion marked as reviewed. Press Validate before exporting.")
        else:
            return

        self.review_validated = False
        self.export_reviewed_btn.setEnabled(False)
        self._refresh_all(run_validation=False)

    def _handle_pipeline_step_started(self, step_name: str):
        if step_name in {"Pre-review architecture agents", "Final KDM generation"}:
            self._set_review_actions_enabled(False)
            self.review_busy_bar.setVisible(True)
            self.review_busy_label.setText(f"Running: {step_name}...")

    def _handle_pipeline_step_finished(self, step_name: str, success: bool):
        if step_name in {"Pre-review architecture agents", "Final KDM generation"}:
            self.review_busy_bar.setVisible(False)
            self.review_busy_label.setText(
                "Completed." if success else "Failed. See the Process log."
            )
            self._set_review_actions_enabled(True)

    def _set_review_actions_enabled(self, enabled: bool):
        for button in [
            self.load_for_review_btn,
            self.run_pre_review_btn,
            self.validate_btn,
            self.export_reviewed_btn,
            self.generate_reviewed_kdm_btn,
            self.export_actions_btn,
            self.open_proposal_btn,
        ]:
            button.setEnabled(enabled)

        if enabled:
            self.export_reviewed_btn.setEnabled(self.review_validated)

    def _handle_pipeline_step_success(self, step_name: str, command_output: str):
        if step_name == "Pre-review architecture agents":
            self.artifact_panel.refresh()
            if self.pipeline_panel.ai_architecture_json.exists():
                self.load_proposal_from_path(self.pipeline_panel.ai_architecture_json)
                self.statusBar().showMessage("Pre-review completed and loaded for human review.")
            return

        if step_name == "Final KDM generation":
            self.artifact_panel.refresh()
            self.statusBar().showMessage("KDM generated successfully.")

    def _handle_outputs_cleaned(self, output_dir: str):
        self.artifact_panel.set_output_dir(output_dir)
        self.artifact_panel.refresh()
        self.statusBar().showMessage(f"Outputs cleaned: {output_dir}")

    def load_current_for_review(self):
        input_json = (
            self.pipeline_panel.ai_architecture_json
            if self.pipeline_panel.ai_architecture_json.exists()
            else self.pipeline_panel.architecture_json
        )

        if not input_json.exists():
            QMessageBox.warning(
                self,
                "Missing architecture proposal",
                "Run Architecture recovery first, or run Pre-review agents.",
            )
            return

        self.load_proposal_from_path(input_json)

    def run_pre_review_and_load(self):
        self.pipeline_panel.run_pre_review_agents()

    def open_proposal(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open architecture proposal JSON",
            "",
            "JSON files (*.json);;All files (*)",
        )

        if not path:
            return

        self.load_proposal_from_path(path)

    def load_proposal_from_path(self, path):
        if self.session.model is not None:
            answer = QMessageBox.question(
                self,
                "Model already loaded",
                (
                    "A model is already loaded in Human Review. "
                    "Do you want to replace it with another proposal?"
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            self.session.load_proposal(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"Could not load proposal:\n{exc}",
            )
            return

        self.review_validated = False
        self.export_reviewed_btn.setEnabled(False)
        self._refresh_all(run_validation=False)
        self.main_tabs.setCurrentWidget(self.review_widget)
        self.statusBar().showMessage(f"Loaded: {path}. Press Validate before exporting.")

    def export_reviewed(self):
        if not self.session.model:
            QMessageBox.warning(self, "No model", "Load a proposal first.")
            return

        if not self.review_validated:
            QMessageBox.warning(
                self,
                "Validation required",
                "Press Validate before exporting the reviewed architecture.",
            )
            return

        report = self.session.validate()
        self.validation_panel.show_report(report)

        export_summary = build_review_export_summary(
            model=self.session.model,
            session=self.session,
            validation_report=report,
        )
        confirm_dialog = ReviewExportSummaryDialog(export_summary, self)

        if confirm_dialog.exec() != ReviewExportSummaryDialog.DialogCode.Accepted:
            return

        if report.get("summary", {}).get("forbidden", 0) > 0:
            ans = QMessageBox.question(
                self,
                "Forbidden findings",
                (
                    "The reviewed architecture has FORBIDDEN findings. "
                    "Export anyway?"
                ),
            )

            if ans != QMessageBox.StandardButton.Yes:
                return

        default_path = str(self.pipeline_panel.reviewed_architecture_json)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export reviewed architecture JSON",
            default_path,
            "JSON files (*.json);;All files (*)",
        )

        if not path:
            return

        self.session.save_reviewed_architecture(path)
        self.pipeline_panel.register_reviewed_architecture(path)
        self.artifact_panel.refresh()
        self.statusBar().showMessage(f"Exported reviewed architecture: {path}")

    def export_review_actions(self):
        if not self.session.model:
            QMessageBox.warning(self, "No model", "Load a proposal first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export review actions JSON",
            "",
            "JSON files (*.json);;All files (*)",
        )

        if not path:
            return

        self.session.save_review_actions(path)
        self.statusBar().showMessage(f"Exported review actions: {path}")

    def _refresh_all(self, run_validation=False):
        self._refresh_lists()
        self.graph_view.render_model(self.session.model)
        self.ai_suggestions_panel.show_model(self.session.model)
        if run_validation:
            self.validate_model()

    def _refresh_lists(self):
        self.component_list.clear()
        self.relationship_list.clear()

        for component in self.session.components:
            marker = "✓" if component.get("materialize", True) is not False else "✗"
            item = QListWidgetItem(
                f"{marker} {component.get('name', 'Component')} "
                f"[{component.get('role', '?')}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, component.get("id"))
            self.component_list.addItem(item)

        for relationship in self.session.relationships:
            marker = "✓" if relationship.get("materialize", True) is not False else "✗"
            item = QListWidgetItem(
                f"{marker} {relationship.get('type', 'relationship')} "
                f"[{relationship.get('relationship_level', '?')}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, relationship.get("id"))
            self.relationship_list.addItem(item)

    def _component_selected(self, current, previous):
        if current:
            component_id = current.data(Qt.ItemDataRole.UserRole)
            self.properties_panel.show_component(component_id)
            self.traceability_panel.show_component(component_id)

    def _relationship_selected(self, current, previous):
        if current:
            relationship_id = current.data(Qt.ItemDataRole.UserRole)
            self.properties_panel.show_relationship(relationship_id)
            self.traceability_panel.show_relationship(relationship_id)

    def _model_changed(self, _):
        self.review_validated = False
        self.export_reviewed_btn.setEnabled(False)
        self._refresh_lists()
        self.graph_view.render_model(self.session.model)
        self.ai_suggestions_panel.show_model(self.session.model)
        self.statusBar().showMessage("Model changed. Press Validate before exporting.")

    def validate_model(self):
        report = self.session.validate()
        self.validation_panel.show_report(report)
        self.review_validated = True
        self.export_reviewed_btn.setEnabled(True)
        self.statusBar().showMessage("Validation completed. Reviewed JSON can now be exported.")
        return report
