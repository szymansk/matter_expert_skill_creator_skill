import json
from pathlib import Path

from matter_expert.index import ConceptIndex, ConceptIndexEntry


def test_concept_index_entry_round_trip():
    entry = ConceptIndexEntry(
        path="concepts/oauth2-flow.md",
        title="OAuth2 Flow",
        summary="Authorization framework using access/refresh tokens",
        tags=["auth", "oauth2"],
        aliases=["OAuth 2.0", "Authorization Code Grant"],
        moc=["MOCs/authentication.md"],
    )
    assert ConceptIndexEntry.from_dict(entry.to_dict()) == entry


def test_concept_index_round_trip(tmp_path: Path):
    index = ConceptIndex({
        "oauth2-flow": ConceptIndexEntry(
            path="concepts/oauth2-flow.md",
            title="OAuth2 Flow",
            summary="...",
            tags=["auth"],
            aliases=["OAuth 2.0"],
            moc=["MOCs/authentication.md"],
        ),
        "jwt-tokens": ConceptIndexEntry(
            path="concepts/jwt-tokens.md",
            title="JWT Tokens",
            summary="...",
            tags=["auth", "tokens"],
            aliases=["JWT", "JSON Web Token"],
            moc=["MOCs/authentication.md"],
        ),
    })
    file = tmp_path / "concept_index.json"
    index.write(file)

    reread = ConceptIndex.read(file)
    assert reread == index


def test_concept_index_lookup():
    index = ConceptIndex({
        "oauth2-flow": ConceptIndexEntry(
            path="concepts/oauth2-flow.md",
            title="OAuth2 Flow",
            summary="...",
            tags=["auth"],
            aliases=["OAuth 2.0"],
            moc=[],
        ),
    })
    assert index["oauth2-flow"].title == "OAuth2 Flow"
    assert "oauth2-flow" in index
    assert "missing" not in index


def test_concept_index_disk_format_is_json(tmp_path: Path):
    """Verify the JSON on disk is valid and human-readable."""
    index = ConceptIndex({
        "x": ConceptIndexEntry(
            path="concepts/x.md", title="X", summary="...",
            tags=[], aliases=[], moc=[],
        ),
    })
    file = tmp_path / "concept_index.json"
    index.write(file)

    raw = json.loads(file.read_text())
    assert "x" in raw
    assert raw["x"]["title"] == "X"


from matter_expert.index import MOCMap, MOCMapEntry


def test_moc_map_entry_round_trip():
    entry = MOCMapEntry(
        path="MOCs/authentication.md",
        children=["oauth2-flow", "jwt-tokens"],
        parents=["security"],
    )
    assert MOCMapEntry.from_dict(entry.to_dict()) == entry


def test_moc_map_round_trip(tmp_path: Path):
    mocs = MOCMap({
        "authentication": MOCMapEntry(
            path="MOCs/authentication.md",
            children=["oauth2-flow", "jwt-tokens"],
            parents=["security"],
        ),
        "security": MOCMapEntry(
            path="MOCs/security.md",
            children=[],
            parents=[],
        ),
    })
    file = tmp_path / "moc_map.json"
    mocs.write(file)

    reread = MOCMap.read(file)
    assert reread == mocs
