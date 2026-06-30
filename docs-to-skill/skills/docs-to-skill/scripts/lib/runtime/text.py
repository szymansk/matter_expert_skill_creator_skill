"""Stdlib-only text helpers for the Layer-2 search engine.

Tokenization, light stemming, and synonym expansion. No file I/O beyond
reading the optional synonyms JSON. Bundled into every produced skill via the
runtime copytree, so this module must remain standard-library only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_STOPWORDS = {
    # English
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "is", "it", "of", "on", "or", "the", "to", "was", "what", "when",
    "which", "who", "why", "with", "do", "does", "can", "could", "should",
    "would", "i", "you", "we", "they", "this", "that", "these", "those",
    # German
    "der", "die", "das", "und", "oder", "ein", "eine", "einen", "einem",
    "einer", "ist", "sind", "war", "waren", "wie", "wer", "wo", "im",
    "mit", "ohne", "für", "auf", "an", "zu", "den", "dem", "des",
    "nicht", "auch", "noch", "schon", "man", "es", "sich",
}

_TOKEN_RE = re.compile(r"[a-z0-9äöüß]+")

# Longest-first so the most specific suffix is stripped.
_EN_SUFFIXES = ("ization", "isation", "ableness", "ingly", "able", "ible",
                "ment", "ness", "ing", "ies", "ied", "ions", "ion", "ers",
                "er", "ed", "es", "s")
# Conservative DE list. The short "en"/"em" (and bare "e"/"n", "er"/"es") endings
# are intentionally excluded: they over-stem common English words
# ("token"->"tok", "system"->"syst", "broken"->"brok"). Substring matching and
# the longer, distinctive German suffixes below bridge the rest.
_DE_SUFFIXES = ("ungen", "ung", "lich", "isch", "keit", "heit")


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumeric, drop stopwords and <2-char tokens.

    Returns tokens in first-seen order, de-duplicated.
    """
    seen_set: set[str] = set()
    seen: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        if len(raw) < 2 or raw in _STOPWORDS:
            continue
        if raw not in seen_set:
            seen.append(raw)
            seen_set.add(raw)
    return seen


def stem(token: str) -> str:
    """Strip at most one EN/DE suffix, never stripping below 3 chars.

    Inputs already shorter than 3 chars are returned unchanged (cannot be
    lengthened).
    """
    for suffix in (*_EN_SUFFIXES, *_DE_SUFFIXES):
        if len(token) - len(suffix) >= 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def load_synonym_groups(path: Path | None) -> list[list[str]]:
    """Load equivalence groups from ``{"groups": [[...], ...]}``.

    Missing, unreadable, or malformed files yield no groups so search still
    works (just without synonym expansion).
    """
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw_groups = data.get("groups", []) if isinstance(data, dict) else []
    return [
        [str(term).lower() for term in group]
        for group in raw_groups
        if isinstance(group, list)
    ]


def build_synonym_index(groups: list[list[str]]) -> dict[str, set[str]]:
    """Map each term — and its stem — to the union of every group it appears in.

    Indexing the stem as well lets an inflected query token (``bugfixes``,
    ``reruns``) resolve to its group once it is stemmed, so synonym expansion
    and stemming compose instead of requiring an exact surface-form match.
    """
    index: dict[str, set[str]] = {}
    for group in groups:
        members = set(group)
        for term in group:
            index.setdefault(term, set()).update(members)
            stemmed = stem(term)
            if stemmed != term:
                index.setdefault(stemmed, set()).update(members)
    return index


def expand_token(token: str, syn_index: dict[str, set[str]]) -> set[str]:
    """Return match variants: the token, its stem, synonyms, and their stems.

    Synonyms are looked up by both the raw token and its stem, so an inflected
    query form still reaches its group (the index is keyed by both).
    """
    variants = {token, stem(token)}
    for key in (token, stem(token)):
        for synonym in syn_index.get(key, ()):
            variants.add(synonym)
            variants.add(stem(synonym))
    return variants
