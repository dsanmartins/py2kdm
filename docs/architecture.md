# Architecture

`py2kdm` is organized as a set of independent modules connected through JSON artifacts.

## Main modules

| Module | Responsibility |
|---|---|
| `python_kdm_extractor` | Static Python AST extraction into an intermediate JSON model. |
| `kdm_dynamic_analysis` | Runtime tracing and dynamic enrichment of the intermediate model. |
| `kdm_architecture_recovery` | Recovery of architecture-level abstractions and structure relationships. |
| `kdm_architecture_agents` | Pre-review suggestion generation. |
| `py2kdm_gui` | GUI workbench for configuration, execution, review and artifact inspection. |
| `kdm_pyecore_generator` | Generation of KDM XMI from the reviewed JSON model. |
| `run_pipeline.py` | Console orchestrator for reproducible execution. |

## Data flow

```text
Python source project
  -> python_model.json
  -> runtime enriched JSON, optional
  -> architecture JSON
  -> AI architecture JSON, optional
  -> reviewed architecture JSON
  -> KDM XMI
```

## Methodological boundary

The architecture agents operate before human review. They create suggestions but do not replace the human reviewer. After the user exports `python_model.reviewed_architecture.json`, that reviewed model is treated as authoritative and is used directly for KDM generation.

## Project agnosticism

The GUI and pipeline do not hardcode project-specific scenario logic. Dynamic scenarios are provided through configuration or manually through the GUI.
