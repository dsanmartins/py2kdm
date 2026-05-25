# MAPE-K recovery rules

MAPE-K recovery is based on explicit evidence in the code model and, when available, runtime evidence.

## Role inference

| Role | Typical evidence |
|---|---|
| Monitor | Functions or classes that observe, read, sense or collect data. |
| Analyzer | Functions or classes that evaluate or classify system state. |
| Planner | Functions or classes that decide an adaptation plan. |
| Executor | Functions or classes that perform adaptation actions. |
| Knowledge | Shared state, memory, repositories or configuration data. |
| Sensor | External or internal observation endpoint. |
| Effector | Action endpoint affecting a managed element. |

## Runtime evidence

Runtime calls may support architecture relationships such as:

```text
Executor --acts_through--> Effector
Monitor --observes--> Sensor
```

## Review requirement

Recovered roles are proposals. The GUI lets the user inspect and revise them before KDM generation.
