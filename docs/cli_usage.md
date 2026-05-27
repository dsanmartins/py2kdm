# CLI usage

The console pipeline remains available through `run_pipeline.py`. It is independent of the GUI and can be used for reproducible execution.

## Python project

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

## Java project

```bash
python run_pipeline.py --config configs/demo_java_project.json
```

The Java pipeline invokes the configured `java2kdm` JAR, generates `java_model.json`, and then passes that model to the KDM generator.

## With pre-review agents

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review
```

## With dynamic analysis

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## Skip stages

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-architecture
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-extractor
```

## Python executable

The KDM generator depends on packages such as `pyecore`. If the system Python does not have those dependencies, pass the correct interpreter explicitly:

```bash
python run_pipeline.py \
  --config configs/demo_java_project.json \
  --python /home/dsanmartins/mypython/bin/python
```

## KDM generation and regression checks

If `kdm_generation.validate` is enabled, the generator validates the KDM model. If `kdm_generation.regression_check.enabled` is enabled, the pipeline also runs integrated regression checks after XMI generation.

Typical output:

```text
--- Running KDM regression checks ---
KDM regression summary:
- Language: java
- ActionElement: ...
- Calls: ...
- Creates: ...
- Reads: ...
- Writes: ...
- Throws: ...
- TryUnit: ...
- CatchUnit: ...
- ExceptionFlow: ...
KDM regression checks passed.
```
