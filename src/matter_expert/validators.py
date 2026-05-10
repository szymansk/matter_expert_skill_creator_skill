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


def resolve_wikilinks(
    fm: ConceptFrontmatter,
    known_concepts: set[str],
    concept_name: str,
) -> list[ValidationIssue]:
    """Verify every wikilink target in a concept's typed-link lists exists.

    Each broken target produces one issue, even if it appears multiple times
    across different link types.
    """
    all_targets = set(fm.related) | set(fm.prerequisites) | set(fm.examples) \
                  | set(fm.contrasts) | set(fm.refines)
    broken = sorted(all_targets - known_concepts)
    return [
        ValidationIssue(
            Severity.ERROR,
            f"unresolved wikilink: '{target}' is not a known concept",
            concept_name,
        )
        for target in broken
    ]


def detect_circular_prerequisites(
    concepts: dict[str, ConceptFrontmatter],
) -> list[ValidationIssue]:
    """Detect circular prerequisite chains (A → B → A or longer cycles)."""
    issues: list[ValidationIssue] = []
    visited: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in stack:
            cycle = " → ".join(stack[stack.index(node):] + [node])
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"circular prerequisite chain: {cycle}",
                node,
            ))
            return
        if node in visited:
            return
        visited.add(node)
        if node in concepts:
            for prereq in concepts[node].prerequisites:
                dfs(prereq, stack + [node])

    for name in concepts:
        dfs(name, [])

    # Deduplicate (same cycle may be reported from multiple entry points)
    seen: set[str] = set()
    unique_issues: list[ValidationIssue] = []
    for issue in issues:
        key = issue.message
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)
    return unique_issues


from matter_expert.concept import ConceptPage
from matter_expert.paths import VaultPaths


def validate_vault(paths: VaultPaths) -> list[ValidationIssue]:
    """Validate a vault end-to-end.

    Checks:
    - Required directories exist (concepts/, MOCs/, sources/)
    - Each concept page parses successfully
    - Each concept's frontmatter is structurally valid
    - All wikilinks in concept frontmatter resolve to existing concepts
    - No circular prerequisite chains
    """
    issues: list[ValidationIssue] = []

    # Required directories
    for label, directory in [
        ("concepts", paths.concepts),
        ("MOCs", paths.mocs),
        ("sources", paths.sources),
    ]:
        if not directory.exists():
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"required directory '{label}' is missing at {directory}",
                str(paths.root),
            ))

    if not paths.concepts.exists():
        return issues  # Can't continue without concepts dir

    # Load all concepts
    concepts: dict[str, ConceptPage] = {}
    for path in sorted(paths.concepts.rglob("*.md")):
        try:
            page = ConceptPage.read(path)
            concepts[page.name] = page
        except Exception as e:
            issues.append(ValidationIssue(
                Severity.ERROR,
                f"failed to parse concept: {e}",
                str(path.relative_to(paths.root)),
            ))

    if not concepts:
        issues.append(ValidationIssue(
            Severity.WARNING,
            "vault has no concepts",
            str(paths.root),
        ))
        return issues

    # Per-concept structural validation
    for name, page in concepts.items():
        issues.extend(validate_concept_frontmatter(page.frontmatter, concept_name=name))

    # Wikilink resolution across concepts
    known = set(concepts.keys())
    for name, page in concepts.items():
        issues.extend(resolve_wikilinks(page.frontmatter, known, concept_name=name))

    # Circular prerequisites
    issues.extend(detect_circular_prerequisites(
        {name: page.frontmatter for name, page in concepts.items()}
    ))

    return issues
