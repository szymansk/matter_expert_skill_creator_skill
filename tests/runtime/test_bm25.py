from runtime.bm25 import tokenize
from runtime.bm25 import strip_frontmatter


def test_tokenize_lowercases_and_splits_on_nonalnum():
    assert tokenize("OAuth2 Flow, refresh-token!") == ["oauth2", "flow", "refresh", "token"]


def test_tokenize_keeps_digits_drops_underscore_and_punctuation():
    assert tokenize("merged_from: v2.0 (RFC-6749)") == ["merged", "from", "v2", "0", "rfc", "6749"]


def test_tokenize_empty_string_returns_empty_list():
    assert tokenize("") == []


def test_strip_frontmatter_removes_block_and_leading_newline():
    text = "---\ntitle: Test\ntags: [a]\n---\nBody starts here\n"
    body = strip_frontmatter(text)
    assert not body.startswith("\n")
    assert body.startswith("Body starts here")


def test_strip_frontmatter_without_frontmatter_is_unchanged():
    assert strip_frontmatter("Just body.") == "Just body."


def test_strip_frontmatter_malformed_returns_whole_text():
    text = "---\ntitle: unclosed frontmatter\n"
    assert strip_frontmatter(text) == text


def test_strip_frontmatter_ignores_unindented_triple_dash_in_value():
    # A value line beginning with "---" but not exactly "---" must NOT be
    # treated as the closing delimiter; the real closing "---" comes later.
    text = "---\ntitle: Test\nbody_sample: \"x\"\n--- not a close\n---\nReal body\n"
    body = strip_frontmatter(text)
    assert body.startswith("Real body")
