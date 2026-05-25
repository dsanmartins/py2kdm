# Human review

Human review is the methodological boundary between automated recovery and final KDM generation.

The pre-review agents may suggest changes, but the reviewed model is authoritative. There is no default post-review agent stage. Once the user exports the reviewed architecture JSON, that file is the input to final KDM generation.

## Inputs

The preferred input for the Human Review tab is:

```text
python_model.runtime_enriched.ai_architecture.json
```

If no dynamic analysis was run, use:

```text
python_model.ai_architecture.json
```

If no agents were run, use the architecture JSON produced by architecture recovery.

## AI suggestion decisions

| Button | Meaning |
|---|---|
| Accept | Accepts the suggestion. If the suggestion contains a safe structured change, the GUI applies it to the model. If it is textual only, the decision is recorded. |
| Reject | Rejects the suggestion and does not modify the architecture. |
| Mark reviewed | Records that the suggestion was inspected without accepting or rejecting it. |

## Validation before export

The **Export reviewed JSON** button is disabled until the reviewed architecture has been validated. If validation finds blocking issues, the GUI asks for confirmation before exporting.

## Export summary

Before exporting, the GUI shows a summary with the number of materialized components and relationships, AI suggestion decisions, and validation findings.

## Traceability

The Traceability panel explains why a component or relationship exists. It shows code references, KDM stereotypes, architecture recovery evidence, runtime evidence, related AI suggestions, and incoming/outgoing architecture relationships.
