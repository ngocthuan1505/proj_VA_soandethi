"""Mẫu số giữ cả UNKNOWN; phiếu trống không tự có kết quả sư phạm."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "poc_evaluation", Path(__file__).resolve().parents[2] / "scripts/danh-gia-bo-kiem.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_empty_annotations_stay_pending_and_never_report_accuracy():
    sheet = evaluation.prepare(
        {
            "candidateHash": "a" * 64,
            "checks": [
                {"toolName": "verify_options", "candidateHash": "a" * 64, "status": "PASS"},
            ],
        }
    )
    result = evaluation.evaluate(sheet)
    assert result["pending"] == 1 and result["groups"] == []
    assert result["pedagogicalApproval"] is False
    with pytest.raises(ValueError):
        evaluation.prepare(
            {
                "candidateHash": "a" * 64,
                "checks": [
                    {"toolName": "verify_options", "candidateHash": "b" * 64, "status": "PASS"},
                ],
            }
        )


def test_unknown_is_not_removed_and_mechanism_is_not_mixed_with_expert():
    cases = []
    for kind in ("mechanism", "expert"):
        for expected, observed in (
            ("FAIL", "FAIL"),
            ("FAIL", "PASS"),
            ("FAIL", "UNKNOWN"),
            ("PASS", "FAIL"),
        ):
            cases.append(
                {
                    "toolName": "verify_options",
                    "referenceKind": kind,
                    "expectedStatus": expected,
                    "observedStatus": observed,
                    "confirmedBy": "Danh tính giả trong test",
                    "reason": "Fixture kiểm phép tính.",
                }
            )
    result = evaluation.evaluate({"cases": cases})
    assert result["pending"] == 0 and len(result["groups"]) == 2
    for group in result["groups"]:
        assert group["detected"] == group["missed"] == group["unknown"] == 1
        assert group["detectionRate"] == 1 / 3
        assert group["falseBlockRate"] == 1


def test_comparison_requires_same_checker_and_keeps_failed_and_interrupted(tmp_path, monkeypatch):
    logs = tmp_path / "agent"
    monkeypatch.setattr(evaluation, "AGENT_LOGS", logs)
    directories = []
    for i, status in enumerate(("complete", "failed", "interrupted")):
        path = tmp_path / str(i)
        path.mkdir()
        directories.append(path)
        (path / "input.json").write_text(
            json.dumps({"sample": {"text": "Nguồn cố định"}, "approval": {"plan": {"slots": []}}}),
            encoding="utf8",
        )
        if status != "interrupted":
            (path / "result.json").write_text(
                json.dumps(
                    {
                        "job": {"status": status, "jobId": str(i)},
                        "model": "generator-" + str(i),
                        "checks": {"summary": {}},
                    }
                ),
                encoding="utf8",
            )
            directory = logs / str(i)
            directory.mkdir(parents=True)
            (directory / "environment.json").write_text(
                json.dumps(
                    {
                        "reviewer": {"model": "fixed"},
                        "runPolicy": {"maxModelCalls": 24},
                        "sourceSha256": {"file.py": "a"},
                    }
                ),
                encoding="utf8",
            )
    result = evaluation.compare_runs(directories[:2])
    assert result["controlledComparison"] and result["totalRuns"] == 2
    assert [r["ready"] for r in result["runs"]] == [True, False]
    result = evaluation.compare_runs(directories)
    assert not result["controlledComparison"] and result["totalRuns"] == 3
    assert result["runs"][-1]["status"] == "interrupted"
