# Python Extractor

The Python extractor produces the initial intermediate JSON model from a Python project.

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

## Extracted information

The extractor collects:

- source files and modules;
- classes, functions, methods, parameters, and variables;
- imports and inheritance relationships;
- calls and constructor-like calls when statically resolvable;
- body actions represented as executable statements;
- reads, writes, values, returns, and exceptions;
- source references for traceability.

## Static limitations

Python is dynamic, so static extraction may not resolve every call or type. Examples include:

- duck typing;
- dynamically injected dependencies;
- decorators;
- framework callbacks;
- runtime-bound object methods;
- external libraries without static project definitions.

The dynamic analysis stage complements this by observing real calls and concrete runtime types during scenario execution.

## Output

The main output is:

```text
python_model.json
```

This artifact is the base input for optional dynamic enrichment, architecture recovery, and KDM generation.
