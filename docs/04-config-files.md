# 4. Project configuration files

Project configuration files define the project under analysis, selected language, input/output artifacts, optional dynamic analysis, architecture recovery, agents and KDM generation.

A typical config lives under `configs/`:

```text
configs/pymape_hierarchical.json
configs/phoneadapter.json
configs/demo_java_project.json
```

## Top-level fields

| Field | Meaning |
|---|---|
| `project_name` | Human-readable project identifier used in reports. |
| `language` | `python`, `java` or an equivalent value used by the pipeline. |
| `input` | Source project paths. |
| `outputs` | Paths to generated JSON/XMI artifacts. |
| `java_extractor` | Java-only extractor settings. |
| `dynamic_analysis` | Python runtime scenario configuration. |
| `architecture_recovery` | Architecture recovery settings. |
| `pre_review_agents` | Deterministic/LLM pre-review settings. |
| `kdm_generation` | KDM generation and regression settings. |

## `input`

Example:

```json
"input": {
  "source_path": "examples/pymape_hierarchical"
}
```

| Key | Meaning |
|---|---|
| `source_path` | Root directory of the project to analyze. |

For Java, this is the project root passed to the `java2kdm` JAR.

## `outputs`

Example:

```json
"outputs": {
  "intermediate_json": "outputs/pymape_hierarchical/python_model.json",
  "runtime_enriched_json": "outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json",
  "architecture_json": "outputs/pymape_hierarchical/python_model.architecture.json",
  "ai_architecture_json": "outputs/pymape_hierarchical/python_model.ai_architecture.json",
  "reviewed_architecture_json": "outputs/pymape_hierarchical/python_model.reviewed_architecture.json",
  "kdm_xmi": "outputs/pymape_hierarchical/model.structure.kdm.xmi"
}
```

| Key | Meaning |
|---|---|
| `intermediate_json` | Static extractor output. |
| `runtime_enriched_json` | Combined runtime-enriched model, when dynamic analysis is used. |
| `architecture_json` | Architecture recovery output. |
| `ai_architecture_json` | Pre-review output with code context and suggestions. |
| `reviewed_architecture_json` | Human-reviewed architecture model. |
| `kdm_xmi` | Target KDM XMI path. |

Not every config needs all output keys. The pipeline uses the keys required by enabled stages.

## `java_extractor`

Example:

```json
"java_extractor": {
  "jar_path": "tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar",
  "schema_path": "schemas/python_model.schema.json"
}
```

| Key | Meaning |
|---|---|
| `jar_path` | Path to the Java extractor JAR. |
| `schema_path` | Schema passed to the extractor or used as shared validation entry point. |

This section is required for Java extraction.

## `dynamic_analysis`

Example:

```json
"dynamic_analysis": {
  "enabled": true,
  "project_root": "examples/pymape_hierarchical",
  "scenarios": [
    {
      "name": "cruise_control",
      "script": "scenarios/cruise_control_scenario.py",
      "mode": "desktop",
      "enabled": true
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `enabled` | Enables runtime analysis for Python. |
| `project_root` | Root used to execute scenario scripts. |
| `scenarios` | List of scenario descriptors. |
| `scenarios[].name` | Scenario identifier. |
| `scenarios[].script` | Scenario script path. |
| `scenarios[].mode` | Scenario execution mode, for example `desktop`. |
| `scenarios[].enabled` | Whether the scenario should be executed. |

For Java projects, dynamic analysis is normally disabled.

## `architecture_recovery`

Example:

```json
"architecture_recovery": {
  "enabled": true,
  "input": "intermediate_json",
  "output": "architecture_json"
}
```

| Key | Meaning |
|---|---|
| `enabled` | Enables architecture recovery. |
| `input` | Artifact selector or path. Usually `intermediate_json` or `runtime_enriched_json`. |
| `output` | Artifact selector or path. Usually `architecture_json`. |

The recovery stage adds `structure_model` to the selected model.

## `pre_review_agents`

Example:

```json
"pre_review_agents": {
  "enabled": true,
  "input": "architecture_json",
  "output": "ai_architecture_json",
  "code_context_input": "intermediate_json",
  "llm_provider": "gemini",
  "llm_model": "gemini-2.5-flash-lite",
  "llm_timeout": 300
}
```

| Key | Meaning |
|---|---|
| `enabled` | Enables pre-review agents. |
| `input` | Architecture JSON to review. |
| `output` | AI/pre-review architecture JSON. |
| `code_context_input` | Code JSON used to build compact code evidence. |
| `llm_provider` | `none`, `gemini` or `ollama`. |
| `llm_model` | Provider-specific model name. |
| `llm_timeout` | Timeout in seconds. |

If dynamic analysis is used, `code_context_input` can point to the runtime-enriched JSON. Otherwise, it should normally point to the static intermediate JSON.

## `kdm_generation`

Example for base KDM:

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
      "Creates": 1
    }
  }
}
```

Example for architecture KDM:

```json
"kdm_generation": {
  "enabled": true,
  "validate": true,
  "input": "architecture_json",
  "output": "outputs/pymape_hierarchical/model.structure.kdm.xmi",
  "regression_check": {
    "enabled": true
  }
}
```

| Key | Meaning |
|---|---|
| `enabled` | Enables KDM generation. |
| `validate` | Runs KDM validation after generation. |
| `input` | `intermediate_json`, `runtime_enriched_json`, `architecture_json` or explicit path. |
| `output` | Optional explicit XMI output path. |
| `regression_check.enabled` | Runs XMI regression checks. |
| `regression_check.minimum_counts` | Optional expected lower bounds for KDM elements/relations. |
| `regression_check.forbidden_attribute_tags` | Optional list of XMI attributes that must not appear. |

## Recommended final configuration pattern

For automatic architecture-oriented KDM generation:

```json
"architecture_recovery": {
  "enabled": true,
  "input": "intermediate_json",
  "output": "architecture_json"
},
"kdm_generation": {
  "enabled": true,
  "validate": true,
  "input": "architecture_json",
  "output": "outputs/<project>/model.structure.kdm.xmi"
}
```

Use `pre_review_agents` only when the optional Human Review workflow is needed.
