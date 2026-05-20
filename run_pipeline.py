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

    python run_pipeline.py --config configs/pymape_hierarchical.json

Expected config structure
-------------------------
{
  "project_name": "pymape_hierarchical",
  "language": "python",

  "input": {
    "source_path": "examples/pymape_hierarchical"
  },

  "outputs": {
    "intermediate_json": "outputs/pymape_hierarchical/python_model.json",
    "architecture_json": "outputs/pymape_hierarchical/python_model.architecture.json",
    "ai_architecture_json": "outputs/pymape_hierarchical/python_model.ai_architecture.json",
    "kdm_xmi": "outputs/pymape_hierarchical/model.kdm.xmi"
  },

  "architecture_recovery": {
    "enabled": true,
    "mode": "semi_automatic",
    "target_architecture": "mapek"
  },

  "kdm_generation": {
    "enabled": true,
    "validate": true,
    "input": "architecture_json"
  }
}

Notes
-----
- The Python extractor is still executed as an independent subproject.
- The KDM generator is still executed as an independent subproject.
- Architecture recovery is optional and works over the intermediate JSON.
- MAPE-K recovery is guarded by the AutonomicApplicabilityGate.
- Pre-review architecture agents can optionally enrich the architecture JSON.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parent


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)

    config = load_json(config_path)

    print_header("py2kdm pipeline")
    print(f"Config: {config_path}")

    validate_config(config)

    project_name = config.get("project_name", "unknown_project")
    print(f"Project: {project_name}")

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
            str(architecture_json).replace(".architecture.json", ".ai_architecture.json"),
        )
    )
    kdm_xmi = resolve_path(config["outputs"]["kdm_xmi"])

    ensure_parent(intermediate_json)
    ensure_parent(architecture_json)
    ensure_parent(ai_architecture_json)
    ensure_parent(kdm_xmi)

    run_extractor(
        source_path=source_path,
        output_path=intermediate_json,
        python_executable=args.python,
        skip=args.skip_extractor,
    )

    architecture_input_for_kdm = intermediate_json

    if is_enabled(config.get("architecture_recovery", {})) and not args.skip_architecture:
        run_architecture_recovery(
            input_path=intermediate_json,
            output_path=architecture_json,
            python_executable=args.python,
        )
        architecture_input_for_kdm = architecture_json

        if args.with_agents in {"pre-review", "all"}:
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
        help="Skip python_kdm_extractor and reuse the configured intermediate JSON.",
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
        choices=["none", "pre-review", "all"],
        default="none",
        help=(
            "Run architecture agents as part of the pipeline. "
            "Currently, pre-review agents are supported before human GUI review. "
            "The value 'all' currently behaves as pre-review inside run_pipeline; "
            "post-review should be run after exporting reviewed JSON from the GUI."
        ),
    )

    parser.add_argument(
        "--dynamic-trace",
        help=(
            "Optional dynamic trace JSON consumed by DynamicEvidenceAgent "
            "when --with-agents pre-review or all is used."
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


def run_extractor(
    source_path: Path,
    output_path: Path,
    python_executable: str,
    skip: bool,
) -> None:
    if skip:
        print_step("Python extractor skipped")

        if not output_path.exists():
            raise FileNotFoundError(
                f"Extractor was skipped, but intermediate JSON does not exist: "
                f"{output_path}"
            )

        return

    print_step("Running python_kdm_extractor")

    extractor_main = ROOT / "python_kdm_extractor" / "main.py"

    if not extractor_main.exists():
        raise FileNotFoundError(f"Extractor main.py not found: {extractor_main}")

    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    command = [
        python_executable,
        str(extractor_main),
        "--input",
        str(source_path),
        "--output",
        str(output_path),
    ]

    run_command(command, cwd=ROOT / "python_kdm_extractor")


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
        raise FileNotFoundError(f"Architecture recovery main.py not found: {recovery_main}")

    command = [
        python_executable,
        str(recovery_main),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

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

    Post-review agents should normally be executed after the user exports a
    reviewed JSON from the GUI.
    """

    print_step(f"Running architecture agents ({mode})")

    agents_main = ROOT / "kdm_architecture_agents" / "main.py"

    if not agents_main.exists():
        raise FileNotFoundError(f"Architecture agents main.py not found: {agents_main}")

    if not input_path.exists():
        raise FileNotFoundError(f"Architecture agents input JSON not found: {input_path}")

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
    default_input: Path,
) -> Path:
    """
    Selects which JSON file should feed the KDM generator.

    kdm_generation.input can be:

    - "intermediate_json";
    - "architecture_json";
    - an explicit path.
    """

    input_selector = config.get("kdm_generation", {}).get("input")

    if input_selector in {None, "default"}:
        return default_input

    if input_selector == "intermediate_json":
        return intermediate_json

    if input_selector == "architecture_json":
        return architecture_json

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


def add_extractor_to_path() -> None:
    extractor_path = ROOT / "python_kdm_extractor"

    if str(extractor_path) not in sys.path:
        sys.path.insert(0, str(extractor_path))


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
