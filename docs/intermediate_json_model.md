# Intermediate JSON Model

The intermediate JSON model is the central artifact exchanged between pipeline stages. It contains the static CodeModel, optional runtime enrichment, recovered architecture, AI suggestions, and user review data.

## Main sections

Typical top-level fields include:

```json
{
  "projectName": "pymape_hierarchical",
  "language": "python",
  "files": [],
  "relationships": [],
  "runtime_enrichment": {},
  "structure_model": {},
  "ai_enrichment": {},
  "architecture_review": {}
}
```

## CodeModel information

Static code information is stored mainly under `files` and `relationships`. Static relationships may include imports, calls, creates, reads, writes, types, values, returns, and exceptions.

## Runtime enrichment

Runtime evidence is added to the same model without replacing static facts.

```json
{
  "type": "runtime_calls",
  "source": "...",
  "target": "...",
  "relationship_level": "code",
  "source_level": "runtime",
  "evidence": "dynamic_trace",
  "scenario": "cruise_control"
}
```

Runtime enrichment also stores a summary:

```json
{
  "runtime_enrichment": {
    "status": "runtime_enriched",
    "summary": {
      "events": 1996,
      "events_after_filter": 1707,
      "events_filtered_out": 289,
      "dynamic_relationships_added": 32,
      "observed_argument_types": 808,
      "observed_return_types": 860,
      "observed_exceptions": 0
    }
  }
}
```

## Architecture information

The architecture recovery stage adds `structure_model`:

```json
{
  "structure_model": {
    "components": [],
    "structure_relationships": [],
    "containment_relationships": [],
    "control_loops": [],
    "subsystems": []
  }
}
```

## AI suggestions

Pre-review agents add `ai_enrichment`. These suggestions are not applied automatically.

```json
{
  "ai_enrichment": {
    "status": "pre_review_enriched",
    "suggestions": [],
    "summary": {
      "suggestions": 6,
      "raw_suggestions": 7,
      "deduplicated_suggestions": 1
    }
  }
}
```

## Human review

The GUI writes review decisions into the reviewed architecture JSON. This reviewed JSON is authoritative for final KDM generation.
