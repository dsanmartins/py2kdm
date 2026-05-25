# Python extractor

The Python extractor reads a Python project and produces `python_model.json`.

## Command

```bash
python python_kdm_extractor/main.py   --input examples/three_layer_system   --output outputs/three_layer_system/python_model.json
```

## Extracted information

The extractor records files, modules, classes, functions, methods, parameters, local variables, imports, static calls, value relations, type relations, return relations, exception relations, and block/action structure used later by the KDM generator.

## Output role

`python_model.json` is the base artifact for all later stages. Dynamic analysis, architecture recovery, agents and KDM generation all depend on it directly or indirectly.
