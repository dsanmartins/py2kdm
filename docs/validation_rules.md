# Validation Rules

Validation occurs at two levels:

1. JSON artifact validation through JSON Schema.
2. KDM model validation after XMI generation.

## JSON validation

JSON Schemas are stored under `schemas/` and can be checked with:

```bash
python scripts/validate_json_schema.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --schema schemas/python_model.schema.json
```

Important schemas include:

| Artifact | Schema |
|---|---|
| Static intermediate model | `python_model.schema.json` |
| Architecture model | `architecture_model.schema.json` |
| AI-enriched architecture | `ai_architecture_model.schema.json` |
| Reviewed architecture | `reviewed_architecture_model.schema.json` |
| Runtime trace | `runtime_trace.schema.json` |

## Basic model validation

The generator checks unresolved static calls and reports warnings such as:

```text
Call without target_id: car.gas in ...gas_brake
```

When runtime evidence exists, the runtime-aware validator can classify some of these calls as resolved by runtime evidence instead of reporting them as unresolved warnings.

## KDM validation

The KDM validator checks structural consistency of the generated KDM model:

- valid containment of `ActionElement` inside `BlockUnit` bodies;
- valid `Calls`, `Creates`, `Reads`, and `Writes` targets;
- absence of duplicated child actions in a body block;
- source-region consistency;
- expected CodeModel, InventoryModel, and StructureModel elements.

A successful KDM validation report should contain:

```text
=== KDM VALIDATION REPORT ===
Errors: 0
```

Warnings may remain for cases such as constructor-like actions without an explicit `Creates` relation.

## Runtime-specific validation

Runtime calls are validated semantically as KDM `action::Calls`. The generator tracks:

```text
Runtime Calls created
Runtime Calls skipped as duplicates
Runtime Calls unresolved
```

Unresolved runtime calls usually indicate that a runtime endpoint could not be matched to an existing static CodeItem. This may happen for external libraries, dynamically generated functions, or filtered scenario helpers.
