# Architecture Review GUI

The review GUI allows the user to inspect, accept, reject, or modify the recovered architecture and the AI-generated pre-review suggestions.

## Purpose

The GUI is the point where the user validates the StructureModel. After review, the exported JSON is treated as authoritative and is used directly for final KDM generation.

## Inputs

Typical inputs are:

```text
python_model.runtime_enriched.architecture.json
python_model.runtime_enriched.ai_architecture.json
```

The AI-enriched architecture JSON includes `ai_enrichment.suggestions`, which the GUI can show as reviewable items.

## User actions

The reviewer may:

- accept a suggested component or relationship;
- reject a suggestion;
- rename a component;
- change a role;
- merge or split components;
- add missing abstractions manually;
- mark uncertain suggestions as not applicable.

## Output

The GUI exports a reviewed architecture JSON:

```text
python_model.runtime_enriched.reviewed_architecture.json
```

This file is the final architecture input for KDM generation.

## Methodological boundary

No post-review AI agent is part of the default workflow. The reviewed architecture reflects the human decision and is not reinterpreted by agents before KDM generation.
