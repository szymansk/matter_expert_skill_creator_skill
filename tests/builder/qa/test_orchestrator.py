import json
from pathlib import Path

from builder.phases import Phase
from builder.pipeline import Pipeline
from builder.qa.orchestrator import QAOrchestrator
from builder.qa.report import OverallStatus, QAReport


def test_orchestrator_writes_report_to_disk(populated_vault, canned_agent, run_dir, tmp_path):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": [],
                                         "missed_topics": [],
                                         "unsupported_claims": [],
                                         "issues": []})

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    out_path = tmp_path / "qa_report.json"
    orch = QAOrchestrator(agent=canned_agent, source_outlines={})

    report = orch.run(vault=populated_vault, pipeline=pipeline,
                      report_path=out_path)
    assert isinstance(report, QAReport)
    assert out_path.exists()
    reloaded = QAReport.from_dict(json.loads(out_path.read_text()))
    assert reloaded.overall_status == report.overall_status


def test_orchestrator_aggregates_all_6_validators(
    populated_vault, canned_agent, run_dir, tmp_path,
):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": [],
                                         "missed_topics": [],
                                         "unsupported_claims": [],
                                         "issues": []})
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = QAOrchestrator(agent=canned_agent, source_outlines={})
    report = orch.run(vault=populated_vault, pipeline=pipeline,
                      report_path=tmp_path / "qa.json")

    names = {v.name for v in report.validators}
    assert names == {
        "translation_quality", "link_resolution", "coverage",
        "citation_accuracy", "concept_coherence", "vault_integrity",
    }


def test_orchestrator_records_cost_to_pipeline(
    populated_vault, canned_agent, run_dir, tmp_path,
):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": [],
                                         "missed_topics": [],
                                         "unsupported_claims": [],
                                         "issues": []})
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = QAOrchestrator(agent=canned_agent, source_outlines={})
    orch.run(vault=populated_vault, pipeline=pipeline,
             report_path=tmp_path / "qa.json")
    assert pipeline.state.cost_tracker["per_phase"].get("qa", 0) > 0


def test_orchestrator_overall_status_pass(
    populated_vault, canned_agent, run_dir, tmp_path,
):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": [],
                                         "missed_topics": [],
                                         "unsupported_claims": [],
                                         "issues": []})
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = QAOrchestrator(agent=canned_agent, source_outlines={})
    report = orch.run(vault=populated_vault, pipeline=pipeline,
                      report_path=tmp_path / "qa.json")
    assert report.overall_status == OverallStatus.PASS
