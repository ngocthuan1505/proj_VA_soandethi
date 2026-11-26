"""Kiểm thử UV64 cho danh mục SGK KNTT (Toán 5, Toán 9, Toán 12) và metadata API."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from mach_backend.curriculum_sources import CurriculumSourceCreate
from mach_backend.lesson_catalog import (
    KNTT_SERIES,
    lesson_catalog,
    search_lesson_catalog,
    to_curriculum_source_payload,
)
from mach_backend.local_workspace import create_app


def _kntt_by_grade(grade: str) -> list[dict]:
    return [
        col
        for col in lesson_catalog()
        if col.get("series") == KNTT_SERIES and col["subject"] == "Toán" and col["grade"] == grade
    ]


def test_toan_9_kntt_has_all_10_chapters_and_full_chapter_8_probability():
    cols = _kntt_by_grade("9")
    volumes = {col["volume"]: col for col in cols}
    assert set(volumes) == {"Tập một", "Tập hai"}

    t1_chapters = list(dict.fromkeys(lesson["chapter"] for lesson in volumes["Tập một"]["lessons"]))
    t2_chapters = list(dict.fromkeys(lesson["chapter"] for lesson in volumes["Tập hai"]["lessons"]))
    all_chapters = t1_chapters + t2_chapters
    assert len(all_chapters) == 10

    ch8_name = "Chương VIII. Xác suất của biến cố trong một số mô hình xác suất đơn giản"
    assert ch8_name in t2_chapters

    ch8_lessons = [
        lesson for lesson in volumes["Tập hai"]["lessons"] if lesson["chapter"] == ch8_name
    ]
    assert len(ch8_lessons) == 3
    joined = " | ".join(
        f"{item['title']} {item['summary']} {' '.join(item['learningOutcomes'])}"
        for item in ch8_lessons
    ).lower()
    assert "phép thử ngẫu nhiên và không gian mẫu" in joined
    assert "xác suất của biến cố" in joined
    assert "kiểm nghiệm" in joined and "luyện tập" in joined


def test_toan_12_kntt_splits_bai_18_and_bai_19_and_keyword_search():
    t2 = next(col for col in _kntt_by_grade("12") if col["volume"] == "Tập hai")
    titles = [lesson["title"] for lesson in t2["lessons"]]
    assert "Bài 18: Xác suất có điều kiện" in titles
    assert "Bài 19: Công thức xác suất toàn phần và công thức Bayes" in titles

    keyword_expectations = [
        ("vectơ", "Bài 6: Vectơ và hệ trục tọa độ trong không gian Oxyz"),
        (
            "thống kê",
            "Bài 9: Khoảng biến thiên, khoảng tứ phân vị, phương sai và độ lệch chuẩn mẫu "
            "ghép nhóm",
        ),
        ("mặt cầu", "Bài 14: Phương trình mặt phẳng, đường thẳng và mặt cầu trong không gian"),
        ("xác suất có điều kiện", "Bài 18: Xác suất có điều kiện"),
        ("Bayes", "Bài 19: Công thức xác suất toàn phần và công thức Bayes"),
    ]
    for query, expected_title in keyword_expectations:
        hits = search_lesson_catalog(query, subject="Toán", grade=12, book=KNTT_SERIES)
        hit_titles = [lesson["title"] for col in hits for lesson in col["lessons"]]
        assert expected_title in hit_titles, f"Không tìm thấy '{expected_title}' khi tìm '{query}'"


def test_toan_5_kntt_fixes_lessons_58_59_60_and_missing_topics():
    cols = _kntt_by_grade("5")
    t2 = next(col for col in cols if col["volume"] == "Tập hai")
    t2_titles = [lesson["title"] for lesson in t2["lessons"]]
    assert "Bài 58: Nhân, chia số đo thời gian với một số" in t2_titles
    assert "Bài 59: Vận tốc của một chuyển động đều" in t2_titles
    assert "Bài 60: Quãng đường, thời gian của một chuyển động đều" in t2_titles

    required_keywords = [
        "km2",
        "ha",
        "m2",
        "cm3",
        "dm3",
        "m3",
        "diện tích hình tam giác",
        "hình thang",
        "hình tròn",
        "thống kê",
        "xác suất",
        "ôn tập học kỳ I",
        "ôn tập cuối năm",
    ]
    for kw in required_keywords:
        hits = search_lesson_catalog(kw, subject="Toán", grade=5, book=KNTT_SERIES)
        assert hits and any(col["lessons"] for col in hits), f"Toán 5 KNTT thiếu chủ đề '{kw}'"

    for col in cols:
        total_chars = sum(
            len(to_curriculum_source_payload(col, idx)["content_excerpt"])
            for idx in range(1, len(col["lessons"]) + 1)
        )
        assert total_chars <= 12_000
        for idx in range(1, len(col["lessons"]) + 1):
            CurriculumSourceCreate.model_validate(to_curriculum_source_payload(col, idx))


def test_kntt_api_payload_includes_standard_metadata(tmp_path: Path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        res = client.get("/api/lesson-catalog")
        assert res.status_code == 200
        collections = res.json()["collections"]
    kntt = [col for col in collections if col.get("series") == KNTT_SERIES]
    assert len(kntt) >= 80
    for col in kntt:
        assert col["publisher"] == "NXB Giáo dục Việt Nam"
        assert col["series"] == "Kết nối tri thức với cuộc sống"
        assert col["edition"] == "GDPT 2018"
        assert col["contentType"] == "summary_outline"
