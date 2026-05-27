# Artifact reference

The **Artifacts** tab summarizes generated files and lets the user inspect them without leaving the GUI.

## Common artifacts

| Artifact | Description |
|---|---|
| `python_model.json` | Intermediate model extracted from Python source code. |
| `java_model.json` | Intermediate model extracted from Java source code by `java2kdm`. |
| `runtime_trace.<scenario>.json` | Raw runtime trace for one scenario. |
| `python_model.runtime_enriched.<scenario>.json` | Intermediate runtime-enriched model for one scenario. |
| `python_model.runtime_enriched.combined.json` | Combined runtime-enriched model after all enabled scenarios. |
| `*.architecture.json` | Recovered architecture over the selected intermediate model. |
| `*.ai_architecture.json` | Architecture proposal with pre-review AI suggestions. |
| `*.reviewed_architecture.json` | Human-reviewed architecture model. |
| `model.kdm.xmi` | Generated KDM XMI model. |

## Java artifacts

A Java run typically produces:

```text
outputs/demo-java-project/java_model.json
outputs/demo-java-project/model.kdm.xmi
```

## Python artifacts

A Python run typically produces:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/model.kdm.xmi
```

If dynamic analysis or architecture recovery is enabled, additional enriched JSON files are generated.

## KDM inspection

The final XMI should contain structural and behavioral KDM elements such as:

```text
SourceFile
CompilationUnit
ClassUnit
MethodUnit
CallableUnit
ParameterUnit
StorableUnit
ActionElement
BlockUnit
Calls
Reads
Writes
Creates
Throws
TryUnit
CatchUnit
ExceptionFlow
```
