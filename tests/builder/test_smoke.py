import builder


def test_builder_package_importable():
    assert builder.__version__ == "0.0.1"
