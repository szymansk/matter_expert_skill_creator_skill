import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.vault_search import search_vault


# No module-level skip: search now works with or without ripgrep. When `rg` is on
# PATH the fast path runs; otherwise the pure-Python fallback runs. Both must give
# the same results, so the behavioral tests below are valid in either environment.


def test_search_finds_concept_with_keyword(vault_dir: Path, built_indexes):
    """A keyword that appears in oauth2-flow.md body should return that concept."""
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_returns_empty_for_no_matches(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="ZZZZZZ_definitely_not_in_vault",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_filters_by_tag(vault_dir: Path, built_indexes):
    """When tags are provided, results are restricted to concepts with those tags."""
    matches = search_vault(
        query="auth",  # appears widely
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        tags=["oauth2"],
    )
    # Only concepts tagged oauth2 should remain.
    for m in matches:
        assert m in {"oauth2-flow", "oauth2-google-flow"}


def test_search_does_not_match_frontmatter_only_keywords(vault_dir: Path, built_indexes):
    """Search is body-content matching, not frontmatter.

    'merged_from' is a frontmatter key, never appears in any concept body.
    """
    matches = search_vault(
        query="merged_from",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_cli_outputs_json_list(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_search",
            "--vault", str(vault_dir),
            "--concept-index", str(built_indexes.concept_index),
            "--query", "OAuth2",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed


def test_strip_frontmatter_no_leading_newline(tmp_path: Path):
    """Stripping frontmatter must not leave a leading newline."""
    from runtime.vault_search import _strip_frontmatter

    text = "---\ntitle: Test\n---\nBody starts here\n"
    body = _strip_frontmatter(text)
    assert not body.startswith("\n")
    assert body.startswith("Body starts here")


def test_strip_frontmatter_no_frontmatter_unchanged():
    """Text without frontmatter is returned as-is."""
    from runtime.vault_search import _strip_frontmatter
    text = "Just body, no frontmatter."
    assert _strip_frontmatter(text) == text


def test_search_tokenizes_natural_question(vault_dir: Path, built_indexes):
    """A whole natural-language question matches via its content tokens, not as
    one verbatim substring."""
    matches = search_vault(
        query="how does the oauth2 flow actually work?",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_ranks_rarer_token_concept_higher(tmp_path: Path):
    """The `rare` concept matches BOTH query tokens (including the rare
    `idempotenz` token) while the common* concepts match only `widget`.
    Because `rare` accumulates higher IDF weight it outranks the
    common-only concepts — this tests multi-token IDF scoring, not
    pure-IDF isolation."""
    import json
    # Build a tiny synthetic vault + index inline.
    tmp = tmp_path
    concepts = tmp / "concepts"; concepts.mkdir()
    (concepts / "rare.md").write_text(
        "---\ntitle: Rare\n---\nThe widget uses idempotenz heavily.\n", encoding="utf-8")
    (concepts / "common1.md").write_text(
        "---\ntitle: C1\n---\nThe widget is common.\n", encoding="utf-8")
    (concepts / "common2.md").write_text(
        "---\ntitle: C2\n---\nThe widget is common too.\n", encoding="utf-8")
    index = {
        "rare": {"path": "concepts/rare.md", "title": "Rare", "summary": "",
                 "tags": [], "aliases": [], "moc": []},
        "common1": {"path": "concepts/common1.md", "title": "C1", "summary": "",
                    "tags": [], "aliases": [], "moc": []},
        "common2": {"path": "concepts/common2.md", "title": "C2", "summary": "",
                    "tags": [], "aliases": [], "moc": []},
    }
    cidx = tmp / "concept_index.json"
    cidx.write_text(json.dumps(index), encoding="utf-8")

    ranked = search_vault(query="widget idempotenz", vault_dir=tmp,
                          concept_index_path=cidx)
    assert ranked[0] == "rare"  # matches both tokens incl. the rare one


def test_search_synonym_expansion_bridges_vocabulary(tmp_path: Path):
    import json
    concepts = tmp_path / "concepts"; concepts.mkdir()
    (concepts / "resilience.md").write_text(
        "---\ntitle: Resilience\n---\nTasks support resume after a crash.\n",
        encoding="utf-8")
    index = {"resilience": {"path": "concepts/resilience.md", "title": "Resilience",
                            "summary": "", "tags": [], "aliases": [], "moc": []}}
    cidx = tmp_path / "concept_index.json"
    cidx.write_text(json.dumps(index), encoding="utf-8")
    syn = tmp_path / "synonyms.json"
    syn.write_text('{"groups": [["rerun", "resume"]]}', encoding="utf-8")

    # Query says "rerun"; the body says "resume"; the synonym group bridges them.
    matches = search_vault(query="rerun", vault_dir=tmp_path,
                           concept_index_path=cidx, synonyms_path=syn)
    assert "resilience" in matches
    # Without synonyms there is no match.
    assert search_vault(query="rerun", vault_dir=tmp_path,
                        concept_index_path=cidx) == []


def test_search_limit_caps_results(vault_dir: Path, built_indexes):
    all_matches = search_vault(query="auth security token http session encryption",
                               vault_dir=vault_dir,
                               concept_index_path=built_indexes.concept_index)
    assert len(all_matches) > 2          # cap is meaningful only if there are >2 candidates
    limited = search_vault(query="auth security token http session encryption",
                           vault_dir=vault_dir,
                           concept_index_path=built_indexes.concept_index,
                           limit=2)
    assert len(limited) == 2


def test_single_keyword_preserves_prior_matches(vault_dir: Path, built_indexes):
    """Regression contract: a single keyword still returns its old body matches
    (now possibly ranked / with extras), never fewer."""
    matches = set(search_vault(query="auth", vault_dir=vault_dir,
                               concept_index_path=built_indexes.concept_index))
    assert {"basic-auth", "oauth2-flow", "oauth2-google-flow"} <= matches
