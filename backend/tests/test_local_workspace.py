"""Tích hợp workspace và ma trận với model giả lập tường minh; không là số đo AI thật."""

import importlib.util
import json
import time
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.ai_questions import CheckJob
from mach_backend.local_workspace import create_app
from mach_backend.ollama_protocol import generation_format

SOURCE = "Mai mở cửa thư viện. Nam xếp sách lên kệ. Cô giáo ghi nhận việc giúp đỡ của hai bạn."


class FixtureProvider:
    def __init__(self, fail_first=False):
        self.calls = 0
        self.fail_first = fail_first

    async def __call__(self, job):
        self.calls += 1
        data = job.model_dump(mode="json", include={"jobId", "examId", "baseRevision"})
        if isinstance(job, CheckJob):
            data.update(
                questionId=str(job.question.questionId),
                questionVersion=job.question.questionVersion,
                answer=0,
                explanation="Lời giải test độc lập, không nhận đáp án đề xuất.",
                uncertain=False,
                evidence=[
                    {
                        **job.sources[0].model_dump(mode="json", exclude={"ownerId", "text"}),
                        "quote": "Mai mở cửa thư viện.",
                    }
                ],
            )
            return json.dumps(data, ensure_ascii=False)
        data["questions"] = [
            {
                **slot.model_dump(),
                "stem": f"Câu kiểm thử kỹ thuật {slot.topic} mức {slot.level}?",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "explanation": "Phản hồi soạn sẵn cho test, không dùng trong demo AI thật.",
                "rubric": [{"text": "Chọn đáp án", "pointsQ4": slot.pointsQ4}],
                "evidence": [
                    {
                        **job.sources[0].model_dump(mode="json", exclude={"ownerId", "text"}),
                        "quote": "Mai mở cửa thư viện.",
                    }
                ],
            }
            for i, slot in enumerate(job.slots)
        ]
        if self.fail_first and self.calls == 1:
            data["questions"][0]["rubric"][0]["pointsQ4"] = 1
        return json.dumps(data, ensure_ascii=False)


@pytest.fixture
def workspace(tmp_path):
    provider = FixtureProvider(fail_first=True)
    app = create_app(tmp_path, provider)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        exam = {
            "id": str(uuid4()),
            "revision": 1,
            "subject": "Ngữ văn",
            "grade": "8",
            "questions": [],
            "matrix": [{"topic": "Đọc hiểu", "targets": [1, 1, 0]}],
            "matrixConfirmed": True,
            "history": [],
            "undo": [],
            "redo": [],
            "docs": [],
            "title": "Đề thử",
            "instructions": "Thí sinh chọn đúng một phương án mỗi câu.",
            "layout": {"font": "Arial"},
        }
        assert (
            client.put(
                "/api/kv",
                json={
                    "key": "state",
                    "value": {"exams": [exam], "prefs": [], "current": exam["id"]},
                },
                headers={"If-Match": "0"},
            ).status_code
            == 200
        )
        yield client, exam, provider


def test_workspace_write_openapi_and_invalid_input_keep_saved_revision(workspace):
    client, _, _ = workspace
    path = "/api/kv"
    before = client.get(path, params={"key": "state"}).json()
    schema = client.get("/openapi.json").json()
    put = schema["paths"][path]["put"]
    assert put["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/WorkspaceWrite"
    )
    assert schema["components"]["schemas"]["WorkspaceWrite"]["required"] == ["key", "value"]
    assert any(
        field["in"] == "header" and field["name"] == "if-match" for field in put["parameters"]
    )
    assert schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/WorkspaceSnapshot")

    for body in ("null", "[]", "{", '{"key":"file:test"}'):
        assert (
            client.put(path, content=body, headers={"Content-Type": "application/json"}).status_code
            == 422
        )
    invalid_key = client.put(
        path,
        content='{"key":1e999,"value":{"private":"dữ liệu nháp"}}'.encode(),
        headers={"Content-Type": "application/json"},
    )
    assert invalid_key.status_code == 422
    assert "dữ liệu nháp" not in invalid_key.text
    for revision in (b"\xb2", b"9" * 5000):
        res = client.put(
            path, json={"key": "state", "value": before["value"]}, headers=[(b"If-Match", revision)]
        )
        assert res.status_code == 400
    res = client.put(
        path,
        content='{"key":"state","value":{"exams":[],"prefs":[],"invalid":1e999}}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 400
    assert client.get(path, params={"key": "state"}).json() == before


def test_repeated_save_keeps_workspace_revision_but_stale_write_still_conflicts(workspace):
    client, _, _ = workspace
    before = client.get("/api/kv?key=state").json()
    payload = {"key": "state", "value": before["value"]}
    same = client.put("/api/kv", json=payload, headers={"If-Match": str(before["revision"])})
    assert same.status_code == 200 and same.json()["revision"] == before["revision"]
    stale = client.put("/api/kv", json=payload, headers={"If-Match": str(before["revision"] - 1)})
    assert stale.status_code == 409
    assert client.get("/api/kv?key=state").json() == before


def generate(client, exam):
    prefix = "/api/exams/" + exam["id"]
    approval = client.post(
        prefix + "/matrix/approve",
        json={"baseRevision": 1, "sourceText": SOURCE, "sourceName": "Ngữ liệu test tự viết"},
    )
    assert approval.status_code == 200, approval.text
    result = client.post(
        prefix + "/proposals/generate",
        headers={
            "X-PoC-Config": client.get("/api/status")
            .json()
            .get("config", {})
            .get("fingerprint", "legacy")
        },
        json={
            **approval.json(),
            "requestId": str(uuid4()),
            "consent": True,
            "requireEvidence": True,
        },
    )
    assert result.status_code == 202, result.text
    base = prefix + "/proposals/" + result.json()["jobId"]
    for _ in range(50):
        result = client.get(base + "/status")
        if result.json()["status"] != "running":
            return base, result.json()
        time.sleep(0.02)
    pytest.fail("Fixture chưa xong")


def test_matrix_plan_uses_only_confirmed_exam_preferences(workspace):
    client, exam, _ = workspace
    snapshot = client.get("/api/kv?key=state").json()
    snapshot["value"]["exams"][0]["appliedPrefs"] = [
        {"text": "Dùng đơn vị mét", "confirmedAt": 1234},
        {"text": "Dùng quy tắc còn nháp"},
        {"text": "Mốc xác nhận không hợp lệ", "confirmedAt": True},
    ]
    client.put(
        "/api/kv",
        json={"key": "state", "value": snapshot["value"]},
        headers={"If-Match": str(snapshot["revision"])},
    ).raise_for_status()
    route = f"/api/exams/{exam['id']}/matrix/approve"
    request = {
        "baseRevision": 1,
        "sourceMode": "general",
        "sourceText": "",
        "sourceName": "Dữ liệu tự tạo",
    }
    plan = client.post(route, json=request).raise_for_status().json()["plan"]
    assert "Dùng đơn vị mét" in plan["instructions"]
    assert "quy tắc còn nháp" not in plan["instructions"]
    assert "Mốc xác nhận không hợp lệ" not in plan["instructions"]
    assert "Không bịa trích dẫn" in plan["instructions"]

    snapshot = client.get("/api/kv?key=state").json()
    snapshot["value"]["exams"][0]["generationRequest"] = "Chi tiết. " * 500
    client.put(
        "/api/kv",
        json={"key": "state", "value": snapshot["value"]},
        headers={"If-Match": str(snapshot["revision"])},
    ).raise_for_status()
    plan = client.post(route, json=request).raise_for_status().json()["plan"]
    assert len(plan["instructions"]) == 4000 and "Không bịa trích dẫn" in plan["instructions"]


def test_workspace_generation_retry_review_confirm_reload(workspace):
    client, exam, provider = workspace
    base, result = generate(client, exam)
    assert result["status"] == "complete", result
    assert provider.calls == 5
    before = client.get("/api/kv?key=state").json()["value"]
    assert before["exams"][0]["questions"] == []
    assert client.post(base + "/confirm", json={"baseRevision": 1}).status_code == 409
    for i, question in enumerate(result["proposal"]["questions"]):
        assert (
            client.post(
                base + "/review",
                json={
                    "ordinal": i,
                    "observed": question["level"],
                    "reason": "Nhãn test kỹ thuật",
                    "contentOk": True,
                    "reviewer": "Fixture test",
                },
            ).status_code
            == 200
        )
    receipt = client.post(base + "/confirm", json={"baseRevision": 1})
    assert receipt.status_code == 200, receipt.text
    saved = client.get("/api/kv?key=state").json()["value"]["exams"][0]
    assert saved["revision"] == 2 and len(saved["questions"]) == 2
    assert saved["layout"] == exam["layout"]
    assert saved["undo"][0]["state"]["questions"] == []
    assert len(saved["history"]) == 1
    assert saved["questions"][0]["source"]["quote"] == "Mai mở cửa thư viện."
    assert saved["docs"][0]["text"] == SOURCE
    assert client.post(base + "/confirm", json={"baseRevision": 1}).json() == receipt.json()


def test_conflict_after_preview_keeps_updated_exam(workspace):
    client, exam, _ = workspace
    base, result = generate(client, exam)
    for i, q in enumerate(result["proposal"]["questions"]):
        client.post(
            base + "/review",
            json={
                "ordinal": i,
                "observed": q["level"],
                "reason": "Rà mẫu test",
                "contentOk": True,
                "reviewer": "Fixture test",
            },
        )
    stored = client.get("/api/kv?key=state").json()
    changed = deepcopy(stored["value"])
    changed["exams"][0].update(revision=2, title="Giáo viên đã sửa")
    client.put(
        "/api/kv",
        json={"key": "state", "value": changed},
        headers={"If-Match": str(stored["revision"])},
    )
    assert client.post(base + "/confirm", json={"baseRevision": 1}).status_code == 409
    assert client.get("/api/kv?key=state").json()["value"] == changed


def test_loopback_boundary_and_private_files(workspace):
    client, _, _ = workspace
    assert client.get("/backend/uv.lock").status_code == 404
    assert client.get("/.git/config").status_code == 404
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 403
    assert (
        client.post(
            "/api/assistant/stream", headers={"Origin": "https://evil.example"}, json={}
        ).status_code
        == 403
    )
    assert client.post("/api/assistant/stream", json={}).status_code == 503


def test_mismatch_blocks_save_and_flows_into_next_generation(workspace):
    client, exam, _ = workspace
    base, _ = generate(client, exam)
    assert (
        client.post(
            base + "/review",
            json={
                "ordinal": 1,
                "observed": 0,
                "reason": "Câu chỉ hỏi lại một chi tiết trực tiếp.",
                "contentOk": True,
                "reviewer": "Fixture test",
            },
        ).status_code
        == 200
    )
    assert client.post(base + "/confirm", json={"baseRevision": 1}).status_code == 409
    approval = client.post(
        "/api/exams/" + exam["id"] + "/matrix/approve",
        json={"baseRevision": 1, "sourceText": SOURCE, "sourceName": "Nguồn test"},
    )
    assert approval.status_code == 200
    assert "Câu chỉ hỏi lại một chi tiết trực tiếp." in approval.json()["plan"]["instructions"]
    assert client.get("/api/kv?key=state").json()["value"]["exams"][0]["questions"] == []


def test_model_evidence_choices_keep_source_identity(workspace):
    client, exam, _ = workspace
    base, _ = generate(client, exam)
    row = client.app.state.store.get("matrix-source:" + exam["id"])["value"][0]
    with client.app.state.store.connect() as db:
        payload = db.execute(
            "SELECT payload FROM matrix_pending WHERE job_id=?", (base.split("/")[-1],)
        ).fetchone()[0]
    from mach_backend.patch_confirmation import PendingGeneration

    pending = PendingGeneration.model_validate_json(payload)
    evidence = generation_format(pending.job)["$defs"]["Evidence"]["properties"]
    assert evidence["sourceId"] == {"const": row["sourceId"]}
    assert evidence["sourceVersion"] == {"const": 1}
    assert evidence["quote"]["enum"] == [
        "Mai mở cửa thư viện.",
        "Nam xếp sách lên kệ.",
        "Cô giáo ghi nhận việc giúp đỡ của hai bạn.",
    ]


class AgentModelFixture:
    """Phản hồi giả lập để kiểm API tự sửa; không dùng làm số đo model thật."""

    def __init__(self, *, always_wrong=False):
        self.attempts = 0
        self.always_wrong = always_wrong

    async def __call__(self, purpose, body):
        if purpose == "agent":
            feedback = body["messages"][-1]
            if feedback["role"] == "tool" and json.loads(feedback["content"])["ok"]:
                name, arguments = "finish_exam", {}
            else:
                self.attempts += 1
                name = "check_exam"
                arguments = {
                    "questions": [
                        {
                            "stem": f"Câu giả lập {i}?",
                            "options": ["Mai", "Nam", "Lan", "Hà"],
                            "answer": 1 if self.attempts == 1 or self.always_wrong else 0,
                            "explanation": "Mai mở cửa thư viện.",
                            "evidenceIds": [0],
                        }
                        for i in range(2)
                    ]
                }
            return {"tool_calls": [{"function": {"name": name, "arguments": arguments}}]}
        reviews = [
            (
                {
                    "ordinal": i,
                    "answer": 0,
                    "observedLevel": i,
                    "supported": True,
                    "topicMatches": True,
                    "uncertain": False,
                    "optionVerdicts": ["correct", "incorrect", "incorrect", "incorrect"],
                    "duplicateWith": [],
                    "duplicateUncertain": False,
                    "reason": "Nhãn fixture kiểm tích hợp, không chấm sư phạm.",
                }
                if purpose == "blind_content_check"
                else {"ordinal": i, "consistent": True, "reason": "Fixture nhất quán."}
            )
            for i in range(2)
        ]
        return {"content": json.dumps({"reviews": reviews})}


@pytest.mark.parametrize("always_wrong", [False, True])
def test_agent_handles_repairs_before_teacher_final_confirmation(workspace, tmp_path, always_wrong):
    original, exam, _ = workspace
    model = AgentModelFixture(always_wrong=always_wrong)
    directory = tmp_path / "agent"
    with TestClient(
        create_app(directory, agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        state = original.get("/api/kv?key=state").json()["value"]
        assert client.put("/api/kv", json={"key": "state", "value": state}).status_code == 200
        base, result = generate(client, exam)
        assert model.attempts > 2 if always_wrong else model.attempts == 2
        assert client.get("/api/kv?key=state").json()["value"] == state
        trace = client.get(base + "/trace").json()
        checks = [t for t in trace if t.get("event") == "generation_result"]
        assert checks[0]["ok"] is False
        assert checks[0]["errors"][0]["code"] == "answer_disagreement"
        if always_wrong:
            assert result["status"] == "failed" and result["errorCode"] == "call_budget"
            assert not result.get("proposal")
            return
        assert result["status"] == "complete"
        assert checks[1]["ok"] is True
        report = client.get(base + "/report").json()
        assert report["status"] == "complete"
        assert report["summary"]["modelCalls"] == 7
        assert len(report["checks"]) == 10
        assert all(
            r["status"] == "PASS" and r["candidateHash"] == report["candidateHash"]
            for r in report["checks"]
        )
        assert client.post(base + "/confirm", json={"baseRevision": 1}).status_code == 400
        # Không cần người dùng tự xử lý từng lỗi giữa các lần model sinh.
        response = client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        )
        assert response.status_code == 200, response.text
        saved = client.get("/api/kv?key=state").json()["value"]["exams"][0]
        assert saved["revision"] == 2 and len(saved["questions"]) == 2
        assert saved["undo"][0]["state"]["questions"] == []
        assert saved["quote"]["text"] == SOURCE
        assert saved["instructions"] == exam["instructions"]
        assert len(list((directory / "agent-logs").glob("*/events.jsonl"))) == 1


def test_agent_preview_survives_app_restart(workspace, tmp_path):
    original, exam, _ = workspace
    directory = tmp_path / "restart"
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(directory, agent_call=AgentModelFixture()),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, result = generate(client, exam)
        assert result["status"] == "complete"
    with TestClient(create_app(directory), headers={"Origin": "http://testserver"}) as reopened:
        latest = reopened.get(f"/api/exams/{exam['id']}/proposals/latest").json()
        assert latest["status"] == "complete" and not latest["saved"]
        assert latest["proposal"] == result["proposal"]
        assert reopened.get(base + "/trace").status_code == 200
        assert reopened.get(base + "/status").json()["status"] == "complete"
        result = reopened.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        )
        assert result.status_code == 200, result.text
        assert reopened.get(base + "/status").json()["saved"]
        assert reopened.get("/api/kv?key=state").json()["value"]["exams"][0]["revision"] == 2


def test_generator_and_reviewer_route_to_distinct_models_with_one_budget(
    workspace, tmp_path, monkeypatch
):
    original, exam, _ = workspace
    fixture = AgentModelFixture()
    calls = []
    budgets = []
    pools = []

    class FakeGemini:
        def __init__(self, _client, _key, _log, *, model, budget, key_pool, auto_fallback):
            self.model, self.budget = model, budget
            budgets.append(budget)
            pools.append(key_pool)

        async def __call__(self, purpose, body):
            self.budget.spend()
            calls.append((purpose, self.model))
            return await fixture(purpose, body)

    monkeypatch.setattr("mach_backend.workspace_agent.GeminiModel", FakeGemini)
    with TestClient(
        create_app(tmp_path / "roles"), headers={"Origin": "http://testserver"}
    ) as client:
        state = original.get("/api/kv?key=state").json()["value"]
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        client.post(
            "/api/config",
            json={
                "routes": {"generate": "gemini", "check": "gemini"},
                "gemini": {
                    "key": "fake-key-only-in-test",
                    "freeTierConfirmed": True,
                    "model": "gemini-3.8-flash",
                    "checkModel": "gemini-3.6-flash",
                },
                "runBudget": {"maxModelCalls": 12, "timeoutSeconds": 60},
            },
        ).raise_for_status()
        base, result = generate(client, exam)
        assert result["status"] == "complete"
        assert budgets[0] is budgets[1] and budgets[0].calls == 7
        assert pools[0] is pools[1]
        assert all(
            model == ("gemini-3.8-flash" if purpose == "agent" else "gemini-3.6-flash")
            for purpose, model in calls
        )
        assert (
            client.get(base + "/report").json()["summary"]["reviewer"]["model"]
            == "gemini-3.6-flash"
        )


def test_bio_sample_uses_full_source_and_keeps_reference_answers_out(workspace):
    client, _, _ = workspace
    sample = client.get("/api/poc/sample").json()
    assert sample["subject"] == "Sinh học"
    assert [r["targets"] for r in sample["matrix"]] == [[1, 1, 0], [1, 0, 1]]
    assert all(s in sample["text"] for s in ("S1.", "S2.", "S3.", "cùng nhiệt độ"))
    assert "Đáp án" not in sample["text"]
    assert client.get("/api/poc/sample?dataset=../.runtime").status_code == 400


@pytest.mark.parametrize(
    "case,code",
    [
        ("missing_question", "invalid_plan"),
        ("multiple_correct", "option_verdicts_failed"),
        ("unsupported", "unsupported_answer"),
        ("wrong_level", "level_disagreement"),
        ("duplicate", "semantic_duplicate"),
    ],
)
def test_demo_cases_detect_feedback_recheck_and_reach_final(workspace, tmp_path, case, code):
    script = Path(__file__).resolve().parents[2] / "scripts/chay-fixture-poc.py"
    spec = importlib.util.spec_from_file_location("poc_cases", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(tmp_path / case, agent_call=module.FixtureCase(case)),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, result = generate(client, exam)
        assert result["status"] == "complete"
        checks = [
            e for e in client.get(base + "/trace").json() if e.get("event") == "generation_result"
        ]
        assert code in [e["code"] for e in checks[0]["errors"]]
        assert not checks[0]["ok"] and checks[-1]["ok"]
        assert client.get("/api/kv?key=state").json()["value"] == state


def test_mismatched_check_report_cannot_be_confirmed(workspace, tmp_path):
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(tmp_path / "bound", agent_call=AgentModelFixture()),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, _ = generate(client, exam)
        key = "matrix-agent-result:" + base.rsplit("/", 1)[-1]
        stored = client.app.state.store.get(key)["value"]
        stored["report"]["checks"][0]["candidateHash"] = "a" * 64
        client.app.state.store.put(key, stored)
        result = client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        )
        assert result.status_code == 409
        assert result.json()["code"] == "needs_review"
        assert client.get("/api/kv?key=state").json()["value"] == state


def test_changed_connection_cannot_send_source_with_old_consent(tmp_path):
    model = AgentModelFixture()
    with TestClient(
        create_app(tmp_path, agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        stamp = client.get("/api/config").json()["fingerprint"]
        client.post(
            "/api/config", json={"ollama": {"model": "other-local-model"}}
        ).raise_for_status()
        result = client.post(
            "/api/exams/" + str(uuid4()) + "/proposals/generate",
            headers={"X-PoC-Config": stamp},
            json={},
        )
        assert result.status_code == 409 and result.json()["code"] == "config_changed"
        assert model.attempts == 0


def test_config_change_waits_for_active_task(workspace, tmp_path):
    import asyncio
    from threading import Event

    started = Event()

    async def slow(_purpose, _body):
        started.set()
        await asyncio.sleep(10)
        return {}

    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(tmp_path / "active", agent_call=slow), headers={"Origin": "http://testserver"}
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        approval = client.post(
            "/api/exams/" + exam["id"] + "/matrix/approve",
            json={"baseRevision": 1, "sourceText": SOURCE, "sourceName": "Fixture"},
        ).json()
        config = client.get("/api/config").json()
        prefix = "/api/exams/" + exam["id"] + "/proposals/"
        submitted = client.post(
            prefix + "generate",
            json={**approval, "requestId": str(uuid4()), "consent": True, "requireEvidence": True},
            headers={"X-PoC-Config": config["fingerprint"]},
        )
        assert submitted.status_code == 202
        assert client.get("/api/status").json()["aiBusy"]
        rejected = client.post("/api/config", json={"runBudget": {"maxModelCalls": 4}})
        assert rejected.status_code == 409 and rejected.json()["code"] == "job_limit"
        assert client.get("/api/config").json() == config
        assert started.wait(1)
        base = prefix + submitted.json()["jobId"]
        cancelled = client.post(base + "/cancel", json={}).raise_for_status().json()
        assert cancelled["status"] == "cancelled" and cancelled["errorCode"] is None
        for _ in range(50):
            trace = client.get(base + "/trace").json()
            if trace[-1]["event"] == "run_end":
                break
            time.sleep(0.02)
        assert trace[-1]["event"] == "run_end"
        assert trace[-1]["status"] == "cancelled" and "errorCode" not in trace[-1]
        summary_path = (
            tmp_path / "active" / "agent-logs" / submitted.json()["jobId"] / "result.json"
        )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["status"] == "cancelled" and "errorCode" not in summary
    with TestClient(create_app(tmp_path / "active")) as reopened:
        assert reopened.get(base + "/status").json()["status"] == "cancelled"
        assert reopened.get(base + "/trace").json()[-1]["status"] == "cancelled"


@pytest.mark.parametrize("runner_timeout", [False, True])
def test_timeout_keeps_partial_reports_unknown_and_draft_unchanged(
    workspace, tmp_path, runner_timeout
):
    import asyncio

    import httpx

    model = AgentModelFixture()

    async def call(purpose, body):
        if purpose == "explanation_check":
            if runner_timeout:
                await asyncio.sleep(10)
            raise httpx.ReadTimeout("Fixture dịch vụ quá thời gian.")
        return await model(purpose, body)

    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    with TestClient(
        create_app(tmp_path / "timeout", agent_call=call), headers={"Origin": "http://testserver"}
    ) as client:
        if runner_timeout:
            client.app.state.runner._timeout_seconds = 0.5
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, result = generate(client, exam)
        expected = "timeout" if runner_timeout else "provider_timeout"
        assert result["status"] == "failed" and result["errorCode"] == expected
        report = client.get(base + "/report").json()
        assert len(report["checks"]) == 10 and report["candidateHash"]
        checks = {r["toolName"]: r["status"] for r in report["checks"]}
        assert checks["validate_schema"] == "PASS"
        assert checks["check_explanation"] == checks["aggregate_checks"] == "UNKNOWN"
        assert client.get("/api/kv?key=state").json()["value"] == state
        trace = client.get(base + "/trace").json()
        assert trace[-1]["event"] == "run_end"
        assert trace[-1]["status"] == "failed" and trace[-1]["errorCode"] == expected
        summary_path = tmp_path / "timeout" / "agent-logs" / result["jobId"] / "result.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["status"] == "failed" and summary["errorCode"] == expected
    with TestClient(create_app(tmp_path / "timeout")) as reopened:
        recovered = reopened.get(base + "/status").json()
        assert recovered["sequence"] == 2 and recovered["status"] == "failed"
        assert recovered["errorCode"] == expected and recovered["proposal"] is None
        assert reopened.get("/api/kv?key=state").json()["value"] == state


@pytest.mark.parametrize(
    "path", ["/", "/bootstrap.js", "/app.js", "/subject-profiles.js", "/assets/usability.js"]
)
def test_mutable_ui_files_do_not_mix_old_cached_modules(tmp_path, path):
    with TestClient(create_app(tmp_path)) as client:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


def test_entry_versions_transitive_modules_without_changing_source(tmp_path):
    from mach_backend.local_workspace import ui_entry

    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(
        '<script type="module" src="bootstrap.js"></script>', encoding="utf-8"
    )
    for name, value in [
        ("bootstrap.js", "import('./app.js')"),
        ("app.js", "import './subject-profiles.js'"),
        ("subject-profiles.js", "export const first=1;"),
    ]:
        (tmp_path / name).write_text(value, encoding="utf-8")

    def mapping(html):
        return json.loads(html.split('<script type="importmap">')[1].split("</script>")[0])[
            "imports"
        ]

    first = ui_entry(tmp_path)
    before = mapping(first)
    assert "/bootstrap.js?v=" in first and set(before) == {
        "/app.js",
        "/bootstrap.js",
        "/subject-profiles.js",
    }
    (tmp_path / "subject-profiles.js").write_text(
        "export const first=1;export const added=2;", encoding="utf-8"
    )
    second = mapping(ui_entry(tmp_path))
    assert before["/subject-profiles.js"] != second["/subject-profiles.js"]
    assert before["/app.js"] == second["/app.js"]
    assert (tmp_path / "app.js").read_text(encoding="utf-8") == "import './subject-profiles.js'"
