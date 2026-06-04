# py2kdm

**Author:** [Daniel San Martín](https://www.danielsanmartin.cl/)

`py2kdm` is a model-driven reverse-engineering workbench for generating KDM 1.4 XMI models from Python and Java projects. It extracts code models into JSON, optionally enriches them with runtime evidence, recovers MAPE-K-oriented architecture abstractions, supports deterministic and LLM-assisted pre-review, and generates validated KDM models with `CodeModel`, `Action` elements and, when requested, `StructureModel` elements.

## Main workflow

```text
Python or Java project
  -> static extraction
  -> intermediate JSON
  -> architecture recovery
  -> architecture JSON
  -> KDM generation
  -> model.structure.kdm.xmi
```

The human-in-the-loop workflow is optional:

```text
architecture JSON
  -> pre-review agents, optional
  -> AI architecture JSON
  -> Human Review GUI
  -> reviewed architecture JSON
  -> model.reviewed.kdm.xmi
```

## GUI

Launch the GUI with:

```bash
python -m py2kdm_gui.main
```

The GUI is organized into four tabs:

| Tab | Purpose |
|---|---|
| Configuration | Project paths, language, dynamic scenarios, LLM settings and setup validation. |
| Process | Main automatic pipeline: static extraction, dynamic analysis for Python, architecture recovery and KDM generation. |
| Human Review | Optional pre-review agents, model loading, review validation, reviewed JSON export and reviewed KDM generation. |
| Artifacts | Inspection of generated JSON, trace and XMI artifacts. |

## Console pipeline

Typical Python run:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Typical Java run:

```bash
python run_pipeline.py --config configs/phoneadapter.json
```

With pre-review agents:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review
```

With dynamic analysis:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py
```

## Documentation

The documentation has been consolidated into six focused sections:

1. System purpose.
2. Subprojects and standalone execution.
3. `run_pipeline.py` execution and arguments.
4. Project config files.
5. Technical artifacts: JSON and KDM construction.
6. Architecture agents and assumptions.

Build locally with:

```bash
mkdocs serve
```

If the `material` theme is unavailable, install it:

```bash
pip install mkdocs-material
```

or change the theme in `mkdocs.yml` to `readthedocs` or `mkdocs`.
