"""Validator 2: Link Resolution — uses matter_expert.validate_vault.

Filters issues to wikilink-resolution errors and circular prerequisites.
"""
from __future__ import annotations

from builder.qa.report import Severity, ValidatorResult
from matter_expert import VaultPaths, Severity as MESeverity, validate_vault


class LinkResolutionValidator:
    name = "link_resolution"

    def validate(self, vault: VaultPaths) -> ValidatorResult:
        all_issues = validate_vault(vault)
        link_issues = [
            i for i in all_issues
            if "unresolved wikilink" in i.message
            or "circular prerequisite" in i.message
        ]
        errors = [i for i in link_issues if i.severity == MESeverity.ERROR]
        severity = Severity.FAIL if errors else Severity.PASS
        concepts_count = (
            len(list(vault.concepts.glob("*.md")))
            if vault.concepts.exists() else 0
        )
        return ValidatorResult(
            name=self.name,
            severity=severity,
            sampled=concepts_count,
            total=concepts_count,
            issues=[{
                "message": i.message,
                "location": i.location,
                "severity": i.severity.value,
            } for i in link_issues],
        )
