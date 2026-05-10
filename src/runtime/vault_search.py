"""Layer 2 retrieval: ripgrep + frontmatter-tag filtering.

Body-content search across the vault's concept Markdown files using the
ripgrep system binary. Optional tag filter narrows results to concepts
whose frontmatter tags match the requested set.

Frontmatter (YAML between the leading ``---`` delimiters) is excluded from
the search so that structural keys like ``merged_from`` do not produce false
positive matches.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime.index import load_concept_index


def _strip_frontmatter(text: str) -> str:
    """Return only the body of a Markdown file (content after frontmatter).

    If the file starts with ``---``, the frontmatter block extends up to the
    next ``---`` line. Everything after that closing delimiter is returned.
    If no frontmatter is present the full text is returned unchanged.
    """
    if not text.startswith("---"):
        return text
    # Find the closing delimiter — must be on its own line after the opening.
    rest = text[3:]  # skip opening "---"
    close = rest.find("\n---")
    if close == -1:
        return text  # malformed — treat whole file as body
    # Return everything after the closing "---\n", stripping any leading newline.
    return rest[close + 4:].lstrip("\n")


def search_vault(
    query: str,
    vault_dir: Path,
    concept_index_path: Path,
    tags: list[str] | None = None,
) -> list[str]:
    """Return concept names whose body matches `query` (and `tags`, if given).

    Raises:
        RuntimeError: if `rg` is not on PATH.
    """
    if shutil.which("rg") is None:
        raise RuntimeError("ripgrep ('rg') is required but not on PATH")

    concepts_dir = vault_dir / "concepts"

    # Write frontmatter-stripped bodies to a temp directory so ripgrep only
    # searches body content (preventing false positives on frontmatter keys).
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for md_file in concepts_dir.glob("*.md"):
            body = _strip_frontmatter(md_file.read_text(encoding="utf-8"))
            (tmp_path / md_file.name).write_text(body, encoding="utf-8")

        proc = subprocess.run(
            ["rg", "-l", "-i", "--no-messages", query, str(tmp_path)],
            capture_output=True,
            text=True,
        )

    if proc.returncode == 1:  # ripgrep returncode 1 = no matches (not an error)
        return []
    if proc.returncode != 0:
        raise RuntimeError(f"ripgrep failed: {proc.stderr.strip()}")

    matched_files = [Path(line).stem for line in proc.stdout.splitlines() if line.strip()]
    matched_set = set(matched_files)

    # Apply tag filter if given.
    if tags:
        index = load_concept_index(concept_index_path)
        wanted_tags = set(tags)
        matched_set = {
            name for name in matched_set
            if name in index and wanted_tags.intersection(index[name].get("tags", []))
        }

    return sorted(matched_set)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the vault body content.")
    parser.add_argument("--vault", type=Path, required=True, help="Vault root directory")
    parser.add_argument("--concept-index", type=Path, required=True,
                        help="Path to concept_index.json")
    parser.add_argument("--query", required=True, help="Keyword to search for")
    parser.add_argument("--tags", default="",
                        help="Comma-separated list of tags to filter by")
    args = parser.parse_args(argv)

    tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    matches = search_vault(
        query=args.query,
        vault_dir=args.vault,
        concept_index_path=args.concept_index,
        tags=tag_list or None,
    )
    json.dump(matches, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
