from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TraceabilityPanel(QWidget):
    """
    Shows why an architecture element exists and where it comes from.

    The panel is intentionally defensive because the architecture JSON may be
    produced by different recovery stages: static recovery, runtime enrichment,
    pre-review agents, or manual GUI review.
    """

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Traceability")
        group_layout = QVBoxLayout(group)

        self.summary = QLabel("Select a component or relationship.")
        self.summary.setWordWrap(True)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Traceability details will appear here."
        )

        group_layout.addWidget(self.summary)
        group_layout.addWidget(self.details)

        layout.addWidget(group)

    def clear(self):
        self.summary.setText("Select a component or relationship.")
        self.details.clear()

    def show_component(self, component_id: str):
        component = self.session.get_component(component_id)

        if component is None:
            component = self.session.get_subsystem(component_id)

        if component is None:
            component = self.session.get_control_loop(component_id)

        if component is None:
            self.summary.setText("Component not found.")
            self.details.clear()
            return

        self.summary.setText(
            f"{component.get('name', component.get('id'))} "
            f"[{component.get('role', component.get('type', 'element'))}]"
        )
        self.details.setPlainText(self._format_component_traceability(component))

    def show_relationship(self, relationship_id: str):
        relationship = self.session.get_relationship(relationship_id)

        if relationship is None:
            relationship = self.session.get_containment_relationship(relationship_id)

        if relationship is None:
            self.summary.setText("Relationship not found.")
            self.details.clear()
            return

        self.summary.setText(
            f"{relationship.get('type', 'relationship')}: "
            f"{relationship.get('source')} -> {relationship.get('target')}"
        )
        self.details.setPlainText(self._format_relationship_traceability(relationship))

    def _format_component_traceability(self, component: dict) -> str:
        lines = []

        lines.append("ELEMENT")
        lines.append(f"  id: {component.get('id')}")
        lines.append(f"  name: {component.get('name')}")
        lines.append(f"  role: {component.get('role')}")
        lines.append(f"  materialize: {component.get('materialize', True)}")
        lines.append(f"  review_status: {component.get('review_status', '-')}")
        lines.append("")

        lines.append("KDM STEREOTYPE")
        lines.append(f"  domain: {component.get('stereotype_domain', '-')}")
        lines.append(f"  name: {component.get('stereotype_name', '-')}")
        lines.append(f"  type: {component.get('stereotype_type', '-')}")
        lines.append("")

        lines.extend(self._component_code_traceability(component))
        lines.append("")

        lines.extend(self._component_architecture_evidence(component))
        lines.append("")

        lines.extend(self._relationships_for_element(component.get("id")))
        lines.append("")

        lines.extend(self._runtime_evidence_for_component(component))
        lines.append("")

        lines.extend(self._ai_suggestions_for_element(component.get("id")))

        return "\n".join(lines)

    def _component_code_traceability(self, component: dict) -> list[str]:
        lines = ["CODE TRACEABILITY"]

        trace = {}
        if hasattr(self.session, "get_component_code_traceability"):
            try:
                trace = self.session.get_component_code_traceability(component.get("id"))
            except Exception as exc:
                trace = {"error": str(exc)}

        implemented_by = component.get("implemented_by", []) or []

        lines.append(f"  implemented_by: {implemented_by or '-'}")
        lines.append(f"  code_element_type: {component.get('code_element_type', trace.get('kind', '-'))}")
        lines.append(f"  code_element_qualified_name: {component.get('code_element_qualified_name', '-')}")

        if trace:
            lines.append(f"  normalized_kind: {trace.get('kind', '-')}")
            lines.append(f"  qualified_names: {trace.get('qualified_names', []) or '-'}")
            lines.append(f"  containers: {trace.get('containers', []) or '-'}")
            lines.append(f"  raw_type: {trace.get('raw_type', '-')}")
            if trace.get("error"):
                lines.append(f"  traceability_error: {trace.get('error')}")

        return lines

    def _component_architecture_evidence(self, component: dict) -> list[str]:
        lines = ["ARCHITECTURE RECOVERY EVIDENCE"]

        keys = [
            "source",
            "source_agent",
            "evidence",
            "reason",
            "review_reason",
            "matched_terms",
            "matched_pattern",
            "confidence",
            "relationship_level",
        ]

        found = False
        for key in keys:
            if key in component and component.get(key) not in (None, "", []):
                lines.append(f"  {key}: {self._format_value(component.get(key))}")
                found = True

        if not found:
            lines.append("  -")

        return lines

    def _relationships_for_element(self, element_id: str) -> list[str]:
        lines = ["ARCHITECTURE RELATIONSHIPS"]

        if not element_id:
            lines.append("  -")
            return lines

        all_relationships = (
            list(self.session.relationships)
            + list(self.session.containment_relationships)
        )

        related = [
            rel for rel in all_relationships
            if rel.get("source") == element_id or rel.get("target") == element_id
        ]

        if not related:
            lines.append("  -")
            return lines

        for rel in related[:30]:
            direction = "out" if rel.get("source") == element_id else "in"
            other_id = rel.get("target") if direction == "out" else rel.get("source")
            other = self.session.get_node(other_id)
            other_name = other.get("name") if other else other_id
            lines.append(
                f"  [{direction}] {rel.get('type')} -> {other_name} "
                f"(id={rel.get('id')}, materialize={rel.get('materialize', True)})"
            )

        if len(related) > 30:
            lines.append(f"  ... {len(related) - 30} more relationship(s)")

        return lines

    def _runtime_evidence_for_component(self, component: dict) -> list[str]:
        lines = ["RUNTIME EVIDENCE"]

        model = self.session.model or {}
        runtime_summary = model.get("runtime_enrichment", {}).get("summary", {})

        if runtime_summary:
            lines.append(f"  runtime_summary: {runtime_summary}")

        implemented_by = component.get("implemented_by", []) or []
        qnames = set()

        for item in implemented_by:
            qnames.add(str(item))
            if ":" in str(item):
                qnames.add(str(item).split(":", 1)[1])

        if component.get("code_element_qualified_name"):
            qnames.add(component.get("code_element_qualified_name"))

        runtime_relationships = [
            rel
            for rel in model.get("relationships", [])
            if rel.get("type") == "runtime_calls"
            and self._runtime_rel_matches(rel, qnames)
        ]

        if not runtime_summary and not runtime_relationships:
            lines.append("  -")
            return lines

        if runtime_relationships:
            lines.append("  related runtime_calls:")
            for rel in runtime_relationships[:20]:
                lines.append(
                    "    "
                    f"{rel.get('source')} -> {rel.get('target')} "
                    f"(scenario={rel.get('scenario', '-')})"
                )
            if len(runtime_relationships) > 20:
                lines.append(f"    ... {len(runtime_relationships) - 20} more runtime call(s)")

        return lines

    def _runtime_rel_matches(self, rel: dict, qnames: set[str]) -> bool:
        if not qnames:
            return False

        source = str(rel.get("source", ""))
        target = str(rel.get("target", ""))

        for qn in qnames:
            if qn and (qn in source or qn in target or source in qn or target in qn):
                return True

        return False

    def _format_relationship_traceability(self, relationship: dict) -> str:
        lines = []

        source = self.session.get_node(relationship.get("source"))
        target = self.session.get_node(relationship.get("target"))

        lines.append("RELATIONSHIP")
        lines.append(f"  id: {relationship.get('id')}")
        lines.append(f"  type: {relationship.get('type')}")
        lines.append(f"  level: {relationship.get('relationship_level')}")
        lines.append(f"  materialize: {relationship.get('materialize', True)}")
        lines.append(f"  review_status: {relationship.get('review_status', '-')}")
        lines.append("")

        lines.append("SOURCE")
        lines.append(f"  id: {relationship.get('source')}")
        lines.append(f"  name: {source.get('name') if source else '-'}")
        lines.append(f"  role: {source.get('role') if source else '-'}")
        lines.append("")

        lines.append("TARGET")
        lines.append(f"  id: {relationship.get('target')}")
        lines.append(f"  name: {target.get('name') if target else '-'}")
        lines.append(f"  role: {target.get('role') if target else '-'}")
        lines.append("")

        lines.append("EVIDENCE")
        keys = [
            "source_agent",
            "source",
            "evidence",
            "reason",
            "confidence",
            "scenario",
            "review_reason",
        ]

        found = False
        for key in keys:
            if key in relationship and relationship.get(key) not in (None, "", []):
                lines.append(f"  {key}: {self._format_value(relationship.get(key))}")
                found = True

        if not found:
            lines.append("  -")

        lines.append("")
        lines.extend(self._ai_suggestions_for_relationship(relationship))

        return "\n".join(lines)

    def _ai_suggestions_for_element(self, element_id: str) -> list[str]:
        lines = ["AI SUGGESTIONS"]

        if not element_id:
            lines.append("  -")
            return lines

        suggestions = []
        for index, suggestion in enumerate(
            (self.session.model or {}).get("ai_enrichment", {}).get("suggestions", [])
        ):
            if self._suggestion_mentions_element(suggestion, element_id):
                suggestions.append((index, suggestion))

        if not suggestions:
            lines.append("  -")
            return lines

        for index, suggestion in suggestions:
            lines.append(
                f"  [{index}] status={suggestion.get('status', '-')} "
                f"decision={suggestion.get('review_decision', '-')} "
                f"confidence={suggestion.get('confidence', '-')}"
            )
            lines.append(f"      message: {suggestion.get('message', '-')}")

        return lines

    def _ai_suggestions_for_relationship(self, relationship: dict) -> list[str]:
        lines = ["AI SUGGESTIONS FOR RELATIONSHIP"]

        suggestions = []
        for index, suggestion in enumerate(
            (self.session.model or {}).get("ai_enrichment", {}).get("suggestions", [])
        ):
            if self._suggestion_mentions_relationship(suggestion, relationship):
                suggestions.append((index, suggestion))

        if not suggestions:
            lines.append("  -")
            return lines

        for index, suggestion in suggestions:
            lines.append(
                f"  [{index}] status={suggestion.get('status', '-')} "
                f"decision={suggestion.get('review_decision', '-')} "
                f"confidence={suggestion.get('confidence', '-')}"
            )
            lines.append(f"      message: {suggestion.get('message', '-')}")

        return lines

    def _suggestion_mentions_element(self, suggestion: dict, element_id: str) -> bool:
        affected = suggestion.get("affected_elements", []) or []
        if element_id in affected:
            return True

        for change in suggestion.get("proposed_changes", []) or []:
            if not isinstance(change, dict):
                continue
            if change.get("source") == element_id or change.get("target") == element_id:
                return True

        return False

    def _suggestion_mentions_relationship(self, suggestion: dict, relationship: dict) -> bool:
        source = relationship.get("source")
        target = relationship.get("target")
        rel_type = relationship.get("type")

        for change in suggestion.get("proposed_changes", []) or []:
            if not isinstance(change, dict):
                continue
            if (
                change.get("source") == source
                and change.get("target") == target
                and (
                    change.get("relationship_type") == rel_type
                    or change.get("type") == rel_type
                )
            ):
                return True

        return False

    def _format_value(self, value):
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value
