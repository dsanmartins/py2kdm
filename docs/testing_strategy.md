# Testing Strategy

Testing covers static extraction, dynamic enrichment, architecture recovery, agent suggestions, JSON schemas, and KDM generation.

## Unit tests

Run unit tests with:

```bash
pytest
```

Important areas:

- Python extraction edge cases;
- body action mapping;
- semantic KDM relations;
- exception relations;
- return relations;
- serialization stability;
- KDM validation rules.

## JSON schema validation

Validate each major artifact:

```bash
python scripts/validate_json_schema.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --schema schemas/python_model.schema.json
```

Recommended E2E schema checks:

```text
python_model.json
python_model.runtime_enriched.combined.json
python_model.runtime_enriched.architecture.json
python_model.runtime_enriched.ai_architecture.json
python_model.runtime_enriched.reviewed_architecture.json
runtime_trace.<scenario>.json
```

## Dynamic analysis tests

Dynamic scenarios should verify:

- trace status is `completed`;
- event count is greater than zero;
- filtered events are fewer than raw events;
- runtime calls are added;
- observed argument and return types are collected.

Example checks:

```bash
jq '.metadata.execution_status, .metadata.event_count' \
  outputs/pymape_hierarchical/runtime_trace.cruise_control.json

jq '.runtime_enrichment.summary' \
  outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json
```

## KDM generation tests

A successful generator run should show:

```text
=== KDM VALIDATION REPORT ===
Errors: 0
```

Runtime-specific checks:

```bash
grep -c 'xsi:type="action:Calls"' outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi
grep -c 'runtime_call:' outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi
```

## Regression script

The E2E regression should include:

```text
static extraction
optional dynamic analysis
architecture recovery
pre-review agents
schema validation
KDM generation
KDM validation
```

Post-review agents are not part of the default testing path because the reviewed architecture is considered authoritative.
