from pathlib import Path
import argparse
import json
import sys


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]
KDM_ARCHITECTURE_RECOVERY_ROOT = Path(__file__).resolve().parent

for candidate in (PY2KDM_PROJECT_ROOT, KDM_ARCHITECTURE_RECOVERY_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


from py2kdm_common.paths import ensure_parent, resolve_from_root

from kdm_architecture_recovery.architecture_recovery_engine import (
    ArchitectureRecoveryEngine,
)


def default_output_path(input_path: Path) -> Path:
    if input_path.name.endswith(".architecture.json"):
        return input_path

    if input_path.name.endswith(".json"):
        return input_path.with_name(
            input_path.name.replace(".json", ".architecture.json")
        )

    return input_path.with_suffix(".architecture.json")


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: dict, path: Path):
    path = ensure_parent(path)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Recover a candidate self-adaptive architecture from a py2kdm "
            "intermediate JSON model."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input intermediate JSON model.",
    )

    parser.add_argument(
        "--output",
        help=(
            "Output architecture-enriched JSON model. If omitted, the output "
            "path is derived from the input path."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    input_path = resolve_from_root(args.input)
    output_path = (
        resolve_from_root(args.output)
        if args.output
        else default_output_path(input_path)
    )
    output_path = ensure_parent(output_path)

    project_model = load_json(input_path)

    engine = ArchitectureRecoveryEngine()
    enriched_model = engine.enrich_project_model(project_model)

    save_json(enriched_model, output_path)

    recovery = enriched_model.get("architecture_recovery", {})
    applicability = recovery.get("autonomic_applicability", {})

    print("Architecture recovery result:")
    print(f"- decision: {applicability.get('decision')}")
    print(f"- status: {applicability.get('status')}")
    print(f"- score: {applicability.get('score')}")
    print(f"- mapek_recovery: {recovery.get('mapek_recovery')}")
    print(f"- output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
