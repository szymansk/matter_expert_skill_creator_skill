def test_emit_public_api():
    from builder.emit import (
        PluginMetadata, write_plugin_json,
        build_indexes,
        bundle_runtime,
        DEFAULT_USER_PREFERENCES, initialize_memory,
        SkillMdMeta, generate_skill_md,
        ReadmeMeta, generate_readme,
        EmitConfig, EmitOrchestrator,
    )
    assert callable(generate_skill_md)
    assert callable(generate_readme)
