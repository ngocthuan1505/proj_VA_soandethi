"""Yêu cầu thông thường không bắt giáo viên tự điền ma trận; fixture không là AI thật."""

import asyncio
import copy
import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_local_workspace import workspace as workspace
from test_mixed_questions import MixedModel
from test_mixed_questions import mixed as mixed

from mach_backend.ai_contract import AIError
from mach_backend.exam_planning import PlanRequest, propose_structure
from mach_backend.local_workspace import create_app
from mach_backend.matrix_agent import run_matrix_agent


def test_teacher_can_leave_count_minutes_and_question_types_to_assistant():
    request = PlanRequest(
        request="Tạo1đề Toán lớp5 cuối kì",
        subject="Toán",
        grade=5,
        term="cuối kì (chưa nêu học kì)",
        consent=True,
    )
    calls = []

    async def model(purpose, body):
        calls.append(body)
        assert body["format"]["properties"]["slots"]["minItems"] == 4
        assert "minutes" in body["format"]["required"]
        return {
            "content": json.dumps(
                {
                    "slots": [
                        {"topic": "Phân số", "type": "mcq" if i < 6 else "essay", "level": i % 3}
                        for i in range(10)
                    ],
                    "minutes": 40,
                    "notes": "Chưa nêu học kì/bộ sách, cần rà phạm vi.",
                }
            )
        }

    result = asyncio.run(propose_structure(request, model))
    assert len(calls) == 1 and result["count"] == 10
    assert result["metadata"]["grade"] == "5" and result["metadata"]["minutes"] == 40
    assert result["suggested"] == {"count": True, "minutes": True, "types": True}
    assert {r["type"] for r in result["matrix"]} == {"mcq", "essay"}
    assert result["requiresConfirmation"]


@pytest.mark.parametrize(
    "count,minutes,kind,match",
    [
        (1, 40, "essay", "đủ một đề"),
        (8, None, "essay", "thời gian"),
        (8, 40, "truefalse", "dạng câu"),
    ],
)
def test_auto_plan_rejects_one_question_missing_duration_and_ignored_types(
    count, minutes, kind, match
):
    request = PlanRequest(
        request="Tạo đề Toán lớp5 chỉ tự luận",
        subject="Toán",
        grade=5,
        term="cuối học kì I",
        consent=True,
    )

    async def model(*_):
        return {
            "content": json.dumps(
                {
                    "slots": [{"topic": "Phân số", "type": kind, "level": 1}] * count,
                    "minutes": minutes,
                    "notes": "Gợi ý.",
                }
            )
        }

    with pytest.raises(AIError, match=match):
        asyncio.run(propose_structure(request, model))


def test_natural_request_proposes_structure_once_with_consent_and_exact_count():
    request = PlanRequest(
        request="Tạo đề Toán lớp 12 cuối kì",
        subject="Toán",
        grade=12,
        term="cuối học kì I",
        count=5,
        minutes=90,
        consent=True,
    )
    calls = []

    async def model(purpose, body):
        calls.append((purpose, body))
        return {
            "content": json.dumps(
                {
                    "slots": [
                        {"topic": "Ứng dụng đạo hàm", "type": "essay", "level": level}
                        for level in [0, 1, 1, 2, 3]
                    ],
                    "notes": "Gợi ý cần xem lại phạm vi.",
                }
            )
        }

    result = asyncio.run(propose_structure(request, model))
    assert result["count"] == 5 and result["requiresConfirmation"]
    assert result["metadata"]["grade"] == "12" and result["metadata"]["minutes"] == 90
    assert len(calls) == 1 and calls[0][0] == "exam_planning"
    with pytest.raises(AIError, match="Cho phép"):
        asyncio.run(propose_structure(request.model_copy(update={"consent": False}), model))
    assert len(calls) == 1
    with pytest.raises(AIError, match="số câu"):
        asyncio.run(propose_structure(request.model_copy(update={"count": 6}), model))


def test_planner_uses_selected_local_provider_without_a_gemini_key(tmp_path, monkeypatch):
    calls = []

    async def local(model, purpose, body):
        calls.append((model.model, purpose, body))
        assert model.budget.max_calls == 1
        return {
            "content": json.dumps(
                {
                    "slots": [{"topic": "Đạo hàm", "type": "essay", "level": 3}],
                    "notes": "Gợi ý local.",
                }
            )
        }

    async def forbidden(*_args):
        pytest.fail("Đang chọn Ollama, không được gửi Gemini.")

    monkeypatch.setattr("mach_backend.local_workspace.LocalModel.__call__", local)
    monkeypatch.setattr("mach_backend.local_workspace.GeminiModel.__call__", forbidden)
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/ai/exam-plan",
            json={
                "request": "Soạn một câu tự luận",
                "subject": "Toán",
                "grade": 12,
                "term": "cuối học kì I",
                "count": 1,
                "minutes": 45,
                "consent": True,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["count"] == 1 and len(calls) == 1
        assert response.json()["matrix"][0]["targets"] == [0, 0, 0, 1]
        assert not client.get("/api/status").json()["aiBusy"]


def test_general_knowledge_four_levels_runs_same_checks_without_fabricated_evidence(mixed):
    job, arguments = mixed
    job = job.model_copy(update={"sources": (), "requireEvidence": False})
    job = job.model_copy(
        update={"slots": (*job.slots[:3], job.slots[3].model_copy(update={"level": 3}))}
    )
    for question in arguments["questions"]:
        question["evidenceIds"] = []
    model = MixedModel(job, arguments)
    result = asyncio.run(run_matrix_agent(job, model, lambda *_a, **_kw: None))
    assert result["status"] == "ready_for_teacher_review"
    assert all(q["evidence"] == [] for q in result["proposal"]["questions"])
    assert result["proposal"]["questions"][3]["level"] == 3
    blind = next(body for purpose, body in model.calls if purpose == "blind_content_check")
    assert "Không có tài liệu nguồn" in blind["messages"][0]["content"]
    assert json.loads(blind["messages"][1]["content"])["sources"] == []
    required = job.model_copy(update={"requireEvidence": True})
    with pytest.raises(AIError):
        asyncio.run(run_matrix_agent(required, model, lambda *_a, **_kw: None))


@pytest.mark.parametrize(
    "instructions", ["Chọn một phương án đúng cho mỗi câu hỏi.", "Thầy cô tự ghi: làm câu 1 trước."]
)
def test_general_generation_preview_confirm_preserves_custom_instructions(
    workspace, mixed, tmp_path, instructions
):
    original, exam, _ = workspace
    job, arguments = mixed
    job = job.model_copy(
        update={"slots": (*job.slots[:3], job.slots[3].model_copy(update={"level": 3}))}
    )
    for question in arguments["questions"]:
        question["evidenceIds"] = []
    state = copy.deepcopy(original.get("/api/kv?key=state").json()["value"])
    exam = state["exams"][0]
    exam["instructions"] = instructions
    exam["matrix"] = [
        {
            "topic": slot.topic,
            "type": slot.type,
            "targets": [int(level == slot.level) for level in range(4)],
            "pointsQ4": 10,
        }
        for slot in job.slots
    ]
    with TestClient(
        create_app(tmp_path / "general", agent_call=MixedModel(job, arguments)),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        prefix = "/api/exams/" + exam["id"]
        approval = client.post(
            prefix + "/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Kiến thức chung",
                "sourceMode": "general",
            },
        )
        approval.raise_for_status()
        assert approval.json()["sources"] == []
        response = client.post(
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
                "requireEvidence": False,
            },
        )
        assert response.status_code == 202, response.text
        base = prefix + "/proposals/" + response.json()["jobId"]
        for _ in range(100):
            result = client.get(base + "/status").json()
            if result["status"] != "running":
                break
            time.sleep(0.02)
        assert result["status"] == "complete", result
        assert client.get("/api/kv?key=state").json()["value"] == state
        client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        ).raise_for_status()
        saved = client.get("/api/kv?key=state").json()["value"]["exams"][0]
        assert saved["id"] == exam["id"] and saved["revision"] == 2
        assert saved["questions"][3]["level"] == 3
        assert (
            saved["instructions"] == instructions
            if instructions.startswith("Thầy")
            else "tự luận" in saved["instructions"]
        )
        assert saved["docs"] == []
