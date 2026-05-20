# Testing Strategy

## Purpose

The testing strategy should verify each pipeline stage independently and then verify the complete end-to-end flow.

The main artifacts to test are:

- intermediate JSON;
- architecture-enriched JSON;
- generated KDM XMI;
- validation reports;
- documentation examples.

## Test levels

```text
Unit tests
  ↓
Subproject integration tests
  ↓
Pipeline tests
  ↓
Artifact inspection tests
```

## Extractor tests

Extractor tests should verify that Python code is correctly represented in the intermediate JSON.

Suggested cases:

- imports;
- classes and inheritance;
- functions and methods;
- parameters and local variables;
- calls and constructor calls;
- assignments;
- returns and raises;
- try, except and finally;
- decorators;
- nested body statements.

## Architecture recovery tests

Architecture recovery tests should verify:

- autonomic applicability gate decisions;
- role suggestions;
- promotion of role suggestions to components;
- control-loop grouping;
- recovery of `Sensor`, `Effector`, `ReferenceInput` and `MeasuredOutput`;
- containment relationships;
- semantic construction rules;
- architecture consistency report.

Example check:

```bash
python run_pipeline.py --config configs/pymape_hierarchical.json --skip-kdm
```

Then:

```bash
jq '.structure_model.architecture_consistency' \
  outputs/pymape_hierarchical/python_model.architecture.json
```

## KDM generation tests

KDM generation tests should verify:

- valid KDM XMI serialization;
- presence of inventory and code models;
- body actions and relations;
- type and value relations;
- exception and return-flow relations;
- architecture `StructureModel`;
- `extensionFamily` stereotypes;
- nested architecture containment;
- implementation references;
- aggregated relationships.

Example checks:

```bash
grep -n "extensionFamily\\|Adaptive System Domain" \
  outputs/pymape_hierarchical/model.kdm.xmi
```

```bash
grep -n "Managing Subsystem\\|Control Loop\\|Effector" \
  outputs/pymape_hierarchical/model.kdm.xmi
```

## Regression tests

Regression tests should ensure that:

- previous examples still generate JSON;
- previous examples still generate KDM;
- validation errors do not reappear;
- architecture recovery does not over-detect roles;
- conventional systems are not incorrectly classified as self-adaptive.

## Manual review checklist

For architecture recovery outputs, inspect:

- Are the promoted roles reasonable?
- Are weak suggestions excluded from components?
- Is `Control Loop` nested correctly?
- Are MAPE-K components inside the loop?
- Are `Effector`, `Sensor` and `Measured Output` inside `Managed Subsystem`?
- Are `Reference Input` elements only created when explicit evidence exists?
- Are stereotypes referenced correctly?
- Are implementation links present when code evidence exists?

## Documentation tests

Run:

```bash
mkdocs serve
```

Check that all pages from `mkdocs.yml` exist and render correctly.
