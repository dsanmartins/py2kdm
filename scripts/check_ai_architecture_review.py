#!/usr/bin/env python3
"""
AI architecture review regression checker for py2kdm.

This checker validates the pre-review agents output, usually:

outputs/<project>/<model>.ai_architecture.json

It focuses on the non-invasive review layer:

- compact code_context availability;
- deterministic_code_review availability;
- architecture_assessment status/confidence;
- unsupported architecture roles;
- role confirmations for key components.

Example:

python scripts/check_ai_architecture_review.py \
  --ai-architecture outputs/phoneadapter/java_model.ai_architecture.json \
  --profile phoneadapter \
  --baseline configs/ai_architecture_review_baselines.json
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


def get_ai_enrichment(model: Dict[str, Any]) -> Dict[str, Any]:
    return model.get("ai_enrichment") or model.get("aiEnrichment") or {}


def get_code_context(model: Dict[str, Any]) -> Dict[str, Any]:
    ai = get_ai_enrichment(model)
    return ai.get("code_context") or ai.get("codeContext") or {}


def get_deterministic_review(model: Dict[str, Any]) -> Dict[str, Any]:
    ai = get_ai_enrichment(model)
    return (
        ai.get("deterministic_code_review")
        or ai.get("deterministicCodeReview")
        or {}
    )


def get_assessment(model: Dict[str, Any]) -> Dict[str, Any]:
    review = get_deterministic_review(model)
    return review.get("architecture_assessment") or review.get("architectureAssessment") or {}


def get_summary(model: Dict[str, Any]) -> Dict[str, Any]:
    review = get_deterministic_review(model)
    return review.get("summary") or {}


def get_role_confirmations(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    review = get_deterministic_review(model)
    return review.get("role_confirmations") or review.get("roleConfirmations") or []


def get_unsupported_roles(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    review = get_deterministic_review(model)
    return (
        review.get("unsupported_architecture_roles")
        or review.get("unsupportedArchitectureRoles")
        or []
    )


def normalize_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text.split(".")[-1] if "." in text else text


def normalize_role(value: Any) -> str:
    return "" if value is None else str(value).strip()


def collect_confirmed_roles(model: Dict[str, Any]) -> Dict[str, Set[str]]:
    result: Dict[str, Set[str]] = {}

    for confirmation in get_role_confirmations(model):
        component = normalize_name(
            confirmation.get("component")
            or confirmation.get("class")
            or confirmation.get("name")
            or confirmation.get("qualified_name")
        )
        qualified_name = confirmation.get("qualified_name")
        roles = {
            normalize_role(role)
            for role in confirmation.get("confirmed_roles", []) or []
            if normalize_role(role)
        }

        if component:
            result.setdefault(component, set()).update(roles)
        if qualified_name:
            result.setdefault(normalize_name(qualified_name), set()).update(roles)
            result.setdefault(str(qualified_name), set()).update(roles)

    # Also read class_reviews because some roles may be confirmed there even if
    # role_confirmations formatting changes in the future.
    review = get_deterministic_review(model)
    for class_review in review.get("class_reviews", []) or review.get("classReviews", []) or []:
        class_name = normalize_name(class_review.get("class") or class_review.get("name"))
        qualified_name = class_review.get("qualified_name")
        roles = {
            normalize_role(role)
            for role in class_review.get("confirmed_roles", []) or []
            if normalize_role(role)
        }
        if class_name:
            result.setdefault(class_name, set()).update(roles)
        if qualified_name:
            result.setdefault(normalize_name(qualified_name), set()).update(roles)
            result.setdefault(str(qualified_name), set()).update(roles)

    return result


def check_code_context(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    code_context = get_code_context(model)
    summary = get_summary(model)

    if baseline.get("require_code_context"):
        available = bool(code_context.get("available")) or bool(summary.get("code_context_available"))
        if not available:
            errors.append("code_context: expected available == true")

    min_classes = baseline.get("min_code_context_classes")
    if min_classes is not None:
        classes_count = len(code_context.get("classes", []) or [])
        summary_count = int(summary.get("code_context_classes", classes_count) or classes_count)
        actual = max(classes_count, summary_count)
        if actual < int(min_classes):
            errors.append(f"code_context_classes: expected >= {min_classes}, got {actual}")

    required_classes = set(baseline.get("required_code_context_classes", []))
    if required_classes:
        actual_classes = {
            normalize_name(cls.get("name") or cls.get("qualified_name"))
            for cls in code_context.get("classes", []) or []
        }
        missing = required_classes - actual_classes
        if missing:
            errors.append(f"code_context.classes: missing {sorted(missing)}")

    return errors


def check_deterministic_review(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    review = get_deterministic_review(model)
    assessment = get_assessment(model)

    expected_review_status = baseline.get("expected_review_status")
    if expected_review_status is not None:
        actual = review.get("status")
        if actual != expected_review_status:
            errors.append(f"deterministic_code_review.status: expected {expected_review_status!r}, got {actual!r}")

    expected_assessment_status = baseline.get("expected_assessment_status")
    if expected_assessment_status is not None:
        actual = assessment.get("status")
        if actual != expected_assessment_status:
            errors.append(f"architecture_assessment.status: expected {expected_assessment_status!r}, got {actual!r}")

    expected_candidate = baseline.get("expected_autonomic_candidate")
    if expected_candidate is not None:
        actual = assessment.get("is_autonomic_system_candidate")
        if actual != expected_candidate:
            errors.append(
                "architecture_assessment.is_autonomic_system_candidate: "
                f"expected {expected_candidate!r}, got {actual!r}"
            )

    min_confidence = baseline.get("min_assessment_confidence")
    if min_confidence is not None:
        actual = float(assessment.get("confidence", 0.0) or 0.0)
        if actual < float(min_confidence):
            errors.append(f"architecture_assessment.confidence: expected >= {min_confidence}, got {actual}")

    max_unsupported = baseline.get("max_unsupported_architecture_roles")
    if max_unsupported is not None:
        actual = len(get_unsupported_roles(model))
        if actual > int(max_unsupported):
            errors.append(f"unsupported_architecture_roles: expected <= {max_unsupported}, got {actual}")

    required_core_roles = set(baseline.get("required_confirmed_core_roles", []))
    if required_core_roles:
        confirmed = set(assessment.get("confirmed_core_roles", []) or [])
        missing = required_core_roles - confirmed
        if missing:
            errors.append(f"architecture_assessment.confirmed_core_roles: missing {sorted(missing)}")

    return errors


def check_role_confirmations(model: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    confirmed_by_component = collect_confirmed_roles(model)

    expected_roles_by_component = baseline.get("expected_confirmed_roles_by_component", {})
    for component, expected_roles in expected_roles_by_component.items():
        actual_roles = confirmed_by_component.get(component, set())
        missing = set(expected_roles) - actual_roles
        if missing:
            errors.append(
                f"{component}: missing confirmed roles {sorted(missing)}; "
                f"actual confirmed roles {sorted(actual_roles)}"
            )

    forbidden_roles_by_component = baseline.get("forbidden_confirmed_roles_by_component", {})
    for component, forbidden_roles in forbidden_roles_by_component.items():
        actual_roles = confirmed_by_component.get(component, set())
        hits = set(forbidden_roles) & actual_roles
        if hits:
            errors.append(
                f"{component}: forbidden confirmed roles {sorted(hits)}; "
                f"actual confirmed roles {sorted(actual_roles)}"
            )

    return errors


def print_summary(model: Dict[str, Any], profile: str | None) -> None:
    code_context = get_code_context(model)
    review = get_deterministic_review(model)
    assessment = get_assessment(model)
    summary = get_summary(model)
    unsupported = get_unsupported_roles(model)
    confirmed_by_component = collect_confirmed_roles(model)

    classes_count = len(code_context.get("classes", []) or [])
    summary_classes = summary.get("code_context_classes", classes_count)

    print("AI architecture review regression summary:")
    print(f"- Project: {model.get('projectName')}")
    print(f"- Language: {model.get('language')}")
    if profile:
        print(f"- Profile: {profile}")
    print(f"- Code context available: {bool(code_context.get('available')) or bool(summary.get('code_context_available'))}")
    print(f"- Code context classes: {summary_classes}")
    print(f"- Deterministic review status: {review.get('status')}")
    print(f"- Assessment status: {assessment.get('status')}")
    print(f"- Is autonomic candidate: {assessment.get('is_autonomic_system_candidate')}")
    print(f"- Assessment confidence: {assessment.get('confidence')}")
    print(f"- Unsupported architecture roles: {len(unsupported)}")
    print(f"- Confirmed core roles: {', '.join(assessment.get('confirmed_core_roles', []) or [])}")

    print("\nConfirmed roles by component:")
    for component in sorted(confirmed_by_component):
        print(f"- {component}: {', '.join(sorted(confirmed_by_component[component]))}")


def load_baseline(path: Path | None, profile: str | None) -> Dict[str, Any]:
    if path is None:
        return {}
    data = load_json(path)
    if profile and profile in data:
        return data[profile]
    return data.get("default", data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AI architecture pre-review regression metrics.")
    parser.add_argument("--ai-architecture", required=True, type=Path, help="AI architecture JSON file.")
    parser.add_argument("--profile", default=None, help="Baseline profile name.")
    parser.add_argument("--baseline", type=Path, default=None, help="AI architecture review baseline JSON.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")
    args = parser.parse_args()

    try:
        model = load_json(args.ai_architecture)
        baseline = load_baseline(args.baseline, args.profile)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors: List[str] = []
    errors.extend(check_code_context(model, baseline))
    errors.extend(check_deterministic_review(model, baseline))
    errors.extend(check_role_confirmations(model, baseline))

    if args.json:
        print(json.dumps({"errors": errors, "passed": not errors}, indent=2, ensure_ascii=False))
    else:
        print_summary(model, args.profile)
        if errors:
            print("\nAI architecture review regression check FAILED:")
            for error in errors:
                print(f"- {error}")
        else:
            print("\nAI architecture review regression check passed.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
