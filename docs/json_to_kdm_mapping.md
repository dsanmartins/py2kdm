# JSON to KDM 1.4 Mapping

## 1. Purpose

This document describes how the intermediate JSON model produced by `python_kdm_extractor` is transformed into a KDM 1.4 XMI model by `kdm_pyecore_generator`.

The intermediate JSON model is the contract between both subprojects:

```text
python_kdm_extractor
        ↓
Intermediate JSON model
        ↓
kdm_pyecore_generator
        ↓
KDM 1.4 XMI
```

The goal of the mapping is not only to serialize Python information as XML, but to represent program structure and behavior using KDM metaclasses and relations.

---

## 2. General mapping overview

| JSON concept | KDM 1.4 representation |
|---|---|
| Project | `Segment` |
| Source file | `CompilationUnit` + `SourceFile` |
| Class | `ClassUnit` |
| Method | `MethodUnit` |
| Function | `CallableUnit` |
| Parameter | `ParameterUnit` |
| Local variable | `StorableUnit` |
| Callable body | `BlockUnit` |
| Function/method call | `ActionElement` + `Calls` |
| Constructor call | `ActionElement` + `Creates` |
| Assignment | `ActionElement` + `Writes` / `HasValue` |
| Variable read | `Reads` |
| Return | `ActionElement kind="return"` + `Reads` |
| Raise | `ActionElement kind="raise"` + `Throws` |
| Try block | `TryUnit` |
| Except block | `CatchUnit` + `ExceptionFlow` |
| Finally block | `FinallyUnit` + `ExitFlow` |
| Type information | `HasType` |
| Literal value | `Value` + `HasValue` |
| Import | `Imports` |
| Inheritance | `Extends` |
| Source traceability | `SourceRef` + `SourceRegion` |

---

## 3. Project mapping

### JSON

```json
{
  "projectName": "example_project",
  "language": "python",
  "files": []
}
```

### KDM

```text
Segment name="example_project"
```

The project root is mapped to a KDM `Segment`. The segment contains the inventory model, the internal code model, optional external code models and the Python builtins model.

---

## 4. Source file mapping

### JSON

```json
{
  "id": "file:example_project.app",
  "name": "app.py",
  "path": "example_project/app.py",
  "qualified_name": "example_project.app"
}
```

### KDM

```text
InventoryModel
 └── SourceFile name="app.py" path="example_project/app.py"

CodeModel
 └── CompilationUnit name="app.py"
```

Each source file is represented in two complementary KDM layers:

1. The inventory layer, using `InventoryModel` and `SourceFile`.
2. The code layer, using `CompilationUnit`.

The inventory layer enables source traceability through `SourceRef` and `SourceRegion`.

---

## 5. Class mapping

### JSON

```json
{
  "id": "class:example_project.models.User",
  "name": "User",
  "qualified_name": "example_project.models.User",
  "bases": ["BaseEntity"],
  "methods": []
}
```

### KDM

```text
CompilationUnit
 └── ClassUnit name="User"
      └── Extends → BaseEntity
```

A JSON class is mapped to a KDM `ClassUnit`. If the class has base classes, the generator creates `Extends` relations.

---

## 6. Function and method mapping

### Function JSON

```json
{
  "id": "function:example_project.utils.is_valid_name",
  "name": "is_valid_name",
  "qualified_name": "example_project.utils.is_valid_name",
  "parameters": [],
  "local_variables": [],
  "calls": [],
  "body": []
}
```

### Function KDM

```text
CompilationUnit
 └── CallableUnit name="is_valid_name"
```

### Method JSON

```json
{
  "id": "method:example_project.services.UserService.create_user",
  "name": "create_user",
  "qualified_name": "example_project.services.UserService.create_user",
  "parameters": [],
  "local_variables": [],
  "calls": [],
  "body": []
}
```

### Method KDM

```text
ClassUnit UserService
 └── MethodUnit name="create_user"
```

Functions are mapped to `CallableUnit`. Methods are mapped to `MethodUnit` and contained inside their corresponding `ClassUnit`.

---

## 7. Callable body mapping

The body of a function or method is not attached directly to the `CallableUnit` or `MethodUnit`.

Instead, the generator creates a `BlockUnit` for the executable body.

### KDM structure

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      ├── ActionElement
      ├── TryUnit
      ├── CatchUnit
      ├── FinallyUnit
      └── nested ActionElement nodes
```

The `BlockUnit` contains traceability metadata:

```xml
<attribute tag="role" value="callable_body"/>
<attribute tag="callable_body_id" value="method:..."/>
```

This design separates callable declaration from executable implementation and is more consistent with the KDM notion of logical executable blocks.

---

## 8. Parameter mapping

### JSON

```json
{
  "id": "param:create_user.name",
  "name": "name",
  "type": "str"
}
```

### KDM

```text
MethodUnit create_user
 └── ParameterUnit name="name"
      └── HasType → str
```

Parameters are mapped to `ParameterUnit`. If type information is available or resolved, a `HasType` relation is created.

---

## 9. Local variable mapping

### JSON

```json
{
  "id": "local:create_user.user",
  "name": "user",
  "assigned_type": "User"
}
```

### KDM

```text
MethodUnit create_user
 └── StorableUnit name="user"
      └── HasType → User
```

Local variables are mapped to `StorableUnit`. Type information is represented with `HasType`.

---

## 10. Call mapping

### JSON

```json
{
  "id": "call:001",
  "name": "save",
  "kind": "method_call",
  "classification": "internal",
  "target_id": "method:example_project.repository.UserRepository.save",
  "line": 20
}
```

### KDM

```text
ActionElement name="save" kind="method_call"
 └── Calls → MethodUnit save
```

Function and method calls are represented by an `ActionElement` and a `Calls` relation.

The final KDM does not store `target_id` or `resolved` as attributes. The semantic target is represented by the `to` reference of the `Calls` relation.

---

## 11. Constructor call mapping

### JSON

```json
{
  "id": "call:User",
  "name": "User",
  "kind": "constructor_call",
  "classification": "constructor",
  "target_id": "class:example_project.models.User",
  "line": 15
}
```

### KDM

```text
ActionElement name="User" kind="constructor_call"
 └── Creates → ClassUnit User
```

Constructor calls are mapped to `Creates` instead of `Calls`.

---

## 12. Assignment mapping

### JSON

```json
{
  "id": "body:assign_1",
  "type": "statement",
  "statement_type": "assignment",
  "targets": ["user"],
  "value": "User(name)",
  "line_start": 15,
  "line_end": 15
}
```

### KDM

```text
ActionElement kind="assignment"
 └── Writes → StorableUnit user
```

If the assigned value is a literal or a resolved value, the generator may also create a `HasValue` relation.

If the right-hand side contains a call, that call is modeled as a nested `ActionElement`.

---

## 13. Read/write mapping

Data accesses are modeled using KDM data-flow relations.

```text
read variable  → Reads → StorableUnit
write variable → Writes → StorableUnit
```

The generator validates that `Reads` and `Writes` point to `StorableUnit` elements.

---

## 14. Return mapping

KDM 1.4 does not define a specific `Returns` relation.

Therefore, the generator models returned values as values read by the `return` action.

### Return variable

#### JSON

```json
{
  "id": "body:return_user",
  "type": "statement",
  "statement_type": "return",
  "value": "user"
}
```

#### KDM

```text
ActionElement name="return" kind="return"
 └── Reads → StorableUnit user
```

### Return literal

#### JSON

```json
{
  "id": "body:return_true",
  "type": "statement",
  "statement_type": "return",
  "value": "True"
}
```

#### KDM

```text
ActionElement name="return" kind="return"
 ├── StorableUnit return_literal_True
 │    └── HasValue → Value True
 └── Reads → return_literal_True
```

### Return call result

#### JSON

```json
{
  "id": "body:return_call",
  "type": "statement",
  "statement_type": "return",
  "value_calls": [
    {
      "id": "call:json.dumps",
      "name": "json.dumps"
    }
  ]
}
```

#### KDM

```text
ActionElement name="return" kind="return"
 ├── StorableUnit return_value_of_json_dumps
 │    ├── role = returned_call_result
 │    └── source_call_name = json.dumps
 └── Reads → return_value_of_json_dumps
```

### Bare return

#### JSON

```json
{
  "id": "body:return_void",
  "type": "statement",
  "statement_type": "return",
  "value": null
}
```

#### KDM

```text
ActionElement name="return" kind="return"
 └── Attribute return_flow="void"
```

---

## 15. Raise mapping

### JSON

```json
{
  "id": "body:raise_repository_error",
  "type": "statement",
  "statement_type": "raise",
  "exception": "RepositoryError",
  "exception_calls": []
}
```

### KDM

```text
ActionElement name="raise" kind="raise"
 ├── StorableUnit RepositoryError_exception
 │    └── HasType → ClassUnit RepositoryError
 └── Throws → RepositoryError_exception
```

`Throws` points to a `StorableUnit` representing the thrown exception object, not directly to a `ClassUnit`.

### Bare raise

A bare `raise` is treated as a rethrow:

```text
ActionElement name="raise" kind="raise"
 └── Attribute exception_flow="rethrow"
```

---

## 16. Try / except / finally mapping

### JSON

```json
{
  "id": "body:try_1",
  "type": "control_structure",
  "control_type": "try",
  "body": [],
  "handlers": [],
  "orelse": [],
  "finalbody": []
}
```

### KDM

```text
TryUnit name="try"
 ├── CatchUnit name="except"
 ├── FinallyUnit name="finally"
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

### Except with exception type

```text
CatchUnit name="except"
 ├── ParameterUnit exception_RepositoryError
 │    └── HasType → RepositoryError
 ├── Attribute exception_type_name="RepositoryError"
 └── Attribute exception_target_name="RepositoryError"
```

### Bare except

```text
CatchUnit name="except"
 └── Attribute exception_flow="catch_all"
```

The generator does not use `ActionRelationship kind="catches"`. Catch behavior is represented using `CatchUnit` and `ExceptionFlow`.

---

## 17. Import mapping

### JSON

```json
{
  "name": "json",
  "classification": "external",
  "target_id": "external:json"
}
```

### KDM

```text
CompilationUnit
 └── Imports → external json element
```

The import target is represented by the `to` reference of the `Imports` relation.

---

## 18. Inheritance mapping

### JSON

```json
{
  "name": "UserService",
  "bases": ["BaseService"]
}
```

### KDM

```text
ClassUnit UserService
 └── Extends → ClassUnit BaseService
```

---

## 19. Source traceability mapping

KDM elements that correspond to source-level elements receive source traceability information.

```text
ActionElement / ClassUnit / MethodUnit / CallableUnit / BlockUnit
 └── SourceRef
      └── SourceRegion
```

A `SourceRegion` may include:

- source file path;
- source file reference;
- start line;
- end line;
- start position;
- end position.

The validator checks that source regions have at least a file reference or path and that line ranges are valid.

---

## 20. External and builtin elements

When a target is not internal to the analyzed project, the generator may create elements in an external model.

Examples include:

- builtin functions such as `print` or `len`;
- builtin exceptions such as `ValueError` or `OSError`;
- external libraries such as `json`.

Builtin exceptions are represented as `ClassUnit` elements inside the `PythonBuiltins` model.

```text
CodeModel PythonBuiltins
 └── ClassUnit ValueError
 └── ClassUnit OSError
```

---

## 21. Removed temporary attributes

Earlier versions of the generator used temporary attributes to store resolution information.

The final KDM output must not contain these attributes:

- `resolved`;
- `target_id`;
- `statement_type`;
- `body_type`;
- `control_type`;
- `condition`;
- `target`;
- `iter`;
- `exception`;
- `value`;
- `targets`;
- `kind` as a generic attribute.

This information is now represented by KDM metaclasses and relations.

---

## 22. Minimal traceability attributes

Some attributes are intentionally preserved as lightweight traceability or unresolved-status metadata.

Examples:

- `original_id`;
- `body_id`;
- `callable_body_id`;
- `classification`;
- `occurrence_index`;
- `expression_role`;
- `role`;
- `builtin_id`;
- `literal_value`;
- `exception_type_name`;
- `exception_target_name`;
- `source_call_name`;
- `return_flow`;
- `exception_flow`;
- `unresolved_return_value`;
- `unresolved_exception_type`;
- `resolution_status`;
- `unresolved_target_name`.

These attributes do not replace semantic KDM relations. They only provide traceability or mark unresolved cases.

---

## 23. Validation implications

The `KDMValidator` checks that the mapping is correctly applied.

Examples:

- `Reads` and `Writes` must point to `StorableUnit`.
- `Throws` must point to `StorableUnit`.
- `ExceptionFlow` must point to `CatchUnit`.
- `ExitFlow` must point to `FinallyUnit`.
- `return` actions must have `Reads`, `return_flow="void"`, or `unresolved_return_value`.
- `raise` actions must have `Throws` or `exception_flow="rethrow"`.
- `MethodUnit` and `CallableUnit` must not contain direct executable actions.
- Callable bodies must be represented with `BlockUnit`.
- Obsolete temporary attributes are treated as validation errors.

---

## 24. Summary

The current mapping strategy aims to produce a KDM model that is:

- structurally valid;
- semantically meaningful;
- traceable to source code;
- stable across serializations;
- testable using JSON fixtures;
- aligned with KDM 1.4 metaclasses and relations.

The most important design choices are:

```text
Callable body  → BlockUnit
return value   → Reads
raise          → Throws
try            → TryUnit
except         → CatchUnit + ExceptionFlow
finally        → FinallyUnit + ExitFlow
literal value  → Value + HasValue
variable access → Reads / Writes
```
