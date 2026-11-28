"""Sinh/kiểm/xác nhận nhiều kích thước bằng model giả lập tường minh."""

import json

import pytest
from fastapi.testclient import TestClient
from test_local_workspace import generate
from test_local_workspace import workspace as workspace

from mach_backend.local_workspace import create_app


@pytest.mark.parametrize("count", [1, 3, 5, 8, 9, 30])
def test_changed_matrix_size_repairs_previews_and_saves_exact_count(workspace, tmp_path, count):
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    exam["matrix"] = [
        {"topic": "Đọc hiểu", "targets": [count - 2, 1, 1] if count > 2 else [1, 0, 0]}
    ]
    state["exams"] = [exam]
    attempts = 0
    levels = []

    async def model(purpose, body):
        nonlocal attempts, levels
        if purpose == "agent":
            levels = [
                s["level"] for s in json.loads(body["messages"][1]["content"])["matrix"]["slots"]
            ]
            if (
                body["messages"][-1]["role"] == "tool"
                and json.loads(body["messages"][-1]["content"])["ok"]
            ):
                return {"tool_calls": [{"function": {"name": "finish_exam", "arguments": {}}}]}
            attempts += 1
            return {
                "tool_calls": [
                    {
                        "function": {
                            "name": "check_exam",
                            "arguments": {
                                "questions": [
                                    {
                                        "stem": f"Câu fixture thứ {i + 1} cần tìm gì?",
                                        "options": ["Mai", "Nam", "Hà", "Lan"],
                                        "answer": 1 if attempts == 1 else 0,
                                        "explanation": "Mai mở cửa thư viện.",
                                        "evidenceIds": [0],
                                    }
                                    for i in range(count)
                                ]
                            },
                        }
                    }
                ]
            }
        reviews = [
            {
                "ordinal": i,
                "answer": 0,
                "observedLevel": levels[i],
                "supported": True,
                "topicMatches": True,
                "uncertain": False,
                "optionVerdicts": ["correct", "incorrect", "incorrect", "incorrect"],
                "duplicateWith": [],
                "duplicateUncertain": False,
                "reason": "Fixture kiểm cơ chế.",
            }
            if purpose == "blind_content_check"
            else {"ordinal": i, "consistent": True, "reason": "Fixture."}
            for i in range(count)
        ]
        return {"content": json.dumps({"reviews": reviews})}

    with TestClient(
        create_app(tmp_path / "sizes", agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        base, result = generate(client, exam)
        assert result["status"] == "complete", result
        assert attempts == 2 and len(result["proposal"]["questions"]) == count
        assert sum(q["pointsQ4"] for q in result["proposal"]["questions"]) == 40
        assert client.get("/api/kv?key=state").json()["value"] == state
        saved = client.post(
            base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
        )
        assert saved.status_code == 200, saved.text
        questions = client.get("/api/kv?key=state").json()["value"]["exams"][0]["questions"]
        assert len(questions) == count and sum(q["points"] for q in questions) == 10


def test_matrix_slots_share_remaining_points_and_do_not_merge_same_topic_types():
    from mach_backend.matrix_import import matrix_slots

    rows = [
        {"topic": "A", "type": "mcq", "targets": [2, 0, 0], "pointsQ4": 2},
        {"topic": "A", "type": "essay", "targets": [0, 1, 0]},
        {"topic": "A", "type": "short", "targets": [0, 0, 1]},
    ]
    slots = matrix_slots(rows)
    assert [q.type for q in slots] == ["mcq", "mcq", "essay", "short"]
    assert [q.pointsQ4 for q in slots] == [2, 2, 18, 18]
    assert sum(q.pointsQ4 for q in slots) == 40


@pytest.mark.parametrize(
    "rows",
    [
        [{"topic": "A", "targets": [61, 0, 0]}],
        [{"topic": "A", "targets": [1, 0, 0], "pointsQ4": 39}],
        [
            {"topic": "A", "targets": [2, 0, 0], "pointsQ4": 20},
            {"topic": "B", "targets": [1, 0, 0]},
        ],
        [{"topic": "A", "targets": [1, 0, 0]}, {"topic": "a", "targets": [1, 0, 0]}],
    ],
)
def test_invalid_matrix_cannot_allocate_or_silently_reduce_slots(rows):
    from mach_backend.ai_contract import AIError
    from mach_backend.matrix_import import matrix_slots

    with pytest.raises(AIError):
        matrix_slots(rows)


def test_ambiguous_total_points_column_requires_clarification_instead_of_ignoring_points():
    from mach_backend.matrix_import import parse_table

    assert (
        parse_table(
            [
                ["Chủ đề", "Điểm", "Nhận biết", "Thông hiểu", "Vận dụng"],
                ["Chuyển động", "3", "2", "1", "1"],
            ]
        )
        is None
    )
