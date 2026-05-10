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


from matter_expert.concept import ConceptFrontmatter, Source
from datetime import date
from matter_expert.index import LinkGraph, LinkGraphEntry


def test_link_graph_entry_round_trip():
    entry = LinkGraphEntry(
        related=["jwt-tokens"],
        prerequisites=["http-basics"],
        examples=["oauth2-google-flow"],
        contrasts=["basic-auth"],
        refines=["authentication-overview"],
        leads_to=[],
        instances=[],
        refined_by=[],
    )
    assert LinkGraphEntry.from_dict(entry.to_dict()) == entry


def test_link_graph_round_trip(tmp_path: Path):
    graph = LinkGraph({
        "oauth2-flow": LinkGraphEntry(
            related=["jwt-tokens"],
            prerequisites=["http-basics"],
            examples=["oauth2-google-flow"],
            contrasts=["basic-auth"],
            refines=["authentication-overview"],
            leads_to=[],
            instances=[],
            refined_by=[],
        ),
    })
    file = tmp_path / "link_graph.json"
    graph.write(file)

    assert LinkGraph.read(file) == graph


def test_link_graph_build_from_concepts_computes_inverse_links():
    """Builder builds LinkGraph from concept frontmatter and materializes
    the inverse links (leads_to, instances, refined_by)."""
    today = date(2026, 5, 10)
    src = Source(file="a.pdf", sections=[])

    oauth2 = ConceptFrontmatter(
        title="OAuth2", sources=[src], tags=[], created=today,
        prerequisites=["http-basics"],
        examples=["oauth2-google-flow"],
        refines=["authentication-overview"],
    )
    http_basics = ConceptFrontmatter(
        title="HTTP", sources=[src], tags=[], created=today,
    )
    google_flow = ConceptFrontmatter(
        title="Google Flow", sources=[src], tags=[], created=today,
    )
    auth_overview = ConceptFrontmatter(
        title="Auth", sources=[src], tags=[], created=today,
    )

    graph = LinkGraph.build({
        "oauth2-flow": oauth2,
        "http-basics": http_basics,
        "oauth2-google-flow": google_flow,
        "authentication-overview": auth_overview,
    })

    # Forward links preserved:
    assert graph["oauth2-flow"].prerequisites == ["http-basics"]

    # Inverse links materialized:
    assert "oauth2-flow" in graph["http-basics"].leads_to
    assert "oauth2-flow" in graph["oauth2-google-flow"].instances
    assert "oauth2-flow" in graph["authentication-overview"].refined_by


def test_link_graph_build_includes_symmetric_links_unchanged():
    """related and contrasts are symmetric — both sides set them via
    the link agent. LinkGraph.build does not flip them again."""
    today = date(2026, 5, 10)
    src = Source(file="a.pdf", sections=[])

    a = ConceptFrontmatter(
        title="A", sources=[src], tags=[], created=today,
        related=["b"], contrasts=["c"],
    )
    b = ConceptFrontmatter(
        title="B", sources=[src], tags=[], created=today,
        related=["a"],
    )
    c = ConceptFrontmatter(
        title="C", sources=[src], tags=[], created=today,
        contrasts=["a"],
    )

    graph = LinkGraph.build({"a": a, "b": b, "c": c})

    assert graph["a"].related == ["b"]
    assert graph["b"].related == ["a"]
    assert graph["a"].contrasts == ["c"]
    assert graph["c"].contrasts == ["a"]


from matter_expert.index import AliasMap


def test_alias_map_round_trip(tmp_path: Path):
    aliases = AliasMap({
        "OAuth": "oauth2-flow",
        "OAuth 2.0": "oauth2-flow",
        "Authorization Code Grant": "oauth2-flow",
        "JWT": "jwt-tokens",
    })
    file = tmp_path / "alias_map.json"
    aliases.write(file)

    assert AliasMap.read(file) == aliases


def test_alias_map_lookup_case_insensitive():
    aliases = AliasMap({"OAuth": "oauth2-flow", "JWT": "jwt-tokens"})

    assert aliases.resolve("OAuth") == "oauth2-flow"
    assert aliases.resolve("oauth") == "oauth2-flow"
    assert aliases.resolve("OAUTH") == "oauth2-flow"
    assert aliases.resolve("jwt") == "jwt-tokens"


def test_alias_map_lookup_missing_returns_none():
    aliases = AliasMap({"OAuth": "oauth2-flow"})
    assert aliases.resolve("nonexistent") is None


def test_alias_map_build_from_concept_index():
    """Builder builds the AliasMap by inverting the aliases of each
    ConceptIndexEntry."""
    index = ConceptIndex({
        "oauth2-flow": ConceptIndexEntry(
            path="concepts/oauth2-flow.md",
            title="OAuth2 Flow",
            summary="...", tags=[],
            aliases=["OAuth", "OAuth 2.0"],
            moc=[],
        ),
        "jwt-tokens": ConceptIndexEntry(
            path="concepts/jwt-tokens.md",
            title="JWT Tokens",
            summary="...", tags=[],
            aliases=["JWT", "JSON Web Token"],
            moc=[],
        ),
    })
    aliases = AliasMap.build(index)

    assert aliases.resolve("OAuth") == "oauth2-flow"
    assert aliases.resolve("OAuth 2.0") == "oauth2-flow"
    assert aliases.resolve("JWT") == "jwt-tokens"
    assert aliases.resolve("JSON Web Token") == "jwt-tokens"
