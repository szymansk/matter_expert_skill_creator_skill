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


from matter_expert.validators import resolve_wikilinks, detect_circular_prerequisites


def test_resolve_wikilinks_all_resolve():
    fm = _valid_fm(related=["jwt-tokens"], prerequisites=["http-basics"])
    known = {"jwt-tokens", "http-basics", "self"}

    issues = resolve_wikilinks(fm, known_concepts=known, concept_name="self")
    assert issues == []


def test_resolve_wikilinks_broken_link_errors():
    fm = _valid_fm(related=["does-not-exist"])
    known = {"self"}

    issues = resolve_wikilinks(fm, known_concepts=known, concept_name="self")
    assert any(
        i.severity == Severity.ERROR and "does-not-exist" in i.message
        for i in issues
    )


def test_resolve_wikilinks_reports_each_broken_link_once():
    fm = _valid_fm(
        related=["broken-1"],
        prerequisites=["broken-2"],
        examples=["broken-1"],  # repeated
    )
    known: set[str] = set()

    issues = resolve_wikilinks(fm, known_concepts=known, concept_name="self")
    broken_messages = [i.message for i in issues]
    # broken-1 appears in two link lists, but should only generate one issue
    assert sum("broken-1" in m for m in broken_messages) == 1
    assert sum("broken-2" in m for m in broken_messages) == 1


def test_circular_prerequisites_simple_cycle():
    """A → B → A is a circular prerequisite chain."""
    today = date(2026, 5, 10)
    src = Source(file="a.pdf", sections=[])
    concepts = {
        "a": ConceptFrontmatter(
            title="A", sources=[src], tags=[], created=today, prerequisites=["b"]
        ),
        "b": ConceptFrontmatter(
            title="B", sources=[src], tags=[], created=today, prerequisites=["a"]
        ),
    }

    issues = detect_circular_prerequisites(concepts)
    assert any("circular" in i.message.lower() for i in issues)


def test_circular_prerequisites_three_cycle():
    """A → B → C → A."""
    today = date(2026, 5, 10)
    src = Source(file="a.pdf", sections=[])
    concepts = {
        "a": ConceptFrontmatter(
            title="A", sources=[src], tags=[], created=today, prerequisites=["b"]
        ),
        "b": ConceptFrontmatter(
            title="B", sources=[src], tags=[], created=today, prerequisites=["c"]
        ),
        "c": ConceptFrontmatter(
            title="C", sources=[src], tags=[], created=today, prerequisites=["a"]
        ),
    }

    issues = detect_circular_prerequisites(concepts)
    assert any(i.severity == Severity.ERROR for i in issues)


def test_no_circular_prerequisites_when_dag():
    """A → B → C is fine; no cycle."""
    today = date(2026, 5, 10)
    src = Source(file="a.pdf", sections=[])
    concepts = {
        "a": ConceptFrontmatter(
            title="A", sources=[src], tags=[], created=today, prerequisites=["b"]
        ),
        "b": ConceptFrontmatter(
            title="B", sources=[src], tags=[], created=today, prerequisites=["c"]
        ),
        "c": ConceptFrontmatter(
            title="C", sources=[src], tags=[], created=today,
        ),
    }

    issues = detect_circular_prerequisites(concepts)
    assert issues == []


from pathlib import Path
from matter_expert.paths import VaultPaths
from matter_expert.validators import validate_vault


def test_validate_empty_vault_warns(tmp_path: Path):
    """An empty vault directory is structurally valid but warns about no concepts."""
    vault_root = tmp_path / "vault"
    paths = VaultPaths(root=vault_root)
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    issues = validate_vault(paths)
    assert any(i.severity == Severity.WARNING and "no concepts" in i.message.lower()
               for i in issues)


def test_validate_missing_required_directory_errors(tmp_path: Path):
    """Missing concepts/ or MOCs/ or sources/ is an error."""
    vault_root = tmp_path / "vault"
    paths = VaultPaths(root=vault_root)
    paths.concepts.mkdir(parents=True)
    # MOCs and sources missing on purpose

    issues = validate_vault(paths)
    error_msgs = [i.message for i in issues if i.severity == Severity.ERROR]
    assert any("MOCs" in m for m in error_msgs)
    assert any("sources" in m for m in error_msgs)


def test_validate_complete_minimal_vault(tmp_path: Path):
    """A vault with one valid concept passes integrity validation."""
    from matter_expert.concept import ConceptFrontmatter, ConceptPage, Source

    vault_root = tmp_path / "vault"
    paths = VaultPaths(root=vault_root)
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    fm = ConceptFrontmatter(
        title="Concept A",
        sources=[Source(file="a.md", sections=[])],
        tags=["topic"],
        created=date(2026, 5, 10),
    )
    page = ConceptPage(frontmatter=fm, body="Body.", path=paths.concept_for("concept-a"))
    page.write()

    issues = validate_vault(paths)
    assert all(i.severity != Severity.ERROR for i in issues)


def test_validate_detects_broken_wikilink_in_vault(tmp_path: Path):
    from matter_expert.concept import ConceptFrontmatter, ConceptPage, Source

    vault_root = tmp_path / "vault"
    paths = VaultPaths(root=vault_root)
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    fm = ConceptFrontmatter(
        title="A",
        sources=[Source(file="a.md", sections=[])],
        tags=[],
        created=date(2026, 5, 10),
        related=["does-not-exist"],
    )
    ConceptPage(
        frontmatter=fm, body="Body.", path=paths.concept_for("a")
    ).write()

    issues = validate_vault(paths)
    assert any(
        i.severity == Severity.ERROR and "does-not-exist" in i.message
        for i in issues
    )
