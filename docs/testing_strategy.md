# Testing strategy

Testing combines unit tests, schema validation and end-to-end regression.

## Unit tests

Run:

```bash
pytest
```

Tests cover extractor behavior, KDM mapping, validation and serialization stability.

## Schema validation

Validate JSON artifacts with:

```bash
python scripts/validate_json_schema.py --input outputs/.../python_model.json --type python
```

## End-to-end regression

Run:

```bash
bash scripts/e2e_regression.sh --clean
```

The regression script now follows the current methodology:

```text
extractor
architecture recovery
pre-review agents
pass-through reviewed JSON for CI only
KDM generation from reviewed JSON
sanity checks over KDM XMI
```

It does not run post-review agents because the reviewed model is authoritative after human review.
