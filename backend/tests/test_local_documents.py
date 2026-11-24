"""Kiểm nguồn/xuất bằng dữ liệu tự viết, không cần AI hoặc tài liệu giáo viên."""

import base64
import io
import json
import zipfile
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import exam_html, exam_variant, export_file, extract_text
from mach_backend.local_workspace import create_app


@pytest.fixture
def exam():
    return {
        "title": "Đề thử <script>alert(1)</script>",
        "subject": "Ngữ văn",
        "grade": "6",
        "questions": [
            {
                "stem": "Mai báo với ai?",
                "options": ["Nam", "Cô Loan", "Hà", "Lan"],
                "answer": 1,
                "explanation": "Chỉ dành cho giáo viên.",
                "evidence": [{"quote": "Mai báo với cô Loan."}],
            }
        ],
    }


def test_student_export_hides_teacher_data_and_escapes_html(exam):
    student = exam_html(exam, False, "http://localhost")
    assert "<script>alert(1)</script>" not in student
    assert "&lt;script&gt;" in student
    assert "Chỉ dành cho giáo viên" not in student
    assert "Mai báo với cô Loan." not in student
    teacher = exam_html(exam, True, "http://localhost")
    assert "Đáp án B." in teacher and "Chỉ dành cho giáo viên" in teacher
    assert "Họ và tên:" in student and "Họ và tên:" not in teacher
    assert "BẢN GIÁO VIÊN" in teacher and "BẢN GIÁO VIÊN" not in student


def test_export_includes_image_and_refuses_to_silently_drop_geometry(exam):
    image = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format="PNG")
    exam["questions"][0]["images"] = [
        {
            "data": "data:image/png;base64," + base64.b64encode(image.getvalue()).decode(),
            "caption": "Hình <thử>",
        }
    ]
    output = exam_html(exam, False, "http://localhost")
    assert 'src="data:image/png;base64,' in output
    assert "Hình &lt;thử&gt;" in output
    exam["questions"][0]["figure"] = {"points": {}}
    with pytest.raises(AIError, match="không bỏ hình"):
        exam_html(exam, False, "http://localhost")


def test_word_refuses_mismatched_rich_document_instead_of_dropping_it(exam, tmp_path):
    exam["questions"][0]["richDoc"] = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Bản rich đã cũ"}]}],
    }
    with pytest.raises(AIError, match="chưa khớp"):
        export_file({"type": "exam", "exam": exam, "format": "docx"}, tmp_path, "http://localhost")
    assert list(tmp_path.iterdir()) == []


def test_export_preserves_points_and_teacher_rubric(exam, tmp_path):
    exam["questions"][0].update(points=2.5, rubric=[{"text": "Chọn đúng", "points": 2.5}])
    student = exam_html(exam, False, "http://localhost")
    teacher = exam_html(exam, True, "http://localhost")
    assert "2,5 điểm" in student and "Chọn đúng" not in student
    assert "Hướng dẫn chấm" in teacher and "Chọn đúng" in teacher
    assert 'class="rubric-title"' in teacher
    assert "section,ol,ul{break-inside:avoid}" in student
    assert ".rubric-title{break-after:avoid}" in teacher
    output = export_file(
        {"type": "exam", "exam": exam, "format": "docx", "teacher": True},
        tmp_path,
        "http://localhost",
    )
    data = (tmp_path / output["filename"]).read_bytes()
    source = extract_text(
        "de.docx", "data:application/octet-stream;base64," + base64.b64encode(data).decode()
    )
    assert "Hướng dẫn chấm" in source["pages"][0]["text"]
    assert "Chọn đúng" in source["pages"][0]["text"] and "2,5" in source["pages"][0]["text"]


def test_docx_is_real_zip_and_source_roundtrips(exam, tmp_path):
    output = export_file(
        {"type": "exam", "exam": exam, "format": "docx", "teacher": True},
        tmp_path,
        "http://localhost",
    )
    data = (tmp_path / output["filename"]).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert ET.fromstring(archive.read("word/document.xml")) is not None
        assert "[Content_Types].xml" in archive.namelist()
    extracted = extract_text(
        "de.docx", "data:application/octet-stream;base64," + base64.b64encode(data).decode()
    )
    assert "Mai báo với ai?" in extracted["pages"][0]["text"]
    assert "Đáp án B" in extracted["pages"][0]["text"]


def test_pptx_preserves_slide_numbers_and_natural_order(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for number in (10, 2, 1):
            archive.writestr(
                f"ppt/slides/slide{number}.xml",
                '<p xmlns="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<r><t>Nội dung trang {number}</t></r></p>",
            )
    encoded = base64.b64encode(buffer.getvalue()).decode()
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/extract",
            json={"name": "source.pptx", "data": "data:application/octet-stream;base64," + encoded},
        )
        response.raise_for_status()
        assert response.json()["sentToAI"] is False
        pages = response.json()["pages"]
        assert client.get("/api/kv?key=state").json() == {"value": None, "revision": 0}
    assert [(p["number"], p["text"]) for p in pages] == [
        (1, "Nội dung trang 1"),
        (2, "Nội dung trang 2"),
        (10, "Nội dung trang 10"),
    ]


def test_pptx_preserves_presentation_order_when_slide_files_differ(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "ppt/presentation.xml",
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<p:sldIdLst>"
            '<p:sldId id="258" r:id="rId3"/>'
            '<p:sldId id="256" r:id="rId1"/>'
            '<p:sldId id="257" r:id="rId2"/>'
            "</p:sldIdLst></p:presentation>",
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            'Target="slides/slide1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            'Target="slides/slide2.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            'Target="slides/slide3.xml"/>'
            "</Relationships>",
        )
        for number in (1, 2, 3):
            archive.writestr(
                f"ppt/slides/slide{number}.xml",
                '<p xmlns="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<r><t>Nội dung slide {number}</t></r></p>",
            )
    encoded = base64.b64encode(buffer.getvalue()).decode()
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/extract",
            json={
                "name": "reordered.pptx",
                "data": "data:application/octet-stream;base64," + encoded,
            },
        )
        response.raise_for_status()
        assert response.json()["sentToAI"] is False
        pages = response.json()["pages"]
    assert [(p["number"], p["text"]) for p in pages] == [
        (1, "Nội dung slide 3"),
        (2, "Nội dung slide 1"),
        (3, "Nội dung slide 2"),
    ]


@pytest.mark.parametrize(
    "name,data", [("anh.png", b"abc"), ("de.docx", b"not a zip"), ("x.txt", b"\xff")]
)
def test_invalid_import_is_reported(name, data):
    with pytest.raises(AIError):
        extract_text(
            name, "data:application/octet-stream;base64," + base64.b64encode(data).decode()
        )


def test_backup_keeps_all_data(exam, tmp_path):
    backup = {"version": 1, "state": {"exams": [exam]}, "files": {"example": "sample"}}
    output = export_file({"type": "backup", "backup": backup}, tmp_path, "http://localhost")
    assert json.loads((tmp_path / output["filename"]).read_text(encoding="utf8")) == backup


def test_local_http_import_export_and_download(exam, tmp_path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        data = (
            "data:text/plain;base64,"
            + base64.b64encode("Nguồn tiếng Việt tự viết.".encode()).decode()
        )
        client.put("/api/kv", json={"key": "file:sample", "value": data}).raise_for_status()
        result = client.post("/api/extract", json={"fileId": "sample", "name": "nguon.txt"})
        assert result.json()["pages"][0]["text"] == "Nguồn tiếng Việt tự viết."
        result = client.post(
            "/api/save-export", json={"type": "exam", "exam": exam, "format": "html"}
        )
        result.raise_for_status()
        saved = client.get(result.json()["url"])
        assert saved.status_code == 200 and "Mai báo với ai?" in saved.text
        assert client.get("/api/exports/workspace.sqlite").status_code == 404


def test_export_variant_reorders_questions_without_changing_saved_answers(exam, tmp_path):
    first = {**exam["questions"][0], "id": "first", "pageBreak": True}
    last = {**first, "id": "last", "stem": "Nam mang gì?", "answer": 2, "pageBreak": False}
    held = {**first, "id": "held", "stem": "Giữ câu này."}
    exam["questions"] = [first, held, last]
    payload = {
        "type": "exam",
        "format": "html",
        "teacher": True,
        "exam": exam,
        "variant": {"questionIds": ["last", "first"], "offset": 1},
    }
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        result = client.post("/api/save-export", json=payload).raise_for_status().json()
        output = client.get(result["url"]).raise_for_status().text
        assert "Mã đề 102" in output and '<section class="page-break">' in output
        assert (
            output.index("Nam mang gì?") < output.index("Đáp án C.") < output.index("Giữ câu này.")
        )
        assert output.index("Mai báo với ai?") < output.rindex("Đáp án B.")
        word = (
            client.post("/api/save-export", json={**payload, "format": "docx"})
            .raise_for_status()
            .json()
        )
        with zipfile.ZipFile(
            io.BytesIO(client.get(word["url"]).raise_for_status().content)
        ) as archive:
            xml = archive.read("word/document.xml").decode()
        assert "Mã đề 102" in xml
        assert xml.index("Nam mang gì?") < xml.index("Giữ câu này.") < xml.index("Mai báo với ai?")
        batch = (
            client.post(
                "/api/save-export",
                json={
                    "type": "variant-pack",
                    "format": "docx",
                    "exam": exam,
                    "questionIds": ["last", "first"],
                    "teacher": True,
                },
            )
            .raise_for_status()
            .json()
        )
        with zipfile.ZipFile(
            io.BytesIO(client.get(batch["url"]).raise_for_status().content)
        ) as archive:
            assert archive.namelist() == [
                "HOC_SINH/Ma_101.docx",
                "HOC_SINH/Ma_102.docx",
                "GIAO_VIEN/Doi_chieu_dap_an.html",
            ]
            key = archive.read("GIAO_VIEN/Doi_chieu_dap_an.html").decode()
            assert "B <small>(gốc: 1)" in key and "C <small>(gốc: 3)" in key
            assert "Mã 101" in key and "Mã 102" in key and "<script>" not in key
            for code in (101, 102):
                with zipfile.ZipFile(io.BytesIO(archive.read(f"HOC_SINH/Ma_{code}.docx"))) as doc:
                    student = doc.read("word/document.xml").decode()
                assert f"Mã đề {code}" in student and "Chỉ dành cho giáo viên" not in student
                assert (student.index("Mai báo với ai?") < student.index("Nam mang gì?")) == (
                    code == 101
                )
        assert client.get("/api/kv?key=state").json() == {"value": None, "revision": 0}
        for invalid in (
            {"questionIds": ["first", "first"], "offset": 0},
            {"questionIds": ["first", "missing"], "offset": 1},
            {"questionIds": ["first", "last"], "offset": 2},
        ):
            assert client.post("/api/save-export", json={**payload, "variant": invalid}).is_error
    assert exam["questions"] == [first, held, last]


def test_variant_preview_and_exports_share_shuffle_and_keep_dependent_options(exam, tmp_path):
    first = {
        **exam["questions"][0],
        "id": "first",
        "optionDocs": [
            None,
            {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Cô Loan", "marks": [{"type": "bold"}]}
                        ],
                    }
                ],
            },
        ],
    }
    second = {
        **first,
        "id": "second",
        "stem": "Ai đã đến?",
        "options": ["Nam", "Cô Loan", "Hà", "Cả hai đáp án trên"],
        "answer": 3,
    }
    exam["questions"] = [first, second]
    settings = {"questionIds": ["first", "second"], "shuffleOptions": True}
    choice = {**settings, "offset": 1}
    variant = exam_variant(exam, choice)
    assert variant["questions"][0]["options"] == second["options"]
    assert variant["questions"][0]["answer"] == 3
    assert variant["questions"][1]["options"] == ["Hà", "Lan", "Nam", "Cô Loan"]
    assert variant["questions"][1]["optionDocs"] == [None, None, None, first["optionDocs"][1]]
    assert variant["questions"][1]["answer"] == 3
    assert first["answer"] == 1 and first["options"][1] == "Cô Loan"
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        preview = client.post("/api/preview-variant", json={"exam": exam, "variant": choice})
        assert preview.raise_for_status().json()["questions"] == [
            {"originalNumber": 2, "stem": second["stem"], "options": second["options"]},
            {
                "originalNumber": 1,
                "stem": first["stem"],
                "options": variant["questions"][1]["options"],
            },
        ]
        assert not (tmp_path / "exports").exists()
        batch = (
            client.post(
                "/api/save-export",
                json={"type": "variant-pack", "exam": exam, "format": "html", **settings},
            )
            .raise_for_status()
            .json()
        )
        with zipfile.ZipFile(
            io.BytesIO(client.get(batch["url"]).raise_for_status().content)
        ) as archive:
            student = archive.read("HOC_SINH/Ma_102.html").decode()
            key = archive.read("GIAO_VIEN/Doi_chieu_dap_an.html").decode()
        assert "Đáp án" not in student and student.index("Hà") < student.rindex("Cô Loan")
        assert "D <small>(gốc: 1)" in key and "D <small>(gốc: 2)" in key


@pytest.mark.parametrize(
    "changes",
    [
        {"dataLinked": True},
        {"groupId": "khác"},
        {"stem": "Dựa vào Câu 1 để trả lời."},
    ],
)
def test_variant_refuses_to_move_across_a_linked_group(exam, changes):
    first = {**exam["questions"][0], "id": "first"}
    exam["questions"] = [first, {**first, "id": "second", **changes}]
    with pytest.raises(AIError, match="Chọn câu trong cùng phần|Có câu được nhắc theo số"):
        exam_variant(exam, {"questionIds": ["first", "second"], "offset": 1})


def test_extract_inline_validates_before_any_workspace_write(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        text = "Nguồn tiếng Việt tự viết."
        payload = "data:text/plain;base64," + base64.b64encode(text.encode()).decode()
        result = client.post("/api/extract", json={"name": "nguon.txt", "data": payload})
        assert result.json()["pages"][0]["text"] == text
        assert client.get("/api/kv?key=state").json() == {"value": None, "revision": 0}
        assert (
            client.post(
                "/api/extract", json={"name": "nguon.txt", "data": payload, "fileId": "another"}
            ).status_code
            == 400
        )
        assert client.post("/api/extract", json={"name": "hong.docx", "data": payload}).is_error
        assert (
            client.post("/api/extract", json={"fileId": "../secret", "name": "x.txt"}).status_code
            == 400
        )
        sample = client.get("/api/poc/sample").json()
        assert "questions" not in sample
        assert sum(sum(r["targets"]) for r in sample["matrix"]) == 4


def test_chat_requires_consent_and_does_not_change_exam(tmp_path):
    calls = []

    async def model(purpose, body):
        calls.append((purpose, body))
        return {"content": '{"message":"Có thể dùng ma trận để soạn bộ câu."}'}

    with TestClient(
        create_app(tmp_path, agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        assert (
            client.post("/api/assistant/chat", json={"text": "Làm sao soạn đề?"}).status_code == 400
        )
        response = client.post(
            "/api/assistant/chat", json={"text": "Làm sao soạn đề?", "consent": True}
        )
        assert response.status_code == 200 and "ma trận" in response.json()["message"]
        assert len(calls) == 1 and calls[0][0] == "chat"
        assert client.get("/api/kv?key=state").json()["value"] is None


def test_chat_uses_selected_gemini_and_never_falls_back_to_ollama(tmp_path, monkeypatch):
    from mach_backend import local_workspace
    from mach_backend.gemini_model import GEMINI_MODEL

    calls = []

    class FakeGemini:
        def __init__(self, client, key, log, *, model, key_pool, auto_fallback):
            assert key == "fake-key-in-memory" and model == GEMINI_MODEL
            assert key_pool.keys[0] == key

        async def __call__(self, purpose, body):
            calls.append(purpose)
            return {"content": '{"message":"Phản hồi giả lập Gemini."}'}

    monkeypatch.setattr(local_workspace, "GeminiModel", FakeGemini)
    monkeypatch.setattr(
        local_workspace,
        "LocalModel",
        lambda *_a, **_kw: pytest.fail("Không được tự chuyển sang Ollama"),
    )
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/config",
            json={
                "gemini": {"key": "fake-key-in-memory", "freeTierConfirmed": True},
                "routes": {"generate": "gemini"},
            },
        )
        response.raise_for_status()
        response = client.post(
            "/api/assistant/chat", json={"text": "Giải thích mức thông hiểu", "consent": True}
        )
        assert response.status_code == 200 and "giả lập Gemini" in response.json()["message"]
        assert calls == ["chat"]
        assert client.get("/api/kv?key=state").json()["value"] is None


def test_extract_warns_on_docx_mathtype_ole_and_pptx_image_only_slides():
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as z:
        z.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:o="urn:schemas-microsoft-com:office:office"><w:body>'
            "<w:p><w:r><w:t>Câu 1. Giải phương trình:</w:t></w:r>"
            '<w:r><w:object><o:OLEObject ProgID="Equation.DSMT4"/></w:object></w:r></w:p>'
            "</w:body></w:document>",
        )
    docx_b64 = base64.b64encode(docx_buf.getvalue()).decode()
    docx_res = extract_text("ole.docx", "data:application/octet-stream;base64," + docx_b64)
    assert docx_res["sentToAI"] is False
    assert docx_res["warnings"][0]["code"] == "mathtype_ole_formulas"
    assert docx_res["warnings"][0]["count"] == 1

    pptx_buf = io.BytesIO()
    with zipfile.ZipFile(pptx_buf, "w") as z:
        z.writestr(
            "ppt/slides/slide1.xml",
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Bài 1. Phân số</a:t></a:r></a:p>"
            "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>",
        )
        z.writestr(
            "ppt/slides/slide2.xml",
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            "<p:cSld><p:spTree><p:pic/></p:spTree></p:cSld></p:sld>",
        )
    pptx_b64 = base64.b64encode(pptx_buf.getvalue()).decode()
    pptx_res = extract_text("slides.pptx", "data:application/octet-stream;base64," + pptx_b64)
    assert pptx_res["warnings"][0]["code"] == "image_only_slides"
    assert pptx_res["warnings"][0]["slides"] == [2]


def test_b4_variant_hardened_positional_phrases_and_multi_section_shuffle():
    from mach_backend.local_documents import exam_variant, shuffle_variant_question

    # Câu chứa "hai phương án đầu" hoặc "câu trước" không bị xáo
    q_pos = {
        "id": "q1",
        "type": "mcq",
        "stem": "Chọn nhận định đúng về hai phương án đầu:",
        "options": ["Phương án 1", "Phương án 2", "Sai hết", "Khác"],
        "answer": 0,
    }
    assert shuffle_variant_question(q_pos, 1)["options"] == q_pos["options"]

    exam = {
        "title": "Đề hỗn hợp",
        "questions": [
            {
                "id": "m1",
                "type": "mcq",
                "stem": "MCQ 1",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
            },
            {
                "id": "m2",
                "type": "mcq",
                "stem": "MCQ 2",
                "options": ["5", "6", "7", "8"],
                "answer": 1,
            },
            {
                "id": "m3",
                "type": "mcq",
                "stem": "MCQ 3 câu trước",
                "options": ["a", "b", "c", "d"],
                "answer": 0,
            },
            {"id": "t1", "type": "truefalse", "stem": "TF 1", "truthValues": [True, False] * 2},
            {"id": "t2", "type": "truefalse", "stem": "TF 2", "truthValues": [False, True] * 2},
        ],
    }
    with pytest.raises(AIError, match="trước/sau"):
        exam_variant(exam, {"questionIds": ["m1", "m3"], "offset": 1})
    # P1-3: Câu ngoài vùng trộn (m3 "câu trước") vẫn phải bị chặn nếu phần trước nó hoán đổi.
    with pytest.raises(AIError, match="liền kề|trước/sau"):
        exam_variant(
            exam,
            {
                "offset": 1,
                "sections": [
                    {"questionIds": ["m1", "m2"], "shuffleOptions": True},
                    {"questionIds": ["t1", "t2"], "shuffleOptions": False},
                ],
            },
        )

    safe_exam = {
        "questions": [
            *exam["questions"][:2],
            {
                "id": "m3",
                "type": "mcq",
                "stem": "MCQ 3 độc lập",
                "options": ["a", "b", "c", "d"],
                "answer": 0,
            },
            *exam["questions"][3:],
        ]
    }
    multi = exam_variant(
        safe_exam,
        {
            "offset": 1,
            "sections": [
                {"questionIds": ["m1", "m2"], "shuffleOptions": True},
                {"questionIds": ["t1", "t2"], "shuffleOptions": False},
            ],
        },
    )
    assert [q["id"] for q in multi["questions"]] == ["m2", "m1", "m3", "t2", "t1"]
