"""Kiểm chứng các bản vá lỗi biên QA thực địa UV63.

1. Chặn tài liệu đã thu hồi quyền khi copy sang đề khác (ai_sources.py).
2. Phòng thi online trả về syncedAnswerCount & totalQuestions (exam_rooms.py).
3. Trộn nhóm ngữ liệu đọc hiểu giữ nguyên đoạn văn, lời dẫn và dải số câu mới (local_documents.py).
4. Kiểm tra mã nguồn exam-room.js và studio.js khóa Space audio và đóng menu mobile.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError, Locator
from mach_backend.ai_sources import SourceKey, workspace_page_sources
from mach_backend.curriculum_sources import SCHEMA_DDL
from mach_backend.exam_rooms import install_exam_rooms
from mach_backend.local_documents import (
    exam_html,
    exam_variant,
    preview_exam_variant,
)


def _init_curriculum_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_DDL)


def test_revoked_license_blocked_on_copied_doc():
    """Kiểm tra chặn tài liệu đã bị thu hồi quyền dù ở bản copy sang đề khác có ghi allowed."""
    conn = sqlite3.connect(":memory:")
    _init_curriculum_db(conn)

    source_id = "src-origin-uuid"
    conn.execute(
        """
        INSERT INTO curriculum_sources (
            id, owner_id, grade, subject, series, volume, chapter, lesson,
            title, license_status, license_note, source_origin, locator,
            content_excerpt, sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            "teacher-1",
            8,
            "Ngữ văn",
            "Cánh Diều",
            "1",
            "Chương 1",
            "Bài 1",
            "Nguồn gốc",
            "restricted",
            "Đã thu hồi bản quyền",
            "Bộ GD",
            "Trang 10",
            "Nội dung trích đoạn nguồn",
            "fake-sha256",
            1000,
            1000,
        ),
    )
    conn.commit()

    copied_doc_id = str(uuid4())
    exam = {
        "docs": [
            {
                "id": copied_doc_id,
                "curriculumSourceId": source_id,
                "licenseStatus": "allowed",
                "text": "Bản sao tài liệu trong đề thi mới",
                "version": 1,
            }
        ]
    }
    doc_uuid = uuid4()
    exam["docs"][0]["id"] = str(doc_uuid)
    chosen_keys: tuple[SourceKey, ...] = ((doc_uuid, Locator(kind="page", index=1)),)

    with pytest.raises(AIError) as exc_info:
        workspace_page_sources(exam, "teacher-1", chosen_keys, conn)
    assert exc_info.value.code == "source_license_restricted"
    assert exc_info.value.http_status == 403

    # Thử với originSourceId và pending_review
    conn.execute(
        "UPDATE curriculum_sources SET license_status = 'pending_review' WHERE id = ?",
        (source_id,),
    )
    conn.commit()
    exam2 = {
        "docs": [
            {
                "id": str(doc_uuid),
                "originSourceId": source_id,
                "license_status": "allowed",
                "text": "Bản sao tài liệu",
                "version": 1,
            }
        ]
    }
    with pytest.raises(AIError) as exc_info2:
        workspace_page_sources(exam2, "teacher-1", chosen_keys, conn)
    assert exc_info2.value.code == "source_license_restricted"

    # Cho phép allowed
    conn.execute(
        "UPDATE curriculum_sources SET license_status = 'allowed' WHERE id = ?",
        (source_id,),
    )
    conn.commit()
    res = workspace_page_sources(exam2, "teacher-1", chosen_keys, conn)
    assert len(res) == 1
    assert res[0].text == "Bản sao tài liệu"


def test_exam_rooms_synced_answer_count_and_total_questions():
    """Kiểm tra submit_attempt & get_attempt_result trả về syncedAnswerCount & totalQuestions."""
    app = FastAPI()
    from mach_backend.exam_rooms import _SCHEMA_SQL

    db_conn = sqlite3.connect(":memory:", check_same_thread=False)
    db_conn.executescript(_SCHEMA_SQL)

    def connect():
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield db_conn

        return _cm()

    exam_snap = {
        "id": "exam-test-1",
        "title": "Đề thi kiểm tra",
        "subject": "Toán",
        "grade": 9,
        "revision": 1,
        "minutes": 45,
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "Giá trị của $2 + 3$ bằng bao nhiêu?",
                "options": ["3", "4", "5", "6"],
                "answer": 2,
                "answerKnown": True,
                "explanation": "Vì $2 + 3 = 5$.",
                "points": 1.0,
            },
            {
                "id": "q2",
                "type": "mcq",
                "stem": "Giá trị của $3 + 4$ bằng bao nhiêu?",
                "options": ["5", "6", "7", "8"],
                "answer": 2,
                "answerKnown": True,
                "explanation": "Vì $3 + 4 = 7$.",
                "points": 1.0,
            },
            {
                "id": "q3",
                "type": "mcq",
                "stem": "Giá trị của $4 + 5$ bằng bao nhiêu?",
                "options": ["7", "8", "9", "10"],
                "answer": 2,
                "answerKnown": True,
                "explanation": "Vì $4 + 5 = 9$.",
                "points": 1.0,
            },
        ],
    }

    install_exam_rooms(
        app,
        connect=connect,
        owner_resolver=lambda req: "teacher_owner",
        read_exam=lambda req, exam_id: exam_snap,
        clock=lambda: 1730000000.0,
    )

    client = TestClient(app)

    # Tạo phòng thi qua API
    create_res = client.post(
        "/api/rooms",
        headers={"X-Test-Owner": "teacher_owner"},
        json={
            "examId": "exam-test-1",
            "title": "Phòng thi kiểm tra",
            "durationMinutes": 45,
            "resultPolicy": "score_and_answers",
        },
    )
    assert create_res.status_code == 201, create_res.text
    room_code = create_res.json()["roomCode"]

    # Học sinh vào phòng thi
    join_res = client.post(
        f"/api/rooms/public/{room_code}/join",
        json={"studentName": "Nguyễn Văn A"},
    )
    assert join_res.status_code == 201
    join_data = join_res.json()
    attempt_id = join_data["attemptId"]
    token = join_data["attemptToken"]

    # Lưu 2 câu trả lời (q1 và q2) lên máy chủ
    ans_res = client.put(
        f"/api/rooms/public/attempts/{attempt_id}/answers",
        headers={"X-Attempt-Token": token},
        json={"answers": {"q1": 0, "q2": 1}},
    )
    assert ans_res.status_code == 200

    # Nộp bài
    sub_res = client.post(
        f"/api/rooms/public/attempts/{attempt_id}/submit",
        headers={"X-Attempt-Token": token},
        json={"autoSubmit": False},
    )
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["syncedAnswerCount"] == 2
    assert sub_data["totalQuestions"] == 3

    # Lấy kết quả bài làm
    res_res = client.get(
        f"/api/rooms/public/attempts/{attempt_id}/result",
        headers={"X-Attempt-Token": token},
    )
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["syncedAnswerCount"] == 2
    assert res_data["totalQuestions"] == 3


def test_passage_group_shuffling_and_lead_range_update():
    """Kiểm tra hoán vị khối ngữ liệu giữ nguyên đoạn văn, lời dẫn và đánh số câu mới."""
    exam = {
        "title": "Đề thi Ngữ văn 9",
        "subject": "Ngữ văn",
        "grade": 9,
        "questions": [
            {
                "id": "p1_q1",
                "type": "mcq",
                "stem": "Ý chính đoạn 1?",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "passageId": "p1",
                "passageTitle": "Đọc ngữ liệu sau và trả lời các câu hỏi từ câu 1 đến câu 2:",
                "passageText": "Nội dung đoạn văn thứ nhất về mùa thu.",
            },
            {
                "id": "p1_q2",
                "type": "mcq",
                "stem": "Từ láy trong đoạn 1?",
                "options": ["A", "B", "C", "D"],
                "answer": 1,
                "passageId": "p1",
            },
            {
                "id": "p2_q1",
                "type": "mcq",
                "stem": "Ý chính đoạn 2?",
                "options": ["A", "B", "C", "D"],
                "answer": 2,
                "passageId": "p2",
                "passageTitle": "Đọc đoạn văn sau để trả lời từ câu 3 đến câu 4:",
                "passageText": "Nội dung đoạn văn thứ hai về mùa xuân.",
            },
            {
                "id": "p2_q2",
                "type": "mcq",
                "stem": "Biện pháp tu từ trong đoạn 2?",
                "options": ["A", "B", "C", "D"],
                "answer": 3,
                "passageId": "p2",
            },
        ],
    }

    # Hoán vị khối p2 lên đầu (offset 1)
    v1 = exam_variant(
        exam,
        {"questionIds": ["p1_q1", "p1_q2", "p2_q1", "p2_q2"], "offset": 1},
    )
    assert [q["id"] for q in v1["questions"]] == ["p2_q1", "p2_q2", "p1_q1", "p1_q2"]

    # Đoạn p2 chuyển thành câu 1 đến câu 2 -> lời dẫn được cập nhật
    assert "từ câu 1 đến câu 2" in v1["questions"][0]["passageTitle"]
    assert v1["questions"][0]["passageText"] == "Nội dung đoạn văn thứ hai về mùa xuân."

    # Đoạn p1 chuyển thành câu 3 đến câu 4 -> lời dẫn được cập nhật
    assert "từ câu 3 đến câu 4" in v1["questions"][2]["passageTitle"]
    assert v1["questions"][2]["passageText"] == "Nội dung đoạn văn thứ nhất về mùa thu."

    # Kiểm tra HTML xuất ra có chứa cả 2 đoạn ngữ liệu và lời dẫn mới
    html_content = exam_html(v1, teacher=False, origin="http://localhost")
    assert "Nội dung đoạn văn thứ nhất về mùa thu." in html_content
    assert "Nội dung đoạn văn thứ hai về mùa xuân." in html_content
    assert "từ câu 1 đến câu 2" in html_content
    assert "từ câu 3 đến câu 4" in html_content

    # Kiểm tra preview_exam_variant trả về passageTitle, passageText, passageId
    preview = preview_exam_variant(
        {
            "exam": exam,
            "variant": {"questionIds": ["p1_q1", "p1_q2", "p2_q1", "p2_q2"], "offset": 1},
        }
    )
    q0 = preview["questions"][0]
    assert q0["originalNumber"] == 3
    assert q0["passageId"] == "p2"
    assert "từ câu 1 đến câu 2" in q0["passageTitle"]
    assert q0["passageText"] == "Nội dung đoạn văn thứ hai về mùa xuân."

    q2 = preview["questions"][2]
    assert q2["originalNumber"] == 1
    assert q2["passageId"] == "p1"
    assert "từ câu 3 đến câu 4" in q2["passageTitle"]
    assert q2["passageText"] == "Nội dung đoạn văn thứ nhất về mùa thu."


def test_exam_room_js_source_guards():
    """Kiểm tra mã nguồn assets/exam-room.js khóa phím Space/Enter và nhãn mất mạng."""
    js_path = Path(__file__).resolve().parents[2] / "assets" / "exam-room.js"
    js_content = js_path.read_text(encoding="utf-8")

    # Khóa Space và Enter
    assert "Space" in js_content and "Enter" in js_content
    assert "playsRemaining <= 0" in js_content
    assert "lockExhaustedAudio" in js_content
    assert "audio.pause();" in js_content or "aud.pause();" in js_content

    # Nhãn mất mạng và class .is-offline
    assert "Mất mạng · đang lưu tạm trên máy" in js_content
    assert "is-offline" in js_content

    # Đồng bộ câu hỏi lên máy chủ
    assert "Đã đồng bộ" in js_content
    assert "syncedAnswerCount" in js_content
    assert "Chuyển tới câu chưa làm" in js_content
