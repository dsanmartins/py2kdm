# py2kdm

**Author:** Daniel San Martín


`py2kdm` is a model-driven reverse-engineering workbench for generating KDM-based representations from Python projects. It combines static extraction, optional runtime evidence, architecture recovery, human review, and final KDM XMI generation.

The current workflow is organized around two complementary interfaces:

- a **GUI workbench** for configuration, pipeline execution, human review, traceability inspection, and artifact inspection;
- a **console pipeline** through `run_pipeline.py` for reproducible command-line execution and regression checks.

## Main workflow

1. Configure the project.
2. Run static extraction.
3. Optionally run dynamic analysis through scenarios.
4. Recover architectural abstractions into a `structure_model`.
5. Run pre-review architecture agents to create reviewable suggestions.
6. Review the proposed architecture in the GUI.
7. Export the reviewed architecture JSON.
8. Generate the final KDM XMI.
9. Inspect the generated artifacts.

## Main outputs

| Artifact | Purpose |
|---|---|
| `python_model.json` | Static intermediate model extracted from Python source code. |
| `runtime_trace.<scenario>.json` | Runtime events observed for one scenario. |
| `python_model.runtime_enriched.combined.json` | Static model enriched with runtime relationships and observed types. |
| `python_model.runtime_enriched.architecture.json` | Architecture recovery over the runtime-enriched model. |
| `python_model.runtime_enriched.ai_architecture.json` | Architecture proposal with pre-review AI suggestions. |
| `python_model.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.reviewed.kdm.xmi` | Final KDM XMI model. |

## Recommended entry points

Use the GUI when you need reviewability and traceability:

```bash
python -m py2kdm_gui.main
```

Use the console pipeline when you need reproducible CLI execution:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```
