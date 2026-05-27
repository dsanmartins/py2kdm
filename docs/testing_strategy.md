# Testing strategy

Testing combines unit tests, schema validation, KDM validation and end-to-end regression.

## Unit tests

Run:

```bash
pytest
```

Tests should cover extractor behavior, KDM mapping, validation and serialization stability.

## Schema validation

Validate JSON artifacts with:

```bash
python scripts/validate_json_schema.py \
  --input outputs/.../python_model.json \
  --type python
```

or with the appropriate schema type for the artifact being tested.

## Pipeline validation

Run representative pipelines:

```bash
python run_pipeline.py --config configs/demo_java_project.json
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Each run should complete KDM validation and the integrated regression checks.

## End-to-end regression

If the repository keeps a shell-based regression script, run:

```bash
bash scripts/e2e_regression.sh --clean
```

The regression script should follow the current methodology:

```text
extractor
optional dynamic analysis
architecture recovery
pre-review agents
pass-through reviewed JSON for CI only
KDM generation
KDM validation
KDM regression checks
```

It should not run post-review agents because the reviewed model is authoritative after human review.

## What should be protected

Regression checks should protect at least the following:

```text
Java and Python generate valid KDM.
Behavioral relations are present when expected.
No debug attributes reappear.
No executable ActionElement is directly under MethodUnit or CallableUnit.
No return action lacks Reads or return_flow="void".
No SourceRegion lacks file or path.
```
