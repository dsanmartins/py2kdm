# GUI workflow

The GUI is organized into four top-level tabs:

```text
Configuration
Process
Human Review
Artifacts
```

## Configuration

The **Configuration** tab defines the project setup. It contains project root, output directory, setup mode, dynamic analysis scenarios, and pre-review agent settings.

The project can be configured in one of two mutually exclusive ways:

- **Manual setup**: the user edits fields in the GUI.
- **Config file**: the user loads a GUI configuration JSON and the loaded config becomes the source of truth.

## Process

The **Process** tab executes the pipeline and shows execution state. It contains pipeline actions, setup validation, pipeline state, error diagnostics, the final KDM generation summary, and the execution log.

The usual sequence is:

```text
Validate setup
Run until Human Review
```

After human review:

```text
Generate final KDM
```

## Human Review

The **Human Review** tab is where the user accepts, rejects, or marks suggestions as reviewed. It includes the architecture tree, properties panel, validation panel, traceability panel, AI suggestions panel, and graph view.

The reviewed architecture must be validated before it can be exported.

## Artifacts

The **Artifacts** tab lists generated JSON, trace, and XMI files. It displays descriptions and summaries so the user can inspect outputs without opening each file externally.

## End-to-end GUI checklist

```text
[ ] Configuration: choose Manual setup or Config file.
[ ] Configuration: verify project root and output directory.
[ ] Configuration: enable/disable dynamic scenarios.
[ ] Process: press Validate setup.
[ ] Process: press Run until Human Review.
[ ] Human Review: inspect components, relationships and suggestions.
[ ] Human Review: use Accept, Reject, or Mark reviewed.
[ ] Human Review: press Validate.
[ ] Human Review: export reviewed JSON.
[ ] Process: press Generate final KDM.
[ ] Artifacts: inspect JSON, traces and XMI.
```
