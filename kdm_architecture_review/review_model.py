from dataclasses import dataclass, asdict
from typing import Any, Optional

@dataclass
class ReviewFinding:
    rule_id: str
    level: str
    message: str
    element: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    def to_dict(self):
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class ReviewValidationReport:
    valid: bool
    ok: list[ReviewFinding]
    warnings: list[ReviewFinding]
    forbidden: list[ReviewFinding]
    def to_dict(self):
        return {
            "valid": self.valid,
            "summary": {"ok": len(self.ok), "warnings": len(self.warnings), "forbidden": len(self.forbidden)},
            "ok": [x.to_dict() for x in self.ok],
            "warnings": [x.to_dict() for x in self.warnings],
            "forbidden": [x.to_dict() for x in self.forbidden],
        }
