from runtime.bm25 import tokenize


def test_tokenize_lowercases_and_splits_on_nonalnum():
    assert tokenize("OAuth2 Flow, refresh-token!") == ["oauth2", "flow", "refresh", "token"]


def test_tokenize_keeps_digits_drops_underscore_and_punctuation():
    assert tokenize("merged_from: v2.0 (RFC-6749)") == ["merged", "from", "v2", "0", "rfc", "6749"]


def test_tokenize_empty_string_returns_empty_list():
    assert tokenize("") == []
