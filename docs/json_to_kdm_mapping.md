# JSON to KDM Mapping

## Purpose

This document describes how the JSON model produced by `python_kdm_extractor` and optionally enriched by `kdm_architecture_recovery` is transformed into a KDM 1.4 XMI model.

The generator is implemented in `kdm_pyecore_generator`.

```text
JSON model
   ↓
PyEcore KDM factory and mappers
   ↓
KDM 1.4 XMI
```

## Main mapping overview

| JSON concept | KDM representation |
|---|---|
| Project | `kdm::Segment` |
| Source file | `inventory::SourceFile` and `code::CompilationUnit` |
| Import | `code::Imports` |
| Class | `code::ClassUnit` |
| Method | `code::MethodUnit` |
| Function | `code::CallableUnit` |
| Parameter | `code::ParameterUnit` |
| Variable | `code::StorableUnit` |
| Callable body | `code::BlockUnit` |
| Statement | `action::ActionElement` or specialized action unit |
| Call | `action::Calls` |
| Constructor call | `action::Creates` |
| Read | `action::Reads` |
| Write | `action::Writes` |
| Type | `code::HasType` |
| Value | `code::Value` and `code::HasValue` |
| Return | `action::ActionElement` and `action::Reads` |
| Raise | `action::ActionElement` and `action::Throws` |
| Try block | `action::TryUnit` |
| Except block | `action::CatchUnit` and `action::ExceptionFlow` |
| Finally block | `action::FinallyUnit` and `action::ExitFlow` |
| Architecture component | `structure::Component` |
| Architecture subsystem | `structure::Subsystem` |
| Control loop | `structure::Component <<Control Loop>>` |
| Architecture relationship | `structure::StructureRelationship` and optionally `core::AggregatedRelationship` |

## Segment and models

The root object is a KDM `Segment`. It can contain:

- `InventoryModel`;
- internal `CodeModel`;
- external library `CodeModel`;
- Python builtins model;
- optional `StructureModel`;
- Adaptive System Domain `extensionFamily`.

## Inventory mapping

Each source file is mapped to an inventory element:

```xml
<model xsi:type="inventory:InventoryModel" name="InventoryModel">
  <inventoryElement xsi:type="inventory:SourceFile" name="app.py" path="..."/>
</model>
```

This supports source traceability through `SourceRef` and `SourceRegion`.

## Code mapping

Files, classes and callables are represented in the KDM code model.

Example:

```text
CodeModel
  CompilationUnit
    ClassUnit
      MethodUnit
        ParameterUnit
        StorableUnit
        BlockUnit
```

Functions that are not class methods are represented as `CallableUnit`.

## Body mapping

Callable bodies are represented using `BlockUnit`. Body statements are mapped to action elements and control-flow units.

Examples:

| Python construct | KDM representation |
|---|---|
| Assignment | `ActionElement` with `Writes` and optionally `HasValue` |
| Function call | `ActionElement` with `Calls` |
| Constructor call | `ActionElement` with `Creates` |
| Return | `ActionElement` with `Reads` |
| Raise | `ActionElement` with `Throws` |
| Try | `TryUnit` |
| Except | `CatchUnit` |
| Finally | `FinallyUnit` |

## StructureModel mapping

When `structure_model` exists in the input JSON, the generator creates a KDM `StructureModel`.

The architecture model can contain:

- `SoftwareSystem`;
- `ArchitectureView`;
- `Subsystem`;
- `Component`;
- `StructureRelationship`;
- `AggregatedRelationship`.

The Adaptive System Domain stereotypes are created as an `extensionFamily` under the KDM segment.

## Control loop mapping

KDM does not define a standard `structure::ControlLoop` metaclass. Therefore, a control loop is represented as:

```text
structure::Component <<Control Loop>>
```

Example:

```xml
<structureElement
    xsi:type="structure:Component"
    name="Loop Control Loop"
    stereotype="//@extensionFamily.0/@stereotype.8">
  <attribute tag="id" value="control_loop:loop"/>
  <attribute tag="structure_kind" value="control_loop"/>
</structureElement>
```

## Nested architecture mapping

The generator nests architecture elements to reflect containment.

Example:

```xml
<structureElement xsi:type="structure:Subsystem" name="Managing Subsystem">
  <structureElement xsi:type="structure:Component" name="Loop">
    <structureElement xsi:type="structure:Component" name="Loop Control Loop">
      <structureElement xsi:type="structure:Component" name="pid"/>
    </structureElement>
  </structureElement>
</structureElement>
```

This structure reflects:

```text
Managing Subsystem -> CL Manager -> Control Loop -> MAPE-K components
```

## Relationships and aggregated relations

Architecture relationships are represented as `structure::StructureRelationship`.

For selected relationships, the generator also creates `core::AggregatedRelationship`.

Examples:

- `contains`;
- `mapek_flow`;
- `uses_knowledge`;
- `subscribes_to`.

Relationship metadata is preserved using attributes such as:

- `relationship_type`;
- `relationship_level`;
- `confidence`;
- `source_role`;
- `target_role`;
- `composition_kind`;
- `derived_from`.

## Validation

After generation, the KDM model is validated. If validation reports errors, generation stops unless validation is explicitly disabled.
