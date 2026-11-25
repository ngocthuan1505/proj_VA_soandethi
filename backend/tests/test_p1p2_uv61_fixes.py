"""Kiểm thử hồi quy và tính năng mới P1-1..P1-4, P2-2..P2-4 (UV61)."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import zipfile
from types import SimpleNamespace
from uuid import UUID, uuid4
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from test_tnmaker_export import _decode_qr_png_and_verify_ecc

from mach_backend.ai_contract import AIError, Locator, SourceFragment
from mach_backend.ai_questions import (
    MAX_MATRIX_QUESTIONS,
    ExamSlot,
    GeneratedQuestion,
    GenerateJob,
    validate_generation_plan,
)
from mach_backend.ai_sources import (
    is_teacher_owned_source,
    rank_source_fragments,
    workspace_page_sources,
)
from mach_backend.exam_spec_export import validate_and_normalize_answer_key
from mach_backend.export_preflight import audit_export_preflight, data_snapshot_hash
from mach_backend.local_documents import (
    exam_html,
    exam_variant,
    export_file,
    shuffle_variant_question,
)
from mach_backend.local_workspace import create_app
from mach_backend.matrix_import import (
    MAX_MATRIX_QUESTIONS as MATRIX_IMPORT_MAX,
)
from mach_backend.matrix_import import (
    checked_matrix,
    decode_file,
    matrix_slots,
    parse_table,
    read_matrix,
)
from mach_backend.pdf_matrix import read_pdf_matrix
from mach_backend.source_ocr import read_source
from mach_backend.tnmaker_export import build_xlsx_workbook, export_tnmaker_pack
from mach_backend.workspace_backup import restore, validate_backup
from mach_backend.workspace_store import WorkspaceStore

S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _data_url(data: bytes, mime: str = "application/octet-stream") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _make_pdf(*texts: str | None) -> bytes:
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=600, height=800)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        elif text is None:
            image = DecodedStreamObject()
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(8),
                    NameObject("/Height"): NumberObject(8),
                    NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                    NameObject("/BitsPerComponent"): NumberObject(1),
                }
            )
            image.set_data(bytes.fromhex("ff c3 bd fd f3 cf 81 ff"))
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject("/Scan"): writer._add_object(image)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(b"q 96 0 0 96 50 600 cm /Scan Do Q")
            page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _make_png_url() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, "PNG")
    return _data_url(buf.getvalue(), "image/png")


# ---------------------------------------------------------------------------
# 1. P1-1: Strict Teacher Sources, i/y Normalization, Relevance Gate
# ---------------------------------------------------------------------------


def test_is_teacher_owned_source_and_strict_policy(tmp_path):
    assert is_teacher_owned_source({"id": "t1", "name": "De cuong GV.docx"}) is True
    assert is_teacher_owned_source({"id": "c1", "catalog": True}) is False
    assert is_teacher_owned_source({"id": "s1", "sample": True}) is False
    assert is_teacher_owned_source({"id": "l1", "sourceOrigin": "lesson_catalog"}) is False
    assert is_teacher_owned_source({"id": "m1", "sourceOrigin": "community"}) is False
    assert is_teacher_owned_source({"id": "k1", "communityToken": "tok-abc"}) is False

    cat_uuid = uuid4()
    comm_uuid = uuid4()
    teacher_uuid = uuid4()
    exam = {
        "id": str(uuid4()),
        "revision": 1,
        "strictTeacherOnly": True,
        "docs": [
            {
                "id": str(cat_uuid),
                "catalog": True,
                "version": 1,
                "pages": [{"number": 1, "text": "Ngữ liệu SGK mẫu"}],
            },
            {
                "id": str(comm_uuid),
                "communityToken": "pub-123",
                "sourceOrigin": "community",
                "version": 1,
                "pages": [{"number": 1, "text": "Đề chia sẻ cộng đồng"}],
            },
            {
                "id": str(teacher_uuid),
                "version": 1,
                "pages": [{"number": 1, "text": "Giáo án riêng của giáo viên"}],
            },
        ],
    }

    with pytest.raises(AIError) as exc_cat:
        workspace_page_sources(
            exam,
            "local",
            ((cat_uuid, Locator(kind="page", index=1)),),
            None,
            teacher_files_only=True,
        )
    assert exc_cat.value.code == "strict_source_policy"
    assert exc_cat.value.http_status == 400

    with pytest.raises(AIError) as exc_comm:
        workspace_page_sources(
            exam,
            "local",
            ((comm_uuid, Locator(kind="page", index=1)),),
            None,
            teacher_files_only=True,
        )
    assert exc_comm.value.code == "strict_source_policy"

    store = WorkspaceStore(tmp_path)
    exam_id = UUID(exam["id"])
    with store.connect() as db:
        store.put("state", {"exams": [exam], "prefs": [], "current": exam["id"]}, db=db)
        store.put(
            f"matrix-source:{exam_id}",
            [
                {
                    "ownerId": "local",
                    "sourceId": str(comm_uuid),
                    "sourceVersion": 1,
                    "locator": {"kind": "page", "index": 1},
                    "text": "Đề chia sẻ cộng đồng",
                },
                {
                    "ownerId": "local",
                    "sourceId": str(teacher_uuid),
                    "sourceVersion": 1,
                    "locator": {"kind": "page", "index": 1},
                    "text": "Giáo án riêng của giáo viên",
                },
            ],
            db=db,
        )
        with pytest.raises(AIError) as store_exc:
            store.current_sources(exam, db)
        assert store_exc.value.code == "strict_source_policy"
        assert store_exc.value.http_status == 400


def test_rank_source_fragments_iy_normalization_and_nonsense_gate():
    frags = [
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=1),
            text="Bài học về vật lý chất rắn và kỹ thuật đo đạc tỷ lệ xích.",
        ),
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=2),
            text="Mỹ nghệ cổ điển và sĩ số học sinh lớp 9A.",
        ),
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=3),
            text="Ngữ văn hiện đại Việt Nam giai đoạn 1945 - 1975.",
        ),
    ]

    # Truy vấn vô nghĩa / zero-hit phải trả về rỗng [] thay vì trả 8 đoạn không liên quan.
    assert rank_source_fragments("zzq999", frags, top_k=8) == []
    assert rank_source_fragments("xxyyzz000", frags, top_k=8) == []

    # Chuẩn hóa chính tả i/y: vật lí <-> vật lý, kĩ thuật <-> kỹ thuật, tỉ lệ <-> tỷ lệ.
    hits_ly = rank_source_fragments("vật lí kĩ thuật tỉ lệ", frags, top_k=5)
    assert len(hits_ly) == 1
    assert hits_ly[0].locator.index == 1

    hits_my = rank_source_fragments("mĩ nghệ sỹ số", frags, top_k=5)
    assert len(hits_my) == 1
    assert hits_my[0].locator.index == 2


# ---------------------------------------------------------------------------
# 2. P1-2 & Schema: 60 Questions, subLevels/scoringMode, DOCX/XLSX/PDF Matrix
# ---------------------------------------------------------------------------


def test_max_matrix_questions_60_and_slot_schema_compatibility():
    assert MAX_MATRIX_QUESTIONS == 60
    assert MATRIX_IMPORT_MAX == 60

    # Tương thích ngược: không truyền subLevels/scoringMode -> bị lược khi serialize.
    plain_slot = ExamSlot(type="mcq", topic="Hàm số", level=0, pointsQ4=1)
    assert "subLevels" not in plain_slot.model_dump()
    assert "scoringMode" not in plain_slot.model_dump()

    tf_slot = ExamSlot(
        type="truefalse",
        topic="Hình học",
        level=1,
        pointsQ4=4,
        subLevels=(0, 1, 1, 2),
        scoringMode="cv7991_graduated",
    )
    assert tf_slot.subLevels == (0, 1, 1, 2)
    assert tf_slot.scoringMode == "cv7991_graduated"

    gen_q = GeneratedQuestion(
        type="truefalse",
        topic="Hình học",
        level=1,
        pointsQ4=4,
        subLevels=[0, 1, 2, 3],
        scoringMode="uniform",
        stem="Xét tính đúng sai các mệnh đề sau:",
        options=("Mệnh đề A", "Mệnh đề B", "Mệnh đề C", "Mệnh đề D"),
        answer=(True, False, True, False),
        explanation="Giải thích chi tiết.",
        rubric=({"text": "Đúng đủ 4 ý", "pointsQ4": 4},),
        evidence=(),
    )
    assert gen_q.subLevels == (0, 1, 2, 3)
    assert gen_q.scoringMode == "uniform"

    # Ma trận 50 câu (10 điểm = 50 * 0.20đ) vượt ngưỡng cũ 30 và hợp lệ dưới ngưỡng 60.
    rows_50 = [
        {"topic": f"Chủ đề {i}", "type": "mcq", "points": 0.2, "targets": [10, 0, 0, 0]}
        for i in range(1, 6)
    ]
    preview = checked_matrix({"matrix": rows_50, "notes": ""})
    assert preview["count"] == 50
    slots_50 = matrix_slots(rows_50)
    assert len(slots_50) == 50
    job = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        subject="Tiếng Anh",
        grade="12",
        slots=slots_50,
    )
    validate_generation_plan(job)

    with pytest.raises(AIError):
        matrix_slots([{"topic": "Quá tải", "targets": [60, 1, 0, 0]}])


def test_docx_gridspan_vmerge_and_3row_stacked_headers():
    def tc(text: str, *, colspan: int = 1, vmerge: str | None = None) -> str:
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

    doc_rows = [
        # Bảng phụ 1: bảng chú giải điểm (không phải bảng ma trận)
        None,
    ]
    legend_tbl = (
        "<w:tbl>"
        + f"<w:tr>{tc('Ký hiệu')}{tc('Ý nghĩa')}</w:tr>"
        + f"<w:tr>{tc('NB')}{tc('Nhận biết')}</w:tr>"
        + "</w:tbl>"
    )
    _ = doc_rows
    # Bảng 2: Ma trận 3 tầng header gộp ngang/dọc + 2 loại câu + Tổng gộp ngang
    matrix_tbl = (
        "<w:tbl>"
        + "<w:tr>"
        + tc("Chủ đề", vmerge="restart")
        + tc("Loại câu", vmerge="restart")
        + tc("Điểm/câu", vmerge="restart")
        + tc("Nhóm chọn", vmerge="restart")
        + tc("Mức độ", colspan=4)
        + "</w:tr>"
        + "<w:tr>"
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("Nhận biết")
        + tc("Thông hiểu")
        + tc("Vận dụng")
        + tc("Vận dụng cao")
        + "</w:tr>"
        + "<w:tr>"
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("", vmerge="continue")
        + tc("Số câu")
        + tc("Số câu")
        + tc("Số câu")
        + tc("Số câu")
        + "</w:tr>"
        + "<w:tr>"
        + tc("Hàm số")
        + tc("Nhiều lựa chọn")
        + tc("0,40")
        + tc("")
        + tc("1")
        + tc("0")
        + tc("0")
        + tc("0")
        + "</w:tr>"
        + "<w:tr>"
        + tc("Hàm số")
        + tc("Đúng–Sai")
        + tc("1,00")
        + tc("Nhánh A")
        + tc("0")
        + tc("1")
        + tc("0")
        + tc("0")
        + "</w:tr>"
        + "<w:tr>"
        + tc("Phương trình")
        + tc("Tự luận")
        + tc("8,60")
        + tc("Nhánh A")
        + tc("0")
        + tc("0")
        + tc("1")
        + tc("0")
        + "</w:tr>"
        + "<w:tr>"
        + tc("Tổng", colspan=4)
        + tc("1")
        + tc("1")
        + tc("1")
        + tc("0")
        + "</w:tr>"
        + "</w:tbl>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{legend_tbl}{matrix_tbl}</w:body></w:document>",
        )

    rows, _, _ = decode_file("matran-3tang.docx", _data_url(buf.getvalue()))
    assert hasattr(rows, "merges") and len(rows.merges) >= 5
    parsed = parse_table(rows)
    assert parsed is not None
    assert parsed["count"] == 3
    assert [r["type"] for r in parsed["matrix"]] == ["mcq", "truefalse", "essay"]
    assert parsed["matrix"][0]["points"] == 0.4
    assert parsed["matrix"][1]["pointsQ4"] == 4
    assert parsed["matrix"][1]["choiceGroup"] == "Nhánh A"
    assert parsed["matrix"][2]["points"] == 8.6

    # Gộp ô ngang ở thân bảng qua các cột mức độ -> từ chối an toàn (None).
    ambiguous_tbl = (
        "<w:tbl>"
        + f"<w:tr>{tc('Chủ đề')}{tc('NB')}{tc('TH')}{tc('VD')}</w:tr>"
        + f"<w:tr>{tc('Hàm số')}{tc('2', colspan=2)}{tc('1')}</w:tr>"
        + "</w:tbl>"
    )
    bad_buf = io.BytesIO()
    with zipfile.ZipFile(bad_buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{ambiguous_tbl}</w:body></w:document>",
        )
    bad_rows, _, _ = decode_file("bad-merge.docx", _data_url(bad_buf.getvalue()))
    assert parse_table(bad_rows) is None

    # Gộp ô dọc ở cột số câu trong thân bảng -> từ chối an toàn (None).
    v_ambig_tbl = (
        "<w:tbl>"
        + f"<w:tr>{tc('Chủ đề')}{tc('NB')}{tc('TH')}{tc('VD')}</w:tr>"
        + f"<w:tr>{tc('Hàm số')}{tc('2', vmerge='restart')}{tc('0')}{tc('0')}</w:tr>"
        + f"<w:tr>{tc('Phương trình')}{tc('', vmerge='continue')}{tc('1')}{tc('1')}</w:tr>"
        + "</w:tbl>"
    )
    v_buf = io.BytesIO()
    with zipfile.ZipFile(v_buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{v_ambig_tbl}</w:body></w:document>",
        )
    v_rows, _, _ = decode_file("v-bad-merge.docx", _data_url(v_buf.getvalue()))
    assert parse_table(v_rows) is None


def test_xlsx_merge_cells_comma_decimals_and_cached_vs_uncached_formulas():
    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Loại câu</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Điểm/câu</t></is></c>'
        '<c r="D1" t="inlineStr"><is><t>Mức độ</t></is></c>'
        "</row>"
        '<row r="2">'
        '<c r="C2" t="inlineStr"><is><t>Chủ đề</t></is></c>'
        '<c r="D2" t="inlineStr"><is><t>NB</t></is></c>'
        '<c r="E2" t="inlineStr"><is><t>TH</t></is></c>'
        '<c r="F2" t="inlineStr"><is><t>VD</t></is></c>'
        '<c r="G2" t="inlineStr"><is><t>VDC</t></is></c>'
        "</row>"
        '<row r="3">'
        '<c r="A3" t="inlineStr"><is><t>Trắc nghiệm</t></is></c>'
        '<c r="B3" t="inlineStr"><is><t>0,40</t></is></c>'
        '<c r="C3" t="inlineStr"><is><t>Đại số</t></is></c>'
        '<c r="D3"><v>1</v></c><c r="E3"><v>0</v></c><c r="F3"><v>0</v></c><c r="G3"><v>0</v></c>'
        "</row>"
        '<row r="4">'
        '<c r="A4" t="inlineStr"><is><t>Tự luận</t></is></c>'
        '<c r="B4" t="inlineStr"><is><t>9,60</t></is></c>'
        '<c r="C4" t="inlineStr"><is><t>Hình học</t></is></c>'
        '<c r="D4"><v>0</v></c><c r="E4"><v>0</v></c><c r="F4"><v>1</v></c><c r="G4"><v>0</v></c>'
        "</row>"
        '<row r="5">'
        '<c r="C5" t="inlineStr"><is><t>Tổng</t></is></c>'
        '<c r="D5"><f>SUM(D3:D4)</f><v>1</v></c>'
        '<c r="E5"><f>SUM(E3:E4)</f><v>0</v></c>'
        '<c r="F5"><f>SUM(F3:F4)</f><v>1</v></c>'
        '<c r="G5"><f>SUM(G3:G4)</f><v>0</v></c>'
        "</row>"
        "</sheetData>"
        '<mergeCells count="2">'
        '<mergeCell ref="D1:G1"/>'
        '<mergeCell ref="A5:C5"/>'
        "</mergeCells>"
        "</worksheet>"
    )
    sheet2_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Chủ đề</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Yêu cầu cần đạt</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>NB</t></is></c>'
        '<c r="D1" t="inlineStr"><is><t>TH</t></is></c>'
        '<c r="E1" t="inlineStr"><is><t>VD</t></is></c>'
        "</row>"
        '<row r="2">'
        '<c r="A2" t="inlineStr"><is><t>Đại số</t></is></c>'
        '<c r="B2" t="inlineStr"><is><t>Nêu được định nghĩa</t></is></c>'
        "</row>"
        "</sheetData>"
        "</worksheet>"
    )
    wb_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="Ma tran" sheetId="1" r:id="rId1"/>'
        '<sheet name="Dac ta" sheetId="2" r:id="rId2"/>'
        "</sheets></workbook>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", wb_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        zf.writestr("xl/worksheets/sheet2.xml", sheet2_xml)

    async def forbidden(*_):
        pytest.fail("Không được gọi AI khi đọc ma trận Excel hợp lệ")

    res = asyncio.run(
        read_matrix({"name": "cv7991.xlsx", "data": _data_url(buf.getvalue())}, forbidden)
    )
    assert res["count"] == 2
    assert res["matrix"][0]["type"] == "mcq" and res["matrix"][0]["points"] == 0.4
    assert res["matrix"][1]["type"] == "essay" and res["matrix"][1]["points"] == 9.6

    # Công thức chưa cache giá trị <v> -> phải báo matrix_formula
    uncached_xml = sheet1_xml.replace("<f>SUM(D3:D4)</f><v>1</v>", "<f>SUM(D3:D4)</f>")
    uncached_buf = io.BytesIO()
    with zipfile.ZipFile(uncached_buf, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", uncached_xml)
    with pytest.raises(AIError) as err_f:
        decode_file("uncached.xlsx", _data_url(uncached_buf.getvalue()))
    assert err_f.value.code == "matrix_formula"


def test_pdf_matrix_preserves_topic_and_math_across_pages_and_warns_placeholder(monkeypatch):
    def line(*cells: tuple[int, str]) -> str:
        buf = [" "] * 140
        for col, txt in cells:
            buf[col : col + len(txt)] = list(txt)
        return "".join(buf)

    page1 = "\n".join(
        [
            line(
                (2, "Chủ đề"),
                (28, "Nội dung/Đơn vị kiến thức"),
                (70, "Nhận biết"),
                (86, "Thông hiểu"),
                (102, "Vận dụng"),
                (118, "Vận dụng cao"),
            ),
            line((70, "TL"), (86, "TL"), (102, "TL"), (118, "TL")),
            line((2, "Chủ đề 1"), (26, "Hàm số bậc hai"), (71, "1 câu")),
            line((26, "y = ax² (a ≠ 0)"), (69, "(2 điểm)")),
        ]
    )
    # Trang 2 nối tiếp bảng không lặp header và có thêm 1 dòng cảnh báo placeholder
    page2 = "\n".join(
        [
            line((2, "Chủ đề 2"), (26, "Phương trình quy về bậc hai"), (87, "2 câu")),
            line((85, "(8 điểm)")),
            line(
                (2, "Tổng"),
                (71, "1 Câu"),
                (87, "2 Câu"),
                (103, "0 Câu"),
                (119, "0 Câu"),
                (132, "3 Câu"),
            ),
        ]
    )

    monkeypatch.setattr(
        "mach_backend.pdf_matrix.pdf_pages",
        lambda _: [{"text": "Thời gian: 90 phút"}, {"text": page2}],
    )
    monkeypatch.setattr(
        "mach_backend.pdf_matrix.PdfReader",
        lambda *_a, **_kw: SimpleNamespace(
            pages=[
                SimpleNamespace(extract_text=lambda **_kw: page1),
                SimpleNamespace(extract_text=lambda **_kw: page2),
            ]
        ),
    )
    res = read_pdf_matrix(b"fixture")
    assert res is not None
    assert res["count"] == 3
    assert "Chủ đề 1" in res["matrix"][0]["topic"]
    assert "y = ax² (a ≠ 0)" in res["matrix"][0]["topic"]
    assert "Chủ đề 2" in res["matrix"][1]["topic"]

    # Trường hợp PDF có placeholder công thức rỗng (ví dụ font vector bị mất ký tự sau dấu =)
    page1_placeholder = page1.replace(
        line((26, "y = ax² (a ≠ 0)"), (69, "(2 điểm)")),
        line((26, "Đồ thị hàm số y =   (a ≠ 0)"), (69, "(2 điểm)")),
    )
    monkeypatch.setattr(
        "mach_backend.pdf_matrix.PdfReader",
        lambda *_a, **_kw: SimpleNamespace(
            pages=[
                SimpleNamespace(extract_text=lambda **_kw: page1_placeholder),
                SimpleNamespace(extract_text=lambda **_kw: page2),
            ]
        ),
    )
    res_warn = read_pdf_matrix(b"fixture")
    assert res_warn is not None
    assert any(w["code"] == "pdf_math_font_placeholder" for w in res_warn.get("warnings", []))


# ---------------------------------------------------------------------------
# 3. P1-3: Relative Question Reference Scanning & Directionality
# ---------------------------------------------------------------------------


def test_variant_relative_refs_scan_all_questions_fields_and_directionality():
    def q(qid: str, stem: str = "Hỏi", *, options=None, explanation: str = "", lock: bool = False):
        item = {
            "id": qid,
            "type": "mcq",
            "stem": stem,
            "options": options or ["1", "2", "3", "4"],
            "answer": 0,
            "explanation": explanation,
        }
        if lock:
            item["lockPosition"] = True
        return item

    # 1. Câu ngoài vùng chọn có tham chiếu lùi trong explanation -> chặn trộn phía trước
    exam_back_exp = {
        "title": "Đề thử",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Hỏi hai"),
            q("q3", "Hỏi ba", explanation="Suy ra từ câu vừa rồi."),
            q("q4", "Hỏi bốn"),
        ],
    }
    with pytest.raises(AIError) as err1:
        exam_variant(exam_back_exp, {"questionIds": ["q1", "q2"], "offset": 1})
    assert err1.value.code == "invalid_variant"
    assert err1.value.http_status == 400
    assert "Câu 3 có tham chiếu tương đối" in str(err1.value)

    # Trộn phía sau q2 (q3, q4) thì không làm lệch phía trước q2
    exam_back_after = {
        "title": "Đề thử",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Dựa vào câu kế trước."),
            q("q3", "Hỏi ba"),
            q("q4", "Hỏi bốn"),
        ],
    }
    ok_after = exam_variant(exam_back_after, {"questionIds": ["q3", "q4"], "offset": 1})
    assert [item["id"] for item in ok_after["questions"]] == ["q1", "q2", "q4", "q3"]

    # 2. Tham chiếu tiến trong options/explanation: chặn trộn sau q3, giữ trộn trước q3
    exam_fwd = {
        "title": "Đề thử tiến",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Hỏi hai"),
            q("q3", "Hỏi ba", options=["A", "Theo câu sau", "C", "D"]),
            q("q4", "Hỏi bốn"),
        ],
    }
    ok_before = exam_variant(exam_fwd, {"questionIds": ["q1", "q2"], "offset": 1})
    assert [item["id"] for item in ok_before["questions"]] == ["q2", "q1", "q3", "q4"]

    with pytest.raises(AIError) as err_fwd:
        exam_variant(exam_fwd, {"questionIds": ["q3", "q4"], "offset": 1})
    assert err_fwd.value.code == "invalid_variant"

    # 3. lockPosition giữ nguyên cả cặp liên kết q1-q2 -> trộn q3-q4 vẫn hợp lệ
    exam_locked = {
        "title": "Đề khóa vị trí",
        "questions": [
            q("q1", "Hỏi một", lock=True),
            q("q2", "Hỏi hai theo câu trên", lock=True),
            q("q3", "Hỏi ba"),
            q("q4", "Hỏi bốn"),
        ],
    }
    ok_locked = exam_variant(exam_locked, {"questionIds": ["q1", "q2", "q3", "q4"], "offset": 1})
    assert [item["id"] for item in ok_locked["questions"]] == ["q1", "q2", "q4", "q3"]

    # Nhưng nếu chỉ khóa q2 mà không khóa q1 -> q1 dịch chuyển làm hỏng q2 -> phải chặn!
    exam_half_locked = {
        "title": "Đề khóa nửa cặp",
        "questions": [
            q("q1", "Hỏi một", lock=False),
            q("q2", "Hỏi hai theo câu trên", lock=True),
            q("q3", "Hỏi ba"),
        ],
    }
    with pytest.raises(AIError) as err_half:
        exam_variant(exam_half_locked, {"questionIds": ["q1", "q2", "q3"], "offset": 1})
    assert err_half.value.code == "invalid_variant"


def test_m07_04_rubric_rich_docs_distant_region_and_multi_block_relative_refs():
    def q(qid: str, stem: str = "Hỏi", **extra):
        return {
            "id": qid,
            "type": "mcq",
            "stem": stem,
            "options": ["1", "2", "3", "4"],
            "answer": 0,
            "explanation": "",
            **extra,
        }

    # 1. Quét cả rubric (text/criterion/content/step/richDoc), answerText, solution, richDoc.
    rubric_num_exam = {
        "title": "Tham chiếu trong barem",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Hỏi hai"),
            {
                "id": "q3",
                "type": "essay",
                "stem": "Bài tự luận",
                "rubric": [{"criterion": "Dựa vào kết quả câu 1", "points": 1.0}],
            },
        ],
    }
    with pytest.raises(AIError) as err_rub_num:
        exam_variant(rubric_num_exam, {"questionIds": ["q1", "q2"], "offset": 1})
    assert err_rub_num.value.code == "invalid_variant"

    rubric_rel_exam = {
        "title": "Tham chiếu tương đối trong richDoc barem",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Hỏi hai"),
            {
                "id": "q3",
                "type": "essay",
                "stem": "Bài tự luận",
                "rubric": [
                    {
                        "step": "Ý một",
                        "richDoc": {
                            "type": "doc",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Từ câu trên suy ra."}],
                                }
                            ],
                        },
                        "points": 1.0,
                    }
                ],
            },
        ],
    }
    with pytest.raises(AIError) as err_rub_rel:
        exam_variant(rubric_rel_exam, {"questionIds": ["q1", "q2"], "offset": 1})
    assert err_rub_rel.value.code == "invalid_variant"

    # shuffle_variant_question KHÔNG quét rubric để tránh khóa nhầm phương án A/B/C/D.
    mcq_with_rubric = q(
        "q-shuf",
        "Chọn đáp án đúng:",
        rubric=[{"text": "Chọn A được 0.25đ; hai ý đầu giải thích rõ.", "points": 0.25}],
    )
    shuffled_q = shuffle_variant_question(mcq_with_rubric, 1)
    assert shuffled_q["options"] != mcq_with_rubric["options"]

    # 2. Vùng trộn ở xa không làm vỡ cặp (idx-1, idx) hoặc (idx, idx+1) -> cho phép!
    ok_distant_tail = exam_variant(
        {
            "title": "Vùng trộn xa đuôi",
            "questions": [
                q("q1", "Theo câu sau để tính."),
                q("q2", "Hỏi hai"),
                q("q3", "Hỏi ba"),
                q("q4", "Hỏi bốn"),
            ],
        },
        {"questionIds": ["q3", "q4"], "offset": 1},
    )
    assert [item["id"] for item in ok_distant_tail["questions"]] == ["q1", "q2", "q4", "q3"]

    ok_distant_head = exam_variant(
        {
            "title": "Vùng trộn xa đầu",
            "questions": [
                q("q1", "Hỏi một"),
                q("q2", "Hỏi hai"),
                q("q3", "Hỏi ba"),
                q("q4", "Suy ra từ câu trước."),
            ],
        },
        {"questionIds": ["q1", "q2"], "offset": 1},
    )
    assert [item["id"] for item in ok_distant_head["questions"]] == ["q2", "q1", "q3", "q4"]

    # 3. Tham chiếu số nhiều ("các/những/tất cả câu trên|trước|sau|dưới") kiểm toàn tiền/hậu tố.
    plural_exam = {
        "title": "Số nhiều",
        "questions": [
            q("q1", "Hỏi một"),
            q("q2", "Hỏi hai"),
            q("q3", "Hỏi ba"),
            q("q4", "Tổng hợp tất cả các câu trên."),
        ],
    }
    with pytest.raises(AIError) as err_plural:
        exam_variant(plural_exam, {"questionIds": ["q1", "q2"], "offset": 1})
    assert err_plural.value.code == "invalid_variant"

    # 4. multi_block giữ nguyên cặp liền kề trong cùng khối ngữ liệu, nhưng chặn qua ranh giới khối.
    multi_block_ok = {
        "title": "Đọc hiểu 2 khối",
        "questions": [
            q("p1a", "Đoạn thứ nhất ý đầu", passageId="p1"),
            q("p1b", "Dựa vào câu trên của đoạn thứ nhất", passageId="p1"),
            q("p2a", "Đoạn thứ hai ý đầu", passageId="p2"),
            q("p2b", "Đoạn thứ hai ý sau", passageId="p2"),
        ],
    }
    swapped_blocks = exam_variant(
        multi_block_ok, {"questionIds": ["p1a", "p1b", "p2a", "p2b"], "offset": 1}
    )
    assert [item["id"] for item in swapped_blocks["questions"]] == ["p2a", "p2b", "p1a", "p1b"]

    multi_block_cross_err = {
        "title": "Đọc hiểu lệch khối",
        "questions": [
            q("p1a", "Đoạn thứ nhất ý đầu", passageId="p1"),
            q("p1b", "Đoạn thứ nhất ý tiếp", passageId="p1"),
            q("p2a", "Tiếp nối câu trước", passageId="p2"),
            q("p2b", "Đoạn thứ hai ý tiếp", passageId="p2"),
        ],
    }
    with pytest.raises(AIError) as err_cross:
        exam_variant(
            multi_block_cross_err,
            {"questionIds": ["p1a", "p1b", "p2a", "p2b"], "offset": 1},
        )
    assert err_cross.value.code == "invalid_variant"


# ---------------------------------------------------------------------------
# 4. P1-4: Empty Selected Option, QR V2_indexed & Multi-sheet build_xlsx_workbook
# ---------------------------------------------------------------------------


def test_empty_selected_option_qr_v2_and_build_xlsx_workbook(tmp_path):
    broken_exam = {
        "title": "Đề lỗi phương án rỗng",
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "Hỏi 1",
                "options": ["Đáp án A", "   ", "C", "D"],
                "answer": 1,
                "points": 1.0,
                "level": 0,
            }
        ],
    }
    with pytest.raises(AIError) as err_tnm:
        export_tnmaker_pack({"exam": broken_exam}, tmp_path)
    assert err_tnm.value.code == "empty_selected_option"
    assert err_tnm.value.http_status == 400

    with pytest.raises(AIError) as err_spec:
        validate_and_normalize_answer_key(broken_exam, teacher=True)
    assert err_spec.value.code == "empty_selected_option"
    assert err_spec.value.http_status == 400

    # Đề hỗn hợp: MCQ + Essay + Đúng-Sai + Trả lời ngắn + MCQ -> V2_indexed
    mixed_exam = {
        "title": "Đề hỗn hợp QR V2",
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "MCQ 1",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
            },
            {"id": "q2", "type": "essay", "stem": "Tự luận", "options": []},
            {
                "id": "q3",
                "type": "truefalse",
                "stem": "Đúng sai",
                "options": ["a", "b", "c", "d"],
                "truthValues": [True, False, True, False],
            },
            {
                "id": "q4",
                "type": "short",
                "stem": "Trả lời ngắn",
                "options": [],
                "answerText": "42",
            },
            {
                "id": "q5",
                "type": "mcq",
                "stem": "MCQ 5",
                "options": ["X", "Y", "Z", "W"],
                "answer": 3,
            },
        ],
    }
    pack = export_tnmaker_pack({"exam": mixed_exam}, tmp_path)
    assert pack["qrFormat"] == "V2_indexed"
    assert pack["qrPayload"] == "KEY|V2|101:1A,5D"
    with zipfile.ZipFile(tmp_path / pack["filename"]) as zf:
        assert _decode_qr_png_and_verify_ecc(zf.read("QR_DapAn.png")) == "KEY|V2|101:1A,5D"

    # Đề liên tục 1..2 + Essay ở cuối -> V1_contiguous
    contig_exam = {
        "title": "Đề liên tục QR V1",
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "MCQ 1",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
            },
            {
                "id": "q2",
                "type": "mcq",
                "stem": "MCQ 2",
                "options": ["5", "6", "7", "8"],
                "answer": 1,
            },
            {"id": "q3", "type": "essay", "stem": "TL", "options": []},
        ],
    }
    pack_v1 = export_tnmaker_pack({"exam": contig_exam}, tmp_path)
    assert pack_v1["qrFormat"] == "V1_contiguous"
    assert pack_v1["qrPayload"] == "KEY|V1|101:AB"

    # build_xlsx_workbook hỗ trợ nhiều sheet, inlineStr + ô số
    xlsx = build_xlsx_workbook(
        [
            ("BangDiem", [["HoTen", "Diem", "Dat"], ["Nguyễn An", 8.75, True]]),
            ("ThongKeCauHoi", [["Cau", "TyLeDung"], [1, 0.85]]),
        ]
    )
    with zipfile.ZipFile(io.BytesIO(xlsx)) as xf:
        wb_text = xf.read("xl/workbook.xml").decode("utf-8")
        assert 'name="BangDiem"' in wb_text and 'name="ThongKeCauHoi"' in wb_text
        s1 = ET.fromstring(xf.read("xl/worksheets/sheet1.xml"))
        s2 = ET.fromstring(xf.read("xl/worksheets/sheet2.xml"))
        s1_cells = {c.get("r"): (c.get("t"), "".join(c.itertext())) for c in s1.findall(f".//{S}c")}
        s2_cells = {c.get("r"): (c.get("t"), "".join(c.itertext())) for c in s2.findall(f".//{S}c")}
        assert s1_cells["A2"] == ("inlineStr", "Nguyễn An")
        assert s1_cells["B2"] == (None, "8.75")
        assert s1_cells["C2"] == ("b", "1")
        assert s2_cells["A2"] == (None, "1")
        assert s2_cells["B2"] == (None, "0.85")


# ---------------------------------------------------------------------------
# 5. P2-2: Whitespace Title Reject & tro-ly-soan-de-batch Non-destructive Merge
# ---------------------------------------------------------------------------


def test_whitespace_title_rejected_and_batch_backup_merge_restore(tmp_path):
    exam_existing_id = str(uuid4())
    exam_existing = {
        "id": exam_existing_id,
        "revision": 2,
        "title": "Đề hiện có",
        "subject": "Toán",
        "grade": "9",
        "questions": [],
        "docs": [],
        "matrix": [],
        "history": [],
        "undo": [],
        "redo": [],
        "chat": [],
        "data": [],
        "quote": {"text": "", "versions": []},
    }
    png_old = _make_png_url()
    # Tạo một PNG khác biệt (1x1 khác màu) để kiểm tra không ghi đè file cùng key
    buf_new = io.BytesIO()
    Image.new("RGB", (3, 3), "blue").save(buf_new, "PNG")
    png_new = _data_url(buf_new.getvalue(), "image/png")

    # 1. Từ chối title toàn khoảng trắng
    bad_single = {
        "format": "tro-ly-soan-de",
        "version": 1,
        "state": {
            "current": exam_existing_id,
            "exams": [{**exam_existing, "title": "   "}],
            "prefs": [],
        },
        "files": {},
    }
    with pytest.raises(AIError) as err_ws:
        validate_backup(bad_single)
    assert err_ws.value.code == "invalid_backup"

    bad_batch = {
        "format": "tro-ly-soan-de-batch",
        "version": 1,
        "savedAt": "2026-11-25T00:00:00Z",
        "exams": [{**exam_existing, "title": "\t\n"}],
    }
    with pytest.raises(AIError) as err_batch_ws:
        validate_backup(bad_batch)
    assert err_batch_ws.value.code == "invalid_backup"

    # 2. Batch preview + merge restore không phá hủy dữ liệu cũ
    batch_exam_2_id = str(uuid4())
    batch = {
        "format": "tro-ly-soan-de-batch",
        "version": 1,
        "savedAt": "2026-11-25T00:00:00Z",
        "exams": [
            {
                "id": exam_existing_id,  # Trùng ID + trùng title với đề hiện có
                "title": "Đề hiện có",
                "questions": [
                    {
                        "id": str(uuid4()),
                        "type": "mcq",
                        "stem": "Câu nhập từ batch",
                        "options": ["1", "2", "3", "4"],
                        "answer": 0,
                        "level": 0,
                    }
                ],
                "docs": [{"id": "d1", "fileId": "img-shared", "name": "hinh.png"}],
            },
            {
                "id": batch_exam_2_id,
                "title": "Đề mới từ batch",
                "questions": [],
            },
        ],
        "files": {"img-shared": png_new},
    }

    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        client.put(
            "/api/kv",
            json={
                "key": "state",
                "value": {
                    "current": exam_existing_id,
                    "exams": [exam_existing],
                    "prefs": [{"text": "Giữ tùy chọn cũ"}],
                },
            },
        ).raise_for_status()
        client.put("/api/kv", json={"key": "file:img-shared", "value": png_old}).raise_for_status()

        prev = client.post("/api/workspace/restore/preview", json=batch)
        assert prev.status_code == 200, prev.text
        pjson = prev.json()
        assert pjson["mode"] == "merge_batch"
        assert pjson["examCount"] == 2
        assert pjson["fileCount"] == 1
        assert pjson["duplicateTitles"] == ["Đề hiện có"]

        applied = client.post(
            "/api/workspace/restore",
            json=batch,
            headers={"If-Match": str(pjson["revision"])},
        )
        assert applied.status_code == 200, applied.text
        ajson = applied.json()
        assert ajson["mode"] == "merge_batch" and ajson["importedExams"] == 2

        state_after = client.get("/api/kv?key=state").json()["value"]
        assert state_after["current"] == exam_existing_id
        assert state_after["prefs"] == [{"text": "Giữ tùy chọn cũ"}]
        assert len(state_after["exams"]) == 3
        ids_after = [e["id"] for e in state_after["exams"]]
        assert len(set(ids_after)) == 3
        assert exam_existing_id in ids_after and batch_exam_2_id in ids_after
        # Tệp cũ giữ nguyên, tệp trùng mã khác nội dung được remap an toàn
        assert client.get("/api/kv?key=file:img-shared").json()["value"] == png_old
        remapped_id = state_after["exams"][1]["docs"][0]["fileId"]
        assert remapped_id != "img-shared"
        assert client.get(f"/api/kv?key=file:{remapped_id}").json()["value"] == png_new

        # Tùy chọn skipExisting=True: bỏ qua đề trùng ID
        store = client.app.state.store
        cur_rev = client.get("/api/kv?key=state").json()["revision"]
        res_skip = restore(
            store,
            {
                "format": "tro-ly-soan-de-batch",
                "version": 1,
                "skipExisting": True,
                "exams": [{**exam_existing, "title": "Đề bị bỏ qua"}],
            },
            cur_rev,
        )
        assert res_skip["skippedExams"] == 1 and res_skip["importedExams"] == 0


# ---------------------------------------------------------------------------
# 6. P2-3: UC8 (dataLinked/rule) & UC9 (stale evidence) in export_preflight
# ---------------------------------------------------------------------------


def test_uc8_linked_data_and_uc9_stale_evidence_preflight():
    current_data = [
        {"label": "Khu vực A", "value": 120},
        {"label": "Khu vực B", "value": 300},
        {"label": "Khu vực C", "value": 180},
    ]
    current_hash = data_snapshot_hash(current_data)

    # 1. Ca chuẩn: data, answer, options, hash và explanation đều khớp -> ready=True
    clean_exam = {
        "title": "Đề liên kết chuẩn",
        "data": current_data,
        "docs": [
            {
                "id": "doc-1",
                "name": "Tai_lieu.docx",
                "pages": [
                    {"number": 1, "text": "Số liệu A, B, C."},
                    {"number": 3, "text": "Trang 3."},
                ],
            }
        ],
        "questions": [
            {
                "id": "q1",
                "v": 1,
                "type": "mcq",
                "points": 5.0,
                "rule": "max",
                "dataLinked": True,
                "dataSnapshotHash": current_hash,
                "stem": "Khu vực nào cao nhất?",
                "options": ["Khu vực A", "Khu vực B", "Khu vực C", "Bằng nhau"],
                "answer": 1,
                "explanation": "Khu vực B có 300 người, lớn nhất trong 3 khu vực.",
                "source": {"docId": "doc-1", "page": 1},
                "evidence": [
                    {
                        "sourceId": "doc-1",
                        "sourceVersion": 1,
                        "locator": {"kind": "page", "index": 1},
                        "quote": "Số liệu A, B, C.",
                    }
                ],
                "approval": {"version": 1, "status": "approved"},
            },
            {
                "id": "q2",
                "v": 1,
                "type": "mcq",
                "points": 5.0,
                "rule": "difference",
                "dataLinked": True,
                "dataSnapshotHash": current_hash,
                "stem": "Khu vực B nhiều hơn khu vực A bao nhiêu?",
                "options": ["120 người", "180 người", "240 người", "300 người"],
                "answer": 1,
                "explanation": "300 − 120 = 180 người.",
                "approval": {"version": 1, "status": "approved"},
            },
        ],
    }
    clean_rep = audit_export_preflight(clean_exam)
    assert clean_rep["ready"] is True, clean_rep["blockingIssues"]

    # 2. UC8 lỗi: lời giải còn số liệu cũ (240 thay vì 300/180), hash cũ, check.status == "review"
    stale_uc8 = {
        **clean_exam,
        "questions": [
            {
                **clean_exam["questions"][0],
                "dataSnapshotHash": "old-hash-v0",
                "explanation": "Khu vực B có 240 người, lớn nhất.",
                "check": {"version": 1, "status": "review"},
            },
            {
                **clean_exam["questions"][1],
                "answer": 0,  # sai so với 180
                "explanation": "240 − 120 = 120 người.",
            },
        ],
    }
    rep_uc8 = audit_export_preflight(stale_uc8)
    assert rep_uc8["ready"] is False
    codes_uc8 = {item["code"] for item in rep_uc8["blockingIssues"]}
    assert "linked_data_explanation_stale" in codes_uc8
    assert "linked_data_mismatch" in codes_uc8

    # 3. UC9: evidence.stale=True hoặc lệch trang với q.source.page trên cùng docId
    uc9_exam = {
        **clean_exam,
        "questions": [
            {
                **clean_exam["questions"][0],
                "evidence": [
                    {
                        "sourceId": "doc-1",
                        "sourceVersion": 1,
                        "locator": {"kind": "page", "index": 3},
                        "quote": "Trích dẫn cũ từ trang 3",
                        "stale": True,
                    }
                ],
            },
            clean_exam["questions"][1],
        ],
    }
    rep_uc9 = audit_export_preflight(uc9_exam)
    stale_warns = [w for w in rep_uc9["warnings"] if w["code"] == "stale_quote_evidence"]
    assert len(stale_warns) == 1
    assert stale_warns[0]["requiresReverification"] is True
    assert rep_uc9["needsAttention"] is True

    # UC9 mở rộng: đổi docId khác, chuyển bản nhập tay, lệch questionVersion, và quote thay đổi.
    uc9_doc_changed = {
        **clean_exam,
        "questions": [
            {
                **clean_exam["questions"][0],
                "source": {"docId": "doc-2", "page": 1},
            },
            clean_exam["questions"][1],
        ],
    }
    assert any(
        w["code"] == "stale_quote_evidence"
        for w in audit_export_preflight(uc9_doc_changed)["warnings"]
    )

    uc9_manual = {
        **clean_exam,
        "questions": [
            {
                **clean_exam["questions"][0],
                "source": {"location": "Bản nhập tay"},
            },
            clean_exam["questions"][1],
        ],
    }
    assert any(
        w["code"] == "stale_quote_evidence" for w in audit_export_preflight(uc9_manual)["warnings"]
    )

    uc9_ver_mismatch = {
        **clean_exam,
        "questions": [
            {
                **clean_exam["questions"][0],
                "v": 2,
                "evidence": [{**clean_exam["questions"][0]["evidence"][0], "questionVersion": 1}],
            },
            clean_exam["questions"][1],
        ],
    }
    assert any(
        w["code"] == "stale_quote_evidence"
        for w in audit_export_preflight(uc9_ver_mismatch)["warnings"]
    )

    uc9_quote_stale = {
        **clean_exam,
        "quote": {"text": "Ngữ liệu mới đã sửa khác trước."},
        "questions": [
            {
                **clean_exam["questions"][0],
                "quote": True,
            },
            clean_exam["questions"][1],
        ],
    }
    assert any(
        w["code"] == "stale_quote_evidence"
        for w in audit_export_preflight(uc9_quote_stale)["warnings"]
    )


def test_uc8_uc9_draft_banner_on_teacher_html_and_docx_but_not_student(tmp_path):
    current_data = [{"label": "A", "value": 100}, {"label": "B", "value": 300}]
    stale_exam = {
        "id": "exam-draft-1",
        "title": "Đề có cảnh báo UC8 UC9",
        "subject": "Toán",
        "grade": "9",
        "minutes": 45,
        "data": current_data,
        "quote": {"text": "Ngữ liệu mới đã thay đổi."},
        "questions": [
            {
                "id": "q1",
                "v": 2,
                "type": "mcq",
                "points": 5.0,
                "rule": "max",
                "dataLinked": True,
                "dataSnapshotHash": "old-hash",
                "stem": "Mục nào lớn nhất?",
                "options": ["A", "B", "C", "D"],
                "answer": 1,
                "explanation": "Giá trị cũ là 240.",
                "approval": {"version": 2, "status": "approved"},
            },
            {
                "id": "q2",
                "v": 2,
                "type": "mcq",
                "points": 5.0,
                "quote": True,
                "stem": "Dựa vào ngữ liệu:",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
                "source": {"docId": "doc-1", "page": 1},
                "evidence": [
                    {
                        "sourceId": "doc-1",
                        "questionVersion": 1,
                        "locator": {"kind": "page", "index": 1},
                        "quote": "Trích đoạn cũ không còn trong ngữ liệu",
                    }
                ],
                "approval": {"version": 2, "status": "approved"},
            },
        ],
    }

    # export_file tự động nhặt cảnh báo UC8/UC9 trên bản GV và chèn banner + ghi chú từng câu.
    html_res = export_file(
        {"type": "exam", "format": "html", "teacher": True, "exam": stale_exam},
        tmp_path,
        "http://localhost",
    )
    html_text = (tmp_path / html_res["filename"]).read_text(encoding="utf-8")
    assert "BẢN NHÁP — CẦN RÀ SOÁT TRƯỚC KHI PHÁT" in html_text
    assert 'data-warning-code="linked_data_explanation_stale"' in html_text
    assert 'data-warning-code="stale_quote_evidence"' in html_text
    assert "question-draft-note" in html_text

    # Xuất trực tiếp exam_html bản học sinh dù is_draft=True vẫn không được lộ banner/cảnh báo GV.
    student_html = exam_html(
        stale_exam,
        False,
        "http://localhost",
        [{"svg": "<svg/>"}],
        is_draft=True,
        draft_warnings=[{"code": "stale_quote_evidence", "questionId": "q2", "message": "Ẩn"}],
    )
    assert "BẢN NHÁP — CẦN RÀ SOÁT TRƯỚC KHI PHÁT" not in student_html
    assert "question-draft-note" not in student_html


# ---------------------------------------------------------------------------
# 7. P2-4: Selective PDF OCR Subset & Page Remapping
# ---------------------------------------------------------------------------


def test_selective_pdf_ocr_subset_remaps_numbers_and_preserves_clean_pages():
    mixed = _make_pdf("Page one clean", None, "Page three clean")
    calls: list[bytes] = []

    async def fake_ocr(purpose, body):
        assert purpose == "source_ocr"
        subset_bytes = base64.b64decode(body["document"]["data"])
        calls.append(subset_bytes)
        subset_reader = PdfReader(io.BytesIO(subset_bytes))
        # Chỉ gửi đúng 1 trang scan (không gửi trang 1 và trang 3 đã có chữ sạch)
        assert len(subset_reader.pages) == 1
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {
                            "number": 1,
                            "text": r"Tính $x^2 + 1 = 5$ [HÌNH 1: Đồ thị]",
                            "uncertain": False,
                        }
                    ],
                    "notes": "Đã đọc trang scan.",
                }
            )
        }

    # only_needs_ocr=True -> chỉ OCR trang 2, giữ nguyên number=2 và gắn structured
    res = asyncio.run(
        read_source(
            {"name": "mixed.pdf", "consent": True},
            _data_url(mixed, "application/pdf"),
            fake_ocr,
            only_needs_ocr=True,
        )
    )
    assert len(calls) == 1
    assert res["sentToAI"] is True
    assert [p["number"] for p in res["pages"]] == [2]
    assert res["pages"][0]["math_blocks"][0]["latex"] == "x^2 + 1 = 5"
    assert res["pages"][0]["figures"][0]["kind"] == "placeholder"

    # page_numbers=[3] -> OCR riêng trang 3, remapped về 3
    calls.clear()
    res_p3 = asyncio.run(
        read_source(
            {"name": "mixed.pdf", "consent": True},
            _data_url(mixed, "application/pdf"),
            fake_ocr,
            page_numbers=[3],
        )
    )
    assert [p["number"] for p in res_p3["pages"]] == [3]

    # PDF sạch 100% + only_needs_ocr=True -> không gọi AI
    clean_pdf = _make_pdf("Clean 1", "Clean 2")

    async def forbidden_ocr(*_):
        pytest.fail("PDF đã có chữ sạch không được gọi AI khi only_needs_ocr=True")

    res_clean = asyncio.run(
        read_source(
            {"name": "clean.pdf", "consent": True},
            _data_url(clean_pdf, "application/pdf"),
            forbidden_ocr,
            only_needs_ocr=True,
        )
    )
    assert res_clean["sentToAI"] is False and res_clean["pages"] == []

    # PDF > 20 trang nhưng chỉ có 2 trang scan -> subset hợp lệ (2 <= 20)
    big_pages: list[str | None] = [f"Clean {i}" for i in range(1, 24)] + [None, None]
    big_pdf = _make_pdf(*big_pages)

    async def big_ocr(_purpose, body):
        subset_reader = PdfReader(io.BytesIO(base64.b64decode(body["document"]["data"])))
        assert len(subset_reader.pages) == 2
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {"number": 1, "text": "Scan trang 24", "uncertain": False},
                        {"number": 2, "text": "Scan trang 25", "uncertain": False},
                    ],
                    "notes": "",
                }
            )
        }

    res_big = asyncio.run(
        read_source(
            {"name": "big.pdf", "consent": True},
            _data_url(big_pdf, "application/pdf"),
            big_ocr,
            only_needs_ocr=True,
        )
    )
    assert [p["number"] for p in res_big["pages"]] == [24, 25]
