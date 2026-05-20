# Structure Model Mapping

## Purpose

The `StructureModel` mapping translates the recovered architecture JSON into a KDM `structure::StructureModel`. The mapping preserves architectural roles, stereotypes, implementation links, traceability attributes, and structural relationships.

The input is the `structure_model` section of the architecture JSON. The output is a KDM model containing software systems, architecture views, subsystems, components, control loops, relationships, and aggregated relationships.

## Main JSON elements

The architecture JSON contains the following main sections:

```json
{
  "structure_model": {
    "software_system": {},
    "architecture_views": [],
    "components": [],
    "control_loops": [],
    "subsystems": [],
    "structure_relationships": [],
    "containment_relationships": []
  }
}
```

## Software system

The software system is materialized as a KDM `structure::SoftwareSystem`.

Example JSON:

```json
{
  "id": "software_system:pymape_hierarchical",
  "name": "pymape_hierarchical"
}
```

Expected KDM shape:

```xml
<structureElement xsi:type="structure:SoftwareSystem" name="pymape_hierarchical">
  <attribute tag="id" value="software_system:pymape_hierarchical"/>
  <attribute tag="structure_kind" value="software_system"/>
</structureElement>
```

## Architecture view

The inferred architecture view is materialized as `structure::ArchitectureView`.

Example JSON:

```json
{
  "id": "architecture_view:mapek",
  "name": "Inferred MAPE-K View",
  "status": "proposal"
}
```

## Components

Recovered architectural components are materialized as `structure::Component`.

Example JSON:

```json
{
  "id": "component:pid_planner_cruise_control_pid",
  "name": "pid",
  "role": "Planner",
  "stereotype_name": "Planner",
  "stereotype_domain": "Adaptive System Domain",
  "stereotype_type": "structure:Component",
  "implemented_by": [
    "function:pymape_hierarchical.hierarchical-cruise-control.pid"
  ]
}
```

Expected KDM shape:

```xml
<structureElement
    xsi:type="structure:Component"
    name="pid"
    stereotype="//@extensionFamily.0/@stereotype.2"
    implementation="...">
  <attribute tag="id" value="component:pid_planner_cruise_control_pid"/>
  <attribute tag="role" value="Planner"/>
</structureElement>
```

## Control loop

A recovered control loop is materialized as a `structure::Component` stereotyped as `Control Loop`.

KDM does not define a standard `structure::ControlLoop` metaclass. Therefore, the control loop is represented as:

```text
structure::Component <<Control Loop>>
```

Example JSON:

```json
{
  "id": "control_loop:loop",
  "name": "Loop Control Loop",
  "role": "Loop",
  "stereotype_name": "Control Loop",
  "stereotype_type": "structure:Component"
}
```

Expected KDM shape:

```xml
<structureElement
    xsi:type="structure:Component"
    name="Loop Control Loop"
    stereotype="//@extensionFamily.0/@stereotype.8">
  <attribute tag="id" value="control_loop:loop"/>
  <attribute tag="structure_kind" value="control_loop"/>
</structureElement>
```

## Subsystems

The managing and managed subsystems are materialized as `structure::Subsystem`.

Example:

```json
{
  "id": "subsystem:managing_subsystem",
  "name": "Managing Subsystem",
  "stereotype_name": "Managing Subsystem",
  "stereotype_type": "structure:Subsystem"
}
```

Expected KDM shape:

```xml
<structureElement
    xsi:type="structure:Subsystem"
    name="Managing Subsystem"
    stereotype="//@extensionFamily.0/@stereotype.11">
  ...
</structureElement>
```

## Nested containment

The generated KDM structure is nested to reflect the autonomic architecture.

Preferred hierarchy:

```text
Managing Subsystem
  └── CL Manager
        └── Control Loop
              ├── Monitor
              ├── Analyzer
              ├── Planner
              ├── Executor
              └── Knowledge
```

Managed subsystem hierarchy:

```text
Managed Subsystem
  ├── Sensor
  ├── Effector
  └── Measured Output
```

If no `CL Manager` is recovered, the `Control Loop` may be nested directly under the `Managing Subsystem`.

## Relationships

The generator materializes architecture relationships as `structure::StructureRelationship`. It also creates `core::AggregatedRelationship` entries when appropriate.

Examples of relationship types:

- `contains`
- `mapek_flow`
- `uses_knowledge`
- `subscribes_to`

Containment relationships are represented both as nested `structureElement` containment and as traceable relationships with `relationship_type = contains`.

## Stereotype domain

The generator creates an `extensionFamily` named `Adaptive System Domain` outside the KDM models and under the root KDM segment.

Example:

```xml
<extensionFamily name="Adaptive System Domain">
  <stereotype name="Monitor" type="structure:Component"/>
  <stereotype name="Analyzer" type="structure:Component"/>
  <stereotype name="Planner" type="structure:Component"/>
  <stereotype name="Executor" type="structure:Component"/>
  <stereotype name="Knowledge" type="structure:Component"/>
  <stereotype name="Reference Input" type="structure:Component"/>
  <stereotype name="Measured Output" type="structure:Component"/>
  <stereotype name="CL Manager" type="structure:Component"/>
  <stereotype name="Control Loop" type="structure:Component"/>
  <stereotype name="Sensor" type="structure:Component"/>
  <stereotype name="Effector" type="structure:Component"/>
  <stereotype name="Managing Subsystem" type="structure:Subsystem"/>
  <stereotype name="Managed Subsystem" type="structure:Subsystem"/>
</extensionFamily>
```
