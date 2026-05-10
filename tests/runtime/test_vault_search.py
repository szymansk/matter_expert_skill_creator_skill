import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.vault_search import search_vault


pytestmark = pytest.mark.skipif(
    shutil.which("rg") is None,
    reason="ripgrep not installed",
)


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


def test_search_raises_when_ripgrep_missing(monkeypatch, vault_dir: Path, built_indexes):
    """If ripgrep is not on PATH, search_vault must raise a clear error."""
    monkeypatch.setattr("runtime.vault_search.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="ripgrep"):
        search_vault(
            query="x",
            vault_dir=vault_dir,
            concept_index_path=built_indexes.concept_index,
        )
