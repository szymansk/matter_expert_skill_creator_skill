"""Parsing and normalization of [[wikilink]] references."""
import re

WIKILINK_PATTERN = re.compile(r"\[\[([^\[\]\|]+?)(?:\|[^\[\]]+)?\]\]")
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)


def extract_wikilinks(text: str) -> list[str]:
    """Return wikilink targets from text, ignoring code blocks and inline code.

    Order matches order of appearance. Duplicates are kept as-is — callers
    may dedupe if they need uniqueness.
    """
    cleaned = CODE_BLOCK_PATTERN.sub("", text)
    cleaned = INLINE_CODE_PATTERN.sub("", cleaned)
    return [m.group(1).strip() for m in WIKILINK_PATTERN.finditer(cleaned)]


def normalize_wikilink(raw: str) -> str:
    """Strip whitespace, `[[` `]]` brackets, and `|alias` suffix from a wikilink target."""
    s = raw.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2].strip()
    if "|" in s:
        s = s.split("|", 1)[0].strip()
    return s
