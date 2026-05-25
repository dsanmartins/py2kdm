from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class RuntimeEvidenceFilter:
    """
    Filters runtime events before injecting them into the CodeModel.

    The tracer intentionally captures many events, including imports, scenario
    helper calls and dependency shims. These are useful for debugging the trace,
    but they should not be injected as factual code relationships of the target
    system.

    This filter keeps events that are likely to belong to the analyzed system
    and excludes tracing/scenario infrastructure.
    """

    EXCLUDED_PREFIXES = (
        "scenarios.",
        "_scenario_common.",
    )

    EXCLUDED_CONTAINS = (
        ".Dummy",
        ".NullObserver",
        ".install_dependency_shims",
        ".import_mape",
        ".load_hierarchical_module",
    )

    EXCLUDED_SUFFIXES = (
        ".<module>",
    )

    DEFAULT_INCLUDED_PREFIXES = (
        "fixtures.",
        "mape.",
        "hierarchical_cruise_control_runtime.",
    )

    def __init__(
        self,
        included_prefixes: tuple[str, ...] | None = None,
        keep_module_events: bool = False,
    ):
        self.included_prefixes = included_prefixes or self.DEFAULT_INCLUDED_PREFIXES
        self.keep_module_events = keep_module_events

    def is_relevant_event(self, event: dict[str, Any]) -> bool:
        event_type = event.get("type")

        if event_type not in {"call", "return", "exception"}:
            return False

        names = [
            event.get("source"),
            event.get("target"),
            event.get("qualified_name"),
        ]

        names = [name for name in names if isinstance(name, str)]

        if not names:
            return False

        if not self.keep_module_events:
            if any(name.endswith(self.EXCLUDED_SUFFIXES) for name in names):
                return False

        for name in names:
            if self._is_excluded_name(name):
                return False

        return any(
            self._is_included_name(name)
            for name in names
        )

    def _is_excluded_name(self, name: str) -> bool:
        if name.startswith(self.EXCLUDED_PREFIXES):
            return True

        return any(token in name for token in self.EXCLUDED_CONTAINS)

    def _is_included_name(self, name: str) -> bool:
        return name.startswith(self.included_prefixes)


class CodeModelDynamicEnrichmentAgent:
    """
    Adds factual runtime evidence to the code-level JSON model.

    It adds runtime_calls relationships and runtime type observations.
    It does not create or modify StructureModel elements.
    """

    def __init__(
        self,
        filter_runtime_events: bool = True,
        included_prefixes: tuple[str, ...] | None = None,
    ):
        self.filter_runtime_events = filter_runtime_events
        self.filter = RuntimeEvidenceFilter(included_prefixes=included_prefixes)

    def enrich(self, model: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
        model.setdefault("relationships", [])
        model.setdefault("runtime_enrichment", {})

        raw_events = trace.get("events", [])

        if self.filter_runtime_events:
            events = [
                event for event in raw_events
                if self.filter.is_relevant_event(event)
            ]
        else:
            events = list(raw_events)

        existing = {
            self._key(r)
            for r in model.get("relationships", [])
            if self._key(r) is not None
        }

        added = []
        arg_types = []
        return_types = []
        exceptions = []

        for event in events:
            if event.get("type") == "call":
                rel = self._call_relationship(event)
                if rel and self._key(rel) not in existing:
                    model["relationships"].append(rel)
                    existing.add(self._key(rel))
                    added.append(rel)
                if event.get("arg_types"):
                    arg_types.append({
                        "function": event.get("qualified_name") or event.get("target"),
                        "file": event.get("file"),
                        "line": event.get("line"),
                        "arg_types": event.get("arg_types"),
                        "scenario": event.get("scenario"),
                    })
            elif event.get("type") == "return" and event.get("return_type"):
                return_types.append({
                    "function": event.get("qualified_name") or event.get("source"),
                    "file": event.get("file"),
                    "line": event.get("line"),
                    "return_type": event.get("return_type"),
                    "scenario": event.get("scenario"),
                })
            elif event.get("type") == "exception":
                exceptions.append({
                    "function": event.get("qualified_name") or event.get("source"),
                    "file": event.get("file"),
                    "line": event.get("line"),
                    "exception_type": event.get("exception_type"),
                    "exception_message": event.get("exception_message"),
                    "scenario": event.get("scenario"),
                })

        model["runtime_enrichment"] = {
            "status": "runtime_enriched",
            "source": "kdm_dynamic_analysis.CodeModelDynamicEnrichmentAgent",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trace_metadata": trace.get("metadata", {}),
            "filter": {
                "enabled": self.filter_runtime_events,
                "included_prefixes": list(self.filter.included_prefixes),
                "excluded_prefixes": list(self.filter.EXCLUDED_PREFIXES),
                "excluded_contains": list(self.filter.EXCLUDED_CONTAINS),
                "excluded_suffixes": list(self.filter.EXCLUDED_SUFFIXES),
            },
            "summary": {
                "events": len(raw_events),
                "events_after_filter": len(events),
                "events_filtered_out": len(raw_events) - len(events),
                "dynamic_relationships_added": len(added),
                "observed_argument_types": len(arg_types),
                "observed_return_types": len(return_types),
                "observed_exceptions": len(exceptions),
            },
            "observed_argument_types": arg_types,
            "observed_return_types": return_types,
            "observed_exceptions": exceptions,
        }
        return model

    def _call_relationship(self, event):
        source = event.get("source")
        target = event.get("target")
        if not source or not target or source == target:
            return None
        return {
            "id": f"runtime_calls:{source}->{target}",
            "source": source,
            "target": target,
            "type": "runtime_calls",
            "relationship_level": "code",
            "source_level": "runtime",
            "confidence": 1.0,
            "evidence": "dynamic_trace",
            "scenario": event.get("scenario"),
            "file": event.get("file"),
            "line": event.get("line"),
            "metadata": {
                "thread_id": event.get("thread_id"),
                "receiver_type": event.get("receiver_type"),
                "arg_types": event.get("arg_types", {}),
            },
        }

    def _key(self, relationship):
        if not relationship:
            return None
        source = relationship.get("source")
        target = relationship.get("target")
        rel_type = relationship.get("type")
        if not source or not target or not rel_type:
            return None
        return (str(source), str(target), str(rel_type))
