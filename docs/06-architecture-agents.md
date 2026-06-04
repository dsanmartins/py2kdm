# 6. Architecture agents

Architecture agents operate after deterministic architecture recovery and before human review. Their purpose is to provide reviewable evidence and suggestions, not to replace the deterministic architecture model or the human reviewer.

## Agent input and output

Input:

```text
*.architecture.json
```

Code-context input:

```text
python_model.json
java_model.json
*.runtime_enriched.combined.json
```

Output:

```text
*.ai_architecture.json
```

Typical command:

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

## Current pre-review stages

| Stage | Purpose |
|---|---|
| Context building | Builds compact architecture and code evidence. |
| Deterministic code review | Confirms recovered roles using compact code context. |
| Deterministic suggestions | Flags missing, ambiguous or unsupported architecture roles. |
| LLM-assisted enrichment | Optionally asks a configured LLM for additional review suggestions. |
| Schema guard / normalization | Normalizes suggestions and prevents malformed LLM output from corrupting the artifact. |
| Deduplication | Removes duplicate or overlapping suggestions. |

## Deterministic assumptions without LLM

The non-LLM part is intentionally conservative. It relies on evidence that can be inspected in the JSON model.

### Main assumptions

1. Architecture roles can be inferred from explicit static evidence such as names, imports, decorators, annotations, method names, package names and call relationships.
2. Runtime evidence, when available, can strengthen relationships but is not required for all projects.
3. MAPE-K-like systems often expose role evidence through names such as `monitor`, `analyze`, `plan`, `execute`, `knowledge`, `loop`, `sensor`, `effector`, `manager`, `adapter`, `context`, `repository` or `state`.
4. Python MAPE-K frameworks may materialize roles as top-level decorated functions, for example `loop.monitor`, `loop.plan` and `loop.execute`.
5. Java/Android adaptive systems may materialize roles through classes such as managers, adapters, context providers, sensors, effectors and knowledge/database components.
6. A recovered role should be considered unsupported if it appears in `structure_model` but cannot be confirmed by compact code context or explicit architecture evidence.

### Typical deterministic role evidence

| Role | Evidence examples |
|---|---|
| Monitor | `monitor`, `observe`, `collect`, `sense`, `read`, `distance`, `speed`, `loop.monitor`. |
| Analyzer | `analyze`, `analyse`, `analysis`, `diagnosis`, classification or evaluation behavior. |
| Planner | `plan`, `planner`, `policy`, `strategy`, `decide`, `pid`, `loop.plan`. |
| Executor | `execute`, `executor`, `actuate`, `command`, `gas_brake`, `loop.execute`. |
| Knowledge | `knowledge`, `repository`, `store`, `memory`, `state`, `database`, `history`. |
| Sensor | `sensor`, `read`, `measure`, device/location/bluetooth/context observation APIs. |
| Effector | `effector`, `actuator`, `gas`, `brake`, `siren`, `hazard_lights`, settings or adaptation APIs. |
| LoopManager | `loop`, `mape`, `manager`, `coordinator`, `register`, `MapeLoop`. |

## LLM-assisted assumptions

The LLM is optional. It is used only in the pre-review stage.

### What the LLM sees

The LLM does not need the entire source project. It receives a compact context built from:

- recovered components and relationships;
- selected code-context classes/functions/methods;
- candidate roles;
- evidence strings;
- representative methods, decorators, imports, fields and technology/API hints;
- deterministic review findings.

This prevents unnecessarily large prompts and keeps the LLM focused on architecture review.

### What the LLM is allowed to do

The LLM can produce suggestions such as:

- confirm a role;
- flag a weak or unsupported role;
- suggest a missing component;
- suggest a possible relationship;
- add review notes or confidence estimates.

The LLM does not directly modify the KDM XMI. Its suggestions are stored in `ai_enrichment.suggestions` and must be reviewed or validated before they affect a reviewed model.

### Safety assumptions

1. The LLM can be wrong; deterministic evidence and human review remain necessary.
2. LLM output is schema-guarded and normalized before being stored.
3. LLM suggestions are not authoritative by default.
4. The deterministic `architecture_json` remains the automatic source for `model.structure.kdm.xmi`.
5. The human-reviewed JSON remains the source for `model.reviewed.kdm.xmi`.

## Providers

Supported provider values:

| Provider | Meaning |
|---|---|
| `none` | No LLM; deterministic review only. |
| `gemini` | Uses Google Gemini through `google-genai`. |
| `ollama` | Uses a local Ollama model, when configured. |

For Gemini:

```bash
export GEMINI_API_KEY="..."
```

or use a project-root `.env` file:

```text
GEMINI_API_KEY=...
```

Required packages in the active Python environment:

```bash
python -m pip install google-genai python-dotenv
```

## Output sections

The pre-review output keeps the original architecture model and adds review information.

Important sections:

| Section | Meaning |
|---|---|
| `code_context` | Compact selected source evidence. |
| `deterministic_code_review` | Deterministic role support and unsupported-role report. |
| `ai_enrichment` | Suggestions from deterministic and LLM-assisted agents. |
| `ai_enrichment.summary` | Provider, model, code-context count, suggestion count and diagnostics. |

Useful indicators:

```text
code_context_available: true
code_context_classes: N
deterministic_code_review.status: available
assessment.status: supported_by_code_context
unsupported_architecture_roles: 0
llm_provider: gemini
llm_suggestions: N
```

## Human Review integration

The GUI Human Review tab can load:

```text
*.ai_architecture.json
```

if it exists, otherwise it loads:

```text
*.architecture.json
```

After validation, the reviewer can export:

```text
*.reviewed_architecture.json
```

and generate:

```text
model.reviewed.kdm.xmi
```

## Recommended interpretation for research

For reporting results, separate the three layers:

| Layer | Interpretation |
|---|---|
| Architecture recovery | Deterministic recovery of candidate architecture elements. |
| Deterministic pre-review | Evidence-based confirmation or warning over recovered roles. |
| LLM pre-review | Additional review suggestions, useful but non-authoritative. |

This distinction is important when comparing systems such as Java/Android projects and Python decorator-based MAPE-K projects.
