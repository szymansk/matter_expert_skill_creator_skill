"""Deterministic, high-precision alias derivation for concept pages.

Run at index-build time (Emit). Produces only meaning-bearing phrases so that
Layer-1 lookup stays precise — no short generic fragments that would over-match.
"""
from __future__ import annotations

import re

_PREFIX_RE = re.compile(r"^c\d+-{1,2}")  # strip cNNN- / cNNN-- slug prefixes
_MIN_LEN = 4                              # drop anything shorter than this
_MIN_SINGLE_WORD_LEN = 6                  # single words must be distinctive
_GENERIC = {"loop", "task", "node", "step", "item", "data", "code", "page"}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def derive_aliases(name: str, title: str, tags: list[str]) -> list[str]:
    aliases: list[str] = []

    def add(candidate: str) -> None:
        candidate = _norm(candidate)
        if len(candidate) < _MIN_LEN or candidate in _GENERIC:
            return
        if candidate not in aliases:
            aliases.append(candidate)

    if title:
        add(title)

    slug = _PREFIX_RE.sub("", name)
    slug_words = [w for w in slug.split("-") if w]
    if len(slug_words) >= 2:
        add(" ".join(slug_words))

    for tag in tags:
        if " " in tag or "-" in tag:
            add(tag.replace("-", " "))

    for word in _norm(title).split():
        if len(word) >= _MIN_SINGLE_WORD_LEN:
            add(word)

    return aliases
