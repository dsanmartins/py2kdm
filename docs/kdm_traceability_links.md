# KDM Traceability Links

## Purpose

The KDM generation process preserves traceability between recovered architecture abstractions and the original code elements. This traceability is essential because the recovered architecture is not manually designed from scratch; it is inferred from the intermediate Python model.

Traceability is represented through:

- `implementation` references;
- `attribute` metadata;
- `structureRelationship`;
- `aggregatedRelation`;
- stereotype references;
- confidence and evidence attributes.

## Implementation links

When a recovered component corresponds to a source code element, the generator connects the KDM `structure::Component` to the corresponding KDM code element through the `implementation` reference.

Example:

```xml
<structureElement
    xsi:type="structure:Component"
    name="pid"
    implementation="//@model.1/@codeElement.0/@codeElement.2">
  ...
</structureElement>
```

The component also stores the original identifier:

```xml
<attribute tag="implemented_by_id"
           value="function:pymape_hierarchical.hierarchical-cruise-control.pid"/>
```

This dual representation is useful:

- `implementation` provides a KDM-level reference;
- `implemented_by_id` provides a stable textual trace to the intermediate JSON model.

## Common traceability attributes

Recovered elements may include the following attributes:

| Attribute | Meaning |
|---|---|
| `id` | Stable architecture identifier. |
| `structure_kind` | Kind of recovered structural element. |
| `role` | MAPE-K or autonomic role. |
| `confidence` | Confidence score assigned during recovery. |
| `source` | Source of the inference rule. |
| `status` | Review status, such as `auto_accepted` or `needs_review`. |
| `evidence` | Human-readable explanation of why the element was recovered. |
| `implemented_by_id` | Intermediate-model element that implements the abstraction. |
| `nested_under` | Parent architectural element after nesting. |
| `nested_containment_reason` | Explanation of the nesting decision. |

Example:

```xml
<attribute tag="role" value="Planner"/>
<attribute tag="confidence" value="0.95"/>
<attribute tag="source" value="rule_based_decorator"/>
<attribute tag="evidence" value="Decorator 'loop.plan' maps to MAPE-K role Planner"/>
```

## Stereotype traceability

Autonomic roles are materialized using the `Adaptive System Domain` extension family.

Example:

```xml
<structureElement
    xsi:type="structure:Component"
    name="pid"
    stereotype="//@extensionFamily.0/@stereotype.2">
```

The stereotype reference points to:

```xml
<stereotype name="Planner" type="structure:Component"/>
```

This means that the KDM component is not only named or tagged as a planner. It is structurally connected to the `Planner` stereotype from the Adaptive System Domain.

## Structure relationships

Architecture relationships are represented with `structure::StructureRelationship`.

Example:

```xml
<structureRelationship
    xsi:type="structure:StructureRelationship"
    from="..."
    to="...">
  <attribute tag="relationship_type" value="uses_knowledge"/>
  <attribute tag="relationship_level" value="architectural"/>
</structureRelationship>
```

The relationship includes traceability attributes such as:

- `relationship_id`;
- `relationship_type`;
- `relationship_level`;
- `confidence`;
- `source_role`;
- `target_role`;
- `relationship_status`;
- `derived_from`.

## Aggregated relationships

For structural and architectural relationships, the generator may also create `core::AggregatedRelationship` entries.

Example:

```xml
<aggregatedRelation
    from="..."
    to="..."
    relation="..."
    density="1">
  <attribute tag="relationship_type" value="contains"/>
  <attribute tag="relationship_level" value="architectural"/>
</aggregatedRelation>
```

Aggregated relationships provide an additional KDM representation of relationships among structural elements.

## Containment traceability

Containment is represented in two complementary ways:

1. Real nested KDM containment through nested `structureElement` nodes.
2. Explicit `contains` relationships and aggregated relationships.

Example hierarchy:

```xml
<structureElement xsi:type="structure:Subsystem" name="Managing Subsystem">
  <structureElement xsi:type="structure:Component" name="Loop">
    <structureElement xsi:type="structure:Component" name="Loop Control Loop">
      <structureElement xsi:type="structure:Component" name="pid"/>
    </structureElement>
  </structureElement>
</structureElement>
```

The same containment may also be represented as:

```xml
<structureRelationship from="..." to="...">
  <attribute tag="relationship_type" value="contains"/>
  <attribute tag="composition_kind" value="containment"/>
</structureRelationship>
```

This dual representation helps both visualization and downstream model transformations.

## Technical and architectural relationships

The generator preserves the distinction between technical evidence and architectural interpretation.

Examples:

| Relationship type | Level | Meaning |
|---|---|---|
| `subscribes_to` | `technical` | Implementation-level evidence such as framework subscription calls. |
| `mapek_flow` | `architectural` | Interpreted MAPE-K control flow. |
| `uses_knowledge` | `architectural` | Component uses shared Knowledge. |
| `contains` | `architectural` | Structural composition or containment. |

This distinction allows later tools to decide whether to visualize, transform, or ignore some relationships depending on the analysis objective.

## Review status

Traceability also supports human review. Elements and relationships can be marked as:

- `auto_accepted`;
- `needs_review`;
- `weak_suggestion`.

For example, a class named `Knowledge` may be recovered with `needs_review` if the confidence is not high enough, while a decorated function such as `@loop.plan` may be recovered as `auto_accepted`.

## Summary

The KDM model is not only a structural representation. It is also a traceable artifact that preserves:

- where each architecture abstraction came from;
- why it was inferred;
- how confident the recovery process was;
- how the abstraction is connected to code;
- how it participates in the recovered autonomic architecture.
