"""Hồi quy hai lỗi P1 sau đối chiếu hợp nhất 9ee5069 và 687c5f9."""

from __future__ import annotations

import base64
import io
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import (
    GeneratedQuestion,
    GenerateJob,
    points_p100,
    validate_generation_plan,
)
from mach_backend.ai_service import OllamaProvider, propose_exam
from mach_backend.exam_spec_export import (
    build_matrix_and_specification,
    validate_and_normalize_answer_key,
)
from mach_backend.export_preflight import audit_export_preflight
from mach_backend.local_documents import chrome_path, export_file
from mach_backend.local_workspace import create_app, plan_from_exam
from mach_backend.matrix_import import checked_matrix


def test_confirmed_decimal_matrix_keeps_preview_scores(tmp_path):
    rows = [
        {"topic": "A", "type": "essay", "targets": [1, 0, 0], "points": 0.4},
        {
            "topic": "B",
            "type": "essay",
            "targets": [1, 0, 0],
            "pointsByLevel": [9.6, None, None, None],
        },
    ]
    preview = checked_matrix({"matrix": rows, "notes": ""})
    exam_id = str(uuid4())
    exam = {
        "id": exam_id,
        "revision": 1,
        "subject": "Toán",
        "title": "QA",
        "docs": [],
        "chat": [],
        "history": [],
        "undo": [],
        "redo": [],
        "appliedPrefs": [],
        "quote": {"text": "", "versions": []},
        "grade": "5",
        "questions": [],
        "matrixConfirmed": True,
        "matrix": preview["matrix"],
    }
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": [], "current": exam_id}},
        ).raise_for_status()
        route = f"/api/exams/{exam_id}/matrix/approve"
        result = client.post(
            route,
            json={"baseRevision": 1, "sourceMode": "general", "sourceText": "", "sourceName": "QA"},
        )
        assert result.status_code == 200, result.text
        assigned = [
            slot["points"] if slot.get("points") is not None else slot["pointsQ4"] / 4
            for slot in result.json()["plan"]["slots"]
        ]
        assert assigned == [0.4, 9.6]


def test_two_branch_choice_group_matrix_passes_preview_plan_and_approve(tmp_path):
    rows = [
        {"topic": "Chung", "type": "mcq", "targets": [5, 0, 0, 0], "points": 0.2},
        {"topic": "Phần riêng chung", "type": "essay", "targets": [0, 5, 0, 0], "points": 0.4},
        {"topic": "Tổng hợp", "type": "essay", "targets": [0, 0, 2, 0], "points": 2.0},
        {
            "topic": "Chuyên đề KHMT",
            "type": "mcq",
            "targets": [10, 0, 0, 0],
            "points": 0.1,
            "choiceGroup": "KHMT",
        },
        {
            "topic": "Bài tập KHMT",
            "type": "essay",
            "targets": [0, 2, 0, 0],
            "pointsQ4": 4,
            "choiceGroup": "KHMT",
        },
        {
            "topic": "Chuyên đề THUD",
            "type": "mcq",
            "targets": [10, 0, 0, 0],
            "points": 0.1,
            "choiceGroup": "THUD",
        },
        {
            "topic": "Bài tập THUD",
            "type": "essay",
            "targets": [0, 2, 0, 0],
            "pointsQ4": 4,
            "choiceGroup": "THUD",
        },
    ]
    preview = checked_matrix({"matrix": rows, "notes": ""})
    assert preview["count"] == 24
    exam_id = str(uuid4())
    exam = {
        "id": exam_id,
        "revision": 1,
        "subject": "Tin học",
        "title": "Đề 2 định hướng",
        "docs": [],
        "chat": [],
        "history": [],
        "undo": [],
        "redo": [],
        "appliedPrefs": [],
        "quote": {"text": "", "versions": []},
        "grade": "12",
        "questions": [],
        "matrixConfirmed": True,
        "matrix": preview["matrix"],
    }
    plan = plan_from_exam(exam, general=True)
    assert len(plan.slots) == 36
    assert {slot.choiceGroup for slot in plan.slots if slot.choiceGroup} == {"KHMT", "THUD"}

    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": [], "current": exam_id}},
        ).raise_for_status()
        res = client.post(
            f"/api/exams/{exam_id}/matrix/approve",
            json={"baseRevision": 1, "sourceMode": "general", "sourceText": "", "sourceName": "QA"},
        )
        assert res.status_code == 200, res.text
        plan_json = res.json()["plan"]
        assert len(plan_json["slots"]) == 36
        job = GenerateJob(
            jobId=uuid4(),
            examId=uuid4(),
            baseRevision=1,
            ownerId="local",
            requireEvidence=False,
            **plan_json,
            sources=(),
        )
        validate_generation_plan(job)
        common_p100 = sum(points_p100(s) for s in job.slots if not s.choiceGroup)
        khmt_p100 = sum(points_p100(s) for s in job.slots if s.choiceGroup == "KHMT")
        thud_p100 = sum(points_p100(s) for s in job.slots if s.choiceGroup == "THUD")
        assert common_p100 == 700
        assert common_p100 + khmt_p100 == 1000
        assert common_p100 + thud_p100 == 1000


def test_student_pdf_keeps_table_image_without_teacher_explanation(tmp_path):
    try:
        browser = chrome_path()
    except AIError:
        pytest.skip("Chromium unavailable")
    if not browser:
        pytest.skip("Chromium unavailable")
    data = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(data, "PNG")
    image = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
    exam = {
        "title": "QA",
        "questions": [
            {
                "stem": "Read the image.",
                "options": ["A", "B"],
                "answer": 0,
                "explanation": "QA_ANSWER_ONLY",
                "tables": [{"rows": [[{"data": image, "caption": "QA Table Image"}]]}],
            }
        ],
    }
    result = export_file(
        {"type": "exam", "format": "pdf", "teacher": False, "exam": exam},
        tmp_path,
        "http://localhost",
    )
    pages = PdfReader(tmp_path / result["filename"]).pages
    assert sum(len(page.images) for page in pages) == 1
    text = "".join((page.extract_text() or "") for page in pages)
    assert "QA Table Image" in text
    assert "base64" not in text
    assert "QA_ANSWER_ONLY" not in text


def test_generated_fractional_scores_export_without_rounding_and_keep_q4_compatibility():
    q4_question = GeneratedQuestion(
        type="mcq",
        topic="Q4 chuẩn",
        level=0,
        pointsQ4=2,
        stem="Câu Q4?",
        options=("A", "B", "C", "D"),
        answer=0,
        explanation="Giải thích Q4.",
        rubric=({"text": "Chọn đúng phương án.", "pointsQ4": 2},),
        evidence=(),
    ).model_dump(mode="json")
    assert "points" not in q4_question
    assert "choiceGroup" not in q4_question
    assert q4_question["pointsQ4"] == 2

    questions = []
    for topic, points_val, rubric in (("A", 0.4, [0.2, 0.2]), ("B", 9.6, [9.6])):
        question = GeneratedQuestion(
            type="essay",
            topic=topic,
            level=0,
            points=points_val,
            stem=f"Topic {topic}",
            options=(),
            answer=None,
            explanation="Sample solution.",
            rubric=tuple({"text": "Sample step.", "points": score} for score in rubric),
            evidence=(),
        ).model_dump(mode="json")
        assert "pointsQ4" not in question
        questions.append(question)

    exam = {"title": "QA", "questions": questions}
    matrix = build_matrix_and_specification(exam)
    assert matrix["total_points"] == 10.0
    assert matrix["total_points_q4"] == 40
    assert [row["total_points"] for row in matrix["rows"]] == [0.4, 9.6]
    assert [row["total_points_q4"] / 4 for row in matrix["rows"]] == [0.4, 9.6]
    assert round(sum(row["percentage"] for row in matrix["rows"]), 2) == 100.0

    key_data = validate_and_normalize_answer_key(exam, teacher=True)
    assert key_data["total_points"] == 10.0
    assert key_data["total_points_q4"] == 40
    assert [item["points"] for item in key_data["essay_rubrics"]] == [0.4, 9.6]

    preflight = audit_export_preflight(exam)
    assert preflight["ready"] is True, preflight["blockingIssues"]
    assert preflight["summary"]["totalPoints"] == 10.0
    assert preflight["summary"]["totalPointsQ4"] == 40


def test_matrix_import_rejects_more_than_two_decimal_places():
    with pytest.raises(AIError):
        checked_matrix(
            {
                "matrix": [
                    {"topic": "A", "type": "essay", "targets": [1, 0, 0], "points": 0.125},
                    {"topic": "B", "type": "essay", "targets": [1, 0, 0], "points": 9.875},
                ],
                "notes": "",
            }
        )


def test_ollama_provider_supports_decimal_slots_in_prompt_and_validation():
    import asyncio

    job = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        requireEvidence=False,
        subject="Toán",
        grade="9",
        slots=(
            {"type": "mcq", "topic": "A", "level": 0, "points": 0.4},
            {"type": "essay", "topic": "B", "level": 2, "points": 9.6},
        ),
        sources=(),
    )
    reply = {
        "jobId": str(job.jobId),
        "examId": str(job.examId),
        "baseRevision": 1,
        "questions": [
            {
                "type": "mcq",
                "topic": "A",
                "level": 0,
                "points": 0.4,
                "stem": "Tính 1 + 1?",
                "options": ["1", "2", "3", "4"],
                "answer": 1,
                "explanation": "1 + 1 = 2.",
                "rubric": [{"text": "Chọn đúng phương án.", "points": 0.4}],
                "evidence": [],
            },
            {
                "type": "essay",
                "topic": "B",
                "level": 2,
                "points": 9.6,
                "stem": "Giải phương trình x + 2 = 5.",
                "options": [],
                "answer": None,
                "explanation": "x = 3.",
                "rubric": [{"text": "Tìm đúng x = 3.", "points": 9.6}],
                "evidence": [],
            },
        ],
    }

    captured: list[dict] = []

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(reply)},
            },
        )

    async def current(_job):
        return True

    provider = OllamaProvider("mo-hinh-fixture", transport=httpx.MockTransport(respond))
    proposal = asyncio.run(propose_exam(job, provider, current, timeout_seconds=5))
    assert [points_p100(q) for q in proposal.questions] == [40, 960]
    assert "rubric[].points" in captured[0]["messages"][0]["content"]
