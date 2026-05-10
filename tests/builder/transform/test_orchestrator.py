import json
from datetime import date
from pathlib import Path

from builder.ingest.protocols import ConvertResult
from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.phases import Phase
from builder.pipeline import Pipeline
from builder.transform.orchestrator import TransformOrchestrator
from matter_expert import ConceptPage


def _convert_result(name: str, content: str = "body text"):
    return ConvertResult(
        content=content,
        meta=DocumentMeta(
            source_path=f"/x/{name}",
            source_type="md",
            extraction_method=ExtractionMethod.PASSTHROUGH,
            page_count=1,
            extracted_chars=len(content),
            extracted_images_count=0,
            outline=["A", "B"],
            language_detected="en",
            ingested=date(2026, 5, 10),
        ),
    )


def test_orchestrator_runs_full_pipeline_for_one_document(
    canned_agent, tmp_path, run_dir,
):
    canned_agent.recipes["Identify"] = json.dumps({"entries": [
        {"concept_name": "concept-a", "title": "Concept A",
         "source_sections": [], "estimated_tokens": 800},
    ]})
    canned_agent.recipes["Target concept"] = (
        "# Concept A\n\nBody of concept A.\n"
    )
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    results = orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md")},
        pipeline=pipeline,
    )

    assert "doc1.md" in results
    # One concept page written
    concept_path = vault_dir / "concepts" / "concept-a.md"
    assert concept_path.exists()
    # Concept page parses as a valid ConceptPage
    page = ConceptPage.read(concept_path)
    assert page.frontmatter.title == "Concept A"
    assert "Body of concept A" in page.body
    # Pipeline records item done and cost > 0
    item = pipeline.state.phases["transform"].items["doc1.md"]
    assert item.status == "done"
    assert pipeline.state.cost_tracker["per_phase"]["transform"] > 0


def test_orchestrator_marks_failed_on_analyzer_error(
    canned_agent, tmp_path, run_dir,
):
    canned_agent.default = "not valid json at all"

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    results = orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md")},
        pipeline=pipeline,
    )

    assert "doc1.md" not in results
    assert pipeline.state.phases["transform"].items["doc1.md"].status == "failed"


def test_orchestrator_writes_source_pages(
    canned_agent, tmp_path, run_dir,
):
    """Each source document is preserved under vault/sources/."""
    canned_agent.recipes["Identify"] = json.dumps({"entries": []})
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})

    vault_dir = tmp_path / "vault"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = TransformOrchestrator(agent=canned_agent, vault_dir=vault_dir)

    orch.transform(
        ingest_results={"doc1.md": _convert_result("doc1.md", content="original body")},
        pipeline=pipeline,
    )

    # Source page written under vault/sources/.
    source_path = vault_dir / "sources" / "doc1.md"
    assert source_path.exists()
    assert "original body" in source_path.read_text(encoding="utf-8")
