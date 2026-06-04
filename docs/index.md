# py2kdm documentation

This documentation describes the current `py2kdm` system in a compact form. It focuses on what the system does, how each subproject is executed, how the full pipeline is configured, which artifacts are produced, how KDM is constructed, and how deterministic and LLM-assisted architecture agents operate.

## Recommended reading order

1. [System purpose](01-system-purpose.md)
2. [Subprojects and standalone execution](02-subprojects-cli.md)
3. [Pipeline execution](03-run-pipeline.md)
4. [Project configuration files](04-config-files.md)
5. [Technical artifacts and KDM construction](05-technical-artifacts-kdm.md)
6. [Architecture agents](06-architecture-agents.md)

## Current high-level flow

```text
source project
  -> intermediate JSON
  -> optional runtime-enriched JSON
  -> architecture JSON
  -> optional AI architecture JSON
  -> optional reviewed architecture JSON
  -> KDM XMI
```

## Main outputs

| Artifact | Meaning |
|---|---|
| `python_model.json` / `java_model.json` | Static intermediate code model. |
| `runtime_trace.<scenario>.json` | Runtime evidence collected from a Python scenario. |
| `*.runtime_enriched.combined.json` | Static model enriched with runtime evidence. |
| `*.architecture.json` | Deterministic architecture recovery output. |
| `*.ai_architecture.json` | Architecture output enriched with pre-review suggestions and code context. |
| `*.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.kdm.xmi` | Base KDM, usually generated from the intermediate model. |
| `model.structure.kdm.xmi` | KDM generated from architecture JSON, including `StructureModel`. |
| `model.reviewed.kdm.xmi` | KDM generated from the human-reviewed architecture JSON. |

## Documentation map

This documentation is organized around the main use cases of the project:

1. system purpose;
2. subprojects and command-line execution;
3. complete pipeline execution;
4. configuration files;
5. technical artifacts and KDM construction;
6. architecture agents;
7. graphical user interface.
