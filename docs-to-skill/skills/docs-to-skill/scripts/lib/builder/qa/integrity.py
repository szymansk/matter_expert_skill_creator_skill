"""Validator 6: Vault Integrity — required directories + frontmatter validity.

Uses matter_expert.validate_vault and filters to structural issues.
"""
from __future__ import annotations

from builder.qa.report import Severity, ValidatorResult
from matter_expert import VaultPaths, Severity as MESeverity, validate_vault


class VaultIntegrityValidator:
    name = "vault_integrity"

    def validate(self, vault: VaultPaths) -> ValidatorResult:
        all_issues = validate_vault(vault)
        # Structural issues: missing dirs, parse failures, missing required fields.
        structural = [
            i for i in all_issues
            if "required directory" in i.message
            or "failed to parse" in i.message
            or "no sources" in i.message.lower()
            or "title is empty" in i.message
        ]
        errors = [i for i in structural if i.severity == MESeverity.ERROR]
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
                "message": i.message, "location": i.location,
                "severity": i.severity.value,
            } for i in structural],
        )
