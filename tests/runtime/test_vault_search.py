import json
import shutil
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


def test_search_falls_back_when_ripgrep_missing(monkeypatch, vault_dir: Path, built_indexes):
    """With ripgrep absent, search_vault uses the pure-Python fallback and still
    returns correct body-content matches — produced skills need no system binaries."""
    monkeypatch.setattr("runtime.vault_search.shutil.which", lambda _: None)

    matches = search_vault(
        query="OAuth2",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    )
    assert "oauth2-flow" in matches

    # Frontmatter-only keys still must not match in the fallback path.
    assert search_vault(
        query="merged_from",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
    ) == []

    # Tag filtering still applies in the fallback path.
    tagged = search_vault(
        query="auth",
        vault_dir=vault_dir,
        concept_index_path=built_indexes.concept_index,
        tags=["oauth2"],
    )
    for m in tagged:
        assert m in {"oauth2-flow", "oauth2-google-flow"}


def test_ripgrep_and_python_paths_agree(vault_dir: Path, built_indexes):
    """When ripgrep is available, the fast path and the fallback agree.

    Skipped if ripgrep isn't installed (nothing to compare against)."""
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not installed")
    from runtime.vault_search import _search_with_ripgrep, _search_with_python

    for query in ("OAuth2", "auth", "ZZZZZZ_nope"):
        assert _search_with_ripgrep(query, vault_dir) == _search_with_python(query, vault_dir)
