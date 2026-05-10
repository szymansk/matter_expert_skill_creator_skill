def test_runtime_public_api_exports():
    """The runtime package exposes its core entry points."""
    from runtime import (
        IndexPaths,
        MemoryPaths,
        DEFAULT_USER_PREFERENCES,
        get_citation,
        search_vault,
        locate_entry_points,
        traverse,
        update_memory,
        inspect_memory,
        brainstorm,
    )

    assert callable(get_citation)
    assert callable(search_vault)
    assert callable(locate_entry_points)
    assert callable(traverse)
    assert callable(update_memory)
    assert callable(inspect_memory)
    assert callable(brainstorm)
    assert isinstance(DEFAULT_USER_PREFERENCES, dict)
