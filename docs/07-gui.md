# 7. Graphical User Interface

The `py2kdm_gui` subproject provides a desktop workbench for executing the main py2kdm workflow, inspecting generated artifacts, and optionally reviewing recovered architecture models before generating a final KDM model.

The GUI does not replace the command-line pipeline. Instead, it offers a structured interface over the same backend modules:

```text
static extraction
dynamic analysis
architecture recovery
KDM generation
pre-review agents
human review
artifact inspection
```

## 7.1 Purpose of the GUI

The GUI is intended for users who need to:

- configure a Python or Java project without writing command-line arguments manually;
- execute the main reverse-engineering pipeline step by step;
- inspect intermediate and final artifacts;
- review recovered architectural components and relationships;
- run deterministic or LLM-assisted pre-review agents;
- generate both automatic and reviewed KDM models.

The GUI is especially useful for demonstrations, validation sessions, and human-in-the-loop architecture recovery.

## 7.2 Starting the GUI

From the project root:

```bash
python -m py2kdm_gui.main
```

The GUI assumes that the same environment used for the command-line pipeline is active. For example:

```bash
source /path/to/venv/bin/activate
python -m py2kdm_gui.main
```

If Gemini is used in the pre-review agents, the environment must contain either:

```bash
GEMINI_API_KEY=...
```

or:

```bash
GOOGLE_API_KEY=...
```

The key may also be stored in a `.env` file at the root of the py2kdm project.

## 7.3 Main tabs

The GUI is organized into four main tabs.

```text
Configuration
Process
Human Review
Artifacts
```

Each tab has a distinct responsibility.

## 7.4 Configuration tab

The **Configuration** tab defines the project setup.

It contains:

```text
Project root
Output directory
Project name
Source language
Config file
Dynamic analysis scenarios
Pre-review agent settings
Validate setup
```

### Project setup

The project setup section defines:

| Field | Meaning |
|---|---|
| Project root | Root directory of the target project to analyze. |
| Output directory | Directory where JSON, trace, KDM, and log artifacts are generated. |
| Project name | Logical name of the analyzed project. |
| Source language | `Python`, `Java`, or `Auto-detect`. |
| Config file | Optional JSON configuration file loaded or saved by the GUI. |

For Java projects, dynamic trace enrichment is disabled. Java projects use static KDM-based architecture recovery.

### Dynamic analysis scenarios

Dynamic analysis is available for Python projects. Scenarios define executable scripts that generate runtime traces.

Each scenario has:

| Field | Meaning |
|---|---|
| Enabled | Whether the scenario will be executed. |
| Name | Scenario identifier. |
| Script | Python script to execute. |
| Mode | Execution mode, for example desktop/headless depending on the project. |

### Pre-review agent settings

The GUI exposes the same LLM settings used by the command-line agents:

| Field | Meaning |
|---|---|
| LLM provider | `none`, `gemini`, or `ollama`. |
| LLM model | Model name, for example `gemini-2.5-flash-lite`. |
| LLM timeout | Timeout in seconds. |
| Gemini key | Displays whether a Gemini API key is available. |

### Validate setup

The **Validate setup** button checks whether the selected project configuration is coherent.

It verifies, among other things:

```text
project root exists
output directory is valid
language is known or detectable
dynamic scenarios are valid
LLM provider/key settings are coherent
```

This validation belongs in the Configuration tab because it checks the project setup before executing the pipeline.

## 7.5 Process tab

The **Process** tab contains the main automatic workflow.

It intentionally contains only the principal pipeline steps:

```text
1. Static extraction
2. Dynamic analysis (Python)
3. Architecture recovery
4. Generate KDM
```

### 1. Static extraction

For Python projects, this runs the static extractor and generates:

```text
python_model.json
```

For Java projects, it runs the Java extraction path and generates:

```text
java_model.json
```

These files are the intermediate code models used by later stages.

### 2. Dynamic analysis (Python)

This step is available only for Python projects.

It executes enabled scenarios and produces runtime traces and, when applicable, a runtime-enriched model:

```text
runtime_trace.<scenario>.json
python_model.runtime_enriched.combined.json
```

For Java projects, this step is disabled.

### 3. Architecture recovery

This step runs the deterministic architecture recovery module.

Typical outputs are:

```text
python_model.architecture.json
java_model.architecture.json
```

or, when dynamic analysis is active:

```text
python_model.runtime_enriched.architecture.json
```

These files contain the recovered `structure_model`.

### 4. Generate KDM

This step generates the automatic architecture-enriched KDM:

```text
model.structure.kdm.xmi
```

It uses the deterministic architecture JSON as input.

The generated KDM may contain:

```text
InventoryModel
CodeModel
Action elements
StructureModel
Adaptive System Domain
Components
Subsystems
StructureRelationships
AggregatedRelationships
implementation links to CodeModel elements
```

This is the main automatic KDM artifact of the system.

## 7.6 Human Review tab

The **Human Review** tab contains the optional human-in-the-loop workflow.

It is separate from the Process tab because human review is not required for the automatic pipeline.

The main buttons are:

```text
Load for review
Pre-review agents
Validate
Export reviewed JSON
Generate reviewed KDM
Export review actions
Open proposal file
```

### Load for review

Loads the current architecture proposal into the review interface.

The GUI selects the input in this order:

```text
*.ai_architecture.json
*.architecture.json
```

Thus, if pre-review agents have already been executed, the GUI loads the AI-enriched architecture file. Otherwise, it loads the deterministic architecture recovery output.

If a model is already loaded, the GUI asks whether it should be replaced.

### Pre-review agents

Runs the pre-review agents and then loads the resulting AI architecture model.

This step calls the architecture agents using:

```text
architecture_json as input
ai_architecture_json as output
intermediate_json or runtime_enriched_json as code_context_input
```

The `code_context_input` is important because it allows deterministic code review and LLM suggestions to be grounded in compact code evidence.

While this step is running, the Human Review buttons are disabled and an activity indicator is shown.

### Validate

Validates the current reviewed architecture model.

Validation is required before exporting the reviewed architecture JSON.

### Export reviewed JSON

Exports the reviewed architecture model, typically as:

```text
python_model.reviewed_architecture.json
java_model.reviewed_architecture.json
```

This file contains the architecture model after human decisions and modifications.

### Generate reviewed KDM

Generates:

```text
model.reviewed.kdm.xmi
```

from:

```text
*.reviewed_architecture.json
```

This artifact represents the human-reviewed KDM model.

### Export review actions

Exports only the human review decisions and overrides, without exporting the full architecture model.

This is useful for auditing or reproducing review decisions.

### Open proposal file

Allows the user to manually select an architecture proposal JSON file.

This is useful when reviewing a proposal generated outside the current output directory.

## 7.7 Review views

The Human Review tab includes several views.

### Components

Lists recovered architecture components and their assigned roles.

Examples of roles include:

```text
Monitor
Analyzer
Planner
Executor
Knowledge
LoopManager
Sensor
Effector
```

### Relationships

Lists recovered architecture relationships.

These may include relationships among MAPE-K roles, components, subsystems, and control loops.

### AI Suggestions

Shows suggestions generated by deterministic and/or LLM-assisted pre-review.

The user may accept, reject, or mark suggestions as reviewed.

### Graph View

Displays the recovered architecture as a graph.

This view helps identify the recovered MAPE-K structure and relationships among components.

### Properties Panel

Shows and edits details of the selected component or relationship.

### Validation Panel

Shows validation findings for the current reviewed architecture.

### Traceability Panel

Shows traceability from architectural components to code elements, when available.

For example:

```text
Component: pid
Role: Planner
Implemented by: function:pymape_hierarchical.hierarchical-cruise-control.pid
```

## 7.8 Artifacts tab

The **Artifacts** tab is the central place for inspecting generated files.

It lists artifacts such as:

```text
python_model.json
java_model.json
*.architecture.json
*.ai_architecture.json
*.reviewed_architecture.json
model.structure.kdm.xmi
model.reviewed.kdm.xmi
runtime_trace.<scenario>.json
```

For JSON artifacts, the tab summarizes:

```text
top-level keys
metadata
static model counts
runtime enrichment
architecture model counts
AI enrichment
human review data
```

For XMI artifacts, it summarizes:

```text
StructureModel present
Adaptive System Domain present
number of structure:Component elements
number of structure:Subsystem elements
number of structure:StructureRelationship elements
number of aggregatedRelation elements
number of implementation links
```

The Process tab does not show artifact summaries. Artifact inspection is centralized here.

## 7.9 Recommended GUI workflows

### Automatic architecture-enriched KDM

Use this workflow when no human review is needed:

```text
Configuration
  Validate setup

Process
  1. Static extraction
  2. Dynamic analysis (Python), if needed
  3. Architecture recovery
  4. Generate KDM

Artifacts
  Inspect model.structure.kdm.xmi
```

Main output:

```text
model.structure.kdm.xmi
```

### Human-in-the-loop reviewed KDM

Use this workflow when the recovered architecture needs inspection or correction:

```text
Configuration
  Validate setup

Process
  1. Static extraction
  2. Dynamic analysis (Python), if needed
  3. Architecture recovery

Human Review
  Pre-review agents, optional
  Load for review
  Validate
  Export reviewed JSON
  Generate reviewed KDM

Artifacts
  Inspect model.reviewed.kdm.xmi
```

Main outputs:

```text
*.reviewed_architecture.json
model.reviewed.kdm.xmi
```

## 7.10 Relationship with the command-line pipeline

The GUI calls the same backend modules used by the command-line workflow.

For reproducibility, every GUI action corresponds to a command-line step:

| GUI step | Backend module |
|---|---|
| Static extraction | Python extractor or Java extractor |
| Dynamic analysis | `kdm_dynamic_analysis` |
| Architecture recovery | `kdm_architecture_recovery` |
| Pre-review agents | `kdm_architecture_agents` |
| Generate KDM | `kdm_pyecore_generator` |
| Generate reviewed KDM | `kdm_pyecore_generator` |

Therefore, the GUI should be understood as an orchestration and inspection layer, not as a separate analysis engine.

## 7.11 Notes for demonstrations

For a demonstration, the recommended sequence is:

```text
1. Load a project configuration.
2. Validate setup.
3. Run the four Process steps.
4. Open Artifacts and inspect model.structure.kdm.xmi.
5. Go to Human Review.
6. Run Pre-review agents.
7. Inspect components, relationships, graph, suggestions, and traceability.
8. Export reviewed JSON.
9. Generate reviewed KDM.
10. Inspect model.reviewed.kdm.xmi in Artifacts.
```

This demonstrates both the automatic recovery workflow and the optional human-in-the-loop workflow.
