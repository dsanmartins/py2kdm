# Limitations

## 1. Overview

`py2kdm` is currently a research-oriented prototype for generating KDM 1.4 models from Python projects.

The current implementation already supports a complete two-stage pipeline:

```text
Python source code
        │
        ▼
Intermediate JSON model
        │
        ▼
KDM 1.4 XMI model
```

However, there are several technical and conceptual limitations that should be considered when using, extending or evaluating the tool.

This document summarizes the main limitations of the current version.

---

## 2. Python language limitations

Python is a highly dynamic language. Many semantic properties cannot be determined precisely through static AST analysis alone.

The current extractor does not execute code. It analyzes Python source files statically using AST-based techniques.

As a result, some Python constructs are difficult to resolve completely.

Examples include:

- dynamic imports;
- monkey patching;
- reflection;
- runtime attribute creation;
- dynamic dispatch;
- higher-order functions;
- decorators that modify behavior;
- metaclasses;
- dynamically generated classes or functions.

The extractor may still capture some of these constructs syntactically, but their full runtime meaning may not be resolved.

---

## 3. Type inference limitations

The current type analysis is approximate.

The extractor and generator can identify some types through:

- constructor calls;
- local variable assignments;
- builtin type knowledge;
- simple class references;
- import and symbol-table information.

However, the tool does not yet implement a complete Python type inference engine.

Limitations include:

- variables may have multiple possible runtime types;
- types inferred through complex control flow may be missed;
- generic container types are not fully modeled;
- dynamically assigned attributes may not be resolved;
- inferred external library types may be incomplete;
- annotations are not yet fully exploited as semantic type declarations.

This affects the precision of some `HasType`, `Calls` and `Creates` relations.

---

## 4. Call resolution limitations

The call resolver classifies and resolves many calls, but some calls can remain unresolved.

This can happen when:

- the call target is dynamically computed;
- the receiver type is unknown;
- the call belongs to an external library not represented in the model;
- the call is produced by a factory or dependency injection mechanism;
- the call is made through a variable alias;
- the call depends on runtime imports or configuration.

Unresolved calls are explicitly marked in the intermediate JSON and can be represented in the generated model with unresolved metadata when needed.

The absence of a resolved target does not necessarily mean the input program is invalid. It means the static extractor could not determine a precise target.

---

## 5. Return expression limitations

The current KDM generator models returns using `Reads` relations.

Supported return patterns include:

```text
return x
return True
return None
return f(...)
```

These are mapped to:

```text
return → Reads → StorableUnit
```

For literals, a temporary `StorableUnit` is created and linked to a `Value` using `HasValue`.

For returned calls, a temporary `StorableUnit` represents the call result.

However, complex return expressions are not yet fully decomposed.

Examples:

```python
return role in self.roles
return x + y
return a and b
return user.name if user else None
return [x.id for x in users]
```

These expressions may be represented as unresolved return values, for example:

```text
unresolved_return_value = "role in self.roles"
```

Future versions could introduce expression-level KDM modeling for boolean, arithmetic, conditional and comprehension expressions.

---

## 6. Control-flow limitations

The current generator models body nesting and exception-related flows.

It supports:

- `BlockUnit` for callable bodies;
- `ActionElement` for executable statements;
- `TryUnit`;
- `CatchUnit`;
- `FinallyUnit`;
- `ExceptionFlow`;
- `ExitFlow`.

However, it does not yet construct a complete control-flow graph for all Python control structures.

For example, the current version does not fully model detailed control-flow relations for:

- `if` / `elif` / `else` branches;
- loops;
- `break`;
- `continue`;
- `with` exit behavior;
- short-circuit boolean evaluation;
- generator control flow;
- asynchronous control flow.

The current focus is on structural body nesting and semantically important action/data relations.

---

## 7. Exception modeling limitations

The generator now uses KDM-specific exception modeling:

```text
TryUnit --ExceptionFlow--> CatchUnit
TryUnit --ExitFlow-------> FinallyUnit
raise   --Throws---------> thrown exception object
```

This is more standard than using generic `ActionRelationship(kind="catches")`.

Nevertheless, exception modeling still has limitations:

- exception propagation across call boundaries is not fully modeled;
- multiple exception types in a single handler may require richer modeling;
- exception aliases are not fully represented;
- re-raise semantics are represented using metadata rather than a full exception-flow graph;
- exception hierarchy reasoning is limited;
- `else` blocks in try statements are structurally preserved but not yet represented with a specific KDM flow relation.

---

## 8. KDM coverage limitations

The current generator focuses mainly on selected parts of KDM 1.4:

- Inventory layer;
- Code layer;
- Action elements and action relations;
- source traceability;
- type and value relations.

It does not yet cover all KDM packages or viewpoints.

Currently limited or unsupported areas include:

- Platform model;
- UI model;
- Event model;
- Data model beyond basic `StorableUnit` usage;
- Build model;
- Conceptual model;
- detailed control-flow graphs;
- full architecture-level abstractions.

This is expected because the current goal is to generate a useful code/action-level KDM model from Python source code.

---

## 9. Source traceability limitations

The generator creates `SourceRef` and `SourceRegion` elements using source paths and line numbers from the JSON model.

Current limitations:

- column-level positions may be incomplete or unavailable;
- multi-line expressions may be approximated;
- generated or synthetic elements may use the surrounding statement region;
- temporary semantic elements, such as returned literal storables, may not always have precise source spans.

Despite this, line-level traceability is generally preserved for the main structural and action elements.

---

## 10. Intermediate JSON limitations

The intermediate JSON model is the contract between the extractor and the generator.

The current schema is practical and testable, but it is not yet formalized as an external JSON Schema document.

Current limitations include:

- no formal `.schema.json` file yet;
- no schema-level validation before generation;
- some fields are optional and depend on the construct;
- some expression fields are stored as strings;
- some temporary analysis fields are used internally by the generator but are not part of final KDM output.

A future improvement would be to define:

```text
intermediate_json_model.schema.json
```

and validate all fixtures and extractor outputs against it.

---

## 11. External library limitations

The generator can create external model elements for unresolved or external targets.

However, external library modeling is still approximate.

Limitations include:

- external APIs are not deeply analyzed;
- external classes and methods may be represented as lightweight placeholders;
- version-specific library behavior is not modeled;
- external package structure may be simplified;
- dynamic imports may not be resolved precisely.

This is acceptable for many modernization and analysis scenarios, but should be considered when interpreting external call relations.

---

## 12. Serialization limitations

The current serializer produces stable XMI for the tested cases.

However, stable serialization depends on:

- deterministic traversal order;
- stable JSON input order;
- stable identifier generation;
- deterministic creation of external targets;
- deterministic ordering of attributes and relations.

Tests currently verify that repeated generation produces identical output for the current fixtures and example project.

Future changes should preserve this property.

---

## 13. Testing limitations

The project includes automated tests for:

- stable serialization;
- absence of obsolete attributes;
- semantic relations;
- exception mapping;
- return mapping;
- `BlockUnit` body mapping;
- fixture-based edge cases;
- CLI input and output behavior.

However, test coverage is still limited to the included example project and fixtures.

Additional tests should be added for:

- larger Python projects;
- multiple packages;
- decorators;
- async functions;
- comprehensions;
- nested classes;
- multiple inheritance;
- complex imports;
- complex return expressions;
- control-flow-heavy code.

---

## 14. Current validation boundaries

`KDMValidator` validates many structural and semantic properties of the generated model.

It checks:

- relation targets;
- obsolete attributes;
- duplicate attributes;
- duplicate source regions;
- duplicate child actions;
- return semantics;
- raise semantics;
- try/catch/finally flows;
- callable body `BlockUnit` structure.

However, it does not prove that the generated KDM model is a complete semantic representation of the original Python program.

The validator checks internal consistency of the generated model, not full behavioral equivalence with the source code.

---

## 15. Research prototype status

`py2kdm` should currently be considered a research prototype.

It is suitable for:

- experimenting with Python to KDM generation;
- evaluating KDM-based model-driven modernization workflows;
- generating traceable KDM code/action models;
- testing JSON-to-KDM mappings;
- supporting research on KDM-based refactoring and migration.

It should not yet be considered a complete production-grade Python reverse engineering tool.

---

## 16. Recommended future improvements

Important future improvements include:

1. Define a formal JSON Schema for the intermediate model.
2. Extend expression modeling beyond string-based values.
3. Improve Python type inference.
4. Improve external library modeling.
5. Add support for module-level executable blocks.
6. Add richer control-flow relations.
7. Add more tests for real-world Python projects.
8. Add documentation for unsupported constructs.
9. Add coverage reports for tests.
10. Add CI integration.
11. Add model comparison utilities.
12. Add optional KDM-to-other-model transformations.

---

## 17. Summary

The current version of `py2kdm` provides a functional and validated pipeline for generating KDM 1.4 XMI models from Python projects.

Its main limitations are related to the dynamic nature of Python, incomplete type inference, partial control-flow modeling and limited expression-level semantics.

These limitations are expected at the current prototype stage and provide a clear roadmap for future development.
