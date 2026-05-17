# Development Guide

## 1. Purpose

This guide describes how to work on the `py2kdm` project as a developer.

`py2kdm` is organized as a two-stage toolchain:

```text
Python source code
        ↓
python_kdm_extractor
        ↓
Intermediate JSON model
        ↓
kdm_pyecore_generator
        ↓
KDM 1.4 XMI model
```

The main development principle is to keep the two subprojects separated by a stable intermediate JSON contract.

---

## 2. Repository structure

Recommended project structure:

```text
py2kdm/
├── README.md
├── docs/
│   ├── index.md
│   ├── architecture.md
│   ├── intermediate_json_model.md
│   ├── json_to_kdm_mapping.md
│   ├── validation_rules.md
│   ├── cli_usage.md
│   └── development_guide.md
├── mkdocs.yml
├── python_kdm_extractor/
└── kdm_pyecore_generator/
```

The two subprojects have different responsibilities:

| Subproject | Responsibility |
|---|---|
| `python_kdm_extractor` | Parse Python projects and produce the intermediate JSON model. |
| `kdm_pyecore_generator` | Transform the intermediate JSON model into KDM 1.4 XMI. |

---

## 3. Development environment

Create and activate a virtual environment before working on the project.

Example:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies according to the files available in each subproject.

For the KDM generator, typical dependencies include:

```bash
pip install pyecore pytest
```

If using MkDocs for documentation:

```bash
pip install mkdocs mkdocs-material
```

---

## 4. Running the extractor

The extractor should be executed from the `python_kdm_extractor` subproject.

A typical command has the following form:

```bash
python src/main.py \
  --input path/to/python/project \
  --output ../kdm_pyecore_generator/input/python_model.json
```

The exact command may depend on the current extractor CLI. The important requirement is that the output JSON follows the contract documented in `docs/intermediate_json_model.md`.

---

## 5. Running the KDM generator

From the `kdm_pyecore_generator` subproject:

```bash
python src/main.py
```

This uses the default paths:

```text
input/python_model.json
output/example_project.kdm.xmi
```

The generator also supports explicit input and output paths:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

To use a custom fixture:

```bash
python src/main.py \
  --input tests/fixtures/bare_raise.json \
  --output output/test_bare_raise.kdm.xmi
```

To disable validation:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi \
  --no-validation
```

Validation should remain enabled during normal development.

---

## 6. Running tests

From the `kdm_pyecore_generator` subproject:

```bash
pytest -q
```

The test suite covers:

- stable serialization;
- absence of obsolete attributes;
- semantic KDM relations;
- exception modeling;
- return modeling;
- callable body modeling with `BlockUnit`;
- fixture-based Python edge cases;
- CLI input/output behavior.

Before committing changes, run:

```bash
python -m py_compile src/*.py
pytest -q
```

If shell expansion does not work in your environment, compile individual files:

```bash
python -m py_compile src/main.py
python -m py_compile src/kdm_factory.py
python -m py_compile src/body_action_mapper.py
python -m py_compile src/kdm_validator.py
```

---

## 7. Stable serialization check

The generated XMI should be stable across repeated executions.

```bash
python src/main.py
cp output/example_project.kdm.xmi output/run1.kdm.xmi

python src/main.py
cp output/example_project.kdm.xmi output/run2.kdm.xmi

diff output/run1.kdm.xmi output/run2.kdm.xmi
```

Expected result:

```text
No differences
```

If differences appear, check for:

- non-deterministic iteration over dictionaries or sets;
- unstable ordering of generated elements;
- random identifiers;
- duplicate generation of elements;
- unordered external or builtin target creation.

---

## 8. Development workflow

Recommended workflow for adding or modifying a mapping:

1. Update the intermediate JSON contract if needed.
2. Add or update a fixture in `tests/fixtures/`.
3. Update the corresponding resolver or mapper.
4. Update `KDMValidator` if the new structure requires validation.
5. Add or update tests.
6. Run `pytest -q`.
7. Update documentation.

Example:

```text
New Python construct
        ↓
JSON fixture
        ↓
Mapper / resolver update
        ↓
KDM validation rule
        ↓
Tests
        ↓
Documentation
```

---

## 9. Adding a new JSON fixture

Fixtures should be small and focused.

Recommended location:

```text
kdm_pyecore_generator/tests/fixtures/
```

Example fixture names:

```text
bare_return.json
return_literal.json
bare_raise.json
bare_except.json
try_finally.json
return_unresolved_expression.json
```

A fixture should contain only the minimum JSON required to test one behavior.

Example:

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

## 10. Adding a new KDM mapping

When adding a new mapping, follow these principles:

### Prefer KDM metaclasses and relations

Use native KDM elements and relations whenever possible.

Examples:

| Concept | Preferred KDM representation |
|---|---|
| Function call | `ActionElement` + `Calls` |
| Constructor call | `ActionElement` + `Creates` |
| Return value | `ActionElement kind="return"` + `Reads` |
| Raise statement | `ActionElement kind="raise"` + `Throws` |
| Try block | `TryUnit` |
| Except block | `CatchUnit` + `ExceptionFlow` |
| Finally block | `FinallyUnit` + `ExitFlow` |
| Function/method body | `BlockUnit name="body" kind="body"` |

### Avoid temporary attributes

Do not serialize semantic information using temporary attributes if it can be represented as a KDM relation.

Avoid reintroducing attributes such as:

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

The validator treats these as errors.

### Keep traceability attributes minimal

Allowed traceability or support attributes include:

```text
original_id
body_id
callable_body_id
classification
occurrence_index
expression_role
role
literal_value
exception_type_name
source_call_name
return_flow
unresolved_return_value
resolution_status
unresolved_target_name
```

---

## 11. Callable body modeling rule

Executable statements inside methods and functions must be placed inside a `BlockUnit`.

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

Direct executable actions under `MethodUnit` or `CallableUnit` are not allowed.

This is enforced by `KDMValidator`.

---

## 12. Exception modeling rule

Raised exceptions are modeled as thrown data objects:

```text
raise RepositoryError(...)
  → ActionElement kind="raise"
  → StorableUnit RepositoryError_exception
  → Throws → RepositoryError_exception
  → RepositoryError_exception --HasType--> RepositoryError
```

Exception handlers are modeled using KDM flow relations:

```text
TryUnit --ExceptionFlow--> CatchUnit
TryUnit --ExitFlow-------> FinallyUnit
```

Do not use generic `ActionRelationship kind="catches"`.

---

## 13. Return modeling rule

KDM 1.4 does not define a specific `Returns` relation.

Returns are modeled using `Reads`:

```text
return x
  → ActionElement kind="return"
  → Reads → StorableUnit x
```

For literals:

```text
return True
  → StorableUnit return_literal_True
  → Value value_True
  → return_literal_True --HasValue--> value_True
  → return --Reads--> return_literal_True
```

For returned calls:

```text
return f(...)
  → StorableUnit return_value_of_f
  → return --Reads--> return_value_of_f
```

Do not use generic `ActionRelationship kind="returns"`.

---

## 14. Updating the validator

Whenever a new mapping is added, consider whether the validator should enforce it.

Examples:

- If a new relation is introduced, validate its target type.
- If a new structural container is introduced, validate its placement.
- If a temporary attribute is removed, add it to `OBSOLETE_ERROR_ATTRIBUTES`.
- If a resolver may run more than once, validate against duplicate attributes or duplicate relations.

The validator should catch regressions early.

---

## 15. Documentation workflow

When changing the model or mapping, update the relevant document:

| Change | Document to update |
|---|---|
| Project structure | `README.md`, `docs/architecture.md` |
| JSON contract | `docs/intermediate_json_model.md` |
| KDM mapping | `docs/json_to_kdm_mapping.md` |
| Validation rule | `docs/validation_rules.md` |
| CLI behavior | `docs/cli_usage.md` |
| Development process | `docs/development_guide.md` |

Run MkDocs locally:

```bash
mkdocs serve
```

Build the site:

```bash
mkdocs build
```

---

## 16. Git hygiene

Recommended `.gitignore` entries:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
site/
output/test_fixtures/
output/run1.kdm.xmi
output/run2.kdm.xmi
output/example_project_cli_test.kdm.xmi
```

Do not commit generated caches or temporary output files.

Commit source code, tests, fixtures and documentation.

---

## 17. Pre-commit checklist

Before committing:

```bash
python src/main.py
pytest -q
mkdocs build
```

Check:

```bash
git status
```

Recommended commit message style:

```text
Add BlockUnit body mapping for callable bodies
Update KDM validator for return and exception semantics
Add fixtures for Python exception edge cases
Document JSON to KDM mapping rules
```

---

## 18. Future development tasks

Possible next tasks include:

- improving expression modeling for boolean and arithmetic expressions;
- adding module-level executable blocks;
- adding more control-flow relations;
- improving type inference in the extractor;
- supporting additional Python constructs;
- generating additional KDM views;
- adding transformation targets beyond KDM;
- supporting other languages through the same intermediate JSON contract.
