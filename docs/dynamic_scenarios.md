# Dynamic scenarios

A dynamic scenario is a small Python script that executes a meaningful behavior of the target project. It is the dynamic-analysis equivalent of a test or use case.

## Scenario requirements

A good scenario should import the project consistently, execute a relevant behavior, terminate deterministically, avoid manual input, avoid unplanned external services, and be documented.

## Recommended template

```python
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    # Import and exercise the target behavior here.
    pass


if __name__ == "__main__":
    main()
```

## GUI fields

| Field | Meaning |
|---|---|
| Enabled | Whether the scenario should be run. |
| Name | Name used in output trace file names. |
| Script | Path to the scenario script. |
| Mode | Runtime mode, currently `desktop` or `web`. |

## Example scenarios

For the PyMAPE example, scenario scripts are stored under:

```text
examples/pymape_hierarchical/scenarios/
```

These scripts are examples only. New projects should provide their own scenario scripts or load them through a GUI config file.
