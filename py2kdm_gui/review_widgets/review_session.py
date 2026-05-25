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


    # ------------------------------------------------------------
    # AI suggestion decisions
    # ------------------------------------------------------------

    @property
    def ai_suggestions(self):
        if not self.model:
            return []
        return self.model.setdefault("ai_enrichment", {}).setdefault("suggestions", [])

    def set_ai_suggestion_decision(self, index, decision, status=None, note=None):
        suggestion = self._get_ai_suggestion(index)

        if suggestion is None:
            return False

        suggestion["review_decision"] = decision
        suggestion["status"] = status or f"user_{decision}"
        suggestion.setdefault("metadata", {})
        suggestion["metadata"]["reviewed_by"] = "architecture_review_gui"

        if note:
            suggestion["metadata"]["review_note"] = note

        self._record_ai_suggestion_decision(index, suggestion, decision)
        self.dirty = True
        return True

    def apply_ai_suggestion(self, index):
        suggestion = self._get_ai_suggestion(index)

        if suggestion is None:
            return False, "Suggestion not found."

        applied_changes = []
        unsupported_changes = []

        for change in suggestion.get("proposed_changes", []) or []:
            if not isinstance(change, dict):
                unsupported_changes.append(change)
                continue

            operation = change.get("operation")

            if operation == "add_relationship":
                ok, result = self._apply_add_relationship(change)
            elif operation == "optional_add_component":
                ok, result = self._apply_optional_add_component(change)
            else:
                ok, result = False, f"Unsupported operation: {operation}"

            if ok:
                applied_changes.append(result)
            else:
                unsupported_changes.append(result)

        if applied_changes:
            suggestion["review_decision"] = "applied"
            suggestion["status"] = "user_applied"
            suggestion.setdefault("metadata", {})
            suggestion["metadata"]["applied_changes"] = applied_changes

            if unsupported_changes:
                suggestion["metadata"]["unsupported_changes"] = unsupported_changes

            self._record_ai_suggestion_decision(index, suggestion, "applied")
            self.dirty = True
            return True, "Applied supported structured change(s)."

        suggestion["review_decision"] = "apply_not_supported"
        suggestion["status"] = "apply_not_supported"
        suggestion.setdefault("metadata", {})
        suggestion["metadata"]["unsupported_changes"] = unsupported_changes
        self._record_ai_suggestion_decision(index, suggestion, "apply_not_supported")
        self.dirty = True
        return False, "No supported structured change was applied."

    def _get_ai_suggestion(self, index):
        try:
            index = int(index)
        except Exception:
            return None

        suggestions = self.ai_suggestions

        if index < 0 or index >= len(suggestions):
            return None

        return suggestions[index]

    def _record_ai_suggestion_decision(self, index, suggestion, decision):
        review = self.model.setdefault("architecture_review", {})
        decisions = review.setdefault("ai_suggestion_decisions", [])

        record = {
            "suggestion_index": index,
            "suggestion_id": suggestion.get("id"),
            "suggestion_type": suggestion.get("suggestion_type"),
            "source": suggestion.get("source"),
            "decision": decision,
            "status": suggestion.get("status"),
            "message": suggestion.get("message"),
        }

        for existing in decisions:
            if (
                existing.get("suggestion_index") == index
                and existing.get("suggestion_id") == suggestion.get("id")
            ):
                existing.update(record)
                return

        decisions.append(record)

    def _apply_add_relationship(self, change):
        source = change.get("source")
        target = change.get("target")
        relationship_type = change.get("relationship_type") or change.get("type")

        if not source or not target or not relationship_type:
            return False, "add_relationship requires source, target and relationship_type."

        existing = self._find_relationship(source, target, relationship_type)

        if existing:
            existing["materialize"] = True
            existing["review_status"] = "user_accepted"
            return True, {
                "operation": "add_relationship",
                "result": "existing_relationship_marked_for_materialization",
                "relationship_id": existing.get("id"),
            }

        relationship = {
            "id": self._new_relationship_id(relationship_type, source, target),
            "type": relationship_type,
            "source": source,
            "target": target,
            "relationship_level": change.get("relationship_level", "architectural"),
            "materialize": True,
            "review_status": "user_applied_ai_suggestion",
            "source_agent": change.get("source_agent", "AI"),
        }

        self.relationships.append(relationship)

        return True, {
            "operation": "add_relationship",
            "result": "created_relationship",
            "relationship_id": relationship["id"],
        }

    def _apply_optional_add_component(self, change):
        role = change.get("role")
        target = change.get("target")

        if not role:
            return False, "optional_add_component requires role."

        component = {
            "id": self._new_component_id(role),
            "name": change.get("name") or self._role_to_display_name(role),
            "role": role,
            "materialize": True,
            "review_status": "user_applied_ai_suggestion",
            "implemented_by": [],
            "reason": change.get("description", ""),
        }
        self._sync_component_stereotype(component)
        self.components.append(component)

        result = {
            "operation": "optional_add_component",
            "result": "created_component",
            "component_id": component["id"],
        }

        if target:
            containment = {
                "id": self._new_relationship_id("contains", target, component["id"]),
                "type": "contains",
                "source": target,
                "target": component["id"],
                "relationship_level": "architectural",
                "materialize": True,
                "review_status": "user_applied_ai_suggestion",
                "source_agent": change.get("source_agent", "AI"),
            }
            self.containment_relationships.append(containment)
            result["containment_relationship_id"] = containment["id"]

        return True, result

    def _find_relationship(self, source, target, relationship_type):
        for relationship in self.relationships + self.containment_relationships:
            if (
                relationship.get("source") == source
                and relationship.get("target") == target
                and relationship.get("type") == relationship_type
            ):
                return relationship
        return None

    def _new_relationship_id(self, relationship_type, source, target):
        base = self._safe_id(f"reviewed_relationship:{relationship_type}:{source}:{target}")
        existing_ids = {
            r.get("id")
            for r in self.relationships + self.containment_relationships
        }
        return self._unique_id(base, existing_ids)

    def _new_component_id(self, role):
        base = self._safe_id(f"reviewed_component:{role}")
        existing_ids = {
            c.get("id")
            for c in self.components + self.subsystems + self.control_loops
        }
        return self._unique_id(base, existing_ids)

    def _unique_id(self, base, existing_ids):
        if base not in existing_ids:
            return base

        index = 2
        while f"{base}:{index}" in existing_ids:
            index += 1

        return f"{base}:{index}"

    def _safe_id(self, value):
        safe = []
        for char in str(value):
            if char.isalnum() or char in {":", "_", "-", "."}:
                safe.append(char)
            else:
                safe.append("_")
        return "".join(safe)

    def _role_to_display_name(self, role):
        labels = {
            "ReferenceInput": "Reference Input",
            "MeasuredOutput": "Measured Output",
            "LoopManager": "CL Manager",
            "Loop": "Control Loop",
        }
        return labels.get(role, role)


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
