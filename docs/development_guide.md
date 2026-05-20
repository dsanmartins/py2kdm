# Development Guide

## Project layout

```text
py2kdm/
├── run_pipeline.py
├── python_kdm_extractor/
├── kdm_architecture_recovery/
├── kdm_architecture_review/
├── kdm_pyecore_generator/
├── configs/
├── examples/
├── outputs/
└── docs/
```

## Development principles

The project follows these principles:

1. Keep extraction independent from KDM generation.
2. Use JSON as the contract between stages.
3. Keep architecture recovery evidence-driven.
4. Preserve traceability from architecture elements to code elements.
5. Prefer explicit KDM metaclasses over ad-hoc XML.
6. Use semantic construction rules during architecture recovery.
7. Avoid inventing architecture abstractions without evidence.

## Adding extractor features

Extractor changes usually belong in `python_kdm_extractor/extractor/`.

When adding a new extracted construct:

1. Extend the AST extraction logic.
2. Add the field to the intermediate JSON.
3. Update relationship or symbol-table logic if needed.
4. Update `intermediate_json_model.md`.
5. Add tests or example snippets.
6. Verify KDM generation.

## Adding KDM mappings

Generator changes usually belong in `kdm_pyecore_generator/generator/`.

When adding a new KDM mapping:

1. Add factory support in `kdm_factory.py` if needed.
2. Add mapping logic to the appropriate mapper or resolver.
3. Register generated elements in the relevant index.
4. Add validation rules when useful.
5. Update `json_to_kdm_mapping.md`.

## Adding architecture recovery rules

Architecture recovery changes usually belong in `kdm_architecture_recovery/`.

Important files:

| File | Purpose |
|---|---|
| `autonomic_applicability_gate.py` | Decides whether MAPE-K recovery is enabled. |
| `rule_based_mapek_role_inferer.py` | Infers MAPE-K roles. |
| `control_io_recoverer.py` | Infers Reference Input, Measured Output, Sensor and Effector. |
| `containment_recoverer.py` | Builds containment relations. |
| `semantic_architecture_rules.py` | Constrains semantic construction. |
| `structure_relationship_recoverer.py` | Recovers technical and architectural relationships. |
| `adaptive_stereotype_catalog.py` | Defines Adaptive System Domain stereotypes. |

## Adding stereotypes

Add the stereotype to:

```text
kdm_architecture_recovery/adaptive_stereotype_catalog.py
kdm_pyecore_generator/generator/adaptive_stereotype_builder.py
```

Then update:

```text
docs/architecture_recovery.md
docs/structure_model_mapping.md
docs/json_to_kdm_mapping.md
```

## Running checks

Compile Python files:

```bash
python -m py_compile run_pipeline.py
python -m py_compile kdm_architecture_recovery/*.py
python -m py_compile kdm_pyecore_generator/generator/*.py
```

Run pipeline:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Run documentation locally:

```bash
mkdocs serve
```

## Documentation updates

When code behavior changes, update the corresponding documentation:

| Change | Documentation |
|---|---|
| Pipeline config | `pipeline_configuration.md` |
| Extractor output | `intermediate_json_model.md` |
| Architecture recovery | `architecture_recovery.md`, `mapek_recovery_rules.md` |
| StructureModel generation | `structure_model_mapping.md`, `json_to_kdm_mapping.md` |
| Traceability | `kdm_traceability_links.md` |
| Validation | `validation_rules.md` |
