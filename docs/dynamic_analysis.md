# Dynamic analysis

Dynamic analysis executes project-specific scenarios under the generic runtime tracer. The tracer observes runtime behavior and enriches the static model with dynamic evidence.

## Command

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich   --project-root examples/pymape_hierarchical   --script scenarios/cruise_control_scenario.py   --input outputs/pymape_hierarchical/python_model.json   --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json   --scenario cruise_control   --mode desktop
```

## What is collected

Dynamic analysis can collect runtime call edges, observed argument types, observed return types, observed exceptions, scenario metadata, and execution status.

## Multiple scenarios

Multiple scenarios can be executed sequentially. Each scenario produces a trace. The last enriched model can be used as the combined runtime-enriched model.

## Generic nature

The dynamic analysis engine is generic. It does not know application-specific behavior. Scenario scripts are responsible for exercising the project.
