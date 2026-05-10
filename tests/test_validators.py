from datetime import date

from matter_expert.concept import ConceptFrontmatter, Source
from matter_expert.validators import (
    ValidationIssue,
    Severity,
    validate_concept_frontmatter,
)


def _valid_fm(**overrides) -> ConceptFrontmatter:
    base = dict(
        title="OAuth2 Flow",
        sources=[Source(file="handbook.pdf", sections=["3.1"])],
        tags=["auth"],
        created=date(2026, 5, 10),
    )
    base.update(overrides)
    return ConceptFrontmatter(**base)


def test_valid_frontmatter_yields_no_issues():
    issues = validate_concept_frontmatter(_valid_fm())
    assert issues == []


def test_empty_title_fails():
    issues = validate_concept_frontmatter(_valid_fm(title=""))
    assert any(i.severity == Severity.ERROR and "title" in i.message for i in issues)


def test_no_sources_fails():
    issues = validate_concept_frontmatter(_valid_fm(sources=[]))
    assert any(i.severity == Severity.ERROR and "source" in i.message.lower() for i in issues)


def test_too_many_related_warns():
    issues = validate_concept_frontmatter(_valid_fm(related=[f"x{i}" for i in range(9)]))
    assert any(i.severity == Severity.WARNING and "related" in i.message for i in issues)


def test_too_many_prerequisites_warns():
    issues = validate_concept_frontmatter(_valid_fm(prerequisites=[f"x{i}" for i in range(6)]))
    assert any(i.severity == Severity.WARNING and "prerequisites" in i.message for i in issues)


def test_too_many_examples_warns():
    issues = validate_concept_frontmatter(_valid_fm(examples=[f"x{i}" for i in range(7)]))
    assert any(i.severity == Severity.WARNING and "examples" in i.message for i in issues)


def test_too_many_contrasts_warns():
    issues = validate_concept_frontmatter(_valid_fm(contrasts=[f"x{i}" for i in range(5)]))
    assert any(i.severity == Severity.WARNING and "contrasts" in i.message for i in issues)


def test_too_many_refines_warns():
    issues = validate_concept_frontmatter(_valid_fm(refines=[f"x{i}" for i in range(4)]))
    assert any(i.severity == Severity.WARNING and "refines" in i.message for i in issues)


def test_self_link_fails():
    """A concept must not link to itself in any link list."""
    issues = validate_concept_frontmatter(
        _valid_fm(related=["self"]),
        concept_name="self",
    )
    assert any(i.severity == Severity.ERROR and "self" in i.message.lower() for i in issues)
