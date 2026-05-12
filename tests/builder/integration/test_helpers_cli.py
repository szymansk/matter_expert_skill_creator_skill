import json
import subprocess
import sys
from datetime import date
from pathlib import Path


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "builder.integration.helpers_cli", *args],
        capture_output=True, text=True,
    )


def test_helpers_cli_help_lists_all_subcommands():
    r = _run(["--help"])
    assert r.returncode == 0
    for sub in [
        "ingest-deterministic", "write-concept", "write-source",
        "write-moc", "apply-links", "apply-merge",
        "build-indexes", "emit-finalize",
    ]:
        assert sub in r.stdout


def test_ingest_deterministic_processes_text_file(tmp_path: Path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "doc.md").write_text("# X\n\nbody " * 50, encoding="utf-8")
    out = tmp_path / "work"

    r = _run(["ingest-deterministic",
              "--input", str(in_dir),
              "--output", str(out)])
    assert r.returncode == 0
    # Report on stdout
    report = json.loads(r.stdout)
    assert "results" in report
    # One result for doc.md, marked as text/passthrough → no vision needed
    entry = report["results"]["doc.md"]
    assert entry["needs_vision"] is False
    # Files on disk
    assert (out / "raw" / "doc.md").exists()
    assert (out / "raw" / "doc.meta.json").exists()


def test_write_concept_creates_valid_page(tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("# OAuth2\n\nbody", encoding="utf-8")
    vault = tmp_path / "vault"

    r = _run(["write-concept",
              "--vault", str(vault),
              "--name", "oauth2-flow",
              "--title", "OAuth2 Flow",
              "--source-file", "handbook.md",
              "--source-sections", "3.1,3.2",
              "--body-file", str(body_file)])
    assert r.returncode == 0
    # Reads back as a valid ConceptPage
    from matter_expert import ConceptPage
    page = ConceptPage.read(vault / "concepts" / "oauth2-flow.md")
    assert page.frontmatter.title == "OAuth2 Flow"
    assert page.frontmatter.sources[0].file == "handbook.md"
    assert page.frontmatter.sources[0].sections == ["3.1", "3.2"]


def test_write_moc_creates_valid_page(tmp_path: Path):
    vault = tmp_path / "vault"
    r = _run(["write-moc",
              "--vault", str(vault),
              "--name", "auth",
              "--title", "Authentication",
              "--children", "oauth2-flow,jwt-tokens"])
    assert r.returncode == 0
    from matter_expert import MOCPage
    page = MOCPage.read(vault / "MOCs" / "auth.md")
    assert page.frontmatter.children == ["oauth2-flow", "jwt-tokens"]


def test_apply_links_updates_concept_frontmatter(tmp_path: Path):
    # Seed a concept first
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    vault = tmp_path / "vault"
    _run(["write-concept",
          "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])

    links_file = tmp_path / "links.json"
    links_file.write_text(json.dumps({
        "related": ["y"], "prerequisites": [],
        "examples": [], "contrasts": [], "refines": [],
    }), encoding="utf-8")

    r = _run(["apply-links",
              "--vault", str(vault),
              "--concept", "x",
              "--links-json", str(links_file)])
    assert r.returncode == 0

    from matter_expert import ConceptPage
    page = ConceptPage.read(vault / "concepts" / "x.md")
    assert page.frontmatter.related == ["y"]


def test_apply_merge_replaces_members_with_merged_page(tmp_path: Path):
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")

    # Seed two concepts to merge
    for name in ("oauth-a", "oauth-b"):
        _run(["write-concept", "--vault", str(vault),
              "--name", name, "--title", name.upper(),
              "--source-file", f"{name}.md", "--source-sections", "",
              "--body-file", str(body_file)])

    merged_body = tmp_path / "merged.md"
    merged_body.write_text("# Merged\n\nmerged body", encoding="utf-8")

    r = _run(["apply-merge",
              "--vault", str(vault),
              "--members", "oauth-a,oauth-b",
              "--merged-body-file", str(merged_body)])
    assert r.returncode == 0

    # oauth-a survives with merged body + merged_from list
    from matter_expert import ConceptPage
    surv = ConceptPage.read(vault / "concepts" / "oauth-a.md")
    assert "merged body" in surv.body
    assert set(surv.frontmatter.merged_from) == {"oauth-a", "oauth-b"}
    # oauth-b is gone
    assert not (vault / "concepts" / "oauth-b.md").exists()


def test_build_indexes_writes_four_files(tmp_path: Path):
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    _run(["write-concept", "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])

    index_dir = tmp_path / "_index"
    r = _run(["build-indexes",
              "--vault", str(vault),
              "--index-dir", str(index_dir)])
    assert r.returncode == 0
    assert (index_dir / "concept_index.json").exists()
    assert (index_dir / "moc_map.json").exists()
    assert (index_dir / "link_graph.json").exists()
    assert (index_dir / "alias_map.json").exists()


def test_emit_finalize_produces_plugin_structure(tmp_path: Path):
    # Set up a tiny vault first
    vault = tmp_path / "vault"
    body_file = tmp_path / "body.md"
    body_file.write_text("body", encoding="utf-8")
    _run(["write-concept", "--vault", str(vault),
          "--name", "x", "--title", "X",
          "--source-file", "s.md", "--source-sections", "",
          "--body-file", str(body_file)])
    _run(["write-source", "--vault", str(vault),
          "--name", "s", "--original-file", "s.pdf",
          "--page-count", "1", "--body-file", str(body_file)])
    index_dir = tmp_path / "_index"
    _run(["build-indexes", "--vault", str(vault), "--index-dir", str(index_dir)])

    plugin = tmp_path / "plugin"
    r = _run([
        "emit-finalize",
        "--plugin-root", str(plugin),
        "--plugin-name", "test-skill",
        "--version", "0.1.0",
        "--description", "Test skill.",
        "--author", "tester",
        "--vault", str(vault),
        "--index-dir", str(index_dir),
        "--skill-description", "Pushy trigger description text.",
    ])
    assert r.returncode == 0
    assert (plugin / ".claude-plugin" / "plugin.json").exists()
    assert (plugin / "README.md").exists()
    assert (plugin / "skills" / "test-skill" / "SKILL.md").exists()
    # Bundled runtime
    assert (plugin / "skills" / "test-skill" / "scripts" / "runtime" / "vault_locate.py").exists()
    # Initial memory
    assert (plugin / "skills" / "test-skill" / "memory" / "query_cache.json").exists()
