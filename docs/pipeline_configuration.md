# Pipeline configuration

`run_pipeline.py` uses JSON configuration files. The same pipeline supports Python and Java projects.

## Python CLI config

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
    "kdm_xmi": "outputs/pymape_hierarchical/model.kdm.xmi"
  },
  "architecture_recovery": {
    "enabled": false
  },
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
}
```

## Java CLI config

```json
{
  "project_name": "demo-java-project",
  "language": "java",
  "input": {
    "source_path": "../demo-java-project"
  },
  "outputs": {
    "intermediate_json": "outputs/demo-java-project/java_model.json",
    "kdm_xmi": "outputs/demo-java-project/model.kdm.xmi"
  },
  "java_extractor": {
    "jar_path": "tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar",
    "schema_path": "schemas/python_model.schema.json"
  },
  "architecture_recovery": {
    "enabled": false
  },
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
}
```

## KDM input selector

`kdm_generation.input` can be:

| Value | Meaning |
|---|---|
| `intermediate_json` | Use the static or runtime-enriched intermediate model. |
| `architecture_json` | Use the architecture recovery output. |
| `runtime_enriched_json` | Use the model enriched by dynamic analysis. |
| explicit path | Use a custom JSON file. |

## Regression check options

The `regression_check` section is optional. When enabled, it can define:

| Key | Meaning |
|---|---|
| `enabled` | Enables or disables integrated KDM regression checks. |
| `minimum_counts` | Optional lower bounds for KDM element/relation counts. |
| `forbidden_attribute_tags` | Optional custom list of forbidden XMI attribute tags. |

If no custom list is provided, the pipeline checks the default set of debug and redundant attributes.
