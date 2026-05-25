# GUI configuration

The **Configuration** tab separates project setup from pipeline execution.

## Setup modes

### Manual setup

Manual setup enables editing the fields directly in the GUI:

- project root;
- output directory;
- project name;
- dynamic scenarios;
- LLM provider and model.

Manual setup can be saved as a reusable config with **Save config as**.

### Config file

Config-file mode requires the user to load a JSON configuration. Manual fields are disabled because the config file is the source of truth.

A GUI config has the following shape:

```json
{
  "project": {
    "name": "pymape_hierarchical",
    "root": "examples/pymape_hierarchical",
    "output_dir": "outputs/pymape_hierarchical"
  },
  "dynamic_analysis": {
    "enabled": true,
    "scenarios": [
      {
        "name": "cruise_control",
        "script": "scenarios/cruise_control_scenario.py",
        "mode": "desktop",
        "enabled": true,
        "description": "Cruise-control behavior scenario"
      }
    ]
  },
  "agents": {
    "llm_provider": "none",
    "llm_model": "",
    "llm_timeout": 300
  }
}
```

## Scenario table

| Field | Meaning |
|---|---|
| Enabled | Whether the scenario is executed. |
| Name | Scenario name. It is used in trace file names. |
| Script | Path to the scenario script, relative to project root unless absolute. |
| Mode | Runtime mode. Currently `desktop` or `web`. |

## LLM provider

Supported providers are `none`, `gemini`, and `ollama`.

For Gemini, define either `GEMINI_API_KEY` or `GOOGLE_API_KEY` in the shell or in `.env` at project root.
