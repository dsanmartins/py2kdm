# Java extractor

The Java extractor is provided by the external `java2kdm` JAR. It parses Java source code and generates a rich intermediate JSON model consumed by `kdm_pyecore_generator`.

## Command used by the pipeline

```bash
java -jar tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar \
  /path/to/java/project \
  outputs/demo-java-project/java_model.json \
  schemas/python_model.schema.json
```

The schema path is currently reused as the shared intermediate-model schema entry point.

## Extracted information

The Java extractor records:

- packages and imports;
- classes, interfaces, enums and annotation declarations;
- fields and field annotations;
- methods and constructors;
- parameters and return types;
- local variables;
- method calls;
- assignments;
- return statements;
- object creations through `new X(...)`;
- control structures such as `if`, `for`, `foreach`, `while`, `switch`;
- `try`, `catch` and `throw`;
- Java annotations.

## Rich body model

Methods and constructors include a structured `body` section. Body items use normalized statement and control-structure descriptors, for example:

```json
{
  "type": "statement",
  "statementType": "assignment",
  "targets": ["lastUserName"],
  "value": "name",
  "lineStart": 45,
  "lineEnd": 45
}
```

and:

```json
{
  "type": "control_structure",
  "controlType": "try",
  "body": [],
  "catchClauses": [],
  "finallyBody": []
}
```

## KDM mapping impact

The rich Java JSON enables the KDM generator to create behavioral KDM relations such as:

```text
Calls
Reads
Writes
Creates
Throws
TryUnit
CatchUnit
ExceptionFlow
```

Java annotations are represented in KDM through:

```text
kdm:Annotation
JavaAnnotationUsage
TaggedValue
```

## Notes

The extractor preserves source expressions in fields such as `value`, while semantic fields such as `className` and `targetId` are normalized when possible.
