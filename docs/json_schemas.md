# JSON Schemas

The `py2kdm` pipeline uses JSON artifacts as serialized intermediate models.

Although these artifacts are stored as JSON files, they are treated as structured models. The schemas define the expected structure of each model stage and support validation, documentation, GUI integration, and future LLM-based agents.

## Schema files

```text
schemas/
├── python_model.schema.json
├── architecture_model.schema.json
├── ai_architecture_model.schema.json
├── reviewed_architecture_model.schema.json
└── ai_checked_architecture_model.schema.json
```

## Model stages

| Schema | Artifact |
|---|---|
| `python_model.schema.json` | `python_model.json` |
| `architecture_model.schema.json` | `python_model.architecture.json` |
| `ai_architecture_model.schema.json` | `python_model.ai_architecture.json` |
| `reviewed_architecture_model.schema.json` | `python_model.reviewed_architecture.json` |
| `ai_checked_architecture_model.schema.json` | `python_model.reviewed.ai_checked.json` |

## Validation

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.json   --type python
```

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.architecture.json   --type architecture
```

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.ai_architecture.json   --type ai-architecture
```

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.reviewed_architecture.json   --type reviewed
```

```bash
python scripts/validate_json_schema.py   --input outputs/pymape_hierarchical/python_model.reviewed.ai_checked.json   --type ai-checked
```

Dependency:

```bash
pip install jsonschema
```

## Use in the paper

For the paper, the JSON artifacts can be described as serialized intermediate models. A UML-like conceptual diagram can be derived from these schemas.

Recommended wording:

```text
The intermediate JSON artifacts are treated as serialized models. Their structure is specified through lightweight JSON Schemas and illustrated through UML-like diagrams that expose the main entities, attributes, and relationships used throughout the pipeline.
```
