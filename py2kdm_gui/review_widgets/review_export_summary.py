from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


@dataclass
class ReviewExportSummary:
    components_total: int = 0
    components_materialized: int = 0
    components_rejected: int = 0
    relationships_total: int = 0
    relationships_materialized: int = 0
    relationships_rejected: int = 0
    containment_relationships_total: int = 0
    containment_relationships_materialized: int = 0
    ai_suggestions_total: int = 0
    ai_accepted: int = 0
    ai_rejected: int = 0
    ai_reviewed: int = 0
    ai_applied: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0
    validation_forbidden: int = 0
    validation_allowed: int = 0
    validation_recommendations: int = 0

    def to_text(self) -> str:
        lines = []
        lines.append("Reviewed architecture export summary")
        lines.append("=" * 43)
        lines.append("")
        lines.append("Architecture elements")
        lines.append("---------------------")
        lines.append(f"Components total: {self.components_total}")
        lines.append(f"Components materialized: {self.components_materialized}")
        lines.append(f"Components rejected/not materialized: {self.components_rejected}")
        lines.append("")
        lines.append(f"Relationships total: {self.relationships_total}")
        lines.append(f"Relationships materialized: {self.relationships_materialized}")
        lines.append(f"Relationships rejected/not materialized: {self.relationships_rejected}")
        lines.append("")
        lines.append(f"Containment relationships total: {self.containment_relationships_total}")
        lines.append(
            f"Containment relationships materialized: "
            f"{self.containment_relationships_materialized}"
        )
        lines.append("")
        lines.append("AI suggestion decisions")
        lines.append("-----------------------")
        lines.append(f"AI suggestions total: {self.ai_suggestions_total}")
        lines.append(f"Accepted: {self.ai_accepted}")
        lines.append(f"Applied: {self.ai_applied}")
        lines.append(f"Rejected: {self.ai_rejected}")
        lines.append(f"Reviewed only: {self.ai_reviewed}")
        lines.append("")
        lines.append("Validation")
        lines.append("----------")
        lines.append(f"Errors: {self.validation_errors}")
        lines.append(f"Warnings: {self.validation_warnings}")
        lines.append(f"Forbidden findings: {self.validation_forbidden}")
        lines.append(f"Allowed findings: {self.validation_allowed}")
        lines.append(f"Recommendations: {self.validation_recommendations}")
        lines.append("")

        if self.validation_forbidden > 0 or self.validation_errors > 0:
            lines.append("Attention")
            lines.append("---------")
            lines.append(
                "The model still contains validation errors or FORBIDDEN findings. "
                "Export is possible only if the user explicitly confirms it."
            )
        else:
            lines.append("Status")
            lines.append("------")
            lines.append("No blocking validation findings were detected.")

        return "\n".join(lines)


class ReviewExportSummaryDialog(QDialog):
    """
    Confirmation dialog shown before exporting reviewed architecture JSON.
    """

    def __init__(self, summary: ReviewExportSummary, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export reviewed architecture summary")
        self.resize(720, 620)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Review the summary before exporting the reviewed architecture JSON."
        )
        intro.setWordWrap(True)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlainText(summary.to_text())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Confirm export")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(intro)
        layout.addWidget(self.summary_text)
        layout.addWidget(buttons)


def build_review_export_summary(
    *,
    model: dict[str, Any],
    session,
    validation_report: dict[str, Any],
) -> ReviewExportSummary:
    structure_model = model.get("structure_model", {}) if model else {}

    components = list(structure_model.get("components", []))
    relationships = list(structure_model.get("structure_relationships", []))
    containment = list(structure_model.get("containment_relationships", []))

    if hasattr(session, "components") and session.components:
        components = list(session.components)

    if hasattr(session, "relationships") and session.relationships:
        relationships = list(session.relationships)

    if hasattr(session, "containment_relationships") and session.containment_relationships:
        containment = list(session.containment_relationships)

    suggestions = model.get("ai_enrichment", {}).get("suggestions", []) if model else []

    summary = ReviewExportSummary()

    summary.components_total = len(components)
    summary.components_materialized = _count_materialized(components)
    summary.components_rejected = summary.components_total - summary.components_materialized

    summary.relationships_total = len(relationships)
    summary.relationships_materialized = _count_materialized(relationships)
    summary.relationships_rejected = (
        summary.relationships_total - summary.relationships_materialized
    )

    summary.containment_relationships_total = len(containment)
    summary.containment_relationships_materialized = _count_materialized(containment)

    summary.ai_suggestions_total = len(suggestions)

    for suggestion in suggestions:
        decision = suggestion.get("review_decision")
        status = suggestion.get("status")

        if decision == "accepted" or status == "user_accepted":
            summary.ai_accepted += 1
        elif decision == "rejected" or status == "user_rejected":
            summary.ai_rejected += 1
        elif decision == "reviewed" or status == "user_reviewed":
            summary.ai_reviewed += 1
        elif decision == "applied" or status == "user_applied":
            summary.ai_applied += 1

    validation_summary = validation_report.get("summary", {}) if validation_report else {}

    summary.validation_errors = int(validation_summary.get("errors", 0) or 0)
    summary.validation_warnings = int(validation_summary.get("warnings", 0) or 0)
    summary.validation_forbidden = int(validation_summary.get("forbidden", 0) or 0)
    summary.validation_allowed = int(validation_summary.get("allowed", 0) or 0)
    summary.validation_recommendations = int(
        validation_summary.get("recommendations", 0) or 0
    )

    return summary


def _count_materialized(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if item.get("materialize", True) is not False)
