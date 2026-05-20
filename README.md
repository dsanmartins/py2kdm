# py2kdm

`py2kdm` is a configurable Python-to-KDM 1.4 toolchain for reverse engineering Python projects into KDM/EMF-compatible models.

The project supports two complementary levels of recovery:

1. **Code-level recovery**, where Python source code is transformed into an intermediate JSON model and then into KDM `CodeModel`, `InventoryModel`, action elements and code relations.
2. **Architecture-level recovery**, where candidate self-adaptive architectures are inferred from the intermediate JSON model and represented as a KDM `StructureModel` with Adaptive System Domain stereotypes.

The toolchain supports Architecture-Driven Modernization, model-driven analysis, architectural recovery, KDM-based transformation workflows, human-in-the-loop review, and traceable modernization experiments.

---

## Current status

The current version supports an end-to-end workflow with deterministic architecture agents and human review:

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
Pre-review architecture agents
   ↓
AI-enriched architecture JSON
   ↓
Architecture Review GUI
   ↓
Reviewed architecture JSON
   ↓
Post-review architecture agents
   ↓
AI-checked reviewed JSON
   ↓
kdm_pyecore_generator
   ↓
KDM 1.4 XMI model
```

Implemented capabilities:

```text
✓ Python static extraction
✓ Intermediate JSON model
✓ MAPE-K architecture recovery
✓ Adaptive System Domain stereotypes
✓ KDM StructureModel generation
✓ Nested architectural containment
✓ KDM traceability links
✓ Deterministic pre-review architecture agents
✓ Deterministic post-review architecture agents
✓ Human-in-the-loop Architecture Review GUI
✓ AI Suggestions tab in the GUI
✓ Reviewed JSON export
✓ Reviewed KDM generation
✓ MkDocs documentation
✓ Root-level execution of all main entry points
```

---

## Project structure

```text
py2kdm/
├── run_pipeline.py
├── py2kdm_common/
│   └── shared path utilities
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
├── kdm_architecture_agents/
│   ├── pre_review/
│   └── post_review/
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

The standard automated pipeline is:

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

To run architecture recovery plus pre-review agents:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --skip-kdm
```

Expected outputs:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/python_model.architecture.json
outputs/pymape_hierarchical/python_model.ai_architecture.json
outputs/pymape_hierarchical/model.kdm.xmi
```

---

## Root-level execution

All main entry points are intended to run from the `py2kdm` root.

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

```bash
python kdm_architecture_recovery/main.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --output outputs/pymape_hierarchical/python_model.architecture.json
```

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/python_model.ai_architecture.json
```

```bash
python -m kdm_architecture_review.gui.main
```

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
  --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

The common path utilities are provided by:

```text
py2kdm_common/paths.py
```

---

## Python extraction

The extractor scans Python projects and produces a normalized JSON representation containing:

```text
source files
imports
classes
methods and functions
parameters
local variables
global variables
instance attributes
calls and constructor calls
assignments
reads and writes
returns and raises
try / except / finally blocks
body-level statements
internal relationships
symbol-table information
```

Direct execution:

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

Backward-compatible positional execution is also supported:

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

Architecture recovery is evidence-driven. It does not create all possible autonomic abstractions by default. For example:

```text
Effector         evidence such as brake, gas, siren, hazard_lights
Sensor           evidence such as sensor, read, measure, observe
Measured Output  evidence such as current_speed, measured_distance, actual_temperature
Reference Input  evidence such as target_speed, desired_distance, setpoint, goal, threshold
```

Direct execution:

```bash
python kdm_architecture_recovery/main.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --output outputs/pymape_hierarchical/python_model.architecture.json
```

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

The architecture is not generated first and validated afterwards. The recovery process applies semantic construction rules during architecture construction.

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

This section is a construction report.

---

## Managed interaction recovery

The recovery module can infer candidate interactions between managing-side and managed-side abstractions.

Examples:

```text
Executor -> Effector                 acts_through
Monitor  -> Sensor                   observes_through
Monitor  -> Measured Output          observes
Sensor   -> Measured Output          produces_measurement
Analyzer/Planner -> Reference Input  uses_reference_input
Analyzer/Planner -> Measured Output  evaluates_measured_output
```

These relations are generated only when there is meaningful name or implementation evidence.

Example:

```text
gas_brake <<Executor>> --acts_through--> gas   <<Effector>>
gas_brake <<Executor>> --acts_through--> brake <<Effector>>
```

---

## Architecture agents

`py2kdm` includes an initial architecture-agent layer:

```text
kdm_architecture_agents/
```

The current agents are deterministic Python modules. They are **not LLM-based yet** and do not use an external agent framework. They generate structured suggestions and findings in the architecture JSON.

### Agent package structure

```text
kdm_architecture_agents/
├── __init__.py
├── main.py
├── agent_context_builder.py
├── ai_suggestion_model.py
│
├── pre_review/
│   ├── __init__.py
│   ├── architecture_enrichment_agent.py
│   ├── dynamic_evidence_agent.py
│   └── prompts/
│       └── pre_enrichment.md
│
└── post_review/
    ├── __init__.py
    ├── kdm_readiness_agent.py
    ├── review_consistency_agent.py
    └── prompts/
        └── post_review.md
```

### Pre-review agents

Pre-review agents run after rule-based architecture recovery and before human review.

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/python_model.ai_architecture.json
```

They add:

```json
"ai_enrichment": {
  "status": "pre_review_enriched",
  "suggestions": [],
  "summary": {}
}
```

Current pre-review agents:

```text
DynamicEvidenceAgent
ArchitectureEnrichmentAgent
```

They suggest:

```text
missing ReferenceInput
missing MeasuredOutput
missing Sensor
possible role disambiguation
partial control loop interpretation
optional dynamic relations from a trace
```

### Optional dynamic trace

The `DynamicEvidenceAgent` can consume a dynamic trace JSON:

```json
{
  "events": [
    {
      "type": "call",
      "source": "function:pymape_hierarchical.control.gas_brake",
      "target": "method:pymape_hierarchical.fixtures.VirtualCarSpeed.brake",
      "scenario": "cruise_control_test"
    }
  ]
}
```

Usage:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --dynamic-trace outputs/pymape_hierarchical/runtime_trace.json \
  --skip-kdm
```

### Post-review agents

Post-review agents run after the user exports the reviewed JSON from the GUI.

```bash
python kdm_architecture_agents/main.py \
  --mode post-review \
  --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json
```

They add:

```json
"post_review_ai_check": {
  "summary": {
    "kdm_ready": true
  },
  "findings": []
}
```

Current post-review agents:

```text
ReviewConsistencyAgent
KDMReadinessAgent
```

They check:

```text
Executor without Effector
Monitor without Sensor or MeasuredOutput
Knowledge without uses_knowledge
materialized relationships with missing endpoints
required top-level JSON fields
valid roles
valid relationship types
KDM readiness
```

---

## Architecture Review GUI

The Architecture Review GUI provides a human-in-the-loop review layer between automatic architecture recovery and final KDM generation.

Start the GUI:

```bash
python -m kdm_architecture_review.gui.main
```

Open:

```text
outputs/pymape_hierarchical/python_model.ai_architecture.json
```

or, without agents:

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
✓ AI Suggestions tab
✓ Reviewed JSON export
✓ Review actions export
```

The `AI Suggestions` tab reads:

```json
.ai_enrichment.suggestions
.post_review_ai_check.findings
```

and displays:

```text
Phase | Type | Severity | Confidence | Status | Message
```

The panel is read-only. AI suggestions are not applied automatically.

---

## Review workflow

Recommended human-in-the-loop workflow:

```text
1. Run pipeline with pre-review agents.

2. Open AI-enriched architecture JSON in the GUI.

3. Review:
   - Architecture tree
   - Architecture graph
   - Components
   - Relationships
   - Validation panel
   - AI Suggestions

4. Export reviewed JSON.

5. Run post-review agents.

6. If kdm_ready is true, generate KDM.
```

Commands:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --skip-kdm
```

```bash
python -m kdm_architecture_review.gui.main
```

Export from the GUI as:

```text
outputs/pymape_hierarchical/python_model.reviewed_architecture.json
```

Then run:

```bash
python kdm_architecture_agents/main.py \
  --mode post-review \
  --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json
```

Finally:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
  --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

---

## KDM generation

The KDM generator creates a KDM 1.4 XMI model using PyEcore.

It supports:

```text
InventoryModel and SourceFile
CodeModel
CompilationUnit
ClassUnit
MethodUnit
CallableUnit
ParameterUnit
StorableUnit
BlockUnit
TryUnit
CatchUnit
FinallyUnit
body-level ActionElement nodes
Calls, Creates, Reads, Writes
HasType, HasValue
Imports, Extends
Throws, ExceptionFlow, ExitFlow
optional architecture StructureModel
Adaptive System Domain extensionFamily
StructureRelationship
AggregatedRelationship
architecture implementation links
```

Direct execution:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.kdm.xmi
```

Reviewed execution:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
  --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

If needed, the metamodel can be passed explicitly:

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
  --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi \
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

## Validation in the GUI

The GUI validation table shows findings, not a fixed list of all available rules.

Validation runs automatically when:

```text
a proposal is opened
a component is edited
a relationship is edited
the user presses Validate
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
  outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -40
```

Check architecture elements:

```bash
grep -n "Managing Subsystem\|Managed Subsystem\|Control Loop\|speed_executor\|speed_monitor" \
  outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -100
```

Check architecture relationships:

```bash
grep -n "contains\|mapek_flow\|uses_knowledge\|acts_through" \
  outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -120
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
      - Architecture Agents: architecture_agents.md
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
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --skip-kdm

python -m kdm_architecture_review.gui.main

python kdm_architecture_agents/main.py \
  --mode post-review \
  --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json

python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
  --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi

mkdocs serve
```

Check:

```text
✓ Extractor runs from root.
✓ Architecture recovery runs from root.
✓ Pre-review agents run from root.
✓ GUI opens AI-enriched architecture JSON.
✓ GUI displays AI Suggestions.
✓ GUI validation has no false forbidden findings.
✓ GUI exports reviewed JSON.
✓ Post-review agents report kdm_ready = true.
✓ Reviewed KDM is generated successfully.
✓ KDM contains extensionFamily.
✓ KDM contains StructureModel.
✓ MkDocs renders all pages.
```

---

## Limitations

The current version is static-analysis based. It does not fully resolve all dynamic Python behavior, such as:

```text
dynamic imports
monkey patching
reflection
runtime-generated attributes
dependency injection patterns without static evidence
```

Architecture recovery is conservative. It does not create `Reference Input`, `Measured Output`, or `Sensor` unless explicit evidence exists.

The current architecture agents are deterministic and rule-based. They are not LLM-based yet.

The GUI node positions are visual only and are not persisted in the reviewed JSON.

---

## Future work

Possible next steps include:

```text
persistent GUI layout positions
GUI accept/reject workflow for AI suggestions
dynamic instrumentation for runtime traces
LLM-based architecture reasoning agent
schema validation for LLM outputs
integration of AI pre-enrichment and post-review suggestions in a global desktop app
richer dynamic-analysis support
multi-language extraction
model-to-model transformations from KDM to additional architecture viewpoints
```
