from pathlib import Path

from runtime.text import (
    tokenize, stem, load_synonym_groups, build_synonym_index, expand_token,
)


def test_tokenize_splits_drops_stopwords_and_short_tokens():
    toks = tokenize("Sind kleine Bugfixes erlaubt, ohne einen Rerun?")
    assert "bugfixes" in toks and "rerun" in toks and "kleine" in toks
    assert "sind" not in toks and "ohne" not in toks and "einen" not in toks


def test_tokenize_splits_on_hyphen_and_dedupes():
    assert tokenize("Rerun-Strategie rerun") == ["rerun", "strategie"]


def test_stem_folds_english_plurals_and_suffixes():
    assert stem("bugfixes") == "bugfix"
    assert stem("tokens") == "token"
    assert stem("resumable").startswith("resum")


def test_stem_never_shorter_than_three():
    # "aes" ends with "es", but stripping would leave "a" (<3), so the guard
    # blocks the strip and the token is returned intact.
    assert stem("aes") == "aes"
    assert stem("rerun") == "rerun"  # no EN/DE suffix matches; returned as-is


def test_load_synonym_groups_missing_file_is_empty(tmp_path: Path):
    assert load_synonym_groups(tmp_path / "nope.json") == []
    assert load_synonym_groups(None) == []


def test_load_synonym_groups_reads_groups(tmp_path: Path):
    p = tmp_path / "synonyms.json"
    p.write_text('{"groups": [["rerun", "resume", "Idempotenz"]]}', encoding="utf-8")
    assert load_synonym_groups(p) == [["rerun", "resume", "idempotenz"]]


def test_expand_token_includes_synonyms_and_stems():
    syn = build_synonym_index([["rerun", "resume", "idempotenz"]])
    variants = expand_token("rerun", syn)
    assert {"rerun", "resume", "idempotenz"} <= variants
    # plain token with no group still yields itself + stem
    assert "bugfix" in expand_token("bugfixes", build_synonym_index([]))


def test_expand_token_bridges_inflected_query_via_stem():
    """Synonyms must compose with stemming: an inflected/plural query token
    resolves to its group after stemming (regression — expand_token previously
    only looked up the raw surface form and silently dropped the synonyms)."""
    syn = build_synonym_index([["bugfix", "fix", "patch"]])
    assert {"fix", "patch"} <= expand_token("bugfixes", syn)

    syn2 = build_synonym_index([["rerun", "resume", "idempotenz", "resumable"]])
    assert {"resume", "idempotenz"} <= expand_token("reruns", syn2)


def test_stem_does_not_over_strip_english_en_words():
    """The short DE 'en'/'em' suffixes are excluded so common English words are
    not mangled into 3-char false-positive stems (e.g. token -> tok)."""
    for word in ("token", "broken", "given", "system", "golden", "oxygen"):
        assert stem(word) == word
