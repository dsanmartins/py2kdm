# Pipeline configuration

There are two related configuration formats.

## CLI config

`run_pipeline.py` uses configs such as:

```json
{
  "project_name": "three_layer_system",
  "language": "python",
  "input": {
    "source_path": "examples/three_layer_system"
  },
  "outputs": {
    "intermediate_json": "outputs/three_layer_system/python_model.json",
    "architecture_json": "outputs/three_layer_system/python_model.architecture.json",
    "kdm_xmi": "outputs/three_layer_system/model.kdm.xmi"
  },
  "architecture_recovery": {
    "enabled": true,
    "target_architecture": "mapek"
  },
  "kdm_generation": {
    "enabled": true,
    "validate": true,
    "input": "architecture_json"
  }
}
```

## GUI config

The GUI config stores GUI-specific state:

```json
{
  "project": {
    "name": "pymape_hierarchical",
    "root": "examples/pymape_hierarchical",
    "output_dir": "outputs/pymape_hierarchical"
  },
  "dynamic_analysis": {
    "enabled": true,
    "scenarios": []
  },
  "agents": {
    "llm_provider": "none",
    "llm_model": "",
    "llm_timeout": 300
  }
}
```

## Why two formats?

The CLI config describes batch execution. The GUI config describes the interactive workbench state, including enabled scenarios and LLM settings.
