# py2kdm

`py2kdm` is a model-driven reverse engineering pipeline that transforms Python projects into KDM-compatible XMI models. It combines static extraction, optional runtime evidence, architecture recovery, pre-review AI suggestions, human review, and final KDM generation.

The current methodological flow is:

```text
Python project
  -> static extraction
  -> optional dynamic analysis
  -> runtime-enriched intermediate JSON
  -> architecture recovery
  -> pre-review AI suggestions
  -> human review
  -> final KDM XMI
```

The AI agents are used only before human review. After the user accepts, rejects, or edits suggestions in the review GUI, the reviewed architecture is treated as authoritative and is directly transformed into the final KDM model.

## Main features

- Static extraction of Python files, classes, functions, methods, parameters, variables, calls, imports, values, exceptions, and body actions.
- Runtime tracing through `sys.setprofile` to observe calls, argument types, return types, and exceptions.
- Semantic KDM mapping of runtime calls as native `action::Calls`, not as generic metadata.
- Architecture recovery for MAPE-K oriented self-adaptive systems.
- Pre-review AI suggestions based on deterministic rules, runtime evidence, and optional LLM reasoning.
- Human review through a GUI before generating the final KDM model.
- JSON Schema validation for intermediate, architecture, AI-enriched, and reviewed models.

## Recommended documentation path

1. Read [Architecture](architecture.md) for the high-level design.
2. Read [Pipeline Configuration](pipeline_configuration.md) for configuration files and outputs.
3. Read [Dynamic Analysis](dynamic_analysis.md) if runtime evidence is required.
4. Read [Architecture Agents](architecture_agents.md) if AI-assisted suggestions are enabled.
5. Read [JSON to KDM Mapping](json_to_kdm_mapping.md) for the final KDM generation semantics.
