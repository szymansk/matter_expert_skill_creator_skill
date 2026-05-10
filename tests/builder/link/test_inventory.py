from datetime import date
from pathlib import Path

from builder.link.inventory import ConceptSummary, build_inventory
from matter_expert import ConceptFrontmatter, ConceptPage, Source


def _make_concept(tmp_path: Path, name: str, title: str, body: str, tags=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}-source.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
    )
    concepts_dir = tmp_path / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    page = ConceptPage(frontmatter=fm, body=body, path=concepts_dir / f"{name}.md")
    page.write()
    return page


def test_summary_construction():
    s = ConceptSummary(
        name="oauth2-flow",
        title="OAuth2 Flow",
        summary="An authorization framework using access tokens.",
        tags=["auth", "oauth2"],
    )
    assert s.name == "oauth2-flow"
    assert "authorization" in s.summary


def test_build_inventory_extracts_first_sentence(tmp_path: Path):
    _make_concept(
        tmp_path, "oauth2-flow", "OAuth2 Flow",
        body="# OAuth2 Flow\n\nOAuth2 is an authorization framework using "
             "access and refresh tokens. It is widely used.\n",
        tags=["auth", "oauth2"],
    )

    inv = build_inventory(tmp_path / "concepts")

    assert len(inv) == 1
    entry = inv[0]
    assert entry.name == "oauth2-flow"
    assert entry.title == "OAuth2 Flow"
    assert "authorization framework" in entry.summary
    assert entry.tags == ["auth", "oauth2"]


def test_build_inventory_handles_empty_body(tmp_path: Path):
    _make_concept(tmp_path, "empty", "Empty Concept", body="")
    inv = build_inventory(tmp_path / "concepts")
    assert inv[0].summary == ""


def test_build_inventory_strips_heading_markers(tmp_path: Path):
    _make_concept(
        tmp_path, "x", "X",
        body="# Heading\n\nFirst sentence here. Second sentence.\n",
    )
    inv = build_inventory(tmp_path / "concepts")
    assert "First sentence" in inv[0].summary
    assert not inv[0].summary.startswith("#")


def test_build_inventory_alphabetical_order(tmp_path: Path):
    _make_concept(tmp_path, "z-concept", "Z", body="zz")
    _make_concept(tmp_path, "a-concept", "A", body="aa")
    inv = build_inventory(tmp_path / "concepts")
    assert [s.name for s in inv] == ["a-concept", "z-concept"]
