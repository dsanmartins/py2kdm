# Examples and case studies

The repository includes example systems under `examples/`.

## three_layer_system

A compact example used for static extraction, architecture recovery and KDM generation.

CLI example:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

## pymape_hierarchical

A richer example used to exercise dynamic analysis, MAPE-K recovery, pre-review agents and human review.

Typical GUI workflow:

```bash
python -m py2kdm_gui.main
```

Then:

```text
Configuration -> configure PyMAPE project and scenarios
Process -> Run until Human Review
Human Review -> validate and export reviewed JSON
Process -> Generate final KDM
Artifacts -> inspect outputs
```

## Adding a new project

1. Add the Python project under `examples/` or point to an external project path.
2. Create one or more dynamic scenarios if runtime evidence is needed.
3. Configure the project in the GUI or create a CLI config.
4. Run the pipeline.
5. Review the architecture before KDM generation.
