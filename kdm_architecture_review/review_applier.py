import argparse, copy, json
from pathlib import Path
from kdm_architecture_review.review_validator import ArchitectureReviewValidator

class ArchitectureReviewApplier:
    def apply(self, proposal_model: dict, review_model: dict | None = None):
        review_model = review_model or {}
        model = copy.deepcopy(proposal_model)
        model.setdefault("architecture_review", {}).update({
            "status": "review_applied",
            "source": review_model.get("source", "user_review"),
            "decision": review_model.get("decision", "not_specified"),
            "notes": review_model.get("notes"),
        })
        sm = model.setdefault("structure_model", {})
        sm.setdefault("components", []); sm.setdefault("structure_relationships", [])
        sm.setdefault("control_loops", []); sm.setdefault("subsystems", [])
        self._components(sm, review_model.get("component_overrides", []))
        self._add(sm, "components", review_model.get("additional_components", []), "user_added")
        self._relationships(sm, review_model.get("relationship_overrides", []))
        self._add(sm, "structure_relationships", review_model.get("additional_relationships", []), "user_added")
        self._loops(sm, review_model.get("control_loop_overrides", []))
        self._subsystems(sm, review_model.get("subsystem_overrides", []))
        return model

    def _components(self, sm, overrides):
        by_id = {c.get("id"): c for c in sm.get("components", []) if c.get("id")}
        for o in overrides:
            cid = o.get("component_id") or o.get("id"); c = by_id.get(cid)
            if not c: continue
            d = o.get("decision")
            if d == "accepted": c["materialize"] = True; c["review_status"] = "user_accepted"
            elif d == "rejected": c["materialize"] = False; c["review_status"] = "user_rejected"
            for k in ["role", "name", "implemented_by", "subsystem"]:
                if k in o: c[k] = o[k]; c["review_status"] = "user_modified"
            self._metadata(c, o)

    def _relationships(self, sm, overrides):
        by_id = {r.get("id"): r for r in sm.get("structure_relationships", []) if r.get("id")}
        for o in overrides:
            rid = o.get("relationship_id") or o.get("id"); r = by_id.get(rid)
            if not r: continue
            d = o.get("decision")
            if d == "accepted": r["materialize"] = True; r["review_status"] = "user_accepted"
            elif d == "rejected": r["materialize"] = False; r["review_status"] = "user_rejected"
            for k in ["type", "relationship_level", "source", "target"]:
                if k in o: r[k] = o[k]; r["review_status"] = "user_modified"
            if o.get("promote_to_architectural") is True:
                r["source_level"] = r.get("relationship_level", "technical")
                r["relationship_level"] = "architectural"; r["materialize"] = True; r["review_status"] = "user_promoted"
            self._metadata(r, o)

    def _loops(self, sm, overrides):
        loops = sm.get("control_loops", []); by_id = {l.get("id"): l for l in loops if l.get("id")}
        for o in overrides:
            lid = o.get("control_loop_id") or o.get("id"); l = by_id.get(lid)
            if not l and o.get("action") == "add":
                n = copy.deepcopy(o); n["id"] = lid; n.setdefault("materialize", True); n.setdefault("review_status", "user_added"); loops.append(n); continue
            if not l: continue
            d = o.get("decision")
            if d == "accepted": l["materialize"] = True; l["review_status"] = "user_accepted"
            elif d == "rejected": l["materialize"] = False; l["review_status"] = "user_rejected"
            for k in ["level", "scope", "components", "loop_completeness", "roles_present", "missing_roles"]:
                if k in o: l[k] = o[k]; l["review_status"] = "user_modified"
            self._metadata(l, o)

    def _subsystems(self, sm, overrides):
        subs = sm.get("subsystems", []); by_id = {s.get("id"): s for s in subs if s.get("id")}
        for o in overrides:
            sid = o.get("subsystem_id") or o.get("id"); s = by_id.get(sid)
            if not s and o.get("action") == "add":
                n = copy.deepcopy(o); n["id"] = sid; n.setdefault("components", []); n.setdefault("materialize", True); n.setdefault("review_status", "user_added"); subs.append(n); continue
            if not s: continue
            for k in ["name", "components", "control_loops"]:
                if k in o: s[k] = o[k]; s["review_status"] = "user_modified"
            self._metadata(s, o)

    def _add(self, sm, key, items, status):
        existing = {x.get("id") for x in sm.get(key, [])}
        for item in items:
            if item.get("id") in existing: continue
            n = copy.deepcopy(item); n.setdefault("materialize", True); n.setdefault("source", "user_review"); n.setdefault("status", "user_accepted"); n.setdefault("review_status", status)
            sm[key].append(n); existing.add(n.get("id"))

    def _metadata(self, target, override):
        for src, dst in [("reason", "review_reason"), ("reviewer", "reviewer"), ("notes", "review_notes")]:
            if src in override: target[dst] = override[src]

def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f: return json.load(f)
def save_json(data, path):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Apply architecture review decisions to a proposal.")
    parser.add_argument("--proposal", required=True); parser.add_argument("--review")
    parser.add_argument("--output", required=True); parser.add_argument("--validation-report")
    parser.add_argument("--allow-forbidden", action="store_true")
    args = parser.parse_args()
    reviewed = ArchitectureReviewApplier().apply(load_json(args.proposal), load_json(args.review) if args.review else {})
    report = ArchitectureReviewValidator().validate(reviewed).to_dict()
    if args.validation_report: save_json(report, args.validation_report)
    if not report["valid"] and not args.allow_forbidden:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1
    save_json(reviewed, args.output)
    print(json.dumps(report, indent=2, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
