"""Kiểm thử toàn diện cho module phòng thi trực tuyến và BTVN exam_rooms.py."""

from __future__ import annotations

import base64
import io
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from mach_backend.exam_rooms import (
    ROOM_CODE_RE,
    install_exam_rooms,
    is_public_room_path,
)
from mach_backend.tnmaker_export import _build_qr_matrix


def _sample_exam() -> dict[str, Any]:
    data_wav = base64.b64encode(b"RIFF\x24\x00\x00\x00WAVEfmt ").decode("ascii")
    return {
        "id": "exam-demo-1",
        "revision": 3,
        "title": "Kiểm tra giữa kỳ I — Tổng hợp",
        "subject": "Toán",
        "grade": "9",
        "minutes": 45,
        "passages": [
            {
                "id": "pass-1",
                "title": "Đoạn nghe hiểu",
                "text": "Nghe đoạn hội thoại và chọn phương án đúng.",
                "audio": {
                    "fileId": "aud-inline-1",
                    "filename": "listening_part1.wav",
                    "maxPlays": 2,
                    "dataUri": f"data:audio/wav;base64,{data_wav}",
                },
            }
        ],
        "questions": [
            {
                "id": "q-mcq-1",
                "type": "mcq",
                "points": 1.0,
                "stem": "Giá trị của $2 + 3$ bằng bao nhiêu?",
                "options": ["3", "4", "5", "6"],
                "answer": 2,
                "answerKnown": True,
                "explanation": "Vì $2 + 3 = 5$.",
                "passageId": "pass-1",
                "audio": {
                    "fileId": "aud-cb-1",
                    "filename": "clip_q1.mp3",
                    "maxPlays": 2,
                },
            },
            {
                "id": "q-tf-1",
                "type": "truefalse",
                "points": 1.0,
                "stem": "Xét tính đúng sai của 4 khẳng định sau:",
                "options": ["1+1=2", "2+2=5", "3*3=9", "4-1=0"],
                "truthValues": [True, False, True, False],
                "answerKnown": True,
                "explanation": "Khẳng định a và c đúng; b và d sai.",
            },
            {
                "id": "q-short-1",
                "type": "short",
                "points": 1.0,
                "stem": "Tính $3 / 2$ viết dưới dạng số thập phân:",
                "answerText": "1,5",
                "answerKnown": True,
                "explanation": "$3 / 2 = 1{,}5$.",
            },
            {
                "id": "q-short-2",
                "type": "short",
                "points": 0.5,
                "stem": "Nghiệm âm hoặc tên chất:",
                "answerText": "-3;Hai rưỡi|2.5",
                "answerKnown": True,
                "explanation": "Đáp án đúng là $-3$, Hai rưỡi hoặc $2{,}5$.",
            },
            {
                "id": "q-essay-1",
                "type": "essay",
                "points": 2.0,
                "stem": "Giải thích quy tắc biến đổi biểu thức.",
                "explanation": "Nêu đủ 2 bước lập luận.",
                "rubric": [
                    {"id": "r1", "text": "Nêu đúng điều kiện xác định", "points": 1.0},
                    {"id": "r2", "text": "Biến đổi rút gọn chính xác", "points": 1.0},
                ],
            },
        ],
    }


def _build_test_harness(
    tmp_path: Path,
    *,
    row_factory: Any = None,
    exams_by_owner: dict[str, dict[str, dict[str, Any]]] | None = None,
    file_store: dict[str, tuple[bytes, str]] | None = None,
) -> dict[str, Any]:
    db_path = tmp_path / "rooms.sqlite3"
    clock_state = {"now": 1_730_000_000.0}
    exams = exams_by_owner or {
        "teacher-a": {"exam-demo-1": _sample_exam()},
        "teacher-b": {"exam-other": deepcopy(_sample_exam())},
    }
    files = file_store or {"aud-cb-1": (b"ID3\x03\x00\x00\x00\x00\x00\x00FAKE_MP3", "audio/mpeg")}

    @contextmanager
    def connect():
        conn = sqlite3.connect(db_path, timeout=5)
        if row_factory is not None:
            conn.row_factory = row_factory
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def owner_resolver(request: Request) -> str:
        return request.headers.get("X-Test-Owner", "")

    def read_exam(request: Request, exam_id: str) -> dict[str, Any]:
        uid = owner_resolver(request)
        owner_exams = exams.get(uid, {})
        if exam_id not in owner_exams:
            raise HTTPException(404, "Không tìm thấy đề thi.")
        return deepcopy(owner_exams[exam_id])

    def read_file_bytes(file_id: str, owner_id: str) -> tuple[bytes, str] | None:
        return files.get(file_id)

    app = FastAPI()
    install_exam_rooms(
        app,
        connect,
        owner_resolver,
        read_exam,
        read_file_bytes=read_file_bytes,
        clock=lambda: clock_state["now"],
    )
    client = TestClient(app)
    return {
        "client": client,
        "clock": clock_state,
        "db_path": db_path,
        "exams": exams,
    }


def _teacher_headers(owner: str = "teacher-a") -> dict[str, str]:
    return {"X-Test-Owner": owner}


def _student_headers(token: str) -> dict[str, str]:
    return {"X-Attempt-Token": token}


def test_is_public_room_path_allowlist_and_traversal() -> None:
    assert is_public_room_path("/phong-thi") is True
    assert is_public_room_path("/phong-thi/K7M9P2") is True
    assert is_public_room_path("/api/rooms/public/K7M9P2") is True
    assert is_public_room_path("/api/rooms/public/K7M9P2/join") is True
    assert is_public_room_path("/api/rooms/public/attempts/att-1/answers") is True
    assert is_public_room_path("/assets/exam-room.html") is True
    assert is_public_room_path("/assets/exam-room.css") is True
    assert is_public_room_path("/assets/exam-room.js") is True
    assert is_public_room_path("/assets/exam-icon.svg") is True
    assert is_public_room_path("/assets/katex/katex.min.css") is True
    assert is_public_room_path("/assets/katex/contrib/auto-render.min.js") is True

    # Reject non-public, traversal, percent-encoding, and teacher API paths
    assert is_public_room_path("/phong-thi/") is False
    assert is_public_room_path("/phong-thi/../api/kv") is False
    assert is_public_room_path("/phong-thi/%2e%2e/api/kv") is False
    assert is_public_room_path("/phong-thi/abc/extra") is False
    assert is_public_room_path("/assets/katex/../team-login.js") is False
    assert is_public_room_path("/assets/katex/") is False
    assert is_public_room_path("/api/rooms") is False
    assert is_public_room_path("/api/rooms/room-123") is False
    assert is_public_room_path("/api/kv") is False
    assert is_public_room_path("/core.js") is False


def test_student_portal_html_routes_and_katex_only(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    for route in ("/phong-thi", "/phong-thi/K7M9P2"):
        res = client.get(route)
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        html = res.text
        assert "/assets/katex/katex.min.css" in html
        assert "/assets/katex/katex.min.js" in html
        assert "/assets/katex/contrib/mhchem.min.js" in html
        assert "/assets/katex/contrib/auto-render.min.js" in html
        assert "/assets/exam-room.css" in html
        assert "/assets/exam-room.js" in html
        lower = html.lower()
        assert "tiptap" not in lower
        assert "mathlive" not in lower

    bad = client.get("/phong-thi/bad$code")
    assert bad.status_code == 404


def test_teacher_auth_crud_and_cross_owner_isolation(tmp_path: Path) -> None:
    # Also exercise sqlite3.Row row_factory like TeamAccounts.connect()
    harness = _build_test_harness(tmp_path, row_factory=sqlite3.Row)
    client: TestClient = harness["client"]

    # Unauthenticated requests fail with 401
    assert client.post("/api/rooms", json={"examId": "exam-demo-1"}).status_code == 401
    assert client.get("/api/rooms").status_code == 401

    created_res = client.post(
        "/api/rooms",
        headers=_teacher_headers("teacher-a"),
        json={
            "examId": "exam-demo-1",
            "mode": "exam",
            "classLabel": "9A1",
            "allowLan": True,
            "durationMinutes": 30,
            "pin": "2025",
            "resultPolicy": "score_only",
        },
    )
    assert created_res.status_code == 201
    room = created_res.json()
    assert ROOM_CODE_RE.fullmatch(room["roomCode"])
    for ambig in ("0", "O", "1", "I", "L"):
        assert ambig not in room["roomCode"]
    assert room["requiresPin"] is True
    assert room["allowLan"] is True
    assert room["totalPointsP100"] == 550  # 1.0 + 1.0 + 1.0 + 0.5 + 2.0

    room_id = room["id"]

    # Missing examId -> 404
    missing_exam = client.post(
        "/api/rooms",
        headers=_teacher_headers("teacher-a"),
        json={"examId": "does-not-exist"},
    )
    assert missing_exam.status_code == 404

    # Cross-owner teacher-b gets 404 on every endpoint
    assert (
        client.get(f"/api/rooms/{room_id}", headers=_teacher_headers("teacher-b")).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/rooms/{room_id}",
            headers=_teacher_headers("teacher-b"),
            json={"status": "closed"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/rooms/{room_id}/grading-queue", headers=_teacher_headers("teacher-b")
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/rooms/{room_id}/analytics", headers=_teacher_headers("teacher-b")
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/rooms/{room_id}/export.xlsx", headers=_teacher_headers("teacher-b")
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/rooms/{room_id}/qr.svg", headers=_teacher_headers("teacher-b")
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/rooms/{room_id}", headers=_teacher_headers("teacher-b")).status_code
        == 404
    )

    # Teacher A lists, patches, and deletes
    listed = client.get("/api/rooms", headers=_teacher_headers("teacher-a"))
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()["rooms"]] == [room_id]

    patched = client.patch(
        f"/api/rooms/{room_id}",
        headers=_teacher_headers("teacher-a"),
        json={"status": "closed", "title": "Đề cập nhật"},
    )
    assert patched.status_code == 200
    assert patched.json()["room"]["status"] == "closed"
    assert patched.json()["room"]["title"] == "Đề cập nhật"

    deleted = client.delete(f"/api/rooms/{room_id}", headers=_teacher_headers("teacher-a"))
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert (
        client.get(f"/api/rooms/{room_id}", headers=_teacher_headers("teacher-a")).status_code
        == 404
    )


def test_public_metadata_join_security_and_zero_leak(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]
    now_ms = int(harness["clock"]["now"] * 1000)

    res = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-demo-1",
            "pin": "9876",
            "maxAttempts": 1,
            "opensAt": now_ms + 60_000,
            "deadlineAt": now_ms + 300_000,
            "shuffleQuestions": True,
            "shuffleOptions": True,
        },
    )
    assert res.status_code == 201
    room = res.json()
    code = room["roomCode"]

    # Public metadata requires NO auth and never returns questions or keys
    pub = client.get(f"/api/rooms/public/{code}")
    assert pub.status_code == 200
    pub_json = pub.json()
    assert pub_json["roomCode"] == code
    assert pub_json["requiresPin"] is True
    assert "questions" not in pub_json
    assert "teacher_snapshot_json" not in pub_json
    assert "pinHash" not in pub_json

    # Before opensAt -> 403
    early = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Nguyễn Văn An", "pin": "9876"},
    )
    assert early.status_code == 403

    # Advance into window, wrong PIN -> 403
    harness["clock"]["now"] += 120.0
    wrong_pin = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Nguyễn Văn An", "pin": "0000"},
    )
    assert wrong_pin.status_code == 403

    # Correct PIN -> 201 + fully redacted student exam
    ok = client.post(
        f"/api/rooms/public/{code}/join",
        json={
            "studentName": "Nguyễn Văn An",
            "studentCode": "HS01",
            "studentClass": "9A1",
            "pin": "9876",
        },
    )
    assert ok.status_code == 201
    joined = ok.json()
    assert joined["attemptToken"]
    delivered_exam = joined["exam"]
    for q in delivered_exam["questions"]:
        assert q.get("answer") is None
        assert q.get("answerKnown") is False
        for leaked_key in (
            "answerText",
            "truthValues",
            "explanation",
            "explanationDoc",
            "rubric",
            "solution",
        ):
            assert leaked_key not in q
        if "audio" in q and q["audio"]:
            assert "dataUri" not in q["audio"]
            assert "dataUrl" not in q["audio"]
            assert "src" not in q["audio"]
            assert q["audio"]["url"].endswith(f"/audio/{q['audio']['fileId']}")
    for p in delivered_exam.get("passages") or []:
        if "audio" in p and p["audio"]:
            assert "dataUri" not in p["audio"]

    # Exceeding maxAttempts=1 -> 403
    second = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Nguyễn Văn An", "studentCode": "HS01", "pin": "9876"},
    )
    assert second.status_code == 403

    # Past deadline -> 403
    harness["clock"]["now"] += 500.0
    late = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Trần Bình", "studentCode": "HS02", "pin": "9876"},
    )
    assert late.status_code == 403


def test_exact_p100_grading_mcq_shuffled_cv7991_tf_and_short(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-demo-1",
            "shuffleQuestions": True,
            "shuffleOptions": True,
            "maxAttempts": 10,
            "resultPolicy": "score_and_answers",
        },
    ).json()
    code = room["roomCode"]

    # Join once to test shuffled MCQ + Short variations + TF=4/4
    j_full = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "HS Đạt Đủ", "studentCode": "S1"},
    ).json()
    aid_full = j_full["attemptId"]
    tok_full = j_full["attemptToken"]
    q_by_id = {q["id"]: q for q in j_full["exam"]["questions"]}
    # Original correct option for q-mcq-1 is "5" (index 2 in original)
    shuffled_mcq_idx = q_by_id["q-mcq-1"]["options"].index("5")

    sub_full = client.post(
        f"/api/rooms/public/attempts/{aid_full}/submit",
        headers=_student_headers(tok_full),
        json={
            "answers": {
                "q-mcq-1": shuffled_mcq_idx,  # 100 p100
                "q-tf-1": [True, False, True, False],  # 4/4 -> 100 p100
                "q-short-1": " 1.50 ",  # numeric equiv to 1,5 -> 100 p100
                "q-short-2": "HAI   rưỡi",  # multi-key text match -> 50 p100
            }
        },
    )
    assert sub_full.status_code == 200
    res_full = client.get(
        f"/api/rooms/public/attempts/{aid_full}/result",
        headers=_student_headers(tok_full),
    ).json()
    assert res_full["autoScoreP100"] == 350
    assert res_full["gradingStatus"] == "needs_manual"
    # score_and_answers maps MCQ correctAnswer back into this student's shuffled option index!
    mcq_res = next(q for q in res_full["questions"] if q["questionId"] == "q-mcq-1")
    assert mcq_res["correctAnswer"] == shuffled_mcq_idx
    assert mcq_res["earnedPointsP100"] == 100
    assert "explanation" not in mcq_res

    # Test ALL 5 CV 7991 True/False match counts (0, 1, 2, 3, 4 -> 0, 10, 25, 50, 100 p100)
    # and Unicode minus + decimal comma on short answer
    tf_cases = [
        ([False, True, False, True], 0),  # 0 matches -> 0
        ([True, True, False, True], 10),  # 1 match -> 10
        ([True, False, False, True], 25),  # 2 matches -> 25
        ([True, False, True, True], 50),  # 3 matches -> 50
        ([True, False, True, False], 100),  # 4 matches -> 100
    ]
    for idx, (tf_resp, expected_tf_p100) in enumerate(tf_cases):
        j = client.post(
            f"/api/rooms/public/{code}/join",
            json={"studentName": f"HS TF {idx}", "studentCode": f"TF{idx}"},
        ).json()
        aid = j["attemptId"]
        tok = j["attemptToken"]
        client.post(
            f"/api/rooms/public/attempts/{aid}/submit",
            headers=_student_headers(tok),
            json={
                "answers": {
                    "q-tf-1": tf_resp,
                    "q-short-1": "1.51",  # wrong -> 0
                    "q-short-2": "\u22123,0",  # Unicode minus −3,0 == -3 -> 50 p100
                }
            },
        )
        r = client.get(
            f"/api/rooms/public/attempts/{aid}/result",
            headers=_student_headers(tok),
        ).json()
        tf_item = next(q for q in r["questions"] if q["questionId"] == "q-tf-1")
        s1_item = next(q for q in r["questions"] if q["questionId"] == "q-short-1")
        s2_item = next(q for q in r["questions"] if q["questionId"] == "q-short-2")
        assert tf_item["earnedPointsP100"] == expected_tf_p100
        assert s1_item["earnedPointsP100"] == 0
        assert s2_item["earnedPointsP100"] == 50


def test_essay_grading_queue_and_atomic_score_updates(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-demo-1",
            "resultPolicy": "full_explanation",
        },
    ).json()
    room_id = room["id"]
    code = room["roomCode"]

    joined = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Lê Minh", "studentCode": "LM01"},
    ).json()
    aid = joined["attemptId"]
    tok = joined["attemptToken"]

    client.post(
        f"/api/rooms/public/attempts/{aid}/submit",
        headers=_student_headers(tok),
        json={
            "answers": {
                "q-mcq-1": 2,
                "q-tf-1": [True, False, True, False],
                "q-short-1": "1,5",
                "q-short-2": "-3",
                "q-essay-1": "Điều kiện x khác 0, sau đó rút gọn được kết quả.",
            }
        },
    )

    queue = client.get(f"/api/rooms/{room_id}/grading-queue", headers=_teacher_headers()).json()
    assert queue["pendingCount"] == 1
    assert queue["gradedCount"] == 0
    assert len(queue["items"]) == 1
    item = queue["items"][0]
    assert item["questionId"] == "q-essay-1"
    assert item["maxPointsP100"] == 200

    # Reject out-of-range grades
    bad_over = client.put(
        f"/api/rooms/{room_id}/attempts/{aid}/grades/q-essay-1",
        headers=_teacher_headers(),
        json={"earnedPointsP100": 250},
    )
    assert bad_over.status_code == 422

    bad_neg = client.put(
        f"/api/rooms/{room_id}/attempts/{aid}/grades/q-essay-1",
        headers=_teacher_headers(),
        json={"earnedPointsP100": -10},
    )
    assert bad_neg.status_code == 422

    # Valid manual grade
    graded = client.put(
        f"/api/rooms/{room_id}/attempts/{aid}/grades/q-essay-1",
        headers=_teacher_headers(),
        json={"earnedPointsP100": 175, "graderNote": "Lập luận rõ ràng"},
    )
    assert graded.status_code == 200
    g_data = graded.json()
    assert g_data["earnedPointsP100"] == 175
    assert g_data["autoScoreP100"] == 350
    assert g_data["manualScoreP100"] == 175
    assert g_data["totalScoreP100"] == 525
    assert g_data["gradingStatus"] == "graded"

    queue_after = client.get(
        f"/api/rooms/{room_id}/grading-queue", headers=_teacher_headers()
    ).json()
    assert queue_after["pendingCount"] == 0
    assert queue_after["gradedCount"] == 1

    # Full explanation result reflects grade & note
    res = client.get(
        f"/api/rooms/public/attempts/{aid}/result",
        headers=_student_headers(tok),
    ).json()
    assert res["totalScoreP100"] == 525
    essay_item = next(q for q in res["questions"] if q["questionId"] == "q-essay-1")
    assert essay_item["earnedPointsP100"] == 175
    assert essay_item["graderNote"] == "Lập luận rõ ràng"
    assert essay_item["explanation"] == "Nêu đủ 2 bước lập luận."
    assert len(essay_item["rubric"]) == 2


def test_anti_cheat_auto_lock_and_teacher_lock(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={"examId": "exam-demo-1", "maxTabSwitches": 2, "requireFullscreen": True},
    ).json()
    room_id = room["id"]
    code = room["roomCode"]

    # Student 1: exceeds maxTabSwitches (2 allowed, 3rd auto-locks)
    s1 = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Phạm An"},
    ).json()
    aid1, tok1 = s1["attemptId"], s1["attemptToken"]
    client.put(
        f"/api/rooms/public/attempts/{aid1}/answers",
        headers=_student_headers(tok1),
        json={"answers": {"q-mcq-1": 2}},
    )

    e1 = client.post(
        f"/api/rooms/public/attempts/{aid1}/events",
        headers=_student_headers(tok1),
        json={"eventType": "tab_hidden"},
    ).json()
    assert e1["autoLocked"] is False
    assert e1["tabSwitchCount"] == 1

    e2 = client.post(
        f"/api/rooms/public/attempts/{aid1}/events",
        headers=_student_headers(tok1),
        json={"eventType": "window_blur"},
    ).json()
    assert e2["autoLocked"] is False
    assert e2["tabSwitchCount"] == 2

    e3 = client.post(
        f"/api/rooms/public/attempts/{aid1}/events",
        headers=_student_headers(tok1),
        json={"eventType": "tab_hidden"},
    ).json()
    assert e3["autoLocked"] is True
    assert e3["status"] == "locked"
    assert e3["tabSwitchCount"] == 3

    # Late answer write returns 409 after auto-lock
    late_put = client.put(
        f"/api/rooms/public/attempts/{aid1}/answers",
        headers=_student_headers(tok1),
        json={"answers": {"q-short-1": "1,5"}},
    )
    assert late_put.status_code == 409

    # Student 2: teacher locks manually
    s2 = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Phạm Bình"},
    ).json()
    aid2 = s2["attemptId"]
    lock_res = client.post(
        f"/api/rooms/{room_id}/attempts/{aid2}/lock",
        headers=_teacher_headers(),
        json={"reason": "vi_pham_noi_quy"},
    )
    assert lock_res.status_code == 200
    assert lock_res.json()["attempt"]["status"] == "locked"


def test_release_results_after_close_and_result_policies(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-demo-1",
            "resultPolicy": "score_only",
            "releaseResultsAfterClose": True,
        },
    ).json()
    room_id = room["id"]
    code = room["roomCode"]

    s = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Trần Hà"},
    ).json()
    aid, tok = s["attemptId"], s["attemptToken"]
    client.post(
        f"/api/rooms/public/attempts/{aid}/submit",
        headers=_student_headers(tok),
        json={"answers": {"q-mcq-1": 2}},
    )

    # While open -> zero score or answer leak
    hidden_open = client.get(
        f"/api/rooms/public/attempts/{aid}/result",
        headers=_student_headers(tok),
    ).json()
    assert hidden_open["resultsAvailable"] is False
    assert "totalScoreP100" not in hidden_open
    assert "questions" not in hidden_open

    # Close room -> score_only unlocks scores without correct answers
    client.patch(
        f"/api/rooms/{room_id}",
        headers=_teacher_headers(),
        json={"status": "closed"},
    )
    after_close = client.get(
        f"/api/rooms/public/attempts/{aid}/result",
        headers=_student_headers(tok),
    ).json()
    assert after_close["resultsAvailable"] is True
    assert after_close["autoScoreP100"] == 100
    for q in after_close["questions"]:
        assert "correctAnswer" not in q
        assert "explanation" not in q

    # Policy 'hidden' stays hidden even after room close
    client.patch(
        f"/api/rooms/{room_id}",
        headers=_teacher_headers(),
        json={"resultPolicy": "hidden"},
    )
    still_hidden = client.get(
        f"/api/rooms/public/attempts/{aid}/result",
        headers=_student_headers(tok),
    ).json()
    assert still_hidden["resultsAvailable"] is False
    assert "totalScoreP100" not in still_hidden


def test_audio_streaming_and_max_plays_enforcement(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={"examId": "exam-demo-1"},
    ).json()
    joined = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "Nghe Hiểu"},
    ).json()
    aid = joined["attemptId"]
    tok = joined["attemptToken"]

    # Callback-backed audio (aud-cb-1, maxPlays=2)
    p1 = client.get(
        f"/api/rooms/public/attempts/{aid}/audio/aud-cb-1",
        headers=_student_headers(tok),
    )
    assert p1.status_code == 200
    assert p1.headers["X-Audio-Plays-Used"] == "1"
    assert p1.headers["X-Audio-Plays-Remaining"] == "1"
    assert p1.content.startswith(b"ID3")

    p2 = client.get(
        f"/api/rooms/public/attempts/{aid}/audio/aud-cb-1",
        headers=_student_headers(tok),
    )
    assert p2.status_code == 200
    assert p2.headers["X-Audio-Plays-Used"] == "2"
    assert p2.headers["X-Audio-Plays-Remaining"] == "0"

    p3 = client.get(
        f"/api/rooms/public/attempts/{aid}/audio/aud-cb-1",
        headers=_student_headers(tok),
    )
    assert p3.status_code == 403

    # Inline dataUri fallback on passage audio (aud-inline-1)
    inline_play = client.get(
        f"/api/rooms/public/attempts/{aid}/audio/aud-inline-1",
        headers=_student_headers(tok),
    )
    assert inline_play.status_code == 200
    assert inline_play.content.startswith(b"RIFF")

    # Foreign fileId not attached to this exam -> 404
    foreign = client.get(
        f"/api/rooms/public/attempts/{aid}/audio/not-in-exam",
        headers=_student_headers(tok),
    )
    assert foreign.status_code == 404


def test_timer_expiration_xlsx_export_and_qr_svg(tmp_path: Path) -> None:
    harness = _build_test_harness(tmp_path)
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={"examId": "exam-demo-1", "durationMinutes": 10},
    ).json()
    room_id = room["id"]
    code = room["roomCode"]

    joined = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Vũ Hạnh", "studentCode": "VH09", "studentClass": "9A2"},
    ).json()
    aid = joined["attemptId"]
    tok = joined["attemptToken"]
    client.put(
        f"/api/rooms/public/attempts/{aid}/answers",
        headers=_student_headers(tok),
        json={"answers": {"q-mcq-1": 2}},
    )

    # Advance fake clock past 10 minutes -> auto_submitted
    harness["clock"]["now"] += 700.0
    late_write = client.put(
        f"/api/rooms/public/attempts/{aid}/answers",
        headers=_student_headers(tok),
        json={"answers": {"q-short-1": "1,5"}},
    )
    assert late_write.status_code == 409

    detail = client.get(f"/api/rooms/{room_id}", headers=_teacher_headers()).json()
    assert detail["attempts"][0]["status"] == "auto_submitted"
    assert detail["attempts"][0]["autoScoreP100"] == 100

    # Export .xlsx -> valid OOXML zip with BangDiem + ThongKeCauHoi sheets
    xlsx_res = client.get(f"/api/rooms/{room_id}/export.xlsx", headers=_teacher_headers())
    assert xlsx_res.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        in xlsx_res.headers["content-type"]
    )
    with zipfile.ZipFile(io.BytesIO(xlsx_res.content), "r") as zf:
        names = set(zf.namelist())
        assert {
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
        }.issubset(names)
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
        assert "BangDiem" in wb_xml
        assert "ThongKeCauHoi" in wb_xml
        sheet1 = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "Vũ Hạnh" in sheet1
        assert "VH09" in sheet1
        ET.fromstring(sheet1)
        sheet2 = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
        assert "q-mcq-1" in sheet2
        ET.fromstring(sheet2)

    # Export .svg QR -> valid ISO 18004 SVG matching tnmaker matrix size
    qr_res = client.get(
        f"/api/rooms/{room_id}/qr.svg",
        params={"baseUrl": "https://school.local"},
        headers=_teacher_headers(),
    )
    assert qr_res.status_code == 200
    assert "image/svg+xml" in qr_res.headers["content-type"]
    svg_root = ET.fromstring(qr_res.text)
    assert svg_root.tag.endswith("svg")
    _, qr_size = _build_qr_matrix(f"https://school.local/phong-thi/{code}")
    assert qr_size >= 21
    assert f"0 0 {qr_size + 8} {qr_size + 8}" == svg_root.attrib["viewBox"]


def test_analytics_max_score_not_shadowed_and_top_level_exam_audio(tmp_path: Path) -> None:
    exam = _sample_exam()
    exam["audio"] = {
        "fileId": "aud-top-1",
        "filename": "nghe-chung.mp3",
        "maxPlays": 2,
    }
    harness = _build_test_harness(
        tmp_path,
        exams_by_owner={"teacher-a": {"exam-demo-1": exam}},
        file_store={
            "aud-top-1": (b"ID3\x03\x00\x00\x00\x00\x00\x00TOP_MP3", "audio/mpeg"),
            "aud-cb-1": (b"ID3\x03\x00\x00\x00\x00\x00\x00FAKE_MP3", "audio/mpeg"),
        },
    )
    client: TestClient = harness["client"]

    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={"examId": "exam-demo-1", "durationMinutes": 30},
    ).json()
    room_id = room["id"]
    code = room["roomCode"]

    # HS1 đạt 300 p100 (> câu cuối q-essay-1 200 p100) để chắc chắn maxScoreP100 không bị ghi đè
    s1 = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "An", "studentCode": "HS01", "studentClass": "9A"},
    ).json()
    assert s1["exam"]["audio"]["fileId"] == "aud-top-1"
    assert s1["exam"]["audio"]["maxPlays"] == 2
    assert s1["exam"]["audio"]["playsUsed"] == 0

    for _ in range(2):
        play = client.get(
            f"/api/rooms/public/attempts/{s1['attemptId']}/audio/aud-top-1",
            headers=_student_headers(s1["attemptToken"]),
        )
        assert play.status_code == 200
    assert (
        client.get(
            f"/api/rooms/public/attempts/{s1['attemptId']}/audio/aud-top-1",
            headers=_student_headers(s1["attemptToken"]),
        ).status_code
        == 403
    )

    client.put(
        f"/api/rooms/public/attempts/{s1['attemptId']}/answers",
        headers=_student_headers(s1["attemptToken"]),
        json={
            "answers": {
                "q-mcq-1": 2,
                "q-tf-1": [True, False, True, False],
                "q-short-1": "1,5",
            }
        },
    )
    client.post(
        f"/api/rooms/public/attempts/{s1['attemptId']}/submit",
        headers=_student_headers(s1["attemptToken"]),
    )

    # HS2 đạt 100 p100
    s2 = client.post(
        f"/api/rooms/public/{code}/join",
        json={"studentName": "Bình", "studentCode": "HS02", "studentClass": "9A"},
    ).json()
    client.put(
        f"/api/rooms/public/attempts/{s2['attemptId']}/answers",
        headers=_student_headers(s2["attemptToken"]),
        json={"answers": {"q-mcq-1": 2}},
    )
    client.post(
        f"/api/rooms/public/attempts/{s2['attemptId']}/submit",
        headers=_student_headers(s2["attemptToken"]),
    )

    analytics = client.get(f"/api/rooms/{room_id}/analytics", headers=_teacher_headers())
    assert analytics.status_code == 200
    data = analytics.json()
    assert data["maxScoreP100"] == 300
    assert data["minScoreP100"] == 100
    assert data["avgScoreP100"] == 200
    assert data["medianScoreP100"] == 200


def test_local_workspace_serves_exam_room_html_only_among_assets_html(tmp_path: Path) -> None:
    from mach_backend.local_workspace import create_app

    client = TestClient(create_app(tmp_path))
    room_html = client.get("/assets/exam-room.html")
    assert room_html.status_code == 200
    assert "/assets/exam-room.js" in room_html.text
    assert "student-room-app" in room_html.text
    assert client.get("/assets/team-login.html").status_code == 404
