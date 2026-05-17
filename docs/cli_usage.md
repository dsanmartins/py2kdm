# CLI Usage

This document describes how to run the `py2kdm` toolchain from the command line.

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

The first subproject extracts an intermediate JSON model from Python source code. The second subproject transforms that JSON model into a KDM 1.4 XMI file.

---

## 1. Repository layout

A typical repository layout is:

```text
py2kdm/
├── python_kdm_extractor/
├── kdm_pyecore_generator/
├── docs/
├── README.md
└── mkdocs.yml
```

The commands in this document assume that they are executed from the root directory of the corresponding subproject unless otherwise stated.

---

## 2. Stage 1: Python source code to intermediate JSON

The `python_kdm_extractor` subproject is responsible for analyzing Python source code and generating the intermediate JSON model.

Example command:

```bash
cd python_kdm_extractor
python src/main.py \
  --input examples/example_project \
  --output output/python_model.json
```

The expected output is a JSON file such as:

```text
output/python_model.json
```

This JSON file is the contract consumed by the KDM generator.

If the extractor uses different command-line arguments in the current implementation, use the local extractor help command:

```bash
python src/main.py --help
```

or inspect the extractor README for the exact options.

---

## 3. Stage 2: Intermediate JSON to KDM 1.4 XMI

The `kdm_pyecore_generator` subproject reads the intermediate JSON model and generates a KDM 1.4 XMI file using PyEcore.

Default execution:

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

## 4. Generator CLI options

The generator supports configurable input, output and metamodel paths.

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi \
  --metamodel metamodels/kdm_1_4.ecore
```

### `--input`

Path to the intermediate JSON model.

Example:

```bash
python src/main.py --input input/python_model.json
```

### `--output`

Path where the generated KDM XMI file will be written.

Example:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

### `--metamodel`

Path to the KDM 1.4 Ecore metamodel.

Example:

```bash
python src/main.py \
  --metamodel metamodels/kdm_1_4.ecore
```

### `--no-validation`

Disables JSON-level and KDM-level validation.

Example:

```bash
python src/main.py --no-validation
```

This option should only be used for debugging. In normal use, validation should remain enabled.

---

## 5. Complete two-stage execution

A complete execution can be performed as follows:

```bash
# Stage 1: Extract intermediate JSON from Python source code
cd python_kdm_extractor
python src/main.py \
  --input examples/example_project \
  --output ../kdm_pyecore_generator/input/python_model.json

# Stage 2: Generate KDM 1.4 XMI from the JSON model
cd ../kdm_pyecore_generator
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

The final KDM model will be available at:

```text
kdm_pyecore_generator/output/example_project.kdm.xmi
```

---

## 6. Running with fixture JSON models

The generator can be executed using small JSON fixtures. This is useful for testing specific Python constructs without running the extractor.

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

## 7. Expected generator output

When the generator runs successfully, it prints validation reports and a summary.

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

The `Callable body blocks` count corresponds to the number of generated `BlockUnit` elements representing method/function bodies.

---

## 8. Validation behavior

By default, the generator runs two validation stages.

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

## 9. Running tests

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

---

## 10. Checking serialization stability manually

Stable serialization can be checked manually by generating the same model twice and comparing the outputs.

```bash
python src/main.py
cp output/example_project.kdm.xmi output/run1.kdm.xmi

python src/main.py
cp output/example_project.kdm.xmi output/run2.kdm.xmi

diff output/run1.kdm.xmi output/run2.kdm.xmi
```

If `diff` produces no output, serialization is stable.

---

## 11. Inspecting the generated KDM

Useful commands for inspecting the generated XMI:

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

## 12. Recommended development workflow

A typical development workflow is:

```bash
# Run generator
python src/main.py

# Run tests
pytest -q

# Check generated model manually if needed
grep -n -E 'action:BlockUnit|action:TryUnit|action:Reads|action:Throws' output/example_project.kdm.xmi

# Check Git state
git status
```

Before committing, ensure that:

- the generator runs without validation errors;
- all tests pass;
- generated cache files are not staged;
- temporary outputs are ignored when appropriate.

Recommended ignored files include:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
output/test_fixtures/
output/run1.kdm.xmi
output/run2.kdm.xmi
```

---

## 13. Common issues

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

---

## 14. Summary

The CLI supports both default generation and custom input/output paths. The recommended usage is:

```bash
python src/main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi
```

For tests and isolated cases, use fixture JSON models:

```bash
python src/main.py \
  --input tests/fixtures/return_literal.json \
  --output output/test_fixtures/return_literal.kdm.xmi
```

The generator should be executed with validation enabled during normal development.
