#!/usr/bin/env python3
"""
KDM regression checker for py2kdm.

This version checks noisy external names only as direct library roots of
ExternalLibraries_CodeModel. It does not flag valid nested targets such as
CallableUnit name="super" under a builtins library, nor valid project
ParameterUnit name="self".
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional


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
    "segment": "Segment",
    "model": "Model",
    "inventoryElement": "InventoryElement",
    "codeElement": "CodeElement",
    "actionElement": "ActionElement",
    "parameterUnit": "ParameterUnit",
    "source": "SourceRef",
    "region": "SourceRegion",
    "codeRelation": "CodeRelation",
    "actionRelation": "ActionRelation",
    "attribute": "Attribute",
}


def classify_element(element: ET.Element) -> Optional[str]:
    xsi_type = get_xsi_type(element)
    if xsi_type:
        return xsi_type
    return TAG_TO_KDM_TYPE.get(local_name(element.tag))


def has_direct_source_region(element: ET.Element) -> bool:
    for child in list(element):
        if local_name(child.tag) != "source":
            continue
        for grandchild in list(child):
            if local_name(grandchild.tag) == "region":
                return True
            if classify_element(grandchild) == "SourceRegion":
                return True
        if any(local_name(k) in {"startLine", "line", "endLine"} for k in child.attrib):
            return True
    return False


def count_kdm(path: Path) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()

    counts: Counter[str] = Counter()
    source_region_coverage: Dict[str, Dict[str, int]] = {}

    tracked_for_source = {
        "ClassUnit",
        "MethodUnit",
        "CallableUnit",
        "ParameterUnit",
        "StorableUnit",
        "ActionElement",
        "BlockUnit",
        "TryUnit",
        "CatchUnit",
        "FinallyUnit",
    }

    for element in root.iter():
        kind = classify_element(element)
        if not kind:
            continue

        counts[kind] += 1

        if kind in tracked_for_source:
            coverage = source_region_coverage.setdefault(kind, {"total": 0, "with_source_region": 0})
            coverage["total"] += 1
            if has_direct_source_region(element):
                coverage["with_source_region"] += 1

    important = [
        "Segment", "InventoryModel", "SourceFile", "CodeModel", "Package",
        "CompilationUnit", "ClassUnit", "MethodUnit", "CallableUnit",
        "ParameterUnit", "StorableUnit", "ActionElement", "BlockUnit",
        "TryUnit", "CatchUnit", "FinallyUnit", "Imports", "Extends",
        "Implements", "Calls", "Creates", "Reads", "Writes", "Throws",
        "ExceptionFlow", "ExitFlow", "HasType", "HasValue", "Value",
        "Attribute",
    ]
    for key in important:
        counts.setdefault(key, 0)

    return {
        "counts": dict(counts),
        "source_region_coverage": source_region_coverage,
    }


def load_baseline(path: Optional[Path], language: str, profile: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if profile and profile in data:
        return data[profile]
    return data.get(language, {})


def check_min_counts(counts: Dict[str, int], minimums: Dict[str, int]) -> list[str]:
    errors = []
    for key, expected_min in minimums.items():
        actual = int(counts.get(key, 0))
        if actual < int(expected_min):
            errors.append(f"{key}: expected >= {expected_min}, got {actual}")
    return errors


def check_source_coverage(coverage: Dict[str, Dict[str, int]], minimums: Dict[str, int]) -> list[str]:
    errors = []
    for kind, expected_min in minimums.items():
        actual = int(coverage.get(kind, {}).get("with_source_region", 0))
        if actual < int(expected_min):
            errors.append(f"{kind} with SourceRegion: expected >= {expected_min}, got {actual}")
    return errors


def find_models_by_name(root: ET.Element, model_names: list[str]) -> list[ET.Element]:
    wanted = set(model_names)
    result = []
    for element in root.iter():
        if local_name(element.tag) == "model" or classify_element(element) == "CodeModel":
            if element.attrib.get("name") in wanted:
                result.append(element)
    return result


def direct_named_code_children(element: ET.Element):
    for child in list(element):
        if local_name(child.tag) != "codeElement":
            continue
        name = child.attrib.get("name")
        if name is not None:
            yield child, name


def check_forbidden_names_global(path: Path, forbidden: list[str]) -> list[str]:
    if not forbidden:
        return []

    tree = ET.parse(path)
    root = tree.getroot()
    forbidden_set = set(forbidden)
    hits = []

    for element in root.iter():
        name = element.attrib.get("name")
        if name in forbidden_set:
            kind = classify_element(element) or local_name(element.tag)
            hits.append(f'{kind} name="{name}" is forbidden')
    return hits


def check_forbidden_direct_library_roots(path: Path, model_names: list[str], forbidden: list[str]) -> list[str]:
    if not model_names or not forbidden:
        return []

    tree = ET.parse(path)
    root = tree.getroot()
    forbidden_set = set(forbidden)
    hits = []

    for model in find_models_by_name(root, model_names):
        model_name = model.attrib.get("name", "<unnamed>")
        for element, name in direct_named_code_children(model):
            if name in forbidden_set:
                kind = classify_element(element) or local_name(element.tag)
                hits.append(f'{model_name}: direct library root {kind} name="{name}" is forbidden')
    return hits


def check_forbidden_direct_library_prefixes(path: Path, model_names: list[str], prefixes: list[str]) -> list[str]:
    if not model_names or not prefixes:
        return []

    tree = ET.parse(path)
    root = tree.getroot()
    hits = []

    for model in find_models_by_name(root, model_names):
        model_name = model.attrib.get("name", "<unnamed>")
        for element, name in direct_named_code_children(model):
            for prefix in prefixes:
                if name.startswith(prefix):
                    kind = classify_element(element) or local_name(element.tag)
                    hits.append(
                        f'{model_name}: direct library root {kind} name="{name}" '
                        f'has forbidden prefix "{prefix}"'
                    )
                    break
    return hits


def print_summary(language: str, profile: Optional[str], result: Dict[str, Any]) -> None:
    counts = result["counts"]
    coverage = result["source_region_coverage"]

    print("KDM regression summary:")
    print(f"- Language: {language}")
    if profile:
        print(f"- Profile: {profile}")

    for key in [
        "SourceFile", "Package", "CompilationUnit", "ClassUnit",
        "MethodUnit", "CallableUnit", "ParameterUnit", "StorableUnit",
        "ActionElement", "BlockUnit", "Imports", "Extends", "Implements",
        "Calls", "Creates", "Reads", "Writes", "Throws", "ExceptionFlow",
        "ExitFlow", "HasType", "HasValue",
    ]:
        print(f"- {key}: {counts.get(key, 0)}")

    print("\nSourceRegion coverage:")
    for kind in [
        "ClassUnit", "MethodUnit", "CallableUnit", "ParameterUnit",
        "StorableUnit", "ActionElement", "TryUnit", "CatchUnit",
    ]:
        c = coverage.get(kind, {"total": 0, "with_source_region": 0})
        print(f"- {kind}: {c['with_source_region']} / {c['total']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check KDM XMI regression metrics.")
    parser.add_argument("--xmi", required=True, type=Path, help="Path to generated KDM XMI file.")
    parser.add_argument("--language", required=True, choices=["python", "java"], help="Model language.")
    parser.add_argument("--profile", default=None, help="Optional baseline profile name.")
    parser.add_argument("--baseline", type=Path, default=None, help="JSON baseline thresholds.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary.")
    args = parser.parse_args()

    if not args.xmi.exists():
        print(f"ERROR: XMI file not found: {args.xmi}", file=sys.stderr)
        return 2

    result = count_kdm(args.xmi)
    baseline = load_baseline(args.baseline, args.language, args.profile)

    errors: list[str] = []
    errors += check_min_counts(result["counts"], baseline.get("min_counts", {}))
    errors += check_source_coverage(result["source_region_coverage"], baseline.get("min_source_region", {}))
    errors += check_forbidden_names_global(args.xmi, baseline.get("forbidden_names_global", []))

    external_root_rule = baseline.get("forbidden_external_library_roots", {})
    errors += check_forbidden_direct_library_roots(
        args.xmi,
        external_root_rule.get("model_names", []),
        external_root_rule.get("names", []),
    )

    external_prefix_rule = baseline.get("forbidden_external_library_prefixes", {})
    errors += check_forbidden_direct_library_prefixes(
        args.xmi,
        external_prefix_rule.get("model_names", []),
        external_prefix_rule.get("prefixes", []),
    )

    if args.json:
        print(json.dumps({"result": result, "errors": errors}, indent=2, ensure_ascii=False))
    else:
        print_summary(args.language, args.profile, result)
        if errors:
            print("\nRegression check FAILED:")
            for error in errors:
                print(f"- {error}")
        else:
            print("\nRegression check passed.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
