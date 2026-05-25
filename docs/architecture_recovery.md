# Architecture recovery

Architecture recovery reads the intermediate JSON model and creates a `structure_model` section.

## Command

```bash
python kdm_architecture_recovery/main.py   --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
```

## Output

The recovery stage can create subsystems, control loops, architecture components, containment relationships, and structure relationships.

## MAPE-K focus

The current architecture recovery includes rules for autonomic and MAPE-K-like systems. It can infer roles such as Monitor, Analyzer, Planner, Executor, Knowledge, Managed Element, Sensor, Effector, Reference Input, and Measured Output.

## Applicability gate

Architecture recovery is guarded by an applicability gate. If the project does not provide enough evidence for an adaptive architecture, the recovery can be disabled or marked as not applicable.
