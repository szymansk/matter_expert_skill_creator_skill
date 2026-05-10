from datetime import date
from pathlib import Path

from builder.link.inventory import ConceptSummary
from builder.link.moc_generator import MOCGenerator
from matter_expert import MOCPage


def test_generates_moc_per_tag(tmp_path: Path):
    inventory = [
        ConceptSummary("oauth2-flow", "OAuth2", "x", tags=["auth", "oauth2"]),
        ConceptSummary("jwt-tokens", "JWT", "y", tags=["auth"]),
        ConceptSummary("encryption-fundamentals", "Encryption", "z", tags=["crypto"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    written = gen.generate(inventory, mocs_dir)

    # One MOC: auth. oauth2 and crypto each have only one concept → not separate MOCs.
    moc_names = {m.name for m in written}
    assert "auth" in moc_names
    assert "crypto" not in moc_names
    assert "oauth2" not in moc_names
    # Each written file is readable as an MOCPage
    auth_moc = MOCPage.read(mocs_dir / "auth.md")
    assert set(auth_moc.frontmatter.children) == {"oauth2-flow", "jwt-tokens"}


def test_singleton_tags_are_skipped(tmp_path: Path):
    """Tags appearing on only one concept don't get their own MOC."""
    inventory = [
        ConceptSummary("a", "A", "", tags=["solo"]),
        ConceptSummary("b", "B", "", tags=["shared"]),
        ConceptSummary("c", "C", "", tags=["shared"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    written = gen.generate(inventory, mocs_dir)
    names = {m.name for m in written}
    assert "shared" in names
    assert "solo" not in names


def test_moc_body_lists_children_as_wikilinks(tmp_path: Path):
    inventory = [
        ConceptSummary("a", "A", "", tags=["t"]),
        ConceptSummary("b", "B", "", tags=["t"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    gen.generate(inventory, mocs_dir)

    body = (mocs_dir / "t.md").read_text(encoding="utf-8")
    assert "[[a]]" in body
    assert "[[b]]" in body


def test_related_mocs_populated_for_overlapping_tags(tmp_path: Path):
    """Two MOCs that share a concept (concept with multiple tags) should
    reference each other via related_mocs (spec §4.4 horizontal cross-refs)."""
    # "oauth2-flow" appears in both "auth" and "oauth2" tags.
    inventory = [
        ConceptSummary("oauth2-flow", "OAuth2", "x", tags=["auth", "oauth2"]),
        ConceptSummary("jwt-tokens", "JWT", "y", tags=["auth"]),
        ConceptSummary("saml-sso", "SAML", "z", tags=["auth"]),
        ConceptSummary("oauth2-pkce", "PKCE", "w", tags=["oauth2"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    gen.generate(inventory, mocs_dir)

    auth_moc = MOCPage.read(mocs_dir / "auth.md")
    oauth2_moc = MOCPage.read(mocs_dir / "oauth2.md")

    # auth and oauth2 both contain oauth2-flow → they are related.
    assert "oauth2" in auth_moc.frontmatter.related_mocs
    assert "auth" in oauth2_moc.frontmatter.related_mocs


def test_no_related_mocs_when_disjoint_tag_sets(tmp_path: Path):
    """MOCs whose concept sets don't overlap get empty related_mocs."""
    inventory = [
        ConceptSummary("a", "A", "", tags=["alpha"]),
        ConceptSummary("b", "B", "", tags=["alpha"]),
        ConceptSummary("c", "C", "", tags=["beta"]),
        ConceptSummary("d", "D", "", tags=["beta"]),
    ]
    mocs_dir = tmp_path / "MOCs"
    gen = MOCGenerator()
    gen.generate(inventory, mocs_dir)

    alpha_moc = MOCPage.read(mocs_dir / "alpha.md")
    beta_moc = MOCPage.read(mocs_dir / "beta.md")

    assert alpha_moc.frontmatter.related_mocs == []
    assert beta_moc.frontmatter.related_mocs == []
