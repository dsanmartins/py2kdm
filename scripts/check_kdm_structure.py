#!/usr/bin/env python3
"""
KDM StructureModel regression checker for py2kdm.

This checker validates the architectural KDM layer generated from
architecture_json.  It intentionally does not require explicit
inAggregated/outAggregated serialization because those association ends are
KDM derived navigation properties.  Instead, it validates the materialized
AggregatedRelationship elements owned by the from-endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional


XSI_TYPE_SUFFIX = "}type"


def local_name(name: str) -> str:
    if not name:
        return ""
    if "}" in name:
        return name.rsplit("}", 1)[-1]
    if ":" in name:
        return name.rsplit(":", 1)[-1]
    return name


def get_xsi_type(element: ET.Element) -> Optional[str]:
    for key, value in element.attrib.items():
        if key.endswith(XSI_TYPE_SUFFIX) or local_name(key) == "type":
            return local_name(value) if value else None
    return None


TAG_TO_KDM_TYPE = {
    "model": "Model",
    "structureElement": "StructureElement",
    "structureRelationship": "StructureRelationship",
    "aggregatedRelation": "AggregatedRelationship",
    "extensionFamily": "ExtensionFamily",
    "stereotype": "Stereotype",
    "attribute": "Attribute",
}


def classify_element(element: ET.Element) -> Optional[str]:
    xsi_type = get_xsi_type(element)
    if xsi_type:
        return xsi_type
    return TAG_TO_KDM_TYPE.get(local_name(element.tag))


def is_structure_model(element: ET.Element) -> bool:
    return local_name(element.tag) == "model" and get_xsi_type(element) == "StructureModel"


def iter_structure_models(root: ET.Element):
    for element in root.iter():
        if is_structure_model(element):
            yield element


def has_adaptive_domain(root: ET.Element) -> bool:
    for element in root.iter():
        if local_name(element.tag) == "extensionFamily" and element.attrib.get("name") == "Adaptive System Domain":
            return True
    return False


def collect_stereotype_names(root: ET.Element) -> set[str]:
    names: set[str] = set()
    for element in root.iter():
        if local_name(element.tag) == "stereotype":
            name = element.attrib.get("name")
            if name:
                names.add(name)
    return names


def count_structure(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()

    counts: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    components_with_implementation = 0
    components_with_stereotype = 0
    component_names: list[str] = []
    relationship_types: Counter[str] = Counter()
    aggregated_errors: list[str] = []
    aggregated_total = 0
    aggregated_with_required_fields = 0
    explicit_in_out_aggregated = 0

    structure_models = list(iter_structure_models(root))

    for element in root.iter():
        kind = classify_element(element)
        if kind:
            counts[kind] += 1

        if "inAggregated" in element.attrib or "outAggregated" in element.attrib:
            explicit_in_out_aggregated += 1

        if kind == "Component":
            component_names.append(element.attrib.get("name", ""))
            if element.attrib.get("implementation"):
                components_with_implementation += 1
            if element.attrib.get("stereotype"):
                components_with_stereotype += 1
            for child in element:
                if local_name(child.tag) == "attribute" and child.attrib.get("tag") == "role":
                    value = child.attrib.get("value")
                    if value:
                        roles[value] += 1

        if kind == "StructureRelationship":
            for child in element:
                if local_name(child.tag) == "attribute" and child.attrib.get("tag") == "relationship_type":
                    value = child.attrib.get("value")
                    if value:
                        relationship_types[value] += 1

        if kind == "AggregatedRelationship" or local_name(element.tag) == "aggregatedRelation":
            aggregated_total += 1
            missing = [key for key in ("from", "to", "relation", "density") if not element.attrib.get(key)]
            if missing:
                aggregated_errors.append(
                    f"aggregatedRelation missing {', '.join(missing)} at name={element.attrib.get('name', '<unnamed>')}"
                )
            else:
                aggregated_with_required_fields += 1

            density = element.attrib.get("density")
            if density is not None:
                try:
                    if int(density) < 1:
                        aggregated_errors.append(f"aggregatedRelation density must be >= 1, got {density}")
                except ValueError:
                    aggregated_errors.append(f"aggregatedRelation density is not an integer: {density}")

    for key in [
        "StructureModel",
        "SoftwareSystem",
        "ArchitectureView",
        "Subsystem",
        "Component",
        "StructureRelationship",
        "AggregatedRelationship",
        "Attribute",
    ]:
        counts.setdefault(key, 0)

    return {
        "counts": dict(counts),
        "structure_models": len(structure_models),
        "adaptive_domain": has_adaptive_domain(root),
        "stereotype_names": sorted(collect_stereotype_names(root)),
        "roles": dict(roles),
        "relationship_types": dict(relationship_types),
        "components_with_implementation": components_with_implementation,
        "components_with_stereotype": components_with_stereotype,
        "component_names": sorted(set(name for name in component_names if name)),
        "aggregated_total": aggregated_total,
        "aggregated_with_required_fields": aggregated_with_required_fields,
        "aggregated_errors": aggregated_errors,
        "explicit_in_out_aggregated": explicit_in_out_aggregated,
    }


def load_baseline(path: Optional[Path], profile: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if profile and profile in data:
        return data[profile]
    return data.get("default", {})


def check_min_counts(result: dict[str, Any], minimums: dict[str, int]) -> list[str]:
    errors = []
    counts = result["counts"]
    for key, expected_min in minimums.items():
        actual = int(counts.get(key, 0))
        if actual < int(expected_min):
            errors.append(f"{key}: expected >= {expected_min}, got {actual}")
    return errors


def check_required_roles(result: dict[str, Any], required_roles: list[str]) -> list[str]:
    present = set(result.get("roles", {}).keys())
    missing = sorted(set(required_roles) - present)
    if missing:
        return ["required_roles: missing " + ", ".join(missing)]
    return []


def check_required_stereotypes(result: dict[str, Any], required: list[str]) -> list[str]:
    present = set(result.get("stereotype_names", []))
    missing = sorted(set(required) - present)
    if missing:
        return ["required_stereotypes: missing " + ", ".join(missing)]
    return []


def check_min_scalar(result: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors = []
    scalar_minimums = {
        "components_with_implementation": baseline.get("min_components_with_implementation"),
        "components_with_stereotype": baseline.get("min_components_with_stereotype"),
        "aggregated_total": baseline.get("min_aggregated_relationships"),
        "aggregated_with_required_fields": baseline.get("min_aggregated_with_required_fields"),
    }
    for key, expected in scalar_minimums.items():
        if expected is None:
            continue
        actual = int(result.get(key, 0))
        if actual < int(expected):
            errors.append(f"{key}: expected >= {expected}, got {actual}")
    return errors


def run_checks(result: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors += check_min_counts(result, baseline.get("min_counts", {}))
    errors += check_required_roles(result, baseline.get("required_roles", []))
    errors += check_required_stereotypes(result, baseline.get("required_stereotypes", []))
    errors += check_min_scalar(result, baseline)

    if baseline.get("require_structure_model", True) and result.get("structure_models", 0) < 1:
        errors.append("StructureModel: expected at least 1, got 0")

    if baseline.get("require_adaptive_domain", True) and not result.get("adaptive_domain"):
        errors.append("Adaptive System Domain extension family not found")

    if baseline.get("require_aggregated_required_fields", True):
        errors += result.get("aggregated_errors", [])

    if baseline.get("forbid_explicit_in_out_aggregated", True) and result.get("explicit_in_out_aggregated", 0) > 0:
        errors.append(
            "Explicit inAggregated/outAggregated attributes found. These are derived navigation properties and should not be serialized."
        )

    return errors


def print_summary(profile: Optional[str], result: dict[str, Any]) -> None:
    print("KDM structure regression summary:")
    if profile:
        print(f"- Profile: {profile}")
    print(f"- StructureModel: {result.get('structure_models', 0)}")
    print(f"- Adaptive System Domain: {result.get('adaptive_domain')}")

    counts = result["counts"]
    for key in [
        "SoftwareSystem",
        "ArchitectureView",
        "Subsystem",
        "Component",
        "StructureRelationship",
        "AggregatedRelationship",
    ]:
        print(f"- {key}: {counts.get(key, 0)}")

    print(f"- Components with stereotype: {result.get('components_with_stereotype', 0)}")
    print(f"- Components with implementation: {result.get('components_with_implementation', 0)}")
    print(f"- Aggregated relationships with required fields: {result.get('aggregated_with_required_fields', 0)} / {result.get('aggregated_total', 0)}")
    print(f"- Explicit inAggregated/outAggregated attributes: {result.get('explicit_in_out_aggregated', 0)}")

    print("\nRoles:")
    for role, count in sorted(result.get("roles", {}).items()):
        print(f"- {role}: {count}")

    print("\nRelationship types:")
    for rel_type, count in sorted(result.get("relationship_types", {}).items()):
        print(f"- {rel_type}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check KDM StructureModel regression metrics.")
    parser.add_argument("--xmi", required=True, type=Path, help="Path to generated KDM XMI file.")
    parser.add_argument("--profile", default=None, help="Optional baseline profile name.")
    parser.add_argument("--baseline", type=Path, default=None, help="JSON baseline thresholds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    if not args.xmi.exists():
        print(f"ERROR: XMI file not found: {args.xmi}", file=sys.stderr)
        return 2

    result = count_structure(args.xmi)
    baseline = load_baseline(args.baseline, args.profile)
    errors = run_checks(result, baseline)

    if args.json:
        print(json.dumps({"result": result, "errors": errors}, indent=2, ensure_ascii=False))
    else:
        print_summary(args.profile, result)
        if errors:
            print("\nKDM structure regression check FAILED:")
            for error in errors:
                print(f"- {error}")
        else:
            print("\nKDM structure regression check passed.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
