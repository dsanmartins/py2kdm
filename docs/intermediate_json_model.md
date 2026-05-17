# Intermediate JSON Model

## 1. Purpose

The intermediate JSON model is the contract between the two subprojects of `py2kdm`:

```text
python_kdm_extractor
        ↓
intermediate JSON model
        ↓
kdm_pyecore_generator
```

The extractor is responsible for analyzing Python source code and producing this JSON model. The generator is responsible for consuming the JSON model and transforming it into a KDM 1.4 XMI model.

This separation allows the extractor to remain Python-specific while the KDM generator remains model-driven and independent from Python parsing details.

The intermediate JSON model should contain enough information to reconstruct the structural and executable aspects of a Python project in KDM, including files, classes, functions, methods, parameters, local variables, calls, assignments, returns, exceptions and nested body statements.

---

## 2. Top-level structure

A valid intermediate JSON model has the following top-level structure:

```json
{
  "projectName": "example_project",
  "language": "python",
  "files": []
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `projectName` | string | yes | Name of the analyzed project. It is used to create the root KDM `Segment` and the internal `CodeModel`. |
| `language` | string | yes | Source language. For this extractor, the value is usually `python`. |
| `files` | array | yes | List of source files discovered in the project. |

---

## 3. File model

Each file is represented as an object inside `files`.

```json
{
  "id": "file:example_project.services.user_service",
  "name": "user_service.py",
  "path": "example_project/services/user_service.py",
  "qualified_name": "example_project.services.user_service",
  "imports": [],
  "classes": [],
  "functions": []
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable identifier of the file. |
| `name` | string | yes | File name. |
| `path` | string | yes | Relative or absolute source path. Used for source traceability. |
| `qualified_name` | string | recommended | Python module-like qualified name. |
| `imports` | array | yes | Imports declared in the file. |
| `classes` | array | yes | Classes declared in the file. |
| `functions` | array | yes | Top-level functions declared in the file. |

### KDM role

The generator maps file information mainly to:

```text
InventoryModel / SourceFile
CodeModel / CompilationUnit
```

---

## 4. Import model

Imports are represented inside the `imports` array of each file.

```json
{
  "module": "json",
  "name": "json",
  "alias": null,
  "line": 1,
  "classification": "external",
  "resolved": true,
  "target_id": "external:json"
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `module` | string | recommended | Imported module. |
| `name` | string | recommended | Imported symbol or module name. |
| `alias` | string/null | optional | Alias used in the import. |
| `line` | integer | recommended | Source line. |
| `classification` | string | recommended | Resolution category, for example `internal`, `external`, `builtin`. |
| `resolved` | boolean | optional | Resolution status used by the extractor. This is not serialized as a final KDM attribute. |
| `target_id` | string | recommended if resolved | Target identifier used by the generator to create `Imports`. This is not serialized as a final KDM attribute. |

### KDM role

The generator maps resolved imports to:

```text
CompilationUnit --Imports--> imported target
```

Temporary fields such as `resolved` and `target_id` are used internally during generation but should not appear as final KDM attributes.

---

## 5. Class model

Classes are represented inside the `classes` array of each file.

```json
{
  "id": "class:example_project.services.user_service.UserService",
  "name": "UserService",
  "qualified_name": "example_project.services.user_service.UserService",
  "bases": ["BaseService"],
  "methods": []
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable class identifier. |
| `name` | string | yes | Simple class name. |
| `qualified_name` | string | yes | Fully qualified class name. |
| `bases` | array | optional | Base classes. |
| `methods` | array | yes | Methods declared in the class. |

### KDM role

Classes are mapped to:

```text
ClassUnit
```

Inheritance is mapped to:

```text
ClassUnit --Extends--> base ClassUnit
```

---

## 6. Function and method model

Functions and methods share the same basic structure.

```json
{
  "id": "function:example_project.utils.validators.is_valid_name",
  "name": "is_valid_name",
  "qualified_name": "example_project.utils.validators.is_valid_name",
  "parameters": [],
  "local_variables": [],
  "calls": [],
  "body": []
}
```

For methods:

```json
{
  "id": "method:example_project.services.user_service.UserService.create_user",
  "name": "create_user",
  "qualified_name": "example_project.services.user_service.UserService.create_user",
  "parameters": [],
  "local_variables": [],
  "calls": [],
  "body": []
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable identifier. Usually prefixed by `function:` or `method:`. |
| `name` | string | yes | Function or method name. |
| `qualified_name` | string | yes | Fully qualified callable name. |
| `parameters` | array | yes | Parameters. |
| `local_variables` | array | yes | Local variables detected in the callable. |
| `calls` | array | yes | Calls detected inside the callable. |
| `body` | array | yes | Body statements and control structures. |

### KDM role

Functions are mapped to:

```text
CallableUnit
```

Methods are mapped to:

```text
MethodUnit
```

Executable body statements are not attached directly to the `CallableUnit` or `MethodUnit`. They are placed inside a KDM `BlockUnit`:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      └── executable actions
```

---

## 7. Parameter model

Parameters are represented inside `parameters`.

```json
{
  "id": "param:example_project.services.user_service.UserService.create_user.name",
  "name": "name",
  "type": "str"
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable parameter identifier. |
| `name` | string | yes | Parameter name. |
| `type` | string/null | optional | Declared or inferred type. |

### KDM role

Parameters are mapped to:

```text
ParameterUnit
```

If type information is available, the generator may create:

```text
ParameterUnit --HasType--> Datatype
```

---

## 8. Local variable model

Local variables are represented inside `local_variables`.

```json
{
  "id": "local:example_project.services.user_service.UserService.create_user.user",
  "name": "user",
  "assigned_type": "User",
  "assigned_value": "User(name)"
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable local variable identifier. |
| `name` | string | yes | Variable name. |
| `assigned_type` | string/null | optional | Inferred or assigned type. |
| `assigned_value` | string/null | optional | Assigned expression as extracted from Python. |

### KDM role

Local variables are mapped to:

```text
StorableUnit
```

Type and value information may be represented through:

```text
HasType
HasValue
```

Temporary fields such as `assigned_type` and `assigned_value` should not appear as final KDM attributes if they are semantically represented by KDM relations.

---

## 9. Call model

Calls are represented inside the `calls` array of a callable. They are also referenced by body statements using identifiers.

```json
{
  "id": "call:abc123",
  "name": "json.dumps",
  "kind": "function_call",
  "line": 10,
  "classification": "external",
  "resolved": true,
  "target_id": "external:json.dumps",
  "occurrence_index": 0
}
```

### Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable call identifier. |
| `name` | string | yes | Display or qualified call name. |
| `kind` | string | recommended | Call kind, for example `function_call`, `method_call`, `constructor_call`. |
| `line` | integer | recommended | Source line. |
| `classification` | string | recommended | Internal, external, builtin, constructor, etc. |
| `resolved` | boolean | optional | Resolution status. Used internally, not serialized as final KDM attribute. |
| `target_id` | string | optional | Target id used to create KDM relations. Used internally, not serialized as final KDM attribute. |
| `occurrence_index` | integer | optional | Used to distinguish repeated calls on the same line. |

### KDM role

Calls are mapped to:

```text
ActionElement + Calls
```

Constructor calls are mapped to:

```text
ActionElement + Creates
```

The final KDM output should use semantic relations rather than `resolved` or `target_id` attributes.

---

## 10. Body node model

The `body` array represents executable statements and control structures.

Every body node should have at least:

```json
{
  "id": "body:unique_id",
  "type": "statement",
  "line_start": 1,
  "line_end": 1
}
```

### Common fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `id` | string | yes | Stable body node identifier. |
| `type` | string | yes | Node category, for example `statement`, `control_structure`, `exception_handler`. |
| `statement_type` | string/null | depends | Used for statement nodes, for example `return`, `raise`, `assignment`, `call`. |
| `control_type` | string/null | depends | Used for control structures, for example `if`, `for`, `while`, `try`. |
| `line_start` | integer | recommended | Start line. |
| `line_end` | integer | recommended | End line. |
| `body` | array | optional | Nested body statements. |
| `orelse` | array | optional | Else branch statements. |
| `handlers` | array | optional | Exception handlers for try statements. |
| `finalbody` | array | optional | Finally body for try statements. |

The generator uses these nodes to create nested KDM action structures.

---

## 11. Return statement

A return statement is represented as:

```json
{
  "id": "body:return_true",
  "type": "statement",
  "statement_type": "return",
  "line_start": 10,
  "line_end": 10,
  "value": "True"
}
```

A bare return is represented with `value: null`:

```json
{
  "id": "body:return_void",
  "type": "statement",
  "statement_type": "return",
  "line_start": 10,
  "line_end": 10,
  "value": null
}
```

### Optional call-related fields

For returns involving calls, the node may reference call objects:

```json
{
  "id": "body:return_call",
  "type": "statement",
  "statement_type": "return",
  "line_start": 10,
  "line_end": 10,
  "value": "json.dumps(data)",
  "value_calls": [
    {
      "id": "call:json_dumps"
    }
  ]
}
```

### KDM role

Returns are mapped to:

```text
ActionElement kind="return"
```

The returned value is represented using `Reads`.

Examples:

```text
return x
  → return --Reads--> StorableUnit x
```

```text
return True
  → return --Reads--> StorableUnit return_literal_True
  → return_literal_True --HasValue--> Value True
```

```text
return f(...)
  → return --Reads--> StorableUnit return_value_of_f
```

---

## 12. Raise statement

A raise statement is represented as:

```json
{
  "id": "body:raise_repository_error",
  "type": "statement",
  "statement_type": "raise",
  "line_start": 20,
  "line_end": 20,
  "exception": "RepositoryError",
  "exception_calls": []
}
```

A bare raise is represented as:

```json
{
  "id": "body:raise_bare",
  "type": "statement",
  "statement_type": "raise",
  "line_start": 20,
  "line_end": 20,
  "exception": null,
  "exception_calls": []
}
```

### KDM role

Typed raises are mapped to:

```text
ActionElement kind="raise"
 ├── StorableUnit X_exception
 ├── Throws → X_exception
 └── X_exception --HasType--> X
```

Bare raises are marked as rethrows:

```text
ActionElement kind="raise"
 └── attribute exception_flow = rethrow
```

---

## 13. Try / except / finally model

A try statement is represented as a control structure:

```json
{
  "id": "body:try_1",
  "type": "control_structure",
  "control_type": "try",
  "line_start": 1,
  "line_end": 5,
  "body": [],
  "handlers": [],
  "orelse": [],
  "finalbody": []
}
```

### Exception handler

An exception handler is represented inside `handlers`:

```json
{
  "id": "body:except_repository_error",
  "type": "exception_handler",
  "line_start": 3,
  "line_end": 4,
  "exception": "RepositoryError",
  "body": []
}
```

A bare except is represented with `exception: null`:

```json
{
  "id": "body:except_all",
  "type": "exception_handler",
  "line_start": 3,
  "line_end": 4,
  "exception": null,
  "body": []
}
```

### Finally body

The `finalbody` field contains statements executed in the finally block:

```json
{
  "id": "body:try_1",
  "type": "control_structure",
  "control_type": "try",
  "body": [],
  "handlers": [],
  "orelse": [],
  "finalbody": [
    {
      "id": "body:return_void",
      "type": "statement",
      "statement_type": "return",
      "line_start": 5,
      "line_end": 5,
      "value": null
    }
  ]
}
```

### KDM role

The generator maps:

```text
try     → TryUnit
except  → CatchUnit
finally → FinallyUnit
```

Relations:

```text
TryUnit --ExceptionFlow--> CatchUnit
TryUnit --ExitFlow-------> FinallyUnit
```

---

## 14. Assignment statement

Assignments are represented as body statements.

```json
{
  "id": "body:assign_user",
  "type": "statement",
  "statement_type": "assignment",
  "line_start": 8,
  "line_end": 8,
  "targets": ["user"],
  "value": "User(name)",
  "value_calls": [
    {
      "id": "call:user_constructor"
    }
  ]
}
```

### KDM role

Assignments may be mapped to:

```text
ActionElement kind="assignment"
Writes → target StorableUnit
HasValue → assigned value
```

If the assigned expression contains a call, the corresponding call action can be nested inside the assignment action.

---

## 15. Control structures

Control structures use:

```json
{
  "id": "body:if_1",
  "type": "control_structure",
  "control_type": "if",
  "line_start": 1,
  "line_end": 4,
  "condition": "x > 0",
  "condition_calls": [],
  "body": [],
  "orelse": []
}
```

Supported control structure names may include:

- `if`;
- `for`;
- `while`;
- `with`;
- `try`.

### KDM role

Generic control structures are currently mapped to:

```text
ActionElement kind="if" / "for" / "while" / "with"
```

The `try` control structure is mapped more specifically to:

```text
TryUnit
```

---

## 16. Identifier conventions

The JSON model relies on stable identifiers.

Recommended prefixes:

| Prefix | Meaning |
|---|---|
| `file:` | Source file |
| `class:` | Class |
| `method:` | Method |
| `function:` | Function |
| `param:` | Parameter |
| `local:` | Local variable |
| `call:` | Call expression |
| `body:` | Body statement or control structure |
| `builtin:` | Builtin target |
| `external:` | External target |

Identifiers should be stable across repeated executions on the same source code. This improves reproducibility and stable serialization.

---

## 17. Minimal valid model

A minimal valid model with one function and one bare return:

```json
{
  "projectName": "bare_return_project",
  "language": "python",
  "files": [
    {
      "id": "file:bare_return",
      "name": "bare_return.py",
      "path": "bare_return.py",
      "qualified_name": "bare_return",
      "imports": [],
      "classes": [],
      "functions": [
        {
          "id": "function:bare_return.foo",
          "name": "foo",
          "qualified_name": "bare_return.foo",
          "parameters": [],
          "local_variables": [],
          "calls": [],
          "body": [
            {
              "id": "body:return_void",
              "type": "statement",
              "statement_type": "return",
              "line_start": 1,
              "line_end": 1,
              "value": null
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 18. Extractor responsibilities

The `python_kdm_extractor` should ensure that:

1. All model elements have stable identifiers.
2. Source locations are provided when available.
3. Calls are listed in the callable-level `calls` array.
4. Body nodes reference relevant calls through fields such as `value_calls`, `exception_calls` or `condition_calls`.
5. Try blocks contain `body`, `handlers`, `orelse` and `finalbody` arrays.
6. Exception handlers use `type: "exception_handler"`.
7. Bare returns use `value: null`.
8. Bare raises use `exception: null` and an empty `exception_calls` list.
9. The JSON remains deterministic across repeated runs.

---

## 19. Generator assumptions

The `kdm_pyecore_generator` assumes that:

1. `projectName`, `language` and `files` exist at the top level.
2. Every file has an `id`, `name`, `path`, `classes` and `functions`.
3. Every callable has an `id`, `name`, `parameters`, `local_variables`, `calls` and `body`.
4. Body statements have stable `id` values.
5. Call identifiers referenced inside body statements exist in the callable-level `calls` array.
6. Source line numbers may be absent, but when present they must be consistent.
7. The JSON may contain temporary resolution fields, but the final KDM output should represent semantics through KDM relations.

---

## 20. Testing with fixtures

The generator is tested using small JSON fixtures under:

```text
tests/fixtures/
```

Examples include:

- `bare_return.json`;
- `return_literal.json`;
- `bare_raise.json`;
- `bare_except.json`.

These fixtures allow the generator to be tested without modifying the default `input/python_model.json`.

Example command:

```bash
python src/main.py \
  --input tests/fixtures/bare_raise.json \
  --output output/test_bare_raise.kdm.xmi
```
