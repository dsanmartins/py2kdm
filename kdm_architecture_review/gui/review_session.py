import json
from pathlib import Path

try:
    from kdm_architecture_review.review_validator import ArchitectureReviewValidator
except Exception:
    ArchitectureReviewValidator = None


class ReviewSession:
    def __init__(self):
        self.proposal_path = None
        self.model = None
        self.dirty = False

    def load_proposal(self, path):
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            self.model = json.load(fh)
        self.proposal_path = path
        self.dirty = False
        self._ensure_defaults()

    def save_reviewed_architecture(self, path):
        if not self.model:
            return
        self.model.setdefault("architecture_review", {})
        self.model["architecture_review"].update({
            "status": "reviewed",
            "source": "architecture_review_gui",
            "decision": "approved_with_changes"
        })
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.model, fh, indent=2, ensure_ascii=False)
        self.dirty = False

    def save_review_actions(self, path):
        review = {
            "source": "architecture_review_gui",
            "decision": "approved_with_changes",
            "component_overrides": [],
            "relationship_overrides": []
        }
        for c in self.components:
            if c.get("review_status"):
                review["component_overrides"].append({
                    "component_id": c.get("id"),
                    "decision": "rejected" if c.get("materialize", True) is False else "accepted",
                    "name": c.get("name"),
                    "role": c.get("role"),
                    "implemented_by": c.get("implemented_by", []),
                    "reason": c.get("review_reason")
                })
        for r in self.relationships:
            if r.get("review_status"):
                review["relationship_overrides"].append({
                    "relationship_id": r.get("id"),
                    "decision": "rejected" if r.get("materialize", True) is False else "accepted",
                    "type": r.get("type"),
                    "relationship_level": r.get("relationship_level"),
                    "source": r.get("source"),
                    "target": r.get("target")
                })
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(review, fh, indent=2, ensure_ascii=False)

    @property
    def structure_model(self):
        if not self.model:
            return {}
        return self.model.setdefault("structure_model", {})

    @property
    def components(self):
        return self.structure_model.setdefault("components", [])

    @property
    def subsystems(self):
        return self.structure_model.setdefault("subsystems", [])

    @property
    def control_loops(self):
        return self.structure_model.setdefault("control_loops", [])

    @property
    def relationships(self):
        return self.structure_model.setdefault("structure_relationships", [])

    @property
    def containment_relationships(self):
        return self.structure_model.setdefault("containment_relationships", [])

    def get_component(self, component_id):
        return next((c for c in self.components if c.get("id") == component_id), None)

    def get_subsystem(self, subsystem_id):
        return next((s for s in self.subsystems if s.get("id") == subsystem_id), None)

    def get_control_loop(self, loop_id):
        return next((l for l in self.control_loops if l.get("id") == loop_id), None)

    def get_relationship(self, relationship_id):
        return next((r for r in self.relationships if r.get("id") == relationship_id), None)

    def get_containment_relationship(self, relationship_id):
        return next((r for r in self.containment_relationships if r.get("id") == relationship_id), None)

    def get_node(self, element_id):
        return (
            self.get_component(element_id)
            or self.get_control_loop(element_id)
            or self.get_subsystem(element_id)
        )

    def set_component_materialized(self, component_id, materialize):
        c = self.get_component(component_id)
        if c:
            c["materialize"] = bool(materialize)
            c["review_status"] = "user_accepted" if materialize else "user_rejected"
            self.dirty = True

    def set_component_role(self, component_id, role):
        c = self.get_component(component_id)
        if c:
            c["role"] = role
            c["review_status"] = "user_modified"
            self._sync_component_stereotype(c)
            self.dirty = True

    def set_component_name(self, component_id, name):
        c = self.get_component(component_id)
        if c:
            c["name"] = name
            c["review_status"] = "user_modified"
            self.dirty = True

    def set_component_reason(self, component_id, reason):
        c = self.get_component(component_id)
        if c:
            c["review_reason"] = reason
            c.setdefault("review_status", "user_modified")
            self.dirty = True

    def set_relationship_materialized(self, relationship_id, materialize):
        r = self.get_relationship(relationship_id)
        if r is None:
            r = self.get_containment_relationship(relationship_id)
        if r:
            r["materialize"] = bool(materialize)
            r["review_status"] = "user_accepted" if materialize else "user_rejected"
            self.dirty = True

    def set_relationship_type(self, relationship_id, rel_type):
        r = self.get_relationship(relationship_id)
        if r is None:
            r = self.get_containment_relationship(relationship_id)
        if r:
            r["type"] = rel_type
            r["review_status"] = "user_modified"
            self.dirty = True

    def set_relationship_level(self, relationship_id, level):
        r = self.get_relationship(relationship_id)
        if r is None:
            r = self.get_containment_relationship(relationship_id)
        if r:
            r["relationship_level"] = level
            r["review_status"] = "user_modified"
            self.dirty = True

    def get_component_code_traceability(self, component_id):
        """
        Returns normalized code traceability information for an architecture
        component.

        The method is intentionally defensive because different recoverers may
        provide different levels of detail.

        Returned fields:
        - kind: class / method / function / variable / attribute / module / package / unknown
        - ids: implementation ids from implemented_by
        - qualified_names: readable qualified names when available
        - containers: inferred containers when possible
        - raw_type: original code_element_type value when present
        """

        component = self.get_component(component_id)

        if not component:
            return {
                "kind": "unknown",
                "ids": [],
                "qualified_names": [],
                "containers": [],
                "raw_type": None,
            }

        implemented_by = component.get("implemented_by", []) or []
        raw_type = component.get("code_element_type")

        kind = self._normalize_code_element_type(
            raw_type,
            implemented_by,
        )

        qualified_names = []

        if component.get("code_element_qualified_name"):
            qualified_names.append(component.get("code_element_qualified_name"))

        for implementation_id in implemented_by:
            qn = self._qualified_name_from_code_id(implementation_id)

            if qn and qn not in qualified_names:
                qualified_names.append(qn)

        containers = []

        if component.get("code_element_container"):
            containers.append(component.get("code_element_container"))

        for qn in qualified_names:
            container = self._container_from_qualified_name(qn)

            if container and container not in containers:
                containers.append(container)

        return {
            "kind": kind,
            "ids": implemented_by,
            "qualified_names": qualified_names,
            "containers": containers,
            "raw_type": raw_type,
        }

    def _normalize_code_element_type(self, raw_type, implemented_by):
        if raw_type:
            value = str(raw_type).lower()

            if value in {
                "class",
                "method",
                "function",
                "variable",
                "attribute",
                "parameter",
                "module",
                "package",
                "file",
            }:
                return value

        if implemented_by:
            prefix = str(implemented_by[0]).split(":", 1)[0].lower()

            mapping = {
                "class": "class",
                "method": "method",
                "function": "function",
                "callable": "function",
                "variable": "variable",
                "attribute": "attribute",
                "parameter": "parameter",
                "module": "module",
                "package": "package",
                "file": "file",
            }

            return mapping.get(prefix, prefix or "unknown")

        return "unknown"

    def _qualified_name_from_code_id(self, code_id):
        if not code_id:
            return None

        text = str(code_id)

        if ":" in text:
            return text.split(":", 1)[1]

        return text

    def _container_from_qualified_name(self, qualified_name):
        if not qualified_name or "." not in qualified_name:
            return None

        return qualified_name.rsplit(".", 1)[0]

    def validate(self):
        if not self.model:
            return {"valid": False, "summary": {"ok": 0, "warnings": 0, "forbidden": 1},
                    "ok": [], "warnings": [], "forbidden": [{"rule_id": "GUI-F-01", "level": "forbidden", "message": "No proposal loaded."}]}

        if ArchitectureReviewValidator is None:
            report = {"valid": True, "summary": {"ok": 0, "warnings": 1, "forbidden": 0},
                      "ok": [], "warnings": [{"rule_id": "GUI-W-01", "level": "warning", "message": "Review validator not available."}], "forbidden": []}
        else:
            report = ArchitectureReviewValidator().validate(self.model).to_dict()

        return self._merge_architecture_consistency(report)

    def _merge_architecture_consistency(self, report):
        """
        Merges the construction report stored in structure_model.
        architecture_consistency into the GUI validation report.

        The merge intentionally avoids duplicated user-facing warnings. For
        example, ARV-W-01 and LOOP-W01 both report a partial control loop, so
        LOOP-W01 is omitted when ARV-W-01 is already present for the same loop.
        """

        consistency = self.structure_model.get("architecture_consistency", {})

        if not consistency:
            return report

        report.setdefault("ok", [])
        report.setdefault("warnings", [])
        report.setdefault("forbidden", [])

        existing_warning_keys = self._finding_keys(report.get("warnings", []))
        existing_ok_keys = self._finding_keys(report.get("ok", []))
        existing_forbidden_keys = self._finding_keys(report.get("forbidden", []))

        for item in consistency.get("applied_rules", []):
            finding = {
                "rule_id": item.get("rule_id", "CONSISTENCY-OK"),
                "level": "ok",
                "element": item.get("target") or item.get("source") or "",
                "message": item.get("message", ""),
            }

            key = self._finding_key(finding)

            if key not in existing_ok_keys:
                report["ok"].append(finding)
                existing_ok_keys.add(key)

        for item in consistency.get("warnings", []):
            finding = {
                "rule_id": item.get("rule_id", "CONSISTENCY-W"),
                "level": "warning",
                "element": item.get("target") or "",
                "message": item.get("message", ""),
            }

            if self._is_duplicate_consistency_warning(finding, report):
                continue

            key = self._finding_key(finding)

            if key not in existing_warning_keys:
                report["warnings"].append(finding)
                existing_warning_keys.add(key)

        for item in consistency.get("blocked_constructions", []):
            finding = {
                "rule_id": item.get("rule_id", "CONSISTENCY-F"),
                "level": "forbidden",
                "element": item.get("target") or item.get("source") or "",
                "message": item.get("message", ""),
            }

            key = self._finding_key(finding)

            if key not in existing_forbidden_keys:
                report["forbidden"].append(finding)
                existing_forbidden_keys.add(key)

        report["summary"] = {
            "ok": len(report.get("ok", [])),
            "warnings": len(report.get("warnings", [])),
            "forbidden": len(report.get("forbidden", [])),
        }
        report["valid"] = report["summary"]["forbidden"] == 0

        return report

    def _is_duplicate_consistency_warning(self, finding, report):
        """
        Hides construction warnings that are already represented by the active
        GUI review validator.
        """

        rule_id = finding.get("rule_id")
        element = finding.get("element")

        # LOOP-W01 and ARV-W-01 both mean: partial loop / missing MAPE role.
        if rule_id == "LOOP-W01":
            for existing in report.get("warnings", []):
                if (
                    existing.get("rule_id") == "ARV-W-01"
                    and existing.get("element") == element
                ):
                    return True

        return False

    def _finding_keys(self, findings):
        return {
            self._finding_key(finding)
            for finding in findings
        }

    def _finding_key(self, finding):
        return (
            finding.get("rule_id"),
            finding.get("element"),
            finding.get("message"),
        )

    def _ensure_defaults(self):
        for c in self.components:
            c.setdefault("materialize", True)
        for r in self.relationships:
            r.setdefault("materialize", r.get("relationship_level") == "architectural")
        for r in self.containment_relationships:
            r.setdefault("materialize", True)
        for s in self.subsystems:
            s.setdefault("materialize", True)
        for l in self.control_loops:
            l.setdefault("materialize", True)

    def _sync_component_stereotype(self, component):
        role_to_stereotype = {
            "Monitor": "Monitor",
            "Analyzer": "Analyzer",
            "Planner": "Planner",
            "Executor": "Executor",
            "Knowledge": "Knowledge",
            "LoopManager": "CL Manager",
            "Loop": "Control Loop",
            "ReferenceInput": "Reference Input",
            "MeasuredOutput": "Measured Output",
            "Sensor": "Sensor",
            "Effector": "Effector",
        }
        if component.get("role") in role_to_stereotype:
            component["stereotype_name"] = role_to_stereotype[component["role"]]
            component["stereotype_domain"] = "Adaptive System Domain"
            component["stereotype_type"] = "structure:Component"
