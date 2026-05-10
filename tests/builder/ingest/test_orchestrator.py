from pathlib import Path

from builder.ingest.orchestrator import IngestOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline


def test_orchestrator_handles_md_file(ingest_fixtures_dir, mock_agent, mock_fetcher,
                                       run_dir):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(
        ingest_fixtures_dir, pipeline=pipeline, only_files=["plain.md"],
    )

    assert len(results) == 1
    assert "plain.md" in results
    item = pipeline.state.phases["ingest"].items["plain.md"]
    assert item.status == "done"
    assert item.metadata["extraction_method"] == "passthrough"


def test_orchestrator_handles_url(mock_agent, mock_fetcher, ingest_fixtures_dir,
                                    run_dir):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir,
        url_list=["https://example.com/spec"], run_dir=run_dir,
    )
    mock_fetcher.responses["https://example.com/spec"] = "<h1>S</h1><p>body</p>"
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)

    results = orch.ingest_urls(["https://example.com/spec"], pipeline=pipeline)

    assert "https://example.com/spec" in results
    items = pipeline.state.phases["ingest"].items
    assert items["https://example.com/spec"].status == "done"
    assert items["https://example.com/spec"].metadata["extraction_method"] == "url_fetch"


def test_orchestrator_failed_url_marks_item_failed(mock_agent, ingest_fixtures_dir, run_dir):
    """A fetcher that raises causes the item to be marked failed."""
    class FailingFetcher:
        def fetch(self, url: str) -> str:
            raise RuntimeError("network down")

    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=FailingFetcher())
    results = orch.ingest_urls(["https://x"], pipeline=pipeline)

    assert "https://x" not in results
    assert pipeline.state.phases["ingest"].items["https://x"].status == "failed"
    assert "network down" in (pipeline.state.phases["ingest"].items["https://x"].error or "")


def test_orchestrator_dispatches_pdf_to_text_when_plausible(
    ingest_fixtures_dir, mock_agent, mock_fetcher, run_dir,
):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(
        ingest_fixtures_dir, pipeline=pipeline, only_files=["tiny.pdf"],
    )
    assert "tiny.pdf" in results
    item = pipeline.state.phases["ingest"].items["tiny.pdf"]
    # tiny.pdf has enough text → text extraction succeeds, no vision calls.
    assert item.metadata["extraction_method"] == "text"
    assert mock_agent.calls == []  # vision not invoked


def test_orchestrator_unknown_extension_marks_failed(
    tmp_path: Path, mock_agent, mock_fetcher, run_dir,
):
    pipeline = Pipeline.create(
        run_id="x", input_dir=tmp_path, url_list=[], run_dir=run_dir,
    )
    bad = tmp_path / "weird.xyz"
    bad.write_text("hi")

    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(tmp_path, pipeline=pipeline,
                                     only_files=["weird.xyz"])
    assert "weird.xyz" not in results
    assert pipeline.state.phases["ingest"].items["weird.xyz"].status == "failed"
