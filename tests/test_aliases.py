from matter_expert.aliases import derive_aliases


def test_derives_title_slug_and_distinctive_words():
    aliases = derive_aliases(
        "c192-session-resume", "Session Resume", ["task", "resilience"]
    )
    assert "session resume" in aliases   # full title phrase
    assert "session" in aliases          # distinctive >=6-char word
    assert "resume" in aliases


def test_strips_cNNN_double_dash_prefix_for_slug_phrase():
    aliases = derive_aliases("c196--task-graph-lifecycle", "Task Graph Lifecycle", [])
    assert "task graph lifecycle" in aliases


def test_multi_word_tags_become_phrases():
    aliases = derive_aliases("c001-x", "X", ["change-impact", "single"])
    assert "change impact" in aliases
    assert "single" not in aliases       # single-word tag is not an alias


def test_drops_short_and_dedupes():
    aliases = derive_aliases("c002-ab", "Ab", ["xy"])  # all too short
    assert aliases == []
    assert len(set(aliases)) == len(aliases)
