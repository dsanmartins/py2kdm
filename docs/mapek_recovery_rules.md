# MAPE-K Recovery Rules

## Purpose

The MAPE-K recovery process identifies candidate self-adaptive architecture elements from the intermediate Python model. The goal is not to reconstruct a perfect architecture automatically, but to generate a traceable candidate architecture that can be reviewed, refined, and materialized as KDM.

The recovery process is rule-based and conservative. It only promotes elements when there is enough evidence in the source model.

## Autonomic applicability gate

Before MAPE-K recovery is activated, the system evaluates whether the analyzed project contains enough evidence of self-adaptive behavior.

The gate checks for evidence such as:

- explicit self-adaptation vocabulary;
- MAPE-K role vocabulary;
- sensor or runtime observation evidence;
- effector or adaptation action evidence;
- shared knowledge evidence;
- partial control-loop relation evidence.

If the score is below the activation threshold, the architecture recovery is disabled. If the score is sufficient, the system marks the project as a candidate autonomic system and enables MAPE-K recovery.

Example output:

```json
{
  "decision": "candidate_autonomic_system",
  "status": "mapek_recovery_enabled",
  "score": 0.9,
  "matched_rules": [
    "SAS-GATE-01",
    "SAS-GATE-02",
    "SAS-GATE-03",
    "SAS-GATE-04",
    "SAS-GATE-05"
  ]
}
```

## Role inference

The role inference stage produces role suggestions from visible evidence in the code model.

Supported roles include:

- `Monitor`
- `Analyzer`
- `Planner`
- `Executor`
- `Knowledge`
- `Sensor`
- `Effector`
- `ReferenceInput`
- `MeasuredOutput`
- `LoopManager`

The `Alternative` concept is not promoted as a structural stereotype. Alternatives are treated as internal evidence of the `Planner`.

## Decorator-based evidence

The recovery supports framework-style MAPE-K declarations, especially PyMAPE-like decorators.

Examples:

```python
@loop.monitor
def distance(...):
    ...

@loop.plan
def pid(...):
    ...

@loop.execute
def gas_brake(...):
    ...
```

These decorators are mapped as follows:

| Decorator term | Recovered role |
|---|---|
| `monitor` | `Monitor` |
| `analyze` / `analyse` | `Analyzer` |
| `plan` | `Planner` |
| `execute` | `Executor` |

When a decorator includes a loop reference, a `loop_hint` is also recorded. This hint is used later to group components inside a candidate `Control Loop`.

Example:

```json
{
  "suggested_role": "Planner",
  "confidence": 0.95,
  "source": "rule_based_decorator",
  "status": "auto_accepted",
  "loop_hint": "loop"
}
```

## Registration-call evidence

The recovery also detects registration-style calls, such as:

```python
loop.monitor(distance)
loop.plan(pid)
loop.execute(gas_brake)
```

These calls provide evidence for MAPE-K roles when decorators are not used.

## Confidence and status

Each role suggestion receives a confidence value and a review status.

| Status | Meaning |
|---|---|
| `auto_accepted` | Strong evidence was found. The element can be promoted automatically. |
| `needs_review` | Evidence exists, but human review is recommended. |
| `weak_suggestion` | Evidence is weak. The suggestion is reported but normally not promoted. |

The architecture recovery engine promotes suggestions to components when they are `auto_accepted` or when their confidence is above the configured threshold.

## Control I/O recovery

In addition to MAPE-K roles, the system can recover control-oriented abstractions:

- `ReferenceInput`
- `MeasuredOutput`
- `Sensor`
- `Effector`

This recovery is conservative.

Examples:

| Evidence | Recovered role |
|---|---|
| `target_speed`, `desired_distance`, `setpoint` | `ReferenceInput` |
| `current_speed`, `measured_distance`, `actual_temperature` | `MeasuredOutput` |
| `read_distance`, `measure_speed`, `tachometer` | `Sensor` |
| `brake`, `gas`, `siren`, `hazard_lights` | `Effector` |

If there is no explicit evidence, these abstractions are not invented automatically.

## Control loop construction

A candidate `Control Loop` is created when the system finds enough MAPE-K components grouped by a common loop hint or by structural evidence.

A control loop may be:

- `complete`, when core MAPE roles are present;
- `partial`, when some roles are missing;
- `weak`, when only minimal evidence exists.

Example:

```json
{
  "id": "control_loop:loop",
  "name": "Loop Control Loop",
  "role": "Loop",
  "stereotype_name": "Control Loop",
  "loop_completeness": "partial",
  "missing_roles": ["Analyzer"],
  "roles_present": [
    "Executor",
    "Knowledge",
    "Monitor",
    "Planner"
  ]
}
```

A partial loop is allowed because real implementations may not expose every MAPE-K abstraction explicitly.

## Semantic construction rules

Containment is guided by semantic construction rules. The system does not build arbitrary containment relationships.

Allowed examples:

```text
Managing Subsystem -> CL Manager
CL Manager -> Control Loop
Control Loop -> Monitor
Control Loop -> Planner
Control Loop -> Executor
Managed Subsystem -> Effector
```

Forbidden examples:

```text
Managed Subsystem -> Planner
Managing Subsystem -> Sensor
Control Loop -> Effector
```

The output section `architecture_consistency` reports which rules were applied and which warnings were generated during construction.
