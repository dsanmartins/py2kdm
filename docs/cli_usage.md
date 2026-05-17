# CLI Usage

This document describes how to run the complete `py2kdm` toolchain from the command line.

`py2kdm` is organized as a two-stage pipeline:

```text
Python source project
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

The first subproject, `python_kdm_extractor`, analyzes Python source code and generates an intermediate JSON model. The second subproject, `kdm_pyecore_generator`, transforms that JSON model into a KDM 1.4 XMI file using PyEcore.

---

## 1. Repository layout

A typical repository layout is:

```text
py2kdm/
├── python_kdm_extractor/
│   ├── main.py
│   ├── extractor/
│   └── output/
├── kdm_pyecore_generator/
│   ├── src/
│   ├── input/
│   ├── output/
│   ├── metamodels/
│   └── tests/
├── docs/
├── README.md
└── mkdocs.yml
```

Unless otherwise stated, commands are shown from the root directory of `py2kdm`.

---

## 2. Stage 1: Python source code to intermediate JSON

The `python_kdm_extractor` subproject extracts a JSON-compatible intermediate model from a Python project.

Recommended execution:

```bash
python python_kdm_extractor/main.py \
  --input path/to/python/project \
  --output kdm_pyecore_generator/input/python_model.json
```

Example:

```bash
python python_kdm_extractor/main.py \
  --input examples/example_project \
  --output kdm_pyecore_generator/input/python_model.json
```

The expected output is:

```text
kdm_pyecore_generator/input/python_model.json
```

This JSON file is the contract consumed by the KDM generator.

### Backward-compatible extractor usage

The extractor also supports the older positional form:

```bash
cd python_kdm_extractor
python main.py path/to/python/project
```

By default, this writes:

```text
python_kdm_extractor/output/python_model.json
```

However, the recommended workflow is to use `--input` and `--output`, because it makes the pipeline explicit and avoids manually moving the generated JSON file.

### Extractor help

```bash
python python_kdm_extractor/main.py --help
```

---

## 3. Stage 2: Intermediate JSON to KDM 1.4 XMI

The `kdm_pyecore_generator` subproject reads the intermediate JSON model and generates a KDM 1.4 XMI file.

Recommended execution:

```bash
python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi
```

The final KDM model will be available at:

```text
kdm_pyecore_generator/output/example_project.kdm.xmi
```

---

## 4. KDM generator default execution

From inside `kdm_pyecore_generator`, the generator can also be executed with defaults:

```bash
cd kdm_pyecore_generator
python src/main.py
```

By default, the generator uses:

```text
Input JSON:   input/python_model.json
Output XMI:   output/example_project.kdm.xmi
Metamodel:    metamodels/kdm_1_4.ecore
```

---

## 5. KDM generator CLI options

The KDM generator supports configurable input, output and metamodel paths.

```bash
python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi \
  --metamodel kdm_pyecore_generator/metamodels/kdm_1_4.ecore
```

### `--input`

Path to the intermediate JSON model.

Example:

```bash
python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json
```

### `--output`

Path where the generated KDM XMI file will be written.

Example:

```bash
python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi
```

### `--metamodel`

Path to the KDM 1.4 Ecore metamodel.

Example:

```bash
python kdm_pyecore_generator/src/main.py \
  --metamodel kdm_pyecore_generator/metamodels/kdm_1_4.ecore
```

### `--no-validation`

Disables JSON-level and KDM-level validation.

Example:

```bash
python kdm_pyecore_generator/src/main.py --no-validation
```

This option should only be used for debugging. During normal development, validation should remain enabled.

---

## 6. Complete two-stage execution

A complete execution from the root directory of `py2kdm` is:

```bash
# Stage 1: Extract intermediate JSON from a Python project
python python_kdm_extractor/main.py \
  --input examples/example_project \
  --output kdm_pyecore_generator/input/python_model.json

# Stage 2: Generate KDM 1.4 XMI from the JSON model
python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi
```

The generated artifacts are:

```text
kdm_pyecore_generator/input/python_model.json
kdm_pyecore_generator/output/example_project.kdm.xmi
```

---

## 7. Running with fixture JSON models

The KDM generator can be executed using small JSON fixtures. This is useful for testing specific Python constructs without running the extractor.

Example:

```bash
cd kdm_pyecore_generator
python src/main.py \
  --input tests/fixtures/bare_raise.json \
  --output output/test_fixtures/bare_raise.kdm.xmi
```

This allows isolated testing of cases such as:

- bare `return`;
- return literal;
- return call;
- bare `raise`;
- bare `except`;
- `try` / `except` / `finally`.

---

## 8. Expected extractor output

When the extractor runs successfully, it prints a short summary such as:

```text
Model generated at kdm_pyecore_generator/input/python_model.json
Project name: example_project
Python files analyzed: ...
Elements: ...
Relationships: ...
```

The generated JSON contains the intermediate model sections:

```text
projectName
language
files
elements
relationships
symbol_table
summary
```

---

## 9. Expected KDM generator output

When the generator runs successfully, it prints validation reports and a generation summary.

Example summary:

```text
KDM model generated at: output/example_project.kdm.xmi
Indexed internal KDM elements: ...
Typable elements: ...
Value elements: ...
Statement/body actions: ...
Callable body blocks: ...
Finally units: ...
InventoryModel generated.
Source files: ...
ExternalLibraries_CodeModel generated.
External libraries: ...
External targets: ...
```

The `Callable body blocks` count corresponds to the number of generated `BlockUnit` elements representing method and function bodies.

---

## 10. Validation behavior

The KDM generator runs two validation stages by default.

### JSON-level validation

The JSON-level validator checks unresolved calls and consistency issues in the intermediate JSON model.

### KDM-level validation

The KDM-level validator checks the generated KDM model. It validates:

- inventory model presence;
- source files and source regions;
- relation targets;
- `Reads`, `Writes`, `Calls`, `Creates`, `Throws`;
- `HasType` and `HasValue`;
- `TryUnit`, `CatchUnit`, `FinallyUnit`;
- `ExceptionFlow` and `ExitFlow`;
- callable body `BlockUnit` structure;
- absence of obsolete temporary attributes;
- absence of duplicate attributes, source regions and child actions.

If KDM validation fails, generation stops with an error:

```text
RuntimeError: KDM validation failed. See validation report above.
```

---

## 11. Running tests

The generator test suite is executed with `pytest`.

```bash
cd kdm_pyecore_generator
pytest -q
```

The tests cover:

- stable serialization;
- absence of obsolete attributes;
- semantic KDM relations;
- exception modeling;
- return modeling;
- `BlockUnit` body modeling;
- fixture-based edge cases;
- CLI input/output behavior.

If tests are later added to `python_kdm_extractor`, run them from the corresponding subproject directory.

---

## 12. Checking serialization stability manually

Stable serialization can be checked manually by generating the same model twice and comparing the outputs.

```bash
cd kdm_pyecore_generator

python src/main.py
cp output/example_project.kdm.xmi output/run1.kdm.xmi

python src/main.py
cp output/example_project.kdm.xmi output/run2.kdm.xmi

diff output/run1.kdm.xmi output/run2.kdm.xmi
```

If `diff` produces no output, serialization is stable.

---

## 13. Inspecting the generated KDM

Useful commands for inspecting the generated XMI from inside `kdm_pyecore_generator`:

### Check callable body blocks

```bash
grep -n -E 'action:BlockUnit|callable_body|callable_body_id' output/example_project.kdm.xmi | head -30
```

### Check exception modeling

```bash
grep -n -E 'action:TryUnit|action:CatchUnit|action:FinallyUnit|action:ExceptionFlow|action:ExitFlow|action:Throws' output/example_project.kdm.xmi
```

### Check return modeling

```bash
grep -n -E 'kind="return"|action:Reads|returned_literal|returned_call_result|return_flow|unresolved_return_value' output/example_project.kdm.xmi
```

### Check absence of obsolete attributes

```bash
grep -n -E 'tag="resolved"|tag="target_id"|tag="statement_type"|tag="body_type"|tag="control_type"|tag="condition"|tag="exception"|tag="value"|tag="kind"' output/example_project.kdm.xmi
```

The last command should return no results.

---

## 14. Recommended development workflow

A typical complete development workflow from the root directory of `py2kdm` is:

```bash
# Compile extractor files
cd python_kdm_extractor
python -m py_compile main.py
python -m py_compile extractor/*.py
cd ..

# Compile generator files and run tests
cd kdm_pyecore_generator
python -m py_compile src/*.py
pytest -q
cd ..

# Run full pipeline
python python_kdm_extractor/main.py \
  --input examples/example_project \
  --output kdm_pyecore_generator/input/python_model.json

python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi

# Build documentation
mkdocs build
```

Before committing, ensure that:

- the extractor runs without errors;
- the generator runs without validation errors;
- all tests pass;
- MkDocs builds without warnings;
- generated cache files are not staged;
- temporary outputs are ignored when appropriate.

Recommended ignored files include:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
site/
kdm_pyecore_generator/output/test_fixtures/
kdm_pyecore_generator/output/run1.kdm.xmi
kdm_pyecore_generator/output/run2.kdm.xmi
```

---

## 15. Common issues

### `AttributeError: 'KDMFactory' object has no attribute 'create_block_unit'`

This means `BlockUnit` support is missing in `KDMFactory`.

The factory must include:

```python
self.BlockUnit = resolver.find("BlockUnit")
```

and:

```python
def create_block_unit(self, name="body", kind="body"):
    block = self.BlockUnit()
    block.name = name
    if kind is not None and self.has_feature(block, "kind"):
        block.kind = kind
    return block
```

### `KDM validation failed`

Read the validation report printed before the traceback. It usually indicates one of the following:

- relation target has the wrong KDM type;
- obsolete attributes are still being generated;
- a return action has no `Reads`, `return_flow="void"` or `unresolved_return_value`;
- a raise action has no `Throws` or `exception_flow="rethrow"`;
- a `TryUnit` has a `CatchUnit` without `ExceptionFlow`;
- a callable has executable actions directly under `MethodUnit` or `CallableUnit` instead of under `BlockUnit`.

### Extractor input path does not exist

If the extractor reports that the input project path does not exist, check whether the command is being executed from the expected directory. Prefer absolute paths or run the command from the root directory of `py2kdm`.

Example:

```bash
python python_kdm_extractor/main.py \
  --input /absolute/path/to/python/project \
  --output kdm_pyecore_generator/input/python_model.json
```

---

## 16. Summary

The complete `py2kdm` CLI workflow is:

```bash
python python_kdm_extractor/main.py \
  --input examples/example_project \
  --output kdm_pyecore_generator/input/python_model.json

python kdm_pyecore_generator/src/main.py \
  --input kdm_pyecore_generator/input/python_model.json \
  --output kdm_pyecore_generator/output/example_project.kdm.xmi
```

For isolated KDM generator tests, use fixture JSON models:

```bash
cd kdm_pyecore_generator
python src/main.py \
  --input tests/fixtures/return_literal.json \
  --output output/test_fixtures/return_literal.kdm.xmi
```

During normal development, the KDM generator should be executed with validation enabled.
