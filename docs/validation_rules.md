# Validation Rules

## Purpose

The KDM generator includes validation to ensure that the generated KDM model is structurally consistent and does not contain temporary or obsolete artifacts.

Validation here refers to technical consistency of the generated JSON and KDM model. It is different from semantic architecture construction rules, which are applied during architecture recovery.

## Validation levels

```text
Input JSON
   ↓
BasicValidator
   ↓
KDM generation
   ↓
KDMValidator
   ↓
KDM XMI
```

## JSON-level validation

The `BasicValidator` checks the input JSON before generation. It can report unresolved or suspicious information that may affect the generated model.

Typical checks include:

- presence of project-level fields;
- consistency of files and elements;
- unresolved references when available;
- missing fields required by the generator.

## KDM-level validation

The `KDMValidator` checks the generated KDM model.

Typical validation areas are:

- inventory model consistency;
- source file and source region consistency;
- valid code model structure;
- body representation;
- relation targets;
- type/value/access relations;
- exception and return-flow relations;
- architecture structure model consistency;
- obsolete or temporary attributes.

## Inventory validation

Expected structure:

```text
Segment
  InventoryModel
    SourceFile
```

Rules include:

| Rule | Severity |
|---|---|
| The segment should contain an `InventoryModel`. | Error |
| Source files should have paths. | Error |
| Source regions should have valid line ranges. | Error |

## Code model validation

Expected structure:

```text
CodeModel
  CompilationUnit
    ClassUnit / CallableUnit
```

Rules include:

| Rule | Severity |
|---|---|
| Code models should contain code elements. | Error |
| Compilation units should have names. | Error |
| Methods and callables should have valid containers. | Error |
| Callable bodies should be represented with `BlockUnit`. | Warning or Error depending on context |

## Relation validation

The generator validates that relation targets are meaningful and that relations are not dangling.

Examples:

| Relation | Expected target |
|---|---|
| `Calls` | Callable or method-like element |
| `Creates` | Class or constructor-like element |
| `Reads` | Storable or value-like element |
| `Writes` | Storable element |
| `HasType` | Type-like element |
| `HasValue` | Value-like element |
| `Throws` | Exception-related element |
| `ExceptionFlow` | Catch or exception-flow target |
| `ExitFlow` | Finally or exit-flow target |

## Architecture StructureModel validation

When the input JSON contains architecture recovery information, the generated KDM may include a `StructureModel`.

The KDM validation should verify:

- `StructureModel` existence when architecture input is present;
- valid `structureElement` nesting;
- valid `implementation` references when available;
- valid stereotype references;
- `extensionFamily` presence when stereotypes are used;
- valid `StructureRelationship` source and target references;
- valid `AggregatedRelationship` links.

## Semantic construction rules are not post-hoc validation

Architecture recovery uses semantic construction rules during model construction.

For example, the system does not first create:

```text
Managed Subsystem -> Planner
```

and then reject it later. Instead, the construction rule prevents that relationship from being created.

The generated JSON can contain an `architecture_consistency` section. This is a construction report, not a separate external validation stage.

## Running without validation

The KDM generator supports:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/project/python_model.architecture.json \
  --output outputs/project/model.kdm.xmi \
  --no-validation
```

This should only be used for debugging, because invalid KDM may be serialized.
