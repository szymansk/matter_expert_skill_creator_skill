"""Generate the SKILL.md for the expert skill plugin."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder.emit.prompts import trigger_desc_prompt
from builder.ingest.protocols import AgentCaller


@dataclass(frozen=True)
class SkillMdMeta:
    skill_name: str
    dominant_topics: list[str]


SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
---

# {title}

This skill answers questions and supports brainstorming based on the vault
of curated knowledge bundled in this plugin.

## When the user asks a question (Q&A mode)

1. Run `scripts/vault_locate.py` with the user's query to find entry points.
2. If needed, run `scripts/vault_search.py` for keyword search.
3. Run `scripts/vault_traverse.py` to expand the context via typed links.
4. Read the identified concept pages from `vault/concepts/`.
5. Synthesize the answer with explicit citations using the citation format below.
6. After answering, run `scripts/memory_update.py` to record what was used.

## When the user wants to brainstorm

1. Detect brainstorming intent (hypothetical, "what if", "options for", etc.).
2. Run `scripts/vault_brainstorm.py` for the topic — get a hypothesis scaffold.
3. Present hypotheses with confidence levels, sources, assumptions,
   and falsification criteria.
4. Make vault gaps (🔍) and source contradictions (⚠️) explicit.
5. Mark world-knowledge additions with 💡.
6. End with a forschende Folgefrage.

## Citation format

Cite vault concepts as `[[concept-name]]` and the underlying source as
`Source.pdf §X.Y`. Always show citations alongside the claim they support.
"""


def generate_skill_md(
    skill_dir: Path,
    meta: SkillMdMeta,
    agent: AgentCaller,
) -> Path:
    """Generate the SKILL.md for an expert skill and write it to disk."""
    description = _generate_description(meta, agent)
    content = SKILL_MD_TEMPLATE.format(
        name=meta.skill_name,
        description=description.replace("\n", " ").strip(),
        title=meta.skill_name.replace("-", " ").title(),
    )
    path = skill_dir / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _generate_description(meta: SkillMdMeta, agent: AgentCaller) -> str:
    prompt = trigger_desc_prompt(
        skill_name=meta.skill_name,
        dominant_topics=list(meta.dominant_topics),
    )
    response = agent.call(prompt, model="sonnet")
    return response.text.strip()
