"""Tệp thử tự tạo; không gọi AI thật, không dùng tài liệu giáo viên."""

import asyncio
import base64
import io
import json
import zipfile
from xml.sax.saxutils import escape

import httpx
import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
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


def test_docx_matrix_reads_visible_cell_value_and_multiline_header(tmp_path):
    doc = Document()
    table = doc.add_table(rows=3, cols=4)
    for row, values in zip(table.rows, ROWS, strict=True):
        for cell, value in zip(row.cells, values, strict=True):
            cell.text = value
    table.cell(0, 1).text = "Nhận\nbiết"
    table.cell(1, 1).text = ""
    paragraph = table.cell(1, 1).paragraphs[0]
    # Mã trường của Word đứng trước giá trị hiển thị đã lưu trong ô.
    for kind in ("begin", "separate", "end"):
        if kind == "end":
            paragraph.add_run("2")
        field_char = OxmlElement("w:fldChar")
        field_char.set(qn("w:fldCharType"), kind)
        paragraph.add_run()._r.append(field_char)
        if kind == "begin":
            field = OxmlElement("w:instrText")
            field.text = " = 1+1 "
            paragraph.add_run()._r.append(field)
    buffer = io.BytesIO()
    doc.save(buffer)

    async def forbidden(*_):
        pytest.fail("Bảng rõ không được gửi AI")

    with TestClient(
        create_app(tmp_path, agent_call=forbidden), headers={"Origin": "http://testserver"}
    ) as client:
        result = (
            client.post(
                "/api/ai/matrix", json={"name": "matrix.docx", "data": encoded(buffer.getvalue())}
            )
            .raise_for_status()
            .json()
        )

    assert result["sentToAI"] is False
    assert result["count"] == 5
    assert [(row["topic"], row["targets"]) for row in result["matrix"]] == [
        ("Thẩm thấu", [2, 1, 0]),
        ("Tế bào", [1, 0, 1]),
    ]


def test_status_matches_maximum_matrix_accepted_without_ai(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        limit = client.get("/api/status").json()["matrixImport"]["maxQuestions"]
        assert limit == 60

        def load(n):
            csv = f"Chủ đề;Nhận biết;Thông hiểu;Vận dụng\nSố học;15;0;0\nĐại số;{n};0;0"
            return client.post(
                "/api/ai/matrix",
                json={"name": "matrix.csv", "data": encoded(csv.encode()), "consent": False},
            )

        accepted = load(45)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["count"] == limit and not accepted.json()["sentToAI"]
        rejected = load(46)
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


@pytest.mark.parametrize("targets", [[58, 3, 0], [1.5, 1, 1], [-1, 2, 1], [0, 0, 0]])
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


def _docx_cell(text: str, *, colspan: int = 1, vmerge: str | None = None) -> str:
    tc_pr_parts = []
    if colspan > 1:
        tc_pr_parts.append(f'<w:gridSpan w:val="{colspan}"/>')
    if vmerge == "restart":
        tc_pr_parts.append('<w:vMerge w:val="restart"/>')
    elif vmerge == "continue":
        tc_pr_parts.append("<w:vMerge/>")
    tc_pr = f"<w:tcPr>{''.join(tc_pr_parts)}</w:tcPr>" if tc_pr_parts else ""
    p = f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>" if text else "<w:p/>"
    return f"<w:tc>{tc_pr}{p}</w:tc>"


def test_cv7991_grouped_docx_with_spec_table_parses_locally_with_eight_sublevels(tmp_path):
    from uuid import uuid4

    from mach_backend.ai_questions import GenerateJob, validate_generation_plan
    from mach_backend.matrix_import import checked_matrix, matrix_slots

    banner_tbl = (
        "<w:tbl><w:tr>"
        + _docx_cell("TRƯỜNG MẪU")
        + _docx_cell("KIỂM TRA GIỮA KÌ I - TOÁN 10 Thời gian làm bài: 90 phút")
        + "</w:tr></w:tbl>"
    )
    matrix_tbl = (
        "<w:tbl>"
        + "<w:tr>"
        + _docx_cell("TT", vmerge="restart")
        + _docx_cell("Chương / Chủ đề", vmerge="restart")
        + _docx_cell("Nội dung / Đơn vị kiến thức", vmerge="restart")
        + _docx_cell("Nhiều lựa chọn", colspan=3)
        + _docx_cell("Đúng - Sai (ý)", colspan=3)
        + _docx_cell("Trả lời ngắn", colspan=3)
        + _docx_cell("Tự luận", colspan=3)
        + _docx_cell("Tổng", colspan=3)
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("", vmerge="continue")
        + _docx_cell("", vmerge="continue")
        + _docx_cell("", vmerge="continue")
        + "".join(_docx_cell(lbl) for _ in range(5) for lbl in ("B", "H", "VD"))
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("1", vmerge="restart")
        + _docx_cell("Chương I", vmerge="restart")
        + _docx_cell("Bài 1. Mệnh đề")
        + "".join(
            _docx_cell(v)
            for v in ["1", "", "1", "1", "2", "1", "1", "", "", "", "", "", "3", "2", "2"]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("", vmerge="continue")
        + _docx_cell("", vmerge="continue")
        + _docx_cell("Bài 2. Tập hợp")
        + "".join(
            _docx_cell(v)
            for v in ["1", "", "", "", "", "", "", "1", "", "", "", "1", "1", "1", "1"]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("2")
        + _docx_cell("Chương II")
        + _docx_cell("Bài 3. Bất phương trình")
        + "".join(
            _docx_cell(v) for v in ["", "", "", "", "", "", "", "", "", "", "1", "", "", "1", ""]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("3")
        + _docx_cell("Chương II")
        + _docx_cell("Bài 4. Hệ BPT")
        + "".join(
            _docx_cell(v) for v in ["1", "", "1", "", "", "", "", "", "", "", "", "1", "1", "", "2"]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("4")
        + _docx_cell("Chương III")
        + _docx_cell("Bài 5. Lượng giác")
        + "".join(
            _docx_cell(v) for v in ["1", "1", "", "", "", "", "1", "", "", "", "", "", "2", "1", ""]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("5")
        + _docx_cell("Chương III")
        + _docx_cell("Bài 6. Hệ thức lượng")
        + "".join(
            _docx_cell(v)
            for v in ["2", "1", "", "1", "2", "1", "", "", "", "", "", "", "3", "3", "1"]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("6")
        + _docx_cell("Chương IV")
        + _docx_cell("Bài 7. Vectơ")
        + "".join(
            _docx_cell(v) for v in ["2", "", "", "", "", "", "1", "", "", "", "", "", "3", "", ""]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("Tổng số câu", colspan=3)
        + "".join(
            _docx_cell(v)
            for v in ["8", "2", "2", "2", "4", "2", "3", "1", "", "", "1", "2", "13", "8", "6"]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("Tổng số điểm", colspan=3)
        + "".join(
            _docx_cell(v)
            for v in [
                "2",
                "0,5",
                "0,5",
                "0,5",
                "1",
                "0,5",
                "1,5",
                "0,5",
                "",
                "",
                "1",
                "2",
                "4",
                "3",
                "3",
            ]
        )
        + "</w:tr>"
        + "<w:tr>"
        + _docx_cell("Tỉ lệ %", colspan=3)
        + "".join(
            _docx_cell(v)
            for v in [
                "20",
                "5",
                "5",
                "5",
                "10",
                "5",
                "15",
                "5",
                "",
                "",
                "10",
                "20",
                "40",
                "30",
                "30",
            ]
        )
        + "</w:tr>"
        + "</w:tbl>"
    )
    spec_tbl = (
        "<w:tbl><w:tr>"
        + _docx_cell("Chủ đề")
        + _docx_cell("Yêu cầu cần đạt")
        + _docx_cell("Mức độ")
        + "</w:tr><w:tr>"
        + _docx_cell("Chương I")
        + _docx_cell("Nhận biết mệnh đề")
        + _docx_cell("Biết")
        + "</w:tr></w:tbl>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{banner_tbl}{matrix_tbl}{spec_tbl}</w:body></w:document>",
        )

    async def forbidden(*_):
        pytest.fail("Không được gọi AI hoặc trả 409 với ma trận CV 7991 đọc được tại máy")

    app = create_app(tmp_path, agent_call=forbidden)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        resp = client.post(
            "/api/ai/matrix",
            json={"name": "toan-10-cv7991.docx", "data": encoded(buf.getvalue()), "consent": False},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 21
    assert body["sentToAI"] is False
    assert body["method"] == "python_table"
    assert body["metadata"]["minutes"] == 90

    slots = matrix_slots(body["matrix"])
    assert len(slots) == 21
    tf_slots = [s for s in slots if s.type == "truefalse"]
    assert len(tf_slots) == 2
    assert [s.subLevels for s in tf_slots] == [(0, 1, 1, 2), (0, 1, 1, 2)]
    assert sum(len(s.subLevels or ()) for s in tf_slots) == 8

    job = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        subject="Toán",
        grade="10",
        slots=slots,
    )
    validate_generation_plan(job)

    # statementLevels và subLevels cho 1 dòng có 2 câu Đúng-Sai đều truyền đủ 8 ý vào ExamSlot.
    alias_preview = checked_matrix(
        {
            "matrix": [
                {
                    "topic": "Mệnh đề và tập hợp",
                    "type": "truefalse",
                    "pointsQ4": 4,
                    "targets": [0, 2, 0, 0],
                    "statementLevels": [[0, 1, 1, 2], [0, 1, 2, 3]],
                    "scoringMode": "cv7991_graduated",
                },
                {"topic": "Vectơ", "type": "essay", "pointsQ4": 32, "targets": [0, 0, 1, 0]},
            ],
            "notes": "",
        }
    )
    assert alias_preview["matrix"][0]["subLevels"] == [[0, 1, 1, 2], [0, 1, 2, 3]]
    alias_slots = matrix_slots(alias_preview["matrix"])
    assert alias_slots[0].subLevels == (0, 1, 1, 2)
    assert alias_slots[1].subLevels == (0, 1, 2, 3)
    assert alias_slots[0].scoringMode == "cv7991_graduated"


def test_consent_true_not_blocked_by_spec_only_409():
    calls = []

    async def model(purpose, body):
        calls.append(purpose)
        return {
            "content": json.dumps(
                {
                    "matrix": [{"topic": "Hàm số", "targets": [2, 1, 1]}],
                    "notes": "Đọc khi có đồng ý.",
                }
            )
        }

    spec_csv = (
        "Chủ đề;Yêu cầu cần đạt;Nhận biết;Thông hiểu;Vận dụng\n"
        "Hàm số;Nêu được khái niệm;Nêu định nghĩa;Vẽ được đồ thị;Giải bài tập\n"
    )
    res = asyncio.run(
        read_matrix(
            {"name": "dac-ta.csv", "data": encoded(spec_csv.encode()), "consent": True}, model
        )
    )
    assert res["sentToAI"] is True
    assert res["count"] == 4
    assert calls == ["matrix_import"]
