# Architecture

`py2kdm` is organized as a set of independent pipeline stages. Each stage produces an explicit artifact that can be inspected, validated, or reused by later stages.

```text
python_kdm_extractor
  -> python_model.json

kdm_dynamic_analysis   optional
  -> runtime_trace.<scenario>.json
  -> python_model.runtime_enriched.combined.json

kdm_architecture_recovery
  -> python_model.runtime_enriched.architecture.json

kdm_architecture_agents   optional pre-review
  -> python_model.runtime_enriched.ai_architecture.json

kdm_architecture_review   human review
  -> python_model.runtime_enriched.reviewed_architecture.json

kdm_pyecore_generator
  -> model.runtime_enriched.reviewed.kdm.xmi
```

## Design principles

### CodeModel is factual

The code-level model is built from static analysis and optional runtime evidence. It should represent facts about the program, such as code elements, calls, reads, writes, types, values, returns, and exceptions.

LLMs should not construct or modify the CodeModel. Runtime evidence is injected automatically and semantically, for example:

```text
relationships[type="runtime_calls"] -> KDM action::Calls
```

### StructureModel is reviewable

The architecture-level model is recovered from the code model and can be refined by the user. It contains architectural elements such as components, subsystems, control loops, MAPE-K roles, and structural relationships.

AI agents may suggest improvements to the StructureModel, but they do not apply those changes directly.

### Human review is authoritative

After the user reviews the architecture in the GUI, no further AI agent is executed by default. The reviewed architecture JSON is the authoritative input for KDM generation.

## Main modules

| Module | Responsibility |
|---|---|
| `python_kdm_extractor` | Static Python extraction into intermediate JSON. |
| `kdm_dynamic_analysis` | Runtime tracing and dynamic CodeModel enrichment. |
| `kdm_architecture_recovery` | Architecture recovery and MAPE-K role inference. |
| `kdm_architecture_agents` | Pre-review AI suggestions only. |
| `kdm_architecture_review` | Human review GUI. |
| `kdm_pyecore_generator` | KDM XMI generation and validation. |
| `schemas` | JSON Schemas for pipeline artifacts. |
| `run_pipeline.py` | Configurable orchestration script. |
