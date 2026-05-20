# Architecture Recovery

## Recovery of Autonomic Architecture Abstractions

The architecture recovery process generates a candidate `StructureModel` for self-adaptive systems following the **Adaptive System Domain**. The process is rule-based and evidence-driven: architectural abstractions are promoted when there is explicit evidence in the intermediate Python model.

The recovery process supports the following autonomic abstractions:

- `Monitor`
- `Analyzer`
- `Planner`
- `Executor`
- `Knowledge`
- `Reference Input`
- `Measured Output`
- `Sensor`
- `Effector`
- `CL Manager`
- `Control Loop`
- `Managing Subsystem`
- `Managed Subsystem`

These abstractions are represented in the intermediate architecture JSON as components or subsystems with their corresponding role and stereotype metadata. Then, the KDM generator materializes them as KDM `structure::Component` or `structure::Subsystem` elements with Adaptive System Domain stereotypes.

## Evidence-driven recovery

The system does not create all possible autonomic abstractions by default. Instead, it recovers only those abstractions for which sufficient evidence is available in the source model.

For example:

- `Effector` is recovered from methods or elements whose names suggest actuation, such as `brake`, `gas`, `siren`, or `hazard_lights`.
- `Sensor` is recovered from elements whose names suggest measurement or observation, such as `sensor`, `read`, `measure`, `observe`, or `tachometer`.
- `Measured Output` is recovered from variable-like elements representing observed values, such as `current_speed`, `measured_distance`, or `actual_temperature`.
- `Reference Input` is recovered from variable-like elements representing desired values, such as `target_speed`, `desired_distance`, `setpoint`, `goal`, or `threshold`.

If no explicit evidence is found for one of these abstractions, the system does not invent it automatically. This prevents over-interpreting conventional code as autonomic architecture.

## JSON-to-KDM materialization

The architecture JSON is the source of architectural truth for KDM generation. Therefore, an abstraction is materialized in KDM only if it appears in the JSON `structure_model.components` or `structure_model.subsystems`.

For example, a recovered effector appears in the JSON as:

```json
{
  "id": "component:brake_effector_virtualcarspeed_brake",
  "name": "brake",
  "role": "Effector",
  "stereotype_name": "Effector",
  "stereotype_domain": "Adaptive System Domain",
  "stereotype_type": "structure:Component",
  "source": "rule_based_control_io",
  "status": "auto_accepted"
}
```

and is then materialized in KDM as a `structure::Component` stereotyped as `Effector`.

## Control loop containment

The generated architecture follows the containment hierarchy:

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

If no `CL Manager` is recovered, the `Control Loop` may be placed directly under the `Managing Subsystem`.

The `Managed Subsystem` is intentionally recovered only partially. The system does not attempt to reconstruct all managed-system internals. Instead, it focuses on externally relevant autonomic abstractions:

```text
Managed Subsystem
  ├── Sensor
  ├── Effector
  └── Measured Output
```

## Semantic construction rules

The architecture is not generated first and validated afterwards. Instead, the recovery process applies semantic construction rules during architecture construction.

These rules prevent invalid containment structures, such as:

```text
Managed Subsystem -> Planner
Managing Subsystem -> Sensor
Control Loop -> Effector
```

and allow valid structures such as:

```text
Managing Subsystem -> CL Manager
CL Manager -> Control Loop
Control Loop -> Monitor
Control Loop -> Planner
Managed Subsystem -> Effector
```

The generated JSON includes an `architecture_consistency` section that documents the rules applied, warnings, and blocked constructions. This section should be interpreted as a construction report, not as an external validation phase.

## Current interpretation of missing abstractions

`Reference Input`, `Measured Output`, `Sensor`, and `Effector` are supported by the architecture recovery model. However, they are only materialized when the system finds explicit evidence in the intermediate model.

For example, if the source code contains methods such as `brake`, `gas`, `siren`, or `hazard_lights`, the recovery process may infer `Effector` components. If no explicit names such as `target_speed`, `desired_distance`, `current_speed`, `measured_distance`, `sensor`, or `read_distance` are found, the corresponding `Reference Input`, `Measured Output`, or `Sensor` abstractions are not automatically created.

This behavior is intentional. It keeps the recovery conservative and avoids adding architectural abstractions without evidence.

## Documentation location

This page is intended to be included under the `Architecture Recovery` section of the MkDocs navigation:

```yaml
- Architecture Recovery:
    - Overview: architecture_recovery.md
    - MAPE-K Recovery Rules: mapek_recovery_rules.md
    - Structure Model Mapping: structure_model_mapping.md
    - KDM Traceability Links: kdm_traceability_links.md
```
