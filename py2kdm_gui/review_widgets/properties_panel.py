from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

COMPONENT_ROLES = [
    "Monitor",
    "Analyzer",
    "Planner",
    "Executor",
    "Knowledge",
    "LoopManager",
    "Loop",
    "ReferenceInput",
    "MeasuredOutput",
    "Sensor",
    "Effector",
]

RELATIONSHIP_TYPES = [
    "contains",
    "mapek_flow",
    "uses_knowledge",
    "subscribes_to",
    "acts_through",
    "observes_through",
    "observes",
    "produces_measurement",
    "uses_reference_input",
    "evaluates_measured_output",
    "depends_on",
    "controls",
    "updates",
]

RELATIONSHIP_LEVELS = ["architectural", "technical"]


class PropertiesPanel(QWidget):
    component_changed = Signal(str)
    relationship_changed = Signal(str)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.current_component_id = None
        self.current_relationship_id = None
        self._updating = False

        layout = QVBoxLayout(self)

        # --------------------------------------------------------
        # Component properties
        # --------------------------------------------------------

        self.component_group = QGroupBox("Component properties")
        cl = QFormLayout(self.component_group)

        self.component_id = QLabel("-")
        self.component_id.setWordWrap(True)

        self.component_name = QLineEdit()

        self.component_role = QComboBox()
        self.component_role.addItems(COMPONENT_ROLES)

        self.component_materialize = QCheckBox("Materialize in KDM")

        self.component_impl = QLabel("-")
        self.component_impl.setWordWrap(True)

        self.component_code_kind = QLabel("-")
        self.component_code_kind.setWordWrap(True)

        self.component_code_ids = QLabel("-")
        self.component_code_ids.setWordWrap(True)

        self.component_code_qn = QLabel("-")
        self.component_code_qn.setWordWrap(True)

        self.component_code_container = QLabel("-")
        self.component_code_container.setWordWrap(True)

        self.component_reason = QTextEdit()
        self.component_reason.setMaximumHeight(70)

        cl.addRow("ID:", self.component_id)
        cl.addRow("Name:", self.component_name)
        cl.addRow("Role:", self.component_role)
        cl.addRow("", self.component_materialize)
        cl.addRow("Implementation:", self.component_impl)

        cl.addRow("Code element kind:", self.component_code_kind)
        cl.addRow("Code element ID:", self.component_code_ids)
        cl.addRow("Qualified name:", self.component_code_qn)
        cl.addRow("Container:", self.component_code_container)

        cl.addRow("Reason:", self.component_reason)

        # --------------------------------------------------------
        # Relationship properties
        # --------------------------------------------------------

        self.relationship_group = QGroupBox("Relationship properties")
        rl = QFormLayout(self.relationship_group)

        self.relationship_id = QLabel("-")
        self.relationship_id.setWordWrap(True)

        self.relationship_type = QComboBox()
        self.relationship_type.addItems(RELATIONSHIP_TYPES)

        self.relationship_level = QComboBox()
        self.relationship_level.addItems(RELATIONSHIP_LEVELS)

        self.relationship_materialize = QCheckBox("Materialize in KDM")

        self.relationship_endpoints = QLabel("-")
        self.relationship_endpoints.setWordWrap(True)

        rl.addRow("ID:", self.relationship_id)
        rl.addRow("Type:", self.relationship_type)
        rl.addRow("Level:", self.relationship_level)
        rl.addRow("", self.relationship_materialize)
        rl.addRow("Endpoints:", self.relationship_endpoints)

        layout.addWidget(self.component_group)
        layout.addWidget(self.relationship_group)
        layout.addStretch()

        self.component_name.editingFinished.connect(
            self._component_name_changed
        )
        self.component_role.currentTextChanged.connect(
            self._component_role_changed
        )
        self.component_materialize.toggled.connect(
            self._component_materialize_changed
        )
        self.component_reason.textChanged.connect(
            self._component_reason_changed
        )

        self.relationship_type.currentTextChanged.connect(
            self._relationship_type_changed
        )
        self.relationship_level.currentTextChanged.connect(
            self._relationship_level_changed
        )
        self.relationship_materialize.toggled.connect(
            self._relationship_materialize_changed
        )

    def show_component(self, cid):
        c = self.session.get_component(cid)

        if not c:
            return

        self._updating = True

        self.current_component_id = cid
        self.current_relationship_id = None

        self.component_id.setText(c.get("id", "-"))
        self.component_name.setText(c.get("name", ""))
        self.component_role.setCurrentText(c.get("role", "Monitor"))
        self.component_materialize.setChecked(
            c.get("materialize", True) is not False
        )
        self.component_impl.setText(
            "\n".join(c.get("implemented_by", [])) or "-"
        )

        self._show_code_traceability(cid)

        self.component_reason.setPlainText(c.get("review_reason", ""))

        self._updating = False

    def show_relationship(self, rid):
        r = self.session.get_relationship(rid)

        if not r and hasattr(self.session, "get_containment_relationship"):
            r = self.session.get_containment_relationship(rid)

        if not r:
            return

        self._updating = True

        self.current_relationship_id = rid
        self.current_component_id = None

        self.relationship_id.setText(r.get("id", "-"))
        self.relationship_type.setCurrentText(r.get("type", "mapek_flow"))
        self.relationship_level.setCurrentText(
            r.get("relationship_level", "architectural")
        )
        self.relationship_materialize.setChecked(
            r.get("materialize", True) is not False
        )
        self.relationship_endpoints.setText(
            f"{r.get('source', '-')}\n→ {r.get('target', '-')}"
        )

        self._updating = False

    def _show_code_traceability(self, component_id):
        if not hasattr(self.session, "get_component_code_traceability"):
            self.component_code_kind.setText("-")
            self.component_code_ids.setText("-")
            self.component_code_qn.setText("-")
            self.component_code_container.setText("-")
            return

        trace = self.session.get_component_code_traceability(component_id)

        self.component_code_kind.setText(trace.get("kind") or "-")
        self.component_code_ids.setText(
            "\n".join(trace.get("ids", [])) or "-"
        )
        self.component_code_qn.setText(
            "\n".join(trace.get("qualified_names", [])) or "-"
        )
        self.component_code_container.setText(
            "\n".join(trace.get("containers", [])) or "-"
        )

    def _component_name_changed(self):
        if not self._updating and self.current_component_id:
            self.session.set_component_name(
                self.current_component_id,
                self.component_name.text(),
            )
            self.component_changed.emit(self.current_component_id)

    def _component_role_changed(self, role):
        if not self._updating and self.current_component_id:
            self.session.set_component_role(self.current_component_id, role)
            self.component_changed.emit(self.current_component_id)

    def _component_materialize_changed(self, value):
        if not self._updating and self.current_component_id:
            self.session.set_component_materialized(
                self.current_component_id,
                value,
            )
            self.component_changed.emit(self.current_component_id)

    def _component_reason_changed(self):
        if not self._updating and self.current_component_id:
            self.session.set_component_reason(
                self.current_component_id,
                self.component_reason.toPlainText(),
            )
            self.component_changed.emit(self.current_component_id)

    def _relationship_type_changed(self, value):
        if not self._updating and self.current_relationship_id:
            self.session.set_relationship_type(
                self.current_relationship_id,
                value,
            )
            self.relationship_changed.emit(self.current_relationship_id)

    def _relationship_level_changed(self, value):
        if not self._updating and self.current_relationship_id:
            self.session.set_relationship_level(
                self.current_relationship_id,
                value,
            )
            self.relationship_changed.emit(self.current_relationship_id)

    def _relationship_materialize_changed(self, value):
        if not self._updating and self.current_relationship_id:
            self.session.set_relationship_materialized(
                self.current_relationship_id,
                value,
            )
            self.relationship_changed.emit(self.current_relationship_id)
