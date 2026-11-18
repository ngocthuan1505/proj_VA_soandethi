"""Ngân sách hữu hạn và báo cáo cùng bản; không gọi model."""

import json

import pytest
from pydantic import ValidationError

from mach_backend.ai_contract import AIError
from mach_backend.poc_policy import (
    CHECK_NAMES,
    CallBudget,
    CandidateChecks,
    CheckReport,
    RunPolicy,
    report_from_trace,
)


def test_budget_is_shared_and_does_not_reset_between_roles(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("mach_backend.poc_policy.time.monotonic", lambda: now[0])
    budget = CallBudget(3, 30)
    for _role in ("generate", "blind", "explanation"):
        budget.spend()
    with pytest.raises(AIError, match="ngân sách"):
        budget.spend()
    assert budget.calls == 3
    now[0] = 131
    with pytest.raises(AIError, match="thời gian"):
        budget.remaining()


@pytest.mark.parametrize(
    "body",
    [{"maxModelCalls": 0}, {"maxModelCalls": True}, {"maxModelCalls": 65}, {"timeoutSeconds": 901}],
)
def test_operator_budget_is_bounded(body):
    with pytest.raises(ValidationError):
        RunPolicy.model_validate(body)


def test_unknown_or_missing_checks_cannot_pass_and_reports_bind_candidate():
    rows = []
    checks = CandidateChecks("a" * 64, lambda event, **row: rows.append(row))
    checks.record("validate_schema")
    assert not checks.finish([])["ok"]
    for name in CHECK_NAMES:
        if name != "aggregate_checks":
            checks.record(name)
    passed = checks.finish([])
    assert passed["ok"]
    assert all(
        CheckReport.model_validate_json(json.dumps(r)).candidateHash == "a" * 64
        for r in passed["checks"]
    )
    checks.record("verify_options", status="UNKNOWN")
    assert not checks.finish([])["ok"]
    other = CandidateChecks("b" * 64, lambda *_args, **_kwargs: None)
    assert not other.finish([])["ok"]
    assert all(r["candidateHash"] == "b" * 64 for r in other.finish([])["checks"])


def test_interrupted_check_never_borrows_results_from_previous_submission():
    passed = CheckReport(
        toolName="check_explanation", candidateHash="a" * 64, status="PASS"
    ).model_dump(mode="json")
    schema = CheckReport(
        toolName="validate_schema", candidateHash="a" * 64, status="PASS"
    ).model_dump(mode="json")
    events = [
        {"event": "tool_call", "tool": "check_exam", "generationAttempt": 1},
        {"event": "check_report", **passed},
        {"event": "tool_call", "tool": "check_exam", "generationAttempt": 2},
        {"event": "check_report", **schema},
    ]
    report = report_from_trace(events)
    assert report["generationAttempt"] == 2
    checks = {r["toolName"]: r for r in report["checks"]}
    assert checks["validate_schema"]["status"] == "PASS"
    assert checks["check_explanation"]["status"] == "UNKNOWN"
    assert checks["aggregate_checks"]["status"] == "UNKNOWN"
