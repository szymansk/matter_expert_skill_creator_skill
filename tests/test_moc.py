from datetime import date
from pathlib import Path

from matter_expert.moc import MOCFrontmatter, MOCPage


def test_moc_frontmatter_minimal():
    fm = MOCFrontmatter(
        title="Authentication",
        children=["oauth2-flow", "jwt-tokens"],
        parents=["security"],
        related_mocs=["authorization"],
        created=date(2026, 5, 10),
    )

    assert fm.title == "Authentication"
    assert fm.children == ["oauth2-flow", "jwt-tokens"]
    assert fm.parents == ["security"]
    assert fm.related_mocs == ["authorization"]


def test_moc_frontmatter_round_trip():
    fm = MOCFrontmatter(
        title="Auth",
        children=["a", "b"],
        parents=["sec"],
        related_mocs=["authz"],
        created=date(2026, 5, 10),
    )
    assert MOCFrontmatter.from_dict(fm.to_dict()) == fm


def test_moc_page_round_trip(tmp_path: Path):
    fm = MOCFrontmatter(
        title="Authentication",
        children=["oauth2-flow"],
        parents=["security"],
        related_mocs=["authorization"],
        created=date(2026, 5, 10),
    )
    page = MOCPage(
        frontmatter=fm,
        body="# Authentication MOC\n\nOverview of auth concepts.\n",
        path=tmp_path / "authentication.md",
    )
    page.write()

    reread = MOCPage.read(page.path)
    assert reread.frontmatter == fm
    assert reread.body.strip() == page.body.strip()
    assert reread.name == "authentication"
