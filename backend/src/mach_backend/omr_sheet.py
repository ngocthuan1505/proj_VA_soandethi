"""Xuất Phiếu trả lời trắc nghiệm A4 chuẩn Bộ GD&ĐT 2025 (HTML/PDF), 0 rò đáp án ở bản học sinh."""

from __future__ import annotations

import asyncio
import html
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import chrome_path

OMR_CSS = """
@page { size: A4; margin: 10mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 8px;
  background: #f3f4f6;
  color: #111827;
  font-family: "Times New Roman", Times, serif;
  font-size: 10.5pt;
  line-height: 1.25;
}
.omr-sheet {
  position: relative;
  width: 190mm;
  min-height: 277mm;
  margin: 0 auto;
  padding: 6mm 7mm;
  background: #ffffff;
  border: 1.2px solid #111827;
}
.omr-mark {
  position: absolute;
  width: 5mm;
  height: 5mm;
  background: #111827;
}
.omr-mark.tl { top: 2mm; left: 2mm; }
.omr-mark.tr { top: 2mm; right: 2mm; }
.omr-mark.bl { bottom: 2mm; left: 2mm; }
.omr-mark.br { bottom: 2mm; right: 2mm; }
.omr-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8mm;
  border-bottom: 1.5px solid #111827;
  padding-bottom: 4mm;
  margin-bottom: 4mm;
}
.omr-info {
  flex: 1 1 auto;
}
.omr-title {
  margin: 0 0 2mm;
  font-size: 14pt;
  font-weight: bold;
  text-transform: uppercase;
  text-align: center;
  letter-spacing: 0.4px;
}
.omr-subtitle {
  margin: 0 0 2.5mm;
  font-size: 10.5pt;
  text-align: center;
  color: #374151;
}
.teacher-badge {
  display: inline-block;
  margin: 0 auto 2mm;
  padding: 1.5px 8px;
  border: 1.2px solid #991b1b;
  color: #991b1b;
  font-weight: bold;
  font-size: 9.5pt;
  text-transform: uppercase;
}
.student-fields {
  margin-top: 2mm;
  font-size: 10pt;
}
.student-fields .field-row {
  margin: 1.8mm 0;
}
.omr-id-grids {
  display: flex;
  gap: 4mm;
  flex-shrink: 0;
}
.digit-grid-box {
  border: 1px solid #111827;
  padding: 2mm;
  text-align: center;
}
.digit-grid-box h3 {
  margin: 0 0 1.5mm;
  font-size: 8.5pt;
  text-transform: uppercase;
}
.digit-table {
  border-collapse: collapse;
  margin: 0 auto;
}
.digit-table th, .digit-table td {
  padding: 0.7mm 0.8mm;
  text-align: center;
}
.digit-table .write-cell {
  border: 1px solid #111827;
  width: 5.2mm;
  height: 5.5mm;
  font-weight: bold;
  font-size: 9.5pt;
}
.bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 4.6mm;
  height: 4.6mm;
  border-radius: 50%;
  border: 1px solid #111827;
  font-size: 7.5pt;
  font-weight: 600;
  color: #111827;
  background: #ffffff;
}
.bubble.filled {
  background: #111827;
  color: #ffffff;
  border-color: #111827;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.omr-section {
  margin-top: 3.5mm;
  break-inside: avoid;
}
.omr-section-title {
  margin: 0 0 2mm;
  padding: 1mm 2.5mm;
  background: #f3f4f6;
  border-left: 3px solid #111827;
  font-size: 10pt;
  font-weight: bold;
  text-transform: uppercase;
}
.mcq-columns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3mm;
}
.mcq-col {
  border: 1px solid #374151;
  padding: 1.5mm 2mm;
}
.mcq-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7mm 0;
  border-bottom: 0.5px dotted #d1d5db;
}
.mcq-row:last-child { border-bottom: none; }
.mcq-num {
  font-weight: bold;
  font-size: 9pt;
  min-width: 6mm;
}
.mcq-bubbles {
  display: flex;
  gap: 1.6mm;
}
.tf-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3mm;
}
.tf-card {
  border: 1px solid #374151;
  padding: 1.5mm 2mm;
}
.tf-card-head {
  font-weight: bold;
  font-size: 9.5pt;
  text-align: center;
  border-bottom: 1px solid #9ca3af;
  padding-bottom: 1mm;
  margin-bottom: 1mm;
}
.tf-table {
  width: 100%;
  border-collapse: collapse;
}
.tf-table th, .tf-table td {
  text-align: center;
  padding: 0.7mm 0.5mm;
  font-size: 8.5pt;
}
.short-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 3mm;
}
.short-card {
  border: 1px solid #374151;
  padding: 1.5mm 2mm;
}
.short-card-head {
  font-weight: bold;
  font-size: 9.5pt;
  text-align: center;
  margin-bottom: 1.2mm;
}
.short-table {
  width: 100%;
  border-collapse: collapse;
}
.short-table td {
  text-align: center;
  padding: 0.5mm 0.4mm;
}
.short-table .write-cell {
  border: 1px solid #111827;
  height: 5.5mm;
  font-weight: bold;
  font-size: 9.5pt;
}
.omr-empty-note {
  font-size: 9pt;
  color: #6b7280;
  font-style: italic;
  margin: 1mm 0;
}
@media print {
  body { background: #ffffff; padding: 0; }
  .omr-sheet {
    width: auto;
    min-height: auto;
    margin: 0;
    border-width: 1px;
  }
}
""".strip()

SHORT_ROW_SYMBOLS: tuple[str, ...] = (
    "-",
    ",",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
)


class OmrSheetRequest(BaseModel):
    """Payload yêu cầu xuất Phiếu trả lời trắc nghiệm A4 chuẩn Bộ GD&ĐT 2025."""

    model_config = ConfigDict(extra="forbid")

    exam: dict[str, Any]
    teacher: bool = False
    variantCode: str = Field(default="101", max_length=12)
    format: Literal["html", "pdf"] = "html"

    @field_validator("exam")
    @classmethod
    def check_exam_questions(cls, value: dict[str, Any]) -> dict[str, Any]:
        questions = value.get("questions")
        if not isinstance(questions, list):
            raise ValueError("Đề thi cần có danh sách câu hỏi (questions).")
        for idx, item in enumerate(questions, 1):
            if not isinstance(item, dict):
                raise ValueError(f"Câu {idx} trong đề thi phải là đối tượng JSON.")
        return value


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _bubble(label: str, *, filled: bool = False) -> str:
    cls = "bubble filled" if filled else "bubble"
    extra = ' data-filled="true"' if filled else ""
    return f'<span class="{cls}"{extra}>{_esc(label)}</span>'


def _extract_mcq_answer_index(question: dict[str, Any]) -> int | None:
    if question.get("answerKnown") is False:
        return None
    ans = question.get("answer")
    if isinstance(ans, bool):
        return None
    if isinstance(ans, int) and 0 <= ans < 4:
        return ans
    if isinstance(ans, str):
        clean = ans.strip().upper()
        if clean in {"A", "B", "C", "D"}:
            return ord(clean) - 65
    return None


def _extract_truefalse_values(question: dict[str, Any]) -> list[bool | None]:
    if question.get("answerKnown") is False:
        return [None, None, None, None]
    truth = question.get("truthValues")
    if isinstance(truth, list) and len(truth) == 4 and all(type(v) is bool for v in truth):
        return [bool(v) for v in truth]
    ans = question.get("answer")
    if isinstance(ans, list) and len(ans) == 4 and all(type(v) is bool for v in ans):
        return [bool(v) for v in ans]
    if isinstance(ans, str):
        compact = ans.strip().upper()
        if len(compact) == 4:
            parsed: list[bool | None] = []
            for ch in compact:
                if ch in {"1", "T", "Đ", "D"}:
                    parsed.append(True)
                elif ch in {"0", "F", "S"}:
                    parsed.append(False)
                else:
                    parsed.append(None)
            return parsed
    return [None, None, None, None]


def _extract_short_chars(question: dict[str, Any]) -> list[str]:
    if question.get("answerKnown") is False:
        return ["", "", "", ""]
    raw = question.get("answerText")
    if not isinstance(raw, str) or not raw.strip():
        ans = question.get("answer")
        raw = str(ans) if isinstance(ans, (str, int, float)) and not isinstance(ans, bool) else ""
    cleaned = raw.strip().replace(" ", "").replace(".", ",")
    valid_chars = [ch for ch in cleaned if ch in SHORT_ROW_SYMBOLS][:4]
    while len(valid_chars) < 4:
        valid_chars.append("")
    return valid_chars


def _render_digit_grid(title: str, cols: int, filled_digits: list[str] | None = None) -> str:
    digits = filled_digits or [""] * cols
    write_cells = "".join(
        f'<td class="write-cell">{_esc(digits[c]) if c < len(digits) else ""}</td>'
        for c in range(cols)
    )
    rows_html: list[str] = [f"<tr>{write_cells}</tr>"]
    for d in range(10):
        d_str = str(d)
        cells = "".join(
            f"<td>{_bubble(d_str, filled=(c < len(digits) and digits[c] == d_str))}</td>"
            for c in range(cols)
        )
        rows_html.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="digit-grid-box">'
        f"<h3>{_esc(title)}</h3>"
        f'<table class="digit-table"><tbody>{"".join(rows_html)}</tbody></table>'
        f"</div>"
    )


def _render_part1_mcq(questions: list[dict[str, Any]], *, teacher: bool) -> str:
    if not questions:
        return (
            '<section class="omr-section omr-part-1">'
            '<h2 class="omr-section-title">'
            "Phần I. Câu trắc nghiệm nhiều phương án lựa chọn (0 câu)</h2>"
            '<p class="omr-empty-note">Đề thi không có câu hỏi Phần I.</p>'
            "</section>"
        )
    col_count = min(4, max(1, (len(questions) + 9) // 10))
    per_col = max(1, (len(questions) + col_count - 1) // col_count)
    cols_html: list[str] = []
    for col_idx in range(col_count):
        start = col_idx * per_col
        chunk = questions[start : start + per_col]
        if not chunk:
            continue
        rows: list[str] = []
        for offset, q in enumerate(chunk):
            q_num = start + offset + 1
            correct_idx = _extract_mcq_answer_index(q) if teacher else None
            bubbles = "".join(
                _bubble(letter, filled=(correct_idx == opt_idx))
                for opt_idx, letter in enumerate(("A", "B", "C", "D"))
            )
            rows.append(
                f'<div class="mcq-row" data-q="{q_num}">'
                f'<span class="mcq-num">{q_num}.</span>'
                f'<span class="mcq-bubbles">{bubbles}</span>'
                f"</div>"
            )
        cols_html.append(f'<div class="mcq-col">{"".join(rows)}</div>')
    return (
        '<section class="omr-section omr-part-1">'
        '<h2 class="omr-section-title">'
        f"Phần I. Câu trắc nghiệm nhiều phương án lựa chọn ({len(questions)} câu)</h2>"
        f'<div class="mcq-columns">{"".join(cols_html)}</div>'
        "</section>"
    )


def _render_part2_truefalse(questions: list[dict[str, Any]], *, teacher: bool) -> str:
    if not questions:
        return (
            '<section class="omr-section omr-part-2">'
            '<h2 class="omr-section-title">Phần II. Câu trắc nghiệm đúng sai (0 câu)</h2>'
            '<p class="omr-empty-note">Đề thi không có câu hỏi Phần II.</p>'
            "</section>"
        )
    cards: list[str] = []
    for idx, q in enumerate(questions, 1):
        truths = _extract_truefalse_values(q) if teacher else [None, None, None, None]
        rows: list[str] = []
        for s_idx, letter in enumerate(("a", "b", "c", "d")):
            val = truths[s_idx]
            rows.append(
                f"<tr>"
                f"<td><strong>{letter})</strong></td>"
                f"<td>{_bubble('Đ', filled=(val is True))}</td>"
                f"<td>{_bubble('S', filled=(val is False))}</td>"
                f"</tr>"
            )
        cards.append(
            f'<div class="tf-card" data-tf-q="{idx}">'
            f'<div class="tf-card-head">Câu {idx}</div>'
            f'<table class="tf-table">'
            f"<thead><tr><th>Ý</th><th>Đúng</th><th>Sai</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>"
            f"</div>"
        )
    return (
        '<section class="omr-section omr-part-2">'
        '<h2 class="omr-section-title">'
        f"Phần II. Câu trắc nghiệm đúng sai ({len(questions)} câu)</h2>"
        f'<div class="tf-grid">{"".join(cards)}</div>'
        "</section>"
    )


def _render_part3_short(questions: list[dict[str, Any]], *, teacher: bool) -> str:
    if not questions:
        return (
            '<section class="omr-section omr-part-3">'
            '<h2 class="omr-section-title">Phần III. Câu trắc nghiệm trả lời ngắn (0 câu)</h2>'
            '<p class="omr-empty-note">Đề thi không có câu hỏi Phần III.</p>'
            "</section>"
        )
    cards: list[str] = []
    for idx, q in enumerate(questions, 1):
        chars = _extract_short_chars(q) if teacher else ["", "", "", ""]
        write_row = "".join(f'<td class="write-cell">{_esc(ch)}</td>' for ch in chars)
        body_rows = [f"<tr>{write_row}</tr>"]
        for sym in SHORT_ROW_SYMBOLS:
            cells = "".join(
                f"<td>{_bubble(sym, filled=(teacher and chars[c] == sym))}</td>" for c in range(4)
            )
            body_rows.append(f"<tr>{cells}</tr>")
        cards.append(
            f'<div class="short-card" data-short-q="{idx}">'
            f'<div class="short-card-head">Câu {idx}</div>'
            f'<table class="short-table"><tbody>{"".join(body_rows)}</tbody></table>'
            f"</div>"
        )
    return (
        '<section class="omr-section omr-part-3">'
        '<h2 class="omr-section-title">'
        f"Phần III. Câu trắc nghiệm trả lời ngắn ({len(questions)} câu)</h2>"
        f'<div class="short-grid">{"".join(cards)}</div>'
        "</section>"
    )


def classify_omr_questions(
    exam: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    mcq: list[dict[str, Any]] = []
    truefalse: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    essay_count = 0

    for q in exam.get("questions") or []:
        if not isinstance(q, dict):
            continue
        qtype = str(q.get("type") or "mcq").strip().lower()
        if qtype in {"mcq", "multiple_choice"}:
            mcq.append(q)
        elif qtype in {"truefalse", "true_false"}:
            truefalse.append(q)
        elif qtype in {"short", "short_answer"}:
            short.append(q)
        elif qtype == "essay":
            essay_count += 1
        else:
            mcq.append(q)

    counts = {
        "mcq": len(mcq),
        "truefalse": len(truefalse),
        "short": len(short),
        "essay": essay_count,
        "total": len(mcq) + len(truefalse) + len(short) + essay_count,
    }
    return mcq, truefalse, short, counts


def render_omr_sheet_html(
    exam: dict[str, Any],
    *,
    teacher: bool = False,
    variant_code: str = "101",
) -> tuple[str, dict[str, int]]:
    """Dựng HTML A4 Phiếu OMR chuẩn Bộ GD&ĐT 2025; tuyệt đối 0 rò đáp án khi teacher=False."""
    mcq, truefalse, short, counts = classify_omr_questions(exam)
    title = _esc(exam.get("title") or "Đề kiểm tra")
    subject = _esc(exam.get("subject") or "")
    grade = _esc(exam.get("grade") or "")
    safe_variant = _esc(variant_code.strip() or "101")
    meta_parts = [
        p for p in (subject, f"Lớp {grade}" if grade else "", f"Mã đề {safe_variant}") if p
    ]
    meta_line = " · ".join(meta_parts)

    variant_digits_raw = [ch for ch in str(variant_code or "") if ch.isdigit()][-3:]
    while len(variant_digits_raw) < 3:
        variant_digits_raw.insert(0, "0")
    variant_grid_digits = variant_digits_raw if teacher else ["", "", ""]

    badge_html = (
        '<div style="text-align:center">'
        '<span class="teacher-badge">Bản đáp án giáo viên · Đã tô sẵn đáp án đúng</span>'
        "</div>"
        if teacher
        else ""
    )

    sbd_grid = _render_digit_grid("Số báo danh", 6, filled_digits=None)
    code_grid = _render_digit_grid("Mã đề thi", 3, filled_digits=variant_grid_digits)

    part1_html = _render_part1_mcq(mcq, teacher=teacher)
    part2_html = _render_part2_truefalse(truefalse, teacher=teacher)
    part3_html = _render_part3_short(short, teacher=teacher)

    dots_long = "." * 72
    dots_mid = "." * 30
    dots_short = "." * 24
    doc_html = (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        f"<title>Phiếu trả lời trắc nghiệm · {title}</title>"
        f"<style>{OMR_CSS}</style></head><body>"
        '<main class="omr-sheet">'
        '<span class="omr-mark tl" aria-hidden="true"></span>'
        '<span class="omr-mark tr" aria-hidden="true"></span>'
        '<span class="omr-mark bl" aria-hidden="true"></span>'
        '<span class="omr-mark br" aria-hidden="true"></span>'
        '<header class="omr-header">'
        '<div class="omr-info">'
        '<h1 class="omr-title">Phiếu trả lời trắc nghiệm</h1>'
        f'<p class="omr-subtitle"><strong>{title}</strong>'
        + (f"<br>{meta_line}" if meta_line else "")
        + "</p>"
        f"{badge_html}"
        '<div class="student-fields">'
        f'<div class="field-row">Họ và tên thí sinh: {dots_long}</div>'
        f'<div class="field-row">Lớp: {dots_mid} &nbsp;&nbsp; Phòng thi: {dots_mid}</div>'
        f'<div class="field-row">Ngày thi: ......./......./20..... &nbsp;&nbsp; '
        f"Chữ ký giám thị: {dots_short}</div>"
        "</div>"
        "</div>"
        f'<div class="omr-id-grids">{sbd_grid}{code_grid}</div>'
        "</header>"
        f"{part1_html}"
        f"{part2_html}"
        f"{part3_html}"
        "</main></body></html>"
    )
    return doc_html, counts


def _render_html_to_pdf(html_content: str, target_pdf: Path) -> None:
    chrome = chrome_path()
    if not chrome:
        raise AIError(
            "pdf_unavailable",
            "Cần Chrome/Edge để xuất PDF phiếu OMR. Có thể xuất bản HTML rồi chọn In A4.",
        )
    with tempfile.TemporaryDirectory(prefix="omr-pdf-") as temp:
        source = Path(temp) / "omr.html"
        source.write_text(html_content, encoding="utf-8")
        base_args = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--host-resolver-rules=MAP * ~NOTFOUND",
            "--no-proxy-server",
            "--no-pdf-header-footer",
            "--user-data-dir=" + str(Path(temp) / "profile"),
            "--print-to-pdf=" + str(target_pdf.resolve()),
            "--virtual-time-budget=3000",
            source.resolve().as_uri(),
        ]
        try:
            try:
                subprocess.run(
                    base_args,
                    check=True,
                    timeout=45,
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.SubprocessError:
                if os.name == "nt":
                    raise
                retry_args = [
                    chrome,
                    "--headless",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    *base_args[2:],
                ]
                subprocess.run(
                    retry_args,
                    check=True,
                    timeout=45,
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except (OSError, subprocess.SubprocessError):
            target_pdf.unlink(missing_ok=True)
            raise AIError(
                "export_failed",
                "Chưa tạo được PDF phiếu OMR. Hãy thử lại hoặc chọn định dạng HTML.",
            ) from None
    if not target_pdf.is_file() or not target_pdf.read_bytes().startswith(b"%PDF-"):
        target_pdf.unlink(missing_ok=True)
        raise AIError("export_failed", "Chưa tạo được PDF phiếu OMR hợp lệ.")


def export_omr_sheet(
    payload: OmrSheetRequest,
    exports_dir: Path,
) -> dict[str, Any]:
    """Xuất tệp HTML hoặc PDF phiếu OMR vào thư mục exports và trả metadata + HTML."""
    rendered_html, counts = render_omr_sheet_html(
        payload.exam,
        teacher=payload.teacher,
        variant_code=payload.variantCode,
    )
    exports_dir.mkdir(parents=True, exist_ok=True)
    name = f"Phieu_OMR_{uuid4()}.{payload.format}"
    target = exports_dir / name
    if payload.format == "html":
        target.write_text(rendered_html, encoding="utf-8")
    else:
        _render_html_to_pdf(rendered_html, target)
    return {
        "name": name,
        "downloadUrl": f"/api/exports/{name}",
        "html": rendered_html,
        "questionCounts": counts,
    }


def register_omr_sheet_routes(
    app: FastAPI,
    exports_dir: Path,
    export_slot: asyncio.Semaphore,
) -> None:
    """Đăng ký tuyến `POST /api/exports/omr-sheet` trên FastAPI."""

    @app.post("/api/exports/omr-sheet")
    async def create_omr_sheet(payload: OmrSheetRequest) -> dict[str, Any]:
        async with export_slot:
            return await asyncio.to_thread(export_omr_sheet, payload, exports_dir)
