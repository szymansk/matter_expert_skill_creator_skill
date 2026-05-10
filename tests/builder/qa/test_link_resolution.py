from builder.qa.link_resolution import LinkResolutionValidator
from builder.qa.report import Severity


def test_passes_for_well_formed_vault(populated_vault):
    v = LinkResolutionValidator()
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.PASS
    assert result.issues == []


def test_fails_for_broken_wikilink(populated_vault):
    # Inject a concept with a broken related-link.
    from datetime import date
    from matter_expert import ConceptFrontmatter, ConceptPage, Source

    fm = ConceptFrontmatter(
        title="Broken",
        sources=[Source(file="x.md", sections=[])],
        tags=[], created=date(2026, 5, 10),
        related=["does-not-exist"],
    )
    ConceptPage(
        frontmatter=fm, body="body",
        path=populated_vault.concept_for("broken"),
    ).write()

    v = LinkResolutionValidator()
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.FAIL
    assert any("does-not-exist" in str(issue) for issue in result.issues)
