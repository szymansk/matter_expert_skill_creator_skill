"""Validators for vault content.

Two layers of validation:
- Structural: required fields, types, cardinality limits (this module)
- Semantic: wikilink resolution, circularity, vault integrity
  (also this module — see resolve/integrity functions in later tasks)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from matter_expert.concept import ConceptFrontmatter

# Cardinality limits for typed links — see design spec section 4.4
MAX_RELATED = 8
MAX_PREREQUISITES = 5
MAX_EXAMPLES = 6
MAX_CONTRASTS = 4
MAX_REFINES = 3


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    message: str
    location: str = ""  # e.g. concept name or file path


def validate_concept_frontmatter(
    fm: ConceptFrontmatter,
    concept_name: str | None = None,
) -> list[ValidationIssue]:
    """Validate a single concept's frontmatter.

    concept_name: the concept's canonical name (filename stem). Used for
    self-link detection. If None, self-link check is skipped.
    """
    issues: list[ValidationIssue] = []
    loc = concept_name or fm.title

    if not fm.title.strip():
        issues.append(ValidationIssue(Severity.ERROR, "title is empty", loc))

    if not fm.sources:
        issues.append(ValidationIssue(
            Severity.ERROR, "no sources — every concept must cite at least one source", loc
        ))

    cardinality_checks = [
        ("related", fm.related, MAX_RELATED),
        ("prerequisites", fm.prerequisites, MAX_PREREQUISITES),
        ("examples", fm.examples, MAX_EXAMPLES),
        ("contrasts", fm.contrasts, MAX_CONTRASTS),
        ("refines", fm.refines, MAX_REFINES),
    ]
    for name, links, limit in cardinality_checks:
        if len(links) > limit:
            issues.append(ValidationIssue(
                Severity.WARNING,
                f"{name} has {len(links)} entries (max recommended: {limit})",
                loc,
            ))

    if concept_name is not None:
        all_links = (
            fm.related + fm.prerequisites + fm.examples + fm.contrasts + fm.refines
        )
        if concept_name in all_links:
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"self-link: concept '{concept_name}' links to itself",
                loc,
            ))

    return issues
