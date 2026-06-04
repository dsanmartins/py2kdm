# 2. Subprojects and standalone execution

The repository is organized into subprojects that can be executed independently or through `run_pipeline.py`. The standalone commands are useful for debugging a specific stage, while `run_pipeline.py` is recommended for reproducible end-to-end execution.

## Subprojects

| Subproject | Purpose | Main input | Main output |
|---|---|---|---|
| `python_kdm_extractor` | Static extraction for Python projects. | Python source directory. | `python_model.json`. |
| `tools/java2kdm` | External Java extractor JAR. | Java source directory. | `java_model.json`. |
| `kdm_dynamic_analysis` | Runtime tracing and enrichment for Python scenarios. | Static JSON + scenario script. | `runtime_trace.*.json` and `*.runtime_enriched.*.json`. |
| `kdm_architecture_recovery` | Deterministic architecture recovery. | Intermediate or runtime-enriched JSON. | `*.architecture.json`. |
| `kdm_architecture_agents` | Pre-review enrichment, deterministic code review and optional LLM suggestions. | Architecture JSON + code-context JSON. | `*.ai_architecture.json`. |
| `kdm_pyecore_generator` | KDM XMI generation with validation. | Intermediate, architecture or reviewed JSON. | `*.kdm.xmi`. |
| `py2kdm_gui` | GUI workbench. | Project paths and generated artifacts. | Visual workflow, reviewed JSON and KDM outputs. |
| `scripts` | Regression and validation utilities. | JSON/XMI artifacts. | Console reports. |
| `run_pipeline.py` | End-to-end console orchestrator. | Project config JSON. | All configured artifacts. |

## Python extractor

```bash
python python_kdm_extractor/main.py \
  --input examples/pymape_hierarchical \
  --output outputs/pymape_hierarchical/python_model.json
```

Arguments:

| Argument | Meaning |
|---|---|
| `--input` | Root directory of the Python project to analyze. |
| `--output` | Path where the intermediate JSON model will be written. |

The extractor records source files, modules, imports, classes, functions, methods, parameters, local variables, static calls, reads, writes, return statements, exceptions, decorators and body-level structures used later by the KDM generator.

## Java extractor

```bash
java -jar tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar \
  /path/to/java/project \
  outputs/phoneadapter/java_model.json \
  schemas/python_model.schema.json
```

Arguments:

| Positional argument | Meaning |
|---|---|
| `project root` | Java project source directory. |
| `output JSON` | Path where `java_model.json` will be written. |
| `schema path` | Shared intermediate-model schema entry point. |

The Java extractor records packages, imports, classes, interfaces, enums, fields, methods, constructors, parameters, calls, assignments, returns, object creations, control structures, `try`/`catch`, `throw` and annotations.

## Dynamic analysis

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/cruise_control_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json \
  --scenario cruise_control \
  --mode desktop
```

Arguments:

| Argument | Meaning |
|---|---|
| `trace-and-enrich` | Subcommand that executes a scenario and enriches a model. |
| `--project-root` | Root directory used when executing the scenario. |
| `--script` | Scenario script relative to the project root or absolute path. |
| `--input` | Static JSON model to enrich. |
| `--trace-output` | Raw runtime trace output. |
| `--output` | Runtime-enriched JSON output. |
| `--scenario` | Scenario identifier stored in metadata. |
| `--mode` | Execution mode, for example `desktop`. |

Dynamic analysis is currently intended for Python. Java projects use static KDM-based recovery.

## Architecture recovery

```bash
python kdm_architecture_recovery/main.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --output outputs/pymape_hierarchical/python_model.architecture.json
```

Arguments:

| Argument | Meaning |
|---|---|
| `--input` | Intermediate or runtime-enriched JSON model. |
| `--output` | Architecture JSON output with `structure_model`. |

The recovery stage applies an applicability gate and role inference rules. For adaptive systems, it can materialize MAPE-K-related components, subsystems, control loops and architecture relationships.

## Architecture agents

```bash
python kdm_architecture_agents/main.py \
  --mode pre-review \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/python_model.ai_architecture.json \
  --code-context-input outputs/pymape_hierarchical/python_model.json \
  --llm-provider gemini \
  --llm-model gemini-2.5-flash-lite \
  --llm-timeout 300
```

Arguments:

| Argument | Meaning |
|---|---|
| `--mode pre-review` | Runs the pre-review stage. |
| `--input` | Architecture JSON. |
| `--output` | AI/pre-review architecture JSON. |
| `--code-context-input` | Static or runtime-enriched code JSON used to build compact evidence. |
| `--llm-provider` | `none`, `gemini` or `ollama`. |
| `--llm-model` | Provider-specific model name. |
| `--llm-timeout` | Timeout in seconds. |

For Gemini, set `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the environment or in a project-root `.env` file. The Python environment must include `google-genai` and, if `.env` loading is needed, `python-dotenv`.

## KDM generator

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.architecture.json \
  --output outputs/pymape_hierarchical/model.structure.kdm.xmi
```

Arguments:

| Argument | Meaning |
|---|---|
| `--input` | Intermediate, architecture or reviewed JSON. |
| `--output` | Target KDM XMI file. |
| `--no-validation` | Optional flag to skip KDM validation. |

Use an architecture JSON or reviewed architecture JSON if the resulting XMI must include `StructureModel`.

## GUI

```bash
python -m py2kdm_gui.main
```

The GUI is recommended for interactive inspection and human review. The Process tab contains the automatic workflow, while the Human Review tab contains the optional pre-review and reviewed-KDM workflow.

## Validation and regression scripts

Typical scripts include:

```bash
python scripts/check_kdm_regression.py \
  --xmi outputs/pymape_hierarchical/model.kdm.xmi \
  --language python \
  --profile pymape_hierarchical \
  --baseline configs/kdm_regression_baselines.json
```

```bash
python scripts/check_architecture_recovery.py \
  --architecture outputs/pymape_hierarchical/python_model.architecture.json \
  --profile pymape_hierarchical \
  --baseline configs/architecture_recovery_baselines.json
```

```bash
python scripts/check_ai_architecture_review.py \
  --ai-architecture outputs/pymape_hierarchical/python_model.ai_architecture.json \
  --profile pymape_hierarchical \
  --baseline configs/ai_architecture_review_baselines.json
```

```bash
python scripts/check_kdm_structure.py \
  --xmi outputs/pymape_hierarchical/model.structure.kdm.xmi \
  --profile pymape_hierarchical \
  --baseline configs/kdm_structure_baselines.json
```
