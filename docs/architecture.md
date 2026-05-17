# Architecture

## 1. Overview

`py2kdm` is a two-stage toolchain for generating KDM 1.4 models from Python projects.

The project is organized into two main subprojects:

```text
py2kdm/
├── python_kdm_extractor/
└── kdm_pyecore_generator/
```

The first subproject extracts an intermediate JSON representation from Python source code. The second subproject transforms that JSON model into a KDM 1.4 XMI model using PyEcore.

The complete pipeline is:

```text
Python source code
        │
        ▼
python_kdm_extractor
        │
        ▼
Intermediate JSON model
        │
        ▼
kdm_pyecore_generator
        │
        ▼
KDM 1.4 XMI model
```

This separation makes the architecture modular: the extraction phase is language dependent, while the KDM generation phase is model driven and based on an explicit JSON contract.

---

## 2. Two-stage pipeline

### Stage 1: Python to intermediate JSON

The `python_kdm_extractor` subproject analyzes Python source code and produces a JSON model containing structural and behavioral information.

It identifies elements such as:

- source files;
- imports;
- classes;
- methods;
- functions;
- parameters;
- local variables;
- calls;
- assignments;
- control structures;
- returns;
- exceptions;
- nested body statements.

The output of this stage is an intermediate JSON model. This model acts as the input contract for the KDM generator.

### Stage 2: Intermediate JSON to KDM 1.4

The `kdm_pyecore_generator` subproject reads the intermediate JSON model and generates a KDM 1.4 XMI model.

This stage is responsible for:

- loading the KDM 1.4 Ecore metamodel;
- creating KDM elements using PyEcore;
- mapping JSON structural elements to KDM code elements;
- mapping calls, reads, writes, types and values to KDM relations;
- modeling body actions and nested actions;
- modeling exceptions using KDM action relations;
- validating the generated KDM model;
- serializing the final model as XMI.

---

## 3. Intermediate JSON model as contract

The intermediate JSON model is the contract between both subprojects.

The extractor does not generate KDM directly. Instead, it creates a normalized representation of the Python project. The generator then consumes this representation and transforms it into KDM.

This design has several advantages:

1. **Separation of concerns**  
   Python parsing and KDM generation are independent responsibilities.

2. **Testability**  
   The KDM generator can be tested using small JSON fixtures without requiring real Python projects.

3. **Extensibility**  
   Other language extractors could eventually produce the same intermediate JSON format.

4. **Traceability**  
   JSON element identifiers are preserved as lightweight traceability attributes in the generated KDM.

---

## 4. Main architecture of `python_kdm_extractor`

The role of `python_kdm_extractor` is to analyze Python source code and produce a structured JSON model.

Conceptually, this subproject performs the following steps:

```text
Python files
   │
   ▼
AST parsing
   │
   ▼
Symbol and structure extraction
   │
   ▼
Call, type and body analysis
   │
   ▼
Intermediate JSON model
```

The generated JSON contains enough information for the KDM generator to create a semantically meaningful model, including body-level information such as returns, raises, try blocks, exception handlers and nested calls.

The extractor is intentionally separated from KDM-specific details. It should not need to know how `TryUnit`, `CatchUnit`, `Reads` or `Throws` are represented in KDM. Its responsibility is to expose the relevant Python information in a consistent JSON format.

---

## 5. Main architecture of `kdm_pyecore_generator`

The `kdm_pyecore_generator` subproject transforms the intermediate JSON model into KDM.

Its main flow is:

```text
Load KDM 1.4 Ecore metamodel
        │
        ▼
Load intermediate JSON model
        │
        ▼
Create Segment
        │
        ▼
Create InventoryModel and SourceFile elements
        │
        ▼
Create CodeModel and structural elements
        │
        ▼
Resolve types, calls, values and accesses
        │
        ▼
Map body statements and control structures
        │
        ▼
Resolve exceptions and returns
        │
        ▼
Validate generated KDM
        │
        ▼
Serialize XMI
```

The generator is organized around specialized components. Each component is responsible for a specific part of the KDM construction process.

---

## 6. Main components of `kdm_pyecore_generator`

### `KDMLoader`

Loads the KDM 1.4 Ecore metamodel and returns the PyEcore resource set and root package.

### `ClassifierResolver`

Finds KDM metaclasses by name inside the loaded Ecore metamodel.

It is used by the factory to access elements such as:

- `Segment`;
- `CodeModel`;
- `CompilationUnit`;
- `ClassUnit`;
- `MethodUnit`;
- `CallableUnit`;
- `BlockUnit`;
- `ActionElement`;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`;
- `Calls`;
- `Creates`;
- `Reads`;
- `Writes`;
- `Throws`;
- `ExceptionFlow`;
- `ExitFlow`.

### `KDMFactory`

Centralizes the creation of KDM elements and relations.

It creates elements such as:

- `Segment`;
- `InventoryModel`;
- `SourceFile`;
- `CodeModel`;
- `CompilationUnit`;
- `ClassUnit`;
- `MethodUnit`;
- `CallableUnit`;
- `BlockUnit`;
- `ActionElement`;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`;
- `StorableUnit`;
- `ParameterUnit`;
- `Value`.

It also creates relations such as:

- `Calls`;
- `Creates`;
- `Reads`;
- `Writes`;
- `Throws`;
- `HasType`;
- `HasValue`;
- `Imports`;
- `Extends`;
- `ExceptionFlow`;
- `ExitFlow`.

The factory avoids scattering PyEcore construction logic across the codebase.

### `InventoryBuilder`

Creates the KDM inventory layer.

It maps source files from the JSON model to:

```text
InventoryModel
 └── SourceFile
```

This enables source traceability through `SourceRef` and `SourceRegion`.

### `JsonToKDMMapper`

Creates the main structural code model.

It maps JSON elements to KDM code elements, for example:

| JSON element | KDM element |
|---|---|
| project | `Segment` |
| file | `CompilationUnit` |
| class | `ClassUnit` |
| method | `MethodUnit` |
| function | `CallableUnit` |
| parameter | `ParameterUnit` |
| local variable | `StorableUnit` |

It also builds indexes used by later resolvers.

### `ReferenceResolver`

Creates call-related action elements and resolves call targets.

It maps:

```text
function or method call → ActionElement + Calls
constructor call        → ActionElement + Creates
import                  → Imports
inheritance             → Extends
```

After the attribute-reduction phase, semantic resolution is represented using KDM relations instead of temporary attributes such as `resolved` or `target_id`.

### `BodyActionMapper`

Maps executable body statements and control structures.

It is responsible for creating the executable structure inside methods and functions.

The current body structure is:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      ├── ActionElement
      ├── TryUnit
      ├── CatchUnit
      ├── FinallyUnit
      └── nested ActionElement nodes
```

The body of a method or function is not attached directly to the `MethodUnit` or `CallableUnit`. Instead, it is placed inside a `BlockUnit`. This is more consistent with KDM because `BlockUnit` represents a logical block of executable actions.

The mapper also handles nesting of actions inside:

- control structures;
- returns;
- raises;
- try blocks;
- exception handlers;
- finally blocks;
- expression-level calls;
- nested calls on the same source line.

### `ExceptionRelationResolver`

Models Python exception semantics using KDM action relations.

It maps:

```text
raise X(...)
  → ActionElement kind="raise"
  → StorableUnit X_exception
  → Throws → X_exception
  → X_exception --HasType--> X
```

It also maps try/except/finally structures as:

```text
TryUnit
 ├── CatchUnit
 ├── FinallyUnit
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

The generator does not use a generic `ActionRelationship` with `kind="catches"`. Instead, exception handling is represented with KDM-specific elements and relations.

### `ReturnRelationResolver`

Models return values using standard KDM data-flow relations.

KDM 1.4 does not define a specific `Returns` relation. Therefore, returned values are modeled as data read by the `return` action.

Examples:

```text
return x
  → ActionElement kind="return"
  → Reads → StorableUnit x
```

```text
return True
  → ActionElement kind="return"
  → StorableUnit return_literal_True
  → Value value_True
  → return_literal_True --HasValue--> value_True
  → return --Reads--> return_literal_True
```

```text
return f(...)
  → ActionElement kind="return"
  → StorableUnit return_value_of_f
  → return --Reads--> return_value_of_f
```

### `TypeRelationResolver`

Creates `HasType` relations for typable elements such as parameters, local variables and exception objects.

### `ValueRelationResolver`

Creates `HasValue` relations for assigned values and literal values when appropriate.

### `AccessRelationResolver`

Creates data access relations:

```text
read access  → Reads
write access → Writes
```

These relations connect actions to `StorableUnit` elements.

### `KDMValidator`

Validates the generated KDM model.

It checks:

- inventory consistency;
- source traceability;
- relation targets;
- absence of obsolete temporary attributes;
- return semantics;
- raise semantics;
- try/catch/finally flows;
- callable body structure using `BlockUnit`;
- duplicate attributes;
- duplicate source regions;
- duplicate child actions.

---

## 7. KDM body modeling decision

A key design decision is that the executable body of a method or function is modeled using `BlockUnit`.

The chosen structure is:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      └── executable actions
```

This avoids placing executable actions directly under `MethodUnit` or `CallableUnit`.

This decision improves:

- semantic clarity;
- consistency with KDM block modeling;
- validation;
- future transformations;
- separation between declaration and executable body.

The validator enforces that direct executable actions should not appear directly under `MethodUnit` or `CallableUnit`.

---

## 8. Exception modeling decision

Exception handling is represented using KDM-specific action elements and relations.

The current mapping is:

```text
try
  → TryUnit

except
  → CatchUnit

finally
  → FinallyUnit
```

and:

```text
TryUnit --ExceptionFlow--> CatchUnit
TryUnit --ExitFlow-------> FinallyUnit
```

Raised exceptions are modeled as thrown data objects:

```text
raise RepositoryError(...)
  → ActionElement kind="raise"
  → StorableUnit RepositoryError_exception
  → Throws → RepositoryError_exception
  → RepositoryError_exception --HasType--> RepositoryError
```

This avoids relying on temporary attributes such as `kind="catches"`.

---

## 9. Return modeling decision

Returns are represented using `Reads`.

The generator does not use:

```text
ActionRelationship kind="returns"
```

Instead, it uses:

```text
return → Reads → returned value
```

The returned value must be a `StorableUnit`.

For literals, the generator creates a temporary `StorableUnit` and links it to a `Value` using `HasValue`.

For returned calls, the generator creates a temporary `StorableUnit` representing the result of the call.

---

## 10. Attribute reduction strategy

Earlier versions of the generator used temporary attributes such as:

- `resolved`;
- `target_id`;
- `statement_type`;
- `body_type`;
- `control_type`;
- `condition`;
- `exception`;
- `value`;
- `kind` as an attribute.

These attributes have been removed from the final KDM output when their meaning is already represented by KDM metaclasses or relations.

For example:

| Old temporary attribute | Current KDM representation |
|---|---|
| `target_id` | `Calls.to`, `Creates.to`, `Imports.to`, etc. |
| `resolved` | presence of a semantic relation |
| `statement_type=return` | `ActionElement kind="return"` |
| `exception` | `CatchUnit` annotations and `HasType` |
| `value` | `Reads`, `HasValue`, `Value` |
| `kind=catches` | `ExceptionFlow` |

The validator treats obsolete attributes as errors.

---

## 11. Validation pipeline

The generator uses two levels of validation.

### JSON-level validation

The `BasicValidator` checks unresolved calls and issues detected at the JSON model level.

### KDM-level validation

The `KDMValidator` checks the generated KDM model.

It validates:

```text
InventoryModel
SourceFile
SourceRegion
HasType
HasValue
Calls
Creates
Reads
Writes
Throws
ExceptionFlow
ExitFlow
Imports
Extends
BlockUnit body structure
Obsolete attributes
Duplicate attributes
Duplicate source regions
Duplicate child actions
```

If KDM validation fails, generation stops with an error before producing a final accepted output.

---

## 12. Testing strategy

The project uses `pytest`.

The tests cover:

- stable serialization;
- absence of obsolete attributes;
- semantic KDM relations;
- exception mapping;
- return mapping;
- `BlockUnit` body mapping;
- fixture-based Python edge cases;
- CLI input/output options.

The generator also supports custom input and output paths:

```bash
python src/main.py \
  --input tests/fixtures/bare_raise.json \
  --output output/test_bare_raise.kdm.xmi
```

This allows tests to run without modifying the default `input/python_model.json`.

---

## 13. Current architectural status

The current architecture supports:

- two-stage Python to JSON to KDM transformation;
- PyEcore-based generation of KDM 1.4 XMI;
- source traceability through `SourceFile`, `SourceRef` and `SourceRegion`;
- callable bodies modeled with `BlockUnit`;
- call and constructor relations with `Calls` and `Creates`;
- data access with `Reads` and `Writes`;
- values with `HasValue`;
- types with `HasType`;
- exceptions with `Throws`, `TryUnit`, `CatchUnit`, `FinallyUnit`, `ExceptionFlow` and `ExitFlow`;
- returns with `Reads`;
- custom KDM validation;
- stable serialization;
- automated tests.

---

## 14. Future extensions

Possible future improvements include:

- extending the intermediate JSON model for more Python constructs;
- adding support for module-level executable blocks;
- improving type inference;
- modeling control-flow relations beyond exception flows;
- adding more precise mappings for boolean and arithmetic expressions;
- supporting additional languages that generate the same intermediate JSON contract;
- adding model-to-model transformations from KDM to other architecture models.
