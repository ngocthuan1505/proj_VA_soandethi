"""Sửa short/truefalse dùng snapshot server và lượt giải mù; không gọi AI thật."""

import copy
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_poc_scoped_patch import setup as setup

from mach_backend.ai_contract import AIError
from mach_backend.local_workspace import create_app
from mach_backend.poc_scoped_patch import Draft, Submission, checked_snapshot, validate_draft


@pytest.fixture(params=["short", "truefalse"])
def typed_patch(request, tmp_path):
    kind = request.param
    q = {
        "id": str(uuid4()),
        "v": 1,
        "type": kind,
        "stem": "Xe đi60km trong2giờ. Tính vận tốc (km/h).",
        "options": ["Vận tốc30km/h", "Vận tốc60km/h", "Quãng đường120km", "Thời gian2giờ"]
        if kind == "truefalse"
        else [],
        "answer": 0,
        "answerKnown": False,
        "answerText": "30",
        "truthValues": [True, False, False, True],
        "explanation": "60/2=30km/h.",
        "points": 2.5,
        "rubric": [{"text": "Tính vận tốc", "points": 2.5}],
    }
    fields = ["stem", "options", "answer", "answerText", "truthValues", "explanation", "rubric"]
    q["blockIds"] = {f: str(uuid4()) for f in fields}
    other = copy.deepcopy(q)
    other.update(id=str(uuid4()), blockIds={f: str(uuid4()) for f in fields})
    exam = {
        "id": str(uuid4()),
        "revision": 1,
        "questions": [q, other],
        "docs": [],
        "assistantSources": [],
    }
    changes = {
        "stem": "Tàu đi120km trong2giờ. Tính vận tốc (km/h).",
        "explanation": "Tính $v=120/2=60$ km/h.",
        "rubric": [{"text": "Tính $v=60$ km/h", "points": 2.5}],
    }
    if kind == "short":
        changes["answerText"] = "60"
    else:
        changes.update(
            options=["Vận tốc60km/h", "Vận tốc30km/h", "Quãng đường60km", "Thời gian2giờ"],
            truthValues=[True, False, False, True],
        )
    edits = [
        {"blockId": q["blockIds"][f], "op": "replace", "content": v} for f, v in changes.items()
    ]
    calls, controls = [], {}

    async def model(purpose, body):
        data = json.loads(body["messages"][1]["content"])
        calls.append((purpose, data))
        if purpose == "scoped_patch":
            value = {"edits": edits, "message": "Đề xuất đổi tình huống."}
        elif purpose == "scoped_patch_blind":
            assert set(data["questions"][0]) == {"ordinal", "type", "stem", "options"}
            answer = "60" if kind == "short" else [True, False, False, True]
            if controls.get("wrong"):
                answer = "30" if kind == "short" else [False, False, False, True]
            value = {
                "reviews": [
                    {
                        "ordinal": 0,
                        "answer": answer,
                        "solution": "$120/2=60$ km/h.",
                        "uncertain": controls.get("uncertain", False),
                    }
                ]
            }
        else:
            assert data["questions"][0]["blindSolution"] == "$120/2=60$ km/h."
            value = {"reviews": [{"ordinal": 0, "agrees": not controls.get("explanation", False)}]}
        return {"content": json.dumps(value)}

    app = create_app(tmp_path, agent_call=model)
    app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
    raw = {
        "exam": {"id": exam["id"], "revision": 1},
        "scopes": [
            {
                "id": q["id"],
                "version": 1,
                "blockId": q["blockIds"]["stem"],
                "field": "stem",
                "wholeField": True,
            }
        ],
        "request": "Đổi xe thành tàu120km, cập nhật phần liên quan",
        "consent": True,
    }
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.headers["X-PoC-Config"] = client.get("/api/config").json()["fingerprint"]
        yield client, app, exam, q, raw, edits, controls, calls


def test_typed_edit_returns_reviewed_preview_and_does_not_save(typed_patch):
    client, app, exam, q, raw, edits, _, calls = typed_patch
    response = client.post("/api/assistant/patch", json=raw)
    assert response.status_code == 200, response.text
    assert response.json()["edits"] == edits and len(calls) == 3
    assert app.state.store.exam(exam["id"])[1] == exam
    request = Submission.model_validate(raw)
    _, selected = checked_snapshot(app.state.store, request)
    candidates = validate_draft(
        request,
        selected,
        Draft.model_validate_json(
            json.dumps({"edits": response.json()["edits"], "message": response.json()["message"]})
        ),
    )
    assert candidates[q["id"]]["type"] == q["type"]
    assert candidates[q["id"]]["id"] == q["id"] and candidates[q["id"]]["answerKnown"]


@pytest.mark.parametrize(
    "bad,code",
    [
        ("wrong", "answer_disagreement"),
        ("uncertain", "answer_disagreement"),
        ("explanation", "explanation_disagreement"),
    ],
)
def test_typed_disagreement_never_returns_applicable_preview(typed_patch, bad, code):
    client, app, exam, _, raw, _, controls, _ = typed_patch
    controls[bad] = True
    response = client.post("/api/assistant/patch", json=raw)
    assert response.status_code == 409 and response.json()["code"] == code
    assert app.state.store.exam(exam["id"])[1] == exam


def test_typed_stem_change_requires_answer_and_rubric_dependencies(typed_patch):
    client, app, exam, q, raw, edits, _, _ = typed_patch
    field = "answerText" if q["type"] == "short" else "truthValues"
    edits[:] = [e for e in edits if e["blockId"] != q["blockIds"][field]]
    response = client.post("/api/assistant/patch", json=raw)
    assert response.status_code == 409 and response.json()["code"] == "invalid_result"
    assert app.state.store.exam(exam["id"])[1] == exam


def test_typed_answer_selection_preserves_unselected_text_or_truth_items(typed_patch):
    _, app, _, q, raw, _, _, _ = typed_patch
    field = "answerText" if q["type"] == "short" else "truthValues"
    raw["scopes"][0].update(field=field, blockId=q["blockIds"][field])
    if field == "answerText":
        raw["scopes"][0].update(wholeField=False, start=0, end=1, text="3")
        allowed, forbidden = "40", "41"
    else:
        raw["scopes"][0].update(index=1)
        allowed, forbidden = [True, True, False, True], [True, True, True, True]
    request = Submission.model_validate(raw)
    _, selected = checked_snapshot(app.state.store, request)

    def draft(value):
        return Draft.model_validate_json(
            json.dumps(
                {
                    "message": "Sửa đúng phần",
                    "edits": [{"blockId": q["blockIds"][field], "op": "replace", "content": value}],
                }
            )
        )

    assert validate_draft(request, selected, draft(allowed))[q["id"]][field] == allowed
    with pytest.raises(AIError, match="ngoài"):
        validate_draft(request, selected, draft(forbidden))


def test_explicit_explanation_and_rubric_scope_does_not_expand_to_stem(typed_patch):
    _, app, _, q, raw, _, _, _ = typed_patch
    raw["scopes"][0].update(
        field="explanation", blockId=q["blockIds"]["explanation"], allowFields=["rubric"]
    )
    request = Submission.model_validate(raw)
    _, selected = checked_snapshot(app.state.store, request)
    values = [
        {"blockId": q["blockIds"]["explanation"], "op": "replace", "content": "Lời giải rõ hơn."},
        {
            "blockId": q["blockIds"]["rubric"],
            "op": "replace",
            "content": [{"text": "Chấm đúng bước", "points": 2.5}],
        },
    ]

    def draft():
        return Draft.model_validate_json(
            json.dumps({"edits": values, "message": "Sửa lời giải/barem"})
        )

    assert validate_draft(request, selected, draft())[q["id"]]["stem"] == q["stem"]
    values.append(
        {"blockId": q["blockIds"]["stem"], "op": "replace", "content": "Đổi ngoài phạm vi"}
    )
    with pytest.raises(AIError, match="ngoài phạm vi"):
        validate_draft(request, selected, draft())


def test_mcq_rubric_is_editable_without_rewriting_stem_or_changing_total_points(setup):
    app, client, exam, q, raw, edits, _ = setup
    q.update(points=2.5, rubric=[])
    q["blockIds"]["rubric"] = str(uuid4())
    app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
    raw["scopes"][0].update(field="rubric", blockId=q["blockIds"]["rubric"])
    edits[:] = [
        {
            "blockId": q["blockIds"]["rubric"],
            "op": "replace",
            "content": [{"text": "Chọn đáp án2", "points": 2.5}],
        }
    ]
    response = client.post("/api/assistant/patch", json=raw)
    assert response.status_code == 200, response.text
    assert app.state.store.exam(exam["id"])[1] == exam
    edits[0]["content"][0]["points"] = 3
    response = client.post("/api/assistant/patch", json=raw)
    assert response.status_code == 409 and response.json()["code"] == "invalid_rubric"
