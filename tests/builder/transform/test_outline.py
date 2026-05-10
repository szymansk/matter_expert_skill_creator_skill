from builder.transform.outline import ConceptOutline, OutlineEntry


def test_outline_entry_construction():
    entry = OutlineEntry(
        concept_name="oauth2-flow",
        title="OAuth2 Flow",
        source_sections=["3.1", "3.2"],
        estimated_tokens=1200,
    )
    assert entry.concept_name == "oauth2-flow"
    assert entry.estimated_tokens == 1200


def test_outline_entry_round_trip():
    entry = OutlineEntry(
        concept_name="x",
        title="X",
        source_sections=["1.1"],
        estimated_tokens=500,
    )
    assert OutlineEntry.from_dict(entry.to_dict()) == entry


def test_concept_outline_round_trip():
    outline = ConceptOutline(entries=[
        OutlineEntry(concept_name="a", title="A",
                     source_sections=[], estimated_tokens=600),
        OutlineEntry(concept_name="b", title="B",
                     source_sections=["2.1"], estimated_tokens=1200),
    ])
    assert ConceptOutline.from_dict(outline.to_dict()) == outline


def test_concept_outline_iteration():
    outline = ConceptOutline(entries=[
        OutlineEntry(concept_name="a", title="A",
                     source_sections=[], estimated_tokens=100),
    ])
    names = [e.concept_name for e in outline]
    assert names == ["a"]
