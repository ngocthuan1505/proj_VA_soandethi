"""Fixture sửa câu PoC: không gọi AI thật và không tự lưu đề xuất."""

import asyncio
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError, BlockTarget
from mach_backend.local_workspace import create_app
from mach_backend.poc_scoped_patch import Draft, Submission, checked_snapshot, validate_draft
from mach_backend.rich_patch import project, update_rich


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


def test_disconnecting_patch_cancels_the_model_and_releases_workspace(setup, tmp_path):
    _, _, exam, _, submission, _, _ = setup

    async def run():
        started = asyncio.Event()
        disconnected = asyncio.Event()
        cleaned_up = asyncio.Event()

        async def model(_purpose, _body):
            started.set()
            try:
                await asyncio.sleep(4)
            finally:
                cleaned_up.set()

        app = create_app(tmp_path / "disconnect", agent_call=model)
        app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
        body = json.dumps(submission).encode()
        first = True

        async def receive():
            nonlocal first
            if first:
                first = False
                return {"type": "http.request", "body": body, "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(_message):
            pass

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/assistant/patch",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"origin", b"http://testserver"),
                (b"content-type", b"application/json"),
                (b"x-poc-config", app.state.provider.connection_stamp.encode()),
            ],
        }
        patch = asyncio.create_task(app(scope, receive, send))
        try:
            await asyncio.wait_for(started.wait(), timeout=2)
            assert app.state.ai_busy()
            disconnected.set()
            await asyncio.wait_for(asyncio.shield(patch), timeout=2)
            assert cleaned_up.is_set()
            assert not app.state.ai_busy()
            assert app.state.store.exam(exam["id"])[1] == exam
        finally:
            if not patch.done():
                patch.cancel()
                await asyncio.gather(patch, return_exceptions=True)

    asyncio.run(run())


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


def test_scoped_confirmation_is_transactional_and_replay_safe(setup, monkeypatch):
    app, client, exam, question, body, _, _ = setup
    preview = client.post("/api/assistant/patch", json=body)
    preview.raise_for_status()
    proposal_id = preview.json()["confirmationId"]
    assert proposal_id
    search = f"/api/exams/{exam['id']}/edits/{proposal_id}/confirm"
    store = app.state.store
    before = store.get("state")
    assert before["value"]["exams"][0] == exam
    wrong = client.post(f"/api/exams/{uuid4()}/edits/{proposal_id}/confirm", json={})
    assert wrong.status_code == 409 and wrong.json()["code"] == "proposal_not_found"
    put = store.put

    def fail_receipt(key, value, *args, **kwargs):
        if key.startswith("scoped-patch:"):
            raise RuntimeError("Lỗi SQLite giả lập khi lưu biên nhận")
        return put(key, value, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(store, "put", fail_receipt)
        with pytest.raises(RuntimeError, match="Lỗi SQLite giả lập"):
            client.post(search, json={})
    assert store.get("state") == before
    receipt = client.post(search, json={})
    receipt.raise_for_status()
    changed = store.get("state")
    updated = changed["value"]["exams"][0]
    assert changed["revision"] == before["revision"] + 1
    assert receipt.json()["revision"] == exam["revision"] + 1 == updated["revision"]
    assert updated["questions"][0]["id"] == question["id"]
    assert updated["questions"][0]["stem"] == "Một cộng một được bao nhiêu?"
    assert updated["questions"][0]["v"] == question["v"] + 1
    assert updated["questions"][0]["approval"] is None
    assert updated["questions"][1] == exam["questions"][1]
    assert updated["undo"][-1]["state"] == exam
    assert client.post(search, json={}).json() == receipt.json()
    assert store.get("state") == changed


def test_scoped_confirmation_rejects_change_without_version_bump(setup):
    app, client, exam, _, body, _, _ = setup
    preview = client.post("/api/assistant/patch", json=body)
    preview.raise_for_status()
    proposal_id = preview.json()["confirmationId"]
    store = app.state.store
    changed = store.get("state")["value"]
    changed["exams"][0]["title"] = "Đổi từ phiên khác"
    store.put("state", changed)
    before = store.get("state")
    result = client.post(f"/api/exams/{exam['id']}/edits/{proposal_id}/confirm", json={})
    assert result.status_code == 409 and result.json()["code"] == "stale_snapshot"
    assert store.get("state") == before


def test_discarded_scoped_proposal_can_no_longer_be_confirmed(setup):
    app, client, exam, _, body, _, _ = setup
    preview = client.post("/api/assistant/patch", json=body)
    preview.raise_for_status()
    endpoint = f"/api/exams/{exam['id']}/edits/{preview.json()['confirmationId']}"
    before = app.state.store.get("state")
    assert client.post(endpoint + "/discard", json={}).json() == {"discarded": True}
    assert client.post(endpoint + "/confirm", json={}).json()["code"] == "proposal_not_found"
    assert app.state.store.get("state") == before


@pytest.mark.parametrize(
    "wrappers",
    [("blockquote",), ("bulletList", "listItem"), ("table", "tableRow", "tableHeader")],
)
def test_editor_inserts_new_paragraphs_in_the_same_container(wrappers):
    content = [{"type": "paragraph", "content": [{"type": "text", "text": "Giữ đầu. Sửa chữ."}]}]
    for kind in reversed(wrappers):
        content = [{"type": kind, "attrs": {"id": kind}, "content": content}]
    doc = {"type": "doc", "content": content}
    target = BlockTarget(
        questionId=uuid4(),
        questionVersion=1,
        blockId=uuid4(),
        field="explanation",
        text="Giữ đầu. Sửa chữ.",
    )
    result = update_rich(doc, target, "Giữ đầu. Thay chữ.\nDòng mới.")
    assert project(result, []) == "Giữ đầu. Thay chữ.\nDòng mới."
    parent = result
    for kind in wrappers:
        parent = parent["content"][0]
        assert parent["type"] == parent["attrs"]["id"] == kind
    assert len(parent["content"]) == 2
    assert project(doc, []) == target.text


def test_editor_change_cannot_merge_distinct_table_cells():
    cells = [
        {
            "type": "tableCell",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]},
            ],
        }
        for text in ("Ô một", "Ô hai")
    ]
    doc = {
        "type": "doc",
        "content": [
            {"type": "table", "content": [{"type": "tableRow", "content": cells}]},
        ],
    }
    target = BlockTarget(
        questionId=uuid4(),
        questionVersion=1,
        blockId=uuid4(),
        field="explanation",
        text="Ô một | Ô hai",
    )
    original = deepcopy(doc)
    with pytest.raises(AIError, match="giữ định dạng"):
        update_rich(doc, target, "Gộp hai ô.")
    assert doc == original


@pytest.mark.parametrize("old_latex", [None, "x+1"])
def test_mixed_editor_change_writes_editable_formula(old_latex):
    nodes = [{"type": "text", "text": "Vế trái."}]
    if old_latex:
        nodes.append({"type": "mathInline", "attrs": {"id": "math-id", "latex": old_latex}})
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": nodes}]}
    original = project(doc, [])
    target = BlockTarget(
        questionId=uuid4(),
        questionVersion=1,
        blockId=uuid4(),
        field="explanation",
        text=original,
    )
    updated = update_rich(doc, target, "Vế phải $x+2$.\nDòng sau.")
    first, second = updated["content"]
    formula = next(node for node in first["content"] if node["type"] == "mathInline")
    assert formula["attrs"]["latex"] == "x+2" and formula["attrs"]["id"]
    if old_latex:
        assert formula["attrs"]["id"] == "math-id"
    assert project(updated, []) == "Vế phải $x+2$.\nDòng sau."
    assert project(second, []) == "Dòng sau."
    assert project(doc, []) == original


def test_confirmation_keeps_repeated_text_in_its_selected_style_run(setup):
    app, client, exam, question, body, edits, _ = setup
    store = app.state.store
    state = store.get("state")["value"]
    q = state["exams"][0]["questions"][0]
    marked = {"type": "text", "text": "x", "marks": [{"type": "bold"}]}
    plain = {"type": "text", "text": "x"}
    q["stem"] = "xx"
    q["richDoc"] = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [marked, plain]}],
    }
    store.put("state", state)
    body["scopes"][0].update(wholeField=False, start=0, end=1, text="x")
    edits[0]["content"] = "xxx"
    preview = client.post("/api/assistant/patch", json=body)
    preview.raise_for_status()
    proposal_id = preview.json()["confirmationId"]
    assert proposal_id
    client.post(f"/api/exams/{exam['id']}/edits/{proposal_id}/confirm", json={}).raise_for_status()
    _, result = store.exam(exam["id"])
    nodes = result["questions"][0]["richDoc"]["content"][0]["content"]
    assert nodes[-1] == plain
    assert all(node.get("marks") == marked["marks"] for node in nodes[:-1])
    assert "".join(node["text"] for node in nodes[:-1]) == "xx"
    assert result["questions"][0]["id"] == question["id"]


def test_multiline_editor_change_is_committed_by_python(setup):
    app, client, exam, question, body, edits, _ = setup
    store = app.state.store
    state = store.get("state")["value"]
    state["exams"][0]["questions"][0]["richDoc"] = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": question["stem"]}]}],
    }
    store.put("state", state)
    edits[0]["content"] = "Một cộng một bằng mấy?\nGiải thích."
    preview = client.post("/api/assistant/patch", json=body)
    preview.raise_for_status()
    proposal_id = preview.json()["confirmationId"]
    assert proposal_id
    assert preview.json()["edits"][0]["content"] == edits[0]["content"]
    assert store.get("state")["value"] == state
    client.post(f"/api/exams/{exam['id']}/edits/{proposal_id}/confirm", json={}).raise_for_status()
    updated = store.get("state")["value"]["exams"][0]["questions"][0]
    assert updated["stem"] == edits[0]["content"]
    assert [node["content"][0]["text"] for node in updated["richDoc"]["content"]] == [
        "Một cộng một bằng mấy?",
        "Giải thích.",
    ]


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
