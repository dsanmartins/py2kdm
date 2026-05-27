# KDM regression checks

KDM regression checks are integrated into `run_pipeline.py` and run after KDM XMI generation when enabled.

## Purpose

The checks protect against regressions that are not always caught by schema validation alone. They are especially useful after changing the KDM mapper or the intermediate JSON extractors.

## Default checks

The pipeline verifies that:

- no executable `ActionElement` is directly contained by a `MethodUnit` or `CallableUnit`;
- every `return` action has a `Reads` relation or `return_flow="void"`;
- every `SourceRegion` has either `file` or `path`;
- known debug or redundant attributes are absent from the final XMI.

Examples of forbidden debug or redundant tags include:

```text
body_id
callable_body_id
source_call_name
constructor_resolution
constructor_target
resolution
unresolved_return_value
unresolved_exception_type_target
decorators
declared_type
resolved_type
parameter_kind
parameter_index
method_kind
signature
return_type
resolved_return_type
modifiers
annotations
json_type
qualified_signature
source_line
relationship_type
called_signature
resolution_status
unresolved_target_name
line_start
line_end
assigned_value_kind
```

## Minimum count checks

A config can require minimum counts for specific KDM elements or relations:

```json
"regression_check": {
  "enabled": true,
  "minimum_counts": {
    "Reads": 1,
    "Writes": 1,
    "Creates": 1,
    "Throws": 1,
    "TryUnit": 1,
    "CatchUnit": 1,
    "ExceptionFlow": 1
  }
}
```

This is useful for examples that are expected to exercise body-level behavior.

## Output

A successful run prints a summary such as:

```text
--- Running KDM regression checks ---
KDM regression summary:
- Language: java
- ActionElement: 135
- BlockUnit: 15
- Calls: 35
- Creates: 9
- Reads: 58
- Writes: 16
- Throws: 5
- TryUnit: 2
- CatchUnit: 2
- ExceptionFlow: 2
KDM regression checks passed.
```

If a check fails, the pipeline stops with a regression error.
