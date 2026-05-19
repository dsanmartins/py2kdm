# py2kdm

`py2kdm` is a configurable Python-to-KDM 1.4 toolchain for reverse engineering Python systems into KDM/EMF-compatible models.

The project currently supports two complementary levels of knowledge discovery:

1. **Code-level recovery**, where Python source code is transformed into a KDM `CodeModel`, `Action` relations, and `InventoryModel`.
2. **Architecture-level recovery**, where self-adaptive systems can be semi-automatically analyzed to infer a proposed `StructureModel`, including architectural components, MAPE-K control-loop elements, architectural relationships, implementation links, and aggregated relations.

The toolchain is designed to support Architecture-Driven Modernization (ADM), model-driven analysis, architectural conformance checking, and KDM-based transformation workflows.

---

## Project structure

```text
py2kdm/
├── python_kdm_extractor/
│   └── Python source code → intermediate JSON model
├── kdm_architecture_recovery/
│   └── intermediate JSON model → architecture-enriched JSON model
├── kdm_pyecore_generator/
│   └── architecture-enriched JSON model → KDM 1.4 XMI model
├── configs/
│   └── pipeline configuration files
├── outputs/
│   └── generated JSON and KDM XMI artifacts
└── run_pipeline.py
    └── end-to-end configurable pipeline
```

---

## Overview

The complete pipeline is:

```text
Python project
   ↓
python_kdm_extractor
   ↓
Intermediate JSON model
   ↓
kdm_architecture_recovery
   ↓
Architecture-enriched JSON model
   ↓
kdm_pyecore_generator
   ↓
KDM 1.4 XMI model
```

The intermediate JSON model is the contract between the extractor, the architecture recovery module, and the KDM generator. This separation allows each phase to evolve independently.

The architecture recovery phase is intentionally **semi-automatic**. It does not assume that every project has an architectural design explicitly documented. Instead, it proposes an inferred current architecture from code evidence, such as naming, imports, decorators, calls, subscriptions, and framework-specific usage patterns.

---

## Subprojects

### 1. `python_kdm_extractor`

This subproject analyzes Python source code and produces an intermediate JSON model.

It performs the following tasks:

- scans a Python project and finds `.py` files;
- parses Python files using the native `ast` module;
- extracts files, imports, classes, functions, methods, parameters and local variables;
- analyzes calls, constructor calls, variable references and attribute references;
- resolves imports and internal/external calls when possible;
- synchronizes body-level statements with call information;
- extracts values, assignments, literals, collection literals and call results;
- builds a JSON model containing structural and behavioral information.

Main entry point:

```bash
cd python_kdm_extractor
python main.py <path-to-python-project>
```

Typical output:

```text
outputs/<case_name>/python_model.json
```

---

### 2. `kdm_architecture_recovery`

This subproject enriches the intermediate JSON model with architecture-level information.

Its current focus is the recovery of **self-adaptive MAPE-K architectures**.

It performs the following tasks:

- evaluates whether the analyzed system is a candidate self-adaptive system;
- applies a visible rule-based autonomic applicability gate;
- detects MAPE-K role candidates;
- detects framework-style MAPE-K definitions, including PyMAPE decorators;
- recovers architectural components;
- recovers candidate control loops;
- separates technical relationships from architectural relationships;
- generates an inferred `structure_model` section in the architecture-enriched JSON.

The module does not force an architecture when the system does not exhibit enough self-adaptive evidence. For example, a conventional three-layer system should not produce an artificial MAPE-K view.

---

### 3. `kdm_pyecore_generator`

This subproject reads the architecture-enriched JSON model and generates a KDM 1.4 XMI model using PyEcore.

It performs the following tasks:

- loads the KDM 1.4 Ecore metamodel;
- creates the root `Segment`;
- creates `InventoryModel` and `SourceFile` elements;
- creates `CodeModel`, `CompilationUnit`, `ClassUnit`, `MethodUnit`, `CallableUnit`, `ParameterUnit` and `StorableUnit` elements;
- creates `BlockUnit` elements to represent callable bodies;
- creates action elements and control-flow elements;
- creates KDM relations such as `Calls`, `Creates`, `Reads`, `Writes`, `Throws`, `ExceptionFlow`, `ExitFlow`, `HasType`, `HasValue`, `Imports` and `Extends`;
- creates `StructureModel` when architecture recovery is available;
- links recovered architectural components to concrete code elements through `implementation`;
- creates `StructureRelationship` for architectural relations;
- creates `AggregatedRelationship` through `aggregatedRelation`;
- validates the generated KDM model;
- serializes the final model as XMI.

Main entry point:

```bash
cd kdm_pyecore_generator
python main.py \
  --input input/python_model.json \
  --output output/example_project.kdm.xmi \
  --metamodel metamodels/kdm_1_4.ecore
```

Validation can be disabled with:

```bash
python main.py --no-validation
```

---

## End-to-end usage

The recommended way to run the complete workflow is from the root directory using `run_pipeline.py`.

Example:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

This command executes:

```text
1. Python source extraction
2. Architecture recovery
3. KDM XMI generation
```

Typical outputs are:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/python_model.architecture.json
outputs/pymape_hierarchical/model.kdm.xmi
```

A negative or non-autonomic case can be executed with a separate configuration, for example:

```bash
python run_pipeline.py --config configs/three_layer_system.json
```

The expected behavior for a conventional three-layer system is that MAPE-K recovery is disabled and no artificial self-adaptive architecture is generated.

---

## Configuration-based execution

The pipeline is configuration-driven. A configuration file defines:

- the source project to analyze;
- the intermediate JSON output path;
- the architecture-enriched JSON output path;
- the KDM XMI output path;
- which phases should be executed.

This allows the same pipeline to be reused for several systems without modifying source code.

A typical configuration is conceptually:

```json
{
  "case_name": "pymape_hierarchical",
  "source_project": "examples/pymape_hierarchical",
  "intermediate_json": "outputs/pymape_hierarchical/python_model.json",
  "architecture_json": "outputs/pymape_hierarchical/python_model.architecture.json",
  "kdm_xmi": "outputs/pymape_hierarchical/model.kdm.xmi"
}
```

---

## Current KDM mapping support

The current generator supports the following mappings from the intermediate JSON model to KDM 1.4.

### Structural code mapping

| Intermediate JSON element | KDM element |
|---|---|
| Project | `Segment` |
| Python file | `CompilationUnit` |
| Class | `ClassUnit` |
| Method | `MethodUnit` |
| Function | `CallableUnit` |
| Callable body | `BlockUnit` |
| Parameter | `ParameterUnit` |
| Local variable | `StorableUnit` |
| Source file | `SourceFile` |

### Callable body mapping

Executable statements are not attached directly to `MethodUnit` or `CallableUnit`. Instead, each function or method with a body receives a dedicated `BlockUnit`:

```text
MethodUnit / CallableUnit
 └── BlockUnit name="body" kind="body"
      ├── ActionElement
      ├── TryUnit
      ├── CatchUnit
      ├── FinallyUnit
      └── ...
```

The generated `BlockUnit` includes traceability attributes:

```xml
<attribute tag="role" value="callable_body"/>
<attribute tag="callable_body_id" value="..."/>
```

This keeps the declaration of the callable separated from its executable body and aligns the model more closely with KDM 1.4 block semantics.

### Action and relation mapping

| Python/JSON concept | KDM representation |
|---|---|
| Function or method call | `ActionElement` + `Calls` |
| Constructor call | `ActionElement` + `Creates` |
| Assignment | `Writes` and/or `HasValue` |
| Variable read | `Reads` |
| Return statement | `ActionElement kind="return"` + `Reads` |
| Raise statement | `ActionElement kind="raise"` + `Throws` |
| Try block | `TryUnit` |
| Except block | `CatchUnit` |
| Finally block | `FinallyUnit` |
| Try to except flow | `ExceptionFlow` |
| Try to finally flow | `ExitFlow` |
| Type association | `HasType` |
| Literal value association | `HasValue` |
| Import | `Imports` |
| Inheritance | `Extends` |

---

## Architecture recovery support

The architecture recovery module currently supports self-adaptive systems following or approximating a MAPE-K organization.

### Autonomic applicability gate

Before generating a MAPE-K architectural view, the tool evaluates whether the system appears to be self-adaptive.

The gate uses visible rules, including evidence such as:

- explicit self-adaptation vocabulary;
- MAPE-K role vocabulary;
- monitor, analyze, plan, execute or knowledge terms;
- runtime observation evidence;
- effector or adaptation action evidence;
- shared knowledge evidence;
- partial control-loop evidence.

The gate can return, for example:

```json
{
  "decision": "candidate_autonomic_system",
  "status": "mapek_recovery_enabled",
  "score": 0.9
}
```

or, for a non-autonomic system:

```json
{
  "decision": "not_applicable",
  "status": "mapek_recovery_disabled"
}
```

### MAPE-K role inference

The recovery module can infer roles from:

- class names;
- method names;
- module paths;
- call relationships;
- decorators;
- registration patterns;
- framework-specific usage.

For PyMAPE-style systems, the tool can detect decorators such as:

```python
@loop.monitor
def distance(...):
    ...

@loop.plan()
def pid(...):
    ...

@loop.execute
def speed(...):
    ...
```

and infer:

```text
distance  → Monitor
pid       → Planner
speed     → Executor
```

The resulting role suggestions are classified by confidence and status:

```text
auto_accepted
needs_review
weak_suggestion
```

Weak suggestions are kept as evidence but are not automatically promoted to architecture components.

---

## KDM StructureModel generation

When architecture recovery is enabled, the generator creates a KDM `StructureModel`.

The generated `StructureModel` may include:

```text
StructureModel
├── SoftwareSystem
├── ArchitectureView
├── Component
├── StructureElement
├── Subsystem
└── StructureRelationship
```

For a recovered MAPE-K system, an example conceptual structure is:

```text
StructureModel: InferredCurrentArchitecture
├── SoftwareSystem: pymape_hierarchical
├── ArchitectureView: Inferred MAPE-K View
├── Component: distance
├── Component: pid
├── Component: speed_executor
├── Component: speed_monitor
├── Component: gas_brake
├── Component: Loop
├── Component: Knowledge
├── StructureElement: Loop Control Loop
└── Subsystem: Managing Subsystem
```

### ArchitectureView

`ArchitectureView` represents the architectural viewpoint used to interpret the recovered elements.

For self-adaptive systems, the current view is:

```text
Inferred MAPE-K View
```

This view should be interpreted as a proposed current architecture inferred from source-code evidence, not as a manually designed architecture.

### Component names

If two recovered components have the same source-level name but different roles, the generator disambiguates them.

For example:

```text
speed → Monitor
speed → Executor
```

becomes:

```text
speed_monitor
speed_executor
```

The original source-level name is still preserved through attributes such as:

```xml
<attribute tag="recovered_name" value="speed"/>
<attribute tag="original_component_name" value="speed"/>
```

---

## Architecture-to-code implementation links

Recovered architectural components are linked to the code elements that implement them using the KDM `implementation` reference.

For example:

```xml
<structureElement
    xsi:type="structure:Component"
    name="pid"
    implementation="//@model.1/@codeElement.0/@codeElement.2">
```

This means that the architectural component `pid` is implemented by a concrete KDM code element, such as a `CallableUnit` or `MethodUnit`.

The same code element may implement more than one architectural role. For example, a function named `speed` may be represented as both:

```text
speed_monitor
speed_executor
```

if the architecture recovery phase detects evidence for both roles.

---

## Architecture relationships

The recovery module distinguishes between technical evidence and architectural relationships.

### Technical relationships

Technical relationships are low-level implementation evidence. For example:

```text
subscribes_to
```

These relationships may come from framework or runtime constructs such as:

```python
distance.subscribe(pid)
```

Technical relationships are kept in the architecture JSON as evidence but are not necessarily materialized as primary architectural KDM relationships.

### Architectural relationships

Architectural relationships are materialized in the KDM `StructureModel`.

Currently supported architectural relationship types include:

```text
mapek_flow
uses_knowledge
```

These are generated as `StructureRelationship` elements.

Example:

```xml
<structureRelationship
    xsi:type="structure:StructureRelationship"
    from="..."
    to="...">
  <attribute tag="relationship_type" value="mapek_flow"/>
</structureRelationship>
```

---

## Aggregated relationships

For each generated architectural `StructureRelationship`, the generator can also create a KDM `AggregatedRelationship`.

Aggregated relationships are owned by the source `KDMEntity` through:

```text
aggregatedRelation
```

Example:

```xml
<aggregatedRelation
    from="//@model.4/@structureElement.3"
    to="//@model.4/@structureElement.4"
    relation="//@model.4/@structureElement.3/@structureRelationship.0"
    density="1">
</aggregatedRelation>
```

This allows the KDM model to support aggregated in/out relationship navigation through KDM mechanisms such as:

```text
getInAggregated()
getOutAggregated()
```

The generator currently creates one aggregated relation per explicit architectural relation, with `density="1"`.

---

## Exception mapping

Exceptions are modeled using KDM action elements and standard KDM exception-flow relations.

For a Python statement such as:

```python
raise RepositoryError(...)
```

The generated KDM structure is conceptually:

```text
ActionElement kind="raise"
 ├── StorableUnit RepositoryError_exception
 │    └── HasType → RepositoryError
 └── Throws → RepositoryError_exception
```

For a `try/except/finally` block:

```python
try:
    ...
except RepositoryError:
    ...
finally:
    ...
```

The generated KDM structure is conceptually:

```text
TryUnit
 ├── CatchUnit
 ├── FinallyUnit
 ├── ExceptionFlow → CatchUnit
 └── ExitFlow → FinallyUnit
```

The generator no longer uses temporary generic relations such as:

```text
ActionRelationship kind="catches"
```

Instead, catch blocks are modeled using `CatchUnit` and `ExceptionFlow`.

---

## Return mapping

KDM 1.4 does not define a specific `Returns` relation. Therefore, returned values are modeled as data read by the return action.

For:

```python
return x
```

The generated structure is:

```text
ActionElement kind="return"
 └── Reads → StorableUnit x
```

For:

```python
return True
```

The generated structure is:

```text
ActionElement kind="return"
 ├── StorableUnit return_literal_True
 │    └── HasValue → Value True
 └── Reads → return_literal_True
```

For:

```python
return json.dumps(data)
```

The generated structure is:

```text
ActionElement kind="return"
 ├── ActionElement json.dumps
 ├── StorableUnit return_value_of_json_dumps
 └── Reads → return_value_of_json_dumps
```

---

## Validation

The KDM generator includes validation rules for the generated model.

The validator checks, among others:

- the presence of an `InventoryModel`;
- valid `SourceFile` and `SourceRegion` information;
- valid targets for `HasType`, `HasValue`, `Reads`, `Writes`, `Throws`, `ExceptionFlow`, `ExitFlow`, `Imports` and `Extends`;
- callable body structure using `BlockUnit body`;
- absence of direct executable `ActionElement` children under `MethodUnit` or `CallableUnit`;
- semantic consistency of `return`, `raise`, `try`, `except` and `finally` mappings;
- absence of obsolete temporary attributes such as `resolved`, `target_id`, `statement_type`, `body_type`, `control_type`, `condition`, `exception`, `value` and generic attribute `kind`;
- absence of duplicate attributes, duplicate source regions and duplicate child actions.

For structure models, validation should also check:

- presence of `StructureModel` only when architecture recovery is enabled;
- valid `implementation` references from `StructureElement` to code elements;
- valid `StructureRelationship` endpoints;
- valid `AggregatedRelationship` endpoints;
- consistency between `StructureRelationship` and `AggregatedRelationship`;
- absence of obsolete temporary structure attributes.

---

## Tests

The KDM generator includes an automated test suite based on `pytest`.

To run the tests:

```bash
cd kdm_pyecore_generator
pytest -q
```

The current test suite checks:

- stable serialization;
- CLI-based generation with configurable input/output paths;
- absence of obsolete attributes;
- presence of semantic KDM relations;
- callable body modeling through `BlockUnit`;
- exception mappings;
- return mappings;
- edge-case fixtures such as bare return, return literal, bare raise and bare except.

Recommended additional tests for the architecture recovery phase:

- positive MAPE-K recovery case using PyMAPE;
- negative non-autonomic case using a three-layer system;
- component name disambiguation;
- `implementation` links from `Component` to `CodeModel`;
- generation of `StructureRelationship`;
- generation of `AggregatedRelationship`;
- preservation of technical relationships as evidence only.

---

## Repository hygiene

The following generated files and directories should not be committed:

```gitignore
__pycache__/
*.pyc
.pytest_cache/
outputs/
output/test_fixtures/
output/run1.kdm.xmi
output/run2.kdm.xmi
output/example_project_cli_test.kdm.xmi
```

---

## Documentation plan

Suggested documentation files:

```text
docs/
├── architecture.md
├── intermediate_json_model.md
├── architecture_recovery.md
├── json_to_kdm_mapping.md
├── structure_model_mapping.md
├── validation_rules.md
├── cli_usage.md
└── development_guide.md
```

The README should provide the general overview. The `docs/` directory should contain the detailed technical documentation.

---

## Current status

The current prototype supports a working Python-to-KDM pipeline through an intermediate JSON model and an optional architecture recovery phase.

The KDM generator produces stable XMI output and includes validation for the main semantic mappings. Callable bodies are modeled explicitly using `BlockUnit`, while exceptions, returns, reads/writes and calls are represented through standard KDM elements and relations whenever possible.

For self-adaptive systems, the toolchain can now infer a proposed MAPE-K architectural view and generate a KDM `StructureModel` with:

- `SoftwareSystem`;
- `ArchitectureView`;
- `Component`;
- `StructureElement` for control-loop representation;
- `Subsystem`;
- `StructureRelationship`;
- `implementation` links to the `CodeModel`;
- `AggregatedRelationship` through `aggregatedRelation`.

For systems without sufficient autonomic evidence, MAPE-K recovery is disabled to avoid generating misleading architectural views.
