"""Prompt templates for the Transform agents.

These are exported as plain strings (or functions returning strings) so
tests can assert that the right prompt was used and the orchestrator can
inject parameters cleanly.
"""
from __future__ import annotations


ANALYZER_SYSTEM = (
    "You analyze a source document and identify the atomic concepts it "
    "covers. Output a JSON object with an 'entries' list. Each entry has: "
    "concept_name (kebab-case, used as filename), title (human display), "
    "source_sections (list of section IDs from the source, may be empty), "
    "estimated_tokens (int, 500-2000 ideal). Concepts should be coherent "
    "and self-contained — one concept per filename."
)


def analyzer_prompt(source_text: str, source_name: str) -> str:
    return (
        f"Source document: {source_name}\n\n"
        f"---\n{source_text}\n---\n\n"
        f"Identify the atomic concepts and return JSON only."
    )


EXTRACTOR_SYSTEM = (
    "You extract a single concept from a source document into a clean "
    "Markdown vault page. The output is the BODY of the concept page only "
    "(no YAML frontmatter — that is added separately). Translate any non-"
    "English content to English. Keep the body 500-2000 tokens. Preserve "
    "headings, lists, code blocks. Reference cross-cutting concepts as "
    "[[wikilinks]] using kebab-case names."
)


def extractor_prompt(
    source_text: str,
    source_name: str,
    concept_name: str,
    concept_title: str,
) -> str:
    return (
        f"Source: {source_name}\n"
        f"Target concept: {concept_name} ({concept_title})\n\n"
        f"---\n{source_text}\n---\n\n"
        f"Output the concept's markdown body only."
    )


COVERAGE_SYSTEM = (
    "You compare a source document's outline to the list of concepts "
    "extracted from it. Return JSON: {\"missed_topics\": [list of strings]} "
    "naming any topics from the source outline that are NOT represented by "
    "an extracted concept."
)


def coverage_prompt(
    source_outline: list[str],
    extracted_concept_titles: list[str],
) -> str:
    return (
        f"Source outline:\n" + "\n".join(f"- {h}" for h in source_outline)
        + "\n\nExtracted concepts:\n"
        + "\n".join(f"- {t}" for t in extracted_concept_titles)
        + "\n\nReturn JSON only."
    )
