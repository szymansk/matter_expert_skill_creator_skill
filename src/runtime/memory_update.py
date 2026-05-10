"""Update mutable memory after a query.

Updates query_cache (LRU eviction at max size), path_frequency
(co-access counters), and optionally user_preferences (when language
or other prefs are detected).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.memory import (
    MemoryPaths,
    load_path_frequency,
    load_query_cache,
    load_user_preferences,
    save_path_frequency,
    save_query_cache,
    save_user_preferences,
)

QUERY_CACHE_MAX_ENTRIES = 100
QUERY_CACHE_TTL_DAYS = 30


def _evict_expired(cache: dict, now: datetime, ttl_days: int) -> dict:
    """Drop cache entries whose last_used is older than ttl_days from now.

    Entries with malformed/missing last_used are kept (defensive — don't
    drop entries we can't reason about).
    """
    cutoff = now - timedelta(days=ttl_days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh: dict = {}
    for key, info in cache.items():
        last_used = info.get("last_used", "")
        if last_used and last_used < cutoff_iso:
            continue  # expired, drop
        fresh[key] = info
    return fresh


def update_memory(
    memory_dir: Path,
    query: str,
    used_concepts: list[str],
    user_language: str | None = None,
) -> None:
    """Apply a query's results to mutable memory."""
    paths = MemoryPaths(memory_dir=memory_dir)
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Update query_cache (with TTL and LRU eviction).
    cache = load_query_cache(paths.query_cache)

    # Evict TTL-expired entries first.
    cache = _evict_expired(cache, now, QUERY_CACHE_TTL_DAYS)
    if query in cache:
        cache[query]["use_count"] = cache[query].get("use_count", 0) + 1
        cache[query]["last_used"] = now_iso
        cache[query]["matched_concepts"] = list(used_concepts)
    else:
        cache[query] = {
            "matched_concepts": list(used_concepts),
            "last_used": now_iso,
            "use_count": 1,
            "user_satisfied": True,
        }

    if len(cache) > QUERY_CACHE_MAX_ENTRIES:
        oldest_key = min(cache.keys(), key=lambda k: cache[k].get("last_used", ""))
        del cache[oldest_key]

    save_query_cache(paths.query_cache, cache)

    # 2. Update path_frequency (co-access counters).
    freq = load_path_frequency(paths.path_frequency)
    for c in used_concepts:
        if c not in freq:
            freq[c] = {"co_accessed": {}, "total_accesses": 0}
        freq[c]["total_accesses"] = freq[c].get("total_accesses", 0) + 1
        for other in used_concepts:
            if other == c:
                continue
            co = freq[c]["co_accessed"]
            co[other] = co.get(other, 0) + 1
    save_path_frequency(paths.path_frequency, freq)

    # 3. Update user_preferences if language was detected.
    if user_language:
        prefs = load_user_preferences(paths.user_preferences)
        prefs["response_language"] = user_language
        save_user_preferences(paths.user_preferences, prefs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update memory after a query.")
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--used-concepts", required=True,
                        help="Comma-separated concept names")
    parser.add_argument("--user-language", default="",
                        help="Detected user language (optional)")
    args = parser.parse_args(argv)

    used = [c.strip() for c in args.used_concepts.split(",") if c.strip()]
    update_memory(
        memory_dir=args.memory_dir,
        query=args.query,
        used_concepts=used,
        user_language=args.user_language or None,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
