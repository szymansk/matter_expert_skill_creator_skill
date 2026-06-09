import json
import subprocess
import sys
from pathlib import Path

import pytest

from runtime.bm25_build import main as bm25_build_main


def _make_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    concepts = vault / "concepts"
    concepts.mkdir(parents=True)
    (concepts / "oauth2-flow.md").write_text(
        "---\ntitle: OAuth2 Flow\ntags: [auth]\n---\nOAuth2 authorization body.\n",
        encoding="utf-8",
    )
    index_dir = tmp_path / "_index"
    index_dir.mkdir()
    concept_index = index_dir / "concept_index.json"
    concept_index.write_text(json.dumps({
        "oauth2-flow": {"title": "OAuth2 Flow", "tags": ["auth"], "aliases": []},
    }), encoding="utf-8")
    return vault, concept_index, index_dir


def test_bm25_build_writes_index_beside_concept_index(tmp_path: Path):
    vault, concept_index, index_dir = _make_vault(tmp_path)
    rc = bm25_build_main(["--vault", str(vault), "--concept-index", str(concept_index)])
    assert rc == 0
    out = index_dir / "bm25_index.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "oauth2" in data["postings"]


def test_bm25_build_honors_explicit_out(tmp_path: Path):
    vault, concept_index, _ = _make_vault(tmp_path)
    out = tmp_path / "custom" / "bm25.json"
    rc = bm25_build_main([
        "--vault", str(vault), "--concept-index", str(concept_index), "--out", str(out),
    ])
    assert rc == 0
    assert out.exists()


def test_bm25_build_cli_runs_as_module(tmp_path: Path):
    vault, concept_index, index_dir = _make_vault(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "runtime.bm25_build",
         "--vault", str(vault), "--concept-index", str(concept_index)],
        capture_output=True, text=True, check=True,
    )
    assert (index_dir / "bm25_index.json").exists()
