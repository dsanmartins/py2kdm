# Python extractor

The Python extractor reads a Python project and produces `python_model.json`.

## Command

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

## Extracted information

The extractor records files, modules, classes, functions, methods, parameters, local variables, imports, static calls, value relations, type relations, return relations, exception relations, decorators and block/action structure used later by the KDM generator.

## Body-level information

The Python model can include body-level constructs such as:

```text
assignments
calls
returns
raises
try/except
loops
conditionals
reads
writes
object creations
```

These constructs are used to create behavioral KDM relations such as `Reads`, `Writes`, `Creates`, `Throws` and `ExceptionFlow`.

## Decorators

Python decorators are represented in KDM through:

```text
kdm:Annotation
PythonDecoratorUsage
TaggedValue
```

They are not emitted as loose `Attribute tag="decorators"` entries in the final XMI.

## Output role

`python_model.json` is the base artifact for later stages. Dynamic analysis, architecture recovery, agents and KDM generation all depend on it directly or indirectly.
