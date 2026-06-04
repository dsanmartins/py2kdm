# 1. System purpose

`py2kdm` is a model-driven reverse-engineering workbench for Python and Java systems. Its purpose is to extract code-level evidence, recover architecture-level abstractions, and generate validated KDM 1.4 XMI models that can be used for software maintenance, architecture analysis and research on model-driven reverse engineering.

The system is centered on a sequence of explicit artifacts. Each stage reads a JSON or XMI file and produces another artifact, which makes the workflow reproducible from the command line and inspectable in the GUI.

## What the system does

`py2kdm` currently supports:

- static extraction of Python projects into `python_model.json`;
- static extraction of Java projects into `java_model.json` through the external `java2kdm` JAR;
- optional dynamic analysis for Python projects through scenario execution;
- deterministic architecture recovery, with special support for MAPE-K-like adaptive systems;
- optional pre-review agents, including deterministic review and LLM-assisted suggestions;
- human review of recovered components, relationships, suggestions and traceability;
- KDM XMI generation from intermediate, architecture or reviewed JSON artifacts;
- KDM validation and regression checks;
- a GUI workbench organized into Configuration, Process, Human Review and Artifacts tabs.

## Main conceptual layers

| Layer | Main artifact | Purpose |
|---|---|---|
| Code extraction | `python_model.json` / `java_model.json` | Captures source files, classes, methods, functions, variables, calls, reads, writes and body-level behavior. |
| Runtime enrichment | `*.runtime_enriched.*.json` | Adds observed runtime calls, argument/return evidence and scenario metadata. |
| Architecture recovery | `*.architecture.json` | Adds `structure_model` with subsystems, components, control loops and relationships. |
| AI/pre-review | `*.ai_architecture.json` | Adds `code_context`, deterministic review and optional LLM suggestions. |
| Human review | `*.reviewed_architecture.json` | Stores reviewed architecture decisions and overrides. |
| KDM generation | `*.kdm.xmi` | Serializes the selected model to KDM XMI. |

## Automatic and human-in-the-loop paths

The automatic path is:

```text
project
  -> static extraction
  -> architecture recovery
  -> model.structure.kdm.xmi
```

For Python projects, runtime analysis can be inserted between static extraction and architecture recovery:

```text
project
  -> static extraction
  -> dynamic analysis
  -> runtime-enriched JSON
  -> architecture recovery
  -> model.structure.kdm.xmi
```

The optional human-in-the-loop path is:

```text
architecture JSON
  -> pre-review agents
  -> AI architecture JSON
  -> Human Review GUI
  -> reviewed architecture JSON
  -> model.reviewed.kdm.xmi
```

## Methodological boundary

The deterministic recovery output, `*.architecture.json`, is the authoritative automatic architecture artifact. The pre-review stage adds evidence and suggestions, but it does not replace the reviewer. Once the reviewer exports `*.reviewed_architecture.json`, that reviewed model is treated as the source for `model.reviewed.kdm.xmi`.

## KDM scope

The KDM generator can produce:

- `InventoryModel` for source files;
- `CodeModel` for code entities such as compilation units, classes, methods, functions, parameters and variables;
- `ActionElement`, `BlockUnit` and behavioral relations such as `Calls`, `Reads`, `Writes`, `Creates`, `Throws`, `ExceptionFlow`;
- `StructureModel` for recovered architecture, including `Subsystem`, `Component`, `StructureRelationship` and `AggregatedRelationship`;
- KDM extension stereotypes for the adaptive-system domain, such as `Monitor`, `Analyzer`, `Planner`, `Executor`, `Knowledge`, `Sensor`, `Effector`, `LoopManager` and control-loop-related stereotypes.
