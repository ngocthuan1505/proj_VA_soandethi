"""Tệp thử tự tạo; không gọi AI thật, không dùng tài liệu giáo viên."""

import asyncio
import base64
import io
import json
import zipfile
from xml.sax.saxutils import escape

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mach_backend.ai_contract import AIError
from mach_backend.gemini_model import GeminiModel
from mach_backend.local_workspace import create_app
from mach_backend.matrix_import import decode_file, parse_table, read_matrix
from mach_backend.poc_matrix import RunLog

ROWS = [
    ["Chủ đề", "Nhận biết", "Thông hiểu", "Vận dụng"],
    ["Thẩm thấu", "2", "1", "0"],
    ["Tế bào", "1", "0", "1"],
]


def document(ext):
    buffer = io.BytesIO()
    if ext == ".csv":
        return (
            ";".join(ROWS[0]).encode() + b"\n" + b"\n".join(";".join(r).encode() for r in ROWS[1:])
        )
    with zipfile.ZipFile(buffer, "w") as z:
        if ext == ".docx":
            rows = "".join(
                "<w:tr>"
                + "".join(f"<w:tc><w:p><w:r><w:t>{escape(c)}</w:t></w:r></w:p></w:tc>" for c in row)
                + "</w:tr>"
                for row in ROWS
            )
            z.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>'
                + rows
                + "</w:tbl></w:body></w:document>",
            )
        else:
            rows = "".join(
                f'<row r="{i}">'
                + "".join(
                    f'<c r="{chr(65 + j)}{i}" t="inlineStr"><is><t>{escape(c)}</t></is></c>'
                    for j, c in enumerate(row)
                )
                + "</row>"
                for i, row in enumerate(ROWS, 1)
            )
            z.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                + rows
                + "</sheetData></worksheet>",
            )
    return buffer.getvalue()


def encoded(data):
    return "data:application/octet-stream;base64," + base64.b64encode(data).decode()


@pytest.mark.parametrize("ext", [".docx", ".xlsx", ".csv"])
def test_upload_table_is_local_preview_without_ai_or_state_change(tmp_path, ext):
    async def forbidden(*_):
        pytest.fail("Bảng rõ không được gửi AI")

    app = create_app(tmp_path, agent_call=forbidden)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/ai/matrix",
            json={"name": "ma-tran" + ext, "data": encoded(document(ext)), "consent": False},
        )
        assert response.status_code == 200, response.text
        assert response.json()["count"] == 5
        assert response.json()["matrix"][0]["targets"] == [2, 1, 0]
        assert not response.json()["sentToAI"] and response.json()["requiresConfirmation"]
        assert client.get("/api/kv?key=state").json()["value"] is None


def test_status_matches_maximum_matrix_accepted_without_ai(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        limit = client.get("/api/status").json()["matrixImport"]["maxQuestions"]
        assert limit == 30

        def load(n):
            csv = f"Chủ đề;Nhận biết;Thông hiểu;Vận dụng\nSố học;15;0;0\nĐại số;{n};0;0"
            return client.post(
                "/api/ai/matrix",
                json={"name": "matrix.csv", "data": encoded(csv.encode()), "consent": False},
            )

        accepted = load(15)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["count"] == limit and not accepted.json()["sentToAI"]
        rejected = load(16)
        assert not rejected.is_success
        assert client.get("/api/kv?key=state").json()["value"] is None


@pytest.mark.parametrize("ext", [".pdf", ".png"])
def test_pdf_image_require_consent_then_pass_real_mime_to_model(ext):
    output = io.BytesIO()
    if ext == ".pdf":
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        writer.write(output)
    else:
        Image.new("RGB", (8, 8), "white").save(output, "PNG")
    data = output.getvalue()
    calls = []

    async def model(purpose, body):
        calls.append((purpose, body))
        return {
            "content": json.dumps(
                {
                    "matrix": [{"topic": "Tế bào", "targets": [2, 1, 2]}],
                    "notes": "Đối chiếu tệp gốc.",
                }
            )
        }

    request = {"name": "matrix" + ext, "data": encoded(data), "consent": False}
    with pytest.raises(AIError, match="Tích cho phép"):
        asyncio.run(read_matrix(request, model))
    assert not calls
    result = asyncio.run(read_matrix({**request, "consent": True}, model))
    assert result["count"] == 5 and result["sentToAI"]
    assert base64.b64decode(calls[0][1]["document"]["data"]) == data


@pytest.mark.parametrize("targets", [[28, 3, 0], [1.5, 1, 1], [-1, 2, 1], [0, 0, 0]])
def test_ai_cannot_silently_import_invalid_counts(targets):
    async def model(*_):
        return {
            "content": json.dumps({"matrix": [{"topic": "A", "targets": targets}], "notes": ""})
        }

    with pytest.raises(AIError):
        asyncio.run(read_matrix({"text": "Bảng gộp ô không rõ", "consent": True}, model))


def test_file_type_spoof_and_zip_bomb_are_rejected():
    with pytest.raises(AIError):
        decode_file("a.pdf", encoded(b"not pdf"))
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"a" * (31 * 1024 * 1024))
    with pytest.raises(AIError):
        decode_file("a.docx", encoded(data.getvalue()))


def test_native_gemini_document_input_uses_header_and_validates_finish(tmp_path):
    def respond(request):
        assert request.url.path.endswith(":generateContent") and "key=" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "fake-key-for-document"
        payload = json.loads(request.content)
        assert payload["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "application/pdf"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": '{"matrix":[]}'}]}}
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await GeminiModel(client, "fake-key-for-document", RunLog(tmp_path / "read"))(
                "matrix_import",
                {
                    "messages": [{"role": "user", "content": "Đọc bảng"}],
                    "format": {"type": "object"},
                    "document": {"mimeType": "application/pdf", "data": "Zml4dHVyZQ=="},
                },
            )
            assert result["content"] == '{"matrix":[]}'

    asyncio.run(run())
    assert not any(
        "fake-key-for-document" in p.read_text(encoding="utf8")
        for p in (tmp_path / "read").iterdir()
    )


@pytest.mark.parametrize("totals", [["4", "1", "0"], ["3", "1", "0"], ["", "", ""]])
def test_inconsistent_total_is_not_silently_ignored(totals):
    with pytest.raises(AIError, match="Dòng tổng"):
        parse_table([*ROWS, ["Tổng", *totals]])


def test_consistent_totals_preserve_five_question_matrix():
    assert parse_table([*ROWS, ["Tổng", "3", "1", "1"]])["count"] == 5


def test_multiple_tables_do_not_silently_choose_first_matrix():
    with pytest.raises(AIError, match="nhiều bảng"):
        parse_table([*ROWS, *ROWS])


def test_excel_formula_keeps_actionable_error_code():
    with zipfile.ZipFile(io.BytesIO(document(".xlsx"))) as original:
        xml = original.read("xl/worksheets/sheet1.xml").replace(b"<is>", b"<f>SUM(1,2)</f><is>", 1)
    formula = io.BytesIO()
    with zipfile.ZipFile(formula, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", xml)
    with pytest.raises(AIError) as exc:
        decode_file("matrix.xlsx", encoded(formula.getvalue()))
    assert exc.value.code == "matrix_formula"


@pytest.mark.parametrize("ext", [".docx", ".xlsx", ".csv"])
def test_local_mixed_matrix_keeps_types_and_points_without_ai(monkeypatch, ext):
    rows = [["Chủ đề", "Loại câu", "Điểm/câu", "Nhận biết", "Thông hiểu", "Vận dụng"]]
    for kind, targets in [
        ("Trắc nghiệm", ["1", "0", "0"]),
        ("Đúng-sai", ["0", "1", "0"]),
        ("Trả lời ngắn", ["0", "0", "1"]),
        ("Tự luận", ["1", "0", "0"]),
    ]:
        rows.append(["Đọc hiểu", kind, "2,5", *targets])
    monkeypatch.setattr(__import__(__name__), "ROWS", rows)

    async def forbidden(*_):
        pytest.fail("Bảng loại câu/điểm tường minh phải đọc tại máy")

    result = asyncio.run(
        read_matrix(
            {"name": "matrix" + ext, "data": encoded(document(ext)), "consent": False}, forbidden
        )
    )
    assert result["count"] == 4 and not result["sentToAI"]
    assert [r["type"] for r in result["matrix"]] == ["mcq", "truefalse", "short", "essay"]
    assert [r["pointsQ4"] for r in result["matrix"]] == [10] * 4


def test_spec_only_table_raises_before_ai_and_020_choice_group_parses_locally():
    async def forbidden(*_):
        pytest.fail("Không được gửi AI khi chỉ có bảng đặc tả hoặc ma trận rõ tại máy")

    spec_csv = (
        "Chủ đề;Yêu cầu cần đạt;Nhận biết;Thông hiểu;Vận dụng\n"
        "Hàm số;Nêu được khái niệm;Nêu định nghĩa;Vẽ được đồ thị;Giải bài tập\n"
    )
    with pytest.raises(AIError) as exc:
        asyncio.run(
            read_matrix(
                {"name": "dac-ta.csv", "data": encoded(spec_csv.encode()), "consent": False},
                forbidden,
            )
        )
    assert exc.value.code == "spec_only_matrix"

    dual_csv = (
        "Chủ đề;Loại câu;Điểm/câu;Nhóm chọn;Nhận biết;Thông hiểu;Vận dụng\n"
        "Chung;Trắc nghiệm;0,20;;10;0;0\n"
        "Phần riêng;Tự luận;0,40;;0;5;0\n"
        "Tổng hợp;Tự luận;1,50;;0;0;2\n"
        "Chuyên đề;Trắc nghiệm;0,10;KHMT;10;0;0\n"
        "Chuyên đề;Tự luận;1,00;KHMT;0;2;0\n"
        "Chuyên đề;Trắc nghiệm;0,10;THUD;10;0;0\n"
        "Chuyên đề;Tự luận;1,00;THUD;0;2;0\n"
    )
    res = asyncio.run(
        read_matrix(
            {"name": "hai-nhanh.csv", "data": encoded(dual_csv.encode()), "consent": False},
            forbidden,
        )
    )
    assert not res["sentToAI"]
    # Phần chung (10*0.2 + 5*0.4 + 2*1.5 = 7.0đ) + mỗi nhánh (10*0.1 + 2*1.0 = 3.0đ) = 10.0đ
    assert res["count"] == 29
    assert len(res["matrix"]) == 7
    assert any(r.get("points") == 0.2 for r in res["matrix"])
    assert any(r.get("choiceGroup") == "KHMT" for r in res["matrix"])
