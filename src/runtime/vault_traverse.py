"""Layer 3 graph expansion via the link graph.

BFS from one or more start concepts following typed link relations.
Depth-limited; configurable set of link types to follow.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from runtime.index import load_link_graph

ALL_LINK_TYPES = (
    "related",
    "prerequisites",
    "examples",
    "contrasts",
    "refines",
    "leads_to",     # inverse of prerequisites
    "instances",    # inverse of examples
    "refined_by",   # inverse of refines
)


def traverse(
    starts: list[str],
    link_graph_path: Path,
    depth: int,
    include_types: list[str] | None = None,
) -> list[str]:
    """BFS from `starts` through the link graph up to `depth` hops."""
    graph = load_link_graph(link_graph_path)
    types = list(include_types) if include_types else list(ALL_LINK_TYPES)

    visited: set[str] = {s for s in starts if s in graph}
    frontier = deque((s, 0) for s in visited)

    while frontier:
        node, dist = frontier.popleft()
        if dist >= depth:
            continue

        entry = graph.get(node, {})
        for link_type in types:
            for neighbor in entry.get(link_type, []):
                if neighbor not in visited and neighbor in graph:
                    visited.add(neighbor)
                    frontier.append((neighbor, dist + 1))

    return sorted(visited)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expand from concepts via the link graph.")
    parser.add_argument("--link-graph", type=Path, required=True,
                        help="Path to link_graph.json")
    parser.add_argument("--depth", type=int, required=True, help="BFS depth limit")
    parser.add_argument("--from", dest="starts", action="append", required=True,
                        help="Starting concept (repeat for multiple)")
    parser.add_argument("--include-types", default="",
                        help=("Comma-separated link types to follow. "
                              f"Available: {','.join(ALL_LINK_TYPES)}. "
                              "Default: all."))
    args = parser.parse_args(argv)

    types = [t.strip() for t in args.include_types.split(",") if t.strip()] or None
    result = traverse(
        starts=args.starts,
        link_graph_path=args.link_graph,
        depth=args.depth,
        include_types=types,
    )
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
