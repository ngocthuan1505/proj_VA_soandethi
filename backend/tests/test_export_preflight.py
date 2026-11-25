"""Kiểm thử kiểm tra tiền xuất bản in A4: đối chiếu ngắt trang, OCR cần duyệt và lỗi chặn."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.export_preflight import audit_export_preflight, install_export_preflight


def _make_clean_exam() -> dict[str, Any]:
    return {
        "title": "Đề kiểm tra giữa kỳ I Toán 9",
        "school": "THCS Chuẩn Thực Nghiệm",
        "subject": "Toán",
        "grade": "9",
        "minutes": 45,
        "instructions": "Học sinh làm bài trực tiếp vào giấy thi.",
        "docs": [
            {
                "id": "doc-clean",
                "name": "Tai_lieu_chuan.docx",
                "needsReview": False,
                "pages": [
                    {
                        "number": 1,
                        "text": r"Hàm số bậc nhất $y = 2x + 1$ xác định trên $\mathbb{R}$.",
                        "uncertain": False,
                        "needsReview": False,
                    }
                ],
            }
        ],
        "questions": [
            {
                "id": "q-1",
                "v": 1,
                "type": "mcq",
                "points": 0.5,
                "stem": r"Giá trị của $\frac{x^2 + 1}{2}$ tại $x = 3$ là bao nhiêu?",
                "options": ["3", "4", "5", "6"],
                "answer": 2,
                "explanation": r"Thay $x = 3$ ta được $\frac{3^2 + 1}{2} = 5$.",
                "source": {"docId": "doc-clean", "page": 1},
                "approval": {"version": 1, "status": "approved"},
            },
            {
                "id": "q-2",
                "v": 1,
                "type": "truefalse",
                "points": 1.0,
                "stem": r"Xét các mệnh đề về $\sqrt{x^2}$:",
                "options": [
                    r"$\sqrt{9} = 3$",
                    r"$\sqrt{(-4)^2} = -4$",
                    r"$\sqrt{0} = 0$",
                    r"$\sqrt{25} = -5$",
                ],
                "truthValues": [True, False, True, False],
                "approval": {"version": 1, "status": "approved"},
            },
            {
                "id": "q-3",
                "v": 1,
                "type": "short",
                "points": 1.25,
                "stem": r"Tìm nghiệm dương của phương trình $x^2 - 49 = 0$.",
                "answerText": "7",
                "approval": {"version": 1, "status": "approved"},
            },
            {
                "id": "q-4",
                "v": 1,
                "type": "essay",
                "points": 2.25,
                "pageBreak": True,
                "stem": r"Giải và biện luận phương trình $x^2 = 2m - 1$ theo tham số $m$.",
                "rubric": [
                    {
                        "text": r"Xét $2m - 1 < 0 \Leftrightarrow m < \frac{1}{2}$: vô nghiệm.",
                        "points": 0.75,
                    },
                    {"text": r"Xét $m = \frac{1}{2}$: có nghiệm kép $x = 0$.", "points": 0.75},
                    {
                        "text": r"Xét $m > \frac{1}{2}$: có hai nghiệm $x = \pm\sqrt{2m - 1}$.",
                        "points": 0.75,
                    },
                ],
                "approval": {"version": 1, "status": "approved"},
            },
        ],
    }


def test_clean_exam_is_ready_without_warnings_and_preserves_input():
    exam = _make_clean_exam()
    editor_pages = [
        {"page": 1, "questionIds": ["q-1", "q-2", "q-3"], "oversize": False},
        {"page": 2, "questionIds": ["q-4"], "oversize": False},
    ]
    before_exam = deepcopy(exam)
    before_pages = deepcopy(editor_pages)

    report = audit_export_preflight(exam, editor_pages)

    assert exam == before_exam
    assert editor_pages == before_pages
    assert report["ready"] is True
    assert report["needsAttention"] is False
    assert report["blockingIssues"] == []
    assert report["warnings"] == []
    assert report["ocrReviewItems"] == []

    alignment = report["pageBreakAlignment"]
    assert alignment["editorPageCount"] == 2
    assert alignment["estimatedA4PageCount"] == 2
    assert alignment["explicitPageBreakOrdinals"] == [4]
    assert alignment["oversizePages"] == []
    assert alignment["oversizeQuestionIds"] == []
    assert alignment["pageMismatches"] == []
    assert alignment["pageMap"] == [
        {
            "questionId": "q-1",
            "ordinal": 1,
            "editorPage": 1,
            "estimatedA4Page": 1,
            "explicitBreakBefore": False,
            "oversize": False,
        },
        {
            "questionId": "q-2",
            "ordinal": 2,
            "editorPage": 1,
            "estimatedA4Page": 1,
            "explicitBreakBefore": False,
            "oversize": False,
        },
        {
            "questionId": "q-3",
            "ordinal": 3,
            "editorPage": 1,
            "estimatedA4Page": 1,
            "explicitBreakBefore": False,
            "oversize": False,
        },
        {
            "questionId": "q-4",
            "ordinal": 4,
            "editorPage": 2,
            "estimatedA4Page": 2,
            "explicitBreakBefore": True,
            "oversize": False,
        },
    ]

    summary = report["summary"]
    assert summary["totalQuestions"] == 4
    assert summary["approvedCount"] == 4
    assert summary["unapprovedCount"] == 0
    assert summary["totalPoints"] == 5.0
    assert summary["totalPointsQ4"] == 20
    assert summary["blockingCount"] == 0
    assert summary["warningCount"] == 0
    assert summary["ocrReviewCount"] == 0


def test_unapproved_and_stale_approval_questions_trigger_attention_only():
    exam = _make_clean_exam()
    exam["questions"][0]["v"] = 2  # approval vẫn ở version 1 -> hết hiệu lực duyệt
    exam["questions"][1].pop("approval")  # chưa duyệt
    exam["questions"][2].pop("approval")
    exam["questions"][2]["check"] = {"version": 1, "status": "approved"}  # vẫn tính đã duyệt

    report = audit_export_preflight(exam)

    assert report["ready"] is True
    assert report["needsAttention"] is True
    assert report["summary"]["totalQuestions"] == 4
    assert report["summary"]["approvedCount"] == 2
    assert report["summary"]["unapprovedCount"] == 2
    unapproved_ordinals = [
        w["ordinal"] for w in report["warnings"] if w["code"] == "unapproved_question"
    ]
    assert unapproved_ordinals == [1, 2]


def test_page_break_alignment_detects_mismatches_manual_breaks_and_oversize_pages():
    exam = _make_clean_exam()
    # Thêm bảng lớn + nhiều ảnh + hình + công thức + barem vào câu 4 để vượt chiều cao 1 trang A4.
    exam["questions"][3]["tables"] = [
        {"rows": [[f"Dòng {r}", f"Giá trị {r}", f"Ghi chú {r}"] for r in range(1, 14)]}
    ]
    exam["questions"][3]["images"] = [
        {"data": "data:image/png;base64,AA==", "caption": "Đồ thị thí nghiệm 1"},
        {"data": "data:image/png;base64,AA==", "caption": "Đồ thị thí nghiệm 2"},
    ]
    exam["questions"][3]["figure"] = {"caption": "Hình học không gian"}
    exam["questions"][3]["formulas"] = [
        {
            "id": "f-1",
            "latex": r"\begin{cases} x + y = 3 \\ x - y = 1 \end{cases}",
            "display": True,
        }
    ]

    # Bàn soạn gom q-1..q-4 lệch so với A4 và đánh dấu trang 2 là .oversize-page.
    editor_pages = [
        {"page": 1, "questionIds": ["q-1", "q-2"], "oversize": False},
        {"page": 2, "questionIds": ["q-3", "q-4"], "oversize": True},
    ]

    report = audit_export_preflight(exam, editor_pages)
    alignment = report["pageBreakAlignment"]

    assert report["ready"] is True
    assert report["needsAttention"] is True
    assert alignment["editorPageCount"] == 2
    assert alignment["estimatedA4PageCount"] == 2
    assert alignment["explicitPageBreakOrdinals"] == [4]
    assert alignment["oversizePages"] == [2]
    assert alignment["oversizeQuestionIds"] == ["q-3", "q-4"]

    mismatches_by_qid = {item["questionId"]: item for item in alignment["pageMismatches"]}
    # q-3 lệch trang (editor=2 vs A4=1) và nằm trên trang oversize của bàn soạn.
    assert "page_number_mismatch" in mismatches_by_qid["q-3"]["reasons"]
    assert "oversize_page" in mismatches_by_qid["q-3"]["reasons"]
    # q-4 vượt chiều cao 1 trang A4 và nằm trên .oversize-page.
    assert "oversize_page" in mismatches_by_qid["q-4"]["reasons"]
    assert all(
        entry["oversize"] is True
        for entry in alignment["pageMap"]
        if entry["questionId"] in {"q-3", "q-4"}
    )

    # Khi không truyền editorPages, Python vẫn phát hiện câu 4 vượt chiều cao 1 trang A4.
    a4_only = audit_export_preflight(exam)
    assert a4_only["pageBreakAlignment"]["oversizePages"] == [2]
    assert a4_only["pageBreakAlignment"]["oversizeQuestionIds"] == ["q-4"]


def test_page_break_alignment_estimates_multi_page_overflow_and_missing_editor_entries():
    questions = [
        {
            "id": f"q-{i}",
            "v": 1,
            "type": "mcq",
            "points": 0.5,
            "stem": (
                f"Câu hỏi trắc nghiệm số {i} có nội dung dài vừa phải "
                "để kiểm tra ngắt trang A4 tự động."
            ),
            "options": [
                f"Phương án A cho câu {i}",
                f"Phương án B cho câu {i}",
                f"Phương án C cho câu {i}",
                f"Phương án D cho câu {i}",
            ],
            "answer": 0,
            "approval": {"version": 1, "status": "approved"},
        }
        for i in range(1, 8)
    ]
    exam = {"title": "Đề 7 câu trắc nghiệm", "questions": questions}

    report = audit_export_preflight(exam)
    alignment = report["pageBreakAlignment"]

    assert report["ready"] is True
    assert alignment["editorPageCount"] is None
    assert alignment["estimatedA4PageCount"] >= 2
    assert alignment["pageMap"][0]["estimatedA4Page"] == 1
    assert alignment["pageMap"][-1]["estimatedA4Page"] >= 2
    assert all(item["editorPage"] is None for item in alignment["pageMap"])

    # Nếu editorPages bỏ sót câu hỏi thì ghi nhận missing_from_editor_pages.
    partial_editor = [
        {"page": 1, "questionIds": ["q-1", "q-2", "q-3"], "oversize": False},
    ]
    partial_report = audit_export_preflight(exam, partial_editor)
    missing_ids = {
        item["questionId"]
        for item in partial_report["pageBreakAlignment"]["pageMismatches"]
        if "missing_from_editor_pages" in item["reasons"]
    }
    assert {"q-4", "q-5", "q-6", "q-7"}.issubset(missing_ids)

    # Nếu editorPages có trang trắng dư ở cuối, vẫn cảnh báo lệch tổng trang.
    clean = _make_clean_exam()
    trailing_blank = [
        {"page": 1, "questionIds": ["q-1", "q-2", "q-3"], "oversize": False},
        {"page": 2, "questionIds": ["q-4"], "oversize": False},
        {"page": 3, "questionIds": [], "oversize": False},
    ]
    trailing_report = audit_export_preflight(clean, trailing_blank)
    assert trailing_report["ready"] is True
    assert trailing_report["needsAttention"] is True
    assert any(w["code"] == "page_break_mismatch" for w in trailing_report["warnings"])


def test_ocr_review_items_flags_source_pages_and_linked_and_direct_questions():
    exam = _make_clean_exam()
    exam["docs"] = [
        {
            "id": "doc-scan",
            "name": "De_scan_vat_ly.pdf",
            "needsReview": False,
            "pages": [
                {
                    "number": 1,
                    "text": (
                        "Câu 1: Tính vận tốc [không rõ] với ký tự lỗi \ufffd và công thức "
                        r"$\frac{v^2}{2$ cùng <figure><svg></svg> và [HÌNH 1: Đồ thị v-t]."
                    ),
                    "needsReview": True,
                    "uncertain": ["vận tốc [không rõ]"],
                },
                {
                    "number": 2,
                    "text": r"Định luật II Newton: $F = m \cdot a$. Nội dung rõ nét.",
                    "needsReview": False,
                    "uncertain": False,
                },
            ],
        }
    ]
    # q-1 liên kết trang 1 OCR cần duyệt qua location legacy "Trang 1" (bản thân câu sạch).
    exam["questions"][0]["source"] = {"docId": "doc-scan", "location": "Trang 1"}
    # q-2 liên kết trang 2 sạch -> không bị đánh dấu.
    exam["questions"][1]["source"] = {"docId": "doc-scan", "page": 2}
    # q-3 mang trực tiếp dấu vết OCR cần duyệt + placeholder hình + công thức lỗi ở formulas.
    exam["questions"][2]["ocrNeedsReview"] = True
    exam["questions"][2]["needsReview"] = True
    exam["questions"][2]["stem"] = (
        "Xác định điện trở [không rõ] từ mạch \ufffd [HÌNH 2: Mạch nối tiếp]."
    )
    exam["questions"][2]["formulas"] = [{"id": "f-bad", "latex": r"\frac{U}{R", "display": True}]

    report = audit_export_preflight(exam)
    items = report["ocrReviewItems"]

    source_items = [item for item in items if item["kind"] == "source_page"]
    question_items = [item for item in items if item["kind"] == "question"]

    assert len(source_items) == 1
    src = source_items[0]
    assert src["docId"] == "doc-scan"
    assert src["docName"] == "De_scan_vat_ly.pdf"
    assert src["page"] == 1
    assert src["questionId"] is None
    assert src["ordinal"] is None
    assert src["figureCount"] >= 1
    assert src["uncertainCount"] >= 4
    for expected_reason in (
        "page_needs_review",
        "uncertain_tokens",
        "unknown_marker",
        "replacement_char",
        "unbalanced_braces",
        "unclosed_figure_tag",
        "figure_placeholder",
    ):
        assert expected_reason in src["reasons"]
    assert "De_scan_vat_ly.pdf" in src["message"]

    by_qid = {item["questionId"]: item for item in question_items}
    assert set(by_qid) == {"q-1", "q-3"}

    linked_q = by_qid["q-1"]
    assert linked_q["docId"] == "doc-scan"
    assert linked_q["docName"] == "De_scan_vat_ly.pdf"
    assert linked_q["page"] == 1
    assert linked_q["ordinal"] == 1
    assert "source_page_needs_review" in linked_q["reasons"]

    direct_q = by_qid["q-3"]
    assert direct_q["ordinal"] == 3
    assert direct_q["figureCount"] >= 1
    assert direct_q["mathBlockCount"] >= 1
    assert direct_q["uncertainCount"] >= 3
    for expected_reason in (
        "question_ocr_needs_review",
        "question_needs_review",
        "unknown_marker",
        "replacement_char",
        "figure_placeholder",
        "invalid_math",
    ):
        assert expected_reason in direct_q["reasons"]

    assert report["needsAttention"] is True
    assert report["summary"]["ocrReviewCount"] == len(items)


@pytest.mark.parametrize("bad_points", [-0.25, 0.333, 1.125, True, "abc"])
def test_blocking_issues_reject_invalid_quarter_points_and_negative_values(bad_points: Any):
    exam = _make_clean_exam()
    exam["questions"][0]["points"] = bad_points

    report = audit_export_preflight(exam)

    assert report["ready"] is False
    codes = {item["code"] for item in report["blockingIssues"]}
    assert "invalid_points" in codes


def test_blocking_issues_catch_points_q4_and_rubric_sum_mismatch_and_bare_math():
    exam = _make_clean_exam()
    # Lệch points và pointsQ4 ở câu 1.
    exam["questions"][0]["pointsQ4"] = 3
    # Công thức trần thiếu ngoặc ngoài dấu $ ở câu 3.
    exam["questions"][2]["stem"] = r"Rút gọn biểu thức \frac{x+1}{2 rồi tính tại x=3."
    # Tổng barem câu 4 không khớp điểm câu (1.5 != 2.25).
    exam["questions"][3]["rubric"] = [
        {"text": "Bước 1", "points": 0.75},
        {"text": "Bước 2", "points": 0.75},
    ]

    report = audit_export_preflight(exam)

    assert report["ready"] is False
    found = {(item["ordinal"], item["code"]) for item in report["blockingIssues"]}
    assert (1, "invalid_points") in found
    assert (3, "invalid_math") in found
    assert (4, "invalid_rubric") in found


def test_blocking_issues_catch_missing_mcq_options_answer_rubric_and_invalid_math():
    exam = _make_clean_exam()
    # Câu 1: MCQ thiếu phương án & thiếu đáp án.
    exam["questions"][0]["options"] = ["3", "4"]
    exam["questions"][0]["answer"] = None
    # Câu 2: Công thức hỏng cú pháp trong stem (thiếu ngoặc đóng) và richDoc (mathInline hỏng).
    exam["questions"][1]["stem"] = r"Tính giá trị $\frac{x+1}{2$ biết $x > 0$."
    exam["questions"][1]["richDoc"] = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "mathInline", "attrs": {"latex": r"\sqrt{x", "display": False}}
                ],
            }
        ],
    }
    # Câu 3: Trả lời ngắn chưa xác nhận đáp án + công thức mở không đóng.
    exam["questions"][2]["answerKnown"] = False
    exam["questions"][2]["stem"] = "Tìm $x + 1 khi biết kết quả bằng 5."
    # Câu 4: Tự luận thiếu barem dù có explanation + công thức formulas thiếu \end{cases}.
    exam["questions"][3]["rubric"] = []
    exam["questions"][3]["explanation"] = "Giải thích sơ bộ nhưng chưa chia ý barem."
    exam["questions"][3]["formulas"] = [{"id": "f-broken", "latex": r"\begin{cases} x = 1"}]

    report = audit_export_preflight(exam)

    assert report["ready"] is False
    found = {(item["ordinal"], item["code"]) for item in report["blockingIssues"]}
    assert (1, "missing_options") in found
    assert (1, "missing_answer") in found
    assert (2, "invalid_math") in found
    assert (3, "missing_answer") in found
    assert (3, "invalid_math") in found
    assert (4, "missing_rubric") in found
    assert (4, "invalid_math") in found


def test_empty_exam_reports_blocking_issue_and_invalid_input_raises_ai_error():
    empty_report = audit_export_preflight({"title": "Đề trống", "questions": []})
    assert empty_report["ready"] is False
    assert empty_report["blockingIssues"][0]["code"] == "empty_exam"
    assert empty_report["summary"]["totalQuestions"] == 0
    assert empty_report["pageBreakAlignment"]["estimatedA4PageCount"] == 0

    with pytest.raises(AIError) as err:
        audit_export_preflight({"title": "Thiếu questions"})
    assert err.value.code == "invalid_exam"
    assert err.value.http_status == 422


def test_fastapi_preflight_route_enforces_extra_forbid_401_guest_and_workspace_compatibility():
    app = FastAPI()

    # Giả lập exception handler cũ trả 409 để bảo đảm route vẫn trả đúng 401/422.
    @app.exception_handler(AIError)
    async def legacy_ai_handler(_request: Request, error: AIError) -> JSONResponse:
        return JSONResponse({"error": str(error), "code": error.code}, status_code=409)

    def team_style_owner_resolver(request: Request) -> str | None:
        return request.headers.get("X-Team-User")

    install_export_preflight(app, owner_resolver=team_style_owner_resolver)

    clean_exam = _make_clean_exam()
    valid_payload = {
        "exam": clean_exam,
        "editorPages": [
            {"page": 1, "questionIds": ["q-1", "q-2", "q-3"], "oversize": False},
            {"page": 2, "questionIds": ["q-4"], "oversize": False},
        ],
    }

    with TestClient(app) as client:
        # 1. Guest chưa đăng nhập (owner_resolver trả None) -> 401 auth_required.
        guest_resp = client.post("/api/exports/preflight", json=valid_payload)
        assert guest_resp.status_code == 401
        assert guest_resp.json() == {
            "error": "Cần đăng nhập trước khi kiểm bản in.",
            "code": "auth_required",
        }
        assert guest_resp.headers["cache-control"] == "no-store"

        headers = {"X-Team-User": "gv-toan-01"}

        # 2. 422 với extra="forbid" ở cấp gốc và bên trong editorPages.
        extra_root = client.post(
            "/api/exports/preflight",
            headers=headers,
            json={**valid_payload, "unexpected": True},
        )
        assert extra_root.status_code == 422

        extra_page = client.post(
            "/api/exports/preflight",
            headers=headers,
            json={
                "exam": clean_exam,
                "editorPages": [{"page": 1, "questionIds": ["q-1"], "extraKey": 123}],
            },
        )
        assert extra_page.status_code == 422

        # 3. 422 khi page < 1, page là bool hoặc exam thiếu questions: list.
        bad_page_zero = client.post(
            "/api/exports/preflight",
            headers=headers,
            json={
                "exam": clean_exam,
                "editorPages": [{"page": 0, "questionIds": ["q-1"]}],
            },
        )
        assert bad_page_zero.status_code == 422

        bad_page_bool = client.post(
            "/api/exports/preflight",
            headers=headers,
            json={
                "exam": clean_exam,
                "editorPages": [{"page": True, "questionIds": ["q-1"]}],
            },
        )
        assert bad_page_bool.status_code == 422

        missing_questions = client.post(
            "/api/exports/preflight",
            headers=headers,
            json={"exam": {"title": "Không có danh sách câu"}},
        )
        assert missing_questions.status_code == 422

        # 4. Đề sạch với người dùng đã đăng nhập -> 200 ready=True.
        ok_resp = client.post("/api/exports/preflight", headers=headers, json=valid_payload)
        assert ok_resp.status_code == 200, ok_resp.text
        body = ok_resp.json()
        assert body["ready"] is True
        assert body["needsAttention"] is False
        assert body["ownerId"] == "gv-toan-01"
        assert body["pageBreakAlignment"]["editorPageCount"] == 2
        assert body["pageBreakAlignment"]["estimatedA4PageCount"] == 2

    # 5. Chế độ local mặc định (owner_resolver=None) vẫn hoạt động trực tiếp.
    local_app = FastAPI()
    install_export_preflight(local_app)
    with TestClient(local_app) as local_client:
        local_resp = local_client.post("/api/exports/preflight", json=valid_payload)
        assert local_resp.status_code == 200
        assert local_resp.json()["ownerId"] == "local"
        assert local_resp.json()["ready"] is True

    # 6. Tương thích kiểu team_workspace khi owner_resolver chủ động ném HTTPException(401).
    strict_team_app = FastAPI()

    def raising_resolver(request: Request) -> str:
        user = request.headers.get("X-Session")
        if not user:
            raise HTTPException(status_code=401, detail="Đăng nhập trước khi tiếp tục.")
        return user

    install_export_preflight(strict_team_app, owner_resolver=raising_resolver)
    with TestClient(strict_team_app) as team_client:
        assert team_client.post("/api/exports/preflight", json=valid_payload).status_code == 401
        authed = team_client.post(
            "/api/exports/preflight",
            headers={"X-Session": "gv-team-02"},
            json=valid_payload,
        )
        assert authed.status_code == 200
        assert authed.json()["ownerId"] == "gv-team-02"


def test_uc9_stale_evidence_detects_doc_change_manual_version_and_quote():
    base_ev = {
        "sourceId": "doc-clean",
        "sourceVersion": 1,
        "questionVersion": 1,
        "locator": {"kind": "page", "index": 1},
        "quote": "Hàm số bậc nhất y = 2x + 1",
    }

    # 1. Nguồn khớp hoàn toàn (kể cả khi q.quote=True với khoảng trắng chuẩn hóa) -> không cảnh báo.
    ok_exam = _make_clean_exam()
    ok_exam["quote"] = {"text": "Hàm   số bậc nhất\n  y = 2x + 1 xác định trên R."}
    ok_exam["questions"][0]["quote"] = True
    ok_exam["questions"][0]["evidence"] = [deepcopy(base_ev)]
    ok_rep = audit_export_preflight(ok_exam)
    assert not [w for w in ok_rep["warnings"] if w["code"] == "stale_quote_evidence"]

    # 2. Đổi tệp nguồn sang docId khác -> stale_quote_evidence.
    changed_doc_exam = deepcopy(ok_exam)
    changed_doc_exam["questions"][0]["source"] = {"docId": "doc-other", "page": 1}
    rep_doc = audit_export_preflight(changed_doc_exam)
    warns_doc = [w for w in rep_doc["warnings"] if w["code"] == "stale_quote_evidence"]
    assert len(warns_doc) == 1
    assert warns_doc[0]["requiresReverification"] is True

    # 3. Gỡ tệp nguồn (chuyển bản nhập tay, src_doc_id is None) -> stale_quote_evidence.
    manual_exam = deepcopy(ok_exam)
    manual_exam["questions"][0]["source"] = {"docId": None, "location": "Bản nhập tay"}
    rep_manual = audit_export_preflight(manual_exam)
    warns_manual = [w for w in rep_manual["warnings"] if w["code"] == "stale_quote_evidence"]
    assert len(warns_manual) == 1

    # 4. evidence.questionVersion != question.v -> stale_quote_evidence.
    ver_exam = deepcopy(ok_exam)
    ver_exam["questions"][0]["v"] = 2
    rep_ver = audit_export_preflight(ver_exam)
    warns_ver = [w for w in rep_ver["warnings"] if w["code"] == "stale_quote_evidence"]
    assert len(warns_ver) == 1

    # 5. question.quote=True nhưng trích dẫn không có trong exam.quote.text -> stale_quote_evidence.
    quote_changed_exam = deepcopy(ok_exam)
    quote_changed_exam["quote"] = {"text": "Ngữ liệu mới hoàn toàn khác với đoạn cũ."}
    rep_quote = audit_export_preflight(quote_changed_exam)
    warns_quote = [w for w in rep_quote["warnings"] if w["code"] == "stale_quote_evidence"]
    assert len(warns_quote) == 1
