"""Deterministic CLI helpers for subscription-native orchestration.

These subcommands do NOT call any LLM. They are designed to be invoked by
the docs-to-skill SKILL.md between subagent dispatches; the subagents
produce LLM output (concept bodies, links JSON, etc.) which the helpers
then write into the vault.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from builder.emit.index_builder import build_indexes as _build_indexes_fn
from builder.emit.memory_initializer import initialize_memory
from builder.emit.plugin_metadata import (
    PluginMetadata,
    write_marketplace_json,
    write_plugin_json,
)
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.runtime_bundler import bundle_runtime
from builder.ingest.pandoc_converter import PandocConverter
from builder.ingest.passthrough import PassthroughConverter
from builder.ingest.pdf_text import PDFTextExtractor, is_text_extraction_plausible
from matter_expert import (
    ConceptFrontmatter, ConceptPage, MOCFrontmatter, MOCPage,
    Source, SourceFrontmatter, SourcePage, VaultPaths,
)


PANDOC_EXT = {".txt", ".html", ".htm", ".docx", ".rtf", ".odt", ".epub"}
MD_EXT = {".md", ".markdown"}


def _cmd_ingest_deterministic(args) -> int:
    input_dir: Path = args.input
    out_dir: Path = args.output
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    passthrough = PassthroughConverter()
    pandoc = PandocConverter()
    pdf_text = PDFTextExtractor()

    results: dict[str, dict] = {}
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        item: dict = {"source_path": str(path), "needs_vision": False}
        try:
            if ext in MD_EXT:
                result = passthrough.convert(path)
            elif ext in PANDOC_EXT:
                result = pandoc.convert(path)
            elif ext == ".pdf":
                text_result = pdf_text.extract(path)
                if is_text_extraction_plausible(
                    text_result.text, text_result.page_count,
                ):
                    result = pdf_text.convert(path)
                else:
                    # Vision needed — write nothing, mark for subagent
                    item["needs_vision"] = True
                    item["page_count"] = text_result.page_count
                    results[path.name] = item
                    continue
            else:
                item["error"] = f"unsupported extension: {ext}"
                results[path.name] = item
                continue
        except Exception as e:
            item["error"] = str(e)
            results[path.name] = item
            continue

        body_path = raw_dir / f"{path.stem}.md"
        body_path.write_text(result.content, encoding="utf-8")
        (raw_dir / f"{path.stem}.meta.json").write_text(
            json.dumps(result.meta.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        item.update({
            "body_path": str(body_path),
            "extraction_method": result.meta.extraction_method.value
            if hasattr(result.meta.extraction_method, "value")
            else result.meta.extraction_method,
            "extracted_chars": result.meta.extracted_chars,
            "outline": list(result.meta.outline),
            "page_count": result.meta.page_count,
        })
        results[path.name] = item

    json.dump({"results": results}, sys.stdout, indent=2,
              default=str, ensure_ascii=False)
    print()
    return 0


def _today():
    return datetime.now(timezone.utc).date()


def _cmd_write_concept(args) -> int:
    paths = VaultPaths(root=args.vault)
    sections = [s for s in args.source_sections.split(",") if s.strip()]
    body = args.body_file.read_text(encoding="utf-8")
    fm = ConceptFrontmatter(
        title=args.title,
        sources=[Source(file=args.source_file, sections=sections)],
        tags=[t for t in (args.tags or "").split(",") if t.strip()],
        created=_today(),
    )
    page = ConceptPage(frontmatter=fm, body=body,
                       path=paths.concept_for(args.name))
    page.write()
    return 0


def _cmd_write_source(args) -> int:
    paths = VaultPaths(root=args.vault)
    body = args.body_file.read_text(encoding="utf-8")
    fm = SourceFrontmatter(
        title=args.name,
        original_file=args.original_file,
        original_format=args.original_format,
        page_count=args.page_count,
        extraction_method=args.extraction_method,
        language_detected=args.language_detected,
        ingested=_today(),
    )
    page = SourcePage(frontmatter=fm, body=body,
                      path=paths.source_for(args.name))
    page.write()
    return 0


def _cmd_write_moc(args) -> int:
    paths = VaultPaths(root=args.vault)
    children = [c for c in args.children.split(",") if c.strip()]
    fm = MOCFrontmatter(
        title=args.title, children=children,
        parents=[p for p in (args.parents or "").split(",") if p.strip()],
        related_mocs=[r for r in (args.related_mocs or "").split(",") if r.strip()],
        created=_today(),
    )
    body = (
        f"# {args.title} MOC\n\n## Concepts\n\n"
        + "\n".join(f"- [[{c}]]" for c in children) + "\n"
    )
    page = MOCPage(frontmatter=fm, body=body,
                   path=paths.mocs / f"{args.name}.md")
    page.write()
    return 0


def _cmd_apply_links(args) -> int:
    paths = VaultPaths(root=args.vault)
    links = json.loads(args.links_json.read_text(encoding="utf-8"))
    page = ConceptPage.read(paths.concept_for(args.concept))
    page.frontmatter.related = list(links.get("related", []))
    page.frontmatter.prerequisites = list(links.get("prerequisites", []))
    page.frontmatter.examples = list(links.get("examples", []))
    page.frontmatter.contrasts = list(links.get("contrasts", []))
    page.frontmatter.refines = list(links.get("refines", []))
    page.write()
    return 0


def _cmd_apply_merge(args) -> int:
    paths = VaultPaths(root=args.vault)
    members = [m.strip() for m in args.members.split(",") if m.strip()]
    if len(members) < 2:
        print("error: --members must list 2+ concept names", file=sys.stderr)
        return 1

    member_pages = []
    for name in members:
        path = paths.concept_for(name)
        if path.exists():
            member_pages.append(ConceptPage.read(path))
    if len(member_pages) < 2:
        print("error: fewer than 2 member pages exist on disk", file=sys.stderr)
        return 1

    body = args.merged_body_file.read_text(encoding="utf-8")
    # Aggregate sources from all members.
    seen: set[str] = set()
    sources: list[Source] = []
    for p in member_pages:
        for s in p.frontmatter.sources:
            if s.file not in seen:
                seen.add(s.file)
                sources.append(s)

    survivor = member_pages[0]
    survivor.frontmatter.sources = sources
    survivor.frontmatter.merged_from = list(members)
    survivor.body = body
    survivor.write()
    for p in member_pages[1:]:
        p.path.unlink()
    return 0


def _cmd_build_indexes(args) -> int:
    paths = VaultPaths(root=args.vault)
    _build_indexes_fn(vault=paths, index_dir=args.index_dir)
    return 0


def _cmd_emit_finalize(args) -> int:
    # Copy the prepared vault into the plugin.
    plugin_root: Path = args.plugin_root
    skill_dir = plugin_root / "skills" / args.plugin_name
    bundled_vault = skill_dir / "vault"
    bundled_vault.mkdir(parents=True, exist_ok=True)
    src_vault: Path = args.vault
    for subdir in ("concepts", "MOCs", "sources"):
        src = src_vault / subdir
        if src.exists():
            shutil.copytree(src, bundled_vault / subdir, dirs_exist_ok=True)

    # Copy the prepared _index/ into the plugin.
    bundled_index = skill_dir / "_index"
    if args.index_dir.exists():
        shutil.copytree(args.index_dir, bundled_index, dirs_exist_ok=True)

    # Bundle runtime.
    bundle_runtime(plugin_skill_dir=skill_dir)

    # Write SKILL.md (uses the pre-generated description text).
    from builder.emit.skill_md import SKILL_MD_TEMPLATE
    skill_md = SKILL_MD_TEMPLATE.format(
        name=args.plugin_name,
        description=args.skill_description.replace("\n", " ").strip(),
        title=args.plugin_name.replace("-", " ").title(),
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # Initialize memory.
    memory_dir = skill_dir / "memory"
    link_graph_path = bundled_index / "link_graph.json"
    link_graph = json.loads(link_graph_path.read_text(encoding="utf-8")) \
        if link_graph_path.exists() else {}
    initialize_memory(memory_dir=memory_dir, link_graph=link_graph)

    # Plugin metadata + marketplace.json (GitHub-installable) + README.
    meta = PluginMetadata(
        name=args.plugin_name, version=args.version,
        description=args.description, author=args.author,
    )
    write_plugin_json(meta, plugin_root=plugin_root)
    write_marketplace_json(meta, plugin_root=plugin_root)
    concept_count = len(list((bundled_vault / "concepts").glob("*.md"))) \
        if (bundled_vault / "concepts").exists() else 0
    moc_count = len(list((bundled_vault / "MOCs").glob("*.md"))) \
        if (bundled_vault / "MOCs").exists() else 0
    generate_readme(
        plugin_root=plugin_root,
        meta=ReadmeMeta(
            plugin_name=args.plugin_name, version=args.version,
            description=args.description,
            concept_count=concept_count, moc_count=moc_count,
        ),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs-to-skill-helpers",
        description="Deterministic helpers for the subscription-native orchestrator.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest-deterministic")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(fn=_cmd_ingest_deterministic)

    p = sub.add_parser("write-concept")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--source-file", required=True)
    p.add_argument("--source-sections", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_write_concept)

    p = sub.add_parser("write-source")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--original-file", required=True)
    p.add_argument("--original-format", default="pdf")
    p.add_argument("--page-count", type=int, required=True)
    p.add_argument("--extraction-method", default="text",
                   choices=["text", "vision_fallback", "hybrid"])
    p.add_argument("--language-detected", default="en")
    p.add_argument("--body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_write_source)

    p = sub.add_parser("write-moc")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--children", required=True)
    p.add_argument("--parents", default="")
    p.add_argument("--related-mocs", default="")
    p.set_defaults(fn=_cmd_write_moc)

    p = sub.add_parser("apply-links")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--concept", required=True)
    p.add_argument("--links-json", type=Path, required=True)
    p.set_defaults(fn=_cmd_apply_links)

    p = sub.add_parser("apply-merge")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--members", required=True)
    p.add_argument("--merged-body-file", type=Path, required=True)
    p.set_defaults(fn=_cmd_apply_merge)

    p = sub.add_parser("build-indexes")
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--index-dir", type=Path, required=True)
    p.set_defaults(fn=_cmd_build_indexes)

    p = sub.add_parser("emit-finalize")
    p.add_argument("--plugin-root", type=Path, required=True)
    p.add_argument("--plugin-name", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--author", required=True)
    p.add_argument("--vault", type=Path, required=True)
    p.add_argument("--index-dir", type=Path, required=True)
    p.add_argument("--skill-description", required=True,
                   help="The pushy trigger description from the trigger-desc-agent.")
    p.set_defaults(fn=_cmd_emit_finalize)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
