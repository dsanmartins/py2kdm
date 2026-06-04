from pathlib import Path
import argparse
import json
import sys


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PY2KDM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PY2KDM_PROJECT_ROOT))


def load_dotenv_if_available() -> None:
    """
    Loads .env from the py2kdm project root.

    The Gemini provider reads GEMINI_API_KEY or GOOGLE_API_KEY from
    os.environ.  Therefore this function must run before the provider is
    created.  It first tries python-dotenv with override=True and then falls
    back to a minimal parser for GEMINI_API_KEY / GOOGLE_API_KEY.
    """
    import os

    env_path = PY2KDM_PROJECT_ROOT / ".env"

    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv is not None:
        load_dotenv(env_path, override=True)

    # Fallback parser in case python-dotenv is not installed in the exact
    # virtualenv used by run_pipeline.py, or if the key was not loaded for any
    # other reason.
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key in {"GEMINI_API_KEY", "GOOGLE_API_KEY"} and value:
            os.environ[key] = value


load_dotenv_if_available()


from py2kdm_common.paths import ensure_parent, resolve_from_root

from kdm_architecture_agents.agent_context_builder import AgentContextBuilder
from kdm_architecture_agents.llm.provider_factory import create_llm_provider
from kdm_architecture_agents.pre_review.architecture_enrichment_agent import (
    ArchitectureEnrichmentAgent,
)
from kdm_architecture_agents.pre_review.dynamic_evidence_agent import (
    DynamicEvidenceAgent,
)
from kdm_architecture_agents.pre_review.deterministic_code_review_agent import (
    DeterministicCodeReviewAgent,
)
from kdm_architecture_agents.pre_review.llm_architecture_reasoning_agent import (
    LLMArchitectureReasoningAgent,
)
from kdm_architecture_agents.suggestion_deduplicator import SuggestionDeduplicator


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(data: dict, path: Path):
    path = ensure_parent(path)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def run_pre_review(
    model,
    trace_path=None,
    code_model=None,
    llm_provider_name="none",
    llm_model=None,
    llm_base_url=None,
    llm_timeout=300,
):
    """
    Runs pre-review architecture agents.

    The agents only create reviewable suggestions. They do not modify the
    structure_model directly.
    """

    context = AgentContextBuilder().build(model, code_model=code_model)

    dynamic_suggestions = DynamicEvidenceAgent().run(
        model=model,
        context=context,
        trace_path=trace_path,
    )
    enrichment_suggestions = ArchitectureEnrichmentAgent().run(
        model=model,
        context=context,
    )

    provider = create_llm_provider(
        provider_name=llm_provider_name,
        model=llm_model,
        base_url=llm_base_url,
        timeout_seconds=llm_timeout,
    )

    deterministic_code_review = DeterministicCodeReviewAgent().run(
        model=model,
        context=context,
    )

    llm_suggestions = LLMArchitectureReasoningAgent(provider).run(
        model=model,
        context=context,
    )

    raw_suggestions = (
        dynamic_suggestions
        + enrichment_suggestions
        + llm_suggestions
    )

    all_suggestions = SuggestionDeduplicator().deduplicate(raw_suggestions)

    model.setdefault("ai_enrichment", {})
    model["ai_enrichment"].update(
        {
            "status": "pre_review_enriched",
            "source": "kdm_architecture_agents.pre_review",
            "suggestions": all_suggestions,
            "code_context": context.get("code_context", {}),
            "ai_architecture_review": {
                "status": "available_for_review",
                "source": "kdm_architecture_agents.pre_review",
                "note": (
                    "This review layer is non-invasive. It does not modify "
                    "structure_model; it only stores reviewable suggestions, "
                    "compact code evidence and deterministic code review."
                ),
                "code_context_available": bool(
                    context.get("code_context", {}).get("available")
                ),
                "deterministic_review_available": True,
            },
            "deterministic_code_review": deterministic_code_review,
            "summary": {
                "suggestions": len(all_suggestions),
                "raw_suggestions": len(raw_suggestions),
                "deduplicated_suggestions": len(raw_suggestions) - len(all_suggestions),
                "dynamic_suggestions": len(dynamic_suggestions),
                "architecture_suggestions": len(enrichment_suggestions),
                "llm_suggestions": len(llm_suggestions),
                "llm_provider": getattr(provider, "name", "unknown"),
                "llm_model": getattr(provider, "model", None),
                "llm_timeout": llm_timeout,
                "code_context_available": bool(
                    context.get("code_context", {}).get("available")
                ),
                "code_context_classes": (
                    context.get("code_context", {}).get("classes_count", 0)
                ),
                "deterministic_review_status": deterministic_code_review.get("status"),
                "deterministic_review_confidence": (
                    deterministic_code_review
                    .get("architecture_assessment", {})
                    .get("confidence")
                ),
            },
        }
    )

    return model


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run py2kdm pre-review architecture agents. "
            "Post-review agents are intentionally not part of the default "
            "methodological pipeline: after human review, the reviewed model "
            "is treated as authoritative and should feed KDM generation."
        )
    )

    parser.add_argument(
        "--mode",
        choices=["pre-review"],
        default="pre-review",
        help="Only pre-review mode is supported in the main agent workflow.",
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--dynamic-trace",
        help=(
            "Optional dynamic trace JSON. Usually not needed when the input "
            "model already contains relationships[type='runtime_calls']."
        ),
    )

    parser.add_argument(
        "--code-context-input",
        help=(
            "Optional intermediate extractor JSON used to build a compact "
            "code_context for the LLM pre-review agent."
        ),
    )

    parser.add_argument(
        "--llm-provider",
        choices=["none", "ollama", "gemini"],
        default="none",
        help="Optional LLM provider. Default: none.",
    )
    parser.add_argument(
        "--llm-model",
        help=(
            "Optional LLM model name, for example qwen2.5-coder:1.5b, "
            "gemini-2.5-flash-lite, or gemini-2.5-flash."
        ),
    )
    parser.add_argument(
        "--llm-base-url",
        help="Optional LLM base URL, used by providers such as Ollama.",
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for local or remote LLM calls. Default: 300.",
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
    code_context_path = (
        resolve_from_root(args.code_context_input)
        if args.code_context_input
        else None
    )

    model = load_json(input_path)
    code_model = load_json(code_context_path) if code_context_path else None

    model = run_pre_review(
        model,
        trace_path=trace_path,
        code_model=code_model,
        llm_provider_name=args.llm_provider,
        llm_model=args.llm_model,
        llm_base_url=args.llm_base_url,
        llm_timeout=args.llm_timeout,
    )

    save_json(model, output_path)

    print("Architecture agents completed.")
    print("- mode: pre-review")
    print(f"- input: {input_path}")
    print(f"- output: {output_path}")

    if model.get("ai_enrichment"):
        summary = model["ai_enrichment"].get("summary", {})
        print("- pre-review suggestions:", summary.get("suggestions", 0))
        print("- raw_suggestions:", summary.get("raw_suggestions", 0))
        print("- deduplicated_suggestions:", summary.get("deduplicated_suggestions", 0))
        print("- llm_provider:", summary.get("llm_provider"))
        print("- llm_model:", summary.get("llm_model"))
        print("- llm_suggestions:", summary.get("llm_suggestions", 0))
        print("- llm_timeout:", summary.get("llm_timeout"))
        print("- code_context_available:", summary.get("code_context_available"))
        print("- code_context_classes:", summary.get("code_context_classes"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
