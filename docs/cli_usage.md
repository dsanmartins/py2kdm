# CLI usage

The console pipeline remains available through `run_pipeline.py`. It is independent of the GUI and can be used for reproducible execution.

## Basic execution

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

## With pre-review agents

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --with-agents pre-review
```

## With dynamic analysis

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --enable-dynamic-analysis   --dynamic-project-root examples/pymape_hierarchical   --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## Skip stages

```bash
python run_pipeline.py --config configs/three_layer_system.json --skip-kdm
python run_pipeline.py --config configs/three_layer_system.json --skip-extractor --skip-kdm
```

## Status of CLI mode

The console mode is still valid. It runs without opening the GUI. It supports static extraction, optional dynamic analysis, architecture recovery, optional pre-review agents and KDM generation.

The GUI is recommended when human review and traceability inspection are required.
