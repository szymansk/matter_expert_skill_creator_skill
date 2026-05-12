"""Smoke test that both execution modes are documented and reachable."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


SKILL_MD = REPO / "docs-to-skill" / "skills" / "docs-to-skill" / "SKILL.md"


def test_subscription_mode_skill_md_exists():
    assert SKILL_MD.exists(), (
        "SKILL.md must live under docs-to-skill/skills/docs-to-skill/ "
        "(Claude Code plugin layout requirement)"
    )


def test_subscription_mode_agents_dir_has_12_files():
    agents = list((REPO / "docs-to-skill" / "agents").glob("*.md"))
    assert len(agents) == 12


def test_api_direct_mode_cli_module_importable():
    # The original API-direct path still works.
    from builder.integration.cli import main
    assert callable(main)


def test_helpers_cli_module_importable():
    # The subscription-mode helpers are reachable.
    from builder.integration.helpers_cli import main
    assert callable(main)


def test_skill_md_documents_both_modes():
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Subscription-native" in content or "subscription-native" in content
    assert "API-direct" in content or "api-direct" in content
