# PyMAPE Hierarchical Runtime Scenarios

This folder contains non-interactive runtime scenarios for dynamic CodeModel enrichment.

The original `hierarchical-cruise-control.py` script is an interactive application. It configures prompt/key handlers and runs the application loop, which is not ideal for automated tracing. These scenarios instead execute controlled, bounded flows.

## Scenarios

```text
scenarios/cruise_control_scenario.py
scenarios/hold_distance_scenario.py
```

## Why a no-op Influx observer?

The original example subscribes some MAPE elements to `InfluxObserver`. During tracing we do not want an external InfluxDB dependency, so the scenarios monkeypatch the imported `InfluxObserver` with a local no-op observer.

## Cruise-control trace

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/cruise_control_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.json \
  --scenario cruise_control \
  --mode desktop
```

## Hold-distance trace

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/hold_distance_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.hold_distance.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.json \
  --scenario hold_distance \
  --mode desktop
```
