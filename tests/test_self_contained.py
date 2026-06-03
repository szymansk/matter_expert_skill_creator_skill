"""The plugin must work immediately after install with zero third-party packages.

These tests are the regression guard for that promise. They run the bundled code
in a *fully isolated* interpreter:

* ``-S`` disables site-packages (nothing pip-installed is visible), and
* ``-E`` ignores ``PYTHONPATH`` and other env vars,

then inject *only* the plugin's ``scripts/lib`` onto ``sys.path``. If anything in
the bundle needs a pip package, these tests fail — which is exactly what we want,
because the real plugin runs in environments where no such package exists.
"""
import subprocess
import sys
from pathlib import Path

LIB = (
    Path(__file__).resolve().parent.parent
    / "docs-to-skill" / "skills" / "docs-to-skill" / "scripts" / "lib"
)


def _run_isolated(body: str) -> subprocess.CompletedProcess:
    """Run `body` in an interpreter with no site-packages and no env, with only
    the plugin lib dir on sys.path."""
    code = f"import sys; sys.path.insert(0, {str(LIB)!r})\n{body}"
    return subprocess.run(
        [sys.executable, "-S", "-E", "-c", code],
        capture_output=True, text=True,
    )


def test_lib_dir_exists():
    assert LIB.is_dir(), f"bundled lib dir missing: {LIB}"
    # The vendored pure-Python YAML must travel with the plugin.
    assert (LIB / "yaml" / "__init__.py").exists(), "vendored yaml not bundled"


def test_bundle_imports_with_no_third_party_packages():
    r = _run_isolated(
        "import matter_expert, builder, runtime, yaml\n"
        "import builder.integration.helpers_cli\n"
        "import builder.integration.cli\n"
        "import matter_expert.concept, matter_expert.frontmatter, matter_expert.moc\n"
        "print('OK', yaml.__with_libyaml__)\n"
    )
    assert r.returncode == 0, f"isolated import failed:\n{r.stderr}"
    assert r.stdout.startswith("OK")
    # Vendored YAML is the pure-Python build (no compiled extension required).
    assert "False" in r.stdout


def test_third_party_frontmatter_is_not_a_dependency():
    """Guard against re-introducing python-frontmatter."""
    r = _run_isolated(
        "import importlib.util as u\n"
        "assert u.find_spec('frontmatter') is None, 'python-frontmatter must not be a dependency'\n"
        "print('OK')\n"
    )
    assert r.returncode == 0, f"frontmatter dependency reintroduced:\n{r.stderr}"
    assert r.stdout.strip() == "OK"


def test_frontmatter_roundtrip_works_isolated():
    """The YAML-backed frontmatter parser works with only the vendored yaml."""
    r = _run_isolated(
        "from matter_expert.frontmatter import parse_frontmatter, write_frontmatter, ParsedDocument\n"
        "doc = ParsedDocument(metadata={'title': 'T', 'tags': ['a', 'b'],"
        " 'sources': [{'file': 'x.pdf', 'sections': ['1.1']}]}, body='# Body\\n')\n"
        "again = parse_frontmatter(write_frontmatter(doc))\n"
        "assert again.metadata == doc.metadata, again.metadata\n"
        "assert again.body.strip() == doc.body.strip()\n"
        "print('OK')\n"
    )
    assert r.returncode == 0, f"isolated frontmatter roundtrip failed:\n{r.stderr}"
    assert r.stdout.strip() == "OK"


def test_doctor_runs_isolated():
    """The preflight check itself must run with zero third-party packages."""
    r = _run_isolated(
        "from builder.integration.helpers_cli import main\n"
        "raise SystemExit(main(['doctor']))\n"
    )
    assert r.returncode == 0, f"doctor failed in isolation:\n{r.stderr}"
    assert "environment check" in r.stdout
