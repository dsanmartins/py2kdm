import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AISuggestionsPanel(QWidget):
    """
    Displays pre-review AI suggestions and allows explicit human decisions.

    Accept applies the suggestion to the model when a safe structured operation
    is available. If the suggestion is only textual, Accept records the
    acceptance decision without modifying the architecture.
    """

    suggestion_action_requested = Signal(str, int)

    LEVEL_STYLES = {
        "blocking": {
            "background": QColor("#b00020"),
            "foreground": QColor("#ffffff"),
            "bold": True,
        },
        "warning": {
            "background": QColor("#f57c00"),
            "foreground": QColor("#ffffff"),
            "bold": True,
        },
        "info": {
            "background": QColor("#1565c0"),
            "foreground": QColor("#ffffff"),
            "bold": False,
        },
    }

    STATUS_STYLES = {
        "user_accepted": QColor("#1b5e20"),
        "user_rejected": QColor("#6d6d6d"),
        "user_reviewed": QColor("#4e342e"),
        "user_applied": QColor("#004d40"),
        "accept_not_applied": QColor("#795548"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._items = []

        layout = QVBoxLayout(self)

        group = QGroupBox("AI Suggestions")
        group_layout = QVBoxLayout(group)

        self.summary = QLabel("No AI suggestions loaded.")

        self.help_label = QLabel(
            "Accept applies a structured suggestion when possible. "
            "Reject discards the suggestion. Mark reviewed records that it was checked."
        )
        self.help_label.setWordWrap(True)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Phase",
                "Type",
                "Severity",
                "Confidence",
                "Status",
                "Decision",
                "Message",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._show_selected_details)

        actions = QHBoxLayout()
        self.accept_btn = QPushButton("Accept")
        self.reject_btn = QPushButton("Reject")
        self.reviewed_btn = QPushButton("Mark reviewed")

        self.accept_btn.setToolTip(
            "Accept this suggestion. If it contains a safe structured change, "
            "the GUI applies it to the reviewed architecture. If not, the "
            "decision is only recorded."
        )
        self.reject_btn.setToolTip(
            "Reject this suggestion. The architecture model is not modified."
        )
        self.reviewed_btn.setToolTip(
            "Mark this suggestion as reviewed without accepting, rejecting, "
            "or modifying the architecture."
        )

        actions.addWidget(self.accept_btn)
        actions.addWidget(self.reject_btn)
        actions.addWidget(self.reviewed_btn)
        actions.addStretch(1)

        self.accept_btn.clicked.connect(lambda: self._request_action("accept"))
        self.reject_btn.clicked.connect(lambda: self._request_action("reject"))
        self.reviewed_btn.clicked.connect(lambda: self._request_action("reviewed"))

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(240)
        self.details.setPlaceholderText(
            "Select an AI suggestion to see details."
        )

        group_layout.addWidget(self.summary)
        group_layout.addWidget(self.help_label)
        group_layout.addWidget(self.table)
        group_layout.addLayout(actions)
        group_layout.addWidget(QLabel("Details"))
        group_layout.addWidget(self.details)

        layout.addWidget(group)

    def show_model(self, model):
        self._items = self._collect_items(model or {})
        self._render_items()

    def selected_suggestion_index(self):
        selected = self.table.selectedItems()

        if not selected:
            return None

        row = selected[0].data(Qt.ItemDataRole.UserRole)

        if row is None or row >= len(self._items):
            return None

        item = self._items[row]

        if item.get("_kind") != "suggestion":
            return None

        return item.get("_suggestion_index")

    def _request_action(self, action: str):
        index = self.selected_suggestion_index()

        if index is None:
            QMessageBox.information(
                self,
                "No suggestion selected",
                "Select a pre-review suggestion first.",
            )
            return

        self.suggestion_action_requested.emit(action, index)

    def _collect_items(self, model):
        items = []

        ai_enrichment = model.get("ai_enrichment", {})
        for index, suggestion in enumerate(ai_enrichment.get("suggestions", [])):
            item = dict(suggestion)
            item["_phase"] = "pre-review"
            item["_kind"] = "suggestion"
            item["_suggestion_index"] = index
            items.append(item)

        post_review = model.get("post_review_ai_check", {})
        for finding in post_review.get("findings", []):
            item = dict(finding)
            item["_phase"] = "legacy post-review"
            item["_kind"] = "finding"
            items.append(item)

        return items

    def _render_items(self):
        self.table.setRowCount(len(self._items))

        pre_count = sum(1 for item in self._items if item.get("_phase") == "pre-review")
        decided_count = sum(
            1
            for item in self._items
            if item.get("review_decision") or str(item.get("status", "")).startswith("user_")
        )

        self.summary.setText(
            f"AI suggestions: {pre_count} | "
            f"Decided/reviewed: {decided_count}"
        )

        for row, item in enumerate(self._items):
            values = [
                item.get("_phase", ""),
                item.get("suggestion_type") or item.get("finding_type") or "",
                item.get("severity", "info"),
                self._format_confidence(item.get("confidence")),
                item.get("status", ""),
                item.get("review_decision", ""),
                item.get("message", ""),
            ]

            severity = item.get("severity", "info")
            status = item.get("status", "")

            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, row)
                self._apply_style(cell, severity, status)
                self.table.setItem(row, col, cell)

        self.table.resizeColumnsToContents()

        if not self._items:
            self.details.clear()

    def _format_confidence(self, value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return "-"

    def _apply_style(self, item, severity, status=None):
        if status in self.STATUS_STYLES:
            item.setBackground(QBrush(self.STATUS_STYLES[status]))
            item.setForeground(QBrush(QColor("#ffffff")))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            return

        style = self.LEVEL_STYLES.get(severity)

        if not style:
            return

        item.setBackground(QBrush(style["background"]))
        item.setForeground(QBrush(style["foreground"]))

        if style.get("bold"):
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def _show_selected_details(self):
        selected = self.table.selectedItems()

        if not selected:
            self.details.clear()
            return

        row = selected[0].data(Qt.ItemDataRole.UserRole)

        if row is None or row >= len(self._items):
            self.details.clear()
            return

        item = self._items[row]
        self.details.setPlainText(self._format_details(item))

    def _format_details(self, item):
        lines = []

        lines.append(f"Phase: {item.get('_phase')}")
        lines.append(f"Kind: {item.get('_kind')}")
        lines.append(
            f"Type: {item.get('suggestion_type') or item.get('finding_type')}"
        )
        lines.append(f"Severity: {item.get('severity')}")
        lines.append(f"Status: {item.get('status')}")
        lines.append(f"Review decision: {item.get('review_decision', '-')}")
        lines.append(f"Confidence: {self._format_confidence(item.get('confidence'))}")
        lines.append("")
        lines.append("Message:")
        lines.append(str(item.get("message", "-")))

        if item.get("recommendation"):
            lines.append("")
            lines.append("Recommendation:")
            lines.append(str(item.get("recommendation")))

        if item.get("affected_elements"):
            lines.append("")
            lines.append("Affected elements:")
            for element in item.get("affected_elements", []):
                lines.append(f"- {element}")

        if item.get("evidence"):
            lines.append("")
            lines.append("Evidence:")
            for evidence in item.get("evidence", []):
                lines.append(f"- {evidence}")

        if item.get("proposed_changes"):
            lines.append("")
            lines.append("Proposed changes:")
            lines.append(
                json.dumps(
                    item.get("proposed_changes", []),
                    indent=2,
                    ensure_ascii=False,
                )
            )

        if item.get("metadata"):
            lines.append("")
            lines.append("Metadata:")
            lines.append(
                json.dumps(
                    item.get("metadata", {}),
                    indent=2,
                    ensure_ascii=False,
                )
            )

        return "\n".join(lines)
