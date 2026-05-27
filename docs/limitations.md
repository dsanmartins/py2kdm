# Limitations

## Python coverage

The Python extractor maps a practical subset of Python constructs to the intermediate model and KDM. Highly dynamic features may require runtime evidence or additional extractor rules.

## Java coverage

The Java extractor supports rich static extraction for common Java constructs, including methods, constructors, annotations, local variables, assignments, calls, object creation, control flow and exceptions. Some complex cases may still require refinement, for example advanced generics, reflection, dynamic proxies or framework-specific behavior.

## Dynamic analysis

Runtime evidence depends on scenario quality. If a behavior is not exercised by a scenario, it will not appear in runtime traces.

## Architecture recovery

Recovered architecture is evidence-based and heuristic. It must be reviewed by the user before KDM generation when used for architecture-level studies.

## AI suggestions

LLM-backed suggestions are optional. They are pre-review suggestions only and are not authoritative.

## KDM mapping

The KDM generator aims to use KDM semantics where possible. Some project-specific or domain-specific evidence may still require stereotypes or extension families.

## Regression checks

Regression checks protect known invariants, but they are not a proof of semantic completeness. They should be extended when new mapper rules or extractors are added.

## GUI configuration

The GUI has a separate configuration workflow from the CLI config. Both should be kept synchronized at the conceptual level, but they are not the same file format.
