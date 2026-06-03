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

## Paths (all bundled inside this skill)

Claude Code sets `${{CLAUDE_SKILL_DIR}}` to this skill's directory when the
skill activates. Every runtime command below uses absolute paths derived
from it, so the commands work regardless of the current working directory.

- Vault root:  `${{CLAUDE_SKILL_DIR}}/vault`
- Indexes:     `${{CLAUDE_SKILL_DIR}}/_index`
- Memory:      `${{CLAUDE_SKILL_DIR}}/memory`
- Scripts:     `${{CLAUDE_SKILL_DIR}}/scripts/runtime`

## When the user asks a question (Q&A mode)

1. **Layer 1 — Locate entry points.** Run:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_locate.py" \\
     --index-dir "${{CLAUDE_SKILL_DIR}}/_index" \\
     --memory-dir "${{CLAUDE_SKILL_DIR}}/memory" \\
     "<user-query>"
   ```

2. **Layer 2 — Keyword search (if Layer 1 yielded nothing useful).** Run:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_search.py" \\
     --vault "${{CLAUDE_SKILL_DIR}}/vault" \\
     --concept-index "${{CLAUDE_SKILL_DIR}}/_index/concept_index.json" \\
     --query "<keyword>"
   ```

3. **Layer 3 — Expand via typed links.** Run with the names found above:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_traverse.py" \\
     --link-graph "${{CLAUDE_SKILL_DIR}}/_index/link_graph.json" \\
     --depth 1 \\
     --from "<concept-name>"
   ```

4. **Read** the identified concept pages from `${{CLAUDE_SKILL_DIR}}/vault/concepts/`.

5. **Synthesize** the answer with explicit citations (see Citation format below).

6. **Update memory** with what was used:
   ```bash
   python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/memory_update.py" \\
     --memory-dir "${{CLAUDE_SKILL_DIR}}/memory" \\
     --query "<original user query>" \\
     --used-concepts "concept-a,concept-b"
   ```

## When the user wants to brainstorm

Detect brainstorming intent (hypothetical, "what if", "options for", etc.)
and run the scaffold:

```bash
python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_brainstorm.py" \\
  --index-dir "${{CLAUDE_SKILL_DIR}}/_index" \\
  --vault "${{CLAUDE_SKILL_DIR}}/vault" \\
  --memory-dir "${{CLAUDE_SKILL_DIR}}/memory" \\
  --topic "<topic>"
```

The output is structured JSON with `relevant_concepts`, `clusters`,
`contradictions`, `gaps`, and `entry_questions`. Use it as the scaffold to:
- Present hypotheses with confidence levels, sources, assumptions, and
  falsification criteria
- Make vault gaps (🔍) and source contradictions (⚠️) explicit
- Mark world-knowledge additions with 💡
- End with a forschende Folgefrage

## Looking up source attribution for a citation

```bash
python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/vault_cite.py" \\
  --concept-index "${{CLAUDE_SKILL_DIR}}/_index/concept_index.json" \\
  "<concept-name>"
```

## Inspecting what the memory has learned

```bash
python3 "${{CLAUDE_SKILL_DIR}}/scripts/runtime/memory_inspect.py" \\
  --memory-dir "${{CLAUDE_SKILL_DIR}}/memory"
```

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
