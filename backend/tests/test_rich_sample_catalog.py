"""Kiểm thử kho bài học mẫu đa môn tự soạn, PoC đa môn, tìm kiếm NFD và trích dẫn."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from mach_backend.ai_contract import Locator, validate_ai_text, validate_sources
from mach_backend.ai_questions import GenerateJob, validate_generation_plan
from mach_backend.ai_sources import SourceKey, workspace_page_sources
from mach_backend.curriculum_sources import CurriculumCitation, CurriculumSourceCreate
from mach_backend.exam_spec_export import (
    build_matrix_and_specification,
    export_answer_key_rubric_docx,
    export_matrix_specification_html,
)
from mach_backend.lesson_catalog import (
    lesson_catalog,
    normalize_nfd_text,
    search_lesson_catalog,
    to_curriculum_source_payload,
)
from mach_backend.local_documents import exam_variant, preview_exam_variant
from mach_backend.local_workspace import create_app

POC_DATA_DIR = Path(__file__).resolve().parents[1] / "poc-data"
LOCAL_ORIGIN = {"Origin": "http://testserver"}


def test_lesson_catalog_preserves_existing_contracts_and_covers_all_required_subjects():
    collections = lesson_catalog()
    by_name = {item["name"]: item for item in collections}

    # Giữ nguyên 4 bộ gốc và cấu trúc lọc cho E2E IT-09.
    assert by_name["Toán 9 · Đại số THCS · Tập 1"]["lessons"][0]["number"] == 1
    assert len(by_name["Toán 9 · Đại số THCS · Tập 1"]["lessons"]) == 4
    assert len(by_name["Toán 9 · Đại số THCS · Tập 2"]["lessons"]) == 2
    assert len(by_name["Toán 5 · Số và đo lường · Tập 1"]["lessons"]) == 1
    assert len(by_name["Vật lí 10 · Cơ học nhập môn · Tập 1"]["lessons"]) == 1

    toan9_daiso_1 = [
        item
        for item in collections
        if item["subject"] == "Toán"
        and item["grade"] == "9"
        and item["book"] == "Đại số THCS"
        and item["volume"] == "Tập 1"
    ]
    assert len(toan9_daiso_1) == 1

    subjects = {item["subject"] for item in collections}
    for required in (
        "Toán",
        "Ngữ văn",
        "Tiếng Anh",
        "Khoa học tự nhiên",
        "Vật lí",
        "Hoá học",
        "Sinh học",
    ):
        assert required in subjects, f"Thiếu môn {required} trong lesson_catalog()"

    seen_ids: set[str] = set()
    for collection in collections:
        UUID(collection["id"])
        assert collection["id"] not in seen_ids
        seen_ids.add(collection["id"])
        assert collection["version"] == 1
        assert collection["licenseStatus"] == "allowed"
        assert collection["licenseNote"].strip()
        assert collection["sourceOrigin"] == "lesson_catalog"
        assert len(collection["sha256"]) == 64
        grade_num = int(collection["grade"])
        assert 1 <= grade_num <= 12

        total_formatted_chars = 0
        for expected_num, lesson in enumerate(collection["lessons"], 1):
            assert lesson["number"] == expected_num
            for field in ("chapter", "title", "outcome", "text"):
                assert isinstance(lesson[field], str) and lesson[field].strip()
                validate_ai_text(lesson[field])
            formatted = (
                f"Bài {lesson['number']}. {lesson['title']}\n"
                f"{lesson['text']}\n"
                f"Mục tiêu: {lesson['outcome']}"
            )
            assert len(formatted) <= 12_000
            total_formatted_chars += len(formatted)
        # Bảo đảm chọn "Chọn cả tập" vẫn nằm dưới giới hạn 12.000 ký tự của ai_sources.py.
        assert total_formatted_chars <= 12_000


def test_lesson_catalog_subject_richness_latex_passages_and_tables():
    collections = lesson_catalog()
    texts_by_subject: dict[str, str] = {}
    for item in collections:
        combined = "\n".join(f"{lesson['title']}\n{lesson['text']}" for lesson in item["lessons"])
        texts_by_subject[item["subject"]] = (
            texts_by_subject.get(item["subject"], "") + "\n" + combined
        )

    assert r"\begin{cases}" in texts_by_subject["Toán"]
    assert r"\triangle" in texts_by_subject["Toán"]
    assert r"\int_0^2" in texts_by_subject["Toán"]
    assert "|" in texts_by_subject["Toán"]

    assert "[Đoạn 1]" in texts_by_subject["Ngữ văn"]
    assert "[Đoạn 2]" in texts_by_subject["Ngữ văn"]
    assert "[Đoạn 3]" in texts_by_subject["Ngữ văn"]

    assert "[Paragraph 1]" in texts_by_subject["Tiếng Anh"]
    assert "First conditional" in texts_by_subject["Tiếng Anh"]

    assert r"\ce{" in texts_by_subject["Khoa học tự nhiên"]
    assert r"\Omega" in texts_by_subject["Khoa học tự nhiên"]
    assert r"\ce{" in texts_by_subject["Hoá học"]
    assert r"\mathcal{E}" in texts_by_subject["Vật lí"]
    assert "co nguyên sinh" in texts_by_subject["Sinh học"]


@pytest.mark.parametrize(
    ("query", "expected_title"),
    [
        ("giai he bang phep the", "Giải hệ bằng phép thế"),
        ("truc tam va duong tron ngoai tiep", "Đường cao, trực tâm và đường tròn ngoại tiếp"),
        ("bang dinh muc van chuyen", "Lập hệ từ bảng định mức vận chuyển"),
        ("toi uu tuyen tinh", "Bài toán tối ưu tuyến tính từ bảng nguyên liệu"),
        ("dien tich hinh phang", "Diện tích hình phẳng giới hạn bởi hai đường cong"),
        ("tram khi tuong", "Ngữ liệu: Chiếc đèn dầu và cuốn sổ tay trạm khí tượng"),
        ("kiem chung thong tin", "Ngữ liệu: Giá trị của việc tự kiểm chứng thông tin"),
        ("nghe gom ven song", "Ngữ liệu: Bảo tồn tri thức nghề gốm ven sông"),
        ("rooftop herb garden", "School Rooftop Herb Garden"),
        ("repair cafes", "Neighborhood Repair Cafes"),
        ("dinh luat om", "Thí nghiệm kiểm chứng định luật Ôm với bảng đo"),
        ("phan ung trung hoa", "Thực hành phản ứng trung hòa và tính nồng độ"),
        ("suat dien dong", "Thí nghiệm xác định suất điện động và điện trở trong"),
        ("kim loai tac dung voi dung dich axit", "Thực hành kim loại tác dụng với dung dịch axit"),
        ("hoat tinh enzim", "Thí nghiệm ảnh hưởng của nhiệt độ đến hoạt tính enzim"),
    ],
)
def test_nfd_accent_insensitive_search_matches_rich_lessons(query: str, expected_title: str):
    # Kiểm cả chuỗi không dấu ASCII lẫn chuỗi tiếng Việt dạng NFD có dấu kết hợp.
    results = search_lesson_catalog(query)
    titles = [lesson["title"] for col in results for lesson in col["lessons"]]
    assert expected_title in titles

    nfd_query = unicodedata.normalize("NFD", expected_title)
    nfd_results = search_lesson_catalog(nfd_query)
    nfd_titles = [lesson["title"] for col in nfd_results for lesson in col["lessons"]]
    assert expected_title in nfd_titles

    # Đảm bảo IT-09 tìm 'giai he bang phep the' trong Toán 9 Đại số Tập 1 chỉ ra 1 bài duy nhất.
    it09_hits = search_lesson_catalog(
        "giai he bang phep the",
        subject="Toán",
        grade=9,
        book="Đại số THCS",
        volume="Tập 1",
    )
    assert [row["title"] for col in it09_hits for row in col["lessons"]] == [
        "Giải hệ bằng phép thế"
    ]


def test_normalize_nfd_handles_vietnamese_d_and_diacritics():
    assert normalize_nfd_text("  Đọc   hiểu  ĐƯỜNG TRÒN  ") == "doc hieu duong tron"
    assert normalize_nfd_text("Hoá học") == normalize_nfd_text("Hóa học") == "hoa hoc"


def test_all_catalog_lessons_validate_curriculum_sources_citation_and_ai_sources(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers=LOCAL_ORIGIN) as client:
        catalog_resp = client.get("/api/lesson-catalog")
        assert catalog_resp.status_code == 200
        collections = catalog_resp.json()["collections"]
        assert len(collections) >= 15

        # Kiểm từng bài hợp lệ Pydantic CurriculumSourceCreate & giải quyết trang nguồn AI.
        for collection in collections:
            doc_id = UUID(collection["id"])
            keys: tuple[SourceKey, ...] = tuple(
                (doc_id, Locator(kind="page", index=lesson["number"]))
                for lesson in collection["lessons"]
            )
            exam = {
                "docs": [
                    {
                        "id": collection["id"],
                        "version": collection["version"],
                        "catalog": True,
                        "licenseStatus": collection["licenseStatus"],
                    }
                ]
            }
            fragments = workspace_page_sources(exam, "local", keys, app.state.store.connect)
            assert len(fragments) == len(collection["lessons"])

            for lesson in collection["lessons"]:
                payload = to_curriculum_source_payload(collection, lesson["number"])
                CurriculumSourceCreate.model_validate(payload)

        # Tạo bản ghi thật qua API /api/lesson-catalog/sources, tìm NFD và gọi /citation.
        sample_targets = [
            ("toan-9-hinh-hoc-1", 1),
            ("ngu-van-9-doc-hieu-1", 1),
            ("tieng-anh-9-doc-hieu-1", 1),
            ("khtn-9-thuc-hanh-1", 2),
        ]
        by_key_id = {c["id"]: c for c in collections}

        for key, lesson_no in sample_targets:
            col = by_key_id[str(uuid5(NAMESPACE_URL, f"soan-de-thi/hoc-lieu/{key}/1"))]
            payload = to_curriculum_source_payload(col, lesson_no)
            created = client.post("/api/lesson-catalog/sources", json=payload)
            assert created.status_code == 201, created.text
            rec = created.json()
            assert rec["license_status"] == "allowed"

            nfd_q = unicodedata.normalize("NFD", rec["title"])
            found = client.get("/api/lesson-catalog/sources", params={"q": nfd_q})
            assert found.status_code == 200
            assert any(item["id"] == rec["id"] for item in found.json()["sources"])

            cite_res = client.get(f"/api/lesson-catalog/sources/{rec['id']}/citation")
            assert cite_res.status_code == 200, cite_res.text
            citation = CurriculumCitation.model_validate(cite_res.json())
            assert citation.sourceId == rec["id"]
            assert citation.licenseStatus == "allowed"
            assert citation.sha256 == rec["sha256"]
            assert payload["content_excerpt"] == citation.excerpt


def test_all_poc_data_datasets_validate_generate_job_and_10_point_plan():
    files = sorted(POC_DATA_DIR.glob("*.json"))
    expected_files = {
        "bio-tham-thau.json",
        "thu-vien.json",
        "toan-9-he-hinh.json",
        "ngu-van-9-doc-hieu.json",
        "tieng-anh-9-reading.json",
        "khtn-9-thuc-hanh.json",
    }
    assert expected_files.issubset({path.name for path in files})

    subjects_seen: set[str] = set()
    for path in files:
        raw_text = path.read_text(encoding="utf-8")
        job = GenerateJob.model_validate_json(raw_text)
        validate_generation_plan(job)
        validate_sources(job)
        validate_ai_text(job.instructions)
        for src in job.sources:
            validate_ai_text(src.text)
        assert sum(slot.pointsQ4 or 0 for slot in job.slots) == 40
        subjects_seen.add(job.subject)

        # Kiểm chứng parse JSON không dư trường lạ ngoài schema.
        parsed = json.loads(raw_text)
        assert parsed["ownerId"] == "poc-local"

    assert {"Sinh học", "Ngữ văn", "Toán", "Tiếng Anh", "Khoa học tự nhiên"}.issubset(subjects_seen)


def test_rich_catalog_passage_group_variant_and_exports_integration():
    van_col = search_lesson_catalog("tram khi tuong", subject="Ngữ văn")[0]
    passage_text = van_col["lessons"][0]["text"]
    toan_col = search_lesson_catalog("bang dinh muc van chuyen", subject="Toán")[0]
    toan_text = toan_col["lessons"][0]["text"]

    exam = {
        "id": str(uuid4()),
        "title": "Đề tổng hợp ngữ liệu tự soạn đa môn",
        "school": "THCS Thực nghiệm Mẫu",
        "subject": "Ngữ văn",
        "grade": "9",
        "minutes": 60,
        "questions": [
            {
                "id": "van-1",
                "type": "mcq",
                "topic": "Đọc hiểu tự sự",
                "lesson": van_col["lessons"][0]["title"],
                "level": 0,
                "points": 1.0,
                "passageId": "p-tram-khi-tuong",
                "groupId": "g-doc-hieu-1",
                "passageTitle": van_col["lessons"][0]["title"],
                "passageText": passage_text,
                "stem": "Vì sao Minh băn khoăn khi ra đọc vạch đo lúc 19 giờ?",
                "options": [
                    "Gió mùa thổi mạnh và thùng đo rung bần bật",
                    "Chiếc đèn dầu đã hết nhiên liệu",
                    "Ông Hòa đã ghi xong số liệu trước đó",
                    "Trời đã tạnh mưa hoàn toàn",
                ],
                "answer": 0,
                "explanation": "Đoạn 1 nêu rõ gió mùa thổi ràn rạt, thùng đo rung lên bần bật.",
            },
            {
                "id": "van-2",
                "type": "mcq",
                "topic": "Tiếng Việt",
                "lesson": van_col["lessons"][0]["title"],
                "level": 1,
                "points": 1.0,
                "passageId": "p-tram-khi-tuong",
                "groupId": "g-doc-hieu-1",
                "stem": (
                    "Câu 'Số liệu thời tiết giống như nhịp tim của bầu trời' "
                    "dùng biện pháp tu từ nào?"
                ),
                "options": ["Ẩn dụ", "So sánh", "Hoán dụ", "Nói quá"],
                "answer": 1,
                "explanation": "Từ 'giống như' nối hai vế so sánh rõ rệt ở Đoạn 2.",
            },
            {
                "id": "toan-1",
                "type": "essay",
                "topic": "Hệ phương trình thực tế",
                "lesson": toan_col["lessons"][0]["title"],
                "level": 2,
                "points": 3.0,
                "stem": (
                    f"Dựa vào dữ kiện định mức:\n{toan_text}\n"
                    "Hãy giải lại hệ và kiểm chứng kết quả."
                ),
                "options": [],
                "explanation": "Giải hệ x + y = 22 và 15x + 20y = 380 được x = 12, y = 10.",
                "rubric": [
                    {"text": "Lập đúng hệ phương trình hai ẩn", "points": 1.5},
                    {"text": "Giải đúng $x=12, y=10$ và thử lại", "points": 1.5},
                ],
            },
        ],
    }

    preview = preview_exam_variant(
        {
            "exam": exam,
            "variant": {"questionIds": ["van-1", "van-2"], "offset": 1, "shuffleOptions": True},
        }
    )
    assert len(preview["passageGroups"]) == 1
    assert preview["passageGroups"][0]["contiguous"] is True
    assert preview["passageGroups"][0]["questionNumbers"] == [1, 2]

    variant = exam_variant(
        exam,
        {"questionIds": ["van-1", "van-2"], "offset": 1, "shuffleOptions": True},
    )
    assert variant["questions"][0]["passageText"] == passage_text
    assert "passageText" not in variant["questions"][1]

    spec = build_matrix_and_specification(exam)
    assert spec["total_questions"] == 3
    assert spec["total_points"] == 5.0
    html_spec = export_matrix_specification_html(exam)
    assert "@page" in html_spec and "Đọc hiểu tự sự" in html_spec
    docx_bytes = export_answer_key_rubric_docx(exam)
    assert len(docx_bytes) > 1000
