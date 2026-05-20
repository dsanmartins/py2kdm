from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AISuggestion:
    """
    Generic suggestion produced by an architecture agent.

    Suggestions are not directly applied to KDM. They are stored in the JSON
    model and are intended to be reviewed by the user or by a later pipeline
    stage.
    """

    suggestion_type: str
    message: str
    confidence: float = 0.0
    status: str = "needs_review"
    source: str = "ai_assisted_enrichment"
    severity: str = "info"
    affected_elements: list[str] = field(default_factory=list)
    proposed_changes: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"ai_suggestion:{uuid4().hex}")
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AIFinding:
    """
    Post-review finding produced by consistency/readiness agents.
    """

    finding_type: str
    message: str
    severity: str = "warning"
    status: str = "ai_warning"
    confidence: float = 1.0
    source: str = "post_review_ai_check"
    affected_elements: list[str] = field(default_factory=list)
    recommendation: str | None = None
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"ai_finding:{uuid4().hex}")
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
