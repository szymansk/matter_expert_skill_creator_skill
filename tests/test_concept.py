from matter_expert.concept import Source


def test_source_from_dict():
    data = {"file": "handbook.pdf", "sections": ["3.1", "3.2"]}
    source = Source.from_dict(data)

    assert source.file == "handbook.pdf"
    assert source.sections == ["3.1", "3.2"]


def test_source_to_dict_round_trip():
    original = Source(file="security.pdf", sections=["2.4"])
    assert Source.from_dict(original.to_dict()) == original


def test_source_to_dict_no_sections():
    source = Source(file="readme.md", sections=[])
    assert source.to_dict() == {"file": "readme.md", "sections": []}
