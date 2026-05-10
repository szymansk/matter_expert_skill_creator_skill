from builder.link.cardinality import (
    MAX_RELATED, MAX_PREREQUISITES, MAX_EXAMPLES,
    MAX_CONTRASTS, MAX_REFINES,
    enforce_link_cardinality,
)


def test_constants_match_design_spec():
    assert MAX_RELATED == 8
    assert MAX_PREREQUISITES == 5
    assert MAX_EXAMPLES == 6
    assert MAX_CONTRASTS == 4
    assert MAX_REFINES == 3


def test_under_limit_unchanged():
    links = {
        "related": ["a", "b"],
        "prerequisites": ["c"],
        "examples": [],
        "contrasts": [],
        "refines": [],
    }
    assert enforce_link_cardinality(links) == links


def test_over_limit_trimmed_to_max():
    links = {
        "related": [f"r{i}" for i in range(12)],
        "prerequisites": [],
        "examples": [],
        "contrasts": [],
        "refines": [],
    }
    result = enforce_link_cardinality(links)
    assert len(result["related"]) == MAX_RELATED
    assert result["related"] == [f"r{i}" for i in range(MAX_RELATED)]


def test_all_link_types_enforced():
    over = {
        "related": [f"a{i}" for i in range(20)],
        "prerequisites": [f"b{i}" for i in range(10)],
        "examples": [f"c{i}" for i in range(10)],
        "contrasts": [f"d{i}" for i in range(10)],
        "refines": [f"e{i}" for i in range(10)],
    }
    result = enforce_link_cardinality(over)
    assert len(result["related"]) == MAX_RELATED
    assert len(result["prerequisites"]) == MAX_PREREQUISITES
    assert len(result["examples"]) == MAX_EXAMPLES
    assert len(result["contrasts"]) == MAX_CONTRASTS
    assert len(result["refines"]) == MAX_REFINES
