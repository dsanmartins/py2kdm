# Limitations

## Python coverage

The extractor targets Python source code and maps a practical subset of Python constructs to the intermediate model and KDM.

## Dynamic analysis

Runtime evidence depends on scenario quality. If a behavior is not exercised by a scenario, it will not appear in runtime traces.

## Architecture recovery

Recovered architecture is evidence-based and heuristic. It must be reviewed by the user before KDM generation.

## AI suggestions

LLM-backed suggestions are optional. They are pre-review suggestions only and are not authoritative.

## KDM mapping

The KDM generator aims to use KDM semantics where possible. Some project-specific or domain-specific evidence may still require stereotypes or extension families.

## GUI configuration

The GUI has a separate configuration format from the CLI pipeline. This is intentional because the GUI stores interactive state, while the CLI config describes batch execution.
