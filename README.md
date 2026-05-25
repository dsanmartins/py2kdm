# py2kdm

**Author:** [Daniel San Martín](https://www.danielsanmartin.cl/)


`py2kdm` is a model-driven reverse-engineering workbench for Python systems. It extracts a static code model, optionally enriches it with runtime evidence, recovers architecture-level abstractions, supports human review, and generates KDM XMI.

## Current workflow

```text
Python project
  -> static extraction
  -> optional dynamic analysis
  -> architecture recovery
  -> pre-review suggestions
  -> human review
  -> reviewed architecture JSON
  -> final KDM XMI
```

The reviewed architecture is authoritative. Pre-review agents can suggest changes, but no default post-review agent modifies or reinterprets the reviewed model before KDM generation.

## GUI workbench

Launch the GUI with:

```bash
python -m py2kdm_gui.main
```

The GUI has four main tabs:

| Tab | Purpose |
|---|---|
| Configuration | Project setup, dynamic scenarios and agent configuration. |
| Process | Pipeline execution, setup validation, diagnostics, logs and KDM summary. |
| Human Review | Review components, relationships, suggestions and traceability. |
| Artifacts | Inspect generated JSON, trace and XMI files. |

Recommended GUI flow:

```text
Configuration -> Validate setup
Process -> Run until Human Review
Human Review -> Validate -> Export reviewed JSON
Process -> Generate final KDM
Artifacts -> Inspect outputs
```

## Console pipeline

The console pipeline remains available and runs without the GUI:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

With pre-review agents:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review
```

With dynamic analysis from the command line:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## Main artifacts

| Artifact | Description |
|---|---|
| `python_model.json` | Static intermediate model. |
| `runtime_trace.<scenario>.json` | Runtime trace for one scenario. |
| `python_model.runtime_enriched.combined.json` | Static model enriched with runtime evidence. |
| `python_model.runtime_enriched.architecture.json` | Architecture recovery over runtime-enriched model. |
| `python_model.runtime_enriched.ai_architecture.json` | Architecture proposal with pre-review AI suggestions. |
| `python_model.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.reviewed.kdm.xmi` | Final KDM model. |

## Regression check

```bash
bash scripts/e2e_regression.sh --clean
```

The regression script creates a pass-through reviewed JSON only for CI/regression purposes. It does not replace human review in the GUI.

## Scripts folder

Keep:

```text
scripts/e2e_regression.sh
scripts/validate_json_schema.py
```

Temporary patch scripts named `scripts/apply_*.py` can be removed from the final repository.

## Documentation

Build the documentation with MkDocs:

```bash
mkdocs serve
```

The documentation entry point is `docs/index.md`.
