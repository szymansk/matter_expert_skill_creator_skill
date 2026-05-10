"""Prompts for the 4 LLM-based QA validators."""
from __future__ import annotations


TRANSLATION_SYSTEM = (
    "You judge whether a translated concept page reads naturally in English "
    "and preserves the technical content of its source. Return JSON: "
    "{\"verdict\": \"pass\" | \"fail\", \"reasons\": [string, ...]}."
)


def translation_prompt(concept_title: str, body: str, source_excerpt: str) -> str:
    return (
        f"Concept: {concept_title}\n\n"
        f"Translation:\n---\n{body}\n---\n\n"
        f"Source excerpt:\n---\n{source_excerpt}\n---\n\n"
        f"Return JSON verdict."
    )


COVERAGE_SYSTEM = (
    "Given a source document outline and the list of concepts extracted "
    "from it, return JSON {\"missed_topics\": [...]} naming any outline "
    "topics not represented by an extracted concept."
)


def coverage_prompt(outline: list[str], concept_titles: list[str]) -> str:
    return (
        "Source outline:\n" + "\n".join(f"- {h}" for h in outline)
        + "\n\nExtracted concepts:\n"
        + "\n".join(f"- {t}" for t in concept_titles)
        + "\n\nReturn JSON only."
    )


CITATION_SYSTEM = (
    "You verify that the source citations on a concept page actually back "
    "the claims in the page body. Return JSON: {\"verdict\": \"pass\" | "
    "\"fail\", \"unsupported_claims\": [string, ...]}."
)


def citation_prompt(concept_title: str, body: str,
                    cited_sources: list[str], source_excerpts: dict[str, str]) -> str:
    sources_block = "\n\n".join(
        f"=== {f} ===\n{source_excerpts.get(f, '(no excerpt)')}"
        for f in cited_sources
    )
    return (
        f"Concept: {concept_title}\n\nBody:\n---\n{body}\n---\n\n"
        f"Cited sources:\n{sources_block}\n\nReturn JSON verdict."
    )


COHERENCE_SYSTEM = (
    "You judge whether a concept page makes sense as a standalone unit — "
    "no unexplained references ('as mentioned above'), unresolved acronyms, "
    "or missing context. Return JSON: {\"verdict\": \"pass\" | \"fail\", "
    "\"issues\": [string, ...]}."
)


def coherence_prompt(concept_title: str, body: str) -> str:
    return (
        f"Concept: {concept_title}\n\nBody (read in isolation):\n"
        f"---\n{body}\n---\n\nReturn JSON verdict."
    )
