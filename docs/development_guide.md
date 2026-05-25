# Development guide

## Recommended development loop

1. Make changes in one module.
2. Run unit tests for that module.
3. Run schema validation on representative outputs.
4. Run the GUI for interactive review when UI behavior is affected.
5. Run `scripts/e2e_regression.sh` before release.

## GUI development

Launch the GUI with:

```bash
python -m py2kdm_gui.main
```

The GUI should remain project-agnostic. Project-specific scenario sets should be loaded from config files rather than hardcoded into visible buttons.

## Scripts folder

Keep these scripts:

- `scripts/e2e_regression.sh`;
- `scripts/validate_json_schema.py`.

Patch-application scripts named `scripts/apply_*.py` were temporary during development and should not be kept in the final repository.

## Generated folders

Do not commit:

- `__pycache__/`;
- generated outputs unless they are intentional fixtures;
- local `.env` files containing API keys.
