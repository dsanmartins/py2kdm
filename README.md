# py2kdm

`py2kdm` is a configurable Python-to-KDM 1.4 toolchain for reverse engineering Python projects into KDM/EMF-compatible models.

The project supports two complementary levels of recovery:

1. **Code-level recovery**, where Python source code is transformed into an intermediate JSON model and then into KDM `CodeModel`, `InventoryModel`, action elements and code relations.
2. **Architecture-level recovery**, where candidate self-adaptive architectures can be inferred from the intermediate JSON model and represented as a KDM `StructureModel` with Adaptive System Domain stereotypes.

The toolchain is designed to support Architecture-Driven Modernization, model-driven analysis, architectural recovery, KDM-based transformation workflows, human-in-the-loop architecture review, and traceable modernization experiments.

---

## Current status

The current version supports the following end-to-end workflow:

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
Architecture Review GUI
   ↓
Reviewed architecture JSON
   ↓
kdm_pyecore_generator
   ↓
KDM 1.4 XMI model
```

Main implemented capabilities:

```text
✓ Python static extraction
✓ Intermediate JSON model
✓ MAPE-K architecture recovery
✓ Adaptive System Domain stereotypes
✓ KDM StructureModel generation
✓ Nested architectural containment
✓ KDM traceability links
✓ Human-in-the-loop Architecture Review GUI
✓ Reviewed JSON export
✓ Reviewed KDM generation
✓ MkDocs documentation
```

---

## Project structure

```text
py2kdm/
├── run_pipeline.py
├── configs/
│   └── pipeline configuration files
├── examples/
│   └── example Python systems
├── outputs/
│   └── generated JSON and KDM XMI artifacts
├── python_kdm_extractor/
│   └── Python source code → intermediate JSON model
├── kdm_architecture_recovery/
│   └── intermediate JSON → architecture-enriched JSON
├── kdm_architecture_review/
│   ├── review validator
│   └── gui/
│       └── Architecture Review GUI
├── kdm_pyecore_generator/
│   └── JSON model → KDM 1.4 XMI model
├── docs/
│   └── MkDocs documentation
└── mkdocs.yml
```

---

## Main pipeline

The complete automated pipeline is:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
```

This executes:

```text
1. Python extraction
2. Architecture recovery
3. KDM generation
```

To stop after architecture recovery:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
```

Expected outputs:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/python_model.architecture.json
outputs/pymape_hierarchical/model.kdm.xmi
```

---

## Python extraction

The extractor scans Python projects and produces a normalized JSON representation containing:

- source files;
- imports;
- classes;
- methods and functions;
- parameters;
- local variables;
- global variables;
- instance attributes;
- calls and constructor calls;
- assignments;
- reads and writes;
- returns and raises;
- try, except and finally blocks;
- body-level statements;
- internal relationships and symbol-table information.

Direct execution:

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

Backward-compatible execution:

```bash
python python_kdm_extractor/main.py examples/pymape_hierarchical
```

---

## Architecture recovery

The architecture recovery module identifies candidate self-adaptive architecture abstractions from the intermediate JSON model.

Supported Adaptive System Domain abstractions include:

```text
Monitor
Analyzer
Planner
Executor
Knowledge
Reference Input
Measured Output
Sensor
Effector
CL Manager
Control Loop
Managing Subsystem
Managed Subsystem
```

The recovery process is **evidence-driven**. It does not create all possible autonomic abstractions by default. For example:

- `Effector` can be recovered from evidence such as `brake`, `gas`, `siren`, or `hazard_lights`.
- `Sensor` can be recovered from evidence such as `sensor`, `read`, `measure`, or `observe`.
- `Measured Output` can be recovered from evidence such as `current_speed`, `measured_distance`, or `actual_temperature`.
- `Reference Input` can be recovered from evidence such as `target_speed`, `desired_distance`, `setpoint`, `goal`, or `threshold`.

If no explicit evidence exists, the abstraction is not automatically invented.

---

## MAPE-K recovery

The recovery process can identify:

```text
Monitor
Analyzer
Planner
Executor
Knowledge
```

It supports decorator-based and registration-style evidence, for example:

```python
@loop.monitor
def distance(...):
    ...

@loop.plan
def pid(...):
    ...

@loop.execute
def gas_brake(...):
    ...
```

The recovered architecture can include a control loop such as:

```text
Managing Subsystem
  └── CL Manager
        └── Control Loop
              ├── Monitor
              ├── Planner
              ├── Executor
              └── Knowledge

Managed Subsystem
  ├── Effector
  ├── Sensor
  └── Measured Output
```

`Control Loop` is represented in KDM as:

```text
structure::Component <<Control Loop>>
```

because KDM does not define a native `structure::ControlLoop` metaclass.

---

## Semantic construction rules

The architecture is not generated first and validated afterwards. Instead, the recovery process applies semantic construction rules during architecture construction.

Allowed examples:

```text
Managing Subsystem -> CL Manager
CL Manager -> Control Loop
Control Loop -> Monitor
Control Loop -> Planner
Control Loop -> Executor
Managed Subsystem -> Effector
```

Forbidden examples are blocked during construction:

```text
Managed Subsystem -> Planner
Managing Subsystem -> Sensor
Control Loop -> Effector
```

The architecture JSON may contain:

```json
"architecture_consistency": {
  "status": "constructed_with_warnings",
  "applied_rules": [],
  "warnings": [],
  "blocked_constructions": []
}
```

This section is a construction report, not a separate external validation phase.

---

## Managed interaction recovery

The recovery module can also infer candidate interactions between managing-side and managed-side abstractions.

Examples:

```text
Executor -> Effector                 acts_through
Monitor  -> Sensor                   observes_through
Monitor  -> Measured Output          observes
Sensor   -> Measured Output          produces_measurement
Analyzer/Planner -> Reference Input  uses_reference_input
Analyzer/Planner -> Measured Output  evaluates_measured_output
```

These relations are only generated when there is meaningful name or implementation evidence.

For example, if an executor is named `gas_brake`, the system can infer:

```text
gas_brake <<Executor>> --acts_through--> gas   <<Effector>>
gas_brake <<Executor>> --acts_through--> brake <<Effector>>
```

---

## KDM generation

The KDM generator creates a KDM 1.4 XMI model using PyEcore.

It supports:

- `InventoryModel` and `SourceFile`;
- `CodeModel`;
- `CompilationUnit`;
- `ClassUnit`;
- `MethodUnit`;
- `CallableUnit`;
- `ParameterUnit`;
- `StorableUnit`;
- `BlockUnit`;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`;
- body-level `ActionElement` nodes;
- relations such as `Calls`, `Creates`, `Reads`, `Writes`, `HasType`, `HasValue`, `Imports`, `Extends`, `Throws`, `ExceptionFlow`, and `ExitFlow`;
- optional architecture `StructureModel`;
- Adaptive System Domain `extensionFamily`;
- `StructureRelationship`;
- `AggregatedRelationship`;
- architecture implementation links.

Direct execution:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi
```

If the KDM metamodel path is not resolved from the current directory, use:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi \
  --metamodel kdm_pyecore_generator/metamodels/kdm_1_4.ecore
```

---

## Adaptive System Domain stereotypes

The generator creates an `extensionFamily` under the KDM segment:

```xml
<extensionFamily name="Adaptive System Domain">
  <stereotype name="Monitor" type="structure:Component"/>
  <stereotype name="Analyzer" type="structure:Component"/>
  <stereotype name="Planner" type="structure:Component"/>
  <stereotype name="Executor" type="structure:Component"/>
  <stereotype name="Knowledge" type="structure:Component"/>
  <stereotype name="Reference Input" type="structure:Component"/>
  <stereotype name="Measured Output" type="structure:Component"/>
  <stereotype name="CL Manager" type="structure:Component"/>
  <stereotype name="Control Loop" type="structure:Component"/>
  <stereotype name="Sensor" type="structure:Component"/>
  <stereotype name="Effector" type="structure:Component"/>
  <stereotype name="Managing Subsystem" type="structure:Subsystem"/>
  <stereotype name="Managed Subsystem" type="structure:Subsystem"/>
</extensionFamily>
```

Architecture elements reference these stereotypes through the KDM `stereotype` reference.

---

## Architecture Review GUI

The Architecture Review GUI provides a human-in-the-loop review layer between automatic architecture recovery and final KDM generation.

Start the GUI:

```bash
python -m kdm_architecture_review.gui.main
```

Open:

```text
outputs/pymape_hierarchical/python_model.architecture.json
```

The GUI supports:

```text
✓ Architecture tree view
✓ Architecture graph view
✓ Zoom with mouse wheel
✓ Pan with mouse drag
✓ Movable architecture nodes
✓ Component editing
✓ Relationship editing
✓ Code traceability display
✓ Validation panel
✓ Reviewed JSON export
✓ Review actions export
```

The graph shows the recovered architecture and allows visual inspection of relationships such as:

```text
mapek_flow
uses_knowledge
contains
acts_through
```

The component properties panel shows code traceability, including:

```text
Code element kind
Code element ID
Qualified name
Container
```

This allows the reviewer to understand whether an architecture element comes from a function, method, class, variable, attribute, module, or package.

---

## Review workflow

Recommended human-in-the-loop workflow:

```text
1. Generate architecture proposal:
   python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm

2. Open GUI:
   python -m kdm_architecture_review.gui.main

3. Open:
   outputs/pymape_hierarchical/python_model.architecture.json

4. Review:
   - Architecture tree
   - Architecture graph
   - Components
   - Relationships
   - Validation panel
   - Code traceability

5. Export reviewed JSON:
   outputs/pymape_hierarchical/python_model.reviewed_architecture.json

6. Generate reviewed KDM:
   python kdm_pyecore_generator/main.py \
     --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
     --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

Important:

```text
Export reviewed JSON
```

produces a complete model that can be used by the KDM generator.

```text
Export review actions
```

exports only user decisions and is not a valid input for the KDM generator.

---

## Validation in the GUI

The GUI validation table shows findings, not a fixed list of all rules.

Validation runs automatically when:

```text
1. a proposal is opened;
2. a component is edited;
3. a relationship is edited;
4. the user presses Validate.
```

Validation levels:

```text
OK        valid construction or accepted decision
WARNING   review recommended
FORBIDDEN blocking consistency issue
```

Common warnings:

```text
ARV-W-04  Same code element implements multiple architecture roles.
ARV-W-01  Control loop is partial, for example missing Analyzer.
CTRL-W01  No Reference Input was recovered.
CTRL-W02  No Measured Output was recovered.
CTRL-W03  No Sensor was recovered.
```

A warning does not necessarily mean the architecture is incorrect. It indicates that the user should review the finding.

---

## Example KDM verification

After generating KDM, check stereotypes:

```bash
grep -n "extensionFamily\|Adaptive System Domain" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -40
```

Check architecture elements:

```bash
grep -n "Managing Subsystem\|Managed Subsystem\|Control Loop\|speed_executor\|speed_monitor" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -100
```

Check architecture relationships:

```bash
grep -n "contains\|mapek_flow\|uses_knowledge\|acts_through" \
  outputs/pymape_hierarchical/model.kdm.xmi | head -120
```

---

## Documentation

The documentation is generated with MkDocs.

Run:

```bash
mkdocs serve
```

Open:

```text
http://127.0.0.1:8000
```

Recommended navigation structure:

```yaml
nav:
  - Home: index.md
  - Architecture: architecture.md
  - Pipeline Configuration: pipeline_configuration.md
  - Python Extractor: python_extractor.md
  - Intermediate JSON Model: intermediate_json_model.md
  - Architecture Recovery:
      - Overview: architecture_recovery.md
      - MAPE-K Recovery Rules: mapek_recovery_rules.md
      - Structure Model Mapping: structure_model_mapping.md
      - KDM Traceability Links: kdm_traceability_links.md
      - Architecture Review GUI: architecture_review_gui.md
  - KDM Generation:
      - JSON to KDM Mapping: json_to_kdm_mapping.md
      - Validation Rules: validation_rules.md
  - Usage:
      - CLI Usage: cli_usage.md
      - Examples and Case Studies: examples.md
  - Development:
      - Development Guide: development_guide.md
      - Testing Strategy: testing_strategy.md
      - Limitations: limitations.md
```

---

## Regression checklist

Before considering a version stable, run:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
python -m kdm_architecture_review.gui.main
mkdocs serve
```

Check:

```text
✓ KDM validation report has no errors.
✓ Architecture JSON contains structure_model.
✓ KDM contains extensionFamily.
✓ KDM contains StructureModel.
✓ GUI opens the architecture JSON.
✓ GUI validation has no false forbidden findings.
✓ GUI exports reviewed JSON.
✓ Reviewed KDM is generated successfully.
✓ MkDocs renders all pages.
```

---

## Limitations

The current version is static-analysis based. It does not fully resolve all dynamic Python behavior, such as:

- dynamic imports;
- monkey patching;
- reflection;
- runtime-generated attributes;
- dependency injection patterns without static evidence.

Architecture recovery is conservative. It does not create `Reference Input`, `Measured Output`, or `Sensor` unless explicit evidence exists.

The GUI node positions are visual only and are not persisted in the reviewed JSON.

---

## Future work

Possible next steps include:

- persistent GUI layout positions;
- DSL-based architecture review;
- stronger review action reapplication;
- integration of AI-based pre-enrichment and post-review suggestions;
- richer dynamic-analysis support;
- multi-language extraction;
- model-to-model transformations from KDM to additional architecture viewpoints.
