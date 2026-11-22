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
from mach_backend.local_workspace import create_app, plan_from_exam
from mach_backend.matrix_agent import run_matrix_agent


def test_generation_plan_uses_only_confirmed_preferences_and_latest_request():
    exam = {
        "subject": "Toán",
        "grade": "5",
        "matrixConfirmed": True,
        "matrix": [{"topic": "Phân số", "targets": [2, 1, 1, 0]}],
        "generationRequest": "Bản đã sửa: tập trung vào phân số.",
        "appliedPrefs": [
            {"text": "Tránh phủ định kép", "confirmedAt": 1},
            {"text": "Quy tắc vẫn là bản nháp"},
        ],
    }
    plan = plan_from_exam(exam, general=True)
    assert "Bản đã sửa: tập trung vào phân số." in plan.instructions
    assert "Tránh phủ định kép" in plan.instructions
    assert "Quy tắc vẫn là bản nháp" not in plan.instructions
    assert len(plan.slots) == 4
    assert sum(slot.pointsQ4 for slot in plan.slots) == 40


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
    ("instructions", "with_source"),
    [
        ("Đọc kỹ và làm theo yêu cầu của từng câu.", False),
        ("Chọn một phương án đúng cho mỗi câu hỏi.", False),
        ("Thầy cô tự ghi: làm câu 1 trước.", False),
        ("Đọc kỹ và làm theo yêu cầu của từng câu.", True),
    ],
)
def test_generation_preview_confirm_preserves_custom_instructions(
    workspace, mixed, tmp_path, instructions, with_source
):
    original, exam, _ = workspace
    job, arguments = mixed
    job = job.model_copy(
        update={"slots": (*job.slots[:3], job.slots[3].model_copy(update={"level": 3}))}
    )
    if with_source:
        slots = [slot.model_copy(update={"pointsQ4": 8}) for slot in job.slots]
        slots.extend(
            job.slots[i].model_copy(update={"topic": "Đọc chi tiết", "pointsQ4": 4}) for i in (0, 1)
        )
        for i in (0, 1):
            extra = copy.deepcopy(arguments["questions"][i])
            extra["stem"] = f"Câu đọc chi tiết {i + 5}?"
            arguments["questions"].append(extra)
        for slot, question in zip(slots, arguments["questions"], strict=True):
            question["rubric"][0]["pointsQ4"] = slot.pointsQ4
        job = job.model_copy(update={"slots": tuple(slots)})
    else:
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
            "pointsQ4": slot.pointsQ4,
        }
        for slot in job.slots
    ]
    model = MixedModel(job, arguments)
    with TestClient(
        create_app(tmp_path / "general", agent_call=model),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        prefix = "/api/exams/" + exam["id"]
        approval = client.post(
            prefix + "/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": job.sources[0].text if with_source else "",
                "sourceName": "Ngữ liệu tự viết" if with_source else "Kiến thức chung",
                "sourceMode": "provided" if with_source else "general",
            },
        )
        approval.raise_for_status()
        assert len(approval.json()["sources"]) == int(with_source)
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
                "requireEvidence": with_source,
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
        assert model.attempts == 2
        if with_source:
            trace = client.get(base + "/trace").json()
            rounds = [row["ok"] for row in trace if row["event"] == "generation_result"]
            assert rounds == [False, True]
            source_id = approval.json()["sources"][0]["sourceId"]
            for question in result["proposal"]["questions"]:
                assert question["evidence"][0]["sourceId"] == source_id
        assert client.get("/api/kv?key=state").json()["value"] == state
        client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        ).raise_for_status()
        saved = client.get("/api/kv?key=state").json()["value"]["exams"][0]
        assert saved["id"] == exam["id"] and saved["revision"] == 2
        assert saved["questions"][3]["level"] == 3
        assert len(saved["questions"]) == len(job.slots)
        assert sum(question["points"] for question in saved["questions"]) == 10
        if instructions.startswith("Thầy"):
            assert saved["instructions"] == instructions
        else:
            assert all(
                label in saved["instructions"]
                for label in ("nhiều lựa chọn", "đúng/sai", "trả lời ngắn", "tự luận")
            )
        assert len(saved["docs"]) == int(with_source)


def test_reverse_matrix_endpoint_preserves_mixed_types_points_and_unique_choice_slots(tmp_path):
    exam_id = str(uuid4())
    exam = {
        "id": exam_id,
        "revision": 2,
        "title": "Đề Tin học 2 định hướng",
        "subject": "Tin học",
        "grade": "12",
        "minutes": 50,
        "docs": [],
        "chat": [],
        "history": [],
        "undo": [],
        "redo": [],
        "matrix": [],
        "appliedPrefs": [],
        "quote": {"text": "", "versions": []},
        "questions": [
            {"id": str(uuid4()), "v": 1, "type": "mcq", "topic": "Mạng", "level": 0, "points": 0.2},
            {
                "id": str(uuid4()),
                "v": 1,
                "type": "truefalse",
                "topic": "CSDL",
                "level": 1,
                "points": 1.6,
            },
            {
                "id": str(uuid4()),
                "v": 1,
                "type": "short",
                "topic": "SQL",
                "level": 2,
                "points": 0.2,
            },
            {
                "id": str(uuid4()),
                "v": 1,
                "type": "essay",
                "topic": "Thuật toán",
                "level": 2,
                "points": 2.0,
                "choiceGroup": "KHMT",
            },
            {
                "id": str(uuid4()),
                "v": 1,
                "type": "essay",
                "topic": "Ứng dụng",
                "level": 2,
                "points": 2.0,
                "choiceGroup": "THUD",
            },
            {"id": str(uuid4()), "v": 1, "type": "mcq", "topic": "", "level": 0, "points": None},
        ],
    }
    state = {"exams": [exam], "prefs": [], "current": exam_id}
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        stale = client.post(f"/api/exams/{exam_id}/reverse-matrix", json={"baseRevision": 1})
        assert stale.status_code == 409
        res = client.post(f"/api/exams/{exam_id}/reverse-matrix", json={"baseRevision": 2})
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["sentToAI"] is False
        slot_ids = [s["slotId"] for s in data["slots"]]
        assert len(set(slot_ids)) == len(slot_ids) == 6
        assert [s["type"] for s in data["slots"][:5]] == [
            "mcq",
            "truefalse",
            "short",
            "essay",
            "essay",
        ]
        assert data["missingPointsOrdinals"] == [6]
        assert data["totalPoints"] == pytest.approx(4.0)
        assert any("chưa có điểm" in w for w in data["warnings"])
