# MAPE-K Recovery Rules

MAPE-K recovery identifies Monitor, Analyzer, Planner, Executor, Knowledge, Sensor, Effector, Reference Input, and Measured Output candidates from code and runtime evidence.

## Core roles

| Role | Typical evidence |
|---|---|
| Monitor | Code that observes state, subscribes to updates, or reads measured values. |
| Analyzer | Code that evaluates monitored data and determines whether adaptation is needed. |
| Planner | Code that decides a target adaptation or computes a control action. |
| Executor | Code that performs adaptation by invoking actuators or effectors. |
| Knowledge | Shared state, configuration, memory, or data repository used by the loop. |

## Peripheral roles

| Role | Typical evidence |
|---|---|
| Sensor | Interface or function that obtains external measurements. |
| Effector | Interface or function that applies changes to the managed system. |
| ReferenceInput | Desired setpoint, policy, or target value. |
| MeasuredOutput | Observed value used for feedback control. |

## Rule-based inference

Role inference uses names, call relationships, data-flow hints, containment, and known MAPE-K vocabulary. Examples:

- `speed`, `distance`, `monitor`, `observe`, `subscribe` may indicate Monitor behavior.
- `pid`, `plan`, `control`, `target`, `setpoint` may indicate Planner behavior.
- `gas`, `brake`, `actuate`, `execute` may indicate Executor or Effector behavior.
- Shared memory, Redis-like structures, or configuration containers may indicate Knowledge.

## Runtime evidence

Runtime evidence may support or refine relationships between recovered components. For example:

```text
gas_brake --acts_through--> gas
gas_brake --acts_through--> brake
```

Such suggestions are generated as reviewable architecture changes, not applied automatically.

## Missing roles

A control loop may be valid even if a role is not explicit in the implementation. For example, an Analyzer may be absorbed into a Planner or Monitor. Therefore, missing-role suggestions should remain `needs_review`.
