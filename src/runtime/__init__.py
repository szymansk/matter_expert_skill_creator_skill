"""Runtime engine for the generated expert skill — stdlib only.

This package is bundled into the generated expert-skill plugin.
It must never import third-party libraries (only Python stdlib + ripgrep).
"""

__version__ = "0.0.1"

from runtime.index import (
    IndexPaths,
    load_alias_map,
    load_concept_index,
    load_link_graph,
    load_moc_map,
)
from runtime.memory import (
    MemoryPaths,
    DEFAULT_USER_PREFERENCES,
    load_query_cache,
    save_query_cache,
    load_path_frequency,
    save_path_frequency,
    load_user_preferences,
    save_user_preferences,
    load_learned_aliases,
    save_learned_aliases,
    load_session_log,
    save_session_log,
)
from runtime.vault_cite import get_citation
from runtime.vault_search import search_vault
from runtime.vault_locate import locate_entry_points
from runtime.vault_traverse import traverse
from runtime.memory_update import update_memory, QUERY_CACHE_MAX_ENTRIES
from runtime.memory_inspect import inspect_memory
from runtime.vault_brainstorm import brainstorm

__all__ = [
    "IndexPaths",
    "load_alias_map", "load_concept_index", "load_link_graph", "load_moc_map",
    "MemoryPaths", "DEFAULT_USER_PREFERENCES",
    "load_query_cache", "save_query_cache",
    "load_path_frequency", "save_path_frequency",
    "load_user_preferences", "save_user_preferences",
    "load_learned_aliases", "save_learned_aliases",
    "load_session_log", "save_session_log",
    "get_citation",
    "search_vault",
    "locate_entry_points",
    "traverse",
    "update_memory", "QUERY_CACHE_MAX_ENTRIES",
    "inspect_memory",
    "brainstorm",
]
