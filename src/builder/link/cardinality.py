"""Enforce per-link-type maximum cardinality (design spec §4.4)."""
from __future__ import annotations


MAX_RELATED = 8
MAX_PREREQUISITES = 5
MAX_EXAMPLES = 6
MAX_CONTRASTS = 4
MAX_REFINES = 3


_LIMITS = {
    "related": MAX_RELATED,
    "prerequisites": MAX_PREREQUISITES,
    "examples": MAX_EXAMPLES,
    "contrasts": MAX_CONTRASTS,
    "refines": MAX_REFINES,
}


def enforce_link_cardinality(links: dict[str, list[str]]) -> dict[str, list[str]]:
    """Trim each link list to its max-recommended count.

    Returns a new dict; the input is not mutated. Preserves order — the
    first N entries are kept (callers must order by importance).
    """
    return {
        key: list(values[:_LIMITS.get(key, len(values))])
        for key, values in links.items()
    }
