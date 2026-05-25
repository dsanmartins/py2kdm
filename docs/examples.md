# Examples and Case Studies

The repository includes examples used to validate the pipeline.

## `three_layer_system`

A small example project used to test extraction, architecture recovery, and KDM generation on a conventional layered architecture.

Typical outputs:

```text
outputs/three_layer_system/python_model.json
outputs/three_layer_system/python_model.architecture.json
outputs/three_layer_system/model.kdm.xmi
```

## `pymape_hierarchical`

A self-adaptive MAPE-K example used to test:

- static extraction;
- dynamic tracing;
- runtime call enrichment;
- MAPE-K recovery;
- pre-review architecture agents;
- KDM generation with runtime `action::Calls`.

Runtime scenarios include:

```text
scenarios/cruise_control_scenario.py
scenarios/hold_distance_scenario.py
```

Typical runtime outputs:

```text
runtime_trace.cruise_control.json
runtime_trace.hold_distance.json
python_model.runtime_enriched.combined.json
model.runtime_enriched.combined.kdm.xmi
```

## Expected dynamic results

A successful dynamic run should report completed traces and dynamic relationships, for example:

```text
Runtime trace generated.
- events: 1996
- status: completed
Code model dynamically enriched.
- events after filter: 1707
- dynamic relationships added: 151
```

The generated KDM should validate with:

```text
Errors: 0
```
