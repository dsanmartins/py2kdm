# Architecture review GUI

The GUI review workflow is implemented in `py2kdm_gui`.

## Launch

```bash
python -m py2kdm_gui.main
```

## Tabs

| Tab | Purpose |
|---|---|
| Configuration | Project setup, scenarios and pre-review agents. |
| Process | Pipeline execution, diagnostics and KDM summary. |
| Human Review | Architecture review, validation and export. |
| Artifacts | Generated file inspection. |

## Open proposal

The preferred proposal is the AI-enriched architecture JSON:

```text
python_model.runtime_enriched.ai_architecture.json
```

## Review actions

AI suggestions support Accept, Reject, and Mark reviewed.

Accept applies a structured suggestion when possible. If the suggestion is textual only, the acceptance decision is recorded without modifying the model.

## Export

The reviewed architecture must be validated before export. The GUI shows an export summary before writing:

```text
python_model.reviewed_architecture.json
```

This reviewed JSON is the input for final KDM generation.
