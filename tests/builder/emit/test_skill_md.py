from pathlib import Path

from builder.emit.skill_md import generate_skill_md, SkillMdMeta


def test_generate_skill_md_writes_file(tmp_path: Path, canned_agent):
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)

    meta = SkillMdMeta(
        skill_name="my-skill",
        dominant_topics=["oauth2", "jwt"],
    )
    path = generate_skill_md(skill_dir=skill_dir, meta=meta, agent=canned_agent)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "name: my-skill" in content
    assert "description:" in content


def test_skill_md_uses_sonnet(tmp_path: Path, canned_agent):
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=[]),
        agent=canned_agent,
    )
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_skill_md_includes_workflow_sections(tmp_path: Path, canned_agent):
    """SKILL.md must document Q&A and brainstorming workflows + citation format."""
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=["auth"]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")
    assert "Q&A" in content or "answer" in content.lower()
    assert "brainstorm" in content.lower()
    assert "citation" in content.lower() or "source" in content.lower()
