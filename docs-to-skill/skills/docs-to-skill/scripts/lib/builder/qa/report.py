"""QA report data types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class OverallStatus(Enum):
    PASS = "pass"
    PASS_WITH_WARNINGS = "pass_with_warnings"
    FAIL = "fail"


@dataclass
class ValidatorResult:
    name: str
    severity: Severity
    sampled: int
    total: int
    issues: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidatorResult":
        return cls(
            name=data["name"],
            severity=Severity(data["severity"]),
            sampled=int(data["sampled"]),
            total=int(data["total"]),
            issues=list(data.get("issues", [])),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity.value,
            "sampled": self.sampled,
            "total": self.total,
            "issues": list(self.issues),
            "notes": self.notes,
        }


@dataclass
class QAReport:
    overall_status: OverallStatus
    validators: list[ValidatorResult]
    recommendations: list[str] = field(default_factory=list)

    @classmethod
    def compute_overall(cls, validators: list[ValidatorResult]) -> OverallStatus:
        if any(v.severity == Severity.FAIL for v in validators):
            return OverallStatus.FAIL
        if any(v.severity == Severity.WARNING for v in validators):
            return OverallStatus.PASS_WITH_WARNINGS
        return OverallStatus.PASS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QAReport":
        return cls(
            overall_status=OverallStatus(data["overall_status"]),
            validators=[ValidatorResult.from_dict(v)
                        for v in data.get("validators", [])],
            recommendations=list(data.get("recommendations", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "validators": [v.to_dict() for v in self.validators],
            "recommendations": list(self.recommendations),
        }
