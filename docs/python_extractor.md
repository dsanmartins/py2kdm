# Python Extractor

## 1. Purpose

`python_kdm_extractor` is the first stage of the `py2kdm` toolchain.

Its responsibility is to analyze a Python project and produce an intermediate JSON model. This JSON model is then consumed by `kdm_pyecore_generator`, which transforms it into a KDM 1.4 XMI model.

The extractor is intentionally independent from the KDM metamodel. It does not create KDM elements directly. Instead, it captures Python-specific information in a normalized JSON structure.

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
KDM 1.4 XMI
```

This separation allows the extractor to focus on Python analysis, while the generator focuses on KDM semantics.

---

## 2. Input and output

### Input

The extractor receives the path to a Python project.

Example:

```bash
python python_kdm_extractor/main.py python_kdm_extractor/example_project
```

### Output

The extractor produces:

```text
python_kdm_extractor/output/python_model.json
```

This file contains the intermediate JSON representation of the analyzed Python project.

---

## 3. Extraction pipeline

The extraction process follows these main stages:

```text
Project path
   │
   ▼
Find Python files
   │
   ▼
Parse each file using Python AST
   │
   ▼
Extract files, classes, functions and methods
   │
   ▼
Extract parameters, variables, calls and body statements
   │
   ▼
Build symbol table
   │
   ▼
Resolve imports
   │
   ▼
Resolve calls
   │
   ▼
Synchronize body calls
   │
   ▼
Build relationships and element summaries
   │
   ▼
Write intermediate JSON model
```

The main entry point is `main.py`, which calls `extract_project(project_path)`.

---

## 4. Main modules

### `project_scanner.py`

Responsible for finding Python source files inside a project.

It ignores generated or irrelevant directories such as:

- `__pycache__`;
- `.git`;
- virtual environments;
- pytest and mypy caches.

Its main function is:

```python
def find_python_files(project_root: Path)
```

---

### `file_extractor.py`

Responsible for extracting the model of a single Python file.

It parses the file using Python's native `ast` module and delegates structural extraction to the AST visitor.

Its main function is:

```python
def extract_file_model(file_path: Path, project_root: Path)
```

The output is a file-level JSON object containing imports, classes, functions and body-level information.

---

### `python_ast_visitor.py`

Contains the main AST visitor used to traverse Python syntax trees.

The central class is:

```python
class PythonASTVisitor(ast.NodeVisitor)
```

It is responsible for identifying high-level Python constructs such as:

- classes;
- methods;
- functions;
- parameters;
- local variables;
- imports;
- calls;
- class inheritance;
- body statements.

The visitor builds the initial structure of the intermediate JSON model.

---

### `body_extractor.py`

Extracts executable body statements from functions and methods.

It identifies body-level nodes such as:

- assignments;
- calls;
- returns;
- raises;
- if statements;
- loops;
- with statements;
- try blocks;
- exception handlers;
- finally blocks.

The output of this module is critical for KDM action modeling because it provides the information used later to create:

- `ActionElement`;
- `BlockUnit`;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`;
- `Reads`;
- `Writes`;
- `Throws`;
- `ExceptionFlow`;
- `ExitFlow`.

---

### `body_call_synchronizer.py`

Synchronizes calls discovered at the callable level with calls embedded inside body statements.

This step is important because a call can appear as:

- a standalone statement;
- the right-hand side of an assignment;
- a return expression;
- a raise expression;
- a condition;
- a context manager expression;
- a nested expression call.

The synchronizer helps the generator later attach call `ActionElement` nodes to the correct body parent.

---

### `call_analyzer.py`

Analyzes Python call expressions.

It extracts information such as:

- call name;
- function or method name;
- receiver object;
- constructor-like calls;
- argument-level calls;
- source line;
- call classification.

This information is later used by `CallResolver` and by the KDM generator to create `Calls` and `Creates` relations.

---

### `call_resolver.py`

Resolves calls against the symbol table.

It attempts to classify and resolve calls as:

- internal functions;
- internal methods;
- constructors;
- builtin calls;
- external calls;
- builtin type methods;
- external type methods;
- unresolved calls.

The result of this phase is stored in the intermediate JSON model using fields such as classification and target identifiers. These temporary fields are consumed by the KDM generator, but are not serialized as final KDM attributes.

---

### `symbol_table.py`

Builds a symbol table from the extracted project model.

The symbol table records known project entities such as:

- files;
- modules;
- classes;
- methods;
- functions;
- parameters;
- local variables.

It is used by import and call resolution phases.

---

### `import_resolver.py`

Resolves imports against the project symbol table.

It classifies imports as internal or external and records target information for later transformation into KDM `Imports` relations.

---

### `model_id_builder.py`

Centralizes the construction of stable identifiers for model elements.

Stable identifiers are important because the JSON model is the contract between the extractor and the generator. They allow the KDM generator to build traceability indexes and connect elements consistently.

Typical identifiers include:

```text
file:example_project.services.user_service
class:example_project.services.user_service.UserService
method:example_project.services.user_service.UserService.create_user
function:example_project.utils.validators.is_valid_name
body:...
call:...
```

---

### `ast_name_resolver.py`

Resolves names from Python AST nodes.

It supports extracting readable names from expressions such as:

- `Name`;
- `Attribute`;
- chained attributes;
- calls;
- subexpressions.

This module is useful for call extraction, assignments, return expressions and exception expressions.

---

### `builtin_type_registry.py`

Stores knowledge about Python builtin types and their methods.

It is used during call and type resolution to classify constructs related to builtin objects.

Examples include calls or methods associated with:

- `str`;
- `list`;
- `dict`;
- `int`;
- `float`;
- `bool`.

---

### `external_type_registry.py`

Stores information about external types and external type methods.

It supports classification of calls that are not defined inside the analyzed project.

---

### `relationship_builder.py`

Builds high-level relationships inside the intermediate JSON model.

These relationships are not necessarily final KDM relations. Instead, they summarize structural or semantic connections discovered during extraction.

---

### `element_builder.py`

Builds a flattened element list from the project model.

This can be useful for inspection, debugging, summaries and later model processing.

---

### `summary_builder.py`

Builds summary information for the extracted project.

The summary may include counts of:

- files;
- classes;
- methods;
- functions;
- imports;
- calls;
- relationships;
- unresolved elements.

---

### `json_writer.py`

Writes the final intermediate model to JSON.

Its main function is:

```python
def write_json_model(model: dict, output_path: str)
```

---

## 5. Intermediate JSON responsibilities

The extractor must produce enough information for the KDM generator to create a semantic KDM model.

At minimum, the JSON model should include:

- project name;
- language;
- files;
- imports;
- classes;
- methods;
- functions;
- parameters;
- local variables;
- calls;
- body statements;
- source line information;
- stable identifiers.

For body-level KDM generation, the extractor must provide enough information to distinguish:

| Python construct | Required JSON information |
|---|---|
| `return x` | statement type, value, line, body id |
| `return f()` | statement type, value calls, call ids |
| `raise X()` | statement type, exception, exception calls |
| `try` | control type, body, handlers, finalbody |
| `except X` | exception handler type, exception name, body |
| `finally` | finalbody list |
| assignment | targets, value, value calls |
| call statement | call id, call object, line |

---

## 6. Body model examples

### Return

```json
{
  "id": "body:return_1",
  "type": "statement",
  "statement_type": "return",
  "line_start": 10,
  "line_end": 10,
  "value": "True"
}
```

This can be transformed into:

```text
ActionElement kind="return"
  └── Reads → StorableUnit return_literal_True
```

---

### Raise

```json
{
  "id": "body:raise_1",
  "type": "statement",
  "statement_type": "raise",
  "line_start": 12,
  "line_end": 12,
  "exception": "RepositoryError",
  "exception_calls": []
}
```

This can be transformed into:

```text
ActionElement kind="raise"
  └── Throws → StorableUnit RepositoryError_exception
```

---

### Try / except / finally

```json
{
  "id": "body:try_1",
  "type": "control_structure",
  "control_type": "try",
  "line_start": 20,
  "line_end": 30,
  "body": [],
  "handlers": [],
  "orelse": [],
  "finalbody": []
}
```

This can be transformed into:

```text
TryUnit
 ├── CatchUnit
 ├── FinallyUnit
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

---

## 7. Identifier conventions

Stable identifiers are essential for linking elements during generation.

Recommended conventions:

```text
file:<qualified_module_name>
class:<qualified_class_name>
method:<qualified_class_name>.<method_name>
function:<qualified_function_name>
call:<stable_hash_or_counter>
body:<stable_hash_or_counter>
```

Identifiers should be:

- unique inside the project model;
- stable between runs when source code does not change;
- descriptive enough to help debugging;
- independent from KDM serialization details.

---

## 8. Relationship with the KDM generator

The extractor produces temporary analysis information such as resolved call targets and classifications.

The generator consumes this information and converts it into KDM relations.

For example:

| JSON analysis field | KDM representation |
|---|---|
| resolved call target | `Calls.to` or `Creates.to` |
| import target | `Imports.to` |
| base class | `Extends.to` |
| returned value | `Reads.to` |
| raised exception | `Throws.to` |
| exception handler | `ExceptionFlow.to` |
| finalbody | `ExitFlow.to` |

Temporary analysis fields should not necessarily appear as final KDM attributes.

---

## 9. Current limitations

The extractor is a research prototype and currently has limitations:

- Python type inference is approximate.
- Dynamic dispatch is only partially resolved.
- Some external calls may remain unresolved.
- Complex expressions may be represented textually rather than semantically.
- Some return expressions may be marked as unresolved by the generator.
- Control-flow modeling is focused on body nesting and exception structures, not full control-flow graphs.
- The extractor depends on Python AST information and does not execute code.

---

## 10. Development recommendations

When extending the extractor:

1. Keep the intermediate JSON stable.
2. Add fixtures for new Python constructs.
3. Avoid introducing KDM-specific assumptions into the extractor.
4. Preserve source line information.
5. Use stable identifiers.
6. Keep call and body information synchronized.
7. Update `intermediate_json_model.md` when the JSON schema changes.
8. Update `json_to_kdm_mapping.md` when a new construct is mapped to KDM.

---

## 11. Summary

`python_kdm_extractor` is responsible for extracting a normalized, language-specific representation of Python projects.

Its output is not KDM. Its output is the intermediate JSON contract used by `kdm_pyecore_generator`.

This design keeps Python analysis and KDM generation separated, making the toolchain easier to test, extend and maintain.
