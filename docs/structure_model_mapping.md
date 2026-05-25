# Structure Model Mapping

The `structure_model` stores the recovered architecture before KDM generation.

## Components

Components represent architectural abstractions recovered from code.

```json
{
  "id": "component:gas_brake_executor_control_gas_brake",
  "name": "gas_brake",
  "role": "Executor",
  "implemented_by": [
    "function:pymape_hierarchical.hierarchical-cruise-control.gas_brake"
  ],
  "confidence": 0.85,
  "materialize": true
}
```

Important fields:

| Field | Meaning |
|---|---|
| `id` | Stable architecture-level identifier. |
| `name` | Human-readable component name. |
| `role` | Candidate architectural role. |
| `implemented_by` | Code elements implementing the component. |
| `confidence` | Recovery confidence. |
| `materialize` | Whether the component should be emitted to the final KDM structure model. |

## Structure relationships

Relationships connect architecture components.

```json
{
  "id": "relationship:gas_brake_acts_through_gas",
  "type": "acts_through",
  "source": "component:gas_brake_executor_control_gas_brake",
  "target": "component:gas_effector_pymape_hierarchical_fixtures_virtualcarspeed_gas",
  "status": "needs_review"
}
```

## Containment relationships

Containment relationships organize components inside subsystems or control loops.

```json
{
  "type": "contains",
  "source": "control_loop:loop",
  "target": "component:speed_monitor_cruise_control_speed"
}
```

## Control loops

Control loops group components involved in adaptive behavior.

```json
{
  "id": "control_loop:loop",
  "name": "loop",
  "components": [
    "component:speed_monitor_cruise_control_speed",
    "component:pid_planner_cruise_control_pid",
    "component:gas_brake_executor_control_gas_brake"
  ]
}
```

## Review status

Suggestions from agents are not applied directly. They are passed to the review GUI where the user decides whether to accept, reject, or modify them.
