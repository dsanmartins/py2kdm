import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class AISuggestionsPanel(QWidget):
    """
    Displays pre-review AI suggestions and post-review AI findings.

    The panel is read-only. It does not apply changes automatically. This is
    intentional: AI suggestions must remain reviewable by the user.
    """

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

    def __init__(self, parent=None):
        super().__init__(parent)

        self._items = []

        layout = QVBoxLayout(self)

        group = QGroupBox("AI Suggestions / Findings")
        group_layout = QVBoxLayout(group)

        self.summary = QLabel("No AI suggestions loaded.")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Phase", "Type", "Severity", "Confidence", "Status", "Message"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._show_selected_details)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(220)
        self.details.setPlaceholderText(
            "Select an AI suggestion/finding to see details."
        )

        group_layout.addWidget(self.summary)
        group_layout.addWidget(self.table)
        group_layout.addWidget(QLabel("Details"))
        group_layout.addWidget(self.details)

        layout.addWidget(group)

    def show_model(self, model):
        self._items = self._collect_items(model or {})
        self._render_items()

    def _collect_items(self, model):
        items = []

        ai_enrichment = model.get("ai_enrichment", {})
        for suggestion in ai_enrichment.get("suggestions", []):
            item = dict(suggestion)
            item["_phase"] = "pre-review"
            item["_kind"] = "suggestion"
            items.append(item)

        post_review = model.get("post_review_ai_check", {})
        for finding in post_review.get("findings", []):
            item = dict(finding)
            item["_phase"] = "post-review"
            item["_kind"] = "finding"
            items.append(item)

        return items

    def _render_items(self):
        self.table.setRowCount(len(self._items))

        pre_count = sum(1 for item in self._items if item.get("_phase") == "pre-review")
        post_count = sum(1 for item in self._items if item.get("_phase") == "post-review")

        self.summary.setText(
            f"AI items: {len(self._items)} | "
            f"Pre-review suggestions: {pre_count} | "
            f"Post-review findings: {post_count}"
        )

        for row, item in enumerate(self._items):
            values = [
                item.get("_phase", ""),
                item.get("suggestion_type") or item.get("finding_type") or "",
                item.get("severity", "info"),
                self._format_confidence(item.get("confidence")),
                item.get("status", ""),
                item.get("message", ""),
            ]

            severity = item.get("severity", "info")

            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, row)
                self._apply_style(cell, severity)
                self.table.setItem(row, col, cell)

        self.table.resizeColumnsToContents()

        if not self._items:
            self.details.clear()

    def _format_confidence(self, value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}"
        return "-"

    def _apply_style(self, item, severity):
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
