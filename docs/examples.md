# Examples and Case Studies

## Available examples

The repository includes example systems under `examples/`.

Typical examples include:

```text
examples/
├── pymape_hierarchical/
└── three_layer_system/
```

## PyMAPE hierarchical example

Run:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Expected outputs:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/python_model.architecture.json
outputs/pymape_hierarchical/model.kdm.xmi
```

This example is useful for testing MAPE-K recovery because it contains explicit control-loop evidence, decorators and self-adaptive vocabulary.

Expected architecture features include:

- `Managing Subsystem`;
- `CL Manager`;
- `Control Loop`;
- `Monitor`;
- `Planner`;
- `Executor`;
- `Knowledge`;
- `Managed Subsystem`;
- `Effector`.

Some abstractions, such as `Reference Input`, `Measured Output` or `Sensor`, may not be recovered if the code does not contain explicit evidence.

## Three-layer system example

Run:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

This example is useful for checking that conventional systems are not over-interpreted as self-adaptive systems.

The autonomic applicability gate should prevent automatic MAPE-K recovery unless enough evidence is present.

## Inspecting generated artifacts

Inspect the architecture JSON:

```bash
jq '.structure_model' outputs/pymape_hierarchical/python_model.architecture.json
```

Inspect only recovered components:

```bash
jq '.structure_model.components[] | {
  name: .name,
  role: .role,
  status: .status,
  confidence: .confidence
}' outputs/pymape_hierarchical/python_model.architecture.json
```

Inspect the KDM XMI:

```bash
grep -n "StructureModel\\|extensionFamily\\|Control Loop" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -100
```

## Adding a new example

1. Create a new folder under `examples/`.
2. Add Python source files.
3. Create a matching config file under `configs/`.
4. Run:

```bash
python run_pipeline.py --config configs/my_example.json
```

5. Inspect outputs under `outputs/my_example/`.
