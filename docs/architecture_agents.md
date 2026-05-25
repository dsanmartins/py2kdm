# Architecture agents

Architecture agents run before human review and produce reviewable suggestions.

## Supported mode

The current main workflow supports only:

```bash
python kdm_architecture_agents/main.py --mode pre-review   --input outputs/pymape_hierarchical/python_model.runtime_enriched.architecture.json   --output outputs/pymape_hierarchical/python_model.runtime_enriched.ai_architecture.json
```

Post-review agents are intentionally not part of the default methodological pipeline. After human review, the reviewed architecture JSON is authoritative.

## Agent types

| Agent | Purpose |
|---|---|
| `DynamicEvidenceAgent` | Suggests architecture relationships supported by runtime evidence. |
| `ArchitectureEnrichmentAgent` | Detects missing or ambiguous architecture abstractions. |
| `LLMArchitectureReasoningAgent` | Optionally asks an LLM for additional pre-review suggestions. |
| `SuggestionDeduplicator` | Removes duplicate or overlapping suggestions. |

## LLM providers

Supported providers are `none`, `gemini`, and `ollama`.

Gemini reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from the environment. A `.env` file at project root is loaded when `python-dotenv` is installed.

## Suggestion schema

Suggestions are stored in:

```json
"ai_enrichment": {
  "status": "pre_review_enriched",
  "suggestions": []
}
```

Suggestions are not automatically transformed to KDM. They must be accepted, rejected or marked as reviewed in the GUI.
