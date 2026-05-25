# JSON to KDM Mapping

The KDM generator transforms the intermediate or reviewed JSON model into KDM XMI using the KDM 1.4 Ecore metamodel.

```bash
python kdm_pyecore_generator/main.py \
  --input outputs/pymape_hierarchical/python_model.runtime_enriched.reviewed_architecture.json \
  --output outputs/pymape_hierarchical/model.runtime_enriched.reviewed.kdm.xmi
```

## CodeModel mapping

Static code elements map to KDM code elements.

| JSON concept | KDM concept |
|---|---|
| File/module | `code:CompilationUnit` |
| Class | `code:ClassUnit` |
| Function | `code:CallableUnit` |
| Method | `code:MethodUnit` |
| Parameter | `code:ParameterUnit` |
| Local variable | `code:StorableUnit` |
| Statement/body action | `action:ActionElement` |
| Body block | `action:BlockUnit` |

## Static relationships

| JSON relationship | KDM relation |
|---|---|
| call | `action::Calls` |
| create | `action::Creates` |
| read | `action::Reads` |
| write | `action::Writes` |
| return | `action::ExitFlow` or body-level return action |
| throw | `action::Throws` |
| exception flow | `action::ExceptionFlow` |
| type relation | `code::HasType` |
| value relation | `code::HasValue` |

## Runtime calls

Runtime calls are mapped using KDM semantics:

```text
relationships[type="runtime_calls"] -> action::Calls
```

They are not represented as `TaggedValue` objects.

The generator creates:

```text
CallableUnit / MethodUnit
  -> BlockUnit body
      -> ActionElement runtime_call:...
          -> action::Calls -> target CodeItem
```

If an equivalent static `Calls(source, target)` already exists, the runtime call is skipped to avoid duplication.

## StructureModel mapping

Architecture components and control-loop elements are mapped to KDM Structure Model elements. The reviewed architecture JSON determines what is materialized.

Typical mappings include:

| JSON structure element | KDM structure element |
|---|---|
| Component | `structure:Component` or equivalent structure abstraction |
| Subsystem | `structure:Subsystem` |
| Control loop | structure grouping element with adaptive stereotypes |
| Containment | structure containment relation |
| Architecture relationship | structure relationship or tagged stereotype relation, depending on metamodel support |

## Traceability

Traceability is maintained from architecture elements to code elements through implementation references and source regions. Code elements retain `SourceRef` and `SourceRegion` information so the generated XMI can be traced back to files and lines when available.

## Runtime-aware validation

The generator validation distinguishes unresolved static calls from static calls explained by runtime evidence. A static call without `target_id` may be counted as runtime-resolved when a matching `runtime_calls` relationship exists.

Example report fields:

```text
Runtime-resolved static calls: 31
Runtime Calls created: 64
Runtime Calls skipped as duplicates: 18
Runtime Calls unresolved: 37
```
