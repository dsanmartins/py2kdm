# Limitations

## Static analysis limitations

Python static analysis cannot always resolve:

- dynamically bound methods;
- decorated functions;
- dependency injection;
- monkey patching;
- callback registration;
- external library behavior;
- framework-managed execution.

Dynamic analysis can complement these gaps but only for executed scenarios.

## Dynamic analysis limitations

Runtime evidence is scenario-dependent. If a behavior is not executed, it will not appear in the trace.

Dynamic tracing may also capture infrastructure noise. The enrichment stage filters common noise, but project-specific helpers may require additional filtering.

## Architecture recovery limitations

Recovered architecture is a proposal. Some roles may be implicit or merged in the implementation. For example, an Analyzer role may be absorbed into a Planner or Monitor.

Therefore, recovered components and AI suggestions require human review.

## LLM limitations

LLMs are optional and are restricted to pre-review suggestions. They do not construct or modify the CodeModel and do not apply changes directly to the StructureModel.

Potential limitations include:

- redundant suggestions;
- overly generic architectural advice;
- incorrect interpretation of missing roles;
- output formatting issues.

The schema guard and suggestion deduplicator reduce these issues, but human review remains required.

## KDM mapping limitations

Some Python constructs do not map perfectly to KDM. The generator uses the closest KDM semantic construct available and validates the resulting model.

Runtime calls that cannot be resolved to known CodeItems are reported as unresolved and are not emitted as KDM `Calls`.
