# Architecture Agents

Architecture agents run only in the pre-review phase. Their purpose is to produce reviewable suggestions for the user.

They do not modify `structure_model` directly.

## Workflow

```text
architecture recovery
  -> pre-review architecture agents
  -> human review in GUI
  -> reviewed architecture JSON
  -> final KDM generation
```

After human review, no additional AI agent modifies or reinterprets the architecture. The reviewed JSON is authoritative.

## Agent types

### DynamicEvidenceAgent

Uses runtime evidence from the model:

```text
relationships[type="runtime_calls"]
runtime_enrichment.summary
```

It can suggest architecture-level relationships such as:

```text
Executor --acts_through--> Effector
Monitor --observes--> MeasuredOutput
Sensor --produces_measurement--> MeasuredOutput
```

Example suggestion:

```json
{
  "suggestion_type": "dynamic_relation",
  "message": "Runtime evidence suggests gas_brake --acts_through--> gas.",
  "status": "needs_review",
  "proposed_changes": [
    {
      "operation": "add_relationship",
      "relationship_type": "acts_through",
      "source": "component:gas_brake_executor_control_gas_brake",
      "target": "component:gas_effector_pymape_hierarchical_fixtures_virtualcarspeed_gas"
    }
  ]
}
```

### ArchitectureEnrichmentAgent

Uses deterministic architecture rules. It detects missing abstractions, role ambiguity, partial control loops, and candidate review points.

Examples:

- no Reference Input recovered;
- no Measured Output recovered;
- one code element appears to implement multiple roles;
- a control loop has no explicit Analyzer.

### LLMArchitectureReasoningAgent

Optionally calls an LLM provider to provide additional reviewable suggestions. The LLM receives a compact context that includes:

- components;
- structure relationships;
- control-loop summaries;
- runtime summary;
- current architecture consistency information.

The LLM must return JSON only and cannot modify the model directly.

## Suggestion deduplication

The pipeline deduplicates semantically equivalent suggestions. If a deterministic agent and an LLM suggest the same issue, the deterministic suggestion remains primary and the LLM message is merged into metadata.

Summary fields include:

```json
{
  "raw_suggestions": 7,
  "deduplicated_suggestions": 1,
  "suggestions": 6
}
```

## Gemini configuration

The Gemini provider reads the API key from the environment:

```bash
export GEMINI_API_KEY="your_key_here"
```

Optionally, install `python-dotenv` and create `.env` at the project root:

```bash
pip install python-dotenv
```

`.env`:

```bash
GEMINI_API_KEY=your_key_here
```

The `.env` file must be ignored by Git.

## Running agents

Offline deterministic mode:

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json \
  --llm-provider none
```

Gemini mode:

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash-lite
```
