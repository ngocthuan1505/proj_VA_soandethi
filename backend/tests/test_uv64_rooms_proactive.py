"""Kiểm thử hồi quy & tính năng UV64 miền C: Phòng thi, điểm tự chọn, XLSX, Audio và Nhắc lịch."""

from __future__ import annotations

import io
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mach_backend.campaigns import install_campaign_routes
from mach_backend.exam_rooms import (
    _SCHEMA_SQL,
    _parse_short_decimal,
    _short_matches,
    install_exam_rooms,
)


def _build_rooms_harness(
    tmp_path: Path,
    *,
    exam_map: dict[str, dict[str, Any]],
) -> TestClient:
    db_path = tmp_path / "rooms.sqlite"
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.executescript(_SCHEMA_SQL)

    @contextmanager
    def connect():
        yield conn
        conn.commit()

    app = FastAPI()

    def owner_resolver(request: Request) -> str:
        return request.headers.get("x-test-owner", "teacher-a")

    def read_exam(_request: Request, exam_id: str) -> dict[str, Any] | None:
        return exam_map.get(exam_id)

    install_exam_rooms(
        app,
        connect=connect,
        owner_resolver=owner_resolver,
        read_exam=read_exam,
        clock=lambda: 1_760_200_000.0,
    )
    return TestClient(app)


def _teacher_headers(owner: str = "teacher-a") -> dict[str, str]:
    return {"x-test-owner": owner}


def _student_headers(token: str) -> dict[str, str]:
    return {"X-Attempt-Token": token}


def test_short_answer_fraction_decimal_equivalence_and_guards(tmp_path: Path) -> None:
    # Unit checks for _parse_short_decimal & _short_matches
    assert _parse_short_decimal("0,75") == _parse_short_decimal("3/4")
    assert _parse_short_decimal("6/8") == _parse_short_decimal("0.75")
    assert _parse_short_decimal("−3/4") == _parse_short_decimal("-0,75")
    assert _parse_short_decimal("1/0") is None
    assert _parse_short_decimal("-5/0.0") is None
    assert _parse_short_decimal("0." + "75" + "0" * 35) is None
    assert _parse_short_decimal("1 1/2") is None

    for ans in ("3/4", "6/8", " 3 / 4 ", "0.75", "0,75", "+0,75"):
        assert _short_matches(ans, "0,75") is True
    for neg in ("-3/4", "−3/4", "-6/8", "−0,75", "-0.75", "3/-4"):
        assert _short_matches(neg, "−0,75") is True
    assert _short_matches("2/6", "1/3") is True
    assert _short_matches("1/0", "0,75") is False
    assert _short_matches("0,74", "0,75") is False
    assert _short_matches("1/" + "2" * 35, "0,75") is False

    # End-to-end room grading for fraction vs decimal
    exam = {
        "id": "exam-short-frac",
        "title": "Toán 7 Phân số",
        "subject": "Toán",
        "grade": 7,
        "minutes": 30,
        "questions": [
            {
                "id": "q-short",
                "type": "short",
                "stem": "Viết kết quả phép tính dưới dạng số thập phân hoặc phân số.",
                "answerText": "0,75",
                "answerKnown": True,
                "points": 2.0,
            }
        ],
    }
    client = _build_rooms_harness(tmp_path, exam_map={"exam-short-frac": exam})
    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={"examId": "exam-short-frac", "resultPolicy": "score_and_answers"},
    ).json()
    joined = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "Nguyễn Minh"},
    ).json()
    sub = client.post(
        f"/api/rooms/public/attempts/{joined['attemptId']}/submit",
        headers=_student_headers(joined["attemptToken"]),
        json={"answers": {"q-short": "6/8"}},
    )
    assert sub.status_code == 200
    res = client.get(
        f"/api/rooms/public/attempts/{joined['attemptId']}/result",
        headers=_student_headers(joined["attemptToken"]),
    ).json()
    assert res["totalScoreP100"] == 200
    assert res["totalPointsP100"] == 200


def test_choice_group_effective_points_and_track_selection(tmp_path: Path) -> None:
    # 0.50 chung + 9.50 Tự chọn A + 9.50 Tự chọn B -> hiệu lực 10.00 điểm (1000 p100)
    exam = {
        "id": "exam-tin-2nhanh",
        "title": "Đề Tin học 12 hai hướng",
        "subject": "Tin học",
        "grade": 12,
        "minutes": 45,
        "questions": [
            {
                "id": "q-common",
                "type": "mcq",
                "stem": "Câu chung 1",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "answerKnown": True,
                "points": 0.5,
            },
            {
                "id": "q-a1",
                "type": "mcq",
                "choiceGroup": "Tự chọn A",
                "stem": "Câu A1",
                "options": ["A1", "B1", "C1", "D1"],
                "answer": 1,
                "answerKnown": True,
                "points": 4.5,
            },
            {
                "id": "q-a2",
                "type": "short",
                "choiceGroup": "Tự chọn A",
                "stem": "Câu A2",
                "answerText": "0,75",
                "answerKnown": True,
                "points": 5.0,
            },
            {
                "id": "q-b1",
                "type": "mcq",
                "choiceGroup": "Tự chọn B",
                "stem": "Câu B1",
                "options": ["A2", "B2", "C2", "D2"],
                "answer": 2,
                "answerKnown": True,
                "points": 4.5,
            },
            {
                "id": "q-b2",
                "type": "essay",
                "choiceGroup": "Tự chọn B",
                "stem": "Câu B2 tự luận",
                "rubric": [{"text": "Đúng ý", "points": 5.0}],
                "points": 5.0,
            },
        ],
    }
    client = _build_rooms_harness(tmp_path, exam_map={"exam-tin-2nhanh": exam})
    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-tin-2nhanh",
            "maxAttempts": 5,
            "shuffleQuestions": True,
            "resultPolicy": "score_and_answers",
        },
    ).json()
    assert room["totalPointsP100"] == 1000
    assert room["choiceGroups"] == ["Tự chọn A", "Tự chọn B"]

    # HS1 chỉ làm Phần chung + Tự chọn A (đạt 10/10, không bị tự luận B kéo thành needs_manual)
    j1 = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "HS Chỉ Chọn A", "studentCode": "A1"},
    ).json()
    assert j1["room"]["totalPointsP100"] == 1000
    assert j1["room"]["choiceGroups"] == ["Tự chọn A", "Tự chọn B"]
    # Kiểm tra shuffle không trộn lẫn Tự chọn A và Tự chọn B
    q_groups = [q.get("choiceGroup", "") for q in j1["exam"]["questions"]]
    assert q_groups == ["", "Tự chọn A", "Tự chọn A", "Tự chọn B", "Tự chọn B"]

    client.post(
        f"/api/rooms/public/attempts/{j1['attemptId']}/submit",
        headers=_student_headers(j1["attemptToken"]),
        json={"answers": {"q-common": 0, "q-a1": 1, "q-a2": "3/4"}},
    ).raise_for_status()
    r1 = client.get(
        f"/api/rooms/public/attempts/{j1['attemptId']}/result",
        headers=_student_headers(j1["attemptToken"]),
    ).json()
    assert r1["totalScoreP100"] == 1000
    assert r1["totalPointsP100"] == 1000
    assert r1["chosenTrack"] == "Tự chọn A"
    assert r1["trackScores"]["Tự chọn A"]["scoreP100"] == 950
    assert r1["trackScores"]["Tự chọn B"]["scoreP100"] == 0
    assert r1["gradingStatus"] == "auto_graded"
    assert r1["ungradedEssayCount"] == 0
    assert r1["isProvisionalScore"] is False

    # Hàng đợi chấm tự luận KHÔNG hiện câu tự luận ở Tự chọn B mà HS1 bỏ qua
    queue = client.get(
        f"/api/rooms/{room['id']}/grading-queue",
        headers=_teacher_headers(),
    ).json()
    assert queue["pendingCount"] == 0

    # HS2 làm cả 2 hướng: A đúng câu 5.0đ, B tự luận 4.5đ -> A (5.0) > B (4.5)
    j2 = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "HS Làm Cả 2", "studentCode": "AB1"},
    ).json()
    client.post(
        f"/api/rooms/public/attempts/{j2['attemptId']}/submit",
        headers=_student_headers(j2["attemptToken"]),
        json={
            "answers": {
                "q-common": 0,  # 50
                "q-a1": 0,  # sai (0)
                "q-a2": "6/8",  # đúng (500)
                "q-b1": 0,  # sai (0)
                "q-b2": "Bài làm tự luận nhánh B",
            }
        },
    ).raise_for_status()
    r2_before = client.get(
        f"/api/rooms/public/attempts/{j2['attemptId']}/result",
        headers=_student_headers(j2["attemptToken"]),
    ).json()
    assert r2_before["gradingStatus"] == "needs_manual"
    assert r2_before["ungradedEssayCount"] == 1
    assert r2_before["isProvisionalScore"] is True

    # Chấm tự luận B = 450 -> nhánh A (500) vẫn cao hơn B (450)
    g1 = client.put(
        f"/api/rooms/{room['id']}/attempts/{j2['attemptId']}/grades/q-b2",
        headers=_teacher_headers(),
        json={"earnedPointsP100": 450},
    ).json()
    assert g1["chosenTrack"] == "Tự chọn A"
    assert g1["totalScoreP100"] == 550
    assert g1["gradingStatus"] == "graded"

    # Chấm lại tự luận B = 500 + đúng thêm -> nếu chấm B = 500 (tổng B=500 == A=500, theo thứ tự A),
    # kiểm tra một ca khác mà B > A hoàn toàn:
    j3 = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "HS B Cao Hơn", "studentCode": "B1"},
    ).json()
    client.post(
        f"/api/rooms/public/attempts/{j3['attemptId']}/submit",
        headers=_student_headers(j3["attemptToken"]),
        json={
            "answers": {
                "q-common": 0,  # 50
                "q-a1": 1,  # 450
                "q-b1": 2,  # 450
                "q-b2": "Lập luận đầy đủ nhánh B",
            }
        },
    ).raise_for_status()
    g2 = client.put(
        f"/api/rooms/{room['id']}/attempts/{j3['attemptId']}/grades/q-b2",
        headers=_teacher_headers(),
        json={"earnedPointsP100": 500},
    ).json()
    assert g2["chosenTrack"] == "Tự chọn B"
    assert g2["totalScoreP100"] == 1000
    assert g2["trackScores"]["Tự chọn B"]["scoreP100"] == 950
    assert g2["trackScores"]["Tự chọn A"]["scoreP100"] == 450


def test_provisional_score_marking_guidance_and_xlsx_detail_sheet(tmp_path: Path) -> None:
    guidance = (
        "Học sinh làm cách khác đúng vẫn cho đủ điểm.\n"
        "Trừ 0,25 điểm nếu thiếu đơn vị ở kết quả cuối."
    )
    exam = {
        "id": "exam-essay-xlsx",
        "title": "Đề có tự luận & hướng dẫn chấm",
        "subject": "Vật lí",
        "grade": 10,
        "minutes": 45,
        "markingGuidance": guidance,
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "Đơn vị lực là?",
                "options": ["J", "N", "W", "Pa"],
                "answer": 1,
                "answerKnown": True,
                "points": 2.0,
            },
            {
                "id": "q2",
                "type": "short",
                "stem": "Tính gia tốc (m/s²)",
                "answerText": "0,75",
                "answerKnown": True,
                "points": 3.0,
            },
            {
                "id": "q3",
                "type": "essay",
                "stem": "Giải thích hiện tượng rơi tự do",
                "rubric": [{"text": "Nêu đúng định luật", "points": 5.0}],
                "points": 5.0,
            },
        ],
    }
    client = _build_rooms_harness(tmp_path, exam_map={"exam-essay-xlsx": exam})
    room = client.post(
        "/api/rooms",
        headers=_teacher_headers(),
        json={
            "examId": "exam-essay-xlsx",
            "shuffleOptions": True,
            "resultPolicy": "score_only",
        },
    ).json()
    room_id = room["id"]
    assert room["markingGuidance"] == guidance

    # Chi tiết phòng và hàng đợi chấm có markingGuidance; cổng công khai KHÔNG rò markingGuidance
    detail = client.get(f"/api/rooms/{room_id}", headers=_teacher_headers()).json()
    assert detail["room"]["markingGuidance"] == guidance

    pub_meta = client.get(f"/api/rooms/public/{room['roomCode']}").json()
    assert "markingGuidance" not in pub_meta

    joined = client.post(
        f"/api/rooms/public/{room['roomCode']}/join",
        json={"studentName": "Trần Lan", "studentCode": "TL10"},
    ).json()
    assert "markingGuidance" not in joined["exam"]

    # Tìm chỉ số phương án "N" trên đề đã trộn của học sinh
    q1_opts = joined["exam"]["questions"][0]["options"]
    n_idx = q1_opts.index("N")
    client.post(
        f"/api/rooms/public/attempts/{joined['attemptId']}/submit",
        headers=_student_headers(joined["attemptToken"]),
        json={
            "answers": {
                "q1": n_idx,
                "q2": "3/4",
                "q3": "Vật chỉ chịu tác dụng của trọng lực.\x0bKý tự điều khiển đã lọc.",
            }
        },
    ).raise_for_status()

    # Result score_only vẫn báo điểm tạm & số câu tự luận chưa chấm mà không lộ danh sách câu hỏi
    res_pending = client.get(
        f"/api/rooms/public/attempts/{joined['attemptId']}/result",
        headers=_student_headers(joined["attemptToken"]),
    ).json()
    assert res_pending["questions"] == []
    assert res_pending["gradingStatus"] == "needs_manual"
    assert res_pending["ungradedEssayCount"] == 1
    assert res_pending["isProvisionalScore"] is True

    # Grading queue trả về markingGuidance
    queue = client.get(f"/api/rooms/{room_id}/grading-queue", headers=_teacher_headers()).json()
    assert queue["markingGuidance"] == guidance
    assert queue["pendingCount"] == 1

    # Chấm tự luận -> hết tạm
    client.put(
        f"/api/rooms/{room_id}/attempts/{joined['attemptId']}/grades/q3",
        headers=_teacher_headers(),
        json={"earnedPointsP100": 475, "graderNote": "Thiếu đơn vị trừ 0,25"},
    ).raise_for_status()
    res_final = client.get(
        f"/api/rooms/public/attempts/{joined['attemptId']}/result",
        headers=_student_headers(joined["attemptToken"]),
    ).json()
    assert res_final["gradingStatus"] == "graded"
    assert res_final["ungradedEssayCount"] == 0
    assert res_final["isProvisionalScore"] is False
    assert res_final["totalScoreP100"] == 975

    # Export XLSX chứa sheet thứ 3 BaiLamChiTiet với đáp án gốc đã giải mã & bài tự luận
    xlsx_res = client.get(f"/api/rooms/{room_id}/export.xlsx", headers=_teacher_headers())
    assert xlsx_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(xlsx_res.content), "r") as zf:
        names = set(zf.namelist())
        assert "xl/worksheets/sheet3.xml" in names
        wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
        assert "BangDiem" in wb_xml
        assert "ThongKeCauHoi" in wb_xml
        assert "BaiLamChiTiet" in wb_xml
        sheet3_xml = zf.read("xl/worksheets/sheet3.xml").decode("utf-8")
        ET.fromstring(sheet3_xml)
        assert "Cau 1" in sheet3_xml
        assert "Cau 2" in sheet3_xml
        assert "Cau 3" in sheet3_xml
        assert "Trần Lan" in sheet3_xml
        assert "B. N" in sheet3_xml
        assert "3/4" in sheet3_xml
        assert "Vật chỉ chịu tác dụng của trọng lực." in sheet3_xml


def test_reminders_and_proactive_digest_include_attached_exam_title(tmp_path: Path) -> None:
    db_path = tmp_path / "campaigns.sqlite"
    conn = sqlite3.connect(db_path, check_same_thread=False)

    @contextmanager
    def connect():
        yield conn
        conn.commit()

    now_ms = 1_760_200_000_000
    state_box: dict[str, Any] = {
        "state": {
            "exams": [
                {
                    "id": "ex-toan-11",
                    "title": "Đề Toán 11 Giữa Kì I",
                    "questions": [{"id": "q1", "approvalStatus": "approved"}],
                    "updated": now_ms - 3600_000,
                }
            ],
            "trash": [],
        }
    }
    app = FastAPI()
    install_campaign_routes(app, connect, lambda: state_box["state"], lambda _r: "teacher-a")
    client = TestClient(app)

    created = client.post(
        "/api/reminders",
        json={
            "title": "Rà lại ma trận trước khi in",
            "kind": "review",
            "targetType": "exam",
            "targetId": "ex-toan-11",
            "remindAt": now_ms + 3_600_000,
        },
    )
    assert created.status_code == 201
    rem = created.json()["reminder"]
    assert rem["targetTitle"] == "Đề Toán 11 Giữa Kì I"
    assert rem["examTitle"] == "Đề Toán 11 Giữa Kì I"

    listed = client.get("/api/reminders").json()["reminders"]
    assert listed[0]["targetTitle"] == "Đề Toán 11 Giữa Kì I"

    digest = client.get(f"/api/proactive/digest?nowMs={now_ms}").json()
    dl = digest["urgentDeadlines"][0]
    assert dl["targetId"] == "ex-toan-11"
    assert dl["targetTitle"] == "Đề Toán 11 Giữa Kì I"
    assert dl["examTitle"] == "Đề Toán 11 Giữa Kì I"
