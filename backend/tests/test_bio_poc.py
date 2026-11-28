"""Chạy đúng mẫu Sinh học PoC qua API với phản hồi lỗi soạn sẵn, không là AI thật."""

import importlib.util
import time
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_local_workspace import workspace  # noqa: F401

from mach_backend.local_workspace import create_app

spec = importlib.util.spec_from_file_location(
    "bio_fixture_server", Path(__file__).resolve().parents[2] / "scripts/chay-fixture-poc.py"
)
fixture_server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_server)


@pytest.fixture
def bio(request, workspace, tmp_path):  # noqa: F811
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    app = create_app(tmp_path / "bio", agent_call=fixture_server.FixtureCase(request.param))
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        sample = client.get("/api/poc/sample").json()
        state["exams"][0].update(
            subject=sample["subject"],
            grade=sample["grade"],
            matrix=sample["matrix"],
            aiInstructions=sample["instructions"],
        )
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        prefix = "/api/exams/" + exam["id"]
        approval = client.post(
            prefix + "/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": sample["text"],
                "sourceName": "Sinh học tự viết",
            },
        ).json()
        submitted = client.post(
            prefix + "/proposals/generate",
            json={
                **approval,
                "requestId": str(uuid4()),
                "consent": True,
                "requireEvidence": True,
            },
            headers={"X-PoC-Config": client.get("/api/config").json()["fingerprint"]},
        )
        assert submitted.status_code == 202, submitted.text
        base = prefix + "/proposals/" + submitted.json()["jobId"]
        yield client, exam, base, sample, approval


@pytest.mark.parametrize(
    "bio,code",
    [
        ("repair", "answer_disagreement"),
        ("missing_question", "invalid_plan"),
        ("multiple_correct", "option_verdicts_failed"),
        ("unsupported", "unsupported_answer"),
        ("unknown", "uncertain_answer"),
        ("wrong_level", "level_disagreement"),
        ("duplicate", "semantic_duplicate"),
    ],
    indirect=["bio"],
)
def test_bio_four_questions_repair_and_recheck_without_touching_exam(bio, code):
    client, exam, base, sample, approval = bio
    for _ in range(100):
        result = client.get(base + "/status").json()
        if result["status"] != "running":
            break
        time.sleep(0.02)
    assert result["status"] == "complete", result
    trace = client.get(base + "/trace").json()
    reports = [row for row in trace if row["event"] == "generation_result"]
    assert not reports[0]["ok"] and reports[-1]["ok"]
    assert reports[0]["candidateHash"] != reports[-1]["candidateHash"]
    assert code in [error["code"] for error in reports[0]["errors"]]
    questions = result["proposal"]["questions"]
    assert len(questions) == 4
    assert [q["level"] for q in questions] == [0, 1, 0, 2]
    assert [q["pointsQ4"] for q in questions] == [10] * 4
    report = client.get(base + "/report").json()
    assert len(report["checks"]) == 10
    assert all(
        row["status"] == "PASS" and row["candidateHash"] == report["candidateHash"]
        for row in report["checks"]
    )
    saved = client.get("/api/kv?key=state").json()["value"]["exams"][0]
    assert saved["revision"] == 1 and saved["questions"] == []
    assert client.post(base + "/confirm", json={"baseRevision": 1}).status_code == 400
    assert client.get(base + "/review-pack").status_code == 200
    assert all(marker in sample["text"] for marker in ("S1.", "S2.", "S3."))
    assert approval["plan"]["subject"] == "Sinh học"


@pytest.mark.parametrize("bio", ["cancel"], indirect=True)
def test_bio_cancel_keeps_original_source_matrix_and_questions(bio):
    client, _, base, _, _ = bio
    before = client.get("/api/kv?key=state").json()
    client.post(base + "/cancel", json={}).raise_for_status()
    assert client.get(base + "/status").json()["status"] == "cancelled"
    assert client.get("/api/kv?key=state").json() == before


@pytest.mark.parametrize("bio", ["budget"], indirect=True)
def test_bio_budget_stops_without_partial_save(bio):
    client, _, base, _, _ = bio
    before = client.get("/api/kv?key=state").json()
    for _ in range(200):
        result = client.get(base + "/status").json()
        if result["status"] != "running":
            break
        time.sleep(0.02)
    assert result["status"] == "failed" and result["errorCode"] == "call_budget"
    trace = client.get(base + "/trace").json()
    assert len([row for row in trace if row["event"] == "generation_result"]) > 2
    assert client.get("/api/kv?key=state").json() == before
    assert client.get(base + "/review-pack").status_code == 409


@pytest.mark.parametrize("bio", ["repair"], indirect=True)
@pytest.mark.parametrize("changed", ["exam", "source"])
def test_bio_stale_exam_or_source_keeps_human_changes(bio, changed):
    client, exam, base, sample, _ = bio
    for _ in range(100):
        if client.get(base + "/status").json()["status"] != "running":
            break
        time.sleep(0.02)
    before = client.get("/api/kv?key=state").json()
    if changed == "exam":
        before["value"]["exams"][0].update(revision=2, title="Bản người dùng đã sửa")
        client.put(
            "/api/kv",
            json={"key": "state", "value": before["value"]},
            headers={"If-Match": str(before["revision"])},
        ).raise_for_status()
    else:
        client.post(
            "/api/exams/" + exam["id"] + "/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": sample["text"] + "\nNguồn được người dùng bổ sung.",
                "sourceName": "Nguồn phiên bản mới",
            },
        ).raise_for_status()
    current = client.get("/api/kv?key=state").json()
    rejected = client.post(base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True})
    assert rejected.status_code == 409
    assert client.get("/api/kv?key=state").json() == current
