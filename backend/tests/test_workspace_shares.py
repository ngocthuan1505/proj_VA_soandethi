"""Snapshot và thu hồi bằng ngữ liệu tự viết, không gọi AI."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.local_workspace import create_app
from mach_backend.share_snapshot import snapshot
from mach_backend.team_workspace import create_team_app

ORIGIN = {"Origin": "http://testserver"}
PASSWORD = "mat-khau-chi-dung-test"


@pytest.fixture
def exam():
    return {
        "id": str(uuid4()),
        "revision": 3,
        "title": "ĐỀ CHIA SẺ TỰ VIẾT",
        "subject": "Vật lí",
        "grade": "8",
        "minutes": 45,
        "chat": [{"text": "CHAT_KÍN"}],
        "history": ["LỊCH_SỬ_KÍN"],
        "docs": [{"text": "NGUỒN_RIÊNG_KÍN"}],
        "quote": {"text": "Một xe đi 60 km trong 2 giờ.", "versions": ["PHIÊN_BẢN_KÍN"]},
        "questions": [
            {
                "id": str(uuid4()),
                "v": 2,
                "type": "mcq",
                "stem": "Vận tốc xe bằng bao nhiêu?",
                "points": 2.5,
                "options": ["30 km/h", "40 km/h", "50 km/h", "60 km/h"],
                "answer": 0,
                "answerKnown": True,
                "explanation": "LỜI_GIẢI_KÍN: 60/2=30.",
                "rubric": [{"text": "BAREM_KÍN", "points": 2.5}],
                "check": {"notes": "KIỂM_KÍN"},
                "evidence": [{"quote": "DẪN_CHỨNG_KÍN"}],
                "approval": {"version": 2, "status": "approved", "name": "TÊN_RÀ_KÍN"},
                "richDoc": {
                    "type": "doc",
                    "private": "NODE_KÍN",
                    "content": [
                        {
                            "type": "paragraph",
                            "attrs": {"private": "ATTR_KÍN"},
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Vận tốc xe bằng bao nhiêu?",
                                    "marks": [{"type": "bold", "attrs": {"private": "MARK_KÍN"}}],
                                }
                            ],
                        }
                    ],
                },
            }
        ],
    }


def seed(client, exam):
    client.put(
        "/api/kv",
        json={
            "key": "state",
            "value": {"exams": [exam], "prefs": [], "current": exam["id"]},
        },
    ).raise_for_status()


def create(client, exam, **flags):
    return client.post(
        "/api/share",
        json={
            "examId": exam["id"],
            "baseRevision": exam["revision"],
            **flags,
        },
    )


def test_student_snapshot_is_whitelisted_and_independent(exam):
    selected = snapshot(exam, False)
    raw = json.dumps(selected, ensure_ascii=False)
    assert "_KÍN" not in raw and "60 km" in selected["quote"]["text"]
    assert selected["questions"][0]["answer"] is None
    assert not selected["questions"][0]["answerKnown"]
    exam["questions"][0]["options"][0] = "ĐÃ SỬA"
    assert selected["questions"][0]["options"][0] == "30 km/h"
    assert (
        selected["questions"][0]["richDoc"]["content"][0]["content"][0]["marks"][0]["type"]
        == "bold"
    )


def test_teacher_snapshot_only_adds_selected_teacher_content(exam):
    selected = snapshot(exam, True)
    raw = json.dumps(selected, ensure_ascii=False)
    assert "LỜI_GIẢI_KÍN" in raw and "BAREM_KÍN" in raw
    assert all(
        word not in raw
        for word in ["CHAT_KÍN", "NGUỒN_RIÊNG_KÍN", "KIỂM_KÍN", "TÊN_RÀ_KÍN", "NODE_KÍN"]
    )
    assert selected["questions"][0]["approval"] == {"version": 2, "status": "approved"}


def test_rich_private_attributes_on_supported_marks_are_not_copied(exam):
    leaf = exam["questions"][0]["richDoc"]["content"][0]["content"][0]
    leaf["marks"] = [{"type": "bold", "attrs": {"href": "ĐƯỜNG_DẪN_KÍN", "color": "MÀU_KÍN"}}]
    raw = json.dumps(snapshot(exam, False), ensure_ascii=False)
    assert "ĐƯỜNG_DẪN_KÍN" not in raw and "MÀU_KÍN" not in raw


def test_geometry_dependent_label_positions_are_retained(exam):
    exam["questions"][0]["figure"] = {
        "points": {"A": "free", "B": "free"},
        "constraints": ["H=midpoint(A,B)"],
        "objects": ["segment(A,H)"],
        "labels": {"A": "above", "H": "left"},
    }
    assert snapshot(exam, False)["questions"][0]["figure"]["labels"]["H"] == "left"


def test_bad_style_is_reported_without_internal_error_or_link(tmp_path, exam):
    leaf = exam["questions"][0]["richDoc"]["content"][0]["content"][0]
    leaf["marks"] = [{"type": "textStyle", "attrs": {"color": True}}]
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        seed(client, exam)
        response = create(client, exam)
        assert response.status_code == 409 and response.json()["code"] == "invalid_document"
        assert client.get("/api/share", params={"examId": exam["id"]}).json()["shares"] == []


def test_legacy_runs_are_normalized_to_visible_document(exam):
    q = exam["questions"][0]
    q.pop("richDoc")
    q["runs"] = [{"text": q["stem"], "bold": True, "private": "RUN_KÍN"}]
    selected = snapshot(exam, False)["questions"][0]
    assert "runs" not in selected and "RUN_KÍN" not in json.dumps(selected, ensure_ascii=False)
    assert selected["richDoc"]["content"][0]["content"][0]["marks"] == [{"type": "bold"}]


def test_snapshot_keeps_displayed_data_dependency_without_internal_solver(exam):
    exam["questions"][0]["rule"] = "difference"
    exam["data"] = [
        {"id": "a", "label": "A", "value": 120},
        {"id": "b", "label": "B", "value": 240},
    ]
    selected = snapshot(exam, False)
    assert selected["questions"][0]["dataLinked"] is True
    assert "rule" not in selected["questions"][0]
    assert selected["data"] == exam["data"]


def test_snapshot_does_not_send_unused_data(exam):
    exam["data"] = [{"label": "DỮ_KIỆN_KHÔNG_HIỂN_THỊ_KÍN", "value": 120}]
    assert snapshot(exam, False)["data"] == []


def test_local_share_is_fixed_and_revoked_across_reload(tmp_path, exam):
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        seed(client, exam)
        response = create(client, exam, allowCopy=True)
        response.raise_for_status()
        share = response.json()
        body = client.get("/s/" + share["token"])
        assert body.status_code == 200 and "_KÍN" not in body.text
        assert body.headers["cache-control"] == "no-store"
        assert body.headers["referrer-policy"] == "no-referrer"
        before = client.get("/api/share/read/" + share["token"]).json()
        assert before["exam"]["questions"][0]["answer"] is None
        exam["revision"] += 1
        exam["questions"][0]["stem"] = "ĐỀ GỐC ĐÃ SỬA"
        exam["questions"][0].pop("richDoc")
        seed(client, exam)
        assert client.get("/api/share/read/" + share["token"]).json() == before
    with TestClient(create_app(tmp_path), headers=ORIGIN) as reloaded:
        assert reloaded.get("/s/" + share["token"]).status_code == 200
        assert len(reloaded.get("/api/share", params={"examId": exam["id"]}).json()["shares"]) == 1
        reloaded.post("/api/share/revoke", json={"token": share["token"]}).raise_for_status()
        assert reloaded.get("/s/" + share["token"]).status_code == 404
        assert reloaded.get("/api/share/read/" + share["token"]).status_code == 404
        assert reloaded.get("/api/share", params={"examId": exam["id"]}).json()["shares"] == []


def test_stale_and_invalid_rich_do_not_create_links(tmp_path, exam):
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        seed(client, exam)
        stale = deepcopy(exam)
        stale["revision"] -= 1
        assert create(client, stale).status_code == 409
        exam["questions"][0]["stem"] += " sửa nhưng chưa cập nhật rich"
        seed(client, exam)
        assert create(client, exam).status_code == 409
        assert client.get("/api/share", params={"examId": exam["id"]}).json()["shares"] == []
        assert client.get("/api/kv?key=state").json()["value"]["exams"][0] == exam


def test_no_copy_does_not_expose_json_and_teacher_flag_is_explicit(tmp_path, exam):
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        seed(client, exam)
        created = create(client, exam, answers=True, allowCopy=False).json()
        data = client.get("/api/share/read/" + created["token"]).json()
        assert data["allowCopy"] is False and "exam" not in data
        body = client.get("/s/" + created["token"]).text
        assert "LỜI_GIẢI_KÍN" in body and "BAREM_KÍN" in body
        assert "Tạo bản sao riêng" not in body


def test_team_owner_guest_and_other_owner_permissions(tmp_path, exam):
    app = create_team_app(tmp_path)
    accounts = app.state.accounts
    owner = accounts.create("a@example.test", PASSWORD, "A", accounts.invite(bootstrap=True))
    member = accounts.create("b@example.test", PASSWORD, "B", accounts.invite())
    with (
        TestClient(app, headers=ORIGIN) as first,
        TestClient(app, headers=ORIGIN) as second,
        TestClient(app, headers=ORIGIN) as guest,
    ):
        for client, account in ((first, owner), (second, member)):
            client.post(
                "/api/account/login", json={"email": account["email"], "password": PASSWORD}
            ).raise_for_status()
        seed(first, exam)
        response = create(first, exam, allowCopy=True)
        response.raise_for_status()
        token = response.json()["token"]
        assert guest.get("/s/" + token).status_code == 200
        assert guest.get("/api/share/read/" + token).json()["allowCopy"]
        assert guest.get("/api/kv?key=state").status_code == 401
        assert create(guest, exam).status_code == 401
        assert create(second, exam).status_code == 404
        assert second.post("/api/share/revoke", json={"token": token}).status_code == 404
        assert second.get("/api/share", params={"examId": exam["id"]}).json()["shares"] == []
        target = guest.get("/?copy=" + token, follow_redirects=False).headers["location"]
        assert target == "/login?copy=" + token
        first.post("/api/share/revoke", json={"token": token}).raise_for_status()
        assert guest.get("/s/" + token).status_code == 404


def test_change_during_render_is_not_published(tmp_path, exam, monkeypatch):
    from mach_backend import workspace_shares

    app = create_app(tmp_path)
    export = workspace_shares.export_file

    def render_and_change(*args):
        result = export(*args)
        value = app.state.store.get("state")["value"]
        value["exams"][0]["revision"] += 1
        app.state.store.put("state", value)
        return result

    monkeypatch.setattr(workspace_shares, "export_file", render_and_change)
    with TestClient(app, headers=ORIGIN) as client:
        seed(client, exam)
        assert create(client, exam).status_code == 409
        assert client.get("/api/share", params={"examId": exam["id"]}).json()["shares"] == []


@pytest.mark.parametrize("token", ["bad", "A" * 43, "A" * 44])
def test_unknown_or_malformed_link_returns_404(tmp_path, token):
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        assert client.get("/s/" + token).status_code == 404


@pytest.mark.parametrize(
    "kind,fields,label",
    [
        ("short", {"answerText": "DAP_AN_NGAN_42"}, "DAP_AN_NGAN_42"),
        (
            "truefalse",
            {"truthValues": [True, False, True, False]},
            "1. Đúng · 2. Sai · 3. Đúng · 4. Sai",
        ),
    ],
)
def test_teacher_snapshot_keeps_split_answers_but_student_cannot_read_them(
    exam, kind, fields, label
):
    from mach_backend.ai_questions import saved_answer_label

    q = exam["questions"][0]
    q.update(type=kind, answer=0, **fields)
    teacher = snapshot(exam, True)["questions"][0]
    assert saved_answer_label(teacher) == label
    student = snapshot(exam, False)["questions"][0]
    assert "answerText" not in student and "truthValues" not in student
    assert student["answer"] is None and not student["answerKnown"]
