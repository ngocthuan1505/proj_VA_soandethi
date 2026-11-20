"""Giải lại từ câu/nguồn server, không sửa đáp án; fixture không gọi AI thật."""

import asyncio
import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from mach_backend.lesson_catalog import lesson_catalog
from mach_backend.local_workspace import create_app


@pytest.fixture
def setup(tmp_path):
    source_id, question_id, exam_id = map(str, (uuid4(), uuid4(), uuid4()))
    q = {
        "id": question_id,
        "v": 2,
        "type": "mcq",
        "stem": "Ai mở cửa thư viện?",
        "options": ["Mai", "Nam", "Hà", "Lan"],
        "answer": 1,
        "explanation": "ĐÁP_ÁN_CŨ_KHÔNG_GỬI",
        "rubric": [{"text": "RUBRIC_CŨ", "points": 2}],
    }
    doc = {
        "id": source_id,
        "version": 3,
        "kind": "pdf",
        "text": "Mai mở cửa thư viện.",
        "pages": [{"number": 1, "text": "Mai mở cửa thư viện."}],
    }
    exam = {"id": exam_id, "revision": 4, "questions": [q], "docs": [doc]}
    calls, mode = [], {"answer": 0, "uncertain": False}

    async def model(purpose, body):
        calls.append((purpose, body))
        data = json.loads(body["messages"][1]["content"])
        evidence = [{**s, "quote": s["text"]} for s in data["sources"]]
        for e in evidence:
            del e["text"]
        if mode.get("tamper"):
            state = app.state.store.get("state")["value"]
            state["exams"][0]["docs"][0]["pages"][0]["text"] = "Nguồn đã thay đổi khi AI chạy."
            app.state.store.put("state", state)
        return {
            "content": json.dumps(
                {
                    **{k: data[k] for k in ("jobId", "examId", "baseRevision")},
                    "questionId": data["question"]["questionId"],
                    "questionVersion": data["question"]["questionVersion"],
                    **(
                        {
                            "optionVerdicts": mode.get(
                                "verdicts", ["correct", "incorrect", "incorrect", "incorrect"]
                            )
                        }
                        if data["question"]["type"] == "mcq"
                        else {}
                    ),
                    "answer": mode["answer"],
                    "explanation": "Mai mở cửa thư viện, chọn A.",
                    "uncertain": mode["uncertain"],
                    "evidence": evidence,
                }
            )
        }

    app = create_app(tmp_path, agent_call=model)
    app.state.store.put("state", {"exams": [exam], "current": exam_id})
    path = f"/api/exams/{exam_id}/questions/{question_id}/check"
    body = {
        "baseRevision": 4,
        "questionVersion": 2,
        "consent": True,
        "sources": [
            {
                "sourceId": source_id,
                "sourceVersion": 3,
                "locator": {"kind": "page", "index": 1},
            }
        ],
    }
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        client.headers["X-PoC-Config"] = client.get("/api/config").json()["fingerprint"]
        yield app, client, path, body, q, calls, mode


def test_check_reads_server_snapshot_hides_saved_answer_and_does_not_mutate(setup):
    app, client, path, body, _, calls, _ = setup
    before = deepcopy(app.state.store.get("state"))
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["comparison"] == "disagrees" and r.json()["answer"] == 0
    assert app.state.store.get("state") == before
    purpose, payload = calls[0]
    assert purpose == "question_check"
    data = json.loads(payload["messages"][1]["content"])
    assert "answer" not in data["question"] and "ownerId" not in data
    assert "ĐÁP_ÁN_CŨ_KHÔNG_GỬI" not in json.dumps(payload, ensure_ascii=False)
    assert "RUBRIC_CŨ" not in json.dumps(payload, ensure_ascii=False)
    assert data["sources"][0]["text"] == "Mai mở cửa thư viện."


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("consent", False, 403),
        ("baseRevision", 3, 409),
        ("questionVersion", 1, 409),
    ],
)
def test_bad_or_stale_submission_does_not_call_model(setup, field, value, expected):
    _, client, path, body, _, calls, _ = setup
    body[field] = value
    assert client.post(path, json=body).status_code == expected and not calls


def test_unknown_source_and_spoofed_question_are_rejected(setup):
    _, client, path, body, _, calls, _ = setup
    body["sources"][0]["sourceId"] = str(uuid4())
    assert client.post(path, json=body).status_code == 404 and not calls
    body["question"] = {"answer": 0, "stem": "Câu giả từ UI"}
    assert client.post(path, json=body).status_code == 422 and not calls


def test_check_keeps_source_id_and_exact_page_across_version_change(setup):
    app, client, path, body, _, calls, _ = setup
    snapshot = app.state.store.get("state")
    state = snapshot["value"]
    document = state["exams"][0]["docs"][0]
    document["pages"].append({"number": 2, "text": "Nam xếp sách lên kệ."})
    document["version"] = 4
    app.state.store.put("state", state, snapshot["revision"])

    submitted = deepcopy(body)
    assert client.post(path, json=submitted).status_code == 409
    selected = submitted["sources"][0]
    selected["sourceVersion"] = 4
    selected["locator"]["index"] = 3
    assert client.post(path, json=submitted).status_code == 404
    assert calls == []

    selected["locator"]["index"] = 2
    response = client.post(path, json=submitted)
    response.raise_for_status()
    evidence = response.json()["evidence"]
    assert evidence == [
        {
            **selected,
            "locator": {**selected["locator"], "regionId": None},
            "quote": "Nam xếp sách lên kệ.",
        }
    ]


def test_source_changed_without_revision_during_model_is_still_stale(setup):
    _, client, path, body, _, calls, mode = setup
    mode["tamper"] = True
    r = client.post(path, json=body)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "stale_snapshot"
    assert len(calls) == 1


def test_uncertain_answer_is_returned_for_review_not_claimed_correct(setup):
    _, client, path, body, _, _, mode = setup
    mode.update(answer=None, uncertain=True)
    r = client.post(path, json=body)
    assert r.status_code == 200 and r.json()["comparison"] == "needs_review"


def test_missing_question_and_old_config_do_not_call_model(setup):
    _, client, path, body, _, calls, _ = setup
    client.headers["X-PoC-Config"] = "old"
    assert client.post(path, json=body).json()["code"] == "config_changed"
    client.headers["X-PoC-Config"] = client.get("/api/config").json()["fingerprint"]
    path = path.rsplit("/questions/", 1)[0] + f"/questions/{uuid4()}/check"
    assert client.post(path, json=body).status_code == 404 and not calls


@pytest.mark.parametrize(
    "kind,answer", [("essay", None), ("short", "Mai"), ("truefalse", [True, False, True, False])]
)
def test_other_question_types_use_existing_contract(setup, kind, answer):
    app, client, path, body, _, _, mode = setup
    state = app.state.store.get("state")["value"]
    q = state["exams"][0]["questions"][0]
    q.update(type=kind, answer=answer, options=q["options"] if kind == "truefalse" else [])
    app.state.store.put("state", state)
    mode["answer"] = answer
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["comparison"] == ("agrees" if kind == "truefalse" else "needs_review")


def test_local_arithmetic_needs_no_model_and_compares_real_saved_answer(setup):
    app, client, path, body, _, calls, _ = setup
    state = app.state.store.get("state")["value"]
    state["exams"][0]["questions"][0].update(
        stem="Tính $x+2$ khi $x=3$.",
        options=["4", "5", "6", "7"],
        answer=0,
    )
    app.state.store.put("state", state)
    body["sources"] = []
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["method"] == "local_arithmetic"
    assert r.json()["answer"] == 1 and r.json()["comparison"] == "disagrees" and not calls


def test_formulas_tables_are_sent_but_missing_visual_data_never_silently_ignored(setup):
    app, client, path, body, _, calls, _ = setup
    state = app.state.store.get("state")["value"]
    q = state["exams"][0]["questions"][0]
    q.update(formulas=[{"latex": "x^2"}], tables=[{"rows": [["A", "B"], ["1", "2"]]}])
    app.state.store.put("state", state)
    assert client.post(path, json=body).status_code == 200
    text = json.loads(calls[0][1]["messages"][1]["content"])["question"]["stem"]
    assert "$x^2$" in text and "A | B" in text and "1 | 2" in text
    q["images"] = [{"data": "fake"}]
    app.state.store.put("state", state)
    r = client.post(path, json=body)
    assert r.status_code == 422 and len(calls) == 1


def test_check_serializes_with_generation_and_config(setup):
    app, _, path, body, _, _, _ = setup

    async def run():
        from types import SimpleNamespace

        app.state.runner._runs[uuid4()] = SimpleNamespace(state=SimpleNamespace(status="running"))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Origin": "http://testserver"},
        ) as client:
            config = (await client.get("/api/config")).json()
            r = await client.post(path, json=body, headers={"X-PoC-Config": config["fingerprint"]})
            assert r.status_code == 409 and r.json()["code"] == "job_limit"
        app.state.runner._runs.clear()

    asyncio.run(run())


@pytest.mark.parametrize(
    "verdicts",
    [
        ["correct", "correct", "incorrect", "incorrect"],
        ["correct", "unknown", "incorrect", "incorrect"],
        ["incorrect", "correct", "incorrect", "incorrect"],
    ],
)
def test_ambiguous_or_conflicting_option_verdicts_cannot_claim_agreement(setup, verdicts):
    _, client, path, body, _, _, mode = setup
    mode["verdicts"] = verdicts
    r = client.post(path, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["uncertain"] and r.json()["answer"] is None
    assert r.json()["comparison"] == "needs_review"


def test_bundled_lesson_is_resolved_by_id_version_and_selected_page(setup):
    app, client, path, body, _, calls, _ = setup
    collection = next(c for c in lesson_catalog() if len(c["lessons"]) > 1)
    lesson = collection["lessons"][1]
    state = app.state.store.get("state")["value"]
    document = {
        "id": collection["id"],
        "version": collection["version"],
        "pages": [{"number": lesson["number"], "text": "Bản sao đã bị thay thế."}],
    }
    state["exams"][0]["docs"] = [document]
    app.state.store.put("state", state)
    body["sources"][0].update(
        sourceId=document["id"],
        sourceVersion=document["version"],
        locator={"kind": "page", "index": lesson["number"]},
    )
    ok = client.post(path, json=body)
    assert ok.status_code == 200, ok.text
    _, request = calls.pop()
    [source] = json.loads(request["messages"][1]["content"])["sources"]
    assert source["text"] == (
        f"Bài {lesson['number']}. {lesson['title']}\n{lesson['text']}\n"
        f"Mục tiêu: {lesson['outcome']}"
    )

    document["version"] += 1
    app.state.store.put("state", state)
    body["sources"][0]["sourceVersion"] = document["version"]
    stale = client.post(path, json=body)
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_snapshot"
    assert not calls

    document["catalog"] = True
    document["pages"][0]["method"] = "manual"
    app.state.store.put("state", state)
    edited = client.post(path, json=body)
    assert edited.status_code == 200, edited.text
    _, request = calls.pop()
    [source] = json.loads(request["messages"][1]["content"])["sources"]
    assert source["text"] == "Bản sao đã bị thay thế."


def test_personal_lesson_rechecks_owner_version_content_and_rights(setup):
    app, client, path, body, _, calls, _ = setup
    route = "/api/lesson-catalog/sources"
    excerpt = "Mai mở cửa thư viện. Nội dung thuộc kho của giáo viên."
    created = client.post(
        route,
        json={
            "grade": 6,
            "subject": "Ngữ văn",
            "title": "Nguồn riêng",
            "license_status": "teacher_owned",
            "content_excerpt": excerpt,
        },
    )
    assert created.status_code == 201, created.text
    source = created.json()
    state = app.state.store.get("state")["value"]
    doc = {
        "id": source["id"],
        "version": source["updated_at"],
        "personalLesson": True,
        "pages": [{"number": 1, "text": "Nội dung bản sao bị đổi."}],
    }
    state["exams"][0]["docs"] = [doc]
    app.state.store.put("state", state)
    body["sources"][0].update(sourceId=doc["id"], sourceVersion=doc["version"])
    ok = client.post(path, json=body)
    assert ok.status_code == 200, ok.text
    _, request = calls.pop()
    [fragment] = json.loads(request["messages"][1]["content"])["sources"]
    assert fragment["text"] == excerpt

    assert (
        client.patch(
            route + "/" + doc["id"], json={"content_excerpt": excerpt + " Bản mới."}
        ).status_code
        == 200
    )
    assert client.post(path, json=body).status_code == 409
    conflict = client.patch(
        route + "/" + doc["id"],
        json={"content_excerpt": excerpt},
        headers={"If-Match": str(doc["version"])},
    )
    assert conflict.status_code == 409
    with app.state.store.connect() as db:
        db.execute("UPDATE curriculum_sources SET owner_id = ? WHERE id = ?", ("other", doc["id"]))
    unknown = client.post(path, json=body)
    assert unknown.status_code == 404
    assert not calls


def test_overlong_source_and_empty_page_have_actionable_errors(setup):
    app, client, path, body, _, calls, _ = setup
    state = app.state.store.get("state")["value"]
    page = state["exams"][0]["docs"][0]["pages"][0]
    for text, code in [("a" * 12001, "source_limit"), ("", "invalid_source")]:
        page["text"] = text
        app.state.store.put("state", state)
        r = client.post(path, json=body)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code
    assert not calls


@pytest.mark.parametrize(
    "field,value", [("stem", None), ("tables", [{"rows": [[12]]}]), ("formulas", [{"latex": None}])]
)
def test_malformed_saved_content_is_reported_without_model_or_server_crash(setup, field, value):
    app, client, path, body, _, calls, _ = setup
    state = app.state.store.get("state")["value"]
    state["exams"][0]["questions"][0][field] = value
    app.state.store.put("state", state)
    r = client.post(path, json=body)
    assert r.status_code == 422 and not calls


def test_linked_data_table_is_part_of_blind_context_and_stale_detection(setup):
    app, client, path, body, _, calls, _ = setup
    state = app.state.store.get("state")["value"]
    exam = state["exams"][0]
    exam["questions"][0]["dataLinked"] = True
    exam["data"] = [{"label": "Lớp A", "value": 30}, {"label": "Lớp B", "value": 42}]
    app.state.store.put("state", state)
    assert client.post(path, json=body).status_code == 200
    stem = json.loads(calls[0][1]["messages"][1]["content"])["question"]["stem"]
    assert "Lớp A: 30" in stem and "Lớp B: 42" in stem
    exam["data"] = []
    app.state.store.put("state", state)
    r = client.post(path, json=body)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "missing_data"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "kind,field,answer",
    [
        ("short", "answerText", "Mai"),
        ("truefalse", "truthValues", [True, False, True, False]),
    ],
)
def test_check_reads_split_workspace_answers_and_hides_them_from_blind_solver(
    setup, kind, field, answer
):
    app, client, path, body, _, calls, mode = setup
    state = app.state.store.get("state")["value"]
    q = state["exams"][0]["questions"][0]
    q.update(
        type=kind, answer=0, answerKnown=True, options=q["options"] if kind == "truefalse" else []
    )
    q[field] = answer
    app.state.store.put("state", state)
    before = deepcopy(app.state.store.get("state")["value"]["exams"])
    mode["answer"] = answer
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["comparison"] == ("agrees" if kind == "truefalse" else "needs_review")
    blind = json.loads(calls[-1][1]["messages"][1]["content"])["question"]
    assert field not in blind and "answer" not in blind
    assert app.state.store.get("state")["value"]["exams"] == before
