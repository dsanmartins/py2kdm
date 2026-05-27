# Examples and case studies

The repository includes example configurations under `configs/` and example systems under `examples/`.

## demo_java_project

A Java example used to exercise the `java2kdm` extractor and rich Java body mapping.

CLI example:

```bash
python run_pipeline.py --config configs/demo_java_project.json
```

Expected KDM behavior includes:

```text
Calls
Reads
Writes
Creates
Throws
TryUnit
CatchUnit
ExceptionFlow
```

## pymape_hierarchical

A richer Python example used to exercise static extraction, dynamic analysis, MAPE-K recovery, pre-review agents, human review and KDM generation.

CLI example:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Typical GUI workflow:

```bash
python -m py2kdm_gui.main
```

Then:

```text
Configuration -> configure PyMAPE project and scenarios
Process -> Run until Human Review
Human Review -> validate and export reviewed JSON
Process -> Generate final KDM
Artifacts -> inspect outputs
```

## three_layer_system

A compact Python example used for static extraction, architecture recovery and KDM generation.

CLI example:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

## Adding a new project

1. Add the project under `examples/` or point to an external project path.
2. Create a config under `configs/`.
3. Choose the correct `language`: `python` or `java`.
4. Set `outputs.intermediate_json` and `outputs.kdm_xmi`.
5. Enable `kdm_generation`.
6. Optionally enable `regression_check.minimum_counts` if the example is expected to contain behavioral relations.
