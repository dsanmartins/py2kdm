# py2kdm

**Author:** [Daniel San Martín](https://www.danielsanmartin.cl/)

`py2kdm` is a model-driven reverse-engineering workbench for generating validated KDM XMI models from **Python and Java** projects. It extracts structural and behavioral information, maps it to KDM using the KDM 1.4 Ecore metamodel, and supports optional runtime evidence, architecture recovery, pre-review suggestions, human review, and integrated KDM regression checks.

## Current capabilities

`py2kdm` currently supports:

- Python static extraction through `python_kdm_extractor`;
- Java static extraction through the external `java2kdm` JAR;
- generation of KDM XMI from intermediate JSON models;
- structural KDM elements such as source files, compilation units, classes, methods, parameters and variables;
- behavioral KDM elements and relations such as `ActionElement`, `BlockUnit`, `Calls`, `Reads`, `Writes`, `Creates`, `Throws`, `TryUnit`, `CatchUnit` and `ExceptionFlow`;
- Java annotations and Python decorators represented through `kdm:Annotation`, `Stereotype` and `TaggedValue`;
- KDM validation and integrated regression checks in the console pipeline;
- optional dynamic analysis, architecture recovery, pre-review AI suggestions and human review.

## Current workflow

For direct KDM generation, the minimal workflow is:

```text
Python or Java project
  -> static extraction
  -> intermediate JSON
  -> KDM XMI generation
  -> KDM validation
  -> KDM regression checks
```

For architecture-oriented studies, the extended workflow is:

```text
Python project
  -> static extraction
  -> optional dynamic analysis
  -> architecture recovery
  -> pre-review suggestions
  -> human review
  -> reviewed architecture JSON
  -> final KDM XMI
  -> KDM validation and regression checks
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

The console pipeline remains available and runs without the GUI.

### Python example

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

### Java example

```bash
python run_pipeline.py --config configs/demo_java_project.json
```

### With pre-review agents

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review
```

### With dynamic analysis

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## KDM regression checks

After KDM generation, the pipeline can run integrated regression checks. These checks protect the model from known regressions, including:

- executable `ActionElement` nodes directly under `MethodUnit` or `CallableUnit`;
- `return` actions without `Reads` or `return_flow="void"`;
- `SourceRegion` elements without `file` or `path`;
- debug or redundant attributes such as `body_id`, `callable_body_id`, `source_call_name`, `constructor_resolution`, `constructor_target`, `resolution`, `unresolved_return_value`, `unresolved_exception_type_target`, `decorators`, `declared_type`, `parameter_kind`, and similar tags.

Example configuration:

```json
"kdm_generation": {
  "enabled": true,
  "validate": true,
  "input": "intermediate_json",
  "regression_check": {
    "enabled": true,
    "minimum_counts": {
      "Reads": 1,
      "Writes": 1,
      "Creates": 1,
      "Throws": 1,
      "TryUnit": 1,
      "CatchUnit": 1,
      "ExceptionFlow": 1
    }
  }
}
```

## Main artifacts

| Artifact | Description |
|---|---|
| `python_model.json` | Intermediate model extracted from Python source code. |
| `java_model.json` | Intermediate model extracted from Java source code by `java2kdm`. |
| `runtime_trace.<scenario>.json` | Runtime trace for one scenario. |
| `python_model.runtime_enriched.combined.json` | Static Python model enriched with runtime evidence. |
| `*.architecture.json` | Architecture recovery output. |
| `*.ai_architecture.json` | Architecture proposal with pre-review AI suggestions. |
| `*.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.kdm.xmi` | Generated KDM XMI model. |

## Scripts folder

Keep stable scripts such as:

```text
scripts/e2e_regression.sh
scripts/validate_json_schema.py
```

Temporary patch or repair scripts, such as `tools/fix_*.py` or `scripts/apply_*.py`, can be removed from the final repository once their changes have been incorporated into the source code.

## Documentation

Build the documentation with MkDocs:

```bash
mkdocs serve
```

The documentation entry point is `docs/index.md`.

If the `material` theme is not installed, install it with:

```bash
pip install mkdocs-material
```

or change the theme in `mkdocs.yml` to `readthedocs` or `mkdocs`.
