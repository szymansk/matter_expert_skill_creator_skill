from datetime import date

from matter_expert.concept import ConceptFrontmatter, Source


def test_source_from_dict():
    data = {"file": "handbook.pdf", "sections": ["3.1", "3.2"]}
    source = Source.from_dict(data)

    assert source.file == "handbook.pdf"
    assert source.sections == ["3.1", "3.2"]


def test_source_to_dict_round_trip():
    original = Source(file="security.pdf", sections=["2.4"])
    assert Source.from_dict(original.to_dict()) == original


def test_source_to_dict_no_sections():
    source = Source(file="readme.md", sections=[])
    assert source.to_dict() == {"file": "readme.md", "sections": []}


def test_concept_frontmatter_minimal():
    fm = ConceptFrontmatter(
        title="OAuth2 Flow",
        sources=[Source(file="handbook.pdf", sections=["3.1"])],
        tags=["auth", "oauth2"],
        created=date(2026, 5, 10),
    )

    assert fm.title == "OAuth2 Flow"
    assert fm.related == []
    assert fm.prerequisites == []
    assert fm.examples == []
    assert fm.contrasts == []
    assert fm.refines == []
    assert fm.merged_from == []


def test_concept_frontmatter_with_links():
    fm = ConceptFrontmatter(
        title="OAuth2 Flow",
        sources=[Source(file="handbook.pdf", sections=["3.1"])],
        tags=["auth"],
        created=date(2026, 5, 10),
        related=["jwt-tokens", "session-management"],
        prerequisites=["http-basics"],
    )

    assert fm.related == ["jwt-tokens", "session-management"]
    assert fm.prerequisites == ["http-basics"]


def test_concept_frontmatter_from_dict():
    data = {
        "title": "OAuth2 Flow",
        "sources": [{"file": "handbook.pdf", "sections": ["3.1"]}],
        "tags": ["auth"],
        "created": date(2026, 5, 10),
        "related": ["jwt-tokens"],
        "prerequisites": [],
        "examples": [],
        "contrasts": [],
        "refines": [],
        "merged_from": [],
    }
    fm = ConceptFrontmatter.from_dict(data)

    assert fm.title == "OAuth2 Flow"
    assert fm.sources == [Source(file="handbook.pdf", sections=["3.1"])]
    assert fm.related == ["jwt-tokens"]


def test_concept_frontmatter_to_dict_round_trip():
    fm = ConceptFrontmatter(
        title="JWT Tokens",
        sources=[Source(file="security.pdf", sections=["2.4"])],
        tags=["auth", "tokens"],
        created=date(2026, 5, 10),
        related=["oauth2-flow"],
        prerequisites=["encryption-fundamentals"],
        examples=[],
        contrasts=["session-tokens"],
        refines=[],
    )
    assert ConceptFrontmatter.from_dict(fm.to_dict()) == fm


def test_concept_frontmatter_normalizes_wikilinks_in_links():
    """Wikilinks in frontmatter may be stored bracket-wrapped or bare —
    canonical form is bare."""
    fm = ConceptFrontmatter.from_dict({
        "title": "X",
        "sources": [{"file": "a.pdf", "sections": []}],
        "tags": [],
        "created": date(2026, 5, 10),
        "related": ["[[jwt-tokens]]", "session-management"],
    })

    assert fm.related == ["jwt-tokens", "session-management"]


from pathlib import Path
from matter_expert.concept import ConceptPage


def test_concept_page_read(tmp_path: Path):
    md = """---
title: OAuth2 Flow
sources:
  - file: handbook.pdf
    sections: ["3.1", "3.2"]
tags: [auth, oauth2]
created: 2026-05-10
related: [jwt-tokens]
prerequisites: [http-basics]
examples: []
contrasts: [basic-auth]
refines: []
merged_from: []
---

# OAuth2 Flow

OAuth2 separates authentication and authorization through tokens.
"""
    file = tmp_path / "oauth2-flow.md"
    file.write_text(md)

    page = ConceptPage.read(file)

    assert page.path == file
    assert page.frontmatter.title == "OAuth2 Flow"
    assert page.frontmatter.related == ["jwt-tokens"]
    assert page.frontmatter.contrasts == ["basic-auth"]
    assert "OAuth2 separates" in page.body


def test_concept_page_name_from_path(tmp_path: Path):
    """The concept's canonical name is its filename without extension."""
    md = """---
title: X
sources: [{file: a.pdf, sections: []}]
tags: []
created: 2026-05-10
---

body
"""
    file = tmp_path / "oauth2-flow.md"
    file.write_text(md)

    page = ConceptPage.read(file)
    assert page.name == "oauth2-flow"
