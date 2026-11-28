"""Kế thừa ca revision/replay/rollback BE-3, kiểm chính kho PoC bằng fixture, không di trú DB."""

import asyncio
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_local_workspace import AgentModelFixture, generate, workspace  # noqa: F401

from mach_backend.ai_contract import AIError
from mach_backend.local_workspace import create_app
from mach_backend.matrix_agent import sha256_json
from mach_backend.patch_confirmation import PendingGeneration, confirm_patch
from mach_backend.workspace_store import WorkspaceTransaction


@pytest.fixture
def ready(workspace, tmp_path):  # noqa: F811
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(tmp_path / "agent", agent_call=AgentModelFixture()),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, result = generate(client, exam)
        assert result["status"] == "complete"
        yield client, exam, base, result


def test_discard_is_durable_idempotent_and_never_changes_exam(ready, tmp_path):
    client, exam, base, _ = ready
    before = client.get("/api/kv?key=state").json()["value"]
    for _ in range(2):
        response = client.post(base + "/discard", json={})
        assert response.status_code == 200 and response.json()["discarded"]
    assert client.get("/api/kv?key=state").json()["value"] == before
    assert client.get("/api/exams/" + exam["id"] + "/proposals/latest").json()["discarded"]
    with TestClient(
        create_app(tmp_path / "agent"), headers={"Origin": "http://testserver"}
    ) as restarted:
        response = restarted.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        )
        assert response.status_code == 409 and response.json()["code"] == "proposal_discarded"
        assert restarted.get("/api/kv?key=state").json()["value"] == before


def test_discard_cannot_reverse_an_already_saved_proposal(ready):
    client, _, base, _ = ready
    client.post(
        base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
    ).raise_for_status()
    before = client.get("/api/kv?key=state").json()["value"]
    assert client.post(base + "/discard", json={}).status_code == 409
    assert client.get("/api/kv?key=state").json()["value"] == before


def test_discard_cannot_target_a_different_exam(ready):
    client, _, base, _ = ready
    other = "/api/exams/" + str(uuid4()) + "/proposals/" + base.rsplit("/", 1)[1]
    assert client.post(other + "/discard", json={}).status_code >= 400
    assert (
        client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        ).status_code
        == 200
    )


def race(function, items):
    barrier = Barrier(2)

    def run(item):
        barrier.wait(timeout=5)
        try:
            return "ok", function(item)
        except AIError as error:
            return error.code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, items))


def test_two_writers_with_same_workspace_revision_do_not_overwrite(ready):
    client, exam, _, _ = ready
    store = client.app.state.store
    before = store.get("state")
    candidates = []
    for title in ("Writer A", "Writer B"):
        state = deepcopy(before["value"])
        state["exams"][0]["title"] = title
        candidates.append(state)
    results = race(lambda value: store.put("state", value, before["revision"]), candidates)
    assert sorted(r[0] for r in results) == ["ok", "stale_snapshot"]
    after = store.get("state")
    assert after["revision"] == before["revision"] + 1
    assert after["value"]["exams"][0]["title"] in {"Writer A", "Writer B"}
    assert store.sources(exam["id"]) and store.plan(exam["id"])


def test_duplicate_concurrent_confirmation_commits_once(ready):
    client, exam, _, result = ready
    store = client.app.state.store
    job = UUID(result["jobId"])
    results = race(lambda _: confirm_patch(store, "local", UUID(exam["id"]), job, 1), [0, 1])
    assert [r[0] for r in results] == ["ok", "ok"]
    assert results[0][1] == results[1][1]
    saved = store.exam(exam["id"])[1]
    assert saved["revision"] == 2 and len(saved["history"]) == len(saved["undo"]) == 1
    assert len(saved["questions"]) == len({q["id"] for q in saved["questions"]}) == 2


def test_competing_proposals_only_one_can_change_exam(ready):
    client, exam, _, result = ready
    store = client.app.state.store
    with store.connect() as db:
        raw = db.execute(
            "SELECT payload FROM matrix_pending WHERE job_id=?", (result["jobId"],)
        ).fetchone()[0]
    first = PendingGeneration.model_validate_json(raw)
    other = uuid4()
    second = PendingGeneration(
        job=first.job.model_copy(update={"jobId": other}),
        proposal=first.proposal.model_copy(update={"jobId": other}),
    )
    assert asyncio.run(store.store_pending(second))
    metadata = store.get("matrix-agent-result:" + result["jobId"])["value"]
    store.put(
        "matrix-agent-result:" + str(other),
        {**metadata, "proposalSha256": sha256_json(second.proposal.model_dump(mode="json"))},
    )
    results = race(
        lambda job: confirm_patch(store, "local", UUID(exam["id"]), job, 1),
        [UUID(result["jobId"]), other],
    )
    assert sorted(r[0] for r in results) == ["ok", "stale_snapshot"]
    assert store.exam(exam["id"])[1]["revision"] == 2


def test_failed_confirmation_rolls_back_state_receipt_and_preserves_trace(ready, monkeypatch):
    client, exam, _, result = ready
    store, job = client.app.state.store, UUID(result["jobId"])
    before, trace = store.get("state"), store.trace(job)
    original = WorkspaceTransaction.write

    def broken(self, snapshot, receipt):
        original(self, snapshot, receipt)
        raise RuntimeError("Fixture lỗi sau ghi, trước commit.")

    with monkeypatch.context() as patch:
        patch.setattr(WorkspaceTransaction, "write", broken)
        with pytest.raises(RuntimeError):
            confirm_patch(store, "local", UUID(exam["id"]), job, 1)
    assert store.get("state") == before and store.trace(job) == trace
    with store.connect() as db:
        assert (
            db.execute("SELECT receipt FROM matrix_pending WHERE job_id=?", (str(job),)).fetchone()[
                0
            ]
            is None
        )
    assert confirm_patch(store, "local", UUID(exam["id"]), job, 1).revision == 2


def test_review_pack_hides_ai_answers_in_first_sheet_and_does_not_save(ready):
    client, exam, base, _ = ready
    before = client.get("/api/kv?key=state").json()
    response = client.get(base + "/review-pack")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        first = archive.read("1_TU_GIAI_TRUOC.html").decode()
        second = archive.read("2_DOI_CHIEU_SAU.html").decode()
        report = json.loads(archive.read("bao-cao-kiem.json"))
        assert "Đáp án AI đề xuất" not in first and "Lời giải AI:" not in first
        assert "Đáp án AI đề xuất" in second and "Lời giải AI:" in second
        assert report["candidateHash"] in first and report["candidateHash"] in second
        assert "Ngữ liệu dùng sinh câu" in first and "Câu giả lập 0?" in first
    assert client.get("/api/kv?key=state").json() == before
    audit = client.get(base + "/audit").json()
    assert not audit["traceVerified"]  # Fixture không có HTTP gốc, không giả xác minh.
    assert client.get(base.replace(exam["id"], str(uuid4())) + "/review-pack").status_code == 404


def test_review_pack_rejects_report_from_another_proposal(ready):
    client, _, base, result = ready
    store = client.app.state.store
    key = "matrix-agent-result:" + result["jobId"]
    metadata = store.get(key)["value"]
    store.put(key, {**metadata, "proposalSha256": "0" * 64})
    assert client.get(base + "/review-pack").status_code == 409
