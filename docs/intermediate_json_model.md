# Intermediate JSON Model

## Purpose

The intermediate JSON model is the contract between:

```text
python_kdm_extractor
kdm_architecture_recovery
kdm_pyecore_generator
```

It stores source-code information in a language-aware but KDM-independent format.

## Top-level structure

A typical JSON model contains:

```json
{
  "projectName": "pymape_hierarchical",
  "language": "python",
  "files": [],
  "elements": [],
  "relationships": [],
  "symbol_table": {},
  "summary": {}
}
```

When architecture recovery is enabled, the model may also contain:

```json
{
  "architecture_recovery": {},
  "structure_model": {}
}
```

## File model

Each file can include:

```json
{
  "id": "file:example.app",
  "name": "app.py",
  "path": "example/app.py",
  "qualified_name": "example.app",
  "imports": [],
  "classes": [],
  "functions": [],
  "global_variables": []
}
```

## Class model

Classes may include:

```json
{
  "id": "class:example.app.Service",
  "name": "Service",
  "qualified_name": "example.app.Service",
  "bases": [],
  "methods": [],
  "attributes": [],
  "instance_attributes": []
}
```

## Callable model

Functions and methods can include:

```json
{
  "id": "function:example.app.main",
  "name": "main",
  "qualified_name": "example.app.main",
  "parameters": [],
  "local_variables": [],
  "calls": [],
  "body": [],
  "decorators": []
}
```

## Body model

The `body` section preserves executable statements. It is used by the KDM generator to create body-level action elements and relations.

Typical statement kinds include:

- assignment;
- expression call;
- return;
- raise;
- if;
- for;
- while;
- try;
- except;
- finally.

## Architecture-enriched JSON

After architecture recovery, the JSON can contain:

```json
{
  "structure_model": {
    "software_system": {},
    "architecture_views": [],
    "role_suggestions": [],
    "components": [],
    "control_loops": [],
    "subsystems": [],
    "structure_relationships": [],
    "containment_relationships": [],
    "architecture_consistency": {}
  }
}
```

This section is the source of architectural truth for KDM `StructureModel` generation.
