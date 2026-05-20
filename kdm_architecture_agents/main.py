from pathlib import Path
import argparse
import json
import sys


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PY2KDM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PY2KDM_PROJECT_ROOT))


from py2kdm_common.paths import ensure_parent, resolve_from_root

from kdm_architecture_agents.agent_context_builder import AgentContextBuilder
from kdm_architecture_agents.pre_review.architecture_enrichment_agent import (
    ArchitectureEnrichmentAgent,
)
from kdm_architecture_agents.pre_review.dynamic_evidence_agent import (
    DynamicEvidenceAgent,
)
from kdm_architecture_agents.post_review.kdm_readiness_agent import (
    KDMReadinessAgent,
)
from kdm_architecture_agents.post_review.review_consistency_agent import (
    ReviewConsistencyAgent,
)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: dict, path: Path):
    path = ensure_parent(path)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def run_pre_review(model, trace_path=None):
    """
    Runs agents that enrich the architecture proposal before human review.

    These agents should not directly materialize KDM elements. They only add
    suggestions under `ai_enrichment`.
    """

    context = AgentContextBuilder().build(model)

    dynamic_suggestions = DynamicEvidenceAgent().run(
        model=model,
        context=context,
        trace_path=trace_path,
    )
    enrichment_suggestions = ArchitectureEnrichmentAgent().run(
        model=model,
        context=context,
    )

    all_suggestions = dynamic_suggestions + enrichment_suggestions

    model.setdefault("ai_enrichment", {})
    model["ai_enrichment"].update(
        {
            "status": "pre_review_enriched",
            "source": "kdm_architecture_agents.pre_review",
            "suggestions": all_suggestions,
            "summary": {
                "suggestions": len(all_suggestions),
                "dynamic_suggestions": len(dynamic_suggestions),
                "architecture_suggestions": len(enrichment_suggestions),
            },
        }
    )

    return model


def run_post_review(model):
    """
    Runs agents that audit the reviewed architecture before KDM generation.

    These agents should not overwrite human decisions. They only add findings
    under `post_review_ai_check`.
    """

    context = AgentContextBuilder().build(model)

    consistency_findings = ReviewConsistencyAgent().run(
        model=model,
        context=context,
    )
    readiness_findings = KDMReadinessAgent().run(
        model=model,
        context=context,
    )

    all_findings = consistency_findings + readiness_findings

    blocking = [
        finding for finding in all_findings
        if finding.get("severity") == "blocking"
        or finding.get("status") == "ai_blocking_issue"
    ]

    model.setdefault("post_review_ai_check", {})
    model["post_review_ai_check"].update(
        {
            "status": "blocking_issues_found" if blocking else "ready_with_warnings",
            "source": "kdm_architecture_agents.post_review",
            "findings": all_findings,
            "summary": {
                "findings": len(all_findings),
                "blocking": len(blocking),
                "warnings": len(all_findings) - len(blocking),
                "kdm_ready": len(blocking) == 0,
            },
        }
    )

    return model


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run py2kdm architecture agents before or after human review."
        )
    )

    parser.add_argument(
        "--mode",
        choices=["pre-review", "post-review", "all"],
        required=True,
        help=(
            "pre-review adds AI suggestions before GUI review; post-review "
            "checks reviewed JSON before KDM generation; all runs both."
        ),
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input architecture JSON.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON enriched with agent results.",
    )

    parser.add_argument(
        "--dynamic-trace",
        help="Optional dynamic trace JSON used by DynamicEvidenceAgent.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    input_path = resolve_from_root(args.input)
    output_path = ensure_parent(resolve_from_root(args.output))
    trace_path = (
        resolve_from_root(args.dynamic_trace)
        if args.dynamic_trace
        else None
    )

    model = load_json(input_path)

    if args.mode in {"pre-review", "all"}:
        model = run_pre_review(model, trace_path=trace_path)

    if args.mode in {"post-review", "all"}:
        model = run_post_review(model)

    save_json(model, output_path)

    print("Architecture agents completed.")
    print(f"- mode: {args.mode}")
    print(f"- input: {input_path}")
    print(f"- output: {output_path}")

    if model.get("ai_enrichment"):
        print(
            "- pre-review suggestions:",
            model["ai_enrichment"].get("summary", {}).get("suggestions", 0),
        )

    if model.get("post_review_ai_check"):
        summary = model["post_review_ai_check"].get("summary", {})
        print("- post-review findings:", summary.get("findings", 0))
        print("- kdm_ready:", summary.get("kdm_ready"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
