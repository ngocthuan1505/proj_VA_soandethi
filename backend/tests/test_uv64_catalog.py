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
        assert isinstance(col["bookTitle"], str) and col["bookTitle"].strip()
        assert isinstance(col["officialTitle"], str) and col["officialTitle"].strip()
        assert isinstance(col["sourceUrl"], str) and col["sourceUrl"].startswith("https://")


def test_kntt_toan_5_bai_6_phan_so_and_bai_64_bieu_do_quat_tron():
    for query in ("Bài 6", "cộng trừ hai phân số", "phân số khác mẫu số"):
        hits = search_lesson_catalog(query, subject="Toán", grade=5, book=KNTT_SERIES)
        titles = [lesson["title"] for col in hits for lesson in col["lessons"]]
        assert "Bài 6: Cộng, trừ hai phân số khác mẫu số" in titles

    chart_hits = search_lesson_catalog(
        "biểu đồ hình quạt tròn", subject="Toán", grade=5, book=KNTT_SERIES
    )
    chart_titles = [lesson["title"] for col in chart_hits for lesson in col["lessons"]]
    assert "Bài 64: Biểu đồ hình quạt tròn" in chart_titles


def test_kntt_toan_5_reviewed_lessons_have_own_pages_and_preserve_saved_numbers():
    expected = {
        "Tập một": {
            17: 60,
            18: 62,
            30: 120,
            33: 130,
            34: 133,
            35: 135,
        },
        "Tập hai": {
            51: 48,
            54: 58,
            55: 60,
            66: 96,
            67: 100,
            69: 107,
            70: 111,
            71: 113,
            72: 119,
            73: 121,
            74: 123,
            75: 128,
        },
    }
    for col in _kntt_by_grade("5"):
        assert col["version"] == 2
        lessons = col["lessons"]
        assert sorted(lesson["number"] for lesson in lessons) == list(range(1, len(lessons) + 1))
        by_lesson = {
            int(lesson["title"].split(":")[0].removeprefix("Bài ")): lesson for lesson in lessons
        }
        assert list(by_lesson) == sorted(by_lesson)
        for number, page_start in expected[col["volume"]].items():
            lesson = by_lesson[number]
            assert lesson["pageStart"] == page_start
            assert page_start <= lesson["pageEnd"] <= col["totalPages"]
            assert to_curriculum_source_payload(col, lesson["number"])["title"] == lesson["title"]
        if col["volume"] == "Tập một":
            assert by_lesson[19]["id"] == "kntt-toan-5-t1-b15"
            assert by_lesson[31]["id"] == "kntt-toan-5-t1-b22"
        else:
            assert by_lesson[50]["id"] == "kntt-toan-5-t2-b8"
            assert by_lesson[51]["id"] == "kntt-toan-5-t2-b9"
            assert by_lesson[64]["id"] == "kntt-toan-5-t2-b16"


def test_kntt_ngu_van_12_bai_4_5_9_chuyen_de_3_and_aligned_writing_6_8():
    hits = search_lesson_catalog(subject="Ngữ văn", grade=12, book=KNTT_SERIES)
    by_vol = {col["volume"]: col for col in hits}
    assert set(by_vol) == {"Tập một", "Tập hai", "Chuyên đề học tập"}

    t1_joined = " | ".join(
        f"{lesson['chapter']} {lesson['title']}" for lesson in by_vol["Tập một"]["lessons"]
    )
    assert "Bài 4: Yếu tố kì ảo trong truyện kể" in t1_joined
    assert "Bài 5: Tiếng cười của hài kịch" in t1_joined

    t2_joined = " | ".join(
        f"{lesson['chapter']} {lesson['title']}" for lesson in by_vol["Tập hai"]["lessons"]
    )
    assert "Bài 9: Văn học và cuộc đời" in t2_joined

    cd_joined = " | ".join(
        f"{lesson['chapter']} {lesson['title']}"
        for lesson in by_vol["Chuyên đề học tập"]["lessons"]
    )
    assert "Chuyên đề 3:" in cd_joined
    assert "trường phái văn học" in cd_joined.lower()

    # Khớp đúng kỹ năng viết từng bài 6-8 theo mục lục NXB
    bai6_hits = search_lesson_catalog(
        "báo cáo dự án", subject="Ngữ văn", grade=12, book=KNTT_SERIES
    )
    assert any("Bài 6:" in lesson["chapter"] for col in bai6_hits for lesson in col["lessons"])
    bai7_hits = search_lesson_catalog(
        "ứng xử của tuổi trẻ", subject="Ngữ văn", grade=12, book=KNTT_SERIES
    )
    assert any("Bài 7:" in lesson["chapter"] for col in bai7_hits for lesson in col["lessons"])
    bai8_hits = search_lesson_catalog("viết thư", subject="Ngữ văn", grade=12, book=KNTT_SERIES)
    assert any("Bài 8:" in lesson["chapter"] for col in bai8_hits for lesson in col["lessons"])


def test_kntt_toan_10_t2_splits_lessons_15_to_27_and_tieng_anh_8_12_units_khtn_8():
    t2_hits = search_lesson_catalog(subject="Toán", grade=10, book=KNTT_SERIES, volume="Tập hai")
    assert len(t2_hits) == 1
    t2 = t2_hits[0]
    assert t2["version"] == 2
    assert (
        t2["sourceUrl"]
        == "https://sachdientu.nxbgd.vn/thu-vien-so/doc-sach/shs-toan-tap-2.4491365365"
    )
    t2_lessons = t2["lessons"]
    assert len(t2_lessons) == 13
    assert [lesson["title"].split(":")[0] for lesson in t2_lessons] == [
        f"Bài {number}" for number in range(15, 28)
    ]
    assert sorted(lesson["number"] for lesson in t2_lessons) == list(range(1, 14))
    by_id = {lesson["id"]: lesson for lesson in t2_lessons}
    for number, old_lesson in enumerate((16, 17, 19, 23, 26), start=1):
        lesson = by_id[f"kntt-toan-10-t2-b{number}"]
        assert lesson["number"] == number
        assert lesson["title"].startswith(f"Bài {old_lesson}:")
    assert to_curriculum_source_payload(t2, 1)["title"] == "Bài 16: Hàm số bậc hai"

    newton_hits = search_lesson_catalog(
        "nhị thức newton", subject="Toán", grade=10, book=KNTT_SERIES, volume="Tập hai"
    )
    assert [lesson["title"] for col in newton_hits for lesson in col["lessons"]] == [
        "Bài 25: Nhị thức Newton"
    ]

    ta8_hits = search_lesson_catalog(subject="Tiếng Anh", grade=8, book=KNTT_SERIES)
    assert len(ta8_hits) == 1
    ta8 = ta8_hits[0]
    assert ta8["volume"] == "Cả năm"
    assert ta8["totalPages"] == 128
    assert "Global Success" in ta8["bookTitle"]
    assert "heid.vn" in ta8["sourceUrl"]
    assert len(ta8["lessons"]) == 12
    for u in range(1, 13):
        assert any(lesson["title"].startswith(f"Unit {u}:") for lesson in ta8["lessons"]), (
            f"Thiếu Unit {u}"
        )

    for kw, expected in (
        ("sinh quyển", "Bài 45: Sinh quyển"),
        ("bảo vệ môi trường", "Bài 47: Bảo vệ môi trường"),
    ):
        khtn_hits = search_lesson_catalog(
            kw, subject="Khoa học tự nhiên", grade=8, book=KNTT_SERIES
        )
        titles = [lesson["title"] for col in khtn_hits for lesson in col["lessons"]]
        assert expected in titles
