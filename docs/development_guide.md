# Development Guide

## Repository organization

```text
python_kdm_extractor/          Static Python extraction
kdm_dynamic_analysis/          Runtime tracing and CodeModel enrichment
kdm_architecture_recovery/     Architecture recovery
kdm_architecture_agents/       Pre-review AI suggestions
kdm_architecture_review/       Human review GUI
kdm_pyecore_generator/         KDM XMI generation
schemas/                       JSON Schemas
configs/                       Pipeline configurations
docs/                          MkDocs documentation
run_pipeline.py                Configurable pipeline runner
```

## Development workflow

1. Implement or modify one pipeline stage.
2. Run unit tests for that stage.
3. Run schema validation on affected JSON artifacts.
4. Run an E2E pipeline on `three_layer_system` or `pymape_hierarchical`.
5. Generate KDM and check validation errors.
6. Update documentation and examples.

## Environment variables

For Gemini:

```bash
export GEMINI_API_KEY="your_key_here"
```

Or use `.env` if `python-dotenv` is installed:

```bash
pip install python-dotenv
```

`.env`:

```bash
GEMINI_API_KEY=your_key_here
```

Never commit `.env`.

## Adding a new dynamic scenario

Create a scenario under the target project, for example:

```text
examples/my_project/scenarios/my_scenario.py
```

Then run:

```bash
python run_pipeline.py \
  --config configs/my_project.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/my_project \
  --dynamic-scenario my_scenario:scenarios/my_scenario.py
```

## Adding an agent suggestion

Agents should only add suggestions under `ai_enrichment.suggestions`. They must not directly modify `structure_model`.

Suggestions should include:

- `suggestion_type`;
- `message`;
- `status`;
- `confidence`;
- `affected_elements`;
- `proposed_changes`;
- `evidence`.

## KDM semantic rule

When KDM has a native semantic construct, use it. For example:

```text
runtime_calls -> action::Calls
```

Do not encode semantic facts only as `TaggedValue` if KDM has an appropriate relation.
