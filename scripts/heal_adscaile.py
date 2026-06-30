# scripts/heal_adscaile.py
"""One-off: heal the already-built adscaile-expert skill in place.

Rebuilds its _index with the fixed builder (populating aliases), copies the
fixed runtime scripts into its bundled scripts/runtime/, and seeds an editable
synonyms.json. Not part of the plugin; lives in the generator repo only.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "docs-to-skill" / "skills" / "docs-to-skill" / "scripts" / "lib"
sys.path.insert(0, str(LIB))

BUILT = Path(
    "/Users/marc.szymanski/Projects/adSCAILE_expert/adscaile-expert/"
    "skills/adscaile-expert"
)

from builder.emit.index_builder import build_indexes  # noqa: E402
from matter_expert import VaultPaths  # noqa: E402

SYNONYM_GROUPS = {
    "groups": [
        ["rerun", "resume", "wiederaufnahme", "idempotenz", "resumable"],
        ["bugfix", "fix", "patch"],
    ]
}


def main() -> int:
    if not BUILT.exists():
        print(f"built skill not found: {BUILT}")
        return 1

    # 1. Rebuild the index (fills aliases + alias_map).
    build_indexes(vault=VaultPaths(root=BUILT / "vault"),
                  index_dir=BUILT / "_index")

    # 2. Copy the fixed runtime scripts.
    runtime_src = LIB / "runtime"
    runtime_dst = BUILT / "scripts" / "runtime"
    for fname in ("vault_search.py", "vault_locate.py", "text.py"):
        shutil.copy2(runtime_src / fname, runtime_dst / fname)

    # 3. Seed editable synonyms.
    (BUILT / "memory" / "synonyms.json").write_text(
        json.dumps(SYNONYM_GROUPS, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 4. Report.
    cidx = json.loads((BUILT / "_index" / "concept_index.json").read_text())
    amap = json.loads((BUILT / "_index" / "alias_map.json").read_text())
    with_aliases = sum(1 for v in cidx.values() if v.get("aliases"))
    print(f"concepts: {len(cidx)}, with aliases: {with_aliases}, "
          f"alias_map entries: {len(amap)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
