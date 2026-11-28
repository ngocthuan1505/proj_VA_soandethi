"""Kiểm thử tách câu từ văn bản đề cũ thuần Python và chẩn đoán lỗi theo trang/câu."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from mach_backend.local_workspace import create_app
from mach_backend.question_parser import parse_questions_with_diagnostics
from mach_backend.team_workspace import create_team_app

ORIGIN = {"Origin": "http://testserver"}
PNG_1X1 = (
    "data:image/png;base64,"
    + base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc`\xf8\xcf"
        b"\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode()
)


def test_parse_legacy_compatibility_mcq_essay_images_and_answer_key_cutoff():
    text = (
        "Câu 1: (0,5 điểm) Giá trị của $\\frac{4}{2}$ bằng bao nhiêu? [[HINH:img_1]]\n"
        "A. 1\n"
        "B. 2\n"
        "C. 3\n"
        "D. 4\n\n"
        "Bài 1: (2,0 điểm) Giải phương trình $x + 1 = 3$.\n"
        "— Hết —\n\n"
        "HƯỚNG DẪN CHẤM VÀ THANG ĐIỂM\n"
        "Câu 1: Chọn B.\n"
        "Bài 1: x = 2.\n"
    )
    images = [
        {"marker": "[[HINH:img_1]]", "data": PNG_1X1, "caption": "Đồ thị mẫu"},
        {"marker": "[[HINH:bad]]", "data": "data:image/svg+xml;base64,abc", "caption": "SVG"},
        {"marker": "INVALID", "data": PNG_1X1, "caption": "Sai marker"},
    ]
    result = parse_questions_with_diagnostics(text, images, page=1)
    assert result["summary"] == {
        "totalQuestions": 2,
        "completeCount": 2,
        "incompleteCount": 0,
        "needsReviewCount": 0,
        "pagesScanned": 1,
        "issueCount": 0,
    }
    assert result["issues"] == []

    q1, q2 = result["questions"]
    assert q1["type"] == "mcq"
    assert q1["points"] == 0.5
    assert q1["options"] == ["1", "2", "3", "4"]
    assert q1["incomplete"] is False
    assert q1["images"] == [{"data": PNG_1X1, "caption": "Đồ thị mẫu"}]
    assert "[[HINH:" not in q1["stem"]
    assert q1["sourcePage"] == 1
    assert q1["sourceLabel"] == "Câu 1"

    assert q2["type"] == "essay"
    assert q2["points"] == 2.0
    assert q2["options"] == []
    assert q2["rubric"] == []
    assert "HƯỚNG DẪN CHẤM" not in q2["stem"]
    assert "Hết" not in q2["stem"]


def test_parse_multipage_diagnostics_reports_page_and_question_numbers():
    pages = [
        {
            "number": 1,
            "text": ("Câu 1: (0,3 điểm) Tìm $x biết [không rõ] số học.\nA. 1\nB. 2\n\nCâu 2:\n"),
            "images": [],
        },
        {
            "number": 2,
            "text": ("Câu 2: Phân số $\\frac{1}{2$ bị lỗi \\ufffd.\nA. 1\nB. 2\nC. 3\nD. 4\n"),
            "images": [],
        },
    ]
    result = parse_questions_with_diagnostics("", pages=pages)
    codes_by_loc = {
        (issue["page"], issue["questionNumber"], issue["code"]) for issue in result["issues"]
    }
    assert (1, 1, "invalid_points_step") in codes_by_loc
    assert (1, 1, "ocr_uncertain") in codes_by_loc
    assert (1, 1, "missing_options") in codes_by_loc
    assert (1, 1, "unbalanced_math") in codes_by_loc
    assert (1, 2, "empty_stem") in codes_by_loc
    assert (2, 2, "duplicate_question_number") in codes_by_loc
    assert (2, 2, "unbalanced_math") in codes_by_loc
    assert result["summary"]["totalQuestions"] == 3
    assert result["summary"]["incompleteCount"] == 2
    assert result["summary"]["needsReviewCount"] == 3
    assert result["summary"]["pagesScanned"] == 2


def test_parse_no_questions_found_emits_clear_issue():
    result = parse_questions_with_diagnostics("Đây chỉ là đoạn văn không đánh số câu.", page=3)
    assert result["questions"] == []
    assert len(result["issues"]) == 1
    assert result["issues"][0]["code"] == "no_questions_found"
    assert result["issues"][0]["page"] == 3


def test_parse_questions_http_local_and_team_auth(tmp_path: Path):
    with TestClient(create_app(tmp_path / "local"), headers=ORIGIN) as local:
        ok = local.post(
            "/api/parse-questions",
            json={
                "text": "Câu 1: Thủ đô Việt Nam?\nA. Hà Nội\nB. Huế\nC. Đà Nẵng\nD. Cần Thơ",
                "page": 2,
            },
        )
        assert ok.status_code == 200, ok.text
        data = ok.json()
        assert len(data["questions"]) == 1
        assert data["questions"][0]["sourcePage"] == 2
        assert data["issues"] == []

        bad_extra = local.post("/api/parse-questions", json={"text": "a", "unexpected": True})
        assert bad_extra.status_code == 422
        bad_bool = local.post("/api/parse-questions", json={"text": "a", "page": True})
        assert bad_bool.status_code == 422

    team_app = create_team_app(tmp_path / "team")
    accounts = team_app.state.accounts
    accounts.create(
        "teacher@example.test",
        "mat-khau-thu-nghiem-123",
        "Giáo viên",
        accounts.invite(bootstrap=True),
    )

    with TestClient(team_app, headers=ORIGIN) as guest:
        denied = guest.post("/api/parse-questions", json={"text": "Câu 1: A"})
        assert denied.status_code == 401

    with TestClient(team_app, headers=ORIGIN) as member:
        assert (
            member.post(
                "/api/account/login",
                json={"email": "teacher@example.test", "password": "mat-khau-thu-nghiem-123"},
            ).status_code
            == 200
        )
        authed = member.post(
            "/api/parse-questions",
            json={"text": "Câu 1: Sinh học?\nA. Tế bào", "page": 1},
        )
        assert authed.status_code == 200, authed.text
        body = authed.json()
        assert body["questions"][0]["incomplete"] is True
        assert body["issues"][0]["code"] == "missing_options"
