# Dynamic Analysis

Dynamic analysis complements static extraction by executing project-specific scenarios and tracing runtime behavior with `sys.setprofile`.

The goal is not to infer architecture directly. The goal is to enrich the CodeModel with factual runtime evidence.

## Workflow

```text
python_model.json
  -> runtime_trace.<scenario>.json
  -> python_model.runtime_enriched.<scenario>.json
  -> python_model.runtime_enriched.combined.json
```

## Scenario-based design

The dynamic analysis stage is generic. It does not know how to run a particular project. Each project provides scenarios that activate relevant behavior.

Example:

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/cruise_control_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json \
  --scenario cruise_control \
  --mode desktop
```

A second scenario can enrich the already enriched model:

```bash
python kdm_dynamic_analysis/main.py enrich \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json \
  --trace outputs/pymape_hierarchical/runtime_trace.hold_distance.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json
```

## Runtime evidence captured

The tracer can collect:

- calls observed during execution;
- concrete argument types;
- return types;
- exceptions;
- scenario names;
- file and line information when available.

## Filtering

Raw traces contain noise from imports, helper scripts, and dependency shims. The enrichment agent filters out scenario infrastructure and keeps runtime evidence that belongs to the analyzed system.

Common exclusions include:

```text
scenarios.*
_scenario_common.*
*.Dummy*
*.NullObserver*
*.install_dependency_shims
*.import_mape
*.load_hierarchical_module
*.<module>
```

## KDM semantics

Runtime calls are transformed into semantic KDM relations:

```text
relationships[type="runtime_calls"] -> action::Calls
```

They are not represented as `TaggedValue` objects. If an equivalent static `Calls(source, target)` already exists, the runtime relation is not duplicated.

## Desktop and web modes

The current stable mode is `desktop`. The pipeline is designed to support `web` scenarios as a future runner mode, where a server scenario and HTTP interaction scenarios can be traced.
