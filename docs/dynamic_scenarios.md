# Dynamic Runtime Scenarios

This document explains how to create standardized runtime scenarios for `py2kdm`.

A runtime scenario is a small Python script that executes one relevant behavior of a target system. The dynamic analysis module runs the scenario with `sys.setprofile`, records runtime calls, argument types, return types, and exceptions, and enriches the intermediate JSON model with factual runtime evidence.

The goal is not to test correctness. The goal is to activate representative execution paths so that `py2kdm` can recover runtime-supported code relations and architecture suggestions.

---

## 1. What is a runtime scenario?

A runtime scenario is an executable script placed inside the analyzed project, usually under a `scenarios/` directory.

Recommended structure:

```text
examples/my_project/
├── my_package/
├── main.py
└── scenarios/
    ├── _scenario_common.py
    ├── main_use_case_scenario.py
    ├── error_flow_scenario.py
    └── api_flow_scenario.py
```

Each scenario should activate a meaningful behavior:

```text
login_flow
create_order
process_payment
cruise_control
hold_distance
error_recovery
```

In `py2kdm`, the scenario is executed by:

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/my_project \
  --script scenarios/main_use_case_scenario.py \
  --input outputs/my_project/python_model.json \
  --trace-output outputs/my_project/runtime_trace.main_use_case.json \
  --output outputs/my_project/python_model.runtime_enriched.main_use_case.json \
  --scenario main_use_case \
  --mode desktop
```

The scenario name is stored in the trace and later in the generated runtime relationships.

---

## 2. Why scenarios are needed

Static analysis is useful, but Python is dynamic. Some relations are difficult or impossible to recover statically, for example:

```text
duck typing
dependency injection
decorators
runtime registration
dynamic dispatch
callbacks
framework-level invocation
observer or event-driven flows
```

Runtime scenarios complement the static model by observing what actually happens during execution.

The enrichment phase can add relationships such as:

```json
{
  "type": "runtime_calls",
  "source": "scenario_or_function.source",
  "target": "runtime.target.function",
  "relationship_level": "code",
  "source_level": "runtime",
  "evidence": "dynamic_trace",
  "scenario": "main_use_case"
}
```

During KDM generation, these facts are mapped to native KDM semantic relations:

```text
runtime_calls -> action::Calls
```

They are not represented primarily as `TaggedValue`.

---

## 3. Scenario contract

A scenario must satisfy this contract:

```text
1. It must be a Python script.
2. It must be executable with runpy.run_path(..., run_name="__main__").
3. It must terminate by itself.
4. It must activate one relevant use case or execution path.
5. It must avoid manual interaction.
6. It should avoid long-running servers unless it is a web/server scenario.
7. It should avoid destructive side effects.
8. It should use deterministic or bounded inputs.
9. It should keep sleeps and waits short.
10. It should be repeatable.
```

A scenario should not be a full test suite. It should be a focused runtime stimulus.

---

## 4. Naming convention

Use:

```text
<use_case>_scenario.py
```

Examples:

```text
cruise_control_scenario.py
hold_distance_scenario.py
login_flow_scenario.py
create_order_scenario.py
error_recovery_scenario.py
```

The scenario name passed to the dynamic-analysis CLI should normally match the file name without `_scenario.py`:

```bash
--scenario cruise_control
--script scenarios/cruise_control_scenario.py
```

---

## 5. Minimal scenario structure

A basic desktop scenario should look like this:

```python
#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    # Import the target system after making the project root importable.
    from my_project.service import Service

    service = Service()
    service.run_use_case()


if __name__ == "__main__":
    main()
```

For asynchronous systems:

```python
#!/usr/bin/env python3
from __future__ import annotations

import asyncio


async def main():
    from my_project.service import AsyncService

    service = AsyncService()
    await service.run_use_case()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Recommended scenario anatomy

A good scenario usually has these sections:

```text
1. Imports
2. Project-root setup
3. Optional dependency shims
4. Target system import
5. System initialization
6. Fixture or entity creation
7. Execution stimulus
8. Short waits if the system is asynchronous
9. Clean termination
```

Example skeleton:

```python
#!/usr/bin/env python3
from __future__ import annotations

import asyncio

from _scenario_common import import_application
from fixtures import SampleEntity


async def main():
    app = import_application()
    app.init(debug=False)

    entity = SampleEntity(name="example")

    await app.start_use_case(entity)

    entity.value = 10
    await asyncio.sleep(0.25)

    entity.value = 20
    await asyncio.sleep(0.25)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Example: `cruise_control_scenario.py`

The PyMAPE example uses a scenario that creates one car, starts cruise control, changes its speed, and calls the planner.

Relevant excerpt:

```python
from fixtures import VirtualCarSpeed
from _scenario_common import import_mape, load_hierarchical_module


async def main():
    mape = import_mape()
    hierarchical = load_hierarchical_module()

    mape.init(debug=False)

    car = VirtualCarSpeed(
        "Panda",
        speed=80,
        max_power=70,
        max_break=70,
        position=0,
    )

    await hierarchical.create_cruise_control(car)
```

Then the scenario stimulates the system by changing runtime state:

```python
car.speed = 70
await asyncio.sleep(0.25)

car.speed = 130
await asyncio.sleep(0.25)

car.speed = 95
await asyncio.sleep(0.25)
```

It also activates the planner explicitly:

```python
planner = mape.app["cruise_control_Panda.pid"]
planner.cruise_control(90)

car.speed = 100
await asyncio.sleep(0.25)
```

This scenario is useful because it activates runtime relations among:

```text
Monitor
Planner
Executor
Effector
VirtualCarSpeed
gas
brake
speed
```

---

## 8. Example: `hold_distance_scenario.py`

The second PyMAPE scenario creates two cars and activates both cruise control and distance control.

Relevant excerpt:

```python
car = VirtualCarSpeed(
    "Panda",
    speed=80,
    max_power=70,
    max_break=70,
    position=0,
)
car_in_front = VirtualCarSpeed(
    "Countach",
    speed=90,
    max_power=200,
    max_break=180,
    position=300,
)
```

The scenario activates multiple control loops:

```python
await hierarchical.create_cruise_control(car)
await hierarchical.create_cruise_control(car_in_front)
await hierarchical.create_hold_distance(car, car_in_front)
```

Then it changes the positions of both cars:

```python
car.position = 30
car_in_front.position = 260
await asyncio.sleep(0.30)

car.position = 80
car_in_front.position = 250
await asyncio.sleep(0.30)

car.position = 120
car_in_front.position = 240
await asyncio.sleep(0.30)
```

This scenario is useful because it activates runtime behavior that is not fully covered by the first scenario:

```text
distance monitoring
hold-distance planning
interaction between two runtime entities
position updates
additional executor/effector paths
```

---

## 9. Shared helper file: `_scenario_common.py`

When a project requires import setup, optional dependency shims, or dynamic loading, place this logic in:

```text
scenarios/_scenario_common.py
```

The PyMAPE scenarios use:

```python
from _scenario_common import import_mape, load_hierarchical_module
```

This keeps each scenario focused on the behavior being activated.

A common helper is useful for:

```text
adding project root to sys.path
installing optional dependency shims
loading modules whose filenames are not valid Python identifiers
centralizing test doubles for external services
avoiding duplicated setup logic
```

For example, in PyMAPE, the helper installs minimal shims for optional runtime dependencies such as Redis, REST, Uvicorn, Pydantic, InfluxDB and aiohttp. This makes bounded desktop tracing possible without requiring the full remote infrastructure.

Use shims only when the missing dependency is not part of the behavior being analyzed. If the dependency is central to the behavior, prefer running the real dependency or using a realistic test environment.

---

## 10. Desktop, web and CLI scenarios

### 10.1 Desktop/service scenario

Use this when the system exposes Python functions, classes or services.

```python
from my_project.service import OrderService

service = OrderService()
service.create_order(customer_id="c1", item_id="book")
service.confirm_order(order_id="o1")
```

This is the preferred style because the tracer can observe Python calls in the same process.

### 10.2 Web scenario

Use this when the system is activated through HTTP endpoints.

```python
from urllib import request
import json


def post_json(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def main():
    post_json("http://127.0.0.1:8000/orders", {"item": "book"})
```

For web systems, there are two possible strategies:

```text
1. The scenario starts the server and sends requests.
2. The server is started separately, and the scenario only sends requests.
```

The first strategy is easier for reproducibility. The second is closer to production but requires more orchestration.

### 10.3 CLI scenario

Use this when the system exposes a command-line entry point.

Prefer calling the Python function directly:

```python
from my_project.cli import main

main(["run", "--input", "sample"])
```

Avoid this if possible:

```python
subprocess.run(["python", "-m", "my_project", "run"])
```

A subprocess creates a different Python process. The current tracer will not observe internal calls in that separate process unless subprocess tracing is explicitly supported.

---

## 11. How scenarios are used in the pipeline

A single scenario can be run directly:

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/cruise_control_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json \
  --scenario cruise_control \
  --mode desktop
```

Multiple scenarios can be executed through `run_pipeline.py`:

```bash
python run_pipeline.py \
  --config configs/pymape_hierarchical.json \
  --enable-dynamic-analysis \
  --dynamic-project-root examples/pymape_hierarchical \
  --dynamic-scenario cruise_control:scenarios/cruise_control_scenario.py \
  --dynamic-scenario hold_distance:scenarios/hold_distance_scenario.py
```

The pipeline enriches the model sequentially:

```text
python_model.json
  -> runtime_trace.cruise_control.json
  -> python_model.runtime_enriched.cruise_control.json
  -> runtime_trace.hold_distance.json
  -> python_model.runtime_enriched.combined.json
```

---

## 12. Scenario configuration

A project may declare scenarios in a configuration file:

```json
{
  "dynamic_analysis": {
    "enabled": true,
    "mode": "desktop",
    "project_root": "examples/pymape_hierarchical",
    "scenarios": [
      {
        "name": "cruise_control",
        "script": "scenarios/cruise_control_scenario.py",
        "mode": "desktop",
        "description": "Activates one-car cruise control behavior."
      },
      {
        "name": "hold_distance",
        "script": "scenarios/hold_distance_scenario.py",
        "mode": "desktop",
        "description": "Activates two-car distance control behavior."
      }
    ]
  }
}
```

The GUI can expose the same information as a scenario table:

```text
Name            Script                                  Mode
cruise_control  scenarios/cruise_control_scenario.py    desktop
hold_distance   scenarios/hold_distance_scenario.py     desktop
```

---

## 13. What makes a good scenario?

A good scenario is:

```text
focused
bounded
repeatable
representative
safe
easy to run
independent of manual interaction
```

Good:

```python
car.speed = 130
await asyncio.sleep(0.25)
planner.cruise_control(90)
```

Bad:

```python
while True:
    app.run()
```

Good:

```python
service.create_order(...)
service.confirm_order(...)
```

Bad:

```python
input("Press enter to continue")
```

Good:

```python
fake_email_gateway = FakeEmailGateway()
```

Risky:

```python
real_email_gateway.send(...)
```

---

## 14. Scenario coverage strategy

Do not try to cover the whole system with one large scenario. Prefer several small scenarios.

Recommended set:

```text
main_success_flow_scenario.py
alternative_flow_scenario.py
error_flow_scenario.py
external_adapter_flow_scenario.py
```

For a self-adaptive system, try to cover:

```text
normal monitoring
planning decision
execution/action
knowledge access
sensor/effector interaction
exception or fallback path
```

For a web system, try to cover:

```text
health check
login or authentication
main business operation
read/query operation
error response
```

For a CLI system, try to cover:

```text
main command
subcommand
invalid input
configuration loading
output generation
```

---

## 15. How to know if a scenario worked

After running dynamic analysis, check the output:

```text
Runtime trace generated.
- events: N
- status: completed

Code model dynamically enriched.
- dynamic relationships added: N
- observed argument types: N
- observed return types: N
- observed exceptions: N
```

Useful checks:

```bash
jq '.metadata.execution_status, .metadata.event_count' \
  outputs/my_project/runtime_trace.main_use_case.json
```

```bash
jq '.runtime_enrichment.summary' \
  outputs/my_project/python_model.runtime_enriched.combined.json
```

```bash
jq '.relationships[] | select(.type=="runtime_calls") | {
  source: .source,
  target: .target,
  scenario: .scenario
}' outputs/my_project/python_model.runtime_enriched.combined.json
```

If there are very few events, the scenario may not be activating enough behavior.

If execution status is `failed`, inspect:

```bash
jq '.metadata.execution_error' \
  outputs/my_project/runtime_trace.main_use_case.json
```

---

## 16. Common problems

### Problem: `ModuleNotFoundError`

Usually the project root is not on `sys.path`.

Fix:

```python
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

### Problem: optional infrastructure dependency is missing

Example:

```text
No module named 'redis'
No module named 'fastapi'
No module named 'aiohttp'
```

Options:

```text
1. install the dependency;
2. use a lightweight shim in _scenario_common.py;
3. avoid the path that requires the dependency if it is not relevant.
```

### Problem: scenario never finishes

Avoid unbounded server loops. Use bounded calls, short sleeps and explicit termination.

### Problem: trace has many external-library events

Use filtering in the dynamic analysis module. The enrichment phase should prioritize calls that belong to the analyzed project.

### Problem: no dynamic relationships are added

Possible causes:

```text
the scenario did not call project code;
the tracer filtered out all events;
runtime names could not be matched to static model elements;
the behavior is executed in a subprocess.
```

---

## 17. Checklist for adding scenarios to a new project

Use this checklist:

```text
[ ] Create examples/my_project/scenarios/
[ ] Add _scenario_common.py if shared setup is needed.
[ ] Create one scenario per relevant use case.
[ ] Make each scenario terminate by itself.
[ ] Add deterministic fixture data.
[ ] Avoid manual input.
[ ] Avoid destructive side effects.
[ ] Run the scenario manually once.
[ ] Run trace-and-enrich.
[ ] Check execution_status == completed.
[ ] Check event_count > 0.
[ ] Check dynamic_relationships_added > 0.
[ ] Add the scenario to run_pipeline.py CLI or config.
[ ] Run the full pipeline.
[ ] Check KDM validation.
```

---

## 18. Recommended documentation inside each project

Each analyzed project should include:

```text
scenarios/README.md
```

with:

```text
scenario name
purpose
activated use case
expected main components
required dependencies
known limitations
command to run
```

Example:

```markdown
# Runtime scenarios

## cruise_control

Activates the one-car cruise-control loop.

Expected runtime evidence:
- speed monitor calls
- planner update
- gas/brake executor calls
- effector interactions

Command:

```bash
python kdm_dynamic_analysis/main.py trace-and-enrich \
  --project-root examples/pymape_hierarchical \
  --script scenarios/cruise_control_scenario.py \
  --input outputs/pymape_hierarchical/python_model.json \
  --trace-output outputs/pymape_hierarchical/runtime_trace.cruise_control.json \
  --output outputs/pymape_hierarchical/python_model.runtime_enriched.cruise_control.json \
  --scenario cruise_control \
  --mode desktop
```
```

---

## 19. Summary

Runtime scenarios are a standardized way to provide execution evidence to `py2kdm`.

They should be:

```text
small
bounded
repeatable
behavior-focused
safe
```

They allow the toolchain to move from:

```text
static-only CodeModel
```

to:

```text
static + runtime-enriched CodeModel
```

and then to a KDM model where runtime-observed calls are represented using native KDM semantics:

```text
action::Calls
```
