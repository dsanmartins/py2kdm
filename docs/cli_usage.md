# CLI Usage

## Full pipeline without dynamic analysis

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

## Full pipeline with dynamic analysis

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py \
  --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py
```

## Static extraction only

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

## Runtime trace and enrichment

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

## Architecture recovery

```bash
python kdm_architecture_recovery/main.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
```

## Pre-review agents

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json \
  --llm-provider none
```

With Gemini:

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash-lite
```

## Final KDM generation

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/model.runtime_enriched.reviewed.kdm.xmi
```

For debugging only:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json \
  --output outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi \
  --no-validation
```
