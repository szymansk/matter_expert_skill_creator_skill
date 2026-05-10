import importlib
import sys

import runtime


FORBIDDEN_PACKAGES = {"matter_expert", "frontmatter"}


def test_runtime_package_importable():
    assert runtime.__version__ == "0.0.1"


def test_runtime_does_not_import_matter_expert():
    """The runtime package must remain stdlib-only.

    Approach: clear `runtime`, `matter_expert`, and `frontmatter` from
    `sys.modules`, then re-import `runtime` and check whether any
    forbidden package re-appeared as a side effect.
    """
    for mod_name in list(sys.modules):
        top = mod_name.split(".")[0]
        if top == "runtime" or top in FORBIDDEN_PACKAGES:
            del sys.modules[mod_name]

    importlib.import_module("runtime")

    leaked = {
        m for m in sys.modules
        if m.split(".")[0] in FORBIDDEN_PACKAGES
    }
    assert leaked == set(), f"runtime imported forbidden packages: {leaked}"
