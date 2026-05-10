"""Prompt templates for the Link phase agents."""
from __future__ import annotations


CLUSTER_SYSTEM = (
    "You analyze a flat list of concept inventories and identify CLUSTERS of "
    "concepts that describe the same thing (different names, identical "
    "underlying concept). Return JSON: {\"clusters\": [{\"members\": "
    "[concept_name, concept_name, ...]}]}. Singleton concepts (no duplicates) "
    "must NOT be included. Be conservative — only group concepts whose summaries "
    "describe the same thing."
)


def cluster_prompt(inventory_json: str) -> str:
    return f"Inventory (JSON):\n\n{inventory_json}\n\nReturn JSON only."


MERGE_SYSTEM = (
    "You are given several concept pages that describe the same underlying "
    "concept and must produce ONE merged page. The merged body should keep "
    "the most complete and accurate content from each source, NOT just "
    "concatenate them. When sources disagree, mark the disagreement explicitly "
    "with a > Note: blockquote pointing at the conflicting source."
)


def merge_prompt(concepts: list[dict]) -> str:
    """concepts is a list of {name, title, body, sources}."""
    parts = []
    for c in concepts:
        parts.append(f"=== {c['name']} (title: {c['title']}) ===\n{c['body']}")
    body = "\n\n".join(parts)
    return (
        "Merge the following concept pages into one. Return the merged "
        f"markdown body only.\n\n{body}"
    )


LINK_SYSTEM = (
    "You assign typed links between concepts. Given a target concept and the "
    "full inventory of other concepts, decide which other concepts belong in "
    "each of 5 lists: related, prerequisites, examples, contrasts, refines. "
    "Return JSON: {\"related\": [...], \"prerequisites\": [...], ...}. "
    "Use the concept_name (kebab-case), NEVER the title. "
    "Be selective — fewer high-quality links is better."
)


def link_prompt(target_summary: dict, inventory_json: str) -> str:
    return (
        f"Target concept:\n{target_summary['name']} — {target_summary['title']}\n"
        f"Summary: {target_summary['summary']}\n\n"
        f"Full inventory (JSON):\n{inventory_json}\n\n"
        f"Return typed-link JSON only."
    )
