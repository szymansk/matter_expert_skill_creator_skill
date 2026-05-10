from matter_expert.frontmatter import parse_frontmatter, write_frontmatter, ParsedDocument


def test_parse_simple_frontmatter():
    content = """---
title: OAuth2 Flow
tags: [auth, oauth2]
---

# Body

Some text here.
"""
    parsed = parse_frontmatter(content)

    assert isinstance(parsed, ParsedDocument)
    assert parsed.metadata["title"] == "OAuth2 Flow"
    assert parsed.metadata["tags"] == ["auth", "oauth2"]
    assert "# Body" in parsed.body
    assert "Some text here." in parsed.body


def test_parse_no_frontmatter():
    content = "Just plain markdown.\n"
    parsed = parse_frontmatter(content)

    assert parsed.metadata == {}
    assert parsed.body.strip() == "Just plain markdown."


def test_parse_empty_frontmatter():
    content = """---
---

Body only.
"""
    parsed = parse_frontmatter(content)

    assert parsed.metadata == {}
    assert "Body only." in parsed.body


def test_write_frontmatter_roundtrip():
    original = ParsedDocument(
        metadata={"title": "Test", "tags": ["a", "b"]},
        body="# Hello\n\nWorld.\n",
    )
    serialized = write_frontmatter(original)
    reparsed = parse_frontmatter(serialized)

    assert reparsed.metadata == original.metadata
    assert reparsed.body.strip() == original.body.strip()


def test_write_frontmatter_preserves_list_order():
    doc = ParsedDocument(
        metadata={"sources": [{"file": "a.pdf", "sections": ["1.1", "1.2"]}]},
        body="content",
    )
    serialized = write_frontmatter(doc)
    reparsed = parse_frontmatter(serialized)

    assert reparsed.metadata["sources"] == doc.metadata["sources"]
