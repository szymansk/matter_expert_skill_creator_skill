"""Emit phase — generates the installable expert-skill plugin."""
from builder.emit.plugin_metadata import (
    PluginMetadata,
    write_marketplace_json,
    write_plugin_json,
)
from builder.emit.index_builder import build_indexes
from builder.emit.runtime_bundler import bundle_runtime
from builder.emit.memory_initializer import (
    DEFAULT_USER_PREFERENCES, initialize_memory,
)
from builder.emit.skill_md import SkillMdMeta, generate_skill_md
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.orchestrator import EmitConfig, EmitOrchestrator

__all__ = [
    "PluginMetadata", "write_plugin_json", "write_marketplace_json",
    "build_indexes",
    "bundle_runtime",
    "DEFAULT_USER_PREFERENCES", "initialize_memory",
    "SkillMdMeta", "generate_skill_md",
    "ReadmeMeta", "generate_readme",
    "EmitConfig", "EmitOrchestrator",
]
