"""Citation lookup: given a concept name, return its source attribution.

Read by the runtime when it needs to format citations into an answer.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# When this script is executed directly from a bundled plugin the runtime/
# directory sits inside scripts/.  Add scripts/ to sys.path so that
# `from runtime.xxx import` resolves regardless of the working directory.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.index import load_concept_index


def get_citation(
    concept_name: str,
    concept_index_path: Path,
) -> dict[str, Any]:
    """Look up a concept and return citation-ready fields.

    Raises:
        KeyError: if the concept is not found in the index.
    """
    index = load_concept_index(concept_index_path)
    if concept_name not in index:
        raise KeyError(f"concept '{concept_name}' not in index")

    entry = index[concept_name]
    return {
        "concept": concept_name,
        "title": entry["title"],
        "path": entry["path"],
        "summary": entry.get("summary", ""),
        "tags": list(entry.get("tags", [])),
        "moc": list(entry.get("moc", [])),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up citation info for a concept.")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("concept", help="Concept name (filename stem)")
    args = parser.parse_args(argv)

    try:
        result = get_citation(args.concept, args.concept_index)
    except KeyError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
