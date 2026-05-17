# Testing Strategy

## 1. Overview

The `py2kdm` project uses automated tests to ensure that the transformation pipeline remains stable, reproducible and semantically consistent.

The current testing strategy focuses on the second stage of the toolchain:

```text
Intermediate JSON model
        │
        ▼
kdm_pyecore_generator
        │
        ▼
KDM 1.4 XMI model
```

The tests verify that the KDM generator:

- produces stable XMI output;
- preserves the expected semantic relations;
- does not reintroduce obsolete temporary attributes;
- correctly models exceptions;
- correctly models return values;
- represents callable bodies using `BlockUnit`;
- supports CLI input and output parameters;
- works with small JSON fixtures for edge cases.

---

## 2. Test framework

The project uses `pytest`.

To run the full test suite:

```bash
pytest -q
```

A successful run should report all tests passing, for example:

```text
18 passed in ...s
```

The exact number may increase as new fixtures and validation rules are added.

---

## 3. Test organization

The tests are organized under the `tests/` directory.

A typical structure is:

```text
tests/
├── fixtures/
│   ├── bare_return.json
│   ├── return_literal.json
│   ├── bare_raise.json
│   └── bare_except.json
├── test_block_unit_body.py
├── test_exception_relations.py
├── test_kdm_no_obsolete_attributes.py
├── test_kdm_semantic_relations.py
├── test_return_relations.py
├── test_serialization_stability.py
└── test_python_edge_case_fixtures.py
```

The tests combine integration-style checks over generated XMI with fixture-based checks for small Python edge cases represented as intermediate JSON models.

---

## 4. Serialization stability tests

The generator must produce the same XMI output across repeated executions over the same input.

This is important because KDM models may be used in downstream model transformations, comparisons and version-controlled artifacts.

A stability test typically runs the generator twice and compares the generated XMI text:

```python
def test_kdm_serialization_is_stable():
    first = run_generator()
    second = run_generator()

    assert first == second
```

This test helps detect nondeterministic ordering caused by dictionaries, sets, unstable ID generation or inconsistent element insertion order.

---

## 5. Semantic relation tests

The generated KDM model must contain the expected KDM relations.

The general semantic tests check for relations such as:

```text
action::Calls
action::Creates
action::Reads
action::Writes
action::Throws
action::ExceptionFlow
action::ExitFlow
code::HasType
code::HasValue
code::Imports
code::Extends
```

These tests ensure that the generator does not fall back to temporary attributes when proper KDM metaclasses or relations should be used.

---

## 6. Obsolete attribute tests

Earlier versions of the generator used temporary attributes such as:

```text
resolved
target_id
statement_type
body_type
control_type
condition
exception
value
kind as an Attribute
```

These attributes are now considered obsolete when their meaning is represented by KDM elements or relations.

Tests verify that these attributes do not appear in the generated XMI:

```python
OBSOLETE_ATTRIBUTES = [
    'tag="resolved"',
    'tag="target_id"',
    'tag="statement_type"',
    'tag="body_type"',
    'tag="control_type"',
    'tag="condition"',
    'tag="exception"',
    'tag="value"',
    'tag="kind"',
]
```

This protects the attribute-reduction strategy from regressions.

---

## 7. Exception relation tests

Exception-related tests verify that Python exception constructs are mapped to KDM-specific structures.

Expected mappings include:

```text
raise X(...)
  → ActionElement kind="raise"
  → StorableUnit X_exception
  → action::Throws → X_exception
  → X_exception --code::HasType--> X
```

and:

```text
try
  → TryUnit

except
  → CatchUnit

finally
  → FinallyUnit

TryUnit --action::ExceptionFlow--> CatchUnit
TryUnit --action::ExitFlow-------> FinallyUnit
```

The tests also ensure that the old generic relation:

```text
ActionRelationship kind="catches"
```

is not used.

---

## 8. Return relation tests

Return-related tests verify that return values are modeled using `Reads`, not a custom `returns` relation.

Expected mappings include:

```text
return x
  → ActionElement kind="return"
  → action::Reads → StorableUnit x
```

```text
return True
  → ActionElement kind="return"
  → StorableUnit return_literal_True
  → Value value_True
  → return_literal_True --code::HasValue--> value_True
  → return --action::Reads--> return_literal_True
```

```text
return f(...)
  → ActionElement kind="return"
  → StorableUnit return_value_of_f
  → return --action::Reads--> return_value_of_f
```

The tests also verify that the old generic relation:

```text
ActionRelationship kind="returns"
```

is not used.

---

## 9. BlockUnit body tests

Callable bodies are expected to be represented using `BlockUnit`.

The expected structure is:

```text
MethodUnit / CallableUnit
  └── BlockUnit name="body" kind="body"
        └── executable actions
```

Tests verify that the generated XMI contains:

```xml
<codeElement xsi:type="action:BlockUnit" name="body" kind="body">
  <attribute tag="role" value="callable_body"/>
  <attribute tag="callable_body_id" value="..."/>
</codeElement>
```

This test complements the validator rule that prevents direct executable actions under `MethodUnit` or `CallableUnit`.

---

## 10. Fixture-based edge case tests

Small JSON fixtures are used to test specific Python constructs without modifying the default input model.

Fixtures are stored under:

```text
tests/fixtures/
```

Examples include:

```text
bare_return.json
return_literal.json
bare_raise.json
bare_except.json
```

The generator is executed with CLI parameters:

```bash
python src/main.py \
  --input tests/fixtures/bare_raise.json \
  --output output/test_fixtures/bare_raise.kdm.xmi
```

This strategy keeps tests isolated and avoids overwriting `input/python_model.json`.

---

## 11. CLI tests

The generator supports custom input and output paths:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

Tests and manual checks should verify that:

- the default command works;
- custom input files work;
- custom output paths are created;
- validation failures stop generation;
- `--no-validation` can be used when validation is intentionally disabled.

---

## 12. Recommended commands

Run all tests:

```bash
pytest -q
```

Run the generator manually:

```bash
python src/main.py
```

Run with explicit input and output:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

Check that `BlockUnit` appears in the generated XMI:

```bash
grep -n -E 'action:BlockUnit|callable_body|callable_body_id' output/example_project.kdm.xmi | head -30
```

Check that obsolete attributes are absent:

```bash
grep -n -E 'tag="resolved"|tag="target_id"|tag="statement_type"|tag="body_type"|tag="control_type"|tag="condition"|tag="exception"|tag="value"|tag="kind"' output/example_project.kdm.xmi
```

The last command should return no matches.

---

## 13. Future testing improvements

Possible future improvements include:

- unit tests with mocked PyEcore objects for each resolver;
- fixture tests for loops, conditionals, `with` statements and nested calls;
- tests for module-level executable code;
- tests for unresolved imports and unresolved calls;
- tests for multiple exception handlers;
- tests for `try/except/else/finally` combinations;
- regression tests for generated XMI fragments;
- CI integration using GitHub Actions.

