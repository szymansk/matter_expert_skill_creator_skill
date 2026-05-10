from builder.qa.report import (
    OverallStatus, QAReport, Severity, ValidatorResult,
)


def test_severity_values():
    assert Severity.PASS.value == "pass"
    assert Severity.WARNING.value == "warning"
    assert Severity.FAIL.value == "fail"


def test_overall_status_values():
    assert OverallStatus.PASS.value == "pass"
    assert OverallStatus.PASS_WITH_WARNINGS.value == "pass_with_warnings"
    assert OverallStatus.FAIL.value == "fail"


def test_validator_result_round_trip():
    r = ValidatorResult(
        name="translation_quality",
        severity=Severity.WARNING,
        sampled=18, total=180,
        issues=[{"concept": "x", "issue": "minor"}],
        notes="sampled 10%",
    )
    assert ValidatorResult.from_dict(r.to_dict()) == r


def test_qa_report_round_trip():
    report = QAReport(
        overall_status=OverallStatus.PASS_WITH_WARNINGS,
        validators=[
            ValidatorResult(name="v1", severity=Severity.PASS,
                            sampled=10, total=10, issues=[], notes=""),
            ValidatorResult(name="v2", severity=Severity.WARNING,
                            sampled=5, total=5, issues=[{"x": 1}], notes=""),
        ],
        recommendations=["Re-run coverage"],
    )
    assert QAReport.from_dict(report.to_dict()) == report


def test_qa_report_compute_overall_all_pass():
    validators = [
        ValidatorResult("a", Severity.PASS, 10, 10, [], ""),
        ValidatorResult("b", Severity.PASS, 5, 5, [], ""),
    ]
    assert QAReport.compute_overall(validators) == OverallStatus.PASS


def test_qa_report_compute_overall_any_warning():
    validators = [
        ValidatorResult("a", Severity.PASS, 10, 10, [], ""),
        ValidatorResult("b", Severity.WARNING, 5, 5, [], ""),
    ]
    assert QAReport.compute_overall(validators) == OverallStatus.PASS_WITH_WARNINGS


def test_qa_report_compute_overall_any_fail():
    validators = [
        ValidatorResult("a", Severity.PASS, 10, 10, [], ""),
        ValidatorResult("b", Severity.WARNING, 5, 5, [], ""),
        ValidatorResult("c", Severity.FAIL, 2, 2, [], ""),
    ]
    assert QAReport.compute_overall(validators) == OverallStatus.FAIL
