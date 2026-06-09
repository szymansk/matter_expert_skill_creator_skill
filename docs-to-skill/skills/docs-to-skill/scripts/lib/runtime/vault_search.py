"""Layer 2 retrieval: ranked BM25F search over a precomputed index.

Loads ``_index/bm25_index.json`` (built by the Emit phase or rebuilt with
``runtime/bm25_build.py``) and returns concept names ranked by relevance.
An optional tag filter narrows results to concepts whose frontmatter tags
match. Pure Python — no system binaries required at query time.

If the index is missing it is built once automatically. If the vault has been
modified more recently than the index a staleness warning is printed to stderr.
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

from runtime.bm25 import (
    BM25Index,
    assemble_docs,
    build_bm25_index,
    strip_frontmatter,  # re-exported for backward compatibility
)
from runtime.index import load_concept_index

# Backward-compatible alias: older callers/tests import this private name.
_strip_frontmatter = strip_frontmatter

DEFAULT_TOP_N = 10


def _vault_newer_than(vault_dir: Path, index_path: Path) -> bool:
    """True if any concept file is newer than the index file."""
    idx_mtime = index_path.stat().st_mtime
    for md_file in (vault_dir / "concepts").glob("*.md"):
        if md_file.stat().st_mtime > idx_mtime:
            return True
    return False


def _load_or_build_index(
    index_path: Path, vault_dir: Path, concept_index_path: Path
) -> BM25Index:
    if not index_path.exists():
        print("bm25: index missing — building it now.", file=sys.stderr)
        data = build_bm25_index(assemble_docs(vault_dir, concept_index_path))
        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(
                json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8"
            )
        except OSError as exc:
            print(
                f"bm25: could not persist index ({exc}); using in-memory index.",
                file=sys.stderr,
            )
        return BM25Index.from_dict(data)
    if _vault_newer_than(vault_dir, index_path):
        print(
            "bm25: index may be stale; run bm25_build.py to refresh.",
            file=sys.stderr,
        )
    try:
        return BM25Index.load(index_path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"bm25: corrupt index at {index_path}: {exc}") from exc


def _ranked_with_scores(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None,
    top_n: int | None,
    bm25_index_path: Path | None,
) -> list[tuple[str, float]]:
    if bm25_index_path is None:
        bm25_index_path = concept_index_path.parent / "bm25_index.json"
    index = _load_or_build_index(bm25_index_path, vault_dir, concept_index_path)
    ranked = index.score(query)  # full ranking; truncate after tag filter

    if tags:
        concept_index = load_concept_index(concept_index_path)
        wanted = set(tags)
        ranked = [
            (name, score)
            for name, score in ranked
            if name in concept_index
            and wanted.intersection(concept_index[name].get("tags", []))
        ]
    return ranked[:top_n] if top_n is not None else ranked


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
    top_n: int | None = DEFAULT_TOP_N,
    bm25_index_path: Path | None = None,
) -> list[str]:
    """Return concept names ranked by BM25F relevance (best first).

    Results are restricted to concepts carrying at least one of ``tags`` when
    given, and truncated to ``top_n`` (pass ``None`` for all hits).
    """
    ranked = _ranked_with_scores(
        query, vault_dir, concept_index_path, tags, top_n, bm25_index_path
    )
    return [name for name, _score in ranked]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ranked BM25F vault search.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="Maximum number of ranked results (0 = all)")
    parser.add_argument("--scores", action="store_true",
                        help="Output [{name, score}] instead of a name list")
    parser.add_argument("--index", type=Path, default=None,
                        help="Path to bm25_index.json (default: beside concept-index)")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    top_n = args.top_n if args.top_n > 0 else None

    ranked = _ranked_with_scores(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
        top_n=top_n,
        bm25_index_path=args.index,
    )

    if args.scores:
        payload = [{"name": name, "score": score} for name, score in ranked]
    else:
        payload = [name for name, _score in ranked]
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
