#!/usr/bin/env python3
"""
Architecture recovery regression checker for py2kdm.

Validates architecture recovery JSON files produced by
kdm_architecture_recovery/main.py.

It supports both shapes:

1. Root-level applicability:
   {
     "autonomic_applicability": {...},
     "structure_model": {...}
   }

2. Nested applicability:
   {
     "architecture_recovery": {
       "autonomic_applicability": {...},
       "mapek_recovery": "enabled",
       ...
     },
     "structure_model": {...}
   }
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_architecture_recovery(model: Dict[str, Any]) -> Dict[str, Any]:
    return model.get("architecture_recovery") or model.get("architectureRecovery") or {}


def get_applicability(model: Dict[str, Any]) -> Dict[str, Any]:
    root_applicability = (
        model.get("autonomic_applicability")
        or model.get("applicability")
        or model.get("autonomic_applicability_gate")
    )
    if isinstance(root_applicability, dict) and root_applicability:
        return root_applicability

    recovery = get_architecture_recovery(model)
    nested = (
        recovery.get("autonomic_applicability")
        or recovery.get("applicability")
        or recovery.get("autonomic_applicability_gate")
    )
    if isinstance(nested, dict):
        return nested

    return {}


def get_mapek_recovery(model: Dict[str, Any], applicability: Dict[str, Any]) -> Any:
    if "mapek_recovery" in applicability:
        return applicability.get("mapek_recovery")
    if "mapek_recovery" in model:
        return model.get("mapek_recovery")
    recovery = get_architecture_recovery(model)
    return recovery.get("mapek_recovery")


def get_structure_model(model: Dict[str, Any]) -> Dict[str, Any]:
    return model.get("structure_model") or model.get("structureModel") or {}


def get_components(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_structure_model(model).get("components") or []


def get_control_loops(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    structure = get_structure_model(model)
    return structure.get("control_loops") or structure.get("controlLoops") or []


def get_subsystems(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    return get_structure_model(model).get("subsystems") or []


def get_relationships(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    structure = get_structure_model(model)
    return structure.get("structure_relationships") or structure.get("relationships") or []


def normalize_role(role: Any) -> str:
    return "" if role is None else str(role).strip()


def normalize_name(name: Any) -> str:
    if name is None:
        return ""
    text = str(name).strip()
    return text.split(".")[-1] if "." in text else text


def component_name(component: Dict[str, Any]) -> str:
    for key in ("name", "component", "id"):
        value = component.get(key)
        if value:
            return normalize_name(value)

    implemented_by = component.get("implemented_by") or component.get("implementedBy")
    if isinstance(implemented_by, list) and implemented_by:
        return normalize_name(implemented_by[0])

    return ""


def component_role(component: Dict[str, Any]) -> str:
    return normalize_role(
        component.get("role")
        or component.get("mapek_role")
        or component.get("type")
        or component.get("stereotype")
    )


def collect_component_roles(model: Dict[str, Any]) -> Dict[str, Set[str]]:
    result: Dict[str, Set[str]] = {}
    for component in get_components(model):
        name = component_name(component)
        role = component_role(component)
        if name and role:
            result.setdefault(name, set()).add(role)
    return result


def collect_roles(model: Dict[str, Any]) -> Set[str]:
    roles = set()
    for component in get_components(model):
        role = component_role(component)
        if role:
            roles.add(role)

    for loop in get_control_loops(model):
        for role in loop.get("roles_present", []) or loop.get("rolesPresent", []) or []:
            role = normalize_role(role)
            if role:
                roles.add(role)
    return roles


def loop_roles(loop: Dict[str, Any]) -> Set[str]:
    return {
        normalize_role(role)
        for role in (loop.get("roles_present") or loop.get("rolesPresent") or [])
        if normalize_role(role)
    }


def check_applicability(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    applicability = get_applicability(model)

    expected_decision = baseline.get("expected_decision")
    if expected_decision is not None:
        actual = applicability.get("decision")
        if actual != expected_decision:
            errors.append(f"decision: expected {expected_decision!r}, got {actual!r}")

    expected_status = baseline.get("expected_status")
    if expected_status is not None:
        actual = applicability.get("status")
        if actual != expected_status:
            errors.append(f"status: expected {expected_status!r}, got {actual!r}")

    expected_mapek = baseline.get("expected_mapek_recovery")
    if expected_mapek is not None:
        actual = get_mapek_recovery(model, applicability)
        if actual != expected_mapek:
            errors.append(f"mapek_recovery: expected {expected_mapek!r}, got {actual!r}")

    min_score = baseline.get("min_score")
    if min_score is not None:
        actual = float(applicability.get("score", 0.0) or 0.0)
        if actual < float(min_score):
            errors.append(f"score: expected >= {min_score}, got {actual}")

    expected_rules = set(baseline.get("expected_matched_rules", []))
    if expected_rules:
        actual_rules = set(applicability.get("matched_rules", []) or [])
        missing = expected_rules - actual_rules
        if missing:
            errors.append(f"matched_rules: missing {sorted(missing)}")

    return errors


def check_role_coverage(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    roles = collect_roles(model)

    required_roles = set(baseline.get("required_roles", []))
    missing_roles = required_roles - roles
    if missing_roles:
        errors.append(f"required_roles: missing {sorted(missing_roles)}")

    expected_roles_by_component = baseline.get("expected_roles_by_component", {})
    actual_by_component = collect_component_roles(model)

    for name, expected_roles in expected_roles_by_component.items():
        actual_roles = actual_by_component.get(name, set())
        missing = set(expected_roles) - actual_roles
        if missing:
            errors.append(
                f"{name}: missing roles {sorted(missing)}; actual roles {sorted(actual_roles)}"
            )

    optional_roles_by_component = baseline.get("optional_roles_by_component", {})
    for name, optional_roles in optional_roles_by_component.items():
        actual_roles = actual_by_component.get(name, set())
        if actual_roles:
            missing = set(optional_roles) - actual_roles
            if missing:
                errors.append(
                    f"{name}: component exists but is missing roles {sorted(missing)}; "
                    f"actual roles {sorted(actual_roles)}"
                )

    forbidden_roles_by_component = baseline.get("forbidden_roles_by_component", {})
    for name, forbidden_roles in forbidden_roles_by_component.items():
        actual_roles = actual_by_component.get(name, set())
        hits = set(forbidden_roles) & actual_roles
        if hits:
            errors.append(
                f"{name}: forbidden roles present {sorted(hits)}; actual roles {sorted(actual_roles)}"
            )

    return errors


def check_counts(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    checks = [
        ("min_components_count", len(get_components(model)), "components_count"),
        ("min_control_loops_count", len(get_control_loops(model)), "control_loops_count"),
        ("min_subsystems_count", len(get_subsystems(model)), "subsystems_count"),
        ("min_structure_relationships_count", len(get_relationships(model)), "structure_relationships_count"),
    ]

    for baseline_key, actual, label in checks:
        expected_min = baseline.get(baseline_key)
        if expected_min is not None and actual < int(expected_min):
            errors.append(f"{label}: expected >= {expected_min}, got {actual}")
    return errors


def check_control_loops(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    loops = get_control_loops(model)

    if baseline.get("require_complete_loop"):
        required_roles = set(baseline.get("required_loop_roles", baseline.get("required_roles", [])))
        found = False
        for loop in loops:
            completeness = loop.get("loop_completeness") or loop.get("completeness")
            roles = loop_roles(loop)
            if completeness == "complete" and required_roles.issubset(roles):
                found = True
                break
        if not found:
            errors.append(
                "control_loops: no complete loop contains required roles "
                f"{sorted(required_roles)}"
            )

    min_loop_confidence = baseline.get("min_loop_confidence")
    if min_loop_confidence is not None and loops:
        best = max(float(loop.get("confidence", 0.0) or 0.0) for loop in loops)
        if best < float(min_loop_confidence):
            errors.append(f"control_loops: expected best confidence >= {min_loop_confidence}, got {best}")

    return errors


def check_forbidden_components(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    forbidden_names = set(baseline.get("forbidden_component_names", []))
    forbidden_suffixes = tuple(baseline.get("forbidden_component_suffixes", []))
    forbidden_prefixes = tuple(baseline.get("forbidden_component_prefixes", []))

    for component in get_components(model):
        name = component_name(component)
        role = component_role(component)
        if not name:
            continue
        if name in forbidden_names:
            errors.append(f"component {name!r} is forbidden but appears with role {role!r}")
        if forbidden_suffixes and name.endswith(forbidden_suffixes):
            errors.append(f"component {name!r} has forbidden suffix and appears with role {role!r}")
        if forbidden_prefixes and name.startswith(forbidden_prefixes):
            errors.append(f"component {name!r} has forbidden prefix and appears with role {role!r}")

    return errors


def print_summary(model: Dict[str, Any], profile: str | None) -> None:
    applicability = get_applicability(model)
    mapek_recovery = get_mapek_recovery(model, applicability)
    components = get_components(model)
    loops = get_control_loops(model)
    subsystems = get_subsystems(model)
    relationships = get_relationships(model)
    roles = collect_roles(model)
    by_component = collect_component_roles(model)

    print("Architecture recovery regression summary:")
    print(f"- Project: {model.get('projectName')}")
    print(f"- Language: {model.get('language')}")
    if profile:
        print(f"- Profile: {profile}")
    print(f"- Decision: {applicability.get('decision')}")
    print(f"- Status: {applicability.get('status')}")
    print(f"- Score: {applicability.get('score')}")
    print(f"- MAPE-K recovery: {mapek_recovery}")
    print(f"- Components: {len(components)}")
    print(f"- Control loops: {len(loops)}")
    print(f"- Subsystems: {len(subsystems)}")
    print(f"- Relationships: {len(relationships)}")
    print(f"- Roles: {', '.join(sorted(roles))}")

    print("\nComponent roles:")
    for name in sorted(by_component):
        print(f"- {name}: {', '.join(sorted(by_component[name]))}")

    if loops:
        print("\nControl loops:")
        for idx, loop in enumerate(loops, start=1):
            completeness = loop.get("loop_completeness") or loop.get("completeness")
            confidence = loop.get("confidence")
            roles_present = sorted(loop_roles(loop))
            print(
                f"- loop #{idx}: completeness={completeness}, "
                f"confidence={confidence}, roles={roles_present}"
            )


def load_baseline(path: Path | None, profile: str | None) -> Dict[str, Any]:
    if path is None:
        return {}
    data = load_json(path)
    if profile and profile in data:
        return data[profile]
    return data.get("default", data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check architecture recovery regression metrics.")
    parser.add_argument("--architecture", required=True, type=Path, help="Architecture recovery JSON file.")
    parser.add_argument("--profile", default=None, help="Baseline profile name.")
    parser.add_argument("--baseline", type=Path, default=None, help="Architecture recovery baseline JSON.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")
    args = parser.parse_args()

    try:
        model = load_json(args.architecture)
        baseline = load_baseline(args.baseline, args.profile)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors: List[str] = []
    errors.extend(check_applicability(model, baseline))
    errors.extend(check_role_coverage(model, baseline))
    errors.extend(check_counts(model, baseline))
    errors.extend(check_control_loops(model, baseline))
    errors.extend(check_forbidden_components(model, baseline))

    if args.json:
        print(json.dumps({"errors": errors, "passed": not errors}, indent=2, ensure_ascii=False))
    else:
        print_summary(model, args.profile)
        if errors:
            print("\nArchitecture recovery regression check FAILED:")
            for error in errors:
                print(f"- {error}")
        else:
            print("\nArchitecture recovery regression check passed.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
