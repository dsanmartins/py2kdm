# Artifact reference

The **Artifacts** tab summarizes generated files and lets the user inspect them without leaving the GUI.

## Common artifacts

| Artifact | Description |
|---|---|
| `python_model.json` | Static model extracted from Python source code. |
| `runtime_trace.<scenario>.json` | Raw runtime trace for one scenario. |
| `python_model.runtime_enriched.<scenario>.json` | Intermediate runtime-enriched model for one scenario. |
| `python_model.runtime_enriched.combined.json` | Combined runtime-enriched model after all enabled scenarios. |
| `python_model.runtime_enriched.architecture.json` | Recovered architecture over runtime-enriched model. |
| `python_model.runtime_enriched.ai_architecture.json` | Architecture proposal with pre-review AI suggestions. |
| `python_model.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.reviewed.kdm.xmi` | Final KDM XMI generated from the reviewed architecture. |

## JSON summaries

For JSON files, the GUI reports top-level keys, metadata, static relationship counts, runtime enrichment summary, architecture element counts, AI suggestion counts, and human review decisions.

## XMI summaries

For XMI files, the GUI reports approximate counters for `action:Calls`, `runtime_call` labels, `structure:Component`, `structure:Subsystem`, `structure:StructureRelationship`, and `extensionFamily`.
