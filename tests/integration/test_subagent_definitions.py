"""Validates that all subagent definition files are well-formed."""
import re
from pathlib import Path

import frontmatter
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "docs-to-skill" / "agents"


REQUIRED_FIELDS = {"name", "description", "model"}
ALLOWED_MODELS = {"haiku", "sonnet", "opus"}


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_has_required_frontmatter_fields(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_FIELDS - set(fm.metadata)
    assert not missing, f"{path.name} missing fields: {missing}"


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_model_is_valid(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.metadata["model"] in ALLOWED_MODELS


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_name_matches_filename(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    expected = path.stem
    assert fm.metadata["name"] == expected


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_description_is_non_empty(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.metadata["description"].strip()


@pytest.mark.parametrize("path", _agent_files(),
                          ids=lambda p: p.name)
def test_agent_has_system_prompt_body(path: Path):
    fm = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert fm.content.strip(), f"{path.name} has empty system prompt"


def test_all_expected_agents_exist():
    expected = {
        "analyzer-agent", "extractor-agent", "coverage-transform-agent",
        "cluster-agent", "merger-agent", "linker-agent",
        "translation-qa-agent", "citation-qa-agent", "coherence-qa-agent",
        "coverage-qa-agent", "vision-pdf-agent", "trigger-desc-agent",
    }
    actual = {p.stem for p in _agent_files()}
    missing = expected - actual
    assert not missing, f"missing agent definitions: {missing}"


def test_models_match_design_spec():
    """Per spec §4.1: per-phase model assignments."""
    expected_models = {
        "analyzer-agent": "haiku",
        "extractor-agent": "haiku",
        "coverage-transform-agent": "haiku",
        "cluster-agent": "sonnet",
        "merger-agent": "sonnet",
        "linker-agent": "sonnet",
        "translation-qa-agent": "sonnet",
        "citation-qa-agent": "sonnet",
        "coherence-qa-agent": "sonnet",
        "coverage-qa-agent": "haiku",
        "vision-pdf-agent": "sonnet",
        "trigger-desc-agent": "sonnet",
    }
    for path in _agent_files():
        fm = frontmatter.loads(path.read_text(encoding="utf-8"))
        expected = expected_models.get(path.stem)
        if expected is None:
            continue
        assert fm.metadata["model"] == expected, (
            f"{path.stem}: expected {expected}, got {fm.metadata['model']}"
        )
