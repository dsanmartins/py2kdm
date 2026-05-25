# py2kdm

`py2kdm` is a configurable Python-to-KDM 1.4 toolchain for reverse engineering Python projects into KDM/EMF-compatible models.

The toolchain supports two complementary recovery levels:

1. **Code-level recovery**, where Python source code is transformed into an intermediate JSON model and then into KDM `CodeModel`, `InventoryModel`, action elements, source references and semantic code relations.
2. **Architecture-level recovery**, where candidate self-adaptive architectures are inferred from the intermediate JSON model and represented as a KDM `StructureModel` with Adaptive System Domain stereotypes.

`py2kdm` supports Architecture-Driven Modernization, model-driven analysis, architectural recovery, KDM-based transformation workflows, human-in-the-loop review, runtime-informed analysis, and traceable modernization experiments.

---

## Current status

The current version supports an end-to-end pipeline with optional dynamic analysis, pre-review architecture agents, human review, and final KDM generation.

```text
1. Project selection
   1.1 Select the input Python project.
   1.2 Define or load the pipeline configuration.
   1.3 Define the output directory.

2. Reverse engineering
   2.1 Run the static extractor.
       Output:
         python_model.json

   2.2 Optionally run dynamic analysis scenarios.
       Output:
         runtime_trace.<scenario>.json
         python_model.runtime_enriched.combined.json

   2.3 Run architecture recovery.
       Input:
         python_model.json
         or python_model.runtime_enriched.combined.json
       Output:
         python_model.architecture.json
         or python_model.runtime_enriched.architecture.json

   2.4 Run pre-review architecture agents.
       Output:
         AI-enriched architecture JSON

3. Human architecture review
   3.1 Open the enriched architecture proposal in the GUI.
   3.2 Accept, reject or manually incorporate suggestions.
   3.3 Export the reviewed architecture JSON.

4. Final KDM generation
   4.1 Run the KDM generator.
       Input:
         python_model.reviewed_architecture.json
       Output:
         model.reviewed.kdm.xmi
```

After human review, the reviewed architecture is treated as authoritative. No additional AI agent modifies or reinterprets the model before final KDM generation.

Implemented capabilities:

```text
✓ Python static extraction
✓ Intermediate JSON model
✓ Optional runtime tracing with sys.setprofile
✓ Dynamic CodeModel enrichment from runtime calls
✓ Runtime calls mapped to native KDM action::Calls relations
✓ Runtime-aware static validation reporting
✓ MAPE-K architecture recovery
✓ Adaptive System Domain stereotypes
✓ KDM StructureModel generation
✓ Nested architectural containment
✓ KDM traceability links
✓ Pre-review architecture agents
✓ Optional LLM-assisted architecture suggestions
✓ Gemini and Ollama provider support
✓ Human-in-the-loop Architecture Review GUI
✓ AI Suggestions tab in the GUI
✓ Reviewed JSON export
✓ Final KDM generation
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
│   └── example Python systems and optional runtime scenarios
├── outputs/
│   └── generated JSON, runtime traces and KDM XMI artifacts
├── python_kdm_extractor/
│   └── Python source code → intermediate JSON model
├── kdm_dynamic_analysis/
│   └── runtime tracing and CodeModel enrichment
├── kdm_architecture_recovery/
│   └── intermediate JSON → architecture-enriched JSON
├── kdm_architecture_agents/
│   ├── pre_review/
│   ├── llm/
│   ├── agent_context_builder.py
│   ├── ai_suggestion_model.py
│   ├── suggestion_deduplicator.py
│   └── main.py
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
python run_pipeline.py   --config configs/pymape_hierarchical.json   --skip-kdm
```

To run architecture recovery plus pre-review agents:

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --with-agents pre-review   --skip-kdm
```

To run the generic dynamic-analysis pipeline:

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --enable-dynamic-analysis   --dynamic-project-root examples/pymape_hierarchical   --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py   --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py
```

Expected outputs include:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/runtime_trace.cruise_control.json
outputs/pymape_hierarchical/runtime_trace.hold_distance.json
outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json
outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json
outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi
```

The dynamic pipeline is generic. It does not hardcode project-specific scenarios. Runtime scenarios are provided through CLI arguments or configuration files.

---

## Root-level execution

All main entry points are intended to run from the `py2kdm` root.

```bash
python python_kdm_extractor/main.py   --input examples/pymape_hierarchical   --output outputs/pymape_hierarchical/python_model.json
```

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich   --project-root examples/pymape_hierarchical   --script scenarios/cruise_control_scenario.py   --input outputs/pymape_hierarchical/python_model.json   --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json   --scenario cruise_control   --mode desktop
```

```bash
python kdm_architecture_recovery/main.py   --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
```

```bash
python kdm_architecture_agents/main.py   --mode pre-review   --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json   --llm-provider none
```

```bash
python -m kdm_architecture_review.gui.main
```

```bash
python kdm_pyecore_generator/main.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
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
python python_kdm_extractor/main.py   --input examples/pymape_hierarchical   --output outputs/pymape_hierarchical/python_model.json
```

---

## Dynamic analysis

Dynamic analysis is optional. It enriches the CodeModel with factual runtime evidence collected from execution traces.

The runtime tracer uses `sys.setprofile` to observe:

```text
function calls
returns
exceptions
runtime argument types
runtime return types
scenario names
```

The dynamic enrichment phase adds runtime relationships to the JSON model:

```json
{
  "type": "runtime_calls",
  "source": "source.qualified.name",
  "target": "target.qualified.name",
  "relationship_level": "code",
  "source_level": "runtime",
  "evidence": "dynamic_trace",
  "scenario": "cruise_control"
}
```

During KDM generation, these runtime facts are mapped to native KDM semantic relations:

```text
runtime_calls -> action::Calls
```

They are not represented as `TaggedValue` entries.

Example:

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich   --project-root examples/pymape_hierarchical   --script scenarios/cruise_control_scenario.py   --input outputs/pymape_hierarchical/python_model.json   --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json   --scenario cruise_control   --mode desktop
```

Multiple scenarios can be combined by enriching sequentially:

```bash
python kdm_dynamic_analysis/main.py enrich   --input outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json   --trace outputs/pymape_hierarchical/runtime_trace.hold_distance.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json
```

---

## Architecture recovery

The architecture recovery module identifies candidate self-adaptive architecture abstractions from the intermediate or runtime-enriched JSON model.

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
python kdm_architecture_recovery/main.py   --input outputs/pymape_hierarchical/python_model.runtime_enriched.combined.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
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

Runtime evidence can also support architectural interaction suggestions before human review.

---

## Architecture agents

`py2kdm` includes a pre-review architecture-agent layer:

```text
kdm_architecture_agents/
```

Agents generate structured suggestions in the architecture JSON. They do not modify `structure_model` directly. Suggestions are intended for human review.

### Agent package structure

```text
kdm_architecture_agents/
├── __init__.py
├── main.py
├── agent_context_builder.py
├── ai_suggestion_model.py
├── suggestion_deduplicator.py
│
├── llm/
│   ├── gemini_provider.py
│   ├── ollama_provider.py
│   ├── null_provider.py
│   ├── provider_factory.py
│   └── schema_guard.py
│
└── pre_review/
    ├── architecture_enrichment_agent.py
    ├── dynamic_evidence_agent.py
    ├── llm_architecture_reasoning_agent.py
    └── prompts/
```

### Pre-review agents

Pre-review agents run after rule-based architecture recovery and before human review.

```bash
python kdm_architecture_agents/main.py   --mode pre-review   --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json   --llm-provider none
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
LLMArchitectureReasoningAgent
```

They can suggest:

```text
missing ReferenceInput
missing MeasuredOutput
missing Sensor
possible role disambiguation
partial control loop interpretation
architecture-level relations supported by runtime evidence
LLM-assisted reviewable architecture improvements
```

### Runtime-aware suggestions

When the input model contains:

```text
relationships[type="runtime_calls"]
runtime_enrichment.summary
```

the agents use this evidence to create reviewable architecture suggestions. For example:

```text
Runtime evidence suggests gas_brake --acts_through--> gas.
Runtime evidence suggests gas_brake --acts_through--> brake.
```

These are suggestions over the `StructureModel`, not automatic modifications.

### LLM providers

The architecture-agent layer supports:

```text
none
ollama
gemini
```

Example with Gemini:

```bash
python kdm_architecture_agents/main.py   --mode pre-review   --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json   --llm-provider gemini   --llm-model gemini-2.5-flash-lite
```

The Gemini provider reads the key from environment variables:

```bash
GEMINI_API_KEY
```

or:

```bash
GOOGLE_API_KEY
```

For local development, create `.env` in the project root:

```bash
GEMINI_API_KEY=your_key_here
```

If `python-dotenv` is installed, `kdm_architecture_agents/main.py` can load `.env` automatically:

```bash
pip install python-dotenv
```

Ensure `.env` is ignored by Git:

```bash
grep -qxF '.env' .gitignore || echo '.env' >> .gitignore
```

### Suggestion deduplication

The pre-review pipeline deduplicates semantically equivalent suggestions. When deterministic and LLM-based agents report the same issue, the deterministic suggestion is kept as primary, and the LLM suggestion is merged into metadata as supporting information.

Example:

```json
"summary": {
  "raw_suggestions": 7,
  "deduplicated_suggestions": 1,
  "suggestions": 6
}
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
outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json
```

or, without agents:

```text
outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json
```

The GUI supports:

```text
✓ Architecture tree view
✓ Architecture graph view
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
```

The panel is read-only. AI suggestions are not applied automatically.

---

## Review workflow

Recommended human-in-the-loop workflow:

```text
1. Run extraction, optional dynamic analysis, architecture recovery and pre-review agents.
2. Open AI-enriched architecture JSON in the GUI.
3. Review architecture, relationships, validation and AI suggestions.
4. Accept, reject or manually incorporate suggestions.
5. Export reviewed architecture JSON.
6. Generate the final KDM model directly from the reviewed JSON.
```

Commands:

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --enable-dynamic-analysis   --dynamic-project-root examples/pymape_hierarchical   --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py   --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py   --with-agents pre-review   --skip-kdm
```

```bash
python -m kdm_architecture_review.gui.main
```

Export from the GUI as:

```text
outputs/pymape_hierarchical/python_model.reviewed_architecture.json
```

Then generate the final KDM:

```bash
python kdm_pyecore_generator/main.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

After human review, no additional AI agent modifies or reinterprets the reviewed architecture.

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
runtime_calls mapped to action::Calls
optional architecture StructureModel
Adaptive System Domain extensionFamily
StructureRelationship
AggregatedRelationship
architecture implementation links
```

Direct execution:

```bash
python kdm_pyecore_generator/main.py   --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json   --output outputs/pymape_hierarchical/model.runtime_enriched.kdm.xmi
```

Reviewed execution:

```bash
python kdm_pyecore_generator/main.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
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
grep -n "extensionFamily\|Adaptive System Domain"   outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -40
```

Check architecture elements:

```bash
grep -n "Managing Subsystem\|Managed Subsystem\|Control Loop\|speed_executor\|speed_monitor"   outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -100
```

Check architecture relationships:

```bash
grep -n "contains\|mapek_flow\|uses_knowledge\|acts_through"   outputs/pymape_hierarchical/model.reviewed.kdm.xmi | head -120
```

Check dynamic runtime calls mapped to KDM:

```bash
grep -c 'runtime_call:'   outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi
```

```bash
grep -c 'xsi:type="action:Calls"'   outputs/pymape_hierarchical/model.runtime_enriched.combined.kdm.xmi
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

The documentation source is in:

```text
docs/
mkdocs.yml
```

---

## Regression checklist

Before considering a version stable, run:

```bash
python run_pipeline.py   --config configs/pymape_hierarchical.json   --enable-dynamic-analysis   --dynamic-project-root examples/pymape_hierarchical   --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py   --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py   --with-agents pre-review   --skip-kdm

python -m kdm_architecture_review.gui.main

python kdm_pyecore_generator/main.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi

mkdocs serve
```

Check:

```text
✓ Extractor runs from root.
✓ Dynamic scenarios run from root.
✓ Runtime traces are generated.
✓ Runtime-enriched JSON is generated.
✓ Architecture recovery runs over runtime-enriched JSON.
✓ Pre-review agents run from root.
✓ LLM suggestions are optional and reviewable.
✓ Duplicate deterministic/LLM suggestions are consolidated.
✓ GUI opens AI-enriched architecture JSON.
✓ GUI displays AI Suggestions.
✓ GUI exports reviewed JSON.
✓ Reviewed KDM is generated successfully.
✓ KDM contains extensionFamily.
✓ KDM contains StructureModel.
✓ KDM contains runtime-derived action::Calls when dynamic analysis is enabled.
✓ MkDocs renders all pages.
```

---

## Limitations

Dynamic analysis is scenario dependent. It only observes behavior executed by the provided runtime scenarios.

Architecture recovery is conservative. It does not create `Reference Input`, `Measured Output`, or `Sensor` unless explicit evidence exists.

LLM-assisted suggestions are optional, reviewable and non-authoritative. They do not modify the `StructureModel` directly.

The GUI node positions are visual only and are not persisted in the reviewed JSON.

---

## Future work

Possible next steps include:

```text
persistent GUI layout positions
GUI accept/reject workflow for AI suggestions
richer dynamic-analysis support
web runtime tracing scenarios
multi-language extraction
schema validation for reviewed architecture artifacts
model-to-model transformations from KDM to additional architecture viewpoints
```
