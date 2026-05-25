# Pipeline Configuration

The pipeline is configured with a JSON file passed to `run_pipeline.py`.

Example:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

## Minimal configuration

```json
{
  "project_name": "pymape_hierarchical",
  "language": "python",
  "input": {
    "source_path": "examples/pymape_hierarchical"
  },
  "outputs": {
    "intermediate_json": "outputs/pymape_hierarchical/python_model.json",
    "architecture_json": "outputs/pymape_hierarchical/python_model.architecture.json",
    "ai_architecture_json": "outputs/pymape_hierarchical/python_model.ai_architecture.json",
    "runtime_enriched_json": "outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json",
    "kdm_xmi": "outputs/pymape_hierarchical/model.kdm.xmi"
  },
  "architecture_recovery": {
    "enabled": true,
    "mode": "semi_automatic",
    "target_architecture": "mapek"
  },
  "kdm_generation": {
    "enabled": true,
    "validate": true,
    "input": "default"
  }
}
```

## Dynamic analysis configuration

Dynamic analysis is optional and project agnostic. The pipeline does not know the behavior of each project; instead, projects provide scenarios.

```json
{
  "dynamic_analysis": {
    "enabled": true,
    "mode": "desktop",
    "project_root": "examples/pymape_hierarchical",
    "scenarios": [
      {
        "name": "cruise_control",
        "script": "scenarios/cruise_control_scenario.py"
      },
      {
        "name": "hold_distance",
        "script": "scenarios/hold_distance_scenario.py"
      }
    ]
  }
}
```

When enabled, dynamic analysis runs after static extraction and before architecture recovery.

## KDM input selection

`kdm_generation.input` may be:

| Value | Meaning |
|---|---|
| `default` or omitted | Use the latest pipeline artifact. |
| `intermediate_json` | Generate KDM directly from the static intermediate JSON. |
| `architecture_json` | Generate KDM from recovered architecture JSON. |
| `runtime_enriched_json` | Generate KDM from the runtime-enriched CodeModel. |
| explicit path | Use a custom JSON path. |

For the full reviewed workflow, the final KDM generator should receive the reviewed architecture JSON exported by the GUI.

## Command-line overrides

Dynamic analysis can also be enabled from the CLI:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py \
  --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py
```

The pipeline remains generic: scenario contents are project-specific, but scenario execution is handled by the generic dynamic analysis stage.
