from matter_expert.frontmatter import parse_frontmatter, ParsedDocument


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
