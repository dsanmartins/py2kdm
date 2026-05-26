#!/usr/bin/env python3
"""
py2kdm configurable pipeline runner.

This script separates py2kdm implementation code from example systems,
configuration files and generated outputs.

Typical usage
-------------
From the py2kdm root directory:

    python run_pipeline.py --config configs/three_layer_system.json

or:

    python run_pipeline.py --config configs/demo_java_project.json

Expected config structure
-------------------------
{
  "project_name": "demo-java-project",
  "language": "java",

  "input": {
    "source_path": "/path/to/java/project"
  },

  "outputs": {
    "intermediate_json": "outputs/demo-java-project/java_model.json",
    "architecture_json": "outputs/demo-java-project/java_model.architecture.json",
    "ai_architecture_json": "outputs/demo-java-project/java_model.ai_architecture.json",
    "runtime_enriched_json": "outputs/demo-java-project/java_model.runtime_enriched.combined.json",
    "kdm_xmi": "outputs/demo-java-project/model.kdm.xmi"
  },

  "java_extractor": {
    "jar_path": "tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar",
    "schema_path": "schemas/python_model.schema.json"
  },

  "dynamic_analysis": {
    "enabled": false
  },

  "architecture_recovery": {
    "enabled": false
  },

  "kdm_generation": {
    "enabled": false,
    "validate": true,
    "input": "intermediate_json"
  }
}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parent


class DynamicScenario:
    """
    Runtime scenario descriptor used by the generic dynamic analysis pipeline.

    The pipeline does not know project-specific scenarios. It only receives
    scenario descriptors through CLI arguments or configuration files.
    """

    def __init__(self, name: str, script: str, script_args: list[str] | None = None):
        if not name:
            raise ValueError("Dynamic scenario name cannot be empty.")

        if not script:
            raise ValueError("Dynamic scenario script cannot be empty.")

        self.name = name
        self.script = script
        self.script_args = script_args or []


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)

    config = load_json(config_path)

    print_header("py2kdm pipeline")
    print(f"Config: {config_path}")

    validate_config(config)

    project_name = config.get("project_name", "unknown_project")
    language = config.get("language", "python").lower().strip()

    print(f"Project: {project_name}")
    print(f"Language: {language}")

    source_path = resolve_path(config["input"]["source_path"])

    intermediate_json = resolve_path(config["outputs"]["intermediate_json"])

    architecture_json = resolve_path(
        config["outputs"].get(
            "architecture_json",
            str(intermediate_json).replace(".json", ".architecture.json"),
        )
    )

    ai_architecture_json = resolve_path(
        config["outputs"].get(
            "ai_architecture_json",
            str(architecture_json).replace(
                ".architecture.json",
                ".ai_architecture.json",
            ),
        )
    )

    kdm_xmi = resolve_path(config["outputs"]["kdm_xmi"])

    ensure_parent(intermediate_json)
    ensure_parent(architecture_json)
    ensure_parent(ai_architecture_json)
    ensure_parent(kdm_xmi)

    run_extractor(
        language=language,
        source_path=source_path,
        output_path=intermediate_json,
        python_executable=args.python,
        skip=args.skip_extractor,
        config=config,
    )

    model_input_for_recovery = intermediate_json

    dynamic_outputs = run_dynamic_analysis_if_requested(
        config=config,
        args=args,
        source_path=source_path,
        intermediate_json=intermediate_json,
        python_executable=args.python,
    )

    if dynamic_outputs.get("runtime_enriched_json"):
        model_input_for_recovery = dynamic_outputs["runtime_enriched_json"]

    architecture_input_for_kdm = model_input_for_recovery

    if is_enabled(config.get("architecture_recovery", {})) and not args.skip_architecture:
        run_architecture_recovery(
            input_path=model_input_for_recovery,
            output_path=architecture_json,
            python_executable=args.python,
        )

        architecture_input_for_kdm = architecture_json

        if args.with_agents == "pre-review":
            run_architecture_agents(
                mode="pre-review",
                input_path=architecture_json,
                output_path=ai_architecture_json,
                dynamic_trace=args.dynamic_trace,
                python_executable=args.python,
            )
            architecture_input_for_kdm = ai_architecture_json
    else:
        print_step("Architecture recovery skipped")

    if is_enabled(config.get("kdm_generation", {})) and not args.skip_kdm:
        kdm_input = select_kdm_input(
            config=config,
            intermediate_json=intermediate_json,
            architecture_json=architecture_json,
            runtime_enriched_json=dynamic_outputs.get("runtime_enriched_json"),
            default_input=architecture_input_for_kdm,
        )

        run_kdm_generator(
            input_path=kdm_input,
            output_path=kdm_xmi,
            validate=bool(config.get("kdm_generation", {}).get("validate", True)),
            python_executable=args.python,
        )
    else:
        print_step("KDM generation skipped")

    print_header("Pipeline completed")
    print(f"Intermediate JSON: {intermediate_json}")

    if dynamic_outputs.get("runtime_enriched_json"):
        print(f"Runtime-enriched JSON: {dynamic_outputs['runtime_enriched_json']}")

    for trace_path in dynamic_outputs.get("runtime_traces", []):
        if trace_path.exists():
            print(f"Runtime trace: {trace_path}")

    if architecture_json.exists():
        print(f"Architecture JSON: {architecture_json}")

    if ai_architecture_json.exists():
        print(f"AI Architecture JSON: {ai_architecture_json}")

    if kdm_xmi.exists():
        print(f"KDM XMI: {kdm_xmi}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the configurable py2kdm pipeline."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to a JSON configuration file.",
    )

    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for subprocesses.",
    )

    parser.add_argument(
        "--skip-extractor",
        action="store_true",
        help="Skip static extraction and reuse the configured intermediate JSON.",
    )

    parser.add_argument(
        "--skip-architecture",
        action="store_true",
        help="Skip architecture recovery even if enabled in the config.",
    )

    parser.add_argument(
        "--skip-kdm",
        action="store_true",
        help="Skip KDM generation even if enabled in the config.",
    )

    parser.add_argument(
        "--with-agents",
        choices=["none", "pre-review"],
        default="none",
        help=(
            "Run pre-review architecture agents before human GUI review. "
            "After human review, the reviewed architecture is treated as authoritative "
            "and is used directly for KDM generation."
        ),
    )

    parser.add_argument(
        "--dynamic-trace",
        help=(
            "Optional dynamic trace JSON consumed by DynamicEvidenceAgent "
            "when --with-agents pre-review is used."
        ),
    )

    parser.add_argument(
        "--enable-dynamic-analysis",
        action="store_true",
        help=(
            "Enable generic runtime tracing and CodeModel enrichment before "
            "architecture recovery and KDM generation."
        ),
    )

    parser.add_argument(
        "--dynamic-project-root",
        help=(
            "Project root used by kdm_dynamic_analysis. Defaults to "
            "dynamic_analysis.project_root from config, or input.source_path."
        ),
    )

    parser.add_argument(
        "--dynamic-mode",
        choices=["desktop", "web"],
        help=(
            "Dynamic analysis mode. Defaults to dynamic_analysis.mode from "
            "config, or desktop."
        ),
    )

    parser.add_argument(
        "--dynamic-scenario",
        action="append",
        default=[],
        metavar="NAME:SCRIPT",
        help=(
            "Dynamic scenario descriptor. Can be repeated. The pipeline does "
            "not hardcode scenarios; each descriptor has the form "
            "name:relative_script_path."
        ),
    )

    return parser.parse_args()


def validate_config(config: Dict[str, Any]) -> None:
    required_paths = [
        ("input", "source_path"),
        ("outputs", "intermediate_json"),
        ("outputs", "kdm_xmi"),
    ]

    for section, key in required_paths:
        if section not in config or key not in config[section]:
            raise ValueError(f"Missing config field: {section}.{key}")

    if "project_name" not in config:
        print("Warning: config.project_name is missing; using unknown_project.")

    language = config.get("language", "python").lower().strip()

    if language not in {"python", "java"}:
        raise ValueError(
            f"Unsupported language '{language}'. Supported values: python, java."
        )


def run_extractor(
    language: str,
    source_path: Path,
    output_path: Path,
    python_executable: str,
    skip: bool,
    config: Dict[str, Any],
) -> None:
    if skip:
        print_step("Static extractor skipped")

        if not output_path.exists():
            raise FileNotFoundError(
                "Extractor was skipped, but intermediate JSON does not exist: "
                f"{output_path}"
            )

        return

    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    if language == "python":
        run_python_extractor(
            source_path=source_path,
            output_path=output_path,
            python_executable=python_executable,
        )
        return

    if language == "java":
        java_config = config.get("java_extractor", {})

        jar_path = resolve_path(
            java_config.get(
                "jar_path",
                "tools/java2kdm/java2kdm-1.0-SNAPSHOT.jar",
            )
        )

        schema_path = resolve_path(
            java_config.get(
                "schema_path",
                "schemas/python_model.schema.json",
            )
        )

        run_java_extractor(
            source_path=source_path,
            output_path=output_path,
            jar_path=jar_path,
            schema_path=schema_path,
        )
        return

    raise ValueError(f"Unsupported language for static extraction: {language}")


def run_python_extractor(
    source_path: Path,
    output_path: Path,
    python_executable: str,
) -> None:
    print_step("Running python_kdm_extractor")

    extractor_main = ROOT / "python_kdm_extractor" / "main.py"

    if not extractor_main.exists():
        raise FileNotFoundError(f"Extractor main.py not found: {extractor_main}")

    ensure_parent(output_path)

    command = [
        python_executable,
        str(extractor_main),
        "--input",
        str(source_path),
        "--output",
        str(output_path),
    ]

    run_command(command, cwd=ROOT / "python_kdm_extractor")


def run_java_extractor(
    source_path: Path,
    output_path: Path,
    jar_path: Path,
    schema_path: Path | None = None,
) -> None:
    print_step("Running java2kdm extractor")

    if not jar_path.exists():
        raise FileNotFoundError(f"java2kdm jar not found: {jar_path}")

    if schema_path is not None and not schema_path.exists():
        raise FileNotFoundError(f"java2kdm schema not found: {schema_path}")

    ensure_parent(output_path)

    command = [
        "java",
        "-jar",
        str(jar_path),
        str(source_path),
        str(output_path),
    ]

    if schema_path is not None:
        command.append(str(schema_path))

    run_command(command, cwd=ROOT)


def run_architecture_recovery(
    input_path: Path,
    output_path: Path,
    python_executable: str,
) -> None:
    print_step("Running architecture recovery")

    if not input_path.exists():
        raise FileNotFoundError(f"Intermediate JSON not found: {input_path}")

    recovery_main = ROOT / "kdm_architecture_recovery" / "main.py"

    if not recovery_main.exists():
        raise FileNotFoundError(
            f"Architecture recovery main.py not found: {recovery_main}"
        )

    ensure_parent(output_path)

    command = [
        python_executable,
        str(recovery_main),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    run_command(command, cwd=ROOT)


def run_dynamic_analysis_if_requested(
    config: Dict[str, Any],
    args: argparse.Namespace,
    source_path: Path,
    intermediate_json: Path,
    python_executable: str,
) -> Dict[str, Any]:
    """
    Runs generic dynamic analysis if enabled.

    The pipeline is project-agnostic. It does not know scenario names or
    project-specific behavior. Scenarios are provided by configuration or CLI.
    """

    dynamic_config = config.get("dynamic_analysis", {})
    enabled = bool(args.enable_dynamic_analysis or dynamic_config.get("enabled", False))

    if not enabled:
        print_step("Dynamic analysis skipped")
        return {
            "runtime_enriched_json": None,
            "runtime_traces": [],
        }

    scenarios = collect_dynamic_scenarios(dynamic_config, args.dynamic_scenario)

    if not scenarios:
        raise ValueError(
            "Dynamic analysis is enabled, but no scenarios were provided. "
            "Use --dynamic-scenario name:script or dynamic_analysis.scenarios."
        )

    project_root = resolve_path(
        args.dynamic_project_root
        or dynamic_config.get("project_root")
        or source_path
    )

    mode = args.dynamic_mode or dynamic_config.get("mode", "desktop")

    runtime_enriched_json = resolve_path(
        config.get("outputs", {}).get(
            "runtime_enriched_json",
            str(intermediate_json).replace(".json", ".runtime_enriched.combined.json"),
        )
    )

    ensure_parent(runtime_enriched_json)

    print_step("Running dynamic analysis")
    print(f"Dynamic project root: {project_root}")
    print(f"Dynamic mode: {mode}")
    print(f"Dynamic scenarios: {', '.join(s.name for s in scenarios)}")

    current_input = intermediate_json
    runtime_traces: list[Path] = []

    for index, scenario in enumerate(scenarios):
        is_last = index == len(scenarios) - 1

        trace_output = intermediate_json.with_name(
            f"runtime_trace.{scenario.name}.json"
        )

        if is_last:
            enriched_output = runtime_enriched_json
        else:
            enriched_output = intermediate_json.with_name(
                f"{intermediate_json.stem}.runtime_enriched.{scenario.name}.json"
            )

        run_dynamic_trace_and_enrich(
            project_root=project_root,
            script=scenario.script,
            input_path=current_input,
            trace_output=trace_output,
            output_path=enriched_output,
            scenario_name=scenario.name,
            mode=mode,
            script_args=scenario.script_args,
            python_executable=python_executable,
        )

        runtime_traces.append(trace_output)
        current_input = enriched_output

    return {
        "runtime_enriched_json": runtime_enriched_json,
        "runtime_traces": runtime_traces,
    }


def collect_dynamic_scenarios(
    dynamic_config: Dict[str, Any],
    cli_scenarios: list[str],
) -> List[DynamicScenario]:
    scenarios: list[DynamicScenario] = []

    for item in dynamic_config.get("scenarios", []):
        scenarios.append(parse_config_dynamic_scenario(item))

    for item in cli_scenarios:
        scenarios.append(parse_cli_dynamic_scenario(item))

    return scenarios


def parse_config_dynamic_scenario(item: Any) -> DynamicScenario:
    if isinstance(item, str):
        return parse_cli_dynamic_scenario(item)

    if not isinstance(item, dict):
        raise ValueError(
            "dynamic_analysis.scenarios entries must be either strings "
            "name:script or objects with name and script."
        )

    return DynamicScenario(
        name=item.get("name"),
        script=item.get("script"),
        script_args=list(item.get("args", [])),
    )


def parse_cli_dynamic_scenario(value: str) -> DynamicScenario:
    if ":" not in value:
        raise ValueError(
            f"Invalid dynamic scenario '{value}'. Expected format: name:script"
        )

    name, script = value.split(":", 1)

    return DynamicScenario(
        name=name.strip(),
        script=script.strip(),
    )


def run_dynamic_trace_and_enrich(
    project_root: Path,
    script: str,
    input_path: Path,
    trace_output: Path,
    output_path: Path,
    scenario_name: str,
    mode: str,
    script_args: list[str],
    python_executable: str,
) -> None:
    print_step(f"Running dynamic scenario: {scenario_name}")

    dynamic_main = ROOT / "kdm_dynamic_analysis" / "main.py"

    if not dynamic_main.exists():
        raise FileNotFoundError(f"Dynamic analysis main.py not found: {dynamic_main}")

    if not input_path.exists():
        raise FileNotFoundError(f"Dynamic analysis input JSON not found: {input_path}")

    ensure_parent(trace_output)
    ensure_parent(output_path)

    command = [
        python_executable,
        str(dynamic_main),
        "trace-and-enrich",
        "--project-root",
        str(project_root),
        "--script",
        script,
        "--input",
        str(input_path),
        "--trace-output",
        str(trace_output),
        "--output",
        str(output_path),
        "--scenario",
        scenario_name,
        "--mode",
        mode,
    ]

    if script_args:
        command.extend(script_args)

    run_command(command, cwd=ROOT)


def run_architecture_agents(
    mode: str,
    input_path: Path,
    output_path: Path,
    dynamic_trace: str | None,
    python_executable: str,
) -> None:
    """
    Runs architecture agents over an architecture-enriched JSON model.

    In the pipeline, this is currently intended for the pre-review phase:

        architecture recovery -> pre-review agents -> GUI review

    Only pre-review agents are supported in the default pipeline. After the user
    exports a reviewed JSON from the GUI, that reviewed model should feed KDM
    generation directly.
    """

    print_step(f"Running architecture agents ({mode})")

    agents_main = ROOT / "kdm_architecture_agents" / "main.py"

    if not agents_main.exists():
        raise FileNotFoundError(f"Architecture agents main.py not found: {agents_main}")

    if not input_path.exists():
        raise FileNotFoundError(f"Architecture agents input JSON not found: {input_path}")

    ensure_parent(output_path)

    command = [
        python_executable,
        str(agents_main),
        "--mode",
        mode,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    if dynamic_trace:
        trace_path = resolve_path(dynamic_trace)

        if not trace_path.exists():
            raise FileNotFoundError(f"Dynamic trace JSON not found: {trace_path}")

        command.extend(["--dynamic-trace", str(trace_path)])

    run_command(command, cwd=ROOT)


def run_kdm_generator(
    input_path: Path,
    output_path: Path,
    validate: bool,
    python_executable: str,
) -> None:
    print_step("Running kdm_pyecore_generator")

    generator_main_candidates = [
        ROOT / "kdm_pyecore_generator" / "main.py",
        ROOT / "kdm_pyecore_generator" / "src" / "main.py",
    ]

    generator_main = next(
        (candidate for candidate in generator_main_candidates if candidate.exists()),
        None,
    )

    if generator_main is None:
        raise FileNotFoundError(
            "Could not find kdm_pyecore_generator/main.py or "
            "kdm_pyecore_generator/src/main.py"
        )

    if not input_path.exists():
        raise FileNotFoundError(f"KDM input JSON not found: {input_path}")

    ensure_parent(output_path)

    command = [
        python_executable,
        str(generator_main),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    if not validate:
        command.append("--no-validation")

    run_command(command, cwd=ROOT / "kdm_pyecore_generator")


def select_kdm_input(
    config: Dict[str, Any],
    intermediate_json: Path,
    architecture_json: Path,
    runtime_enriched_json: Path | None,
    default_input: Path,
) -> Path:
    """
    Selects which JSON file should feed the KDM generator.

    kdm_generation.input can be:

    - "intermediate_json";
    - "architecture_json";
    - "runtime_enriched_json";
    - an explicit path.
    """

    input_selector = config.get("kdm_generation", {}).get("input")

    if input_selector in {None, "default"}:
        return default_input

    if input_selector == "intermediate_json":
        return intermediate_json

    if input_selector == "architecture_json":
        return architecture_json

    if input_selector == "runtime_enriched_json":
        if runtime_enriched_json is None:
            raise ValueError(
                "kdm_generation.input is runtime_enriched_json, but dynamic "
                "analysis did not produce a runtime-enriched JSON."
            )

        return runtime_enriched_json

    return resolve_path(input_selector)


def run_command(command: list[str], cwd: Path) -> None:
    print("$ " + " ".join(command))

    completed = subprocess.run(command, cwd=str(cwd))

    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: "
            + " ".join(command)
        )


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)

    if path.is_absolute():
        return path

    return (ROOT / path).resolve()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def is_enabled(section: Dict[str, Any]) -> bool:
    return bool(section.get("enabled", True))


def print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_step(title: str) -> None:
    print()
    print(f"--- {title} ---")


if __name__ == "__main__":
    raise SystemExit(main())
