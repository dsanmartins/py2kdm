import argparse, json
from collections import Counter, defaultdict
from pathlib import Path
from kdm_architecture_review.review_model import ReviewFinding, ReviewValidationReport
from kdm_architecture_review.review_rules import (
    ALLOWED_COMPONENT_ROLES, ALLOWED_RELATIONSHIP_TYPES, STANDARD_MAPEK_FLOW,
    OK, WARNING, FORBIDDEN,
)

class ArchitectureReviewValidator:
    COMPLETE_MAPE_ROLES = {"Monitor", "Analyzer", "Planner", "Executor"}
    MANAGING_ROLES = {"Monitor", "Analyzer", "Planner", "Executor", "Knowledge", "LoopManager", "ReferenceInput", "Alternative"}
    MANAGED_ROLES = {"ManagedElement", "Sensor", "Effector"}

    def validate(self, architecture_model: dict, known_code_element_ids: set[str] | None = None) -> ReviewValidationReport:
        known_code_element_ids = known_code_element_ids or set()
        sm = architecture_model.get("structure_model", {})
        components = sm.get("components", [])
        relationships = sm.get("structure_relationships", [])
        loops = sm.get("control_loops", [])
        subsystems = sm.get("subsystems", [])
        ok, warnings, forbidden = [], [], []
        materialized = [c for c in components if c.get("materialize", True) is not False]
        mat_ids = {c.get("id") for c in materialized if c.get("id")}
        all_by_id = {c.get("id"): c for c in components if c.get("id")}
        mat_by_id = {c.get("id"): c for c in materialized if c.get("id")}
        self._validate_components(components, materialized, known_code_element_ids, ok, warnings, forbidden)
        self._validate_relationships(relationships, mat_ids, mat_by_id, all_by_id, ok, warnings, forbidden)
        self._validate_loops(loops, mat_ids, mat_by_id, warnings, forbidden)
        self._validate_subsystems(subsystems, mat_by_id, warnings)
        return ReviewValidationReport(valid=len(forbidden) == 0, ok=ok, warnings=warnings, forbidden=forbidden)

    def _validate_components(self, components, materialized, known_ids, ok, warnings, forbidden):
        ids = [c.get("id") for c in materialized if c.get("id")]
        for cid, count in Counter(ids).items():
            if count > 1:
                forbidden.append(ReviewFinding("ARV-F-02", FORBIDDEN, f"Duplicate materialized component id: {cid}.", cid))
        impl_roles = defaultdict(set)
        for c in components:
            cid, role = c.get("id"), c.get("role")
            if c.get("materialize", True) is False:
                ok.append(ReviewFinding("ARV-OK-02", OK, f"Component {cid} is rejected or not materialized.", cid))
                continue
            if role not in ALLOWED_COMPONENT_ROLES:
                forbidden.append(ReviewFinding("ARV-F-01", FORBIDDEN, f"Invalid component role '{role}'.", cid))
                continue
            if c.get("review_status") in {"accepted", "user_accepted"}:
                ok.append(ReviewFinding("ARV-OK-01", OK, f"Component {cid} was accepted.", cid))
            conf = c.get("confidence")
            if c.get("review_status") in {"accepted", "user_accepted"} and isinstance(conf, (int, float)) and conf < 0.6:
                warnings.append(ReviewFinding("ARV-W-08", WARNING, f"Low-confidence component {cid} was accepted.", cid, {"confidence": conf}))
            impls = c.get("implemented_by", [])
            if not impls:
                warnings.append(ReviewFinding("ARV-W-02", WARNING, f"Component {cid} has no implementation link.", cid))
            for impl in impls:
                impl_roles[impl].add(role)
                if known_ids and impl not in known_ids:
                    warnings.append(ReviewFinding("ARV-W-03", WARNING, f"Implementation reference {impl} could not be resolved.", cid, {"implementation_id": impl}))
        for impl, roles in impl_roles.items():
            if len(roles) > 1:
                warnings.append(ReviewFinding("ARV-W-04", WARNING, f"Code element {impl} implements multiple architectural roles: {', '.join(sorted(roles))}.", impl, {"roles": sorted(roles)}))

    def _validate_relationships(self, relationships, mat_ids, mat_by_id, all_by_id, ok, warnings, forbidden):
        seen = set()
        for r in relationships:
            if r.get("materialize", True) is False:
                continue
            rid, src, tgt, typ = r.get("id"), r.get("source"), r.get("target"), r.get("type")
            if typ not in ALLOWED_RELATIONSHIP_TYPES:
                forbidden.append(ReviewFinding("ARV-F-08", FORBIDDEN, f"Invalid relationship type '{typ}'.", rid)); continue
            if src not in all_by_id:
                forbidden.append(ReviewFinding("ARV-F-03", FORBIDDEN, f"Relationship source does not exist: {src}.", rid)); continue
            if tgt not in all_by_id:
                forbidden.append(ReviewFinding("ARV-F-04", FORBIDDEN, f"Relationship target does not exist: {tgt}.", rid)); continue
            if src not in mat_ids or tgt not in mat_ids:
                forbidden.append(ReviewFinding("ARV-F-05", FORBIDDEN, "A materialized relationship references a non-materialized component.", rid, {"source": src, "target": tgt})); continue
            key = (src, tgt, typ)
            if key in seen:
                forbidden.append(ReviewFinding("ARV-F-10", FORBIDDEN, "Duplicate materialized relationship with the same source, target and type.", rid)); continue
            seen.add(key)
            if r.get("review_status") in {"accepted", "user_accepted"}:
                ok.append(ReviewFinding("ARV-OK-04", OK, f"Relationship {rid} was accepted.", rid))
            sr, tr = mat_by_id[src].get("role"), mat_by_id[tgt].get("role")
            if typ == "uses_knowledge" and tr != "Knowledge":
                forbidden.append(ReviewFinding("ARV-F-07", FORBIDDEN, "uses_knowledge must target a Knowledge component.", rid, {"target_role": tr}))
            if typ == "mapek_flow" and (sr, tr) not in STANDARD_MAPEK_FLOW:
                warnings.append(ReviewFinding("ARV-W-05", WARNING, f"Unusual mapek_flow direction: {sr} -> {tr}.", rid, {"source_role": sr, "target_role": tr}))
            if typ == "mapek_flow" and (sr, tr) == ("Monitor", "Executor"):
                warnings.append(ReviewFinding("ARV-W-06", WARNING, "MAPE-K flow skips intermediate roles.", rid))
            if r.get("source_level") == "technical" and r.get("relationship_level") == "architectural":
                warnings.append(ReviewFinding("ARV-W-07", WARNING, "A technical relationship was promoted to an architectural relationship.", rid))

    def _validate_loops(self, loops, mat_ids, mat_by_id, warnings, forbidden):
        knowledge_usage = defaultdict(set)
        mat_loops = [l for l in loops if l.get("materialize", True) is not False]
        for loop in mat_loops:
            lid = loop.get("id")
            comps = loop.get("components", [])
            mat_comps = [c for c in comps if c in mat_ids]
            if not mat_comps:
                forbidden.append(ReviewFinding("ARV-F-09", FORBIDDEN, f"Control loop {lid} has no materialized components.", lid)); continue
            for cid in comps:
                if cid not in mat_ids:
                    forbidden.append(ReviewFinding("ARV-F-06", FORBIDDEN, f"Control loop {lid} references non-materialized component {cid}.", lid))
            roles = [mat_by_id[c].get("role") for c in mat_comps if c in mat_by_id]
            missing = sorted(self.COMPLETE_MAPE_ROLES - set(roles))
            if missing:
                warnings.append(ReviewFinding("ARV-W-01", WARNING, f"Control loop {lid} is partial. Missing roles: {', '.join(missing)}.", lid, {"missing_roles": missing}))
            repeated = {r: n for r, n in Counter(roles).items() if r in self.COMPLETE_MAPE_ROLES and n > 1}
            if repeated:
                warnings.append(ReviewFinding("ARV-W-09", WARNING, f"Control loop {lid} has multiple components with the same MAPE-K role.", lid, {"repeated_roles": repeated}))
            for cid in mat_comps:
                if mat_by_id.get(cid, {}).get("role") == "Knowledge":
                    knowledge_usage[cid].add(lid)
        for kid, lids in knowledge_usage.items():
            if len(lids) > 1:
                warnings.append(ReviewFinding("ARV-W-10", WARNING, f"Knowledge component {kid} is shared by multiple control loops.", kid, {"control_loops": sorted(lids)}))
        if len(mat_loops) > 1:
            for loop in mat_loops:
                if loop.get("level") is None:
                    warnings.append(ReviewFinding("ARV-W-11", WARNING, "Multiple control loops exist but one has no explicit hierarchy level.", loop.get("id")))

    def _validate_subsystems(self, subsystems, mat_by_id, warnings):
        for s in subsystems:
            roles = {mat_by_id[c].get("role") for c in s.get("components", []) if c in mat_by_id}
            if roles.intersection(self.MANAGING_ROLES) and roles.intersection(self.MANAGED_ROLES):
                warnings.append(ReviewFinding("ARV-W-12", WARNING, f"Subsystem {s.get('id')} mixes managing and managed elements.", s.get("id"), {"roles": sorted(roles)}))

def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f: return json.load(f)
def save_json(data, path):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description="Validate a reviewed architecture JSON model.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = ArchitectureReviewValidator().validate(load_json(args.input)).to_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output: save_json(report, args.output)
    return 0 if report["valid"] else 1
if __name__ == "__main__": raise SystemExit(main())
