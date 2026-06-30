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
    assert len(stem(" run")) >= 3
    assert stem("rerun") == "rerun"  # trimmed DE suffix list leaves it intact


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
