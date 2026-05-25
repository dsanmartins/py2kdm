# JSON Schemas

JSON Schemas define the structure of pipeline artifacts and support regression validation.

## Available schemas

| Schema | Artifact |
|---|---|
| `python_model.schema.json` | Static intermediate JSON. |
| `architecture_model.schema.json` | Recovered architecture JSON. |
| `ai_architecture_model.schema.json` | AI-enriched pre-review architecture JSON. |
| `reviewed_architecture_model.schema.json` | Human-reviewed architecture JSON. |
| `ai_checked_architecture_model.schema.json` | Legacy compatibility schema for AI-checked outputs. |
| `runtime_trace.schema.json` | Runtime trace JSON. |

## Validation command

```bash
python scripts/validate_json_schema.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json \
  --schema schemas/python_model.schema.json
```

## Schema design

Schemas should validate structural consistency but should not enforce project-specific architecture choices. For example, a MAPE-K project may or may not expose an explicit Analyzer component.

## Runtime-enriched models

Runtime-enriched models still conform to the intermediate JSON schema, with additional fields such as:

```text
relationships[type="runtime_calls"]
runtime_enrichment
```

## Reviewed architecture

The reviewed architecture schema validates the artifact that feeds final KDM generation after human review.
