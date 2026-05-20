from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ValidationPanel(QWidget):
    """
    Validation/consistency report panel.

    Uses strong background colors with white text so findings remain readable
    in dark UI themes.
    """

    LEVEL_STYLES = {
        "forbidden": {
            "background": QColor("#b00020"),  # strong red
            "foreground": QColor("#ffffff"),
            "bold": True,
        },
        "warning": {
            "background": QColor("#f57c00"),  # dark orange
            "foreground": QColor("#ffffff"),
            "bold": True,
        },
        "ok": {
            "background": QColor("#1b5e20"),  # dark green
            "foreground": QColor("#ffffff"),
            "bold": True,
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        group = QGroupBox("Validation")
        gl = QVBoxLayout(group)

        self.summary = QLabel("No validation yet.")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Level", "Rule", "Element", "Message"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        gl.addWidget(self.summary)
        gl.addWidget(self.table)

        layout.addWidget(group)

    def show_report(self, report):
        s = report.get("summary", {})

        self.summary.setText(
            f"Valid: {report.get('valid')} | "
            f"OK: {s.get('ok', 0)} | "
            f"Warnings: {s.get('warnings', 0)} | "
            f"Forbidden: {s.get('forbidden', 0)}"
        )

        findings = (
            report.get("forbidden", [])
            + report.get("warnings", [])
            + report.get("ok", [])
        )

        self.table.setRowCount(len(findings))

        for row, finding in enumerate(findings):
            level = finding.get("level", "")
            values = [
                level,
                finding.get("rule_id", ""),
                finding.get("element", ""),
                finding.get("message", ""),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self._apply_level_style(item, level)
                self.table.setItem(row, col, item)

    def _apply_level_style(self, item, level):
        style = self.LEVEL_STYLES.get(level)

        if not style:
            return

        item.setBackground(QBrush(style["background"]))
        item.setForeground(QBrush(style["foreground"]))

        if style.get("bold"):
            font = item.font()
            font.setBold(True)
            item.setFont(font)
