# Python Extractor

## Purpose

`python_kdm_extractor` analyzes a Python project and produces an intermediate JSON model. The extractor does not generate KDM directly. It creates a normalized source model that can be consumed by architecture recovery and KDM generation.

## Entry point

Preferred usage:

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

Backward-compatible usage:

```bash
python python_kdm_extractor/main.py examples/pymape_hierarchical
```

## Extraction pipeline

The extractor performs the following steps:

1. Scans the input directory for Python files.
2. Parses each file using Python's `ast` module.
3. Extracts file-level, class-level and callable-level information.
4. Builds a symbol table.
5. Resolves imports and calls when possible.
6. Synchronizes body-level statements with calls.
7. Builds project-level relationships.
8. Computes summary information.
9. Writes the intermediate JSON model.

## Extracted elements

The extractor identifies:

- source files;
- imports;
- classes;
- methods;
- functions;
- parameters;
- local variables;
- global variables;
- instance attributes;
- calls;
- constructor calls;
- assignments;
- reads and writes;
- returns;
- raises;
- try, except and finally blocks;
- body-level statements.

## Body extraction

Function and method bodies are represented explicitly in the JSON. This enables the KDM generator to create `BlockUnit`, body-level `ActionElement` nodes and relations such as `Calls`, `Reads`, `Writes`, `Throws`, `ExceptionFlow` and `ExitFlow`.

## Symbol and call resolution

The extractor builds a symbol table and attempts to resolve:

- internal class references;
- function calls;
- method calls;
- constructor calls;
- imported elements;
- external calls.

When a target cannot be resolved, the unresolved information is still preserved for traceability and later validation.

## Output structure

The output JSON contains:

```json
{
  "projectName": "example_project",
  "language": "python",
  "files": [],
  "elements": [],
  "relationships": [],
  "symbol_table": {},
  "summary": {}
}
```

The architecture recovery stage may enrich this JSON with additional architecture-level fields.
