from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGroupBox, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

class ValidationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        group = QGroupBox("Validation")
        gl = QVBoxLayout(group)
        self.summary = QLabel("No validation yet.")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Level", "Rule", "Element", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        gl.addWidget(self.summary); gl.addWidget(self.table)
        layout.addWidget(group)

    def show_report(self, report):
        s = report.get("summary", {})
        self.summary.setText(f"Valid: {report.get('valid')} | OK: {s.get('ok',0)} | Warnings: {s.get('warnings',0)} | Forbidden: {s.get('forbidden',0)}")
        findings = report.get("forbidden", []) + report.get("warnings", []) + report.get("ok", [])
        self.table.setRowCount(len(findings))
        for row, f in enumerate(findings):
            level = f.get("level", "")
            vals = [level, f.get("rule_id", ""), f.get("element", ""), f.get("message", "")]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                if level == "forbidden": item.setBackground(QColor("#ffd6d6"))
                elif level == "warning": item.setBackground(QColor("#fff1c2"))
                elif level == "ok": item.setBackground(QColor("#dcf7dc"))
                self.table.setItem(row, col, item)
