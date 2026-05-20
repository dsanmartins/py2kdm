from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QSplitter, QTabWidget, QToolBar, QVBoxLayout, QWidget
from kdm_architecture_review.gui.graph_view import ArchitectureGraphView
from kdm_architecture_review.gui.properties_panel import PropertiesPanel
from kdm_architecture_review.gui.review_session import ReviewSession
from kdm_architecture_review.gui.validation_panel import ValidationPanel
from kdm_architecture_review.gui.ai_suggestions_panel import AISuggestionsPanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("py2kdm Architecture Review")
        self.session = ReviewSession()
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
        right = QSplitter(Qt.Orientation.Vertical); right.addWidget(self.properties_panel); right.addWidget(self.validation_panel); right.setSizes([420,420])
        main = QSplitter(Qt.Orientation.Horizontal); main.addWidget(self.left_tabs); main.addWidget(self.graph_view); main.addWidget(right); main.setSizes([280,760,360])
        container = QWidget(); layout = QVBoxLayout(container); layout.addWidget(main); self.setCentralWidget(container)
        self._toolbar(); self._signals()

    def _toolbar(self):
        tb = QToolBar("Main")
        self.addToolBar(tb)
        a_open = tb.addAction("Open proposal")
        a_validate = tb.addAction("Validate")
        a_export = tb.addAction("Export reviewed JSON")
        a_actions = tb.addAction("Export review actions")
        a_open.triggered.connect(self.open_proposal)
        a_validate.triggered.connect(self.validate_model)
        a_export.triggered.connect(self.export_reviewed)
        a_actions.triggered.connect(self.export_review_actions)

    def _signals(self):
        self.component_list.currentItemChanged.connect(self._component_selected)
        self.relationship_list.currentItemChanged.connect(self._relationship_selected)
        self.properties_panel.component_changed.connect(self._model_changed)
        self.properties_panel.relationship_changed.connect(self._model_changed)

    def open_proposal(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open architecture proposal JSON", "", "JSON files (*.json);;All files (*)")
        if not path: return
        try:
            self.session.load_proposal(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not load proposal:\n{exc}"); return
        self._refresh_all()
        self.statusBar().showMessage(f"Loaded: {path}")

    def export_reviewed(self):
        if not self.session.model:
            QMessageBox.warning(self, "No model", "Load a proposal first."); return
        report = self.session.validate()
        if report.get("summary", {}).get("forbidden", 0) > 0:
            ans = QMessageBox.question(self, "Forbidden findings", "The reviewed architecture has FORBIDDEN findings. Export anyway?")
            if ans != QMessageBox.StandardButton.Yes: return
        path, _ = QFileDialog.getSaveFileName(self, "Export reviewed architecture JSON", "", "JSON files (*.json);;All files (*)")
        if not path: return
        self.session.save_reviewed_architecture(path)
        self.statusBar().showMessage(f"Exported reviewed architecture: {path}")

    def export_review_actions(self):
        if not self.session.model:
            QMessageBox.warning(self, "No model", "Load a proposal first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export review actions JSON", "", "JSON files (*.json);;All files (*)")
        if not path: return
        self.session.save_review_actions(path)
        self.statusBar().showMessage(f"Exported review actions: {path}")

    def _refresh_all(self):
        self._refresh_lists()
        self.graph_view.render_model(self.session.model)
        self.ai_suggestions_panel.show_model(self.session.model)
        self.validate_model()

    def _refresh_lists(self):
        self.component_list.clear(); self.relationship_list.clear()
        for c in self.session.components:
            marker = "✓" if c.get("materialize", True) is not False else "✗"
            item = QListWidgetItem(f"{marker} {c.get('name','Component')} [{c.get('role','?')}]")
            item.setData(Qt.ItemDataRole.UserRole, c.get("id")); self.component_list.addItem(item)
        for r in self.session.relationships:
            marker = "✓" if r.get("materialize", True) is not False else "✗"
            item = QListWidgetItem(f"{marker} {r.get('type','relationship')} [{r.get('relationship_level','?')}]")
            item.setData(Qt.ItemDataRole.UserRole, r.get("id")); self.relationship_list.addItem(item)

    def _component_selected(self, current, previous):
        if current: self.properties_panel.show_component(current.data(Qt.ItemDataRole.UserRole))
    def _relationship_selected(self, current, previous):
        if current: self.properties_panel.show_relationship(current.data(Qt.ItemDataRole.UserRole))
    def _model_changed(self, _):
        self._refresh_lists(); self.graph_view.render_model(self.session.model); self.validate_model()
    def validate_model(self):
        report = self.session.validate(); self.validation_panel.show_report(report); return report
