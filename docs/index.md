# py2kdm

**Author:** [Daniel San Martín](https://www.danielsanmartin.cl/)

`py2kdm` is a model-driven reverse-engineering workbench for generating validated KDM XMI models from Python and Java projects. It combines static extraction, optional runtime evidence, architecture recovery, human review, and KDM generation using the KDM 1.4 Ecore metamodel.

The current workflow is organized around two complementary interfaces:

- a **GUI workbench** for configuration, pipeline execution, human review, traceability inspection, and artifact inspection;
- a **console pipeline** through `run_pipeline.py` for reproducible command-line execution, KDM validation and regression checks.

## Main workflows

### Direct KDM generation

```text
Python or Java source project
  -> static extraction
  -> intermediate JSON
  -> KDM XMI
  -> KDM validation
  -> regression checks
```

### Architecture-oriented workflow

```text
Python project
  -> static extraction
  -> optional dynamic analysis
  -> architecture recovery
  -> pre-review suggestions
  -> human review
  -> reviewed architecture JSON
  -> final KDM XMI
```

The reviewed architecture JSON is authoritative. Pre-review agents produce reviewable suggestions, but no default post-review agent modifies the reviewed model before KDM generation.

## Language support

| Language | Extractor | Main intermediate artifact |
|---|---|---|
| Python | `python_kdm_extractor` | `python_model.json` |
| Java | `java2kdm` JAR | `java_model.json` |

Both Python and Java KDM models include structural and behavioral elements when the extractor provides enough evidence.

## Behavioral KDM coverage

The KDM generator maps body-level behavior to KDM elements and relations such as:

```text
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
HasValue
Value
```

Java annotations and Python decorators are represented using native KDM annotations and formal extension mechanisms:

```text
kdm:Annotation
Stereotype
TaggedValue
```

## Regression checks

The console pipeline can run integrated regression checks after KDM generation. These checks protect against common regressions such as:

- executable actions directly under `MethodUnit` or `CallableUnit`;
- `return` actions without `Reads` or `return_flow="void"`;
- source regions without file or path;
- debug or redundant attributes in the final XMI.

See [KDM Regression Checks](kdm_regression_checks.md).
