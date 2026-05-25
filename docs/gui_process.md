# GUI process tab

The **Process** tab is dedicated to execution and runtime feedback.

## Pipeline actions

| Action | Description |
|---|---|
| Validate setup | Checks project paths, scenarios and LLM settings. |
| Run until Human Review | Runs extraction, optional dynamic analysis, architecture recovery and pre-review agents. |
| Run full pre-review pipeline | Same purpose as running the pipeline until a reviewable architecture proposal exists. |
| Clean project outputs | Cleans only the configured output directory, optionally with backup. |
| Generate final KDM | Generates the KDM XMI from the reviewed architecture JSON. |

## Setup validation

Pipeline actions validate the setup silently when the setup is valid. The explicit **Validate setup** button shows a success or failure dialog because it is an explicit validation request.

Errors block execution. Warnings and info messages are reported but do not necessarily block execution.

## Pipeline state

The state table is artifact-based. It shows whether expected artifacts exist:

```text
EXISTS: path/to/artifact
MISSING: path/to/artifact
```

## Error diagnostics

If a step fails, a compact diagnostic is shown above the full log. The diagnostic recognizes common causes such as missing Python modules, missing files, invalid JSON, KDM validation failures, and common Qt/PySide errors.

## Final KDM summary

After final KDM generation, the GUI reports the output path, file size, validation errors and warnings, and approximate counts of KDM elements such as `action:Calls` and `structure:Component`.
