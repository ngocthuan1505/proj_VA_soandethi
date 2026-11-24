"""Bộ kiểm thử học liệu K-12 Việt Nam (SC-01..SC-10) và ma trận hỗn hợp."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from mach_backend import (
    exam_analytics,
    exam_planning,
    exam_spec_export,
    export_preflight,
    local_documents,
    matrix_import,
    pdf_matrix,
    rich_patch,
    tnmaker_export,
    word_export,
)
from mach_backend.ai_contract import AIError

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "tests" / "fixtures" / "school-corpus"
EDGE_DIR = CORPUS_DIR / "matrix-messy-edge-cases"
EXAM_CODES = tuple(f"SC-{idx:02d}" for idx in range(1, 11))
TEACHER_META = {
    "name": "Cô Nguyễn Minh Anh",
    "school": "TRƯỜNG MẪU GIÁO DỤC PHỔ THÔNG",
    "subject": "Tổng hợp K-12",
    "grade": "9-12",
}


def _load_exam(code: str) -> dict[str, Any]:
    path = CORPUS_DIR / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _file_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:application/octet-stream;base64,{encoded}"


def _find_chrome() -> str | None:
    candidates = [
        os.environ.get("BROWSER_PATH"),
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("msedge"),
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return str(cand)
    return None


def _effective_points_p100(exam: dict[str, Any]) -> int:
    common = 0
    branches: dict[str, int] = {}
    for q in exam["questions"]:
        p100 = round(float(q["points"]) * 100)
        grp = (q.get("choiceGroup") or "").strip()
        if grp:
            branches[grp] = branches.get(grp, 0) + p100
        else:
            common += p100
    if not branches:
        return common
    branch_totals = {common + pts for pts in branches.values()}
    assert len(branch_totals) == 1, f"Các nhánh không cùng tổng điểm: {branches}"
    return next(iter(branch_totals))


def test_corpus_files_exist_and_schemas_match() -> None:
    for code in EXAM_CODES:
        exam = _load_exam(code)
        assert exam["title"]
        assert isinstance(exam["questions"], list)
        assert _effective_points_p100(exam) == 1000, f"{code} phải đúng 10,00 điểm"
        for q_idx, q in enumerate(exam["questions"], 1):
            assert q.get("approved") is True, f"{code} câu {q_idx} chưa approved"
            assert isinstance(q.get("stem"), str) and q["stem"].strip()
            if "richDoc" in q:
                assert rich_patch.project(q["richDoc"], []) == q["stem"]
            if "explanationDoc" in q and q.get("explanation"):
                assert rich_patch.project(q["explanationDoc"], []) == q["explanation"]
            q_type = q["type"]
            if q_type == "mcq":
                opts = q["options"]
                assert len(opts) == 4
                assert all(isinstance(opt, str) and opt.strip() for opt in opts)
                assert 0 <= int(q["answer"]) < 4
                if "optionDocs" in q:
                    for opt, doc in zip(opts, q["optionDocs"], strict=True):
                        assert rich_patch.project(doc, []) == opt
            elif q_type == "truefalse":
                assert len(q["options"]) == 4
                assert len(q["truthValues"]) == 4
                assert all(isinstance(v, bool) for v in q["truthValues"])
            elif q_type == "short":
                assert isinstance(q["answerText"], str) and q["answerText"].strip()
            elif q_type == "essay":
                rubric = q.get("rubric") or []
                assert rubric, f"{code} câu tự luận {q_idx} thiếu rubric"
                rubric_p100 = sum(round(float(item["points"]) * 100) for item in rubric)
                assert rubric_p100 == round(float(q["points"]) * 100)


def test_corpus_subject_specific_features() -> None:
    # SC-01: Toán 9 CV 7991 (22 câu: 12 MCQ + 2 ĐS + 4 TLN + 4 TL, 90 phút)
    sc01 = _load_exam("SC-01")
    assert len(sc01["questions"]) == 22
    assert sc01["minutes"] == 90
    assert any(q.get("figure") for q in sc01["questions"])
    assert any(q.get("tables") for q in sc01["questions"])

    # SC-02: Tuyển sinh 10 Toán (5 bài lớn, barem >= 20 dòng, pointsByLevel)
    sc02 = _load_exam("SC-02")
    assert len(sc02["questions"]) == 5
    assert sc02.get("fullExam") is True
    assert sum(len(q.get("rubric") or []) for q in sc02["questions"]) >= 20
    assert any(row.get("pointsByLevel") for row in sc02["matrix"])

    # SC-03: Ngữ văn 9 (5 Đọc hiểu gắn cùng passageId = 4.0đ + 2 Viết = 6.0đ)
    sc03 = _load_exam("SC-03")
    assert len(sc03["questions"]) == 7
    p_ids_03 = {q.get("passageId") for q in sc03["questions"] if q.get("passageId")}
    assert len(p_ids_03) == 1
    doc_hi_pts = sum(float(q["points"]) for q in sc03["questions"] if q.get("passageId"))
    assert round(doc_hi_pts, 2) == 4.0

    # SC-04: Vật lí 12 CV 7991 (28 câu, bảng số liệu, ảnh PNG đồ thị, SVG trong docs)
    sc04 = _load_exam("SC-04")
    assert len(sc04["questions"]) == 28
    assert any("\\Omega" in q["stem"] for q in sc04["questions"])
    assert any(q.get("images") for q in sc04["questions"])
    assert "<svg" in sc04["docs"][0]["pages"][0]["text"]

    # SC-05: Hóa học 11 (24 câu, phương trình \ce{...}, bảng NTK)
    sc05 = _load_exam("SC-05")
    assert len(sc05["questions"]) == 24
    assert any("\\ce{" in q["stem"] for q in sc05["questions"])
    assert any(q.get("tables") for q in sc05["questions"])

    # SC-06: Tiếng Anh 12 (40 câu, <u> optionDocs, 3 passageId >= 15 câu, listening group + audio)
    sc06 = _load_exam("SC-06")
    assert len(sc06["questions"]) == 40
    underlined_qs = [
        q
        for q in sc06["questions"]
        if any(
            any(
                any(m.get("type") == "underline" for m in node.get("marks", []))
                for blk in doc.get("content", [])
                for node in blk.get("content", [])
            )
            for doc in q.get("optionDocs", [])
        )
    ]
    assert len(underlined_qs) >= 2
    p_ids_06 = [q.get("passageId") for q in sc06["questions"] if q.get("passageId")]
    assert len(set(p_ids_06)) == 3
    reading_cnt = sum(
        1 for q in sc06["questions"] if (q.get("passageId") or "").startswith("eng12-r")
    )
    assert reading_cnt >= 15
    listening_qs = [q for q in sc06["questions"] if q.get("audio")]
    assert len(listening_qs) == 5
    assert all(q.get("groupId") == "eng12-listening-1" for q in listening_qs)

    # SC-07: KHTN 9 liên môn Lý-Hóa-Sinh (26 câu)
    sc07 = _load_exam("SC-07")
    assert len(sc07["questions"]) == 26

    # SC-08: Lịch sử & Địa lí 9 (24 câu, 2 nhánh choiceGroup, data + dataLinked)
    sc08 = _load_exam("SC-08")
    assert len(sc08["questions"]) == 24
    assert sc08["data"]
    assert any(q.get("dataLinked") for q in sc08["questions"])
    assert len({q.get("choiceGroup") for q in sc08["questions"] if q.get("choiceGroup")}) == 2

    # SC-09: Tin học 12 (24 chung + 2 nhánh KHMT/THUD 4 câu = 28 hiệu lực, codeBlock, 0.2/0.4)
    sc09 = _load_exam("SC-09")
    assert len(sc09["questions"]) == 32
    code_qs = [
        q
        for q in sc09["questions"]
        if any(blk.get("type") == "codeBlock" for blk in q.get("richDoc", {}).get("content", []))
    ]
    assert len(code_qs) >= 4
    assert {round(float(q["points"]), 2) for q in sc09["questions"]} >= {0.2, 0.4}

    # SC-10: Tiểu học Toán lớp 5 (10 câu: 6 MCQ 4.0đ + 4 Tự luận 6.0đ)
    sc10 = _load_exam("SC-10")
    assert len(sc10["questions"]) == 10
    assert sum(1 for q in sc10["questions"] if q["type"] == "mcq") == 6
    assert sum(1 for q in sc10["questions"] if q["type"] == "essay") == 4


@pytest.mark.parametrize("code", EXAM_CODES)
def test_analytics_preflight_reverse_matrix_across_corpus(code: str) -> None:
    exam = _load_exam(code)

    analysis = exam_analytics.analyze_exam(exam)
    assert analysis["readinessScore"] >= 80
    assert analysis["totalQuestions"] == len(exam["questions"])
    issue_codes = {item["code"] for item in analysis["issues"]}
    assert not ({"bad_math", "duplicate_stem", "answer_streak"} & issue_codes)

    preflight = export_preflight.audit_export_preflight(exam)
    assert preflight["blockingIssues"] == []
    assert preflight["summary"]["blockingCount"] == 0
    assert preflight["summary"]["unapprovedCount"] == 0

    rev = exam_planning.reverse_matrix(exam)
    assert rev["pointConflicts"] == []
    assert rev["totalPoints"] == 10.0


def test_passage_variant_grouping_preserved() -> None:
    cases = (
        ("SC-03", "phan-1-doc-hieu", 1),
        ("SC-06", "sec-cloze", 1),
        ("SC-06", "sec-reading-1", 1),
        ("SC-06", "sec-reading-2", 1),
    )
    for code, section_id, expected_groups in cases:
        exam = _load_exam(code)
        movable = [
            q["id"]
            for q in exam["questions"]
            if q.get("sectionId") == section_id and not q.get("lockPosition")
        ]
        variant = local_documents.exam_variant(
            exam,
            {"questionIds": movable, "shuffleOptions": False, "offset": 1},
        )
        seen_closed: set[str] = set()
        current: str | None = None
        group_keys_seen: set[str] = set()
        for q in variant["questions"]:
            gk = q.get("passageId") or q.get("groupId")
            if gk:
                group_keys_seen.add(gk)
                assert gk not in seen_closed, f"{code}: nhóm ngữ liệu {gk} bị tách rời khi trộn"
            if gk != current and current is not None:
                seen_closed.add(current)
            current = gk
        assert len(group_keys_seen) >= expected_groups


@pytest.mark.parametrize("code", EXAM_CODES)
def test_spec_exports_and_student_redaction(code: str) -> None:
    exam = _load_exam(code)

    with pytest.raises(AIError) as forbidden:
        exam_spec_export.validate_and_normalize_answer_key(exam, teacher=False)
    assert forbidden.value.code == "teacher_only"
    assert forbidden.value.http_status == 403

    key_info = exam_spec_export.validate_and_normalize_answer_key(exam, teacher=True)
    assert key_info["audience"] == "teacher"
    assert key_info["total_questions"] == len(exam["questions"])
    assert len(key_info["objective_answers"]) + len(key_info["essay_rubrics"]) >= 1

    spec = exam_spec_export.build_matrix_and_specification(exam)
    assert spec["rows"]
    assert spec["specification_rows"]

    rubric_html = exam_spec_export.export_answer_key_rubric_html(exam, teacher=True)
    assert exam["title"] in rubric_html
    rubric_docx = exam_spec_export.export_answer_key_rubric_docx(exam, teacher=True)
    with zipfile.ZipFile(io.BytesIO(rubric_docx)) as zf:
        assert "word/document.xml" in zf.namelist()

    spec_html = exam_spec_export.export_matrix_specification_html(exam)
    assert exam["subject"] in spec_html
    spec_docx = exam_spec_export.export_matrix_specification_docx(exam)
    with zipfile.ZipFile(io.BytesIO(spec_docx)) as zf:
        assert "word/document.xml" in zf.namelist()

    student_html = exam_spec_export.export_student_exam_html(exam)
    assert exam["title"] in student_html
    stem_head = exam["questions"][0]["stem"].split("$")[0].strip()
    if len(stem_head) >= 8:
        assert stem_head in student_html
    for q in exam["questions"]:
        exp = (q.get("explanation") or "").strip()
        if len(exp) >= 35 and "$" not in exp:
            assert exp not in student_html


@pytest.mark.parametrize("code", EXAM_CODES)
def test_tnmaker_pack_across_corpus(code: str) -> None:
    exam = _load_exam(code)
    has_mcq = any(q["type"] == "mcq" for q in exam["questions"])
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        if not has_mcq:
            with pytest.raises(AIError) as exc:
                tnmaker_export.export_tnmaker_pack({"exam": exam, "examCode": code}, out_dir)
            assert exc.value.code == "missing_answer_key"
            return

        res = tnmaker_export.export_tnmaker_pack({"exam": exam, "examCode": code}, out_dir)
        zip_path = out_dir / res["filename"]
        assert zip_path.is_file()
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "DapAn.xlsx" in names
            qr_files = [n for n in names if n.lower().endswith(".png")]
            assert qr_files
            assert zf.read(qr_files[0]).startswith(b"\x89PNG\r\n\x1a\n")
            with zipfile.ZipFile(io.BytesIO(zf.read("DapAn.xlsx"))) as xlsx_zf:
                assert "xl/workbook.xml" in xlsx_zf.namelist()

        # Kiểm tra tương thích QR V1 (MCQ liên tiếp) / V2_indexed (MCQ xen kẽ sau khi P1-4 hợp nhất)
        mcqs = [(i + 1, q) for i, q in enumerate(exam["questions"]) if q["type"] == "mcq"]
        contiguous = [num for num, _ in mcqs] == list(range(1, len(mcqs) + 1))
        qr_format = res.get("qrFormat")
        if qr_format == "V2_indexed":
            assert not contiguous
            assert res["qrPayload"].startswith("KEY|V2|101:")
        elif not contiguous and "qrFormat" in res:
            pytest.fail(f"{code} có MCQ không liên tiếp nhưng qrFormat={qr_format}")
        else:
            assert res["qrPayload"].startswith("KEY|V1|101:")


@pytest.mark.parametrize("code", EXAM_CODES)
def test_word_export_inputs_sync(code: str) -> None:
    exam = _load_exam(code)
    formulas, figures = word_export.export_inputs(exam, TEACHER_META)
    assert isinstance(formulas, list)
    assert isinstance(figures, list)


def test_word_export_chrome_free_exams_and_underline() -> None:
    for code in ("SC-03", "SC-06"):
        exam = _load_exam(code)
        raw = word_export.export_docx(exam, TEACHER_META, None)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml_text = zf.read("word/document.xml").decode("utf-8")
            assert exam["questions"][0]["stem"][:25] in xml_text
            if code == "SC-06":
                assert "<w:u " in xml_text or "<w:u/>" in xml_text


@pytest.mark.parametrize("code", EXAM_CODES)
def test_word_export_all_corpus_exams_with_chrome(code: str) -> None:
    chrome = _find_chrome()
    if not chrome:
        pytest.skip("Không tìm thấy Chrome/Edge để dựng công thức và hình học sang DOCX.")
    exam = _load_exam(code)
    raw = word_export.export_docx(exam, TEACHER_META, chrome)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "word/document.xml" in zf.namelist()
        xml_text = zf.read("word/document.xml").decode("utf-8")
        if code == "SC-09":
            assert "Consolas" in xml_text
    if code == "SC-01":
        redacted = exam_spec_export.redact_exam_for_student(exam)
        student_docx = word_export.export_docx(redacted, False, chrome)
        with zipfile.ZipFile(io.BytesIO(student_docx)) as zf:
            student_xml = zf.read("word/document.xml").decode("utf-8")
            assert "HƯỚNG DẪN CHẤM" not in student_xml
            assert "BẢN GIÁO VIÊN" not in student_xml


def test_matrix_binary_fixtures_ooxml_and_pdf_integrity() -> None:
    # 1. merged-header .docx: kiểm tra w:gridSpan và w:vMerge thực trong OOXML
    merged_docx = CORPUS_DIR / "matrix-cv7991-merged-header.docx"
    with zipfile.ZipFile(merged_docx) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "w:gridSpan" in doc_xml
    assert "w:vMerge" in doc_xml
    assert "0,40" in doc_xml and "9,60" in doc_xml

    # 2. merged-formulas .xlsx: 2 sheet Ma tran & Dac ta, mergeCells, SUM có/không cached <v>
    merged_xlsx = CORPUS_DIR / "matrix-cv7991-merged-formulas.xlsx"
    with zipfile.ZipFile(merged_xlsx) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        sheet_names = [el.attrib.get("name") for el in wb.iter() if el.tag.endswith("}sheet")]
        assert sheet_names == ["Ma tran", "Dac ta"]
        s1_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "<mergeCells" in s1_xml
        assert "<f>SUM(E3:E7)</f><v>" in s1_xml
        assert "<f>SUM(I3:I7)</f></c>" in s1_xml
        sst_xml = zf.read("xl/sharedStrings.xml").decode("utf-8")
        for decimal_str in ("0,25", "0,40", "9,60"):
            assert decimal_str in sst_xml

    # 3. 2-page PDF tuyển sinh 10: PdfReader strict=True đọc đủ 2 trang và giữ y = ax² (a ≠ 0)
    pdf_path = CORPUS_DIR / "matrix-tuyensinh10-2pages.pdf"
    reader = PdfReader(io.BytesIO(pdf_path.read_bytes()), strict=True)
    assert len(reader.pages) == 2
    full_layout = "\n".join(
        page.extract_text(extraction_mode="layout") or "" for page in reader.pages
    )
    assert "y = ax² (a ≠ 0)" in full_layout
    assert "13 Câu" in full_layout


def test_matrix_parser_behavior_across_messy_fixtures() -> None:
    def fail_ai(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Không được gọi AI trong ca ma trận này")

    # (a) 2-table .docx: bỏ qua bảng quy ước điểm, đọc chính xác bảng ma trận 20 câu 10,00đ
    two_tbl = EDGE_DIR / "two-tables-legend-and-matrix.docx"
    parsed_2tbl = asyncio.run(
        matrix_import.read_matrix(
            {"name": two_tbl.name, "data": _file_data_url(two_tbl)},
            fail_ai,
        )
    )
    assert parsed_2tbl["method"] == "python_table"
    assert parsed_2tbl["count"] == 20
    assert len(parsed_2tbl["matrix"]) == 4

    # (b) spec-only .docx: luôn trả về mã lỗi spec_only_matrix không gọi AI
    spec_only = EDGE_DIR / "spec-only-no-counts.docx"
    with pytest.raises(AIError) as spec_exc:
        asyncio.run(
            matrix_import.read_matrix(
                {"name": spec_only.name, "data": _file_data_url(spec_only)},
                fail_ai,
            )
        )
    assert spec_exc.value.code == "spec_only_matrix"

    # (c) mismatched-sum .xlsx: fail sạch bằng invalid_matrix
    bad_sum = EDGE_DIR / "mismatched-sum.xlsx"
    with pytest.raises(AIError) as bad_exc:
        asyncio.run(
            matrix_import.read_matrix(
                {"name": bad_sum.name, "data": _file_data_url(bad_sum)},
                fail_ai,
            )
        )
    assert bad_exc.value.code == "invalid_matrix"

    # (d) merged-formulas .xlsx: công thức không cached/chứa SUM -> từ chối sạch với matrix_formula
    formulas_xlsx = CORPUS_DIR / "matrix-cv7991-merged-formulas.xlsx"
    with pytest.raises(AIError) as formula_exc:
        asyncio.run(
            matrix_import.read_matrix(
                {"name": formulas_xlsx.name, "data": _file_data_url(formulas_xlsx)},
                fail_ai,
            )
        )
    assert formula_exc.value.code == "matrix_formula"


def test_merged_docx_and_multipage_pdf_uv61_contract() -> None:
    def fail_ai(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Không được gọi AI khi kiểm tra không bật consent")

    merged_docx = CORPUS_DIR / "matrix-cv7991-merged-header.docx"
    try:
        res_docx = asyncio.run(
            matrix_import.read_matrix(
                {"name": merged_docx.name, "data": _file_data_url(merged_docx)},
                fail_ai,
            )
        )
    except AIError as exc:
        # Trên baseline trước Wave A: chỉ yêu cầu xác nhận AI, không nhận nhầm spec_only_matrix
        assert exc.code == "matrix_ai_consent"
    else:
        # Sau khi P1-2 hợp nhất: parse cục bộ 5 dòng với đúng điểm lẻ 0,40 / 9,60 và choiceGroup
        assert res_docx["method"] == "python_table"
        assert len(res_docx["matrix"]) == 5
        essays = [r for r in res_docx["matrix"] if r["type"] == "essay"]
        essay_pts = sorted(r.get("points", (r.get("pointsQ4") or 0) * 0.25) for r in essays)
        assert essay_pts == [0.4, 9.6]

    pdf_path = CORPUS_DIR / "matrix-tuyensinh10-2pages.pdf"
    pdf_bytes = pdf_path.read_bytes()
    pdf_res = pdf_matrix.read_pdf_matrix(pdf_bytes)
    if pdf_res is not None:
        # Sau khi P1-2 sửa read_pdf_matrix: đọc đủ 5 dòng, 13 câu và giữ biểu thức y = ax² (a ≠ 0)
        assert pdf_res["count"] == 13
        assert len(pdf_res["matrix"]) == 5
        joined_topics = " ".join(r["topic"] for r in pdf_res["matrix"])
        assert "y = ax²" in joined_topics and "a ≠ 0" in joined_topics
    else:
        # Trên baseline trước Wave A: từ chối sạch yêu cầu consent, không cắt cụt để đoán bừa
        with pytest.raises(AIError) as pdf_exc:
            asyncio.run(
                matrix_import.read_matrix(
                    {"name": pdf_path.name, "data": _file_data_url(pdf_path)},
                    fail_ai,
                )
            )
        assert pdf_exc.value.code == "matrix_ai_consent"


def test_matrix_40_question_capacity_sc06() -> None:
    sc06 = _load_exam("SC-06")
    payload = {"matrix": sc06["matrix"], "notes": "Ma trận Tiếng Anh 12 — 40 câu"}
    if matrix_import.MAX_MATRIX_QUESTIONS >= 40:
        checked = matrix_import.checked_matrix(payload)
        assert checked["count"] == 40
        slots = matrix_import.matrix_slots(checked["matrix"])
        assert len(slots) == 40
    else:
        with pytest.raises(AIError) as exc:
            matrix_import.checked_matrix(payload)
        assert exc.value.code == "invalid_matrix"
