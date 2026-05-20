# CLI Usage

## Full pipeline

Run the full pipeline from the project root:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

This executes:

1. Python extraction.
2. Architecture recovery, if enabled.
3. KDM generation, if enabled.

## Pipeline options

```bash
python run_pipeline.py --config CONFIG
```

Optional flags:

| Flag | Meaning |
|---|---|
| `--python PATH` | Python executable used for subprocesses. |
| `--skip-extractor` | Reuse an existing intermediate JSON. |
| `--skip-architecture` | Skip architecture recovery. |
| `--skip-kdm` | Skip KDM generation. |

Examples:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
```

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --skip-extractor \
  --skip-architecture
```

## Python extractor CLI

Preferred usage:

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

Backward-compatible usage:

```bash
python python_kdm_extractor/main.py examples/pymape_hierarchical
```

## KDM generator CLI

Generate KDM directly from JSON:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi
```

Use a custom metamodel:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi \
  --metamodel kdm_pyecore_generator/metamodels/kdm_1_4.ecore
```

Disable validation:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi \
  --no-validation
```

## Common inspection commands

Inspect recovered components:

```bash
jq '.structure_model.components[] | {
  name: .name,
  role: .role,
  stereotype_name: .stereotype_name,
  confidence: .confidence,
  source: .source
}' outputs/pymape_hierarchical/python_model.architecture.json
```

Inspect control loops:

```bash
jq '.structure_model.control_loops[] | {
  id: .id,
  name: .name,
  loop_completeness: .loop_completeness,
  missing_roles: .missing_roles,
  components: .components
}' outputs/pymape_hierarchical/python_model.architecture.json
```

Inspect containment relationships:

```bash
jq '.structure_model.containment_relationships[] | {
  source: .source,
  type: .type,
  target: .target
}' outputs/pymape_hierarchical/python_model.architecture.json
```

Inspect KDM stereotypes:

```bash
grep -n "extensionFamily\\|Adaptive System Domain\\|stereotype=" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -100
```

Inspect architecture nesting:

```bash
grep -n "Managing Subsystem\\|Managed Subsystem\\|Control Loop\\|nested_under" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -200
```

## Documentation server

Run:

```bash
mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000
```
