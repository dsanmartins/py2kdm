# JSON schemas

JSON schemas are stored under `schemas/`.

## Validator

Use:

```bash
python scripts/validate_json_schema.py --input path/to/file.json --type reviewed
```

Supported `--type` values include:

- `python`;
- `architecture`;
- `ai-architecture`;
- `reviewed`;
- `ai-checked` for legacy artifacts.

## Role

Schemas are used for regression tests and for checking the shape of generated artifacts. They do not replace semantic validation in the GUI or KDM generator.
