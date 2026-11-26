"""Kiểm thử miền B: ngữ liệu Word/HTML/PDF, 2 hướng Tin học, 5 phương án E và ma trận điểm lẻ."""

from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer, saved_answer_label, validate_answer
from mach_backend.local_documents import (
    _update_range_in_text,
    chrome_path,
    exam_html,
    exam_variant,
    export_file,
    preview_exam_variant,
)
from mach_backend.local_workspace import create_app
from mach_backend.rich_patch import project
from mach_backend.word_export import export_docx, field_inputs

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT_DIR = Path(__file__).resolve().parents[2]
ORIGIN = {"Origin": "http://testserver"}


def _docx_xml(data: bytes) -> ET.Element:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return ET.fromstring(zf.read("word/document.xml"))


def _docx_paragraphs(xml_root: ET.Element) -> list[str]:
    paras: list[str] = []
    for p in xml_root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t"))
        if text:
            paras.append(text)
    return paras


def _mcq(
    qid: str,
    stem: str,
    options: list[str] | None = None,
    answer: int = 0,
    **extra: object,
) -> dict[str, object]:
    return {
        "id": qid,
        "type": "mcq",
        "stem": stem,
        "options": options
        if options is not None
        else ["Lựa chọn A", "Lựa chọn B", "Lựa chọn C", "Lựa chọn D"],
        "answer": answer,
        "explanation": f"BI_MAT_GIAI_{qid}",
        "rubric": [{"text": f"BI_MAT_BAREM_{qid}", "points": 0.25}],
        "evidence": [{"quote": f"BI_MAT_NGUON_{qid}"}],
        **extra,
    }


def test_update_range_in_text_vietnamese_and_english_variants() -> None:
    cases = [
        ("Đọc ngữ liệu sau và trả lời câu 1–2.", 4, 5, "Đọc ngữ liệu sau và trả lời câu 4–5."),
        ("Đoạn văn dùng cho câu 1 - 2 bên dưới", 3, 4, "Đoạn văn dùng cho câu 3 - 4 bên dưới"),
        ("Ngữ liệu câu 1—2", 6, 7, "Ngữ liệu câu 6—7"),
        (
            "Đọc văn bản và trả lời từ câu 1 đến câu 2.",
            5,
            6,
            "Đọc văn bản và trả lời từ câu 5 đến câu 6.",
        ),
        (
            "Trả lời từ câu 1 tới câu 2 dựa vào bảng",
            7,
            8,
            "Trả lời từ câu 7 tới câu 8 dựa vào bảng",
        ),
        ("Ngữ liệu cho câu 1 và câu 2", 2, 3, "Ngữ liệu cho câu 2 và câu 3"),
        ("Áp dụng cho câu 1, 2", 4, 5, "Áp dụng cho câu 4, 5"),
        ("Áp dụng cho câu 1, câu 2", 9, 10, "Áp dụng cho câu 9, câu 10"),
        (
            "Read the passage for Questions 1–2 carefully.",
            3,
            4,
            "Read the passage for Questions 3–4 carefully.",
        ),
        ("Đoạn đọc hiểu (câu 1-3):", 6, 8, "Đoạn đọc hiểu (câu 6-8):"),
    ]
    for source, start, end, expected in cases:
        assert _update_range_in_text(source, start, end) == expected


@pytest.mark.parametrize("passages_kind", ["list", "dict", "inline"])
def test_passages_preserved_and_renumbered_across_word_html_variant_and_preview(
    passages_kind: str,
    tmp_path: Path,
) -> None:
    p1_title = "Ngữ liệu 1 (câu 1–2): Bầu trời thu"
    p1_text = "Đoạn đọc hiểu về mùa thu dành cho từ câu 1 đến câu 2. Công thức $x_1 + x_2 = 5$."
    p2_title = "Ngữ liệu 2 (câu 3, câu 4): Lập trình"
    p2_text = "Bảng dữ liệu phục vụ cho câu 3 và câu 4."

    q1 = _mcq(
        "p1_a",
        "Nội dung chính đoạn thu là gì?",
        answer=1,
        passageId="p1",
        points=0.25,
    )
    q2 = _mcq(
        "p1_b",
        "Ý nghĩa hình ảnh bầu trời?",
        answer=2,
        passageId="p1",
        points=0.25,
    )
    q3 = _mcq(
        "p2_a",
        "Giá trị đầu ra ở bước 1?",
        answer=0,
        passageId="p2",
        points=0.25,
    )
    q4 = _mcq(
        "p2_b",
        "Giá trị đầu ra ở bước 2?",
        answer=3,
        passageId="p2",
        points=0.25,
    )

    if passages_kind == "inline":
        q1["passageTitle"] = p1_title
        q1["passageText"] = p1_text
        q2["passageTitle"] = p1_title
        q2["passageText"] = "Áp dụng cho câu 1, 2: nhắc lại đoạn thu."
        q3["passageTitle"] = p2_title
        q3["passageText"] = p2_text
        q4["passageTitle"] = p2_title
        q4["passageText"] = p2_text
        exam: dict[str, object] = {
            "title": "Đề có ngữ liệu inline",
            "subject": "Ngữ văn",
            "grade": "10",
            "minutes": 45,
            "questions": [q1, q2, q3, q4],
        }
    elif passages_kind == "list":
        exam = {
            "title": "Đề có passages dạng list",
            "subject": "Ngữ văn",
            "grade": "10",
            "minutes": 45,
            "passages": [
                {"id": "p1", "title": p1_title, "text": p1_text},
                {"id": "p2", "title": p2_title, "text": p2_text},
            ],
            "questions": [q1, q2, q3, q4],
        }
    else:
        exam = {
            "title": "Đề có passages dạng dict",
            "subject": "Ngữ văn",
            "grade": "10",
            "minutes": 45,
            "passages": {
                "p1": {"id": "p1", "title": p1_title, "text": p1_text},
                "p2": {"id": "p2", "title": p2_title, "text": p2_text},
            },
            "questions": [q1, q2, q3, q4],
        }

    # field_inputs phải thu thập công thức toán trong ngữ liệu (chỉ 1 lần cho mỗi khối)
    collected_texts = [str(text or "") for text, _, _ in field_inputs(exam, False)]
    assert any("$x_1 + x_2 = 5$" in text for text in collected_texts)

    # Xuất Word trên bản copy bỏ công thức LaTeX thô để không phụ thuộc Chromium
    word_exam = deepcopy(exam)
    if passages_kind == "inline":
        word_exam["questions"][0]["passageText"] = (
            "Đoạn đọc hiểu về mùa thu dành cho từ câu 1 đến câu 2."
        )
    elif passages_kind == "list":
        word_exam["passages"][0]["text"] = "Đoạn đọc hiểu về mùa thu dành cho từ câu 1 đến câu 2."
    else:
        word_exam["passages"]["p1"]["text"] = (
            "Đoạn đọc hiểu về mùa thu dành cho từ câu 1 đến câu 2."
        )

    # 1) Xuất Word đề gốc (HS & GV): mỗi khối ngữ liệu hiện 1 lần trước câu đầu, có khung w:pBdr
    for teacher_mode in (False, True):
        docx_bytes = export_docx(word_exam, teacher_mode, None)
        xml_root = _docx_xml(docx_bytes)
        joined = "\n".join(_docx_paragraphs(xml_root))
        assert joined.count("Bầu trời thu") == 1
        assert joined.count("Đoạn đọc hiểu về mùa thu") == 1
        assert joined.count("Lập trình") == 1
        assert xml_root.find(f".//{W}pBdr") is not None
        assert joined.index("Bầu trời thu") < joined.index("Câu 1")
        assert joined.index("Lập trình") < joined.index("Câu 3")
        if not teacher_mode:
            assert "BI_MAT_GIAI_" not in joined
            assert "BI_MAT_BAREM_" not in joined
            assert "BI_MAT_NGUON_" not in joined
        else:
            assert "BI_MAT_GIAI_p1_a" in joined

    # 2) Trộn mã qua exam_variant & preview_exam_variant
    variant_cfg = {
        "questionIds": ["p1_a", "p1_b", "p2_a", "p2_b"],
        "offset": 1,
        "shuffleOptions": False,
    }
    preview = preview_exam_variant({"exam": word_exam, "variant": variant_cfg})
    assert preview["maxVariants"] == 2
    assert len(preview["questionPassages"]) == 4
    first_meta = preview["questionPassages"][0]
    assert "Bầu trời thu" in (first_meta.get("passageTitle") or "") or "Lập trình" in (
        first_meta.get("passageTitle") or ""
    )

    shuffled = exam_variant(word_exam, variant_cfg)
    # p2 lên vị trí 1–2, p1 xuống vị trí 3–4
    assert [q["id"] for q in shuffled["questions"]] == ["p2_a", "p2_b", "p1_a", "p1_b"]
    if passages_kind == "inline":
        assert "câu 1, câu 2" in shuffled["questions"][0]["passageTitle"]
        assert "câu 1 và câu 2" in shuffled["questions"][0]["passageText"]
        assert "câu 3–4" in shuffled["questions"][2]["passageTitle"]
        assert "từ câu 3 đến câu 4" in shuffled["questions"][2]["passageText"]
        assert "câu 3, 4" in shuffled["questions"][3]["passageText"]
    elif passages_kind == "list":
        p2_item = next(p for p in shuffled["passages"] if p["id"] == "p2")
        p1_item = next(p for p in shuffled["passages"] if p["id"] == "p1")
        assert "câu 1, câu 2" in p2_item["title"]
        assert "câu 1 và câu 2" in p2_item["text"]
        assert "câu 3–4" in p1_item["title"]
        assert "từ câu 3 đến câu 4" in p1_item["text"]
    else:
        assert "câu 1, câu 2" in shuffled["passages"]["p2"]["title"]
        assert "câu 1 và câu 2" in shuffled["passages"]["p2"]["text"]
        assert "câu 3–4" in shuffled["passages"]["p1"]["title"]
        assert "từ câu 3 đến câu 4" in shuffled["passages"]["p1"]["text"]

    # 3) Xuất Word và HTML từ đề đã trộn mã giữ đúng ngữ liệu đã đánh số mới
    shuffled_docx = "\n".join(_docx_paragraphs(_docx_xml(export_docx(shuffled, False, None))))
    assert shuffled_docx.count("Lập trình") == 1
    assert shuffled_docx.count("Bầu trời thu") == 1
    assert "câu 1, câu 2" in shuffled_docx
    assert "câu 3–4" in shuffled_docx
    assert shuffled_docx.index("Lập trình") < shuffled_docx.index("Bầu trời thu")

    html = exam_html(shuffled, False, "http://127.0.0.1:8000")
    assert html.count('class="passage"') == 2
    assert "câu 1, câu 2" in html
    assert "từ câu 3 đến câu 4" in html
    assert "BI_MAT_GIAI_" not in html

    if passages_kind == "list":
        pack = export_file(
            {
                "type": "variant-pack",
                "exam": word_exam,
                "format": "docx",
                "questionIds": ["p1_a", "p1_b", "p2_a", "p2_b"],
                "shuffleOptions": False,
            },
            tmp_path,
            "http://127.0.0.1:8000",
        )
        with zipfile.ZipFile(tmp_path / pack["filename"]) as zf:
            ma102 = "\n".join(_docx_paragraphs(_docx_xml(zf.read("HOC_SINH/Ma_102.docx"))))
            assert ma102.count("Lập trình") == 1
            assert ma102.count("Bầu trời thu") == 1
            assert "câu 1, câu 2" in ma102
            assert "câu 3–4" in ma102
            assert "BI_MAT_GIAI_" not in ma102


def test_choice_group_two_tracks_rendered_in_html_and_word() -> None:
    exam = {
        "title": "Đề Tin học 12 hai hướng tự chọn",
        "subject": "Tin học",
        "grade": "12",
        "minutes": 50,
        "questions": [
            _mcq("c1", "Câu chung 1: Giao thức TCP là gì?", answer=0, points=0.25),
            _mcq("c2", "Câu chung 2: Địa chỉ IPv4 gồm bao nhiêu bit?", answer=1, points=0.25),
            _mcq(
                "a1",
                "Câu định hướng KHMT 1: Độ phức tạp tìm kiếm nhị phân?",
                answer=2,
                choiceGroup="Tự chọn A (KHMT)",
                points=0.5,
            ),
            _mcq(
                "a2",
                "Câu định hướng KHMT 2: Học máy có giám sát dùng nhãn?",
                answer=0,
                choiceGroup="Tự chọn A (KHMT)",
                points=0.5,
            ),
            _mcq(
                "b1",
                "Câu định hướng THUD 1: Khóa chính trong CSDL quan hệ?",
                answer=1,
                choiceGroup="Tự chọn B (THUD)",
                points=0.5,
            ),
            _mcq(
                "b2",
                "Câu định hướng THUD 2: Lệnh SELECT dùng để làm gì?",
                answer=3,
                choiceGroup="Tự chọn B (THUD)",
                points=0.75,
            ),
        ],
    }

    html_student = exam_html(exam, False, "http://127.0.0.1:8000")
    for expected in (
        "PHẦN CHUNG",
        "PHẦN RIÊNG",
        "Thí sinh chỉ chọn làm MỘT trong các hướng sau",
        "Hướng 1: Tự chọn A (KHMT) (1 điểm)",
        "Hướng 2: Tự chọn B (THUD) (1,25 điểm)",
    ):
        assert expected in html_student
    assert "BI_MAT_GIAI_" not in html_student
    assert html_student.index("PHẦN CHUNG") < html_student.index("PHẦN RIÊNG")
    assert html_student.index("Hướng 1: Tự chọn A (KHMT)") < html_student.index(
        "Hướng 2: Tự chọn B (THUD)"
    )

    docx_student = "\n".join(_docx_paragraphs(_docx_xml(export_docx(exam, False, None))))
    for expected in (
        "PHẦN CHUNG",
        "PHẦN RIÊNG — Thí sinh chỉ chọn làm MỘT trong các hướng sau",
        "Hướng 1: Tự chọn A (KHMT) (1 điểm)",
        "Hướng 2: Tự chọn B (THUD) (1,25 điểm)",
    ):
        assert expected in docx_student
    assert "BI_MAT_GIAI_" not in docx_student

    # Kiểm tra chéo trên fixture thật SC-09.json nếu có câu choiceGroup
    sc09 = json.loads(
        (ROOT_DIR / "tests" / "fixtures" / "school-corpus" / "SC-09.json").read_text("utf-8")
    )
    sc09_html = exam_html(sc09, False, "http://127.0.0.1:8000")
    assert "PHẦN CHUNG" in sc09_html
    assert "PHẦN RIÊNG" in sc09_html
    assert "Hướng 1:" in sc09_html
    assert "Hướng 2:" in sc09_html


def test_five_option_mcq_with_answer_e_succeeds_across_ai_questions_word_and_html() -> None:
    # Hợp đồng AI mặc định (option_count=None) vẫn khóa chặt 0..3
    with pytest.raises(AIError):
        validate_answer("mcq", 4)

    # Khi truyền option_count=5 (từ saved_answer), cho phép index 4 (E), vẫn chặn 5
    validate_answer("mcq", 4, option_count=5)
    with pytest.raises(AIError):
        validate_answer("mcq", 5, option_count=5)

    q_five = _mcq(
        "mcq5",
        "Chọn phát biểu đúng nhất trong 5 phương án:",
        options=["Phương án A", "Phương án B", "Phương án C", "Phương án D", "Phương án E"],
        answer=4,
    )
    assert saved_answer(q_five) == 4
    assert saved_answer_label(q_five) == "E"

    exam = {
        "title": "Đề trắc nghiệm 5 phương án A–E",
        "subject": "Vật lí",
        "grade": "11",
        "minutes": 15,
        "questions": [q_five],
    }
    docx_teacher = "\n".join(_docx_paragraphs(_docx_xml(export_docx(exam, True, None))))
    assert "E. Phương án E" in docx_teacher
    assert "Đáp án E" in docx_teacher

    html_teacher = exam_html(exam, True, "http://127.0.0.1:8000")
    assert "E." in html_teacher and "Phương án E" in html_teacher
    assert "<b>Đáp án E.</b>" in html_teacher


def test_pdf_code_block_css_preserves_indentation_and_exports_cleanly(tmp_path: Path) -> None:
    py_code = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n - 1) + fib(n - 2)"
    rich_doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "Hàm sau trả về gì với fib(5)?"}],
            },
            {"type": "codeBlock", "content": [{"type": "text", "text": py_code}]},
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Đoạn mã"}],
                                    }
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "codeBlock",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "for i in range(3):\n    print(i)",
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
        ],
    }
    exam = {
        "title": "Đề lập trình Python",
        "subject": "Tin học",
        "grade": "10",
        "minutes": 45,
        "questions": [
            {
                "id": "code1",
                "type": "mcq",
                "stem": project(rich_doc, []),
                "richDoc": rich_doc,
                "options": ["3", "5", "8", "13"],
                "answer": 1,
            }
        ],
    }

    html = exam_html(exam, False, "http://127.0.0.1:8000")
    assert 'Consolas,"Courier New",monospace' in html
    assert "font-size:9.5pt" in html
    assert "white-space:pre-wrap" in html
    assert "tab-size:4" in html
    assert "overflow-wrap:normal" in html
    assert "word-break:normal" in html
    assert "td .code-block,th .code-block" in html
    assert "vertical-align:top" in html
    assert "        return n" in html
    assert "    print(i)" in html

    if chrome_path():
        result = export_file(
            {
                "type": "exam",
                "exam": exam,
                "teacher": False,
                "format": "pdf",
                "allowDraft": True,
                "teacherProfile": {"school": "THPT Test"},
            },
            tmp_path,
            "http://127.0.0.1:8000",
        )
        pdf_path = tmp_path / result["filename"]
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000


def test_matrix_templates_accept_decimal_points_points_by_level_and_two_tracks(
    tmp_path: Path,
) -> None:
    from test_workspace_backup import backup_fixture

    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        # 1) Đề điểm lẻ 0,40 / 9,60
        res_decimal = client.post(
            "/api/matrix-templates",
            json={
                "name": "Mẫu điểm lẻ 0,40 + 9,60",
                "subject": "Toán",
                "grade": "12",
                "rows": [
                    {"topic": "Hàm số", "type": "mcq", "targets": [1, 0, 0, 0], "points": 0.4},
                    {"topic": "Hàm số", "type": "mcq", "targets": [0, 1, 0, 0], "points": 9.6},
                ],
            },
        )
        assert res_decimal.status_code == 201, res_decimal.text
        created_dec = res_decimal.json()
        assert created_dec["total_questions"] == 2
        assert created_dec["total_points_q4"] == 40
        assert created_dec["rows"][0]["points"] == pytest.approx(0.4)
        assert created_dec["rows"][1]["points"] == pytest.approx(9.6)

        # 2) Đề Tin học 2 nhánh + pointsByLevel bước 0,05 (28 câu hiệu lực <= 30, tổng 10,00đ)
        # Chung: 6,10đ (24 câu); mỗi nhánh: 3,90đ (4 câu)
        two_track_payload = {
            "name": "Tin học 12 — Hai hướng tự chọn 28 câu",
            "subject": "Tin học",
            "grade": "12",
            "rows": [
                {
                    "topic": "Mạng máy tính",
                    "type": "mcq",
                    "targets": [10, 10, 4, 0],
                    "pointsByLevel": [0.2, 0.25, 0.4, None],
                },
                {
                    "topic": "Khoa học máy tính",
                    "type": "mcq",
                    "choiceGroup": "Tự chọn A",
                    "targets": [2, 1, 1, 0],
                    "pointsByLevel": [0.75, 1.0, 1.4, None],
                },
                {
                    "topic": "Tin học ứng dụng",
                    "type": "mcq",
                    "choiceGroup": "Tự chọn B",
                    "targets": [2, 1, 1, 0],
                    "pointsByLevel": [0.75, 1.0, 1.4, None],
                },
            ],
        }
        res_two = client.post("/api/matrix-templates", json=two_track_payload)
        assert res_two.status_code == 201, res_two.text
        created_two = res_two.json()
        assert created_two["total_questions"] == 28
        assert created_two["total_points_q4"] == 40
        assert created_two["rows"][0]["pointsByLevel"] == [0.2, 0.25, 0.4, None]
        assert created_two["rows"][1]["choiceGroup"] == "Tự chọn A"
        assert created_two["rows"][2]["choiceGroup"] == "Tự chọn B"

        # 3) Từ chối bước điểm không phải bội 0,05 (422)
        bad_step = client.post(
            "/api/matrix-templates",
            json={
                "name": "Sai bước điểm",
                "subject": "Toán",
                "grade": "10",
                "rows": [
                    {"topic": "Đại số", "type": "mcq", "targets": [1, 0, 0, 0], "points": 0.03}
                ],
            },
        )
        assert bad_step.status_code == 422

        # 4) Backup/restore bảo toàn toàn bộ points, pointsByLevel và choiceGroup
        fetched = client.get("/api/matrix-templates").json()
        backup = backup_fixture()
        backup["matrixTemplates"] = fetched["templates"]

    with TestClient(create_app(tmp_path / "restored"), headers=ORIGIN) as target:
        prev = target.post("/api/workspace/restore/preview", json=backup)
        assert prev.status_code == 200, prev.text
        restored = target.post(
            "/api/workspace/restore",
            json=backup,
            headers={"If-Match": str(prev.json()["revision"])},
        )
        assert restored.status_code == 200, restored.text
        rows_after = target.get(f"/api/matrix-templates/{created_two['id']}").json()["rows"]
        assert rows_after[0]["pointsByLevel"] == [0.2, 0.25, 0.4, None]
        assert rows_after[1]["choiceGroup"] == "Tự chọn A"
        assert rows_after[2]["choiceGroup"] == "Tự chọn B"
