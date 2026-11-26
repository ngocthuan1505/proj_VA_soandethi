"""Kiểm thử kho SGK Bộ Kết nối tri thức với cuộc sống (GDPT 2018) Lớp 1–12 và tương thích IT-09."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from mach_backend.ai_contract import validate_ai_text
from mach_backend.curriculum_sources import CurriculumSourceCreate
from mach_backend.lesson_catalog import (
    KNTT_SERIES,
    lesson_catalog,
    search_lesson_catalog,
    to_curriculum_source_payload,
)

ORIGINAL_15: tuple[tuple[str, str, str, str, int], ...] = (
    ("toan-9-dai-so-1", "Toán", "9", "Đại số THCS", 4),
    ("toan-9-dai-so-2", "Toán", "9", "Đại số THCS", 2),
    ("toan-5-so-do", "Toán", "5", "Số và đo lường", 1),
    ("vat-li-10-chuyen-dong", "Vật lí", "10", "Cơ học nhập môn", 1),
    ("toan-9-hinh-hoc-1", "Toán", "9", "Hình học THCS", 3),
    ("toan-10-dai-so-hinh-1", "Toán", "10", "Đại số và Hình học THPT", 2),
    ("toan-12-giai-tich-1", "Toán", "12", "Giải tích và Thống kê THPT", 2),
    ("ngu-van-9-doc-hieu-1", "Ngữ văn", "9", "Ngữ liệu Đọc hiểu THCS", 2),
    ("ngu-van-11-doc-hieu-1", "Ngữ văn", "11", "Ngữ liệu Đọc hiểu THPT", 2),
    ("tieng-anh-9-doc-hieu-1", "Tiếng Anh", "9", "Ngữ liệu Tiếng Anh THCS", 2),
    ("tieng-anh-11-doc-hieu-1", "Tiếng Anh", "11", "Ngữ liệu Tiếng Anh THPT", 2),
    ("khtn-9-thuc-hanh-1", "Khoa học tự nhiên", "9", "Thực hành Khoa học tự nhiên THCS", 2),
    ("vat-li-11-dien-song-1", "Vật lí", "11", "Vật lí thực nghiệm THPT", 2),
    ("hoa-hoc-10-phan-ung-1", "Hoá học", "10", "Hóa học THPT Thực nghiệm", 2),
    ("sinh-hoc-10-thuc-hanh-1", "Sinh học", "10", "Sinh học tế bào THPT", 2),
)


def test_original_15_collections_and_it09_invariants_preserved():
    collections = lesson_catalog()
    by_id = {col["id"]: col for col in collections}
    for key, subject, grade, book, lesson_count in ORIGINAL_15:
        expected_id = str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1"))
        assert expected_id in by_id, f"Thiếu bộ gốc {key}"
        col = by_id[expected_id]
        assert col["version"] == 1
        assert col["sourceTitle"] == f"Khung học liệu tự biên soạn · {subject} {grade} ({book})"
        assert len(col["lessons"]) == lesson_count

    toan9_daiso_1 = search_lesson_catalog(
        subject="Toán", grade=9, book="Đại số THCS", volume="Tập 1"
    )
    assert len(toan9_daiso_1) == 1
    assert any(
        lesson["chapter"] == "Phương trình và hệ phương trình"
        and lesson["title"] == "Giải hệ bằng phép thế"
        for lesson in toan9_daiso_1[0]["lessons"]
    )

    it09_exact = search_lesson_catalog(
        "giai he bang phep the", subject="Toán", grade=9, book="Đại số THCS", volume="Tập 1"
    )
    assert [lesson["title"] for col in it09_exact for lesson in col["lessons"]] == [
        "Giải hệ bằng phép thế"
    ]


def test_kntt_catalog_covers_grades_1_to_12_and_required_subjects():
    kntt = [col for col in lesson_catalog() if col.get("series") == KNTT_SERIES]
    assert len(kntt) >= 80

    grades = {int(col["grade"]) for col in kntt}
    assert grades == set(range(1, 13))

    by_subject_grade: dict[str, set[int]] = {}
    for col in kntt:
        by_subject_grade.setdefault(col["subject"], set()).add(int(col["grade"]))

    assert by_subject_grade["Toán"] == set(range(1, 13))
    assert by_subject_grade["Tiếng Việt"] == set(range(1, 6))
    assert by_subject_grade["Ngữ văn"] == set(range(6, 13))
    assert by_subject_grade["Tiếng Anh"] == set(range(3, 13))
    assert by_subject_grade["Khoa học tự nhiên"] == set(range(6, 10))
    assert by_subject_grade["Lịch sử và Địa lí"] == set(range(4, 10))
    for thpt_subject in ("Vật lí", "Hoá học", "Sinh học", "Tin học", "Lịch sử", "Địa lí"):
        assert by_subject_grade[thpt_subject] == {10, 11, 12}, f"Thiếu {thpt_subject} THPT"


def test_kntt_toan_10_tap_mot_reference_structure():
    hits = search_lesson_catalog(subject="Toán", grade=10, book=KNTT_SERIES, volume="Tập một")
    assert len(hits) == 1
    toan10 = hits[0]
    assert toan10["totalPages"] == 106
    assert toan10["volumesAvailable"] == ["Tập một", "Tập hai", "Chuyên đề học tập"]
    assert toan10["series"] == KNTT_SERIES

    lessons = toan10["lessons"]
    assert len(lessons) >= 15

    bai1 = lessons[0]
    assert bai1["chapter"] == "Chương I: Mệnh đề và tập hợp"
    assert bai1["title"] == "Bài 1: Mệnh đề"
    assert bai1["pageStart"] == 5
    assert bai1["pageEnd"] == 11
    assert bai1["pageRange"] == "tr. 5-11"
    assert bai1["periods"] == 3

    bai2 = lessons[1]
    assert bai2["title"] == "Bài 2: Tập hợp và các phép toán trên tập hợp"
    assert bai2["pageRange"] == "tr. 12-19"
    assert bai2["periods"] == 4
    assert len(bai2["learningOutcomes"]) >= 2
    assert bai2["summary"].strip()

    chapters = {lesson["chapter"] for lesson in lessons}
    assert "Chương I: Mệnh đề và tập hợp" in chapters
    assert "Chương II: Bất phương trình và hệ bất phương trình bậc nhất hai ẩn" in chapters
    assert "Chương III: Hệ thức lượng trong tam giác" in chapters
    assert "Chương IV: Vectơ" in chapters
    assert "Chương V: Các số đặc trưng của mẫu số liệu không ghép nhóm" in chapters


def test_every_kntt_collection_and_lesson_schema_and_12k_payload_limit():
    collections = lesson_catalog()
    seen_ids: set[str] = set()
    kntt_collections = [col for col in collections if col.get("series") == KNTT_SERIES]
    assert kntt_collections

    for col in collections:
        UUID(col["id"])
        assert col["id"] not in seen_ids
        seen_ids.add(col["id"])

    for col in kntt_collections:
        assert col["version"] == 1
        assert col["book"] == KNTT_SERIES
        assert col["series"] == KNTT_SERIES
        assert col["volume"] in {"Tập một", "Tập hai", "Chuyên đề học tập"}
        assert col["volume"] in col["volumesAvailable"]
        assert isinstance(col["totalPages"], int) and col["totalPages"] > 0
        assert col["sourceTitle"] == (
            f"Khung học liệu tự biên soạn · {col['subject']} {col['grade']} ({KNTT_SERIES})"
        )

        total_formatted_chars = 0
        for idx, lesson in enumerate(col["lessons"], 1):
            assert lesson["number"] == idx
            assert isinstance(lesson["id"], str) and lesson["id"]
            assert isinstance(lesson["pageStart"], int) and lesson["pageStart"] >= 1
            assert isinstance(lesson["pageEnd"], int) and lesson["pageEnd"] >= lesson["pageStart"]
            assert lesson["pageRange"].startswith("tr. ")
            assert isinstance(lesson["periods"], int) and lesson["periods"] >= 1
            assert isinstance(lesson["summary"], str) and lesson["summary"].strip()
            assert isinstance(lesson["learningOutcomes"], list) and lesson["learningOutcomes"]
            for field in ("chapter", "title", "outcome", "text", "summary"):
                validate_ai_text(lesson[field])
            for item in lesson["learningOutcomes"]:
                validate_ai_text(item)

            payload = to_curriculum_source_payload(col, idx)
            CurriculumSourceCreate.model_validate(payload)
            assert len(payload["content_excerpt"]) <= 12_000
            total_formatted_chars += len(payload["content_excerpt"])

        assert total_formatted_chars <= 12_000, (
            f"{col['name']} vượt 12.000 ký tự ({total_formatted_chars})"
        )


def test_kntt_accent_insensitive_search():
    hits = search_lesson_catalog("tap hop va cac phep toan", subject="Toán", grade=10)
    titles = [lesson["title"] for col in hits for lesson in col["lessons"]]
    assert "Bài 2: Tập hợp và các phép toán trên tập hợp" in titles

    bayes_hits = search_lesson_catalog("cong thuc bayes", subject="Toán", grade=12)
    bayes_titles = [lesson["title"] for col in bayes_hits for lesson in col["lessons"]]
    assert "Bài 18: Xác suất có điều kiện và công thức Bayes" in bayes_titles
