from matter_expert.wikilinks import extract_wikilinks, normalize_wikilink


def test_extract_single_wikilink():
    text = "See [[oauth2-flow]] for details."
    assert extract_wikilinks(text) == ["oauth2-flow"]


def test_extract_multiple_wikilinks():
    text = "Compare [[oauth2-flow]] with [[basic-auth]] and [[jwt-tokens]]."
    assert extract_wikilinks(text) == ["oauth2-flow", "basic-auth", "jwt-tokens"]


def test_extract_no_wikilinks():
    assert extract_wikilinks("Plain text without links.") == []


def test_extract_ignores_inline_code():
    text = "The syntax is `[[name]]` but the link is [[real-link]]."
    assert extract_wikilinks(text) == ["real-link"]


def test_extract_ignores_code_blocks():
    text = """
Text [[link-one]] here.

```
This [[fake-link]] is in a code block.
```

More [[link-two]].
"""
    assert extract_wikilinks(text) == ["link-one", "link-two"]


def test_normalize_strips_brackets():
    assert normalize_wikilink("[[oauth2-flow]]") == "oauth2-flow"


def test_normalize_already_normalized_passthrough():
    assert normalize_wikilink("oauth2-flow") == "oauth2-flow"


def test_normalize_strips_whitespace():
    assert normalize_wikilink("  [[oauth2-flow]]  ") == "oauth2-flow"


def test_normalize_strips_pipe_alias_with_brackets():
    assert normalize_wikilink("[[oauth2-flow|OAuth 2.0]]") == "oauth2-flow"


def test_normalize_strips_pipe_alias_without_brackets():
    assert normalize_wikilink("oauth2-flow|OAuth 2.0") == "oauth2-flow"


def test_normalize_strips_pipe_alias_with_whitespace():
    assert normalize_wikilink("  [[oauth2-flow|OAuth 2.0]]  ") == "oauth2-flow"
