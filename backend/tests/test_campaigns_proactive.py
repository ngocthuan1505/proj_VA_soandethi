"""Kiểm thử chiến dịch nhiều đề, nhắc lịch, Trợ lý Chủ động và sao lưu/khôi phục."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mach_backend.campaigns import (
    ensure_campaign_tables,
    install_campaign_routes,
    list_owner_campaigns,
    list_owner_reminders,
)
from mach_backend.workspace_backup import export_workspace_backup, restore
from mach_backend.workspace_store import WorkspaceStore


def _make_db_connect(db_path: Path):
    @contextmanager
    def connect():
        conn = sqlite3.connect(db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    return connect


def _build_test_app(
    tmp_path: Path,
    state_box: dict[str, Any],
) -> tuple[TestClient, Any]:
    db_path = tmp_path / "campaigns.sqlite"
    connect = _make_db_connect(db_path)
    app = FastAPI()

    def owner_resolver(request: Request) -> str:
        return request.headers.get("x-test-owner", "teacher-a")

    install_campaign_routes(
        app,
        connect,
        lambda: state_box["state"],
        owner_resolver=owner_resolver,
    )
    return TestClient(app), connect


def test_campaign_crud_link_exam_and_trash_exclusion(tmp_path: Path):
    state_box: dict[str, Any] = {
        "state": {
            "exams": [
                {"id": "ex-1", "title": "Đề 1", "questions": [{"id": "q1"}]},
                {"id": "ex-2", "title": "Đề 2", "questions": [{"id": "q2"}]},
                {"id": "ex-3", "title": "Đề 3", "questions": [{"id": "q3"}]},
            ],
            "trash": [],
        }
    }
    client, _ = _build_test_app(tmp_path, state_box)

    # Tạo chiến dịch 10 đề
    res = client.post(
        "/api/campaigns",
        json={
            "title": "Bộ 10 đề ôn tập Toán 9",
            "subject": "Toán",
            "grade": "9",
            "targetCount": 10,
            "examIds": ["ex-1"],
            "note": "Ôn thi vào 10",
        },
    )
    assert res.status_code == 201
    camp = res.json()["campaign"]
    cid = camp["id"]
    assert camp["completedCount"] == 1
    assert camp["remainingCount"] == 9
    assert camp["nextOrdinal"] == 2

    # Liên kết thêm đề 2 và đề 3
    r2 = client.post(f"/api/campaigns/{cid}/link-exam", json={"examId": "ex-2"})
    assert r2.status_code == 200
    assert r2.json()["campaign"]["completedCount"] == 2
    assert r2.json()["campaign"]["nextOrdinal"] == 3

    r3 = client.post(f"/api/campaigns/{cid}/link-exam", json={"examId": "ex-3"})
    assert r3.status_code == 200
    assert r3.json()["campaign"]["completedCount"] == 3
    assert r3.json()["campaign"]["remainingCount"] == 7
    assert r3.json()["campaign"]["nextOrdinal"] == 4

    # Chuyển ex-2 vào trash -> completedCount tự giảm còn 2
    state_box["state"]["trash"] = [{"id": "ex-2", "title": "Đề 2"}]
    listed = client.get("/api/campaigns")
    assert listed.status_code == 200
    c_after = listed.json()["campaigns"][0]
    assert c_after["completedCount"] == 2
    assert c_after["remainingCount"] == 8
    assert c_after["nextOrdinal"] == 3

    # Cập nhật PATCH
    patched = client.patch(
        f"/api/campaigns/{cid}", json={"targetCount": 5, "note": "Rút gọn còn 5 đề"}
    )
    assert patched.status_code == 200
    assert patched.json()["campaign"]["targetCount"] == 5
    assert patched.json()["campaign"]["remainingCount"] == 3

    # Xóa DELETE
    deleted = client.delete(f"/api/campaigns/{cid}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/api/campaigns").json()["campaigns"] == []


def test_owner_isolation_for_campaigns_and_reminders(tmp_path: Path):
    state_box = {"state": {"exams": [], "trash": []}}
    client, _ = _build_test_app(tmp_path, state_box)

    c_res = client.post(
        "/api/campaigns",
        headers={"x-test-owner": "owner-a"},
        json={"title": "Chiến dịch A", "targetCount": 4},
    )
    cid = c_res.json()["campaign"]["id"]

    r_res = client.post(
        "/api/reminders",
        headers={"x-test-owner": "owner-a"},
        json={"title": "Nộp đề tổ trưởng", "kind": "deadline"},
    )
    rid = r_res.json()["reminder"]["id"]

    # Owner B không thấy dữ liệu của Owner A
    assert (
        client.get("/api/campaigns", headers={"x-test-owner": "owner-b"}).json()["campaigns"] == []
    )
    assert (
        client.get("/api/reminders", headers={"x-test-owner": "owner-b"}).json()["reminders"] == []
    )
    assert (
        client.patch(
            f"/api/campaigns/{cid}", headers={"x-test-owner": "owner-b"}, json={"title": "Hack"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/campaigns/{cid}/link-exam",
            headers={"x-test-owner": "owner-b"},
            json={"examId": "ex-1"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/campaigns/{cid}", headers={"x-test-owner": "owner-b"}).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/reminders/{rid}", headers={"x-test-owner": "owner-b"}, json={"done": True}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/reminders/{rid}", headers={"x-test-owner": "owner-b"}).status_code
        == 404
    )


def test_reminders_done_and_snooze(tmp_path: Path):
    state_box = {"state": {"exams": [], "trash": []}}
    client, _ = _build_test_app(tmp_path, state_box)
    now_ms = 1_760_000_000_000

    created = client.post(
        "/api/reminders",
        json={
            "title": "Rà lại đề Hóa 10",
            "kind": "review",
            "targetType": "exam",
            "targetId": "ex-hoa",
            "remindAt": now_ms + 3_600_000,
        },
    )
    assert created.status_code == 201
    rid = created.json()["reminder"]["id"]

    # Snooze 4 giờ
    snoozed = client.patch(f"/api/reminders/{rid}", json={"snoozeHours": 4})
    assert snoozed.status_code == 200
    assert snoozed.json()["reminder"]["snoozedUntil"] is not None

    # Done
    done_res = client.patch(f"/api/reminders/{rid}", json={"done": True})
    assert done_res.status_code == 200
    assert done_res.json()["reminder"]["done"] is True
    assert done_res.json()["reminder"]["doneAt"] is not None

    # includeDone=false không trả nhắc đã xong
    active_only = client.get("/api/reminders?includeDone=false")
    assert active_only.json()["reminders"] == []


def test_proactive_digest_all_four_signals(tmp_path: Path):
    now_ms = 1_760_100_000_000  # mốc cố định deterministic
    hour_ms = 3_600_000
    state_box: dict[str, Any] = {
        "state": {
            "exams": [
                {
                    "id": "ex-1",
                    "title": "Đề 1 Toán 9",
                    "subject": "Toán",
                    "grade": "9",
                    "updated": now_ms
                    - 24 * hour_ms,  # 24h trước, có câu draft -> kích hoạt nhắc rà soát
                    "questions": [
                        {"id": "q1", "stem": "Câu 1", "approvalStatus": "draft"},
                        {"id": "q2", "stem": "Câu 2", "approvalStatus": "approved"},
                    ],
                },
                {
                    "id": "ex-2",
                    "title": "Đề 2 Toán 9",
                    "subject": "Toán",
                    "grade": "9",
                    "updated": now_ms - 2 * hour_ms,  # mới sửa 2h trước -> chưa nhắc
                    "questions": [{"id": "q3", "stem": "Câu 3", "approvalStatus": "draft"}],
                },
                {
                    "id": "ex-3",
                    "title": "Đề 3 đã duyệt xong",
                    "subject": "Toán",
                    "grade": "9",
                    "updated": now_ms - 30 * hour_ms,
                    "questions": [{"id": "q4", "stem": "Câu 4", "approvalStatus": "approved"}],
                },
            ],
            "trash": [],
        }
    }
    client, connect = _build_test_app(tmp_path, state_box)

    # Tạo chiến dịch 10 đề đã xong 3 đề, sắp đến hạn trong 12 giờ
    client.post(
        "/api/campaigns",
        json={
            "title": "Bộ 10 đề ôn tập Toán 9",
            "subject": "Toán",
            "grade": "9",
            "targetCount": 10,
            "examIds": ["ex-1", "ex-2", "ex-3"],
            "dueAt": now_ms + 12 * hour_ms,
        },
    )

    # Tạo 1 nhắc lịch quá hạn và 1 nhắc lịch bị snooze
    client.post(
        "/api/reminders",
        json={"title": "In đề cho lớp 9A", "kind": "deadline", "remindAt": now_ms - 2 * hour_ms},
    )
    snoozed_r = client.post(
        "/api/reminders",
        json={"title": "Nhắc đã hoãn", "kind": "general", "remindAt": now_ms + hour_ms},
    ).json()["reminder"]
    with connect() as db:
        db.execute(
            "UPDATE teacher_reminders SET snoozed_until = ? WHERE id = ?",
            (now_ms + 10 * hour_ms, snoozed_r["id"]),
        )

    # Kiểm tra trước khi có bảng exam_rooms -> pendingRoomGrading an toàn = 0
    digest1 = client.get(f"/api/proactive/digest?reviewThresholdHours=18&nowMs={now_ms}").json()
    assert digest1["pendingRoomGrading"] == {"count": 0, "rooms": []}
    assert len(digest1["activeCampaigns"]) == 1
    assert digest1["activeCampaigns"][0]["message"] == "Đã xong 3/10 đề — Bấm soạn tiếp đề 4"
    assert len(digest1["nextDayReviewNudges"]) == 1
    assert digest1["nextDayReviewNudges"][0]["examId"] == "ex-1"
    assert digest1["nextDayReviewNudges"][0]["draftQuestionCount"] == 1
    assert (
        len(digest1["urgentDeadlines"]) == 2
    )  # 1 campaign due in 12h + 1 overdue reminder (snoozed excluded)
    assert digest1["urgentDeadlines"][0]["overdue"] is True
    assert digest1["badgeCount"] == 4
    assert "thầy cô" in digest1["greeting"]

    # Bổ sung bảng exam_rooms & room_attempts có 2 bài tự luận chờ chấm
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE exam_rooms (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, title TEXT NOT NULL,
                room_code TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE room_attempts (
                id TEXT PRIMARY KEY, room_id TEXT NOT NULL,
                status TEXT NOT NULL, grading_status TEXT NOT NULL
            );
            INSERT INTO exam_rooms VALUES ('r1', 'teacher-a', 'Phòng Toán 9A', 'ABC234', 1000);
            INSERT INTO room_attempts VALUES ('a1', 'r1', 'submitted', 'needs_manual');
            INSERT INTO room_attempts VALUES ('a2', 'r1', 'auto_submitted', 'needs_manual');
            INSERT INTO room_attempts VALUES ('a3', 'r1', 'submitted', 'graded');
            """
        )

    digest2 = client.get(f"/api/proactive/digest?reviewThresholdHours=18&nowMs={now_ms}").json()
    assert digest2["pendingRoomGrading"]["count"] == 2
    assert digest2["pendingRoomGrading"]["rooms"][0]["roomCode"] == "ABC234"
    assert digest2["badgeCount"] == 5


def test_workspace_backup_and_restore_campaigns_and_reminders(tmp_path: Path):
    src_store = WorkspaceStore(tmp_path / "src", owner="local")
    src_store.put(
        "state",
        {
            "current": "ex-1",
            "prefs": [],
            "exams": [
                {
                    "id": "ex-1",
                    "title": "Đề Toán 11",
                    "questions": [
                        {
                            "id": "q1",
                            "type": "mcq",
                            "stem": "1 + 1 = ?",
                            "options": ["1", "2", "3", "4"],
                            "answer": 1,
                            "level": 0,
                        }
                    ],
                    "docs": [],
                    "matrix": [],
                    "history": [],
                    "undo": [],
                    "redo": [],
                    "chat": [],
                    "data": [],
                    "quote": {"text": "", "versions": []},
                }
            ],
        },
        0,
    )
    with src_store.connect() as db:
        ensure_campaign_tables(db)
        db.execute(
            """
            INSERT INTO exam_campaigns (
                id, owner_id, title, subject, grade, target_count, exam_ids_json,
                due_at, status, note, created_at, updated_at
            ) VALUES ('camp-1', 'local', 'Bộ 5 đề Toán 11', 'Toán', '11', 5, '["ex-1"]',
                      NULL, 'active', 'Ghi chú', 1000, 2000)
            """
        )
        db.execute(
            """
            INSERT INTO teacher_reminders (
                id, owner_id, title, kind, target_type, target_id,
                remind_at, snoozed_until, done_at, created_at
            ) VALUES ('rem-1', 'local', 'Kiểm tra đáp án câu 1', 'review', 'exam', 'ex-1',
                      3000, NULL, NULL, 1000)
            """
        )

    snapshot = export_workspace_backup(src_store)
    assert len(snapshot["examCampaigns"]) == 1
    assert snapshot["examCampaigns"][0]["id"] == "camp-1"
    assert len(snapshot["teacherReminders"]) == 1
    assert snapshot["teacherReminders"][0]["id"] == "rem-1"

    dst_store = WorkspaceStore(tmp_path / "dst", owner="local")
    result = restore(dst_store, snapshot, 0)
    assert result["restored"] is True

    with dst_store.connect() as db:
        restored_camps = list_owner_campaigns(db, "local")
        restored_rems = list_owner_reminders(db, "local")
    assert len(restored_camps) == 1
    assert restored_camps[0]["title"] == "Bộ 5 đề Toán 11"
    assert restored_camps[0]["examIds"] == ["ex-1"]
    assert len(restored_rems) == 1
    assert restored_rems[0]["title"] == "Kiểm tra đáp án câu 1"
