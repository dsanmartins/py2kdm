#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module="jsonschema.*",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from jsonschema import Draft202012Validator, RefResolver
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: jsonschema. Install with: pip install jsonschema"
    ) from exc


DEFAULT_SCHEMA_MAP = {
    "python": "schemas/python_model.schema.json",
    "architecture": "schemas/architecture_model.schema.json",
    "ai-architecture": "schemas/ai_architecture_model.schema.json",
    "reviewed": "schemas/reviewed_architecture_model.schema.json",
    "ai-checked": "schemas/ai_checked_architecture_model.schema.json",
}


def resolve_path(path):
    path = Path(path)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_store(schema_dir):
    store = {}

    for schema_path in schema_dir.glob("*.schema.json"):
        schema = load_json(schema_path)
        store[schema_path.name] = schema

        if "$id" in schema:
            store[schema["$id"]] = schema

    return store


def validate_json(input_path, schema_path):
    instance = load_json(input_path)
    schema = load_json(schema_path)
    store = build_store(schema_path.parent)

    resolver = RefResolver(
        base_uri=schema_path.resolve().as_uri(),
        referrer=schema,
        store=store,
    )

    validator = Draft202012Validator(schema, resolver=resolver)

    return sorted(
        validator.iter_errors(instance),
        key=lambda error: list(error.path),
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate a py2kdm JSON artifact against a JSON Schema."
    )

    parser.add_argument("--input", required=True, help="Input JSON artifact.")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--schema", help="Path to the JSON Schema.")
    group.add_argument(
        "--type",
        choices=sorted(DEFAULT_SCHEMA_MAP.keys()),
        help="Known model type.",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    input_path = resolve_path(args.input)
    schema_path = (
        resolve_path(DEFAULT_SCHEMA_MAP[args.type])
        if args.type
        else resolve_path(args.schema)
    )

    errors = validate_json(input_path, schema_path)

    if errors:
        print(f"INVALID: {input_path}")
        print(f"Schema: {schema_path}")
        print()

        for error in errors[:50]:
            path = "$"

            for part in error.path:
                path += f"[{part}]" if isinstance(part, int) else f".{part}"

            print(f"- {path}: {error.message}")

        if len(errors) > 50:
            print(f"... {len(errors) - 50} more errors omitted.")

        return 1

    print(f"VALID: {input_path}")
    print(f"Schema: {schema_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
