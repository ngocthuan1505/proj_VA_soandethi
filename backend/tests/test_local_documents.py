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
from mach_backend.local_documents import exam_html, export_file, extract_text
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
