# JSON to KDM mapping

The KDM generator maps the intermediate JSON model to KDM XMI using the KDM 1.4 Ecore metamodel.

## Code model

Static code elements are mapped to KDM CodeModel elements such as:

```text
CompilationUnit
ClassUnit
MethodUnit
CallableUnit
ParameterUnit
StorableUnit
BlockUnit
ActionElement
```

## Behavioral mapping

When the intermediate JSON includes structured body information, the generator maps body-level behavior to KDM relations and elements:

| JSON evidence | KDM representation |
|---|---|
| method call | `ActionElement` + `Calls` |
| variable read | `Reads` |
| assignment target | `Writes` |
| object creation | `Creates` |
| return expression | `ActionElement kind="return"` + `Reads` or `return_flow="void"` |
| throw/raise | `Throws` |
| try/catch | `TryUnit`, `CatchUnit`, `ExceptionFlow` |
| literal/expression value | `Value`, `HasValue` |

Executable body actions must be contained in a `BlockUnit`, not directly under a `MethodUnit` or `CallableUnit`.

## Java and Python body formats

Python and Java use related but not identical JSON shapes. The mapper supports both:

```text
files[*].classes[*].methods[*]
files[*].functions[*]
elements[*].methods[*]
```

It also handles both snake_case and camelCase variants such as:

```text
statement_type / statementType
control_type / controlType
line_start / lineStart
line_end / lineEnd
catch_clauses / catchClauses
finally_body / finallyBody
```

## Annotations and decorators

Java annotations and Python decorators are not emitted as loose `Attribute` tags. They are modeled through:

```text
kdm:Annotation
Stereotype
TaggedValue
```

The generator creates language-specific stereotypes such as:

```text
JavaAnnotationUsage
PythonDecoratorUsage
```

## Structure model

Materialized architecture elements from `structure_model` are mapped to KDM StructureModel elements. Adaptive-system semantics can be represented through KDM extension mechanisms such as stereotypes and tagged values.

## Debug attribute policy

The final XMI should not contain internal debug tags such as `body_id`, `callable_body_id`, `source_call_name`, `constructor_resolution`, `constructor_target`, `resolution`, `unresolved_return_value`, or `unresolved_exception_type_target`.
