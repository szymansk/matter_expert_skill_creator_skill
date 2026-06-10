import json
import subprocess
import sys
from pathlib import Path

from runtime.vault_search import search_vault


def test_search_finds_concept_with_keyword(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches


def test_search_ranks_strong_match_first(vault_dir: Path, built_indexes):
    """'session' hits session-management in title + tags + body, so it ranks #1."""
    matches = search_vault(
        query="session",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches and matches[0] == "session-management"


def test_search_returns_empty_for_no_matches(vault_dir: Path, built_indexes):
    # Single nonsense token — must tokenize to one term that is in no field.
    matches = search_vault(
        query="zzzznonexistentterm",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_filters_by_tag(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="auth",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        tags=["oauth2"],
    )
    for m in matches:
        assert m in {"oauth2-flow", "oauth2-google-flow"}


def test_search_excludes_frontmatter_content(vault_dir: Path, built_indexes):
    """Frontmatter is not indexed: 'created: 2026-..' dates appear in no body."""
    matches = search_vault(
        query="2026",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert matches == []


def test_search_top_n_truncates(vault_dir: Path, built_indexes):
    matches = search_vault(
        query="auth",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        top_n=2,
    )
    assert len(matches) <= 2


def test_search_auto_builds_index_when_missing(vault_dir: Path, built_indexes):
    """Deleting the index should trigger an automatic rebuild, not a crash."""
    built_indexes.bm25_index.unlink()
    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches
    assert built_indexes.bm25_index.exists()


def test_cli_outputs_ranked_json_list(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [sys.executable, "-m", "runtime.vault_search",
         "--vault", str(vault_dir),
         "--concept-index", str(built_indexes.concept_index),
         "--query", "OAuth2"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed


def test_cli_scores_flag_outputs_name_score_objects(vault_dir: Path, built_indexes):
    result = subprocess.run(
        [sys.executable, "-m", "runtime.vault_search",
         "--vault", str(vault_dir),
         "--concept-index", str(built_indexes.concept_index),
         "--query", "google", "--scores"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert parsed and set(parsed[0]) == {"name", "score"}
    # 'google' is a unique term: only oauth2-google-flow matches it.
    assert parsed and parsed[0]["name"] == "oauth2-google-flow"


def test_search_corrupt_index_raises_clear_error(vault_dir: Path, built_indexes):
    """A corrupt bm25_index.json yields a ValueError naming the file."""
    import pytest
    built_indexes.bm25_index.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt index"):
        search_vault(
            query="oauth2",
            vault_dir=vault_dir,
            concept_index_path=built_indexes.concept_index,
        )


def test_strip_frontmatter_still_importable_from_vault_search():
    """Backward-compatible re-export of the frontmatter helper."""
    from runtime.vault_search import _strip_frontmatter
    text = "---\ntitle: Test\n---\nBody starts here\n"
    assert _strip_frontmatter(text).startswith("Body starts here")
