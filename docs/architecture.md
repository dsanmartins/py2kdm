# Architecture

## Overview

`py2kdm` is organized as a modular pipeline. Each stage produces an artifact that can be inspected independently.

```text
Python project
   ↓
python_kdm_extractor
   ↓
Intermediate JSON model
   ↓
kdm_architecture_recovery
   ↓
Architecture-enriched JSON model
   ↓
kdm_pyecore_generator
   ↓
KDM 1.4 XMI model
```

This design separates language-specific extraction from KDM generation and from architecture recovery.

## Subprojects

### `python_kdm_extractor`

The extractor analyzes Python source code and creates a JSON model. It uses Python's `ast` module and enriches the model with symbol-table, import-resolution, call-resolution and relationship information.

### `kdm_architecture_recovery`

The architecture recovery module analyzes the intermediate JSON model and, when applicable, creates a candidate self-adaptive architecture.

It can add:

- `architecture_recovery`;
- `structure_model`;
- `components`;
- `control_loops`;
- `subsystems`;
- `structure_relationships`;
- `containment_relationships`;
- `architecture_consistency`.

### `kdm_architecture_review`

The review module is intended to support human revision of proposed architectures. It separates automatic recovery from user-controlled corrections and is useful for future graphical or DSL-based architecture editing.

### `kdm_pyecore_generator`

The generator loads the KDM 1.4 Ecore metamodel with PyEcore and creates the final KDM XMI model.

It maps JSON data to:

- `InventoryModel`;
- `CodeModel`;
- external library models;
- Python builtins;
- KDM code elements;
- KDM action elements;
- KDM relations;
- optional `StructureModel`.

## Code-level recovery

At code level, the generator creates KDM elements such as:

- `CompilationUnit`;
- `ClassUnit`;
- `MethodUnit`;
- `CallableUnit`;
- `ParameterUnit`;
- `StorableUnit`;
- `BlockUnit`;
- `ActionElement`;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`.

It also creates relations such as:

- `Calls`;
- `Creates`;
- `Reads`;
- `Writes`;
- `HasType`;
- `HasValue`;
- `Imports`;
- `Extends`;
- `Throws`;
- `ExceptionFlow`;
- `ExitFlow`.

## Architecture-level recovery

When the input project contains enough self-adaptive evidence, the architecture recovery stage creates an inferred `StructureModel`.

The recovered structure can include:

```text
Managing Subsystem
  └── CL Manager
        └── Control Loop
              ├── Monitor
              ├── Analyzer
              ├── Planner
              ├── Executor
              └── Knowledge

Managed Subsystem
  ├── Sensor
  ├── Effector
  └── Measured Output
```

The architecture is generated through semantic construction rules. The system avoids creating invalid containment relationships such as `Managed Subsystem -> Planner`.

## KDM architecture stereotypes

The generator creates an Adaptive System Domain `extensionFamily` under the KDM segment. It contains stereotypes such as:

- `Monitor`
- `Analyzer`
- `Planner`
- `Executor`
- `Knowledge`
- `Reference Input`
- `Measured Output`
- `CL Manager`
- `Control Loop`
- `Sensor`
- `Effector`
- `Managing Subsystem`
- `Managed Subsystem`

These stereotypes are referenced by `structure::Component` and `structure::Subsystem` elements.

## Traceability

The architecture model remains linked to code through:

- `implementation` references;
- stable JSON identifiers;
- `implemented_by_id` attributes;
- evidence attributes;
- relationship metadata;
- `AggregatedRelationship` objects.
