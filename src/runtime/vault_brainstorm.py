"""Brainstorming scaffold for the runtime.

Produces a structured JSON skeleton that Claude dresses up into prose
hypotheses. The Python side does the work that's heuristic-friendly:
- relevant_concepts:    locate + traverse depth=2 (broad sweep)
- clusters:             group concepts by shared tags
- contradictions:       concepts with multiple sources flagged for review
- gaps:                 topic words not represented in the vault
- entry_questions:      generated when too many concepts match (need to narrow)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from runtime.index import IndexPaths, load_concept_index
from runtime.vault_locate import locate_entry_points
from runtime.vault_traverse import traverse


BROAD_MATCH_THRESHOLD = 5


def brainstorm(
    topic: str,
    index_dir: Path,
    vault_dir: Path,
    memory_dir: Path,
) -> dict[str, Any]:
    """Build the brainstorming JSON scaffold for a topic."""
    index_paths = IndexPaths(index_dir=index_dir)
    concept_index = load_concept_index(index_paths.concept_index)

    # Step 1: locate entry points for the topic.
    located = locate_entry_points(
        query=topic,
        index_dir=index_dir,
        memory_dir=memory_dir,
    )
    entry_concepts = list(located["matches"])

    # Step 2: traverse depth=2 from entry concepts.
    if entry_concepts:
        expanded = traverse(
            starts=entry_concepts,
            link_graph_path=index_paths.link_graph,
            depth=2,
        )
    else:
        expanded = []

    # Build relevant_concepts list with metadata.
    relevant_concepts = []
    for name in expanded:
        if name not in concept_index:
            continue
        relevant_concepts.append({
            "name": name,
            "title": concept_index[name].get("title", name),
            "tags": list(concept_index[name].get("tags", [])),
            "summary": concept_index[name].get("summary", ""),
        })

    # Step 3: cluster relevant concepts by shared tag.
    by_tag: dict[str, list[str]] = defaultdict(list)
    for c in relevant_concepts:
        for tag in c["tags"]:
            by_tag[tag].append(c["name"])
    clusters = [
        {"tag": tag, "concepts": sorted(names)}
        for tag, names in sorted(by_tag.items())
        if len(names) > 1
    ]

    # Step 4: flag contradiction candidates (concepts with multiple sources).
    contradictions: list[dict[str, Any]] = []
    for c in relevant_concepts:
        rel_path = concept_index[c["name"]]["path"]
        full = vault_dir / rel_path
        if not full.exists():
            continue
        sources = _count_sources_in_frontmatter(full)
        if sources >= 2:
            contradictions.append({
                "concept": c["name"],
                "source_count": sources,
                "reason": "multiple sources may disagree — review needed",
            })

    # Step 5: detect gaps.
    gaps: list[str] = []
    if located["strategy"] == "none":
        gaps.append(f"no match in vault for topic: '{topic}'")
    elif not relevant_concepts and entry_concepts:
        gaps.append(
            f"topic matched vault entry but no connected concepts found: '{topic}'"
        )
    elif located["strategy"] == "moc_match" and not entry_concepts:
        # MOC matched but has no children
        gaps.append(
            f"matched MOC for '{topic}' has no child concepts yet"
        )

    # Step 6: entry questions for broad topics.
    entry_questions: list[str] = []
    if len(relevant_concepts) > BROAD_MATCH_THRESHOLD:
        entry_questions.append(
            f"This topic touches {len(relevant_concepts)} concepts — "
            "do you want to focus on any specific aspect first?"
        )
    if entry_concepts and located["strategy"] == "moc_match":
        entry_questions.append(
            "Are you looking for an overview of this area, "
            "or a specific concept within it?"
        )

    return {
        "topic": topic,
        "strategy": located["strategy"],
        "relevant_concepts": relevant_concepts,
        "clusters": clusters,
        "contradictions": contradictions,
        "gaps": gaps,
        "entry_questions": entry_questions,
    }


def _count_sources_in_frontmatter(md_path: Path) -> int:
    """Count `sources:` entries in a concept .md frontmatter (stdlib only)."""
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return 0
    end = text.find("\n---", 4)
    if end == -1:
        return 0
    fm = text[4:end]

    in_sources = False
    count = 0
    for line in fm.splitlines():
        stripped = line.rstrip()
        if stripped == "sources:":
            in_sources = True
            continue
        if in_sources:
            if line.startswith("  - file:"):
                count += 1
            elif stripped and not line.startswith(" "):
                break
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brainstorm scaffold for a topic.")
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args(argv)

    result = brainstorm(
        topic=args.topic,
        index_dir=args.index_dir,
        vault_dir=args.vault,
        memory_dir=args.memory_dir,
    )
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
