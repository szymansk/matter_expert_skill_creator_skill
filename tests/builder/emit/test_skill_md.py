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


def test_skill_md_references_correct_script_paths(tmp_path: Path, canned_agent):
    """SKILL.md must reference scripts/runtime/ not scripts/ directly.

    Runtime scripts live at scripts/runtime/<name>.py after bundling so that
    ``from runtime.xxx import`` resolves correctly.
    """
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=["auth"]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")
    # Must reference the scripts/runtime/ subpackage, not flat scripts/
    assert "scripts/runtime/vault_locate.py" in content
    assert "scripts/runtime/vault_search.py" in content
    assert "scripts/runtime/memory_update.py" in content
    assert "scripts/runtime/vault_brainstorm.py" in content
    # Must NOT reference the old flat paths
    assert "scripts/vault_locate.py" not in content
    assert "scripts/vault_brainstorm.py" not in content


def test_skill_md_passes_required_args_to_scripts(tmp_path: Path, canned_agent):
    """Every runtime invocation in SKILL.md must pass the args the script requires.

    vault_locate.py and vault_brainstorm.py require --index-dir + --memory-dir.
    memory_update.py requires --memory-dir.
    vault_search.py requires --vault + --concept-index.
    vault_traverse.py requires --link-graph.
    """
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=["topic"]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")

    # vault_locate block must include both required flags.
    locate_idx = content.index("vault_locate.py")
    locate_block = content[locate_idx:locate_idx + 400]
    assert "--index-dir" in locate_block
    assert "--memory-dir" in locate_block

    # vault_brainstorm block.
    bs_idx = content.index("vault_brainstorm.py")
    bs_block = content[bs_idx:bs_idx + 400]
    assert "--index-dir" in bs_block
    assert "--vault" in bs_block
    assert "--memory-dir" in bs_block

    # memory_update block.
    mu_idx = content.index("memory_update.py")
    mu_block = content[mu_idx:mu_idx + 400]
    assert "--memory-dir" in mu_block

    # CLAUDE_SKILL_DIR must be referenced (so paths are absolute, not cwd-dependent).
    assert "CLAUDE_SKILL_DIR" in content


def test_skill_md_template_uses_correct_runtime_paths_relative_to_skill_dir(
    tmp_path: Path, canned_agent,
):
    """All paths must resolve from ${CLAUDE_SKILL_DIR}, not be relative."""
    skill_dir = tmp_path / "skills" / "x"
    skill_dir.mkdir(parents=True)
    path = generate_skill_md(
        skill_dir=skill_dir,
        meta=SkillMdMeta(skill_name="x", dominant_topics=[]),
        agent=canned_agent,
    )
    content = path.read_text(encoding="utf-8")
    # The 4 standard subdirectories of a generated plugin's skill dir.
    assert "${CLAUDE_SKILL_DIR}/_index" in content
    assert "${CLAUDE_SKILL_DIR}/memory" in content
    assert "${CLAUDE_SKILL_DIR}/vault" in content
    assert "${CLAUDE_SKILL_DIR}/scripts/runtime" in content
