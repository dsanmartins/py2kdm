# Development guide

## Recommended development loop

1. Make changes in one module.
2. Run unit tests for that module.
3. Run schema validation on representative outputs.
4. Run the Java and Python pipelines.
5. Check that KDM validation and regression checks pass.
6. Run the GUI for interactive review when UI behavior is affected.
7. Run end-to-end regression before release.

## Representative pipeline commands

```bash
python run_pipeline.py --config configs/demo_java_project.json
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Both commands should end with successful KDM validation and successful KDM regression checks.

## GUI development

Launch the GUI with:

```bash
python -m py2kdm_gui.main
```

The GUI should remain project-agnostic. Project-specific scenario sets should be loaded from config files rather than hardcoded into visible buttons.

## Scripts and temporary tools

Keep stable scripts such as:

- `scripts/e2e_regression.sh`;
- `scripts/validate_json_schema.py`.

Temporary patch or repair scripts, including `tools/fix_*.py` or `scripts/apply_*.py`, should not be kept in the final repository once their changes have been incorporated into the source files.

## Generated folders

Do not commit generated folders such as:

```text
outputs/
site/
target/
__pycache__/
```

## KDM mapper changes

When modifying the KDM mapper, verify both Java and Python. A change that fixes one language must not break the other.

Pay special attention to:

```text
body action containment
return Reads
Reads/Writes
Creates
Throws
TryUnit/CatchUnit/ExceptionFlow
Annotation/Stereotype/TaggedValue modeling
debug attribute cleanup
```
