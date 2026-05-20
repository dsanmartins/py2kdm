# Architecture Agents

## Purpose

`kdm_architecture_agents` is the first agent layer in the `py2kdm` workflow.

The current implementation does **not** use an external LLM framework yet. The agents are deterministic Python modules that inspect the architecture JSON and generate structured suggestions or findings. This design prepares the project for future LLM-based agents while keeping the current workflow reproducible, traceable, and safe.

The agents do not modify the KDM file directly. They operate on the architecture JSON.

```text
python_model.architecture.json
        ↓
pre-review agents
        ↓
python_model.ai_architecture.json
        ↓
Architecture Review GUI
        ↓
python_model.reviewed_architecture.json
        ↓
post-review agents
        ↓
python_model.reviewed.ai_checked.json
        ↓
KDM generator
        ↓
model.reviewed.kdm.xmi
```

---

## Agent phases

The agent layer has two phases.

```text
pre_review/
  runs before human review

post_review/
  runs after human review and before KDM generation
```

The recommended package structure is:

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

---

## Shared modules

### `agent_context_builder.py`

Builds a compact context from the architecture JSON.

It indexes:

```text
components_by_role
components_by_implementation
relationships_by_endpoint
component_by_id
loop_summaries
architecture_consistency
architecture_review
```

This avoids having every agent manually traverse the raw JSON.

### `ai_suggestion_model.py`

Defines the structured output models used by the agents.

Main structures:

```text
AISuggestion
AIFinding
```

`AISuggestion` is used mainly before review.

`AIFinding` is used mainly after review.

Both are serialized as JSON dictionaries.

---

## Pre-review agents

Pre-review agents run after rule-based architecture recovery and before the user opens the GUI.

They add suggestions under:

```json
"ai_enrichment": {
  "status": "pre_review_enriched",
  "source": "kdm_architecture_agents.pre_review",
  "suggestions": [],
  "summary": {}
}
```

They should not directly modify `structure_model`. They only suggest.

### `DynamicEvidenceAgent`

This agent is prepared to consume dynamic execution traces.

In the current version, it does not automatically execute the target system. It can consume an optional dynamic trace JSON.

Expected trace shape:

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

From this, it can suggest runtime-supported relations such as:

```text
Executor -> Effector                 acts_through
Monitor  -> Sensor                   observes_through
Monitor  -> MeasuredOutput           observes
Sensor   -> MeasuredOutput           produces_measurement
Planner  -> ReferenceInput           uses_reference_input
Planner  -> MeasuredOutput           evaluates_measured_output
```

If no dynamic trace is provided, it produces an informational suggestion indicating that dynamic evidence was skipped.

### `ArchitectureEnrichmentAgent`

This agent inspects the rule-based architecture proposal and generates non-invasive suggestions.

It currently suggests:

```text
- missing ReferenceInput;
- missing MeasuredOutput;
- missing Sensor;
- role disambiguation when one code element implements several architecture roles;
- partial control loop interpretation, for example missing Analyzer.
```

Example:

```json
{
  "suggestion_type": "missing_abstraction",
  "message": "No Sensor was recovered.",
  "confidence": 0.70,
  "status": "needs_review",
  "source": "ai_assisted_enrichment",
  "severity": "warning"
}
```

---

## Post-review agents

Post-review agents run after the user exports the reviewed JSON from the GUI and before KDM generation.

They add findings under:

```json
"post_review_ai_check": {
  "status": "ready_with_warnings",
  "source": "kdm_architecture_agents.post_review",
  "findings": [],
  "summary": {
    "kdm_ready": true
  }
}
```

They should not overwrite human decisions.

### `ReviewConsistencyAgent`

Checks whether the human-reviewed architecture remains semantically coherent.

It currently checks:

```text
- Executor without Effector;
- Monitor without Sensor or MeasuredOutput;
- Knowledge without uses_knowledge;
- materialized relationships with missing endpoints.
```

Example finding:

```json
{
  "finding_type": "monitor_without_observation_abstraction",
  "severity": "warning",
  "status": "ai_warning",
  "message": "The reviewed architecture contains Monitor components but no Sensor or Measured Output."
}
```

### `KDMReadinessAgent`

Checks whether the reviewed JSON is ready to be passed to the KDM generator.

It checks:

```text
- projectName exists;
- language exists;
- files exists;
- elements exists;
- relationships exists;
- structure_model exists;
- materialized roles are valid;
- materialized relationship types are valid.
```

If a blocking issue is found, it sets:

```json
"kdm_ready": false
```

Otherwise:

```json
"kdm_ready": true
```

---

## Running pre-review agents manually

After architecture recovery:

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/python_model.ai_architecture.json
```

Check the summary:

```bash
jq '.ai_enrichment.summary' \
  outputs/pymape_hierarchical/python_model.ai_architecture.json
```

Inspect suggestions:

```bash
jq '.ai_enrichment.suggestions[] | {
  type: .suggestion_type,
  severity: .severity,
  status: .status,
  confidence: .confidence,
  message: .message
}' outputs/pymape_hierarchical/python_model.ai_architecture.json
```

---

## Running pre-review agents through the pipeline

`run_pipeline.py` supports:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --skip-kdm
```

This runs:

```text
python_kdm_extractor
        ↓
kdm_architecture_recovery
        ↓
kdm_architecture_agents --mode pre-review
```

Expected outputs:

```text
outputs/pymape_hierarchical/python_model.json
outputs/pymape_hierarchical/python_model.architecture.json
outputs/pymape_hierarchical/python_model.ai_architecture.json
```

The AI-enriched architecture JSON can then be opened in the GUI:

```bash
python -m kdm_architecture_review.gui.main
```

Open:

```text
outputs/pymape_hierarchical/python_model.ai_architecture.json
```

---

## Running with optional dynamic trace

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --with-agents pre-review \
  --dynamic-trace outputs/pymape_hierarchical/runtime_trace.json \
  --skip-kdm
```

The dynamic trace is optional. If it is omitted, the `DynamicEvidenceAgent` reports that dynamic evidence was not available.

---

## Running post-review agents manually

After exporting the reviewed JSON from the GUI:

```bash
python kdm_architecture_agents/main.py \
  --mode post-review \
  --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json
```

Check readiness:

```bash
jq '.post_review_ai_check.summary' \
  outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json
```

Inspect findings:

```bash
jq '.post_review_ai_check.findings[] | {
  type: .finding_type,
  severity: .severity,
  status: .status,
  message: .message,
  recommendation: .recommendation
}' outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json
```

If `kdm_ready` is `true`, the JSON can be passed to the KDM generator.

---

## GUI integration

The Architecture Review GUI includes an `AI Suggestions` tab.

It reads:

```json
.ai_enrichment.suggestions
.post_review_ai_check.findings
```

and displays:

```text
Phase | Type | Severity | Confidence | Status | Message
```

When a row is selected, the detail panel shows:

```text
Message
Recommendation
Affected elements
Evidence
Proposed changes
Metadata
```

The panel is read-only. It does not apply AI suggestions automatically.

---

## Important design rules

The current agents must follow these rules:

```text
1. Do not modify KDM directly.
2. Do not overwrite human review decisions.
3. Do not create auto-accepted architecture elements without strong evidence.
4. Do not invent Sensor, ReferenceInput or MeasuredOutput as explicit code evidence.
5. Use needs_review for uncertain suggestions.
6. Store all outputs in structured JSON.
7. Keep KDM generation dependent on the reviewed architecture JSON, not on raw agent suggestions.
```

---

## Are these LLM agents?

Not yet.

The current implementation is deterministic and rule-based. No external agent framework is used.

Current status:

```text
External agent framework: none
LLM calls: none
Agent package: kdm_architecture_agents
Agent type: deterministic architecture agents
```

This provides a safe scaffold for future LLM-based enrichment.

A future LLM integration could add:

```text
llm_provider.py
llm_architecture_reasoning_agent.py
schema validation for LLM outputs
prompt-based role explanation
prompt-based relationship suggestions
```

However, even with LLM integration, the LLM should only produce structured suggestions. Human review should remain the decision point.

---

## Recommended workflow

```text
1. Run the pipeline with pre-review agents.

   python run_pipeline.py \
     --config configs/pymape_hierarchical.json \
     --with-agents pre-review \
     --skip-kdm

2. Open python_model.ai_architecture.json in the GUI.

3. Review:
   - architecture tree;
   - architecture graph;
   - components;
   - relationships;
   - validation;
   - AI Suggestions.

4. Export reviewed JSON.

5. Run post-review agents.

   python kdm_architecture_agents/main.py \
     --mode post-review \
     --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json \
     --output outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json

6. If kdm_ready is true, generate KDM.

   python kdm_pyecore_generator/main.py \
     --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json \
     --output outputs/pymape_hierarchical/model.reviewed.kdm.xmi
```

---

## Recommended MkDocs entry

Add this page to `mkdocs.yml`, for example under `Architecture Recovery`:

```yaml
- Architecture Recovery:
    - Overview: architecture_recovery.md
    - MAPE-K Recovery Rules: mapek_recovery_rules.md
    - Structure Model Mapping: structure_model_mapping.md
    - KDM Traceability Links: kdm_traceability_links.md
    - Architecture Review GUI: architecture_review_gui.md
    - Architecture Agents: architecture_agents.md
```

Alternative location under `Usage`:

```yaml
- Usage:
    - CLI Usage: cli_usage.md
    - Architecture Review GUI: architecture_review_gui.md
    - Architecture Agents: architecture_agents.md
    - Examples and Case Studies: examples.md
```
