# 3. Pipeline execution with `run_pipeline.py`

`run_pipeline.py` is the console orchestrator. It reads a project configuration file and executes the enabled stages in order. It is the recommended entry point for reproducible experiments and regression runs.

## Basic commands

Python example:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Java example:

```bash
python run_pipeline.py --config configs/phoneadapter.json
```

Run with pre-review agents:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review
```

Skip extraction and reuse an existing intermediate JSON:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --skip-extractor \
  --with-agents pre-review
```

Run dynamic analysis from the command line:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## Main arguments

| Argument | Required | Meaning |
|---|---:|---|
| `--config PATH` | Yes | Project configuration JSON. |
| `--python PATH` | No | Python interpreter used for subprocesses that require project dependencies, PyEcore or agent dependencies. |
| `--skip-extractor` | No | Reuses the existing `intermediate_json` instead of running the static extractor. |
| `--skip-architecture` | No | Skips architecture recovery. Useful for direct code-to-KDM generation. |
| `--skip-kdm` | No | Skips KDM generation. Useful when testing extraction, dynamic analysis or architecture recovery only. |
| `--with-agents pre-review` | No | Runs pre-review architecture agents after architecture recovery. |
| `--enable-dynamic-analysis` | No | Enables dynamic analysis for Python projects from CLI. |
| `--dynamic-project-root PATH` | No | Project root used by dynamic scenarios. |
| `--dynamic-scenario NAME:SCRIPT` | No | Adds a dynamic scenario. Can be repeated if the implementation supports multiple scenarios. |

Use `python run_pipeline.py --help` as the final source of truth for the exact arguments supported by the checked-out version.

## Pipeline stages

A typical run can execute the following stages:

| Stage | Python | Java | Main output |
|---|---:|---:|---|
| Static extraction | Yes | Yes, through `java2kdm` | `python_model.json` / `java_model.json` |
| Dynamic analysis | Yes | Disabled | `runtime_trace.*.json`, `*.runtime_enriched.*.json` |
| Architecture recovery | Yes | Yes | `*.architecture.json` |
| Pre-review agents | Optional | Optional | `*.ai_architecture.json` |
| KDM generation | Yes | Yes | `model.kdm.xmi`, `model.structure.kdm.xmi` or `model.reviewed.kdm.xmi` depending on input/output. |
| Regression checks | Optional | Optional | Console validation report. |

## KDM input selection

The KDM generator input is controlled by `kdm_generation.input` in the config.

| Value | Meaning | Typical output |
|---|---|---|
| `intermediate_json` | Generate KDM from the static code model. | `model.kdm.xmi` |
| `runtime_enriched_json` | Generate KDM from a runtime-enriched model. | `model.kdm.xmi` |
| `architecture_json` | Generate KDM from the recovered architecture model. | `model.structure.kdm.xmi` |
| explicit path | Generate KDM from a custom JSON file, often reviewed architecture. | custom XMI |

For architecture-oriented results, use `architecture_json`, because it contains the `structure_model` section needed to create KDM `StructureModel` elements.

## Typical final automatic run

For the current architecture workflow, the desired automatic output is `model.structure.kdm.xmi`:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --skip-extractor \
  --with-agents pre-review
```

The pre-review stage is optional. The KDM structural model should be generated from `architecture_json`, not from `ai_architecture_json`, unless a specific experiment intentionally uses AI-enriched or reviewed input.

## Common checks after execution

```bash
grep -n "StructureModel" outputs/pymape_hierarchical/model.structure.kdm.xmi | head
grep -n "Adaptive System Domain" outputs/pymape_hierarchical/model.structure.kdm.xmi | head
grep -n "aggregatedRelation" outputs/pymape_hierarchical/model.structure.kdm.xmi | head
grep -n "implementation=" outputs/pymape_hierarchical/model.structure.kdm.xmi | head
```

The structure checker gives a stronger validation:

```bash
python scripts/check_kdm_structure.py \
  --xmi outputs/pymape_hierarchical/model.structure.kdm.xmi \
  --profile pymape_hierarchical \
  --baseline configs/kdm_structure_baselines.json
```
