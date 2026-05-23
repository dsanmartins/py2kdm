# End-to-End Regression with JSON Schema Validation

This page documents the end-to-end regression test with JSON Schema validation.

The regression flow is:

```text
python_kdm_extractor
        ↓
kdm_architecture_recovery
        ↓
pre-review architecture agents
        ↓
JSON Schema validation
        ↓
pass-through reviewed JSON
        ↓
JSON Schema validation
        ↓
post-review architecture agents
        ↓
JSON Schema validation
        ↓
KDM generator
        ↓
sanity checks over the KDM XMI
```

## Script

```text
scripts/e2e_regression.sh
```

Run:

```bash
bash scripts/e2e_regression.sh --clean
```

## Schema checks

The script validates:

```text
python_model.json                       -> python_model.schema.json
python_model.architecture.json          -> architecture_model.schema.json
python_model.ai_architecture.json       -> ai_architecture_model.schema.json
python_model.reviewed_architecture.json -> reviewed_architecture_model.schema.json
python_model.reviewed.ai_checked.json   -> ai_checked_architecture_model.schema.json
```

## Dependency

```bash
pip install jsonschema
```

This makes the regression test stronger because the JSON artifacts are treated as typed intermediate models, not only as generated files.
