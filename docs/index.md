# py2kdm

`py2kdm` is a configurable Python-to-KDM 1.4 toolchain for reverse engineering Python projects into KDM/EMF-compatible models.

It supports both code-level recovery and architecture-level recovery.

```text
Python project
   ↓
Intermediate JSON
   ↓
Architecture-enriched JSON
   ↓
KDM 1.4 XMI
```

## Main subprojects

```text
python_kdm_extractor
  Python source code → intermediate JSON model

kdm_architecture_recovery
  intermediate JSON → architecture-enriched JSON model

kdm_architecture_review
  review support for architecture proposals

kdm_pyecore_generator
  JSON model → KDM 1.4 XMI model
```

## What py2kdm generates

The final KDM XMI can contain:

- source inventory information;
- code structure;
- body-level action elements;
- calls, creates, reads, writes, imports, types and values;
- exception and return-flow relations;
- external library models;
- built-in Python type references;
- an optional architecture `StructureModel`;
- Adaptive System Domain stereotypes for self-adaptive systems;
- architecture containment and traceability links.

## Recommended usage

Run the full configurable pipeline from the project root:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

Run without KDM generation:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
```

Generate documentation locally:

```bash
mkdocs serve
```

## Documentation map

Use the navigation menu to inspect:

- the general architecture;
- pipeline configuration;
- the Python extractor;
- the intermediate JSON model;
- architecture recovery and MAPE-K rules;
- JSON-to-KDM mapping;
- validation rules;
- command-line usage;
- examples and limitations.
