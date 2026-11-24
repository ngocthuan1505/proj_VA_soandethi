"""Kiểm thử mở rộng thư viện học liệu đủ 12 khối lớp, chuẩn hóa điểm thập phân và .cmd."""

from __future__ import annotations

import io
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from docx import Document

from mach_backend.ai_contract import AIError, validate_ai_text
from mach_backend.curriculum_sources import CurriculumSourceCreate
from mach_backend.exam_spec_export import (
    build_matrix_and_specification,
    export_answer_key_rubric_docx,
    export_answer_key_rubric_html,
    export_matrix_specification_docx,
    export_matrix_specification_html,
    export_student_exam_html,
    format_points_vi,
    validate_and_normalize_answer_key,
)
from mach_backend.lesson_catalog import (
    lesson_catalog,
    search_lesson_catalog,
    to_curriculum_source_payload,
)
from mach_backend.matrix_import import matrix_slots

REPO_ROOT = Path(__file__).resolve().parents[2]

ORIGINAL_15_COLLECTIONS: tuple[tuple[str, str, int], ...] = (
    ("toan-9-dai-so-1", "Toán 9 · Đại số THCS · Tập 1", 4),
    ("toan-9-dai-so-2", "Toán 9 · Đại số THCS · Tập 2", 2),
    ("toan-5-so-do", "Toán 5 · Số và đo lường · Tập 1", 1),
    ("vat-li-10-chuyen-dong", "Vật lí 10 · Cơ học nhập môn · Tập 1", 1),
    ("toan-9-hinh-hoc-1", "Toán 9 · Hình học THCS · Tập 1", 3),
    ("toan-10-dai-so-hinh-1", "Toán 10 · Đại số và Hình học THPT · Tập 1", 2),
    ("toan-12-giai-tich-1", "Toán 12 · Giải tích và Thống kê THPT · Tập 1", 2),
    ("ngu-van-9-doc-hieu-1", "Ngữ văn 9 · Ngữ liệu Đọc hiểu THCS · Tập 1", 2),
    ("ngu-van-11-doc-hieu-1", "Ngữ văn 11 · Ngữ liệu Đọc hiểu THPT · Tập 1", 2),
    ("tieng-anh-9-doc-hieu-1", "Tiếng Anh 9 · Ngữ liệu Tiếng Anh THCS · Tập 1", 2),
    ("tieng-anh-11-doc-hieu-1", "Tiếng Anh 11 · Ngữ liệu Tiếng Anh THPT · Tập 1", 2),
    ("khtn-9-thuc-hanh-1", "Khoa học tự nhiên 9 · Thực hành Khoa học tự nhiên THCS · Tập 1", 2),
    ("vat-li-11-dien-song-1", "Vật lí 11 · Vật lí thực nghiệm THPT · Tập 1", 2),
    ("hoa-hoc-10-phan-ung-1", "Hoá học 10 · Hóa học THPT Thực nghiệm · Tập 1", 2),
    ("sinh-hoc-10-thuc-hanh-1", "Sinh học 10 · Sinh học tế bào THPT · Tập 1", 2),
)


def test_catalog_covers_all_12_grades_and_preserves_original_15_collections():
    collections = lesson_catalog()
    total_lessons = sum(len(item["lessons"]) for item in collections)
    assert len(collections) >= 36
    assert total_lessons >= 75

    grades_present = {int(item["grade"]) for item in collections}
    assert grades_present == set(range(1, 13))

    by_id = {item["id"]: item for item in collections}
    for key, expected_name, expected_lesson_count in ORIGINAL_15_COLLECTIONS:
        expected_id = str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1"))
        assert expected_id in by_id, f"Mất bộ gốc {key}"
        col = by_id[expected_id]
        assert col["name"] == expected_name
        assert col["version"] == 1
        assert len(col["lessons"]) == expected_lesson_count

    subjects = {item["subject"] for item in collections}
    for subject in (
        "Toán",
        "Tiếng Việt",
        "Ngữ văn",
        "Tiếng Anh",
        "Khoa học tự nhiên",
        "Lịch sử và Địa lí",
        "Tin học",
        "Vật lí",
        "Hoá học",
        "Sinh học",
    ):
        assert subject in subjects

    for col in collections:
        UUID(col["id"])
        grade_num = int(col["grade"])
        expected_level = "Tiểu học" if grade_num <= 5 else ("THCS" if grade_num <= 9 else "THPT")
        assert col["gradeLevel"] == expected_level
        assert col["curriculumStandard"] == "GDPT 2018"
        assert col["schoolYear"] == "2026-2027"
        assert col["sourceOrigin"] == "lesson_catalog"
        assert col["sourceTitle"] == (
            f"Khung học liệu tự biên soạn · {col['subject']} {col['grade']} ({col['book']})"
        )
        assert col["licenseStatus"] == "allowed"
        assert len(col["sha256"]) == 64

        total_formatted = 0
        for idx, lesson in enumerate(col["lessons"], 1):
            assert lesson["number"] == idx
            for field in ("chapter", "title", "outcome", "text"):
                validate_ai_text(lesson[field])
            payload = to_curriculum_source_payload(col, idx)
            CurriculumSourceCreate.model_validate(payload)
            total_formatted += len(payload["content_excerpt"])
        assert total_formatted <= 12_000


def test_search_lesson_catalog_supports_tieng_viet_and_ngu_van_cross_alias():
    # Tìm môn Tiếng Việt ở từng lớp Tiểu học 1..5
    for grade in range(1, 6):
        tv_hits = search_lesson_catalog(subject="Tiếng Việt", grade=grade)
        assert tv_hits, f"Thiếu Tiếng Việt lớp {grade}"
        assert all(item["subject"] == "Tiếng Việt" for item in tv_hits)

        # Tìm chéo bằng subject='Ngữ văn' ở khối Tiểu học vẫn trả về bộ Tiếng Việt tương ứng
        cross_hits = search_lesson_catalog(subject="Ngữ văn", grade=grade)
        assert [item["id"] for item in cross_hits] == [item["id"] for item in tv_hits]

    # Tìm chéo bằng subject='Tiếng Việt' ở khối THCS/THPT vẫn trả về bộ Ngữ văn tương ứng
    for grade in range(6, 13):
        nv_hits = search_lesson_catalog(subject="Ngữ văn", grade=grade)
        assert nv_hits, f"Thiếu Ngữ văn lớp {grade}"
        cross_tv = search_lesson_catalog(subject="Tiếng Việt", grade=grade)
        assert [item["id"] for item in cross_tv] == [item["id"] for item in nv_hits]

    # Khi không lọc khối, kết quả khớp chính xác tên môn luôn đứng trước kết quả alias
    all_nv = search_lesson_catalog(subject="Ngữ văn")
    assert all_nv[0]["subject"] == "Ngữ văn"
    all_tv = search_lesson_catalog(subject="Tiếng Việt")
    assert all_tv[0]["subject"] == "Tiếng Việt"

    # Giữ nguyên hợp đồng test_rich_sample_catalog.py:270
    van_col = search_lesson_catalog("tram khi tuong", subject="Ngữ văn")[0]
    assert van_col["name"] == "Ngữ văn 9 · Ngữ liệu Đọc hiểu THCS · Tập 1"


def test_matrix_import_error_messages_have_clean_vietnamese_spacing():
    with pytest.raises(AIError) as err_invalid:
        matrix_slots([{"topic": "Đại số", "targets": ["x", 0, 0]}])
    assert "nguyên 0..30" in str(err_invalid.value)
    assert "nguyên0..30" not in str(err_invalid.value)

    with pytest.raises(AIError) as err_dup:
        matrix_slots(
            [
                {"topic": "Đại số", "type": "mcq", "targets": [1, 0, 0]},
                {"topic": "đại số", "type": "mcq", "targets": [1, 0, 0]},
            ]
        )
    assert "Nhận 1–30 câu" in str(err_dup.value)
    assert "Nhận1–30câu" not in str(err_dup.value)

    with pytest.raises(AIError) as err_budget:
        matrix_slots([{"topic": "Đại số", "type": "mcq", "targets": [1, 0, 0], "pointsQ4": 39}])
    assert "đúng 10" in str(err_budget.value)
    assert "0,25 điểm" in str(err_budget.value)
    assert "đúng10" not in str(err_budget.value)
    assert "0,25điểm" not in str(err_budget.value)


def test_exam_spec_export_formats_two_decimal_places_consistently():
    assert format_points_vi(0.05) == "0,05 điểm"
    assert format_points_vi(0.4) == "0,40 điểm"
    assert format_points_vi(9.6) == "9,60 điểm"
    assert format_points_vi(10) == "10,00 điểm"

    exam = {
        "title": "Đề kiểm tra bước điểm 0,05",
        "school": "THPT Thực Nghiệm",
        "subject": "Toán",
        "grade": "11",
        "minutes": 45,
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "topic": "Lượng giác",
                "lesson": "Bài 1: Giá trị lượng giác",
                "level": 0,
                "points": 0.4,
                "stem": "Tính $\\sin^2 x + \\cos^2 x$.",
                "options": ["$1$", "$0$", "$2$", "$-1$"],
                "answer": 0,
                "explanation": "Hằng đẳng thức lượng giác cơ bản bằng $1$.",
            },
            {
                "id": "q2",
                "type": "essay",
                "topic": "Dãy số",
                "lesson": "Bài 2: Cấp số cộng",
                "level": 2,
                "points": 9.6,
                "stem": "Tìm tổng $4$ số hạng đầu của cấp số cộng có $u_1=3, d=4$.",
                "explanation": "Áp dụng công thức $S_4 = 36$.",
                "rubric": [
                    {"text": "Tìm đúng $u_4 = 15$", "points": 3.05},
                    {"text": "Tính đúng $S_4 = 36$", "points": 6.55},
                ],
            },
        ],
    }

    spec = build_matrix_and_specification(exam)
    assert spec["total_points_label"] == "10,00 điểm"
    assert [row["total_points_label"] for row in spec["rows"]] == ["0,40 điểm", "9,60 điểm"]
    assert [row["points_label"] for row in spec["specification_rows"]] == [
        "0,40 điểm",
        "9,60 điểm",
    ]

    key = validate_and_normalize_answer_key(exam, teacher=True)
    assert key["total_points_label"] == "10,00 điểm"
    assert key["objective_points_label"] == "0,40 điểm"
    assert key["essay_points_label"] == "9,60 điểm"
    assert key["objective_answers"][0]["points_label"] == "0,40 điểm"
    assert key["essay_rubrics"][0]["points_label"] == "9,60 điểm"
    assert [step["points_label"] for step in key["essay_rubrics"][0]["rubric"]] == [
        "3,05 điểm",
        "6,55 điểm",
    ]

    spec_html = export_matrix_specification_html(exam)
    assert "0,40 điểm" in spec_html
    assert "9,60 điểm" in spec_html
    assert "10,00 điểm" in spec_html

    key_html = export_answer_key_rubric_html(exam, teacher=True)
    assert "0,40 điểm" in key_html
    assert "9,60 điểm" in key_html
    assert "3,05 điểm" in key_html
    assert "6,55 điểm" in key_html
    assert "10,00 điểm" in key_html

    student_html = export_student_exam_html(exam)
    assert "0,40 điểm" in student_html
    assert "9,60 điểm" in student_html
    assert "10,00 điểm" in student_html

    for binary in (
        export_matrix_specification_docx(exam),
        export_answer_key_rubric_docx(exam, teacher=True),
    ):
        doc = Document(io.BytesIO(binary))
        full_text = "\n".join(
            [p.text for p in doc.paragraphs]
            + [cell.text for tbl in doc.tables for row in tbl.rows for cell in row.cells]
        )
        assert "0,40 điểm" in full_text
        assert "9,60 điểm" in full_text
        assert "10,00 điểm" in full_text


@pytest.mark.parametrize(
    "cmd_name",
    [
        "CHAY_THU_NHOM.cmd",
        "CHAY_DEMO_VA_LOG.cmd",
        "CHAY_NHOM_CO_TAI_KHOAN.cmd",
        "MO_APP_LOCAL.cmd",
        "MO_APP_VA_LOG.cmd",
        "MO_LOG_POC.cmd",
        "START-DEMO.cmd",
    ],
)
def test_all_windows_cmd_launchers_use_utf8_codepage(cmd_name: str):
    path = REPO_ROOT / cmd_name
    assert path.is_file(), f"Thiếu tệp launcher {cmd_name}"
    content = path.read_text(encoding="utf-8")
    assert "chcp 65001 >nul" in content
    assert "\ufffd" not in content
