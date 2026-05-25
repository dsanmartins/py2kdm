# Validation rules

Validation occurs at several points in the pipeline.

## Setup validation

The GUI validates project root, output directory, dynamic scenario scripts, scenario modes, config-file mode, and LLM provider settings.

## Review validation

Before export, the Human Review tab validates the reviewed architecture. Export is disabled until validation is run.

## KDM validation

The KDM generator validates the generated KDM model and reports errors and warnings. If validation fails, the GUI error diagnostic panel summarizes the likely cause.

## JSON Schema validation

The script `scripts/validate_json_schema.py` validates JSON artifacts against schemas in `schemas/`.

Example:

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --type reviewed
```
