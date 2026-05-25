# Intermediate JSON model

The intermediate JSON model is the exchange format used across the py2kdm pipeline.

## Purpose

It decouples the static extractor from the KDM generator and from the architecture recovery stages. This makes it possible to enrich the model before generating KDM.

## Main sections

Typical top-level sections include project metadata, files, modules, classes, functions and methods, variables and parameters, relationships, optional `runtime_enrichment`, optional `structure_model`, optional `ai_enrichment`, and optional `architecture_review`.

## Static relationships

The model can include calls, imports, type references, value references, returns, and raises/throws.

## Runtime relationships

After dynamic analysis, the model may include runtime-aware relationships such as:

```json
{
  "type": "runtime_calls",
  "source": "function:...",
  "target": "function:...",
  "scenario": "cruise_control"
}
```

## Architecture section

Architecture recovery adds a `structure_model` section with components, subsystems, control loops and architecture-level relationships.
