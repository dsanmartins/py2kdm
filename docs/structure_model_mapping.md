# Structure model mapping

The `structure_model` is the architecture-level layer added to the JSON model before KDM generation.

## Main elements

| JSON element | Meaning |
|---|---|
| `subsystems` | Coarse-grained architecture containers. |
| `control_loops` | Adaptive control-loop abstractions. |
| `components` | Architecture components with roles and stereotypes. |
| `structure_relationships` | Architecture relationships between components. |
| `containment_relationships` | Containment between subsystems, loops and components. |

## Materialization flag

Many architecture elements include:

```json
"materialize": true
```

Only materialized elements should be emitted to the final KDM StructureModel.

## Review metadata

Human review can add or update review status, review decisions, reasons, accepted/rejected AI suggestions, and applied changes.
