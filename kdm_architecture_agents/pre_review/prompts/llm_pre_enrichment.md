# LLM pre-review architecture reasoning prompt

The LLM-based pre-review agent must only produce structured suggestions.

It must not:
- modify `structure_model`;
- claim that uncertain evidence is explicit;
- overwrite deterministic recovery;
- mark uncertain suggestions as accepted.

All uncertain suggestions must use:

```json
"status": "needs_review"
```
