from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PY2KDM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PY2KDM_PROJECT_ROOT))

from py2kdm_common.paths import ensure_parent, resolve_from_root
from kdm_dynamic_analysis.code_model_dynamic_enrichment_agent import CodeModelDynamicEnrichmentAgent
from kdm_dynamic_analysis.runtime_tracer import RuntimeTracer


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: dict, path: Path):
    path = ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def parse_prefixes(value: str | None):
    if not value:
        return None

    prefixes = tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )

    return prefixes or None


def run_trace(args):
    tracer = RuntimeTracer(
        project_root=resolve_from_root(args.project_root),
        output_path=resolve_from_root(args.output),
        include_returns=not args.no_returns,
        include_exceptions=not args.no_exceptions,
        max_events=args.max_events,
        scenario_name=args.scenario,
        mode=args.mode,
    )
    trace = tracer.run_script(args.script, args.script_args)
    print("Runtime trace generated.")
    print(f"- output: {resolve_from_root(args.output)}")
    print(f"- events: {len(trace.get('events', []))}")
    print(f"- status: {trace.get('metadata', {}).get('execution_status')}")
    return 0


def run_enrich(args):
    model = load_json(resolve_from_root(args.input))
    trace = load_json(resolve_from_root(args.trace))

    enriched = CodeModelDynamicEnrichmentAgent(
        filter_runtime_events=not args.no_filter,
        included_prefixes=parse_prefixes(args.include_prefixes),
    ).enrich(model, trace)

    save_json(enriched, resolve_from_root(args.output))
    summary = enriched.get("runtime_enrichment", {}).get("summary", {})
    print("Code model dynamically enriched.")
    print(f"- output: {resolve_from_root(args.output)}")
    print(f"- events: {summary.get('events', 0)}")
    print(f"- events after filter: {summary.get('events_after_filter', 0)}")
    print(f"- events filtered out: {summary.get('events_filtered_out', 0)}")
    print(f"- dynamic relationships added: {summary.get('dynamic_relationships_added', 0)}")
    print(f"- observed argument types: {summary.get('observed_argument_types', 0)}")
    print(f"- observed return types: {summary.get('observed_return_types', 0)}")
    print(f"- observed exceptions: {summary.get('observed_exceptions', 0)}")
    return 0


def run_trace_and_enrich(args):
    run_trace(argparse.Namespace(
        project_root=args.project_root,
        output=args.trace_output,
        script=args.script,
        script_args=args.script_args,
        no_returns=args.no_returns,
        no_exceptions=args.no_exceptions,
        max_events=args.max_events,
        scenario=args.scenario,
        mode=args.mode,
    ))
    return run_enrich(argparse.Namespace(
        input=args.input,
        trace=args.trace_output,
        output=args.output,
        no_filter=args.no_filter,
        include_prefixes=args.include_prefixes,
    ))


def parse_args():
    parser = argparse.ArgumentParser(description="Dynamic CodeModel enrichment for py2kdm.")
    sub = parser.add_subparsers(dest="command", required=True)

    trace = sub.add_parser("trace")
    trace.add_argument("--project-root", required=True)
    trace.add_argument("--script", required=True)
    trace.add_argument("--output", required=True)
    trace.add_argument("--scenario")
    trace.add_argument("--mode", choices=["desktop", "web"], default="desktop")
    trace.add_argument("--max-events", type=int, default=20000)
    trace.add_argument("--no-returns", action="store_true")
    trace.add_argument("--no-exceptions", action="store_true")
    trace.add_argument("script_args", nargs=argparse.REMAINDER)

    enrich = sub.add_parser("enrich")
    enrich.add_argument("--input", required=True)
    enrich.add_argument("--trace", required=True)
    enrich.add_argument("--output", required=True)
    enrich.add_argument("--no-filter", action="store_true")
    enrich.add_argument(
        "--include-prefixes",
        help=(
            "Comma-separated qualified-name prefixes to keep. "
            "Default: fixtures.,mape.,hierarchical_cruise_control_runtime."
        ),
    )

    both = sub.add_parser("trace-and-enrich")
    both.add_argument("--project-root", required=True)
    both.add_argument("--script", required=True)
    both.add_argument("--input", required=True)
    both.add_argument("--trace-output", required=True)
    both.add_argument("--output", required=True)
    both.add_argument("--scenario")
    both.add_argument("--mode", choices=["desktop", "web"], default="desktop")
    both.add_argument("--max-events", type=int, default=20000)
    both.add_argument("--no-returns", action="store_true")
    both.add_argument("--no-exceptions", action="store_true")
    both.add_argument("--no-filter", action="store_true")
    both.add_argument(
        "--include-prefixes",
        help=(
            "Comma-separated qualified-name prefixes to keep. "
            "Default: fixtures.,mape.,hierarchical_cruise_control_runtime."
        ),
    )
    both.add_argument("script_args", nargs=argparse.REMAINDER)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "trace":
        return run_trace(args)
    if args.command == "enrich":
        return run_enrich(args)
    if args.command == "trace-and-enrich":
        return run_trace_and_enrich(args)
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
