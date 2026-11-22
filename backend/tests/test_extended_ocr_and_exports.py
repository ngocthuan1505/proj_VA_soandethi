"""Kiểm thử mở rộng cho OCR giữ công thức/hình, Đáp án & Barem 0,25đ, Ma trận & Đặc tả A4/DOCX."""

from __future__ import annotations

import base64
import io
import zipfile
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from docx import Document
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.exam_spec_export import (
    build_matrix_and_specification,
    export_answer_key_rubric_docx,
    export_answer_key_rubric_html,
    export_matrix_specification_docx,
    export_matrix_specification_html,
    export_student_exam_html,
    install_extended_exports,
    latex_to_mathml,
    redact_exam_for_student,
    validate_and_normalize_answer_key,
)
from mach_backend.local_documents import extract_text
from mach_backend.math_word import M, omml
from mach_backend.ocr_structured import structure_ocr_reading

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@pytest.fixture
def sample_exam() -> dict:
    return {
        "title": "Đề kiểm tra giữa kỳ I Toán 9",
        "school": "THCS Chuẩn Thực Nghiệm",
        "subject": "Toán",
        "grade": "9",
        "minutes": 60,
        "questions": [
            {
                "id": "q-1",
                "type": "mcq",
                "topic": "Căn thức",
                "lesson": "Bài 1: Căn bậc hai",
                "level": 0,
                "points": 0.5,
                "stem": r"Giá trị biểu thức $\frac{x^2+1}{2}$ tại $x=3$ là bao nhiêu?",
                "options": ["3", "4", "5", "6"],
                "answer": 2,
                "explanation": r"Thay $x=3$ được $\frac{3^2+1}{2}=5$.",
                "competency": "Nhận biết giá trị biểu thức chứa căn/phân thức",
            },
            {
                "id": "q-2",
                "type": "truefalse",
                "topic": "Căn thức",
                "lesson": "Bài 1: Căn bậc hai",
                "level": "Thông hiểu",
                "points": 1.0,
                "stem": r"Xét các khẳng định về $\sqrt{x^2}$:",
                "options": [
                    r"$\sqrt{9}=3$",
                    r"$\sqrt{(-4)^2}=-4$",
                    r"$\sqrt{0}=0$",
                    r"$\sqrt{16}=-4$",
                ],
                "truthValues": [True, False, True, False],
                "explanation": r"$\sqrt{a^2}=|a|$ nên âm bị loại.",
                "competency": r"Phân biệt hằng đẳng thức $\sqrt{a^2}=|a|$",
            },
            {
                "id": "q-3",
                "type": "short",
                "topic": "Phương trình bậc hai",
                "lesson": "Bài 2: Công thức nghiệm",
                "level": 2,
                "points": 1.25,
                "stem": r"Tìm nghiệm dương của $x^2 - 49 = 0$.",
                "answerText": r"$\sqrt{49}$",
                "explanation": r"Vì $x>0$ nên $x=\sqrt{49}=7$.",
                "competency": "Giải phương trình bậc hai cơ bản",
            },
            {
                "id": "q-4",
                "type": "essay",
                "topic": "Phương trình bậc hai",
                "lesson": "Bài 3: Hệ thức Vi-ét",
                "level": 3,
                "points": 2.25,
                "stem": r"Giải và biện luận phương trình $\frac{x^2+1}{2} = m$ theo tham số $m$.",
                "explanation": "Áp dụng điều kiện $x^2 = 2m - 1 \\ge 0$.",
                "rubric": [
                    {"text": r"Biến đổi tương đương về $x^2 = 2m - 1$", "points": 0.75},
                    {
                        "text": r"Xét $2m - 1 < 0 \Leftrightarrow m < \frac{1}{2}$: vô nghiệm",
                        "points": 0.75,
                    },
                    {
                        "text": r"Xét $m \ge \frac{1}{2}$: kết luận nghiệm $\pm\sqrt{2m-1}$",
                        "points": 0.75,
                    },
                ],
                "competency": "Vận dụng cao biện luận nghiệm phương trình chứa tham số",
            },
        ],
    }


def test_ocr_preserves_latex_and_maps_figures_by_page():
    reading = {
        "method": "gemini_document_ocr",
        "notes": "Bản đọc rõ chữ",
        "pages": [
            {
                "number": 2,
                "text": (
                    "Câu 2: Cho $$\\sqrt{x^2 + 1} = 5$$ và phương trình x^2 - 4 = 0.\n"
                    "Hình 2: Tam giác ABC vuông tại A.\n"
                    '<figure><svg width="10" height="10"></svg>'
                    "<figcaption>Sơ đồ mạch</figcaption></figure>"
                ),
                "uncertain": False,
            },
            {
                "number": 1,
                "text": (
                    "Câu 1: Rút gọn $\\frac{x^2+1}{2}$ với giá trị \\$5.\n"
                    "[HÌNH 1: Đồ thị hàm số y=x^2]\n"
                    "![Parabol](assets/parabol.png)\n"
                    "Công thức trần \\frac{a+b}{2}."
                ),
                "uncertain": False,
            },
        ],
    }

    structured = structure_ocr_reading(reading)
    assert structured["page_count"] == 2
    assert [p["number"] for p in structured["pages"]] == [1, 2]
    assert structured["needs_teacher_review"] is False
    assert structured["uncertain_regions"] == []

    # Công thức được giữ nguyên vẹn cả ở raw text lẫn math_blocks[].
    assert r"$\frac{x^2+1}{2}$" in structured["pages"][0]["text"]
    latex_list = [b["latex"] for b in structured["math_blocks"]]
    assert r"\frac{x^2+1}{2}" in latex_list
    assert r"\frac{a+b}{2}" in latex_list
    assert any(
        r"\sqrt{x^2 + 1} = 5" in item and b["display"]
        for b, item in zip(structured["math_blocks"], latex_list, strict=True)
    )
    assert any("x^2 - 4 = 0" in item for item in latex_list)

    # Hình vẽ được gắn chính xác theo từng số trang.
    figs_p1 = [f for f in structured["figures"] if f["page"] == 1]
    figs_p2 = [f for f in structured["figures"] if f["page"] == 2]
    assert len(figs_p1) == 2
    assert figs_p1[0]["kind"] == "placeholder"
    assert "[HÌNH 1" in figs_p1[0]["raw"]
    assert figs_p1[1]["kind"] == "markdown_image" and figs_p1[1]["src"] == "assets/parabol.png"
    assert len(figs_p2) == 2
    assert figs_p2[0]["kind"] == "caption" and "Hình 2:" in figs_p2[0]["raw"]
    assert figs_p2[1]["kind"] == "figure_tag" and "Sơ đồ mạch" in figs_p2[1]["label"]


@pytest.mark.parametrize(
    "text,uncertain_flag,expected_reason",
    [
        (r"Tính $\frac{x^2+1}{2}$ bị mất dấu đóng $x + 1", False, "unbalanced_dollar"),
        ("Câu 1: Mở $$x+1$ sai dấu đóng", False, "unbalanced_dollar"),
        (r"Tính $\frac{x^2+1{2}$ lỗi ngoặc", False, "unbalanced_braces"),
        (r"Công thức trần \frac{x+1}{2 thiếu ngoặc đóng", False, "unbalanced_braces"),
        ("Vùng chữ mờ [không rõ] cần kiểm tra", False, "unknown_marker"),
        ("Ký tự lỗi mã hóa \ufffd xuất hiện", False, "replacement_char"),
        ("Trang đọc bình thường nhưng OCR nghi ngờ", True, "page_marked_uncertain"),
        ("<figure><svg></svg> thiếu thẻ đóng", False, "unclosed_figure_tag"),
    ],
)
def test_ocr_detects_suspicious_regions_and_forces_teacher_review_without_mutating_text(
    text, uncertain_flag, expected_reason
):
    reading = {"pages": [{"number": 1, "text": text, "uncertain": uncertain_flag}]}
    result = structure_ocr_reading(reading)
    assert result["needs_teacher_review"] is True
    assert result["pages"][0]["text"] == text
    assert any(region["reason"] == expected_reason for region in result["uncertain_regions"])


def test_answer_key_and_rubric_validates_quarter_points_and_separates_sections(sample_exam):
    data = validate_and_normalize_answer_key(sample_exam, teacher=True)
    assert data["total_questions"] == 4
    assert data["total_points"] == 5.0
    assert data["objective_points"] == 2.75
    assert data["essay_points"] == 2.25
    assert [a["answer_label"] for a in data["objective_answers"]] == [
        "C",
        "1. Đúng · 2. Sai · 3. Đúng · 4. Sai",
        r"$\sqrt{49}$",
    ]
    assert len(data["essay_rubrics"]) == 1
    assert len(data["essay_rubrics"][0]["rubric"]) == 3


@pytest.mark.parametrize("bad_points", [-0.25, 0.3, 1.1, 0.125, True, "abc"])
def test_answer_key_and_matrix_reject_invalid_quarter_points(sample_exam, bad_points):
    bad_exam = deepcopy(sample_exam)
    bad_exam["questions"][0]["points"] = bad_points
    with pytest.raises(AIError) as err:
        validate_and_normalize_answer_key(bad_exam, teacher=True)
    assert err.value.http_status == 422
    with pytest.raises(AIError) as m_err:
        build_matrix_and_specification(bad_exam)
    assert m_err.value.http_status == 422


def test_rubric_sum_mismatch_and_missing_answer_are_rejected(sample_exam):
    mismatch = deepcopy(sample_exam)
    mismatch["questions"][3]["rubric"][0]["points"] = 1.0  # tổng 2.5 != 2.25
    with pytest.raises(AIError) as err:
        validate_and_normalize_answer_key(mismatch, teacher=True)
    assert err.value.code == "invalid_rubric" and err.value.http_status == 422

    missing_ans = deepcopy(sample_exam)
    missing_ans["questions"][0]["answer"] = None
    with pytest.raises(AIError) as err2:
        validate_and_normalize_answer_key(missing_ans, teacher=True)
    assert err2.value.code == "missing_answer_key" and err2.value.http_status == 422


def test_student_copy_blocks_answer_key_and_prevents_leak(sample_exam):
    secret_exam = deepcopy(sample_exam)
    secret_exam["questions"][0]["explanation"] = "GIAI_BI_MAT_01"
    secret_exam["questions"][2]["answerText"] = "DAP_AN_BI_MAT_02"
    secret_exam["questions"][3]["rubric"][0]["text"] = "BAREM_BI_MAT_03"
    secret_exam["chat"] = [{"text": "CHAT_NOI_BO_BI_MAT"}]

    before = deepcopy(secret_exam)
    with pytest.raises(AIError) as err:
        export_answer_key_rubric_html(secret_exam, teacher=False)
    assert err.value.http_status == 403 and err.value.code == "teacher_only"

    with pytest.raises(AIError) as err_docx:
        export_answer_key_rubric_docx(secret_exam, teacher=False)
    assert err_docx.value.http_status == 403

    redacted = redact_exam_for_student(secret_exam)
    assert secret_exam == before
    assert "chat" not in redacted
    assert redacted["questions"][0]["answer"] is None
    assert "explanation" not in redacted["questions"][0]
    assert "answerText" not in redacted["questions"][2]
    assert "rubric" not in redacted["questions"][3]

    student_html = export_student_exam_html(secret_exam)
    for secret in ("GIAI_BI_MAT_01", "DAP_AN_BI_MAT_02", "BAREM_BI_MAT_03", "CHAT_NOI_BO_BI_MAT"):
        assert secret not in student_html
    assert "@page { size: A4; margin: 18mm 18mm 20mm 20mm; }" in student_html


def test_matrix_and_specification_computes_4_levels_and_percentages(sample_exam):
    matrix = build_matrix_and_specification(sample_exam)
    assert matrix["total_questions"] == 4
    assert matrix["total_points"] == 5.0
    assert len(matrix["rows"]) == 3  # 2 bài trong Căn thức (gộp 1 bài? không, 2 câu cùng Bài 1!)

    # Câu 1 (NB, 0.5) và Câu 2 (TH, 1.0) cùng ("Căn thức", "Bài 1: Căn bậc hai")
    first_row = matrix["rows"][0]
    assert first_row["topic"] == "Căn thức"
    assert first_row["lesson"] == "Bài 1: Căn bậc hai"
    assert first_row["total_questions"] == 2
    assert first_row["total_points"] == 1.5
    assert first_row["percentage"] == 30.0
    assert first_row["levels"]["Nhận biết"]["count"] == 1
    assert first_row["levels"]["Thông hiểu"]["count"] == 1

    # Kiểm tra tổng 4 mức độ & tổng tỷ lệ % = 100%.
    by_level = matrix["by_level"]
    assert [
        by_level[name]["count"] for name in ("Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao")
    ] == [
        1,
        1,
        1,
        1,
    ]
    assert by_level["Nhận biết"]["percentage"] == 10.0
    assert by_level["Thông hiểu"]["percentage"] == 20.0
    assert by_level["Vận dụng"]["percentage"] == 25.0
    assert by_level["Vận dụng cao"]["percentage"] == 45.0
    assert sum(by_level[name]["percentage"] for name in by_level) == pytest.approx(100.0)
    assert len(matrix["specification_rows"]) == 4


def test_html_a4_exports_contain_print_css_and_escape_xss(sample_exam):
    xss_exam = deepcopy(sample_exam)
    xss_exam["title"] = 'Đề thi <script>alert("xss")</script>'
    xss_exam["questions"][0]["topic"] = '<img src=x onerror="alert(1)">'
    xss_exam["questions"][0]["explanation"] = "Giải <script>evil()</script> với $x<5$"
    xss_exam["questions"][3]["rubric"][0]["text"] = "Bước <script>bad()</script>"
    xss_exam["questions"][3]["competency"] = 'Năng lực "><script>x()</script>'

    answer_html = export_answer_key_rubric_html(xss_exam, teacher=True)
    matrix_html = export_matrix_specification_html(xss_exam)

    for html_doc in (answer_html, matrix_html):
        assert "@page { size: A4; margin: 18mm 18mm 20mm 20mm; }" in html_doc
        assert ".a4-sheet" in html_doc
        assert "break-inside: avoid" in html_doc
        assert "<script" not in html_doc.lower()
        assert "&lt;script&gt;" in html_doc


def test_docx_exports_contain_ooxml_tables_and_omath_and_open_cleanly_in_python_docx(sample_exam):
    # Kiểm tra chuyển đổi LaTeX -> MathML -> OMML thuần Python.
    mathml = latex_to_mathml(r"\frac{x^2+1}{2} + \sqrt{49}")
    omml_elem = omml(mathml)
    assert omml_elem.find(".//" + M + "f") is not None
    assert omml_elem.find(".//" + M + "rad") is not None

    ans_bytes = export_answer_key_rubric_docx(sample_exam, teacher=True)
    mat_bytes = export_matrix_specification_docx(sample_exam)

    for binary, expected_tables in ((ans_bytes, 2), (mat_bytes, 2)):
        with zipfile.ZipFile(io.BytesIO(binary)) as zf:
            assert zf.testzip() is None
            doc_xml = ET.fromstring(zf.read("word/document.xml"))
            assert len(doc_xml.findall(".//" + W + "tbl")) == expected_tables
            assert len(doc_xml.findall(".//" + M + "oMath")) > 0

        doc = Document(io.BytesIO(binary))
        assert len(doc.tables) == expected_tables

    # Round-trip kiểm tra công thức từ DOCX đáp án/barem và hóa học \ce bằng Python thuần.
    chem_omml = omml(latex_to_mathml(r"\ce{2H2 + O2 -> 2H2O}"))
    assert chem_omml.find(".//" + M + "sSub") is not None

    extracted = extract_text(
        "dap_an.docx",
        "data:application/octet-stream;base64," + base64.b64encode(ans_bytes).decode(),
    )
    full_text = extracted["pages"][0]["text"]
    assert "BẢN DÀNH CHO GIÁO VIÊN" in full_text
    assert r"\frac" in full_text
    assert r"\sqrt{49}" in full_text

    extracted_matrix = extract_text(
        "ma_tran.docx",
        "data:application/octet-stream;base64," + base64.b64encode(mat_bytes).decode(),
    )
    matrix_text = extracted_matrix["pages"][0]["text"]
    assert "MA TRẬN VÀ BẢNG ĐẶC TẢ" in matrix_text
    assert "100.00%" in matrix_text


def test_mcq_letter_answer_is_normalized_cleanly(sample_exam):
    exam = deepcopy(sample_exam)
    exam["questions"][0]["answer"] = "B"
    data = validate_and_normalize_answer_key(exam, teacher=True)
    assert data["objective_answers"][0]["answer_label"] == "B"


def test_fastapi_routes_enforce_validation_teacher_gate_and_owner_resolver(sample_exam):
    app = FastAPI()

    # Giả lập exception handler của local_workspace trả 409 để xác nhận route vẫn trả đúng 422/403.
    @app.exception_handler(AIError)
    async def legacy_ai_handler(_request: Request, error: AIError) -> JSONResponse:
        return JSONResponse({"error": str(error), "code": error.code}, status_code=409)

    def resolve_owner(request: Request) -> str:
        user = request.headers.get("X-Owner")
        if not user:
            raise HTTPException(status_code=401, detail="Thiếu thông tin người dùng.")
        return user

    install_extended_exports(app, owner_resolver=resolve_owner)

    with TestClient(app) as client:
        # Thiếu header owner -> 401
        unauth = client.post(
            "/api/ocr/structure",
            json={"pages": [{"number": 1, "text": "$x^2$", "uncertain": False}]},
        )
        assert unauth.status_code == 401

        headers = {"X-Owner": "gv-toan-01"}

        # Route 1: POST /api/ocr/structure
        ocr_resp = client.post(
            "/api/ocr/structure",
            headers=headers,
            json={
                "reading": {
                    "pages": [
                        {
                            "number": 1,
                            "text": r"Tính $\frac{x^2+1}{2}$ [không rõ]",
                            "uncertain": False,
                        }
                    ]
                }
            },
        )
        assert ocr_resp.status_code == 200
        body = ocr_resp.json()
        assert body["ownerId"] == "gv-toan-01"
        assert body["needs_teacher_review"] is True
        assert body["math_blocks"][0]["latex"] == r"\frac{x^2+1}{2}"

        # Extra field bị chặn bởi extra="forbid"
        bad_ocr = client.post(
            "/api/ocr/structure",
            headers=headers,
            json={"pages": [{"number": 1, "text": "x"}], "unknown": 1},
        )
        assert bad_ocr.status_code == 422

        # Route 2: POST /api/exports/answer-key-rubric (HTML & DOCX)
        ans_html = client.post(
            "/api/exports/answer-key-rubric",
            headers=headers,
            json={"exam": sample_exam, "format": "html"},
        )
        assert ans_html.status_code == 200
        assert "text/html" in ans_html.headers["content-type"]
        assert "@page { size: A4; margin: 18mm 18mm 20mm 20mm; }" in ans_html.text

        ans_docx = client.post(
            "/api/exports/answer-key-rubric",
            headers=headers,
            json={"exam": sample_exam, "format": "docx"},
        )
        assert ans_docx.status_code == 200
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in ans_docx.headers["content-type"]
        )
        assert len(Document(io.BytesIO(ans_docx.content)).tables) == 2

        # Chặn bản học sinh lấy đáp án & barem -> 403 (cả teacher=False lẫn audience="student")
        blocked = client.post(
            "/api/exports/answer-key-rubric",
            headers=headers,
            json={"exam": sample_exam, "format": "html", "teacher": False},
        )
        assert blocked.status_code == 403
        blocked_student = client.post(
            "/api/exports/answer-key-rubric",
            headers=headers,
            json={"exam": sample_exam, "format": "docx", "audience": "student"},
        )
        assert blocked_student.status_code == 403

        # Hỗ trợ ?format=docx qua query param và bắt lệch query vs body -> 422
        mat_query_docx = client.post(
            "/api/exports/matrix-specification?format=docx",
            headers=headers,
            json={"exam": sample_exam},
        )
        assert mat_query_docx.status_code == 200
        assert len(Document(io.BytesIO(mat_query_docx.content)).tables) == 2
        mismatch_fmt = client.post(
            "/api/exports/matrix-specification?format=html",
            headers=headers,
            json={"exam": sample_exam, "format": "docx"},
        )
        assert mismatch_fmt.status_code == 422

        # Lệch bước 0,25 điểm -> 422
        bad_exam = deepcopy(sample_exam)
        bad_exam["questions"][0]["points"] = 0.35
        bad_points = client.post(
            "/api/exports/answer-key-rubric",
            headers=headers,
            json={"exam": bad_exam, "format": "html"},
        )
        assert bad_points.status_code == 422

        # Route 3: POST /api/exports/matrix-specification (HTML & DOCX)
        mat_html = client.post(
            "/api/exports/matrix-specification",
            headers=headers,
            json={"exam": sample_exam, "format": "html"},
        )
        assert mat_html.status_code == 200
        assert "BẢNG MA TRẬN 4 MỨC ĐỘ" in mat_html.text
        assert "BẢNG ĐẶC TẢ ĐỀ KIỂM TRA" in mat_html.text

        mat_docx = client.post(
            "/api/exports/matrix-specification",
            headers=headers,
            json={"exam": sample_exam, "format": "docx"},
        )
        assert mat_docx.status_code == 200
        assert len(Document(io.BytesIO(mat_docx.content)).tables) == 2

        # Khổ A4 ngang (landscape) cho Ma trận & Đặc tả
        mat_land = client.post(
            "/api/exports/matrix-specification",
            headers=headers,
            json={"exam": sample_exam, "format": "docx", "orientation": "landscape"},
        )
        assert mat_land.status_code == 200
        land_doc = Document(io.BytesIO(mat_land.content))
        sec = land_doc.sections[0]
        assert sec.page_width.mm == pytest.approx(297, abs=0.5)
        assert sec.page_height.mm == pytest.approx(210, abs=0.5)
        mat_land_html = client.post(
            "/api/exports/matrix-specification",
            headers=headers,
            json={"exam": sample_exam, "format": "html", "orientation": "landscape"},
        )
        assert mat_land_html.status_code == 200
        assert "size:A4 landscape;" in mat_land_html.text


def test_matrix_percentages_always_sum_to_exact_100_via_largest_remainder():
    exam = {
        "title": "Đề 3 chủ đề đồng đều",
        "questions": [
            {"id": f"q{i}", "type": "mcq", "topic": f"Chủ đề {i}", "level": i % 3, "points": 1.0}
            for i in range(1, 4)
        ],
    }
    data = build_matrix_and_specification(exam)
    assert round(sum(r["percentage"] for r in data["rows"]), 2) == 100.0
    assert round(sum(r["percentage"] for r in data["specification_rows"]), 2) == 100.0
    assert round(sum(v["percentage"] for v in data["by_level"].values()), 2) == 100.0
    assert round(sum(v["percentage"] for v in data["by_type"].values()), 2) == 100.0
