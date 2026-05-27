# Intermediate JSON model

The intermediate JSON model is the exchange format used across the py2kdm pipeline.

## Purpose

It decouples language-specific extraction from KDM generation, architecture recovery, dynamic analysis and validation. This makes it possible to enrich the model before generating KDM.

## Supported languages

| Language | Typical artifact |
|---|---|
| Python | `python_model.json` |
| Java | `java_model.json` |

## Main sections

Typical top-level sections include:

```text
project metadata
files
elements
classes
functions
methods
variables
parameters
relationships
runtime_enrichment
structure_model
ai_enrichment
architecture_review
```

Not every extractor emits every section. The KDM mapper is designed to support both Python-oriented and Java-oriented model shapes.

## Static relationships

The model can include calls, imports, type references, value references, returns and raises/throws.

## Body-level model

For rich KDM generation, methods and functions can include structured body items such as:

```text
assignment
return
call
object_creation
if
for
foreach
while
switch
try
catch
throw/raise
```

This body model enables KDM relations such as `Reads`, `Writes`, `Creates`, `Throws` and `ExceptionFlow`.

## Runtime relationships

After dynamic analysis, the model may include runtime-aware relationships such as observed calls, observed argument types, return types and exceptions.

## Architecture layer

After architecture recovery or human review, the model may include `structure_model`, containing architecture-level components, relationships and containment structures.
