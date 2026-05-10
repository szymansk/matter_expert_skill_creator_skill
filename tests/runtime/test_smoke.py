import importlib
import sys

import runtime


def test_runtime_package_importable():
    assert runtime.__version__ == "0.0.1"


def test_runtime_does_not_import_matter_expert():
    """The runtime package must remain stdlib-only.

    Force a fresh import of `runtime` (clearing any previously imported
    runtime modules) and verify that doing so did not transitively pull
    in `matter_expert` or `frontmatter`.
    """
    # Capture state before the fresh import.
    before = set(sys.modules)

    # Clear any runtime modules from sys.modules so the import below is fresh.
    for mod_name in list(sys.modules):
        if mod_name == "runtime" or mod_name.startswith("runtime."):
            del sys.modules[mod_name]

    importlib.import_module("runtime")

    # Anything newly added by the runtime import that belongs to a forbidden
    # package is a leak. (We use top-level package names so transitive
    # submodules also get caught.)
    forbidden = {"matter_expert", "frontmatter"}
    newly_loaded = set(sys.modules) - before
    leaked = {m for m in newly_loaded if m.split(".")[0] in forbidden}
    assert leaked == set(), f"runtime imported forbidden packages: {leaked}"
