# 5. Technical artifacts and KDM construction

This section describes the main JSON artifacts, their sections, how they are constructed, and how they are mapped to KDM XMI.

## Artifact chain

```text
source code
  -> python_model.json / java_model.json
  -> runtime_trace.<scenario>.json, optional
  -> *.runtime_enriched.*.json, optional
  -> *.architecture.json
  -> *.ai_architecture.json, optional
  -> *.reviewed_architecture.json, optional
  -> *.kdm.xmi
```

## Intermediate JSON: `python_model.json` / `java_model.json`

Constructed by:

```text
python_kdm_extractor/main.py
java -jar tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar
```

Main sections:

| Section | Meaning |
|---|---|
| `metadata` | Project, language, execution or extraction information when available. |
| `files` | Source files, modules, classes, methods, functions, fields, parameters, local variables and body elements. |
| `relationships` | Static relationships such as imports, calls, reads, writes, creates, extends, implements, throws, type and value relations. |
| `packages` / `elements` | Language-dependent summaries or normalized elements when provided by the extractor. |

The exact shape can differ between Python and Java. The KDM mapper accepts both snake_case and camelCase variants, for example `line_start` and `lineStart`, or `statement_type` and `statementType`.

### Body-level information

The extractors can record:

```text
assignments
calls
returns
raises / throws
try / catch / finally
loops
conditionals
reads
writes
object creation
literals and expressions
```

This information is used by the KDM generator to create `ActionElement`, `BlockUnit` and behavior relations.

## Runtime trace JSON: `runtime_trace.<scenario>.json`

Constructed by:

```text
kdm_dynamic_analysis/main.py trace-and-enrich
```

Main sections:

| Section | Meaning |
|---|---|
| `metadata` | Scenario name, mode, execution status and error information. |
| `events` | Observed runtime events, such as calls, returns and exceptions. |
| `summary` | Aggregated runtime statistics when available. |

This artifact is raw runtime evidence. It is not normally passed directly to the KDM generator.

## Runtime-enriched JSON: `*.runtime_enriched.*.json`

Constructed by dynamic analysis by combining the static model and the runtime trace.

Main sections:

| Section | Meaning |
|---|---|
| Static model sections | The original extracted model. |
| `runtime_enrichment` | Scenario summaries, observed runtime calls and dynamic evidence. |
| Updated `relationships` | Additional runtime-supported relationships when available. |

When several scenarios are used, the pipeline can produce a combined runtime-enriched model.

## Architecture JSON: `*.architecture.json`

Constructed by:

```text
kdm_architecture_recovery/main.py
```

Main sections:

| Section | Meaning |
|---|---|
| Static or runtime-enriched model sections | Original code evidence retained for KDM generation. |
| `architecture_recovery` / recovery metadata | Decision, score, status and MAPE-K applicability information when present. |
| `structure_model` | Architecture-level model to be materialized into KDM `StructureModel`. |
| `architecture_consistency` | Warnings, blocked constructions and consistency information when present. |

### `structure_model`

Important subsections:

| Section | Meaning |
|---|---|
| `subsystems` | Architecture containers such as Managing Subsystem and Managed Subsystem. |
| `control_loops` | Control loop abstractions. |
| `components` | Components with roles, stereotypes and implementation evidence. |
| `structure_relationships` | Architecture relations between components or subsystems. |
| `containment_relationships` | Containment between subsystems, loops and components. |

Typical component fields:

| Field | Meaning |
|---|---|
| `id` | Stable architecture component identifier. |
| `name` | Human-readable component name. |
| `role` | MAPE-K or adaptive-system role. |
| `stereotype_name` | KDM stereotype to apply. |
| `implemented_by` | Code element identifiers that implement the component. |
| `materialize` | Whether this element should be emitted to KDM. |
| `confidence` | Recovery confidence when available. |
| `evidence` | Static, runtime or naming evidence. |

## AI architecture JSON: `*.ai_architecture.json`

Constructed by:

```text
kdm_architecture_agents/main.py --mode pre-review
```

Main additional sections:

| Section | Meaning |
|---|---|
| `ai_enrichment` | Suggestions from deterministic and LLM-assisted pre-review. |
| `code_context` | Compact selected code evidence used for review. |
| `deterministic_code_review` | Deterministic assessment of recovered roles using code context. |
| `summary` or metadata | Provider, model, number of suggestions, code-context availability and related diagnostics. |

This artifact is used by the Human Review tab. It is normally not the authoritative source for automatic KDM generation.

## Reviewed architecture JSON: `*.reviewed_architecture.json`

Constructed by the Human Review GUI after validation and export.

Main additional section:

| Section | Meaning |
|---|---|
| `architecture_review` | Review status, decisions, accepted/rejected suggestions, component and relationship overrides. |

This is the authoritative artifact for `model.reviewed.kdm.xmi`.

## KDM construction

Constructed by:

```text
kdm_pyecore_generator/main.py
```

The generator uses the KDM 1.4 Ecore metamodel through PyEcore.

### Inventory model

Source files are mapped to:

```text
source:InventoryModel
source:SourceFile
source:SourceRegion
source:SourceRef
```

### Code model

Code entities are mapped to:

| JSON evidence | KDM representation |
|---|---|
| File/module/class container | `code:CompilationUnit`, `code:CodeModel` containers. |
| Class | `code:ClassUnit`. |
| Function | `code:CallableUnit`. |
| Method/constructor | `code:MethodUnit`. |
| Parameter | `code:ParameterUnit`. |
| Variable/field/local | `code:StorableUnit`. |
| Type evidence | `code:HasType`. |
| Value evidence | `code:Value`, `code:HasValue`. |

### Behavioral mapping

| JSON evidence | KDM representation |
|---|---|
| Method/function body | `code:BlockUnit`. |
| Call | `action:ActionElement` + `action:Calls`. |
| Read | `action:Reads`. |
| Write/assignment | `action:Writes`. |
| Object creation | `action:Creates`. |
| Return | `ActionElement kind="return"` plus `Reads` or `return_flow="void"`. |
| Raise/throw | `action:Throws`. |
| Try/catch | `action:TryUnit`, `action:CatchUnit`, `action:ExceptionFlow`. |

Executable body actions must be contained in a `BlockUnit`, not directly under a `MethodUnit` or `CallableUnit`.

### Annotations and decorators

Java annotations and Python decorators are represented through KDM extension mechanisms:

```text
kdm:Annotation
Stereotype
TaggedValue
JavaAnnotationUsage
PythonDecoratorUsage
```

They should not appear as loose debug attributes in the final XMI.

### Structure model

When the input JSON contains `structure_model`, the generator creates:

```text
structure:StructureModel
structure:SoftwareSystem
structure:ArchitectureView
structure:Subsystem
structure:Component
structure:StructureRelationship
core:AggregatedRelationship
```

Component roles are represented through the `Adaptive System Domain` extension family and stereotypes such as:

```text
Monitor
Analyzer
Planner
Executor
Knowledge
Sensor
Effector
LoopManager
Control Loop
Managing Subsystem
Managed Subsystem
```

### Implementation traceability

A `structure:Component` can include:

```xml
implementation="..."
```

This points to the `CodeItem` or code element that implements the architecture component. For example, a `Planner` component can point to the corresponding function, method or class in the `CodeModel`.

### Aggregated relationships

`AggregatedRelationship` represents an architecture-level relationship aggregated from lower-level evidence. It uses:

```text
from
to
relation
density
```

The derived navigation properties `inAggregated` and `outAggregated` should not be serialized manually. The relation should be represented through `aggregatedRelation` with `from`, `to`, `relation` and `density`.

## Validation and regression

Important checks include:

- no executable `ActionElement` directly under `MethodUnit` or `CallableUnit`;
- return actions have either `Reads` or `return_flow="void"`;
- `SourceRegion` has source information;
- debug or redundant internal attributes are absent from XMI;
- `StructureModel` exists when expected;
- `Adaptive System Domain` exists when structure is expected;
- components, subsystems, relationships, `implementation` links and `aggregatedRelation` entries meet baseline expectations.
