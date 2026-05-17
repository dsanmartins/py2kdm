# Validation Rules

## 1. Purpose

The `kdm_pyecore_generator` includes a validation layer to ensure that the generated KDM 1.4 XMI model is structurally consistent, semantically meaningful, and free of temporary attributes used only during intermediate processing.

Validation is important because the generator does not only serialize XML. It builds a model that must preserve the semantics of the original Python project using KDM metaclasses and relations.

The validation process checks three main aspects:

1. Basic structural consistency of the generated KDM model.
2. Correct use of KDM relationships and relation targets.
3. Generator-specific rules, such as avoiding duplicate attributes and ensuring that method bodies are represented using `BlockUnit`.

---

## 2. Validation pipeline

The generator uses two validation levels:

```text
Intermediate JSON model
        │
        ▼
BasicValidator
        │
        ▼
KDM generation
        │
        ▼
KDMValidator
        │
        ▼
KDM 1.4 XMI output
```

### JSON-level validation

The `BasicValidator` validates information still available in the intermediate JSON model. In particular, it reports unresolved calls or inconsistencies detected before KDM generation.

### KDM-level validation

The `KDMValidator` validates the generated KDM model. It checks inventory elements, source regions, semantic relations, body structure, obsolete attributes, and duplicate elements.

If the KDM validation report contains errors, the generator stops and raises an exception before accepting the generated model as valid.

---

## 3. Inventory validation

The generated KDM segment must contain an `InventoryModel`.

Expected structure:

```text
Segment
 └── InventoryModel
      └── SourceFile
```

Validation rules:

| Rule | Severity |
|---|---|
| The `Segment` must contain at least one `InventoryModel`. | Error |
| More than one `InventoryModel` is suspicious. | Warning |
| Each `InventoryModel` must contain inventory elements. | Error |
| At least one `SourceFile` must exist. | Error |
| Each `SourceFile` must have a path. | Error |

---

## 4. Source traceability validation

Source traceability is represented using `SourceRef` and `SourceRegion`.

Expected structure:

```text
KDM element
 └── SourceRef
      └── SourceRegion
```

Validation rules:

| Rule | Severity |
|---|---|
| A `SourceRegion` must have either a file reference or a path. | Error |
| `startLine` must not be greater than `endLine`. | Error |
| Duplicate source regions on the same element are not allowed. | Error |

This ensures that generated KDM elements can be traced back to the source Python files.

---

## 5. Type relation validation

Types are represented with `code::HasType`.

Expected form:

```text
Typed element --HasType--> Datatype / ClassUnit-compatible type
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `HasType` relation must have a target. | Error |
| The target of `HasType` must be a `Datatype`. | Error |

Examples:

```text
ParameterUnit name
 └── HasType → StringType
```

```text
StorableUnit RepositoryError_exception
 └── HasType → ClassUnit RepositoryError
```

---

## 6. Value relation validation

Values are represented with `code::HasValue`.

Expected form:

```text
StorableUnit --HasValue--> Value
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `HasValue` relation must have a target. | Error |
| The target of `HasValue` must be a `Value` or an `ActionElement`. | Error |

Example for returned literal:

```text
StorableUnit return_literal_True
 └── HasValue → Value value_True
```

---

## 7. Call and constructor validation

Function and method invocations are represented using `action::Calls`.

Constructor invocations are represented using `action::Creates`.

Expected forms:

```text
ActionElement call --Calls--> CallableUnit / MethodUnit
```

```text
ActionElement constructor_call --Creates--> ClassUnit
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `Calls` relation must have a target. | Error |
| Every `Creates` relation must have a target. | Error |
| An `ActionElement` with `kind="constructor_call"` should have a `Creates` relation. | Warning |

---

## 8. Reads and Writes validation

Data access is represented using `action::Reads` and `action::Writes`.

Expected forms:

```text
ActionElement --Reads--> StorableUnit
ActionElement --Writes--> StorableUnit
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `Reads` relation must have a target. | Error |
| Every `Writes` relation must have a target. | Error |
| The target of `Reads` must be a `StorableUnit`. | Error |
| The target of `Writes` must be a `StorableUnit`. | Error |

This rule is especially important for returned literals. A `return` action must not read a raw `Value` directly. Instead, the generator creates a temporary `StorableUnit` and connects it to the `Value` using `HasValue`.

Example:

```text
return True
  → ActionElement kind="return"
  → Reads → StorableUnit return_literal_True
  → return_literal_True --HasValue--> Value value_True
```

---

## 9. Return validation

KDM 1.4 does not define a specific `Returns` relation. Therefore, returned values are modeled as data read by the `return` action.

Expected forms:

```text
return x
  → ActionElement kind="return"
  → Reads → StorableUnit x
```

```text
return True
  → ActionElement kind="return"
  → Reads → StorableUnit return_literal_True
  → return_literal_True --HasValue--> Value value_True
```

```text
return f(...)
  → ActionElement kind="return"
  → Reads → StorableUnit return_value_of_f
```

Validation rules:

| Rule | Severity |
|---|---|
| A `return` action must have a `Reads` relation, `return_flow="void"`, or `unresolved_return_value`. | Error |
| The old `ActionRelationship kind="returns"` representation is not allowed. | Error |

Accepted cases:

```text
return x              → Reads
return True           → Reads + HasValue
return f(...)         → Reads temporary result
return                → return_flow="void"
return complex_expr   → unresolved_return_value
```

---

## 10. Throw and raise validation

Raised exceptions are represented with `action::Throws`.

Since `Throws.to` must point to a data element, the generator creates a `StorableUnit` representing the thrown exception object.

Expected form:

```text
raise RepositoryError(...)
  → ActionElement kind="raise"
  → StorableUnit RepositoryError_exception
  → Throws → RepositoryError_exception
  → RepositoryError_exception --HasType--> RepositoryError
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `Throws` relation must have a target. | Error |
| The target of `Throws` must be a `StorableUnit`. | Error |
| A `raise` action must have `Throws` or `exception_flow="rethrow"`. | Error |

Accepted cases:

```text
raise X(...)  → Throws
raise         → exception_flow="rethrow"
```

---

## 11. Try, catch and finally validation

Exception handling is represented using KDM-specific action elements and flows.

Expected structure:

```text
TryUnit
 ├── CatchUnit
 ├── FinallyUnit
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `CatchUnit` contained in a `TryUnit` must be targeted by `ExceptionFlow`. | Error |
| Every `FinallyUnit` contained in a `TryUnit` must be targeted by `ExitFlow`. | Error |
| `ExceptionFlow` must target a `CatchUnit`. | Error |
| `ExitFlow` must target a `FinallyUnit`. | Error |
| The old `ActionRelationship kind="catches"` representation is not allowed. | Error |

This ensures that Python `try/except/finally` structures are represented using KDM action-flow semantics instead of temporary attributes.

---

## 12. Callable body `BlockUnit` validation

The executable body of a method or function is represented using `action::BlockUnit`.

Expected structure:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      ├── ActionElement
      ├── TryUnit
      ├── CatchUnit
      ├── FinallyUnit
      └── nested ActionElement nodes
```

Validation rules:

| Rule | Severity |
|---|---|
| A `MethodUnit` or `CallableUnit` must not contain direct executable actions. | Error |
| Executable actions must be contained in a `BlockUnit`. | Error |
| More than one callable body `BlockUnit` under the same callable is not allowed. | Error |
| A callable body `BlockUnit` should be named `body`. | Warning |
| A callable body `BlockUnit` should have `role="callable_body"`. | Warning |
| A callable body `BlockUnit` should contain executable actions. | Warning |

The generator uses traceability attributes on body blocks:

```xml
<attribute tag="role" value="callable_body"/>
<attribute tag="callable_body_id" value="method:example.Service.foo"/>
```

This validates the design decision that `MethodUnit` and `CallableUnit` represent declarations, while `BlockUnit` represents executable body content.

---

## 13. Imports and extends validation

Imports and inheritance are represented with `code::Imports` and `code::Extends`.

Expected forms:

```text
CompilationUnit --Imports--> imported target
ClassUnit       --Extends--> base class
```

Validation rules:

| Rule | Severity |
|---|---|
| Every `Imports` relation must have a target. | Error |
| Every `Extends` relation must have a target. | Error |

---

## 14. Duplicate attribute validation

The generator must avoid adding the same attribute more than once to the same KDM element.

Validation rule:

| Rule | Severity |
|---|---|
| Duplicate attributes with the same `tag` and `value` on the same element are not allowed. | Error |

Example of invalid output:

```xml
<attribute tag="source_call_name" value="json.dumps"/>
<attribute tag="source_call_name" value="json.dumps"/>
```

This rule helped detect idempotency issues in resolvers such as `ReturnRelationResolver` and `ExceptionRelationResolver`.

---

## 15. Duplicate source region validation

A generated element should not contain the same source region more than once.

Validation rule:

| Rule | Severity |
|---|---|
| Duplicate `SourceRegion` entries on the same element are not allowed. | Error |

A duplicate region is identified using:

```text
path
startLine
endLine
startPosition
endPosition
```

---

## 16. Duplicate child action validation

The generator validates that a container does not contain duplicated executable child actions.

Validation rule:

| Rule | Severity |
|---|---|
| Duplicate child actions under the same parent are not allowed. | Error |

The validator compares child actions using:

```text
EClass name
name
kind
original_id
body_id
```

This prevents accidental duplication when actions are first created by `ReferenceResolver` and later reorganized by `BodyActionMapper`.

---

## 17. Obsolete attribute validation

Earlier versions of the generator used temporary attributes to store semantic information. These attributes are no longer allowed in the final KDM because their meaning must be represented by KDM metaclasses and relations.

Obsolete attributes include:

```text
resolved
target_id
statement_type
body_type
control_type
condition
target
iter
exception
value
targets
line
line_start
line_end
path
language
assigned_value
assigned_type
resolved_type_qualified_name
annotation
function
method
class_name
base_name
source_class
kind as Attribute
```

Validation rule:

| Rule | Severity |
|---|---|
| Obsolete attributes are not allowed in the final KDM model. | Error |

Examples of invalid output:

```xml
<attribute tag="resolved" value="True"/>
<attribute tag="target_id" value="builtin:print"/>
<attribute tag="kind" value="catches"/>
<attribute tag="kind" value="returns"/>
```

The preferred representation is:

| Former attribute | Current KDM representation |
|---|---|
| `target_id` | Relation target, e.g. `Calls.to`, `Creates.to`, `Imports.to` |
| `resolved` | Existence of semantic relation |
| `kind="catches"` | `ExceptionFlow` |
| `kind="returns"` | `Reads` |
| `value` | `Value`, `HasValue`, `Reads` |
| `exception` | `CatchUnit`, `ParameterUnit`, `HasType` |

---

## 18. Validation report

The validator prints a report with errors, warnings and statistics.

Example:

```text
=== KDM VALIDATION REPORT ===
Errors: 0

Warnings: 0

Stats:
- Segment: 1
- InventoryModel: 1
- SourceFile: 5
- CodeModel: 3
- CompilationUnit: 14
- ClassUnit: 13
- MethodUnit: 20
- CallableUnit: 20
- BlockUnit: 20
- ActionElement: 119
- TryUnit: 2
- CatchUnit: 2
- FinallyUnit: 2
- Calls: 44
- Creates: 7
- Reads: 45
- Writes: 31
- Throws: 4
- ExceptionFlow: 2
- ExitFlow: 2
- HasType: 56
- HasValue: 19
```

The exact numbers depend on the input project.

---

## 19. Running validation

Validation is enabled by default when running the generator:

```bash
python src/main.py
```

With custom input and output:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

Validation can be disabled if needed:

```bash
python src/main.py --no-validation
```

Disabling validation is useful only for debugging incomplete models. Normal generation should keep validation enabled.

---

## 20. Testing validation rules

The validation rules are covered by automated tests using `pytest`.

Run all tests with:

```bash
pytest -q
```

The tests cover:

- stable serialization;
- absence of obsolete attributes;
- semantic KDM relations;
- exception relations;
- return relations;
- callable body `BlockUnit` mapping;
- fixture-based edge cases;
- CLI input/output behavior.

