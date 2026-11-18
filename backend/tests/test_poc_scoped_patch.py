"""Fixture sửa câu PoC: không gọi AI thật và không tự lưu đề xuất."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.local_workspace import create_app
from mach_backend.poc_scoped_patch import Draft, Submission, checked_snapshot, validate_draft


@pytest.fixture
def setup(tmp_path):
    question = {
        "id": str(uuid4()),
        "v": 1,
        "type": "mcq",
        "stem": "Một cộng một bằng mấy?",
        "options": ["1", "2", "3", "4"],
        "answer": 1,
        "explanation": "Một cộng một bằng hai.",
        "blockIds": {f: str(uuid4()) for f in ("stem", "options", "answer", "explanation")},
    }
    exam = {
        "id": str(uuid4()),
        "revision": 1,
        "questions": [question, {**deepcopy(question), "id": str(uuid4())}],
        "docs": [],
        "assistantSources": [],
    }
    edits = [
        {
            "blockId": question["blockIds"][f],
            "op": "replace",
            "content": "Một cộng một được bao nhiêu?" if f == "stem" else question[f],
        }
        for f in question["blockIds"]
    ]
    calls = []

    async def model(purpose, body):
        calls.append((purpose, body))
        data = (
            {"edits": edits, "message": "Đã chuẩn bị cách hỏi rõ hơn."}
            if purpose == "scoped_patch"
            else {
                "reviews": [
                    {
                        "ordinal": 0,
                        "answer": 1,
                        "uncertain": False,
                        "optionVerdicts": ["incorrect", "correct", "incorrect", "incorrect"],
                    }
                ]
            }
            if purpose == "scoped_patch_blind"
            else {"reviews": [{"ordinal": 0, "agrees": True}]}
        )
        return {"role": "assistant", "content": json.dumps(data)}

    app = create_app(tmp_path, agent_call=model)
    app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
    request = {
        "exam": {"id": exam["id"], "revision": 1},
        "scopes": [
            {
                "id": question["id"],
                "version": 1,
                "blockId": question["blockIds"]["stem"],
                "field": "stem",
                "wholeField": True,
            }
        ],
        "request": "Viết câu này rõ hơn",
        "consent": True,
    }
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.headers["X-PoC-Config"] = client.get("/api/config").json()["fingerprint"]
        yield app, client, exam, question, request, edits, calls


def test_edit_is_preview_only_and_review_is_blind(setup):
    app, client, exam, question, request, _, calls = setup
    response = client.post("/api/assistant/patch", json=request)
    assert response.status_code == 200, response.text
    assert len(response.json()["checks"]) == 3
    assert [p for p, _ in calls] == [
        "scoped_patch",
        "scoped_patch_blind",
        "scoped_patch_explanation",
    ]
    blind = json.loads(calls[1][1]["messages"][1]["content"])["questions"][0]
    assert "answer" not in blind and "explanation" not in blind
    assert app.state.store.exam(exam["id"])[1] == exam
    assert question["stem"] == "Một cộng một bằng mấy?"


@pytest.mark.parametrize("bad", ["consent", "revision", "version", "block", "config"])
def test_rejects_invalid_snapshot_before_model(setup, bad):
    _, client, _, _, request, _, calls = setup
    if bad == "consent":
        request["consent"] = False
    elif bad == "revision":
        request["exam"]["revision"] = 2
    elif bad == "version":
        request["scopes"][0]["version"] = 2
    elif bad == "block":
        request["scopes"][0]["blockId"] = str(uuid4())
    else:
        client.headers["X-PoC-Config"] = "stale"
    assert client.post("/api/assistant/patch", json=request).status_code == 409
    assert not calls


def test_blocks_unselected_question_and_partial_text_escape(setup):
    app, _, exam, q, raw, edits, _ = setup
    raw["scopes"][0].update(wholeField=False, start=4, end=8, text="cộng")
    request = Submission.model_validate(raw)
    _, selected = checked_snapshot(app.state.store, request)
    edits[0]["content"] = "Một cộng lại một bằng mấy?"
    draft = Draft.model_validate_json(json.dumps({"edits": edits, "message": "Chỉnh đoạn"}))
    assert validate_draft(request, selected, draft)[q["id"]]["stem"] == edits[0]["content"]
    edits[0]["content"] = "Đổi cả phần ngoài đoạn."
    with pytest.raises(ValueError, match="ngoài đoạn"):
        validate_draft(
            request,
            selected,
            Draft.model_validate_json(json.dumps({"edits": edits, "message": "Sai"})),
        )
    edits[0]["blockId"] = exam["questions"][1]["id"]
    with pytest.raises(ValueError, match="ngoài vùng"):
        validate_draft(
            request,
            selected,
            Draft.model_validate_json(json.dumps({"edits": edits, "message": "Sai"})),
        )


def test_blind_disagreement_blocks_preview(setup):
    app, client, exam, _, request, edits, _ = setup
    edits[2]["content"] = 0
    response = client.post("/api/assistant/patch", json=request)
    assert response.status_code == 409
    assert response.json()["code"] == "answer_disagreement"
    assert app.state.store.exam(exam["id"])[1] == exam


@pytest.mark.parametrize("bad", ["none", "rubric", "uncertain", "explanation"])
def test_essay_stem_edit_gets_blind_solution_and_rubric_review(tmp_path, bad):
    q = {
        "id": str(uuid4()),
        "v": 1,
        "type": "essay",
        "stem": "Xe đi 60 km trong 2 giờ. Tính vận tốc.",
        "options": [],
        "answer": 0,
        "explanation": "v = 60/2 = 30 km/h.",
        "points": 2.5,
        "rubric": [{"text": "Tính vận tốc 30 km/h", "points": 2.5}],
        "blockIds": {
            f: str(uuid4()) for f in ("stem", "options", "answer", "explanation", "rubric")
        },
    }
    exam = {"id": str(uuid4()), "revision": 1, "questions": [q], "docs": [], "assistantSources": []}
    calls = []

    async def model(purpose, body):
        data = json.loads(body["messages"][1]["content"])
        calls.append((purpose, data))
        if purpose == "scoped_patch":
            value = {
                "edits": [
                    {"blockId": q["blockIds"][f], "op": "replace", "content": v}
                    for f, v in {
                        "stem": "Tàu đi 120 km trong 2 giờ. Tính vận tốc.",
                        "explanation": "v = 120/2 = 60 km/h.",
                        "rubric": [{"text": "Tính vận tốc 60 km/h", "points": 2.5}],
                    }.items()
                ],
                "message": "Đề xuất đổi tình huống.",
            }
        elif purpose == "scoped_patch_blind":
            assert (
                "explanation" not in data["questions"][0] and "rubric" not in data["questions"][0]
            )
            value = {"reviews": [{"ordinal": 0, "solution": "120/2=60 km/h", "uncertain": False}]}
        else:
            assert data["questions"][0]["blindSolution"] == "120/2=60 km/h"
            value = {"reviews": [{"ordinal": 0, "agrees": True}]}
        if bad == "rubric" and purpose == "scoped_patch":
            value["edits"][-1]["content"][0]["points"] = 3
        if bad == "uncertain" and purpose == "scoped_patch_blind":
            value["reviews"][0]["uncertain"] = True
        if bad == "explanation" and purpose == "scoped_patch_explanation":
            value["reviews"][0]["agrees"] = False
        return {"content": json.dumps(value)}

    app = create_app(tmp_path, agent_call=model)
    app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        request = {
            "exam": {"id": exam["id"], "revision": 1},
            "scopes": [
                {
                    "id": q["id"],
                    "version": 1,
                    "field": "stem",
                    "blockId": q["blockIds"]["stem"],
                    "wholeField": True,
                }
            ],
            "request": "Đổi thành đi tàu nhanh hơn",
            "consent": True,
        }
        client.headers["X-PoC-Config"] = client.get("/api/config").json()["fingerprint"]
        result = client.post("/api/assistant/patch", json=request)
        assert result.status_code == (200 if bad == "none" else 409), result.text
        if bad == "none":
            assert len(result.json()["edits"]) == 3 and len(calls) == 3
        assert app.state.store.exam(exam["id"])[1] == exam
