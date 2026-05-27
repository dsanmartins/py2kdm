# Validation rules

Validation occurs at several points in the pipeline.

## Setup validation

The GUI validates project root, output directory, dynamic scenario scripts, scenario modes, config-file mode, and LLM provider settings.

## Review validation

Before export, the Human Review tab validates the reviewed architecture. Export is disabled until validation is run.

## KDM validation

The KDM generator validates the generated KDM model and reports errors and warnings. If validation fails, the GUI error diagnostic panel summarizes the likely cause.

Typical KDM validation failures include:

```text
ActionElement directly contained by MethodUnit
Return ActionElement without Reads or return_flow
CatchUnit without ExceptionFlow
SourceRegion without file or path
```

## KDM regression checks

After KDM validation, `run_pipeline.py` can run integrated regression checks over the final XMI. These checks make sure that previously fixed issues do not reappear.

The regression checks can verify:

- no debug or redundant attributes;
- no executable actions directly under callables;
- no unresolved return actions;
- no source regions without source information;
- minimum counts for behavioral relations.

See [KDM Regression Checks](kdm_regression_checks.md).

## JSON Schema validation

The script `scripts/validate_json_schema.py` validates JSON artifacts against schemas in `schemas/`.

Example:

```bash
python scripts/validate_json_schema.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --type python
```

Schemas are useful for artifact shape validation, but they do not replace semantic validation in the KDM generator.
