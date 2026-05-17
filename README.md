# py2kdm

`py2kdm` is a two-stage toolchain for generating KDM 1.4 models from Python projects.

The project is organized into two subprojects:

```text
py2kdm/
├── python_kdm_extractor/
│   └── Python source code → intermediate JSON model
└── kdm_pyecore_generator/
    └── intermediate JSON model → KDM 1.4 XMI model
```

The main goal is to support reverse engineering of Python systems into a model-driven representation compatible with KDM/EMF-based modernization workflows.

---

## Overview

The toolchain follows this pipeline:

```text
Python project
   ↓
python_kdm_extractor
   ↓
Intermediate JSON model
   ↓
kdm_pyecore_generator
   ↓
KDM 1.4 XMI model
```

The intermediate JSON model works as the contract between the Python extractor and the KDM generator. This separation allows the Python analysis phase to evolve independently from the KDM generation phase.

---

## Subprojects

### 1. `python_kdm_extractor`

This subproject analyzes Python source code and produces an intermediate JSON model.

It performs the following tasks:

- scans a Python project and finds `.py` files;
- parses Python files using the native `ast` module;
- extracts files, imports, classes, functions, methods, parameters and local variables;
- analyzes calls, constructor calls and references;
- resolves imports and internal/external calls when possible;
- synchronizes body-level statements with call information;
- builds a JSON model containing structural and behavioral information.

Main entry point:

```bash
cd python_kdm_extractor
python main.py example_project
```

Default output:

```text
python_kdm_extractor/output/python_model.json
```

---

### 2. `kdm_pyecore_generator`

This subproject reads the intermediate JSON model and generates a KDM 1.4 XMI model using PyEcore.

It performs the following tasks:

- loads the KDM 1.4 Ecore metamodel;
- creates the root `Segment`;
- creates `InventoryModel` and `SourceFile` elements;
- creates `CodeModel`, `CompilationUnit`, `ClassUnit`, `MethodUnit`, `CallableUnit`, `ParameterUnit` and `StorableUnit` elements;
- creates `BlockUnit` elements to represent callable bodies;
- creates action elements and control-flow elements;
- creates KDM relations such as `Calls`, `Creates`, `Reads`, `Writes`, `Throws`, `ExceptionFlow`, `ExitFlow`, `HasType`, `HasValue`, `Imports` and `Extends`;
- validates the generated KDM model;
- serializes the final model as XMI.

Main entry point:

```bash
cd kdm_pyecore_generator
python src/main.py
```

Default input:

```text
kdm_pyecore_generator/input/python_model.json
```

Default output:

```text
kdm_pyecore_generator/output/example_project.kdm.xmi
```

The generator also supports command-line parameters:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi \
  --metamodel metamodels/kdm_1_4.ecore
```

Validation can be disabled with:

```bash
python src/main.py --no-validation
```

---

## End-to-end usage

From the root directory of `py2kdm`, the intended workflow is:

```bash
cd python_kdm_extractor
python main.py example_project
```

Then copy or move the generated JSON into the generator input directory:

```bash
cp output/python_model.json ../kdm_pyecore_generator/input/python_model.json
```

Then generate the KDM model:

```bash
cd ../kdm_pyecore_generator
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

The result is a KDM 1.4 XMI model:

```text
kdm_pyecore_generator/output/example_project.kdm.xmi
```

---

## Current KDM mapping support

The current generator supports the following mappings from the intermediate JSON model to KDM 1.4.

### Structural mapping

| Intermediate JSON element | KDM element |
|---|---|
| Project | `Segment` |
| Python file | `CompilationUnit` |
| Class | `ClassUnit` |
| Method | `MethodUnit` |
| Function | `CallableUnit` |
| Callable body | `BlockUnit` |
| Parameter | `ParameterUnit` |
| Local variable | `StorableUnit` |
| Source file | `SourceFile` |

### Callable body mapping

Executable statements are not attached directly to `MethodUnit` or `CallableUnit`. Instead, each function or method with a body receives a dedicated `BlockUnit`:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      ├── ActionElement
      ├── TryUnit
      ├── CatchUnit
      ├── FinallyUnit
      └── ...
```

The generated `BlockUnit` includes traceability attributes:

```xml
<attribute tag="role" value="callable_body"/>
<attribute tag="callable_body_id" value="..."/>
```

This keeps the declaration of the callable separated from its executable body and aligns the model more closely with KDM 1.4 block semantics.

### Action and relation mapping

| Python/JSON concept | KDM representation |
|---|---|
| Function or method call | `ActionElement` + `Calls` |
| Constructor call | `ActionElement` + `Creates` |
| Assignment | `Writes` and/or `HasValue` |
| Variable read | `Reads` |
| Return statement | `ActionElement kind="return"` + `Reads` |
| Raise statement | `ActionElement kind="raise"` + `Throws` |
| Try block | `TryUnit` |
| Except block | `CatchUnit` |
| Finally block | `FinallyUnit` |
| Try to except flow | `ExceptionFlow` |
| Try to finally flow | `ExitFlow` |
| Type association | `HasType` |
| Literal value association | `HasValue` |
| Import | `Imports` |
| Inheritance | `Extends` |

---

## Exception mapping

Exceptions are modeled using KDM action elements and standard KDM exception-flow relations.

For a Python statement such as:

```python
raise RepositoryError(...)
```

The generated KDM structure is conceptually:

```text
ActionElement kind="raise"
 ├── StorableUnit RepositoryError_exception
 │    └── HasType → RepositoryError
 └── Throws → RepositoryError_exception
```

For a `try/except/finally` block:

```python
try:
    ...
except RepositoryError:
    ...
finally:
    ...
```

The generated KDM structure is conceptually:

```text
TryUnit
 ├── CatchUnit
 ├── FinallyUnit
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

The generator no longer uses temporary generic relations such as:

```text
ActionRelationship kind="catches"
```

Instead, catch blocks are modeled using `CatchUnit` and `ExceptionFlow`.

---

## Return mapping

KDM 1.4 does not define a specific `Returns` relation. Therefore, returned values are modeled as data read by the return action.

For:

```python
return x
```

The generated structure is:

```text
ActionElement kind="return"
 └── Reads → StorableUnit x
```

For:

```python
return True
```

The generated structure is:

```text
ActionElement kind="return"
 ├── StorableUnit return_literal_True
 │    └── HasValue → Value True
 └── Reads → return_literal_True
```

For:

```python
return json.dumps(data)
```

The generated structure is:

```text
ActionElement kind="return"
 ├── ActionElement json.dumps
 ├── StorableUnit return_value_of_json_dumps
 └── Reads → return_value_of_json_dumps
```

---

## Validation

The KDM generator includes validation rules for the generated model.

The validator checks, among others:

- the presence of an `InventoryModel`;
- valid `SourceFile` and `SourceRegion` information;
- valid targets for `HasType`, `HasValue`, `Reads`, `Writes`, `Throws`, `ExceptionFlow`, `ExitFlow`, `Imports` and `Extends`;
- callable body structure using `BlockUnit body`;
- absence of direct executable `ActionElement` children under `MethodUnit` or `CallableUnit`;
- semantic consistency of `return`, `raise`, `try`, `except` and `finally` mappings;
- absence of obsolete temporary attributes such as `resolved`, `target_id`, `statement_type`, `body_type`, `control_type`, `condition`, `exception`, `value` and generic attribute `kind`;
- absence of duplicate attributes, duplicate source regions and duplicate child actions.

---

## Tests

The KDM generator includes an automated test suite based on `pytest`.

To run the tests:

```bash
cd kdm_pyecore_generator
pytest -q
```

The current test suite checks:

- stable serialization;
- CLI-based generation with configurable input/output paths;
- absence of obsolete attributes;
- presence of semantic KDM relations;
- callable body modeling through `BlockUnit`;
- exception mappings;
- return mappings;
- edge-case fixtures such as bare return, return literal, bare raise and bare except.

---

## Repository hygiene

The following generated files and directories should not be committed:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
output/test_fixtures/
output/run1.kdm.xmi
output/run2.kdm.xmi
output/example_project_cli_test.kdm.xmi
```

---

## Documentation plan

Suggested documentation files:

```text
docs/
├── architecture.md
├── intermediate_json_model.md
├── json_to_kdm_mapping.md
├── validation_rules.md
├── cli_usage.md
└── development_guide.md
```

The README should provide the general overview. The `docs/` directory should contain the detailed technical documentation.

---

## Current status

The current prototype supports a working Python-to-KDM pipeline through an intermediate JSON model. The KDM generator produces stable XMI output and includes validation and automated tests for the main semantic mappings. Callable bodies are now modeled explicitly using `BlockUnit`, while exceptions, returns, reads/writes and calls are represented through standard KDM elements and relations whenever possible.
