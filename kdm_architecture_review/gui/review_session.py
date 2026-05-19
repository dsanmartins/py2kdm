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
    def relationships(self):
        return self.structure_model.setdefault("structure_relationships", [])

    def get_component(self, component_id):
        return next((c for c in self.components if c.get("id") == component_id), None)

    def get_relationship(self, relationship_id):
        return next((r for r in self.relationships if r.get("id") == relationship_id), None)

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
        if r:
            r["materialize"] = bool(materialize)
            r["review_status"] = "user_accepted" if materialize else "user_rejected"
            self.dirty = True

    def set_relationship_type(self, relationship_id, rel_type):
        r = self.get_relationship(relationship_id)
        if r:
            r["type"] = rel_type
            r["review_status"] = "user_modified"
            self.dirty = True

    def set_relationship_level(self, relationship_id, level):
        r = self.get_relationship(relationship_id)
        if r:
            r["relationship_level"] = level
            r["review_status"] = "user_modified"
            self.dirty = True

    def validate(self):
        if not self.model:
            return {"valid": False, "summary": {"ok": 0, "warnings": 0, "forbidden": 1},
                    "ok": [], "warnings": [], "forbidden": [{"rule_id": "GUI-F-01", "level": "forbidden", "message": "No proposal loaded."}]}
        if ArchitectureReviewValidator is None:
            return {"valid": True, "summary": {"ok": 0, "warnings": 1, "forbidden": 0},
                    "ok": [], "warnings": [{"rule_id": "GUI-W-01", "level": "warning", "message": "Review validator not available."}], "forbidden": []}
        return ArchitectureReviewValidator().validate(self.model).to_dict()

    def _ensure_defaults(self):
        for c in self.components:
            c.setdefault("materialize", True)
        for r in self.relationships:
            r.setdefault("materialize", r.get("relationship_level") == "architectural")
