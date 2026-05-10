import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.vault_cite import get_citation


def test_get_citation_returns_concept_metadata(built_indexes):
    """get_citation returns the relevant fields from the concept index."""
    citation = get_citation("oauth2-flow", built_indexes.concept_index)

    assert citation["concept"] == "oauth2-flow"
    assert citation["title"] == "OAuth2 Flow"
    assert citation["path"] == "concepts/oauth2-flow.md"
    assert "auth" in citation["tags"]


def test_get_citation_unknown_concept_raises(built_indexes):
    with pytest.raises(KeyError):
        get_citation("does-not-exist", built_indexes.concept_index)


def test_get_citation_includes_summary(built_indexes):
    """Citation includes the concept summary (first ~120 chars of body)."""
    citation = get_citation("oauth2-flow", built_indexes.concept_index)
    assert "summary" in citation
    assert isinstance(citation["summary"], str)


def test_cli_outputs_json_for_known_concept(built_indexes):
    """Run the script as a CLI and verify JSON output."""
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_cite",
            "--concept-index", str(built_indexes.concept_index),
            "oauth2-flow",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["concept"] == "oauth2-flow"
    assert parsed["title"] == "OAuth2 Flow"


def test_cli_exits_nonzero_for_unknown_concept(built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_cite",
            "--concept-index", str(built_indexes.concept_index),
            "does-not-exist",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "does-not-exist" in result.stderr
