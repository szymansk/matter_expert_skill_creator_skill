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


from runtime.bm25 import build_bm25_index


def _sample_docs():
    return [
        {"name": "oauth2-flow", "title": "OAuth2 Flow", "aliases": [],
         "tags": ["auth", "oauth2"], "body": "OAuth2 is an authorization framework."},
        {"name": "jwt-tokens", "title": "JWT Tokens", "aliases": ["json web token"],
         "tags": ["auth", "token"], "body": "A JWT is a signed token used for auth."},
    ]


def test_build_index_has_expected_top_level_shape():
    idx = build_bm25_index(_sample_docs())
    assert idx["N"] == 2
    assert idx["fields"] == ["title", "aliases", "tags", "body"]
    assert set(idx["avg_field_len"]) == {"title", "aliases", "tags", "body"}
    assert set(idx["doc_field_len"]) == {"oauth2-flow", "jwt-tokens"}


def test_build_index_postings_count_per_field():
    idx = build_bm25_index(_sample_docs())
    # "oauth2" appears in oauth2-flow's title (1), tags (1), body (1).
    assert idx["postings"]["oauth2"]["oauth2-flow"] == {"title": 1, "tags": 1, "body": 1}
    # "auth" appears in both docs' tags, and in jwt-tokens' body once.
    assert idx["postings"]["auth"]["jwt-tokens"]["tags"] == 1
    assert idx["postings"]["auth"]["jwt-tokens"]["body"] == 1


def test_build_index_doc_field_len_counts_tokens():
    idx = build_bm25_index(_sample_docs())
    assert idx["doc_field_len"]["oauth2-flow"]["title"] == 2  # "oauth2", "flow"
    assert idx["doc_field_len"]["jwt-tokens"]["aliases"] == 3  # "json", "web", "token"


def test_build_index_empty_docs():
    idx = build_bm25_index([])
    assert idx["N"] == 0
    assert idx["postings"] == {}
    assert idx["avg_field_len"] == {"title": 0.0, "aliases": 0.0, "tags": 0.0, "body": 0.0}


import json
from pathlib import Path

from runtime.bm25 import assemble_docs


def test_assemble_docs_merges_body_and_index_metadata(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "oauth2-flow.md").write_text(
        "---\ntitle: OAuth2 Flow\ntags: [auth]\n---\nOAuth2 body text.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text(json.dumps({
        "oauth2-flow": {"title": "OAuth2 Flow", "tags": ["auth", "oauth2"], "aliases": ["oauth"]},
    }), encoding="utf-8")

    docs = assemble_docs(vault, concept_index)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["name"] == "oauth2-flow"
    assert doc["title"] == "OAuth2 Flow"
    assert doc["tags"] == ["auth", "oauth2"]
    assert doc["aliases"] == ["oauth"]
    assert doc["body"].startswith("OAuth2 body text")
    assert "title:" not in doc["body"]  # frontmatter stripped


def test_assemble_docs_handles_concept_absent_from_index(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "orphan.md").write_text("---\ntitle: X\n---\nBody.\n", encoding="utf-8")
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text("{}", encoding="utf-8")

    docs = assemble_docs(vault, concept_index)
    assert docs[0]["name"] == "orphan"
    assert docs[0]["title"] == ""
    assert docs[0]["tags"] == []
    assert docs[0]["aliases"] == []
