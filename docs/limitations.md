# Limitations

## Python language coverage

The extractor is based on static analysis. It cannot fully resolve all Python dynamic behavior.

Limitations include:

- dynamic imports;
- monkey patching;
- reflection;
- runtime-generated classes or functions;
- dynamic attribute access;
- dependency injection patterns that do not leave clear static traces.

## Call resolution

Call resolution is best-effort. Some calls may remain unresolved when targets depend on dynamic runtime information.

Unresolved calls are preserved when possible so they can be inspected later.

## Architecture recovery

Architecture recovery is evidence-driven. It does not invent architectural abstractions without evidence.

Consequences:

- `Reference Input` is only recovered when explicit target, goal, threshold or setpoint-like elements are found.
- `Measured Output` is only recovered when explicit observed or measured values are found.
- `Sensor` is only recovered when sensor or measurement evidence exists.
- `Effector` is only recovered when actuation evidence exists.
- `Analyzer` may be missing when the code does not expose an explicit analysis step.

This is intentional. It avoids over-interpreting conventional code as autonomic architecture.

## Self-adaptive system detection

The autonomic applicability gate reduces false positives, but it is still rule-based. A project may be missed if it implements self-adaptation without clear vocabulary or structural hints.

A conventional project may also require review if it uses vocabulary such as `monitor`, `execute` or `state` in non-autonomic ways.

## KDM StructureModel semantics

KDM does not define every domain-specific architecture concept as a native metaclass. Therefore:

- `Control Loop` is represented as `structure::Component <<Control Loop>>`;
- `CL Manager` is represented as `structure::Component <<CL Manager>>`;
- MAPE-K roles are represented as stereotyped `structure::Component` elements;
- autonomic subsystems are represented as stereotyped `structure::Subsystem` elements.

## Stereotype compatibility

The generator uses `extensionFamily` under the KDM segment to represent the Adaptive System Domain. Tool compatibility may depend on how a specific KDM/EMF environment handles extension families and stereotype references.

## Traceability

Implementation links are created when the recovered architecture component has a corresponding KDM code element. If a component is inferred without a direct implementation element, it may only contain textual traceability attributes.

## Nested containment

The generated architecture uses nested `structureElement` containment and also keeps explicit `contains` relationships for traceability. This dual representation is useful for visualization and transformations, but it may introduce redundancy in the XMI.

Some attributes are intentionally retained for traceability even when they duplicate information represented structurally.

## Human review

The architecture recovery is semi-automatic. Its output should be considered a proposed inferred architecture. Human review is expected when:

- confidence is low;
- the system marks elements as `needs_review`;
- the control loop is partial;
- several roles are implemented by the same code element;
- control I/O abstractions are missing;
- the recovered architecture will be used for downstream modernization decisions.

## Future work

Potential improvements include:

- graphical review of architecture proposals;
- DSL-based editing of the architecture JSON;
- stronger support for user-approved corrections;
- optional inference of required but implicit control abstractions;
- improved detection of sensors, measured outputs and reference inputs;
- deeper dynamic-analysis integration;
- multi-language front ends.
