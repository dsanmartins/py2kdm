# Architecture Recovery

Architecture recovery builds a `structure_model` from the intermediate JSON. It focuses on software architecture elements, especially MAPE-K concepts for self-adaptive systems.

```bash
python kdm_architecture_recovery/main.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
```

## Inputs

Architecture recovery can use either:

- the static `python_model.json`; or
- the runtime-enriched `python_model.runtime_enriched.combined.json`.

Using the runtime-enriched model is recommended when execution scenarios are available.

## Output

The recovery stage adds:

```json
{
  "structure_model": {
    "components": [],
    "structure_relationships": [],
    "containment_relationships": [],
    "control_loops": [],
    "subsystems": [],
    "architecture_consistency": {}
  }
}
```

## Recovery responsibilities

The recovery engine detects and organizes:

- components and their candidate architectural roles;
- MAPE-K control-loop elements;
- containment relationships;
- structure relationships;
- adaptive stereotypes;
- traceability from architecture components to code elements.

## Human review requirement

The recovered structure model is a proposal. It should be reviewed in the GUI, especially when an element has multiple possible roles or when a MAPE-K role is missing.
