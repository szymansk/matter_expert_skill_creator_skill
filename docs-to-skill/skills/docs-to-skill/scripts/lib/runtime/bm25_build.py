"""Rebuild ``bm25_index.json`` for a vault.

Run this after adding or editing concept pages so Layer-2 search reflects the
new content. Pure Python — no system binaries required.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# When executed directly from a bundled plugin, runtime/ sits inside scripts/.
_HERE = Path(__file__).resolve().parent
if _HERE.name == "runtime":
    _scripts = _HERE.parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))

from runtime.bm25 import assemble_docs, build_bm25_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the BM25 vault index.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output path (default: bm25_index.json beside concept-index)")
    args = parser.parse_args(argv)

    out = args.out or args.concept_index.parent / "bm25_index.json"
    data = build_bm25_index(assemble_docs(args.vault, args.concept_index))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {out} ({data['N']} concepts, {len(data['postings'])} terms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
