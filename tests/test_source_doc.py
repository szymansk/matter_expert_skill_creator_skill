from datetime import date
from pathlib import Path

from matter_expert.source_doc import SourceFrontmatter, SourcePage


def test_source_frontmatter_round_trip():
    fm = SourceFrontmatter(
        title="Security Handbook",
        original_file="handbook.pdf",
        original_format="pdf",
        page_count=240,
        extraction_method="text",
        language_detected="de",
        ingested=date(2026, 5, 10),
    )
    assert SourceFrontmatter.from_dict(fm.to_dict()) == fm


def test_source_page_round_trip(tmp_path: Path):
    fm = SourceFrontmatter(
        title="Security Handbook",
        original_file="handbook.pdf",
        original_format="pdf",
        page_count=240,
        extraction_method="text",
        language_detected="de",
        ingested=date(2026, 5, 10),
    )
    page = SourcePage(
        frontmatter=fm,
        body="# Security Handbook\n\nFull converted content here.\n",
        path=tmp_path / "handbook.md",
    )
    page.write()

    reread = SourcePage.read(page.path)
    assert reread.frontmatter == fm
    assert reread.body.strip() == page.body.strip()
    assert reread.name == "handbook"
