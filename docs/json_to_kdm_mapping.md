# JSON to KDM mapping

The KDM generator maps the reviewed JSON model to KDM XMI using the KDM 1.4 Ecore metamodel.

## Code model

Static code elements are mapped to KDM CodeModel elements such as compilation units, classes, methods, parameters, local variables, block/action structures, calls, reads/writes, returns, and exceptions.

## Runtime evidence

Runtime calls are represented using KDM semantic relations where possible. The chosen approach keeps one semantic relation when a single relation is sufficient and avoids duplicating static and runtime relations unnecessarily.

## Structure model

Materialized architecture elements from `structure_model` are mapped to KDM StructureModel elements. Adaptive-system semantics are represented through KDM extension mechanisms such as stereotypes and extension families.

## Reviewed model as source

The final generator should use:

```text
python_model.reviewed_architecture.json
```

when human review was performed.
