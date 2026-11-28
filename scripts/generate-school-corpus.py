"""Sinh bộ đề kiểm tra phổ thông K-12 Việt Nam (SC-01..SC-10) và các tệp ma trận hỗn hợp."""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import re
import struct
import unicodedata
import uuid
import zipfile
import zlib
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from docx import Document
from docx.oxml.ns import qn
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "fixtures" / "school-corpus"
FIXED_TIMESTAMP_MS = 1795500000000
FIXED_DT = dt.datetime(2026, 11, 25, 0, 0, 0, tzinfo=dt.UTC)
FIXED_ZIP_DT = (2026, 11, 25, 0, 0, 0)

_JOIN_LINES = {
    "doc",
    "blockquote",
    "listItem",
    "bulletList",
    "orderedList",
    "table",
    "tableCell",
    "tableHeader",
}
_VN_TOKEN_RE = re.compile(r"[0-9a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+")


def det_uuid(key: str) -> str:
    """Tạo UUID tất định theo khóa ngữ nghĩa để giữ nguyên qua mỗi lần chạy."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"soan-de-thi/school-corpus/{key}"))


def project_rich(node: dict[str, Any]) -> str:
    """Chiếu TipTap richDoc sang văn bản thuần giống hệt mach_backend.rich_patch.project."""
    kind = node.get("type")
    if kind == "hardBreak":
        return "\n"
    if kind == "text":
        text = node.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError(f"Nút text trong richDoc không được rỗng: {node!r}")
        return text
    if kind == "mathInline":
        attrs = node.get("attrs") or {}
        latex = attrs.get("latex", "")
        if not isinstance(latex, str) or not latex:
            raise ValueError(f"Nút mathInline thiếu latex: {node!r}")
        marker = "$$" if attrs.get("display") else "$"
        return f"{marker}{latex}{marker}"
    children = node.get("content", [])
    sep = " | " if kind == "tableRow" else ("\n" if kind in _JOIN_LINES else "")
    return sep.join(project_rich(child) for child in children)


def p_node(*parts: str | tuple[Any, ...]) -> dict[str, Any]:
    """Tạo một đoạn paragraph richDoc từ chuỗi thường, đánh dấu mark, công thức hoặc ngắt dòng."""
    content: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, str):
            if part:
                content.append({"type": "text", "text": part})
        elif part[0] == "math":
            content.append(
                {
                    "type": "mathInline",
                    "attrs": {"latex": part[1], "display": bool(part[2]) if len(part) > 2 else False},
                }
            )
        elif part[0] == "br":
            content.append({"type": "hardBreak"})
        else:
            mark_type, text = part[0], part[1]
            if text:
                content.append({"type": "text", "text": text, "marks": [{"type": mark_type}]})
    return {"type": "paragraph", "content": content}


def doc_from(*blocks: dict[str, Any]) -> dict[str, Any]:
    return {"type": "doc", "content": list(blocks)}


def code_doc(intro: str, code: str, outro: str = "") -> tuple[str, dict[str, Any]]:
    """Tạo richDoc chứa khối codeBlock Python/SQL kèm văn bản chiếu đồng bộ."""
    blocks: list[dict[str, Any]] = [
        p_node(intro),
        {"type": "codeBlock", "content": [{"type": "text", "text": code}]},
    ]
    if outro:
        blocks.append(p_node(outro))
    doc = doc_from(*blocks)
    return project_rich(doc), doc


def underline_option(prefix: str, underlined: str, suffix: str) -> tuple[str, dict[str, Any]]:
    """Tạo phương án phát âm tiếng Anh có chữ gạch chân qua optionDocs mark underline."""
    parts: list[str | tuple[Any, ...]] = []
    if prefix:
        parts.append(prefix)
    parts.append(("underline", underlined))
    if suffix:
        parts.append(suffix)
    doc = doc_from(p_node(*parts))
    return project_rich(doc), doc


def make_png_chart(
    points: list[tuple[float, float]],
    *,
    width: int = 360,
    height: int = 200,
    line_rgb: tuple[int, int, int] = (15, 118, 110),
) -> str:
    """Vẽ biểu đồ PNG thuần Python (zlib + struct) cho dữ liệu thí nghiệm Vật lí."""
    pixels = bytearray([255, 255, 255] * (width * height))

    def set_px(x: int, y: int, rgb: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 3
            pixels[idx : idx + 3] = bytes(rgb)

    def draw_line(x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int], thick: int = 1) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            for oy in range(-thick + 1, thick):
                for ox in range(-thick + 1, thick):
                    set_px(x0 + ox, y0 + oy, rgb)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    pad_l, pad_r, pad_t, pad_b = 36, 20, 20, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    # Lưới mờ và hai trục tọa độ
    for gx in range(1, 5):
        xx = pad_l + (plot_w * gx) // 4
        draw_line(xx, pad_t, xx, height - pad_b, (226, 232, 240))
    for gy in range(1, 4):
        yy = pad_t + (plot_h * gy) // 4
        draw_line(pad_l, yy, width - pad_r, yy, (226, 232, 240))
    draw_line(pad_l, pad_t, pad_l, height - pad_b, (51, 65, 85), 1)
    draw_line(pad_l, height - pad_b, width - pad_r, height - pad_b, (51, 65, 85), 1)

    max_x = max((p[0] for p in points), default=1.0) or 1.0
    max_y = max((p[1] for p in points), default=1.0) or 1.0
    mapped = [
        (
            pad_l + int(round((px / max_x) * plot_w)),
            height - pad_b - int(round((py / max_y) * plot_h)),
        )
        for px, py in points
    ]
    for (x0, y0), (x1, y1) in zip(mapped, mapped[1:], strict=False):
        draw_line(x0, y0, x1, y1, line_rgb, 2)
    for cx, cy in mapped:
        for oy in range(-3, 4):
            for ox in range(-3, 4):
                if ox * ox + oy * oy <= 9:
                    set_px(cx + ox, cy + oy, (180, 83, 9))

    raw_rows = b"".join(
        b"\x00" + bytes(pixels[y * width * 3 : (y + 1) * width * 3]) for y in range(height)
    )

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw_rows, level=9))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _block_ids(key: str) -> dict[str, str]:
    return {
        field: det_uuid(f"{key}/block/{field}")
        for field in ("stem", "options", "answer", "explanation", "rubric", "figure")
    }


def mcq(
    key: str,
    topic: str,
    lesson: str,
    competency: str,
    level: int,
    points: float,
    stem: str,
    options: list[str],
    answer: int,
    explanation: str,
    *,
    doc_id: str | None = None,
    location: str = "Tài liệu biên soạn",
    rich_doc: dict[str, Any] | None = None,
    option_docs: list[dict[str, Any] | None] | None = None,
    tables: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
    figure: dict[str, Any] | None = None,
    section_id: str | None = None,
    passage_id: str | None = None,
    passage_title: str | None = None,
    passage_text: str | None = None,
    group_id: str | None = None,
    audio: dict[str, Any] | None = None,
    choice_group: str | None = None,
    lock_position: bool = False,
    data_linked: bool = False,
    rule: str | None = None,
) -> dict[str, Any]:
    if rich_doc is not None:
        stem = project_rich(rich_doc)
    item: dict[str, Any] = {
        "id": det_uuid(key),
        "v": 1,
        "type": "mcq",
        "topic": topic,
        "lesson": lesson,
        "competency": competency,
        "level": level,
        "points": points,
        "stem": stem,
        "options": list(options),
        "answer": answer,
        "answerKnown": True,
        "explanation": explanation,
        "approved": True,
        "approval": {"version": 1, "status": "approved", "method": "Giáo viên duyệt thủ công"},
        "blockIds": _block_ids(key),
    }
    if doc_id:
        item["source"] = {"docId": doc_id, "page": 1, "location": location}
    if rich_doc is not None:
        item["richDoc"] = rich_doc
    if option_docs is not None:
        item["optionDocs"] = option_docs
    if tables:
        item["tables"] = tables
    if images:
        item["images"] = images
    if figure:
        item["figure"] = figure
    if section_id:
        item["sectionId"] = section_id
    if passage_id:
        item["passageId"] = passage_id
    if passage_title:
        item["passageTitle"] = passage_title
    if passage_text:
        item["passageText"] = passage_text
    if group_id:
        item["groupId"] = group_id
    if audio:
        item["audio"] = audio
    if choice_group:
        item["choiceGroup"] = choice_group
    if lock_position:
        item["lockPosition"] = True
    if data_linked:
        item["dataLinked"] = True
    if rule:
        item["rule"] = rule
    return item


def tf(
    key: str,
    topic: str,
    lesson: str,
    competency: str,
    level: int,
    points: float,
    stem: str,
    options: list[str],
    truth_values: list[bool],
    explanation: str,
    *,
    doc_id: str | None = None,
    location: str = "Tài liệu biên soạn",
    rich_doc: dict[str, Any] | None = None,
    tables: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
    figure: dict[str, Any] | None = None,
    section_id: str | None = None,
    choice_group: str | None = None,
) -> dict[str, Any]:
    if rich_doc is not None:
        stem = project_rich(rich_doc)
    item: dict[str, Any] = {
        "id": det_uuid(key),
        "v": 1,
        "type": "truefalse",
        "topic": topic,
        "lesson": lesson,
        "competency": competency,
        "level": level,
        "points": points,
        "stem": stem,
        "options": list(options),
        "truthValues": list(truth_values),
        "answer": None,
        "answerKnown": True,
        "explanation": explanation,
        "approved": True,
        "approval": {"version": 1, "status": "approved", "method": "Giáo viên duyệt thủ công"},
        "blockIds": _block_ids(key),
    }
    if doc_id:
        item["source"] = {"docId": doc_id, "page": 1, "location": location}
    if rich_doc is not None:
        item["richDoc"] = rich_doc
    if tables:
        item["tables"] = tables
    if images:
        item["images"] = images
    if figure:
        item["figure"] = figure
    if section_id:
        item["sectionId"] = section_id
    if choice_group:
        item["choiceGroup"] = choice_group
    return item


def short_q(
    key: str,
    topic: str,
    lesson: str,
    competency: str,
    level: int,
    points: float,
    stem: str,
    answer_text: str,
    explanation: str,
    *,
    doc_id: str | None = None,
    location: str = "Tài liệu biên soạn",
    rich_doc: dict[str, Any] | None = None,
    tables: list[dict[str, Any]] | None = None,
    images: list[dict[str, Any]] | None = None,
    figure: dict[str, Any] | None = None,
    section_id: str | None = None,
    choice_group: str | None = None,
    data_linked: bool = False,
) -> dict[str, Any]:
    if rich_doc is not None:
        stem = project_rich(rich_doc)
    item: dict[str, Any] = {
        "id": det_uuid(key),
        "v": 1,
        "type": "short",
        "topic": topic,
        "lesson": lesson,
        "competency": competency,
        "level": level,
        "points": points,
        "stem": stem,
        "options": [],
        "answer": None,
        "answerText": answer_text,
        "answerKnown": True,
        "explanation": explanation,
        "approved": True,
        "approval": {"version": 1, "status": "approved", "method": "Giáo viên duyệt thủ công"},
        "blockIds": _block_ids(key),
    }
    if doc_id:
        item["source"] = {"docId": doc_id, "page": 1, "location": location}
    if rich_doc is not None:
        item["richDoc"] = rich_doc
    if tables:
        item["tables"] = tables
    if images:
        item["images"] = images
    if figure:
        item["figure"] = figure
    if section_id:
        item["sectionId"] = section_id
    if choice_group:
        item["choiceGroup"] = choice_group
    if data_linked:
        item["dataLinked"] = True
    return item


def essay(
    key: str,
    topic: str,
    lesson: str,
    competency: str,
    level: int,
    points: float,
    stem: str,
    explanation: str,
    rubric: list[tuple[str, float]],
    *,
    doc_id: str | None = None,
    location: str = "Tài liệu biên soạn",
    rich_doc: dict[str, Any] | None = None,
    explanation_doc: dict[str, Any] | None = None,
    tables: list[dict[str, Any]] | None = None,
    figure: dict[str, Any] | None = None,
    section_id: str | None = None,
    passage_id: str | None = None,
    passage_title: str | None = None,
    passage_text: str | None = None,
    choice_group: str | None = None,
    lock_position: bool = False,
    data_linked: bool = False,
) -> dict[str, Any]:
    if rich_doc is not None:
        stem = project_rich(rich_doc)
    if explanation_doc is not None:
        explanation = project_rich(explanation_doc)
    rubric_sum = sum(round(p * 100) for _, p in rubric)
    if rubric_sum != round(points * 100):
        raise ValueError(f"{key}: Tổng barem {rubric_sum} != điểm câu {round(points * 100)}")
    item: dict[str, Any] = {
        "id": det_uuid(key),
        "v": 1,
        "type": "essay",
        "topic": topic,
        "lesson": lesson,
        "competency": competency,
        "level": level,
        "points": points,
        "stem": stem,
        "options": [],
        "answer": None,
        "answerKnown": True,
        "explanation": explanation,
        "rubric": [{"text": text, "points": pts} for text, pts in rubric],
        "approved": True,
        "approval": {"version": 1, "status": "approved", "method": "Giáo viên duyệt thủ công"},
        "blockIds": _block_ids(key),
    }
    if doc_id:
        item["source"] = {"docId": doc_id, "page": 1, "location": location}
    if rich_doc is not None:
        item["richDoc"] = rich_doc
    if explanation_doc is not None:
        item["explanationDoc"] = explanation_doc
    if tables:
        item["tables"] = tables
    if figure:
        item["figure"] = figure
    if section_id:
        item["sectionId"] = section_id
    if passage_id:
        item["passageId"] = passage_id
    if passage_title:
        item["passageTitle"] = passage_title
    if passage_text:
        item["passageText"] = passage_text
    if choice_group:
        item["choiceGroup"] = choice_group
    if lock_position:
        item["lockPosition"] = True
    if data_linked:
        item["dataLinked"] = True
    return item


def build_matrix_rows(
    questions: list[dict[str, Any]], *, use_points_by_level: bool = False
) -> list[dict[str, Any]]:
    """Tổng hợp bảng matrix từ danh sách câu hỏi và bảo đảm chuẩn schema."""
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for q in questions:
        grp = (q.get("choiceGroup") or "").strip()
        key = (q["topic"].strip().casefold(), q["type"], grp.casefold())
        if key not in groups:
            groups[key] = {
                "topic": q["topic"].strip(),
                "type": q["type"],
                "targets": [0, 0, 0, 0],
                "level_pts": [None, None, None, None],
                "pts_set": set(),
                "choiceGroup": grp,
            }
        bucket = groups[key]
        lvl = int(q["level"])
        bucket["targets"][lvl] += 1
        pts = round(float(q["points"]), 2)
        bucket["pts_set"].add(pts)
        bucket["level_pts"][lvl] = pts

    rows: list[dict[str, Any]] = []
    for bucket in groups.values():
        row: dict[str, Any] = {
            "topic": bucket["topic"],
            "type": bucket["type"],
            "targets": bucket["targets"],
        }
        if bucket["choiceGroup"]:
            row["choiceGroup"] = bucket["choiceGroup"]
        if use_points_by_level or len(bucket["pts_set"]) > 1:
            row["pointsByLevel"] = bucket["level_pts"]
        else:
            row["points"] = next(iter(bucket["pts_set"]))
        rows.append(row)
    return rows


def build_exam(
    code: str,
    *,
    title: str,
    school: str,
    department: str,
    subject: str,
    grade: str,
    minutes: int,
    instructions: str,
    questions: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    data: list[dict[str, Any]] | None = None,
    quote: dict[str, Any] | None = None,
    full_exam: bool = False,
    marking_guidance: str = "",
    mcq_columns: int = 2,
    use_points_by_level: bool = False,
) -> dict[str, Any]:
    exam: dict[str, Any] = {
        "id": det_uuid(f"{code}/exam"),
        "title": title,
        "school": school,
        "department": department,
        "subject": subject,
        "grade": grade,
        "minutes": minutes,
        "workflowStatus": "reviewed",
        "revision": 1,
        "updated": FIXED_TIMESTAMP_MS,
        "sample": False,
        "fullExam": full_exam,
        "instructions": instructions,
        "layout": {
            "font": "Times New Roman",
            "fontSize": 14,
            "lineHeight": 1.4,
            "mcqColumns": mcq_columns,
        },
        "blockIds": {
            "heading": det_uuid(f"{code}/heading"),
            "general": det_uuid(f"{code}/general"),
            "marking": det_uuid(f"{code}/marking"),
        },
        "docs": docs,
        "data": data or [],
        "quote": quote or {"text": "", "chosen": None, "versions": []},
        "matrix": build_matrix_rows(questions, use_points_by_level=use_points_by_level),
        "matrixConfirmed": True,
        "appliedPrefs": [],
        "chat": [],
        "history": [],
        "undo": [],
        "redo": [],
        "questions": questions,
    }
    if marking_guidance:
        exam["markingGuidance"] = marking_guidance
    _verify_exam_invariants(code, exam)
    return exam


def _tokens(text: str) -> set[str]:
    nfc = unicodedata.normalize("NFC", text).casefold().replace("$", " ")
    return {t for t in _VN_TOKEN_RE.findall(nfc) if t}


def _verify_exam_invariants(code: str, exam: dict[str, Any]) -> None:
    questions = exam["questions"]
    common_p100 = 0
    track_p100: dict[str, int] = {}
    mcq_answers: list[int] = []
    for idx, q in enumerate(questions, 1):
        p100 = round(float(q["points"]) * 100)
        grp = (q.get("choiceGroup") or "").strip()
        if grp:
            track_p100[grp] = track_p100.get(grp, 0) + p100
        else:
            common_p100 += p100
        if q["type"] == "mcq":
            assert len(q["options"]) == 4 and len({o.strip().casefold() for o in q["options"]}) == 4, (
                f"{code} câu {idx} phương án trùng hoặc thiếu"
            )
            mcq_answers.append(int(q["answer"]))
    if not track_p100:
        assert common_p100 == 1000, f"{code}: tổng điểm = {common_p100 / 100}"
    else:
        for grp, pts in track_p100.items():
            assert common_p100 + pts == 1000, f"{code} nhánh {grp}: {(common_p100 + pts) / 100}"
    if len(mcq_answers) >= 4:
        for a in range(4):
            assert mcq_answers.count(a) / len(mcq_answers) <= 0.45, f"{code}: lệch đáp án {a}"
        streak = 1
        for prev, cur in zip(mcq_answers, mcq_answers[1:], strict=False):
            streak = streak + 1 if cur == prev else 1
            assert streak < 3, f"{code}: lặp đáp án liên tiếp >= 3"
    toks = [_tokens(q["stem"]) for q in questions]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            union = len(toks[i] | toks[j])
            if union and len(toks[i]) >= 2 and len(toks[j]) >= 2:
                sim = len(toks[i] & toks[j]) / union
                assert sim < 0.65, f"{code}: câu {i + 1} và {j + 1} trùng lặp {sim:.2f}"


def make_doc(key: str, name: str, text: str) -> dict[str, Any]:
    return {
        "id": det_uuid(key),
        "name": name,
        "kind": "text",
        "version": 1,
        "needsReview": False,
        "pages": [{"number": 1, "text": text, "uncertain": False, "needsReview": False}],
    }


def _ans_cycle(idx: int) -> int:
    # Chuỗi đảo đều không bao giờ lặp 3 lần liên tiếp và phân bố đều 4 phương án A/B/C/D
    pattern = (0, 1, 2, 3, 1, 3, 0, 2, 2, 0, 3, 1, 3, 2, 1, 0)
    return pattern[idx % len(pattern)]


def _permute_options(correct_first: list[str], target_idx: int) -> tuple[list[str], int]:
    opts = list(correct_first)
    if target_idx != 0:
        opts[0], opts[target_idx] = opts[target_idx], opts[0]
    return opts, target_idx


def _make_sc01() -> dict[str, Any]:
    """SC-01: Toán 9 Cuối kỳ CV 7991 (22 câu: 12 MCQ 3,0đ + 2 ĐS 2,0đ + 4 TLN 2,0đ + 4 TL 3,0đ, 90 phút)."""
    doc = make_doc(
        "sc01/doc",
        "Tai_lieu_on_tap_Toan_9_HK1.txt",
        "Tư liệu Toán 9 tự biên soạn: Căn bậc hai, Hệ phương trình bậc nhất hai ẩn, "
        "Hệ thức lượng tam giác vuông, Đường tròn tâm O và Bảng tần số ghép nhóm.",
    )
    did = doc["id"]
    qs: list[dict[str, Any]] = []
    mcq_specs = [
        ("Căn thức bậc hai", "Bài 1: Căn bậc hai", "Nhận biết điều kiện xác định của căn thức", 0,
         r"Biểu thức $\sqrt{2x - 6}$ xác định trên $\mathbb{R}$ khi nào?",
         [r"$x \ge 3$", r"$x > 3$", r"$x \le 3$", r"$x \ge -3$"],
         r"Biểu thức dưới dấu căn không âm khi $2x - 6 \ge 0 \Leftrightarrow x \ge 3$."),
        ("Căn thức bậc hai", "Bài 2: Hằng đẳng thức căn", "Rút gọn biểu thức chứa căn bậc hai số học", 1,
         r"Rút gọn biểu thức $A = \sqrt{(3 - \sqrt{11})^2} + \sqrt{11}$ ta được kết quả nào?",
         [r"$3$", r"$-3$", r"$2\sqrt{11} - 3$", r"$3 - 2\sqrt{11}$"],
         r"Vì $\sqrt{11} > 3$ nên $|3 - \sqrt{11}| = \sqrt{11} - 3$; không phải âm, cộng thêm $\sqrt{11}$? Xin đối chiếu: $|3-\sqrt{11}| + \sqrt{11} = 2\sqrt{11} - 3$.",
        ),
        ("Phương trình và hệ phương trình", "Bài 3: Phương trình quy về bậc nhất", "Giải phương trình tích cơ bản", 0,
         r"Phương trình $(x - 4)(2x + 5) = 0$ có tổng các nghiệm bằng bao nhiêu?",
         [r"$\frac{3}{2}$", r"$-\frac{3}{2}$", r"$\frac{13}{2}$", r"$4$"],
         r"Nghiệm là $x = 4$ và $x = -\frac{5}{2}$, tổng $4 - \frac{5}{2} = \frac{3}{2}$."),
        ("Phương trình và hệ phương trình", "Bài 4: Hệ phương trình bậc nhất hai ẩn", "Kiểm tra cặp nghiệm của hệ phương trình", 0,
         r"Cặp số $(x; y)$ nào sau đây là nghiệm của hệ $\begin{cases}2x + y = 7\\ x - y = 2\end{cases}$?",
         [r"$(3; 1)$", r"$(1; 3)$", r"$(2; 3)$", r"$(4; -1)$"],
         r"Cộng hai phương trình theo vế: $3x = 9 \Rightarrow x = 3$, suy ra $y = 1$."),
        ("Bất đẳng thức và bất phương trình", "Bài 5: Bất phương trình bậc nhất một ẩn", "Tìm nghiệm nguyên của bất phương trình", 1,
         r"Bất phương trình $5 - 3x \le 14$ có tập nghiệm là gì?",
         [r"$x \ge -3$", r"$x \le -3$", r"$x > -3$", r"$x \le 3$"],
         r"Chuyển vế $-3x \le 9$; chia hai vế cho $-3$ và đổi chiều được $x \ge -3$."),
        ("Hệ thức lượng trong tam giác vuông", "Bài 6: Tỉ số lượng giác góc nhọn", "Tính giá trị lượng giác trong tam giác vuông", 0,
         r"Cho $\triangle ABC$ vuông tại $A$ có $AB = 6\text{ cm}$, $AC = 8\text{ cm}$. Giá trị $\sin C$ bằng bao nhiêu?",
         [r"$\frac{3}{5}$", r"$\frac{4}{5}$", r"$\frac{3}{4}$", r"$\frac{4}{3}$"],
         r"Cạnh huyền $BC = \sqrt{6^2 + 8^2} = 10\text{ cm}$, nên $\sin C = \frac{AB}{BC} = \frac{6}{10} = \frac{3}{5}$."),
        ("Hệ thức lượng trong tam giác vuông", "Bài 7: Ứng dụng đo chiều cao", "Tính chiều cao vật thể bằng tang góc nâng", 1,
         r"Một cột điện đổ bóng dài $12\text{ m}$ trên mặt đất phẳng khi tia nắng tạo với mặt đất góc $45^\circ$. Chiều cao cột điện là?",
         [r"$12\text{ m}$", r"$6\sqrt{2}\text{ m}$", r"$12\sqrt{3}\text{ m}$", r"$24\text{ m}$"],
         r"Chiều cao $h = 12 \cdot \tan 45^\circ = 12\text{ m}$."),
        ("Đường tròn và cung tròn", "Bài 8: Góc ở tâm và độ dài cung", "Tính độ dài cung tròn theo góc ở tâm", 1,
         r"Trên đường tròn bán kính $R = 9\text{ cm}$, cung có số đo $60^\circ$ có độ dài là bao nhiêu?",
         [r"$3\pi\text{ cm}$", r"$6\pi\text{ cm}$", r"$\frac{3\pi}{2}\text{ cm}$", r"$9\pi\text{ cm}$"],
         r"Độ dài cung $l = \frac{\pi R n}{180} = \frac{\pi \cdot 9 \cdot 60}{180} = 3\pi\text{ cm}$."),
        ("Đường tròn và cung tròn", "Bài 9: Diện tích hình quạt tròn", "Tính diện tích hình quạt tròn biết bán kính và góc", 1,
         r"Diện tích hình quạt tròn bán kính $R = 6\text{ cm}$ ứng với cung $90^\circ$ là bao nhiêu?",
         [r"$9\pi\text{ cm}^2$", r"$18\pi\text{ cm}^2$", r"$3\pi\text{ cm}^2$", r"$36\pi\text{ cm}^2$"],
         r"Diện tích quạt $S_q = \frac{\pi R^2 n}{360} = \frac{\pi \cdot 36 \cdot 90}{360} = 9\pi\text{ cm}^2$."),
        ("Đường tròn và cung tròn", "Bài 10: Vị trí tương đối hai đường tròn", "Xác định vị trí tương đối qua khoảng cách tâm", 0,
         r"Hai đường tròn $(O; 7\text{ cm})$ và $(I; 3\text{ cm})$ có khoảng cách hai tâm $OI = 4\text{ cm}$. Vị trí tương đối của chúng là?",
         [r"Tiếp xúc trong", r"Tiếp xúc ngoài", r"Cắt nhau", r"Đựng nhau không đồng tâm"],
         r"Vì $OI = 7 - 3 = 4\text{ cm}$ bằng hiệu hai bán kính nên hai đường tròn tiếp xúc trong."),
        ("Thống kê và xác suất", "Bài 11: Bảng tần số tương đối", "Tính tần số tương đối từ cỡ mẫu và tần số", 0,
         r"Khảo sát $40$ học sinh lớp 9 về thời gian tự học buổi tối, có $10$ em học trên $2$ giờ. Tần số tương đối của nhóm này là?",
         [r"$25\%$", r"$20\%$", r"$30\%$", r"$40\%$"],
         r"Tần số tương đối $f = \frac{10}{40} \cdot 100\% = 25\%$."),
        ("Thống kê và xác suất", "Bài 12: Xác suất thực nghiệm và cổ điển", "Tính xác suất khi rút ngẫu nhiên một thẻ", 2,
         r"Một hộp đựng $12$ thẻ đánh số từ $1$ đến $12$. Rút ngẫu nhiên một thẻ, xác suất rút được thẻ mang số chia hết cho $3$ là?",
         [r"$\frac{1}{3}$", r"$\frac{1}{4}$", r"$\frac{1}{2}$", r"$\frac{5}{12}$"],
         r"Các số chia hết cho $3$ gồm $\{3; 6; 9; 12\}$ có $4$ kết quả thuận lợi, xác suất là $\frac{4}{12} = \frac{1}{3}$."),
    ]
    # Sửa đáp án câu 2 cho khớp biểu thức toán học chính xác: A = |3 - sqrt(11)| + sqrt(11) = 2*sqrt(11) - 3
    mcq_specs[1] = (
        "Căn thức bậc hai",
        "Bài 2: Hằng đẳng thức căn",
        "Rút gọn biểu thức chứa căn bậc hai số học",
        1,
        r"Rút gọn biểu thức $A = \sqrt{(3 - \sqrt{11})^2} - \sqrt{11}$ ta được kết quả nào?",
        [r"$-3$", r"$3$", r"$2\sqrt{11} - 3$", r"$3 - 2\sqrt{11}$"],
        r"Do $\sqrt{11} > 3$ nên $\sqrt{(3-\sqrt{11})^2} = \sqrt{11} - 3$. Do đó $A = \sqrt{11} - 3 - \sqrt{11} = -3$.",
    )
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(mcq_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc01/q{idx + 1}", top, les, comp, lvl, 0.25, stem, p_opts, ans, exp,
                doc_id=did, location="Phần I · Trắc nghiệm", section_id="phan-1-mcq",
            )
        )

    # Phần II: 2 câu Đúng - Sai (1.0đ/câu = 2.0đ)
    qs.append(
        tf(
            "sc01/q13",
            "Bất đẳng thức và bất phương trình",
            "Bài 5: Hệ thống bất phương trình thực tế",
            "Đánh giá tính đúng sai của các mệnh đề về chi phí gửi hàng",
            1,
            1.0,
            "Một cửa hàng thuê xe giao hàng với phí cố định $150$ nghìn đồng và thêm $12$ nghìn đồng mỗi ki-lô-mét (kí hiệu quãng đường là $x > 0$, đơn vị km). Xét các khẳng định sau:",
            [
                "a) Tổng chi phí thuê xe theo $x$ là $150 + 12x$ (nghìn đồng).",
                "b) Để tổng chi phí không vượt quá $390$ nghìn đồng thì $150 + 12x < 390$.",
                "c) Với ngân sách tối đa $390$ nghìn đồng, quãng đường giao hàng lớn nhất là $20\\text{ km}$.",
                "d) Nếu quãng đường là $15\\text{ km}$ thì tổng chi phí bằng $320$ nghìn đồng.",
            ],
            [True, False, True, False],
            "a) Đúng: chi phí gồm phần cố định và biến đổi. b) Sai: 'không vượt quá' là dấu $\\le 390$. c) Đúng: $12x \\le 240 \\Rightarrow x \\le 20\\text{ km}$. d) Sai: $150 + 12 \\cdot 15 = 330$ nghìn đồng.",
            doc_id=did,
            location="Phần II · Câu 13",
            section_id="phan-2-tf",
        )
    )
    qs.append(
        tf(
            "sc01/q14",
            "Đường tròn và cung tròn",
            "Bài 10: Tiếp tuyến và dây cung",
            "Phân tích tính chất tiếp tuyến cắt nhau của đường tròn",
            2,
            1.0,
            "Cho đường tròn $(O; 5\\text{ cm})$ và điểm $M$ nằm ngoài đường tròn sao cho $OM = 13\\text{ cm}$. Kẻ hai tiếp tuyến $MA, MB$ với $(O)$ ($A, B$ là tiếp điểm). Xét các mệnh đề:",
            [
                "a) Tam giác $OAM$ vuông tại $A$.",
                "b) Độ dài đoạn tiếp tuyến $MA = 12\\text{ cm}$.",
                "c) Đường thẳng $OM$ vuông góc với dây cung $AB$ tại trung điểm của $AB$.",
                "d) Tứ giác $OAMB$ có diện tích bằng $120\\text{ cm}^2$.",
            ],
            [True, True, True, False],
            "a, b, c) Đúng theo định lí Pythagore ($MA = \\sqrt{13^2 - 5^2} = 12\\text{ cm}$) và tính chất hai tiếp tuyến cắt nhau. d) Sai: $S_{OAMB} = 2 \\cdot \\frac{1}{2} \\cdot 5 \\cdot 12 = 60\\text{ cm}^2$.",
            doc_id=did,
            location="Phần II · Câu 14",
            section_id="phan-2-tf",
        )
    )

    # Phần III: 4 câu Trả lời ngắn (0.5đ/câu = 2.0đ)
    short_specs = [
        ("Căn thức bậc hai", "Bài 2: Tính giá trị biểu thức căn", "Tính chính xác giá trị biểu thức chứa căn", 1,
         r"Tính giá trị của biểu thức $P = \sqrt{48} + \sqrt{27} - 7\sqrt{3}$ (nhập số nguyên).", "0",
         r"$P = 4\sqrt{3} + 3\sqrt{3} - 7\sqrt{3} = 0$."),
        ("Phương trình và hệ phương trình", "Bài 4: Giải hệ hai ẩn", "Tìm nghiệm của hệ bằng phương pháp cộng đại số", 1,
         r"Cho hệ phương trình $\begin{cases}3x + 2y = 16\\ x - 2y = 0\end{cases}$. Giá trị biểu thức $x + y$ bằng bao nhiêu?", "6",
         r"Cộng hai phương trình được $4x = 16 \Rightarrow x = 4$, suy ra $y = 2$, nên $x + y = 6$."),
        ("Hệ thức lượng trong tam giác vuông", "Bài 6: Tính cạnh tam giác vuông", "Vận dụng tỉ số lượng giác để tính độ dài", 2,
         r"Cho $\triangle DEF$ vuông tại $D$ có $DE = 9\text{ cm}$ và $\tan F = \frac{3}{4}$. Tính độ dài cạnh huyền $EF$ theo đơn vị cm.", "15",
         r"$\tan F = \frac{DE}{DF} = \frac{3}{4} \Rightarrow DF = 12\text{ cm}$, nên $EF = \sqrt{9^2 + 12^2} = 15\text{ cm}$."),
        ("Thống kê và xác suất", "Bài 11: Bảng tần số ghép nhóm", "Đọc bảng số liệu ghép nhóm để tính tỉ lệ", 2,
         "Kết quả đo chiều cao (cm) của $50$ cây giống sau $30$ ngày gieo trồng được cho ở bảng dưới đây. Có bao nhiêu phần trăm số cây cao từ $20\\text{ cm}$ trở lên?", "64",
         "Số cây cao từ $20\\text{ cm}$ trở lên là $18 + 14 = 32$ cây. Tỉ lệ phần trăm là $\\frac{32}{50} \\cdot 100\\% = 64\\%$."),
    ]
    for idx, (top, les, comp, lvl, stem, ans_txt, exp) in enumerate(short_specs, 15):
        tbl = (
            [{"rows": [["Chiều cao (cm)", "[10; 15)", "[15; 20)", "[20; 25)", "[25; 30)"], ["Số cây", "6", "12", "18", "14"]]}]
            if idx == 18
            else None
        )
        qs.append(
            short_q(
                f"sc01/q{idx}", top, les, comp, lvl, 0.5, stem, ans_txt, exp,
                doc_id=did, location=f"Phần III · Câu {idx}", tables=tbl, section_id="phan-3-short",
            )
        )

    # Phần IV: 4 câu Tự luận (0.5 + 0.75 + 1.0 + 0.75 = 3.0đ)
    q19_doc = doc_from(
        p_node("Rút gọn biểu thức ", ("math", r"Q = \left(\frac{1}{\sqrt{x} - 2} + \frac{1}{\sqrt{x} + 2}\right) \cdot \frac{x - 4}{\sqrt{x}}", False), " với ", ("math", r"x > 0, x \ne 4", False), ".")
    )
    qs.append(
        essay(
            "sc01/q19",
            "Căn thức bậc hai",
            "Bài 2: Biến đổi biểu thức chứa căn",
            "Rút gọn biểu thức chứa căn thức bậc hai có điều kiện xác định",
            1,
            0.5,
            "",
            r"Quy đồng trong ngoặc $\frac{2\sqrt{x}}{x - 4}$, nhân với $\frac{x - 4}{\sqrt{x}}$ được $Q = 2$.",
            [
                (r"Quy đồng mẫu thức trong ngoặc thành $\frac{2\sqrt{x}}{(\sqrt{x}-2)(\sqrt{x}+2)}$", 0.25),
                ("Rút gọn đúng kết quả cuối cùng $Q = 2$", 0.25),
            ],
            doc_id=did,
            location="Phần IV · Bài 19",
            rich_doc=q19_doc,
            section_id="phan-4-essay",
        )
    )
    qs.append(
        essay(
            "sc01/q20",
            "Phương trình và hệ phương trình",
            "Bài 4: Giải bài toán thực tế bằng lập hệ",
            "Thiết lập hệ phương trình từ bài toán năng suất làm việc",
            2,
            0.75,
            (
                "Hai đội công nhân cùng sửa một đoạn đường trong $6$ ngày thì xong. Nếu đội một làm riêng trong "
                "$4$ ngày rồi đội hai làm tiếp trong $9$ ngày thì cũng vừa xong đoạn đường đó. Hỏi nếu làm riêng "
                "thì mỗi đội hoàn thành công việc trong bao nhiêu ngày?"
            ),
            (
                r"Đặt ẩn $x, y > 6$ (ngày). Hệ phương trình $\frac{1}{x} + \frac{1}{y} = \frac{1}{6}$ và "
                r"$\frac{4}{x} + \frac{9}{y} = 1$. Suy ra $\frac{5}{y} = 1 - \frac{4}{6} = \frac{1}{3} \Rightarrow y = 15$, "
                r"từ đó $x = 10$ ngày."
            ),
            [
                ("Chọn ẩn $x, y > 6$ (ngày) và viết phương trình $\\frac{1}{x} + \\frac{1}{y} = \\frac{1}{6}$", 0.25),
                ("Lập đúng phương trình thứ hai $\\frac{4}{x} + \\frac{9}{y} = 1$ và giải hệ tìm $x, y$", 0.25),
                ("Đối chiếu điều kiện và kết luận hai đội làm riêng lần lượt $10$ ngày và $15$ ngày", 0.25),
            ],
            doc_id=did,
            location="Phần IV · Bài 20",
            section_id="phan-4-essay",
        )
    )

    qs.append(
        essay(
            "sc01/q21",
            "Đường tròn và cung tròn",
            "Bài 9: Hình học tổng hợp đường tròn",
            "Chứng minh tứ giác nội tiếp và đẳng thức tích đoạn thẳng",
            2,
            1.0,
            (
                "Cho tam giác nhọn $ABC$ ($AB < AC$) nội tiếp đường tròn tâm $O$, hai đường cao $AD$ và $BE$. "
                "Chứng minh bốn điểm $A, B, D, E$ cùng nằm trên một đường tròn và $AD \\cdot BC = BE \\cdot AC$."
            ),
            "Vì $\\widehat{ADB} = \\widehat{AEB} = 90^\\circ$ nên $D, E$ cùng nằm trên đường tròn đường kính $AB$. Mặt khác $2S_{ABC} = AD \\cdot BC = BE \\cdot AC$.",
            [
                ("Chứng minh $\\widehat{ADB} = \\widehat{AEB} = 90^\\circ$, suy ra $A, B, D, E$ cùng thuộc đường tròn đường kính $AB$", 0.5),
                ("Xét cặp tam giác đồng dạng $\\triangle ADC \\sim \\triangle BEC$ hoặc công thức diện tích để suy ra $AD \\cdot BC = BE \\cdot AC$", 0.5),
            ],
            doc_id=did,
            location="Phần IV · Bài 21",
            figure={
                "points": {"A": "free", "B": "free", "C": "free"},
                "constraints": ["D=foot(A,B,C)", "E=foot(B,A,C)", "O=circumcenter(A,B,C)"],
                "objects": [
                    "segment(A,B)",
                    "segment(A,C)",
                    "segment(B,C)",
                    {"type": "segment", "points": ["A", "D"], "dashed": True},
                    {"type": "segment", "points": ["B", "E"], "dashed": True},
                    "circle(O,A)",
                    "rightAngle(A,D,B)",
                ],
                "conditions": ["AB<AC", "acute(A,B,C)"],
                "labels": {"A": "above", "B": "left", "C": "right", "D": "below", "E": "right", "O": "left"},
                "caption": "Tam giác nhọn ABC nội tiếp (O) với đường cao AD, BE",
                "width": 480,
                "align": "center",
            },
            section_id="phan-4-essay",
        )
    )

    qs.append(
        essay(
            "sc01/q22",
            "Bất đẳng thức và bất phương trình",
            "Bài 5: Cực trị bất đẳng thức",
            "Tìm giá trị nhỏ nhất của biểu thức đại số hai biến dương",
            3,
            0.75,
            r"Cho hai số thực dương $x, y$ thỏa mãn $x + y = 6$. Tìm giá trị nhỏ nhất của biểu thức $M = \frac{1}{x} + \frac{4}{y}$.",
            r"Áp dụng bất đẳng thức Cauchy–Schwarz dạng Engel: $M = \frac{1^2}{x} + \frac{2^2}{y} \ge \frac{(1+2)^2}{x+y} = \frac{9}{6} = \frac{3}{2}$. Dấu bằng khi $\frac{1}{x} = \frac{2}{y}$ và $x + y = 6 \Rightarrow x = 2, y = 4$.",
            [
                (r"Biến đổi $M = \left(\frac{1}{x} + \frac{x}{4}\right) + \left(\frac{4}{y} + \frac{y}{4}\right) - \frac{x + y}{4}$", 0.25),
                (r"Áp dụng bất đẳng thức Cô-si chứng minh $M \ge 1 + 2 - \frac{6}{4} = \frac{3}{2}$", 0.25),
                ("Chỉ ra dấu bằng đạt tại $x = 2, y = 4$ và kết luận", 0.25),
            ],
            doc_id=did,
            location="Phần IV · Bài 22",
            section_id="phan-4-essay",
            lock_position=True,
        )
    )

    return build_exam(
        "SC-01",
        title="Đề kiểm tra cuối học kì I — Toán 9 (CV 7991)",
        school="TRƯỜNG THCS BÌNH MINH",
        department="Tổ Toán – Tin học",
        subject="Toán",
        grade="9",
        minutes=90,
        instructions="Học sinh làm bài 22 câu gồm 4 phần theo định hướng Công văn 7991. Không sử dụng tài liệu.",
        questions=qs,
        docs=[doc],
    )


def _make_sc02() -> dict[str, Any]:
    """SC-02: Toán 9 Tuyển sinh lớp 10 (5 bài lớn / 13 ý chấm, barem chi tiết 22 dòng, pointsByLevel)."""
    doc = make_doc(
        "sc02/doc",
        "De_cuong_tuyen_sinh_lop_10_Toan.txt",
        "Chuyên đề ôn thi tuyển sinh lớp 10 THPT: Biểu thức chứa căn, Giải bài toán lập phương trình, "
        "Parabol y = ax^2 và định lí Vi-ét, Hình học đường tròn tứ giác nội tiếp, Cực trị thực tế.",
    )
    did = doc["id"]
    qs = [
        essay(
            "sc02/b1",
            "Biểu thức đại số và căn thức",
            "Chuyên đề 1: Rút gọn và câu hỏi phụ",
            "Rút gọn biểu thức chứa căn, tính giá trị và giải bất phương trình liên quan",
            0,
            2.0,
            (
                "Cho hai biểu thức $A = \\frac{\\sqrt{x} + 2}{\\sqrt{x} - 3}$ và "
                "$B = \\frac{\\sqrt{x}}{\\sqrt{x} + 3} + \\frac{2\\sqrt{x}}{\\sqrt{x} - 3} - \\frac{3x + 9}{x - 9}$ "
                "với $x \\ge 0, x \\ne 9$.\n"
                "a) Tính giá trị của biểu thức $A$ khi $x = 16$.\n"
                "b) Chứng minh $B = \\frac{3}{\\sqrt{x} + 3}$.\n"
                "c) Tìm tất cả các giá trị nguyên của $x$ để $B > \\frac{1}{2}$."
            ),
            (
                "a) Tại $x = 16$: $A = \\frac{4+2}{4-3} = 6$. "
                "b) Quy đồng và rút gọn tử thức được $3(\\sqrt{x}-3)$, chia cho $(\\sqrt{x}-3)(\\sqrt{x}+3)$ ra $B = \\frac{3}{\\sqrt{x}+3}$. "
                "c) $\\frac{3}{\\sqrt{x}+3} > \\frac{1}{2} \\Leftrightarrow \\sqrt{x} < 3 \\Leftrightarrow 0 \\le x < 9$, nên $x \\in \\{0; 1; \\dots; 8\\}$."
            ),
            [
                ("a) Thay $x = 16$ thỏa mãn điều kiện vào $A$: $A = \\frac{4 + 2}{4 - 3} = 6$", 0.5),
                ("b) Quy đồng mẫu chung $(\\sqrt{x}+3)(\\sqrt{x}-3)$ với ba phân thức của $B$", 0.25),
                ("b) Khai triển tử thức thành $(x - 3\\sqrt{x}) + (2x + 6\\sqrt{x}) - (3x + 9) = 3(\\sqrt{x} - 3)$", 0.5),
                ("b) Rút gọn được $B = \\frac{3}{\\sqrt{x} + 3}$", 0.25),
                ("c) Giải bất phương trình $B > \\frac{1}{2} \\Leftrightarrow \\sqrt{x} < 3$, kết hợp $x \\in \\mathbb{Z}$ suy ra $x \\in \\{0;1;2;3;4;5;6;7;8\\}$", 0.5),
            ],
            doc_id=did,
            location="Bài 1 (3 ý chấm)",
        ),
        essay(
            "sc02/b2",
            "Bài toán thực tế và phương trình",
            "Chuyên đề 2: Lập phương trình/hệ phương trình",
            "Giải bài toán chuyển động và bài toán hình học thực tế",
            1,
            2.0,
            (
                "a) Một ô tô dự định đi quãng đường $120\\text{ km}$ với vận tốc không đổi. Sau khi đi được nửa quãng đường, "
                "xe tăng vận tốc thêm $10\\text{ km/h}$ trên nửa đoạn đường còn lại nên đến nơi sớm hơn dự định $12$ phút. "
                "Tính vận tốc dự định ban đầu của ô tô.\n"
                "b) Một bồn chứa nước hình trụ đứng có bán kính đáy $R = 0{,}5\\text{ m}$ và chiều cao $h = 1{,}4\\text{ m}$. "
                "Tính thể tích nước tối đa bồn chứa được (lấy $\\pi \\approx 3{,}14$, làm tròn đến hai chữ số thập phân)."
            ),
            "a) Gọi vận tốc dự định là $x > 0$ (km/h). Phương trình $\\frac{60}{x} - \\frac{60}{x+10} = \\frac{1}{5} \\Rightarrow x^2 + 10x - 3000 = 0 \\Rightarrow x = 50\\text{ km/h}$. b) $V = \\pi R^2 h = 3{,}14 \\cdot 0{,}25 \\cdot 1{,}4 \\approx 1{,}10\\text{ m}^3$.",
            [
                ("a) Chọn ẩn $x > 0$ (km/h), biểu diễn thời gian dự định và thực tế nửa sau", 0.25),
                ("a) Lập phương trình $\\frac{60}{x} - \\frac{60}{x + 10} = \\frac{1}{5}$ và đưa về $x^2 + 10x - 3000 = 0$", 0.5),
                ("a) Giải ra $x = 50$ (nhận) hoặc $x = -60$ (loại), kết luận $50\\text{ km/h}$", 0.5),
                ("b) Áp dụng $V = \\pi R^2 h = 3{,}14 \\cdot 0{,}5^2 \\cdot 1{,}4 = 1{,}099 \\approx 1{,}10\\text{ m}^3$", 0.75),
            ],
            doc_id=did,
            location="Bài 2 (2 ý chấm)",
        ),
        essay(
            "sc02/b3",
            "Hàm số y = ax^2 và định lí Vi-ét",
            "Chuyên đề 3: Parabol và phương trình bậc hai",
            "Tìm giao điểm đường thẳng với parabol và biện luận theo tham số Vi-ét",
            1,
            1.5,
            (
                "Cho phương trình bậc hai $x^2 - 2(m - 1)x + m^2 - 3 = 0$ ($m$ là tham số).\n"
                "a) Giải phương trình khi $m = 2$.\n"
                "b) Tìm tất cả các giá trị của $m$ để phương trình có hai nghiệm phân biệt $x_1, x_2$ thỏa mãn $x_1^2 + x_2^2 = 10$."
            ),
            "a) Với $m = 2$: $x^2 - 2x + 1 = 0 \\Rightarrow x = 1$. b) $\\Delta' = (m-1)^2 - (m^2-3) = 4 - 2m > 0 \\Leftrightarrow m < 2$. Ta có $(x_1+x_2)^2 - 2x_1x_2 = 4(m-1)^2 - 2(m^2-3) = 2m^2 - 8m + 10 = 10 \\Rightarrow m = 0$ (nhận) hoặc $m = 4$ (loại).",
            [
                ("a) Thay $m = 2$ viết đúng $x^2 - 2x + 1 = 0$", 0.25),
                ("a) Giải được nghiệm kép $x_1 = x_2 = 1$", 0.25),
                ("b) Tính $\\Delta' = 4 - 2m > 0 \\Leftrightarrow m < 2$ và viết hệ thức Vi-ét", 0.5),
                ("b) Biến đổi $x_1^2 + x_2^2 = 2m^2 - 8m + 10 = 10$, đối chiếu $m < 2$ nhận $m = 0$", 0.5),
            ],
            doc_id=did,
            location="Bài 3 (2 ý chấm)",
        ),
        essay(
            "sc02/b4",
            "Đường tròn và tứ giác nội tiếp",
            "Chuyên đề 4: Hình học tổng hợp",
            "Chứng minh tứ giác nội tiếp, góc bằng nhau và thẳng hàng trên đường tròn",
            2,
            3.5,
            (
                "Cho tam giác nhọn $ABC$ ($AB < AC$) nội tiếp đường tròn tâm $O$. Các đường cao $AD, BE, CF$ cắt nhau tại trực tâm $H$.\n"
                "a) Chứng minh tứ giác $BFEC$ nội tiếp.\n"
                "b) Chứng minh tứ giác $AEHF$ nội tiếp và xác định tâm đường tròn ngoại tiếp tứ giác đó.\n"
                "c) Kẻ đường kính $AK$ của $(O)$. Chứng minh $AB \\cdot AC = AD \\cdot AK$.\n"
                "d) Gọi $M$ là trung điểm $BC$. Chứng minh ba điểm $H, M, K$ thẳng hàng."
            ),
            "a) $\\widehat{BFC}=\\widehat{BEC}=90^\\circ$. b) $\\widehat{AFH}+\\widehat{AEH}=180^\\circ$, tâm là trung điểm $AH$. c) $\\triangle ABD \\sim \\triangle AKC$ (g.g). d) $BHCK$ là hình bình hành nên trung điểm $M$ của $BC$ cũng là trung điểm $HK$.",
            [
                ("Vẽ hình đúng, chính xác đường tròn $(O)$, các đường cao và đường kính $AK$", 0.25),
                ("a) Chỉ ra $\\widehat{BFC} = \\widehat{BEC} = 90^\\circ$ cùng nhìn cạnh $BC$ suy ra $BFEC$ nội tiếp", 0.75),
                ("b) Chứng minh $\\widehat{AFH} + \\widehat{AEH} = 180^\\circ$, kết luận tâm là trung điểm $AH$", 0.75),
                ("c) Chứng minh $\\widehat{ABD} = \\widehat{AKC}$ (cùng chắn cung $AC$) và $\\widehat{ADB} = \\widehat{ACK} = 90^\\circ$", 0.5),
                ("c) Suy ra $\\triangle ABD \\sim \\triangle AKC \\Rightarrow AB \\cdot AC = AD \\cdot AK$", 0.5),
                ("d) Chứng minh $BH \\parallel KC$ và $CH \\parallel KB$ nên $BHCK$ là hình bình hành, suy ra $H, M, K$ thẳng hàng", 0.75),
            ],
            doc_id=did,
            location="Bài 4 (4 ý chấm)",
            figure={
                "points": {"A": "free", "B": "free", "C": "free"},
                "constraints": [
                    "D=foot(A,B,C)",
                    "E=foot(B,A,C)",
                    "F=foot(C,A,B)",
                    "O=circumcenter(A,B,C)",
                    "H=orthocenter(A,B,C)",
                    "M=midpoint(B,C)",
                    "K=opposite(A,O)",
                ],
                "objects": [
                    "segment(A,B)",
                    "segment(A,C)",
                    "segment(B,C)",
                    "segment(A,D)",
                    "segment(B,E)",
                    "segment(C,F)",
                    {"type": "segment", "points": ["A", "K"], "dashed": True},
                    "circle(O,A)",
                    "rightAngle(A,D,B)",
                ],
                "conditions": ["AB<AC", "acute(A,B,C)"],
                "labels": {"A": "above", "B": "left", "C": "right", "D": "below", "E": "right", "F": "left", "O": "right", "H": "left", "M": "below", "K": "below"},
                "caption": "Tam giác nhọn ABC nội tiếp (O), trực tâm H và đường kính AK",
                "width": 480,
                "align": "center",
            },
        ),
        essay(
            "sc02/b5",
            "Bất đẳng thức và cực trị",
            "Chuyên đề 5: Câu phân loại",
            "Tìm cực trị bằng bất đẳng thức AM-GM và phương pháp đánh giá",
            3,
            1.0,
            (
                "Cho hai số thực dương $a, b$ thỏa mãn $a + b \\ge 4$.\n"
                "a) Chứng minh $\\frac{1}{a} + \\frac{1}{b} \\ge \\frac{4}{a + b}$.\n"
                "b) Tìm giá trị nhỏ nhất của biểu thức $S = a + b + \\frac{1}{a} + \\frac{1}{b}$."
            ),
            (
                "a) Quy đồng $(a + b)^2 \\ge 4ab \\Leftrightarrow (a - b)^2 \\ge 0$ (đúng). "
                "b) Tách điểm rơi tại $a = b = 2$: "
                "$S = \\left(\\frac{a}{4} + \\frac{1}{a}\\right) + \\left(\\frac{b}{4} + \\frac{1}{b}\\right) + \\frac{3}{4}(a + b) \\ge 1 + 1 + 3 = 5$."
            ),
            [
                ("a) Áp dụng bất đẳng thức $(a - b)^2 \\ge 0$ chứng minh $\\frac{1}{a} + \\frac{1}{b} \\ge \\frac{4}{a + b}$", 0.25),
                ("b) Tách điểm rơi $S = \\left(\\frac{a}{4} + \\frac{1}{a}\\right) + \\left(\\frac{b}{4} + \\frac{1}{b}\\right) + \\frac{3}{4}(a + b) \\ge 1 + 1 + 3 = 5$", 0.5),
                ("b) Chỉ ra dấu bằng xảy ra khi $a = b = 2$ và kết luận $\\min S = 5$", 0.25),
            ],
            doc_id=did,
            location="Bài 5 (2 ý chấm)",
            lock_position=True,
        ),
    ]

    return build_exam(
        "SC-02",
        title="Đề thi thử tuyển sinh vào lớp 10 THPT — Môn Toán",
        school="SỞ GD&ĐT TỈNH MINH HẢI (MẪU)",
        department="Hội đồng Bộ môn Toán",
        subject="Toán",
        grade="9",
        minutes=120,
        instructions="Thí sinh trình bày lời giải chi tiết cho cả 5 bài tự luận (13 ý chấm). Không sử dụng tài liệu.",
        questions=qs,
        docs=[doc],
        full_exam=True,
        marking_guidance="Học sinh có cách giải khác đúng về mặt toán học vẫn hưởng trọn số điểm của ý đó; làm tròn điểm toàn bài đến 0,25.",
        mcq_columns=1,
        use_points_by_level=True,
    )


def _make_sc03() -> dict[str, Any]:
    """SC-03: Ngữ văn 9 GDPT 2018 (Đọc hiểu 5 câu gắn passageId 4,0đ + Viết 2 câu NLXH/NLVH 6,0đ)."""
    passage = (
        "NGƯỜI ĐÓNG TÀU BÊN BẾN SÔNG CỬU\n"
        "(Ngữ liệu tự biên soạn)\n\n"
        "Mỗi sáng tháng Chạp, gió chướng thổi qua bãi bồi làm mặt nước bến sông Cửu gợn từng lớp sóng bạc. "
        "Trong căn lán lợp lá dừa nước, ông Bảy Mộc vẫn cặm cụi dùng bào tay chuốt từng thanh gỗ sao vàng óng. "
        "Khác với những xưởng cơ khí đóng tàu sắt ồn ào phía thượng lưu, tiếng đục, tiếng bào ở đây đều nhịp như hơi thở của dòng sông.\n\n"
        "Ông Bảy bảo rằng một chiếc ghe tốt không chỉ nằm ở lớp sơn dầu bóng loáng bên ngoài, mà ở những mối ghép mộng âm dương kín khít nằm khuất dưới lườn tàu. "
        "Chỉ cần một khe hở nhỏ bằng sợi tóc bị bỏ qua, con nước mặn sẽ âm thầm ăn mòn suốt mấy mùa gió bấc. "
        "Thằng Minh — đứa cháu nội vừa học hết lớp chín — ngồi bên cạnh ghi chép từng thông số độ cong sườn ghe vào quyển sổ tay sờn gáy, "
        "ánh mắt sáng lên khi hiểu vì sao người thợ già luôn đo lại hai lần trước khi hạ lưỡi cưa."
    )
    doc = make_doc("sc03/doc", "Ngu_lieu_tu_soan_Ngu_van_9.txt", passage)
    did = doc["id"]
    pid = "nv9-passage-1"
    ptitle = "Văn bản đọc hiểu: Người đóng tàu bên bến sông Cửu"
    qs = [
        essay(
            "sc03/q1", "Đọc hiểu văn bản truyện", "Bài 1: Ngôi kể và phương thức biểu đạt",
            "Xác định ngôi kể trong đoạn trích tự sự", 0, 0.5,
            "Xác định ngôi kể được sử dụng trong văn bản trên.",
            "Văn bản sử dụng ngôi kể thứ ba (người kể giấu mặt gọi nhân vật là ông Bảy Mộc, thằng Minh).",
            [("Nêu đúng ngôi kể thứ ba", 0.5)],
            doc_id=did, location="Đoạn 1–2", section_id="phan-1-doc-hieu",
            passage_id=pid, passage_title=ptitle, passage_text=passage,
        ),
        essay(
            "sc03/q2", "Đọc hiểu văn bản truyện", "Bài 1: Chi tiết nghệ thuật",
            "Tìm chi tiết miêu tả thái độ lao động cẩn trọng", 0, 0.5,
            "Chỉ ra hai chi tiết trong đoạn văn thứ hai cho thấy sự tỉ mỉ, nghiêm túc trong nghề của ông Bảy Mộc.",
            "Hai chi tiết: chú trọng những mối ghép mộng âm dương kín khít dưới lườn tàu và luôn đo lại hai lần trước khi hạ lưỡi cưa.",
            [
                ("Chỉ ra được chi tiết về mối ghép mộng âm dương kín khít dưới lườn tàu", 0.25),
                ("Chỉ ra được chi tiết luôn đo lại hai lần trước khi hạ lưỡi cưa", 0.25),
            ],
            doc_id=did, location="Đoạn 2", section_id="phan-1-doc-hieu",
            passage_id=pid,
        ),
        essay(
            "sc03/q3", "Thực hành tiếng Việt", "Bài 2: Biện pháp tu từ so sánh",
            "Phân tích tác dụng biện pháp tu từ so sánh trong câu văn", 1, 1.0,
            "",
            "So sánh tiếng đục, tiếng bào với hơi thở của dòng sông làm nổi bật sự gắn bó hài hòa giữa người thợ thủ công với thiên nhiên và nhịp sống bền bỉ của nghề truyền thống.",
            [
                ("Chỉ ra đúng phép so sánh 'tiếng đục, tiếng bào ở đây đều nhịp như hơi thở của dòng sông'", 0.25),
                ("Phân tích giá trị gợi hình, gợi âm thanh êm đềm và sự gắn bó hài hòa giữa con người với dòng sông", 0.75),
            ],
            doc_id=did, location="Đoạn 1", section_id="phan-1-doc-hieu",
            passage_id=pid,
            rich_doc=doc_from(
                p_node("Phân tích tác dụng của biện pháp tu từ so sánh trong câu: ", ("italic", "“tiếng đục, tiếng bào ở đây đều nhịp như hơi thở của dòng sông”"), ".")
            ),
        ),
        essay(
            "sc03/q4", "Đọc hiểu văn bản truyện", "Bài 1: Ý nghĩa hình ảnh biểu tượng",
            "Giải thích thông điệp từ chi tiết nghề đóng ghe", 1, 1.0,
            "Theo em, lời dặn của ông Bảy về “những mối ghép mộng âm dương kín khít nằm khuất dưới lườn tàu” gửi gắm bài học gì về phẩm chất của người làm nghề?",
            "Chất lượng thực sự và đạo đức nghề nghiệp nằm ở phần cốt lõi âm thầm bên trong, không chạy theo hình thức hào nhoáng bên ngoài.",
            [
                ("Giải thích nghĩa thực: độ bền con tàu phụ thuộc vào phần kỹ thuật ẩn bên dưới", 0.25),
                ("Rút ra nghĩa ẩn dụ: giá trị thật và chữ tín nghề nghiệp cần sự chỉn chu từ những việc thầm lặng nhất", 0.75),
            ],
            doc_id=did, location="Đoạn 2", section_id="phan-1-doc-hieu",
            passage_id=pid,
        ),
        essay(
            "sc03/q5", "Đọc hiểu văn bản truyện", "Bài 1: Liên hệ tiếp nối giá trị",
            "Nêu suy nghĩ về sự tiếp nối nghề truyền thống qua chi tiết nhân vật Minh", 2, 1.0,
            "Từ hình ảnh nhân vật Minh ghi chép thông số vào sổ tay, em rút ra thông điệp gì về cách thế hệ trẻ tiếp nhận tri thức từ thế hệ đi trước?",
            "Thế hệ trẻ cần biết lắng nghe, khiêm tốn quan sát và hệ thống hóa kinh nghiệm quý báu của lớp người đi trước bằng cách làm khoa học.",
            [
                ("Nhận xét được thái độ trân trọng, cầu thị của Minh qua việc lắng nghe và ghi chép", 0.5),
                ("Nêu bài học thiết thực cho bản thân trong học tập và gìn giữ tri thức truyền thống", 0.5),
            ],
            doc_id=did, location="Đoạn 2", section_id="phan-1-doc-hieu",
            passage_id=pid,
        ),
        essay(
            "sc03/q6", "Viết nghị luận xã hội", "Bài 3: Nghị luận về thái độ làm việc chỉn chu",
            "Viết đoạn văn NLXH khoảng 200 chữ trình bày suy nghĩ về sự cẩn trọng", 2, 2.0,
            "Viết một đoạn văn nghị luận (khoảng 200 chữ) trình bày suy nghĩ của em về ý nghĩa của sự cẩn trọng, làm việc đến nơi đến chốn trong học tập và cuộc sống.",
            "Đoạn văn đảm bảo cấu trúc diễn dịch/quy nạp/tổng-phân-hợp, làm rõ vai trò của sự cẩn trọng giúp hạn chế sai sót, tạo dựng uy tín cá nhân và phản đề thái độ qua loa.",
            [
                ("Đảm bảo hình thức đoạn văn nghị luận khoảng 200 chữ, lập luận mạch lạc", 0.25),
                ("Giải thích khái niệm cẩn trọng, làm việc đến nơi đến chốn", 0.5),
                ("Phân tích ý nghĩa và nêu dẫn chứng phù hợp, có chiều sâu", 0.75),
                ("Bàn luận mở rộng (phê phán thói cẩu thả) và rút ra bài học nhận thức, hành động", 0.5),
            ],
            doc_id=did, location="Phần II · Câu 1", section_id="phan-2-viet",
        ),
        essay(
            "sc03/q7", "Viết nghị luận văn học", "Bài 4: Phân tích tác phẩm truyện ngắn",
            "Viết bài văn NLVH phân tích chủ đề và nghệ thuật xây dựng nhân vật", 3, 4.0,
            "Viết bài văn nghị luận phân tích chủ đề và những nét đặc sắc nghệ thuật trong văn bản “Người đóng tàu bên bến sông Cửu” ở phần Đọc hiểu.",
            "Bài văn đầy đủ bố cục 3 phần, phân tích được chủ đề tôn vinh đạo đức nghề nghiệp và sự tiếp nối thế hệ, kết hợp nghệ thuật miêu tả chi tiết giàu sức gợi và ngôn ngữ bình dị.",
            [
                ("Đảm bảo cấu trúc bài văn nghị luận văn học (Mở bài, Thân bài, Kết bài)", 0.5),
                ("Xác định đúng vấn đề nghị luận: chủ đề và nghệ thuật của truyện ngắn", 0.5),
                ("Phân tích chủ đề về tình yêu nghề, đạo đức lao động thầm lặng và sự tiếp nối giữa hai thế hệ", 1.5),
                ("Phân tích đặc sắc nghệ thuật: ngôi kể thứ ba, bối cảnh sông nước, chi tiết biểu tượng và so sánh gợi cảm", 1.0),
                ("Diễn đạt chuẩn mực, liên kết chặt chẽ, có sáng tạo trong cảm thụ", 0.5),
            ],
            doc_id=did, location="Phần II · Câu 2", section_id="phan-2-viet",
            lock_position=True,
        ),
    ]
    return build_exam(
        "SC-03",
        title="Đề kiểm tra cuối học kì II — Ngữ văn 9 (GDPT 2018)",
        school="TRƯỜNG THCS ĐỒNG TIẾN",
        department="Tổ Ngữ văn – KHXH",
        subject="Ngữ văn",
        grade="9",
        minutes=120,
        instructions="Học sinh đọc kĩ ngữ liệu tự biên soạn và làm đầy đủ cả hai phần Đọc hiểu (4,0 điểm) và Viết (6,0 điểm).",
        questions=qs,
        docs=[doc],
        quote={"text": passage, "chosen": {"id": det_uuid("sc03/quote"), "label": "Ngữ liệu tự biên soạn"}, "versions": []},
        mcq_columns=1,
    )


def _make_sc04() -> dict[str, Any]:
    """SC-04: Vật lí 12 CV 7991 (28 câu: 18 MCQ + 4 ĐS 16 ý + 6 TLN, SI units, table + SVG figure)."""
    svg_snippet = (
        '<figure><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 200" '
        'aria-label="Đồ thị quá trình biến đổi trạng thái khí lí tưởng">'
        '<line x1="40" y1="20" x2="40" y2="170" stroke="#1e293b" stroke-width="2"/>'
        '<line x1="40" y1="170" x2="330" y2="170" stroke="#1e293b" stroke-width="2"/>'
        '<polyline points="70,130 160,60 270,60 270,130 70,130" fill="none" stroke="#0f766e" stroke-width="2"/>'
        '</svg><figcaption>Hình 1. Chu trình biến đổi trạng thái (p, V) trong thí nghiệm Vật lí 12</figcaption></figure>'
    )
    doc = make_doc(
        "sc04/doc",
        "Tu_lieu_thi_nghiem_Vat_li_12.txt",
        "Tư liệu Vật lí 12 tự biên soạn: Vật lí nhiệt, Khí lí tưởng, Từ trường và Vật lí hạt nhân.\n"
        + svg_snippet,
    )
    did = doc["id"]
    chart_png = make_png_chart([(0, 1.2), (2, 2.4), (4, 3.6), (6, 4.8), (8, 6.0)])
    qs: list[dict[str, Any]] = []

    mcq_specs = [
        ("Vật lí nhiệt", "Bài 1: Cấu trúc chất và sự chuyển thể", "Nhận biết tính chất chuyển động phân tử", 0,
         "Khi nhiệt độ của một khối chất khí lí tưởng tăng lên thì đại lượng nào sau đây của các phân tử khí tăng theo?",
         ["Tốc độ chuyển động nhiệt trung bình", "Khối lượng riêng của từng phân tử", "Điện tích hạt nhân nguyên tử", "Số lượng phân tử nếu bình kín"],
         "Nhiệt độ tuyệt đối tỉ lệ thuận với động năng tịnh tiến trung bình của phân tử."),
        ("Vật lí nhiệt", "Bài 2: Định luật I nhiệt động lực học", "Vận dụng dấu của công và nhiệt lượng", 1,
         r"Một khối khí nhận nhiệt lượng $Q = 120\text{ J}$ và thực hiện công ra bên ngoài $A' = 45\text{ J}$. Độ biến thiên nội năng $\Delta U$ của khí bằng?",
         [r"$75\text{ J}$", r"$165\text{ J}$", r"$-75\text{ J}$", r"$-165\text{ J}$"],
         r"Theo quy ước $\Delta U = A + Q$ với $A = -45\text{ J}, Q = +120\text{ J} \Rightarrow \Delta U = 75\text{ J}$."),
        ("Vật lí nhiệt", "Bài 3: Nhiệt dung riêng", "Tính nhiệt lượng thu vào để đun nóng nước", 1,
         r"Cần cung cấp nhiệt lượng bao nhiêu để đun $2{,}0\text{ kg}$ nước ($c = 4200\text{ J/(kg}\cdot\text{K)}$) tăng từ $25^\circ\text{C}$ lên $75^\circ\text{C}$?",
         [r"$420\text{ kJ}$", r"$210\text{ kJ}$", r"$630\text{ kJ}$", r"$840\text{ kJ}$"],
         r"$Q = mc\Delta t = 2{,}0 \cdot 4200 \cdot 50 = 420\,000\text{ J} = 420\text{ kJ}$."),
        ("Vật lí nhiệt", "Bài 4: Nhiệt nóng chảy riêng", "Phân biệt quá trình nóng chảy đẳng nhiệt", 0,
         "Trong suốt thời gian một chất rắn kết tinh tinh khiết đang nóng chảy hoàn toàn ở áp suất không đổi, nhiệt độ của chất đó như thế nào?",
         ["Không thay đổi", "Tăng đều theo thời gian", "Giảm dần rồi ổn định", "Biến thiên tuần hoàn"],
         "Nhiệt lượng cung cấp chỉ dùng để phá vỡ mạng tinh thể nên nhiệt độ giữ nguyên."),
        ("Khí lí tưởng", "Bài 5: Thang nhiệt độ Kelvin", "Chuyển đổi giữa thang Celsius và thang Kelvin", 0,
         r"Nhiệt độ $27^\circ\text{C}$ trong thang Celsius tương ứng với giá trị nào trong thang Kelvin?",
         [r"$300\text{ K}$", r"$246\text{ K}$", r"$273\text{ K}$", r"$327\text{ K}$"],
         r"Áp dụng công thức $T(\text{K}) = t(^\circ\text{C}) + 273 = 300\text{ K}$."),
        ("Khí lí tưởng", "Bài 6: Định luật Boyle", "Tính áp suất sau khi nén đẳng nhiệt", 1,
         r"Nén đẳng nhiệt $6{,}0\text{ L}$ khí lí tưởng từ áp suất $p_1 = 1{,}0 \cdot 10^5\text{ Pa}$ xuống còn $2{,}0\text{ L}$. Áp suất khí lúc sau là?",
         [r"$3{,}0 \cdot 10^5\text{ Pa}$", r"$1{,}5 \cdot 10^5\text{ Pa}$", r"$2{,}0 \cdot 10^5\text{ Pa}$", r"$0{,}33 \cdot 10^5\text{ Pa}$"],
         r"$p_1 V_1 = p_2 V_2 \Rightarrow p_2 = \frac{1{,}0 \cdot 10^5 \cdot 6{,}0}{2{,}0} = 3{,}0 \cdot 10^5\text{ Pa}$."),
        ("Khí lí tưởng", "Bài 7: Định luật Charles", "Tính thể tích khi nung nóng đẳng áp", 1,
         r"Một lượng khí lí tưởng ở $300\text{ K}$ chiếm thể tích $4{,}0\text{ L}$. Làm nóng đẳng áp đến $450\text{ K}$ thì thể tích khí là?",
         [r"$6{,}0\text{ L}$", r"$5{,}0\text{ L}$", r"$2{,}7\text{ L}$", r"$8{,}0\text{ L}$"],
         r"$\frac{V_1}{T_1} = \frac{V_2}{T_2} \Rightarrow V_2 = 4{,}0 \cdot \frac{450}{300} = 6{,}0\text{ L}$."),
        ("Khí lí tưởng", "Bài 8: Áp suất khí theo mô hình động học", "Tính gia tốc va chạm và áp suất thành bình", 2,
         r"Trong hệ SI, nếu mật độ phân tử khí là $n$ và động năng tịnh tiến trung bình mỗi phân tử là $E_d$, biểu thức áp suất khí lí tưởng là?",
         [r"$p = \frac{2}{3} n E_d$", r"$p = \frac{1}{3} n E_d$", r"$p = \frac{3}{2} n E_d$", r"$p = 2 n E_d$"],
         r"Từ mô hình động học phân tử khí lí tưởng, $p = \frac{2}{3} n E_d$."),
        ("Từ trường", "Bài 9: Lực từ tác dụng lên đoạn dây dẫn", "Tính lực từ với dây dẫn vuông góc đường sức", 0,
         r"Một đoạn dây dẫn dài $0{,}5\text{ m}$ mang dòng điện $I = 4{,}0\text{ A}$ đặt vuông góc với từ trường đều có cảm ứng từ $B = 0{,}2\text{ T}$. Độ lớn lực từ tác dụng lên dây là?",
         [r"$0{,}4\text{ N}$", r"$0{,}2\text{ N}$", r"$0{,}8\text{ N}$", r"$4{,}0\text{ N}$"],
         r"$F = B I l \sin 90^\circ = 0{,}2 \cdot 4{,}0 \cdot 0{,}5 = 0{,}4\text{ N}$."),
        ("Từ trường", "Bài 10: Từ thông và cảm ứng điện từ", "Tính từ thông qua khung dây phẳng", 1,
         r"Khung dây phẳng diện tích $S = 20\text{ cm}^2$ đặt sao cho mặt phẳng khung hợp với vectơ cảm ứng từ $B = 0{,}5\text{ T}$ một góc $30^\circ$. Từ thông qua khung bằng?",
         [r"$5{,}0 \cdot 10^{-4}\text{ Wb}$", r"$8{,}66 \cdot 10^{-4}\text{ Wb}$", r"$1{,}0 \cdot 10^{-3}\text{ Wb}$", r"$2{,}5 \cdot 10^{-4}\text{ Wb}$"],
         r"Góc giữa pháp tuyến $\vec{n}$ và $\vec{B}$ là $\alpha = 60^\circ$, nên $\Phi = BS\cos 60^\circ = 0{,}5 \cdot 20\cdot 10^{-4} \cdot 0{,}5 = 5{,}0\cdot 10^{-4}\text{ Wb}$."),
        ("Từ trường", "Bài 11: Dòng điện xoay chiều và mạch điện", "Tính cường độ dòng điện hiệu dụng qua điện trở", 1,
         r"Đặt điện áp xoay chiều có giá trị hiệu dụng $U = 220\text{ V}$ vào hai đầu đoạn mạch chỉ có điện trở thuần $R = 44\,\Omega$. Cường độ dòng điện hiệu dụng là?",
         [r"$5\text{ A}$", r"$5\sqrt{2}\text{ A}$", r"$10\text{ A}$", r"$0{,}2\text{ A}$"],
         r"$I = \frac{U}{R} = \frac{220}{44} = 5\text{ A}$."),
        ("Từ trường", "Bài 12: Máy biến áp và truyền tải điện", "Tính tỉ số vòng dây máy biến áp lí tưởng", 1,
         r"Một máy biến áp lí tưởng có cuộn sơ cấp $1000$ vòng đặt vào điện áp $220\text{ V}$ để lấy ra điện áp $11\text{ V}$ ở cuộn thứ cấp. Số vòng dây cuộn thứ cấp là?",
         [r"$50$ vòng", r"$100$ vòng", r"$200$ vòng", r"$20$ vòng"],
         r"$N_2 = N_1 \frac{U_2}{U_1} = 1000 \cdot \frac{11}{220} = 50$ vòng."),
        ("Từ trường", "Bài 13: Sóng điện từ", "Nhận biết bản chất truyền lan sóng điện từ", 0,
         "Trong chân không, thành phần điện trường $\\vec{E}$ và thành phần từ trường $\\vec{B}$ tại một điểm của sóng điện từ luôn có đặc điểm nào?",
         ["Vuông góc với nhau và cùng pha", "Cùng phương và ngược pha", "Vuông góc với nhau và vuông pha", "Song song với phương truyền sóng"],
         "Sóng điện từ là sóng ngang: $\\vec{E}$, $\\vec{B}$, $\\vec{v}$ lập thành tam diện thuận và $\\vec{E}, \\vec{B}$ biến thiên cùng pha."),
        ("Vật lí hạt nhân", "Bài 14: Cấu tạo hạt nhân nguyên tử", "Xác định số nơtron của đồng vị", 0,
         r"Hạt nhân đồng vị $_{11}^{23}\text{Na}$ chứa bao nhiêu nơtron?",
         ["$12$", "$11$", "$23$", "$34$"],
         r"Số nơtron $N = A - Z = 23 - 11 = 12$."),
        ("Vật lí hạt nhân", "Bài 15: Năng lượng liên kết hạt nhân", "Tính năng lượng liên kết riêng", 1,
         r"Hạt nhân $_2^4\text{He}$ có độ hụt khối $\Delta m = 0{,}0304\text{ u}$. Lấy $1\text{ u}c^2 = 931{,}5\text{ MeV}$. Năng lượng liên kết riêng của hạt nhân này xấp xỉ?",
         [r"$7{,}08\text{ MeV/nuclôn}$", r"$28{,}32\text{ MeV/nuclôn}$", r"$14{,}16\text{ MeV/nuclôn}$", r"$3{,}54\text{ MeV/nuclôn}$"],
         r"$W_{\text{lk}} \approx 0{,}0304 \cdot 931{,}5 \approx 28{,}32\text{ MeV}$, chia cho $A = 4$ được $7{,}08\text{ MeV/nuclôn}$."),
        ("Vật lí hạt nhân", "Bài 16: Định luật phóng xạ", "Tính khối lượng chất phóng xạ còn lại", 2,
         r"Một mẫu chất phóng xạ có chu kì bán rã $T = 8$ ngày và khối lượng ban đầu $m_0 = 64\text{ g}$. Sau $24$ ngày, khối lượng chất phóng xạ còn lại là?",
         [r"$8\text{ g}$", r"$16\text{ g}$", r"$4\text{ g}$", r"$56\text{ g}$"],
         r"Sau $t = 24 = 3T$, khối lượng còn lại là $m = m_0 \cdot 2^{-3} = \frac{64}{8} = 8\text{ g}$."),
        ("Vật lí hạt nhân", "Bài 17: Phản ứng phân hạch và tổng hợp", "Phân biệt bản chất hai loại phản ứng hạt nhân", 1,
         "Đặc điểm chung của phản ứng phân hạch và phản ứng tổng hợp hạt nhân là gì?",
         ["Đều là phản ứng hạt nhân tỏa năng lượng", "Đều xảy ra tự phát ở nhiệt độ phòng", "Đều bảo toàn số prôtôn và khối lượng nghỉ", "Đều chỉ xảy ra với các hạt nhân nhẹ"],
         "Cả hai quá trình đều tạo ra hạt nhân bền vững hơn nên đều tỏa năng lượng lớn."),
        ("Vật lí nhiệt", "Bài 18: Thí nghiệm đo gia tốc và nhiệt dung", "Xử lí đơn vị SI và sai số đo lường", 2,
         r"Một vật khối lượng $2{,}0\text{ kg}$ trượt trên mặt phẳng ngang với gia tốc có độ lớn $a = 1{,}5\text{ m/s}^2$ dưới tác dụng của lực kéo $F_k = 5{,}0\text{ N}$. Độ lớn lực ma sát là?",
         [r"$2{,}0\text{ N}$", r"$3{,}0\text{ N}$", r"$8{,}0\text{ N}$", r"$1{,}5\text{ N}$"],
         r"Theo định luật II Newton: $F_k - F_{\text{ms}} = ma \Rightarrow F_{\text{ms}} = 5{,}0 - 2{,}0 \cdot 1{,}5 = 2{,}0\text{ N}$."),
    ]
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(mcq_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc04/q{idx + 1}", top, les, comp, lvl, 0.25, stem, p_opts, ans, exp,
                doc_id=did, location="Phần I · Trắc nghiệm", section_id="phan-1-mcq",
            )
        )

    # Phần II: 4 Đúng-Sai (1.0đ/câu = 4.0đ), kèm bảng số liệu và đồ thị hình học / ảnh PNG
    qs.append(
        tf(
            "sc04/q19",
            "Vật lí nhiệt",
            "Bài 3: Thực hành đo nhiệt dung riêng của nước",
            "Đánh giá số liệu thực nghiệm và đồ thị nhiệt độ theo thời gian",
            2,
            1.0,
            "Một nhóm học sinh dùng dây đốt điện có công suất ổn định $P = 250\\text{ W}$ (điện trở $R = 20\\,\\Omega$) để đun $0{,}50\\text{ kg}$ nước trong nhiệt lượng kế và ghi lại số liệu ở bảng sau. Coi hiệu suất truyền nhiệt là $84\\%$. Xét các nhận định:",
            [
                "a) Trong mỗi giây, dây đốt tỏa ra nhiệt lượng $250\\text{ J}$.",
                "b) Từ $t = 0\\text{ s}$ đến $t = 200\\text{ s}$, nhiệt lượng nước thực sự thu vào là $42\\,000\\text{ J}$.",
                "c) Từ đồ thị thực nghiệm, tốc độ tăng nhiệt độ trung bình của nước là $0{,}10\\text{ K/s}$.",
                "d) Cường độ dòng điện hiệu dụng chạy qua dây đốt có giá trị nhỏ hơn $3{,}0\\text{ A}$.",
            ],
            [True, True, True, False],
            r"a) Đúng ($Q = Pt$). b) Đúng ($Q_{\text{thu}} = 0{,}84 \cdot 250 \cdot 200 = 42\,000\text{ J}$). c) Đúng ($\Delta T = 20\text{ K}$ trong $200\text{ s}$). d) Sai ($I = \sqrt{P/R} = \sqrt{250/20} \approx 3{,}54\text{ A} > 3{,}0\text{ A}$).",
            doc_id=did,
            location="Phần II · Câu 19",
            tables=[
                {
                    "rows": [
                        ["Thời gian t (s)", "0", "50", "100", "150", "200"],
                        ["Nhiệt độ T (°C)", "25,0", "30,0", "35,0", "40,0", "45,0"],
                    ]
                }
            ],
            images=[{"id": det_uuid("sc04/img1"), "data": chart_png, "caption": "Đồ thị độ tăng nhiệt độ theo thời gian đun nước"}],
            figure={
                "points": {"O": {"x": 0, "y": 0}, "X": {"x": 8, "y": 0}, "Y": {"x": 0, "y": 6}, "A": {"x": 2, "y": 1.2}, "B": {"x": 6, "y": 3.6}, "C": {"x": 8, "y": 4.8}},
                "constraints": [],
                "objects": ["segment(O,X)", "segment(O,Y)", "segment(O,A)", "segment(A,B)", "segment(B,C)"],
                "labels": {"O": "left", "X": "right", "Y": "above", "A": "above", "B": "above", "C": "above"},
                "caption": "Đồ thị tuyến tính biểu diễn sự tăng nhiệt độ theo thời gian",
                "width": 460,
                "align": "center",
            },
            section_id="phan-2-tf",
        )
    )
    qs[-1]["options"][2] = "c) Tốc độ tăng nhiệt độ trung bình của nước trong thí nghiệm là $0{,}10\\text{ K/s}$."

    qs.append(
        tf(
            "sc04/q20",
            "Khí lí tưởng",
            "Bài 7: Phương trình trạng thái khí lí tưởng",
            "Phân tích chu trình kín trên giản đồ p-V",
            2,
            1.0,
            "Một lượng khí lí tưởng đơn nguyên tử chuyển từ trạng thái $(1)$ sang $(2)$ đẳng tích tăng áp suất, rồi giãn đẳng áp từ $(2)$ sang $(3)$. Xét các phát biểu:",
            [
                "a) Trong quá trình đẳng tích $(1) \\to (2)$, khí không thực hiện công cơ học ($A = 0$).",
                "b) Khi chuyển từ $(1)$ sang $(2)$ tăng áp suất, nhiệt độ tuyệt đối của khí tăng.",
                "c) Trong quá trình giãn đẳng áp $(2) \\to (3)$, khí nhận công từ bên ngoài ($A > 0$).",
                "d) Nội năng của khí ở trạng thái $(3)$ lớn hơn ở trạng thái $(1)$.",
            ],
            [True, True, False, True],
            "a, b) Đúng. c) Sai: khí giãn nở sinh công nên $A < 0$. d) Đúng vì $T_3 > T_2 > T_1$.",
            doc_id=did, location="Phần II · Câu 20", section_id="phan-2-tf",
        )
    )
    qs.append(
        tf(
            "sc04/q21",
            "Từ trường",
            "Bài 10: Hiện tượng cảm ứng điện từ",
            "Xác định chiều dòng điện cảm ứng và suất điện động",
            2,
            1.0,
            "Đặt một khung dây tròn $100$ vòng, diện tích mỗi vòng $S = 50\\text{ cm}^2$, điện trở tổng cộng $R = 4\\,\\Omega$ vuông góc với từ trường đều có cảm ứng từ giảm đều từ $0{,}8\\text{ T}$ về $0{,}2\\text{ T}$ trong $0{,}3\\text{ s}$. Xét các khẳng định:",
            [
                "a) Độ biến thiên cảm ứng từ trong khoảng thời gian trên có độ lớn $0{,}6\\text{ T}$.",
                "b) Suất điện động cảm ứng xuất hiện trong khung có độ lớn bằng $1{,}0\\text{ V}$.",
                "c) Cường độ dòng điện cảm ứng chạy qua khung dây bằng $0{,}25\\text{ A}$.",
                "d) Theo định luật Lenz, cảm ứng từ do dòng điện cảm ứng sinh ra ngược chiều với từ trường ngoài.",
            ],
            [True, True, True, False],
            "a) $|\\Delta B| = 0{,}6\\text{ T}$. b) $|e_c| = N \\frac{|\\Delta B| S}{\\Delta t} = 100 \\cdot \\frac{0{,}6 \\cdot 50\\cdot 10^{-4}}{0{,}3} = 1{,}0\\text{ V}$. c) $I = 1{,}0/4 = 0{,}25\\text{ A}$. d) Sai: từ trường ngoài đang giảm nên từ trường cảm ứng cùng chiều để chống lại sự giảm.",
            doc_id=did, location="Phần II · Câu 21", section_id="phan-2-tf",
        )
    )
    qs.append(
        tf(
            "sc04/q22",
            "Vật lí hạt nhân",
            "Bài 16: Phóng xạ và an toàn bức xạ",
            "Đọc đồ thị phân rã và tính độ phóng xạ",
            2,
            1.0,
            "Một nguồn phóng xạ Iôt $_{53}^{131}\\text{I}$ có chu kì bán rã $T = 8$ ngày được sử dụng trong y học. Ban đầu mẫu có $N_0 = 8{,}0 \\cdot 10^{14}$ hạt nhân. Xét các nhận định:",
            [
                "a) Hạt nhân $_{53}^{131}\\text{I}$ có $53$ prôtôn và $78$ nơtron.",
                "b) Sau $16$ ngày, số hạt nhân Iôt bị phân rã là $6{,}0 \\cdot 10^{14}$ hạt.",
                "c) Độ phóng xạ của mẫu giảm tuyến tính theo thời gian.",
                "d) Tỉ số giữa số hạt đã phân rã và số hạt còn lại sau $8$ ngày bằng $1$.",
            ],
            [True, True, False, True],
            r"a) Đúng ($131 - 53 = 78$). b) Đúng ($\Delta N = N_0(1 - 2^{-2}) = 0{,}75 N_0$). c) Sai: giảm theo hàm mũ $H = H_0 2^{-t/T}$. d) Đúng (sau $1T$ còn một nửa và phân rã một nửa).",
            doc_id=did, location="Phần II · Câu 22", section_id="phan-2-tf",
        )
    )

    # Phần III: 6 Trả lời ngắn (0.25đ/câu = 1.5đ)
    short_specs = [
        ("Vật lí nhiệt", "Bài 2: Định luật I nhiệt động lực học", "Tính công cơ học khi biết nhiệt và nội năng", 1,
         r"Một khối khí nhận nhiệt lượng $450\text{ J}$ đồng thời nội năng tăng thêm $320\text{ J}$. Khối khí đã thực hiện ra ngoài một công bằng bao nhiêu jun ($\text{J}$)?", "130",
         r"$\Delta U = Q - A' \Rightarrow A' = 450 - 320 = 130\text{ J}$."),
        ("Khí lí tưởng", "Bài 7: Phương trình Clapeyron", "Tính số mol khí lí tưởng từ áp suất, thể tích, nhiệt độ", 2,
         r"Một bình dung tích $8{,}31\text{ L}$ chứa khí lí tưởng ở nhiệt độ $300\text{ K}$ và áp suất $1{,}5 \cdot 10^5\text{ Pa}$. Lấy $R = 8{,}31\text{ J/(mol}\cdot\text{K)}$. Số mol khí trong bình là bao nhiêu (làm tròn đến một chữ số thập phân)?", "0,5",
         r"$n = \frac{pV}{RT} = \frac{1{,}5 \cdot 10^5 \cdot 8{,}31 \cdot 10^{-3}}{8{,}31 \cdot 300} = 0{,}5\text{ mol}$."),
        ("Từ trường", "Bài 9: Cân bằng lực từ trên dây dẫn", "Tính cường độ dòng điện làm dây treo cân bằng", 2,
         r"Thanh dẫn điện dài $l = 0{,}4\text{ m}$, khối lượng $m = 20\text{ g}$ đặt ngang vuông góc từ trường đều $B = 0{,}5\text{ T}$ ($g = 10\text{ m/s}^2$). Cần dòng điện $I$ bằng bao nhiêu ampe ($\text{A}$) để lực từ hướng lên cân bằng trọng lực?", "1",
         r"$BIl = mg \Rightarrow I = \frac{0{,}02 \cdot 10}{0{,}5 \cdot 0{,}4} = 1\text{ A}$."),
        ("Từ trường", "Bài 11: Công suất tiêu thụ mạch điện trở", "Tính công suất tỏa nhiệt theo định luật Joule-Lenz", 1,
         r"Dòng điện có cường độ hiệu dụng $I = 2{,}5\text{ A}$ chạy qua điện trở $R = 16\,\Omega$. Công suất tỏa nhiệt trên điện trở bằng bao nhiêu oát ($\text{W}$)?", "100",
         r"$P = I^2 R = 2{,}5^2 \cdot 16 = 100\text{ W}$."),
        ("Vật lí hạt nhân", "Bài 15: Phương trình phản ứng hạt nhân", "Tìm số khối hạt nhân sản phẩm", 1,
         r"Trong phản ứng hạt nhân $_1^2\text{H} + _1^3\text{H} \to _2^4\text{He} + _Z^A n$, tổng $A + Z$ của hạt nơtron sinh ra bằng bao nhiêu?", "1",
         r"Bảo toàn số khối và điện tích: $A = 2+3-4 = 1$, $Z = 1+1-2 = 0$, nên $A + Z = 1$."),
        ("Vật lí hạt nhân", "Bài 16: Tuổi mẫu vật phóng xạ", "Tính tuổi mẫu gỗ dựa vào chu kì bán rã C-14", 3,
         r"Một mẫu gỗ cổ có độ phóng xạ của đồng vị $^{14}\text{C}$ giảm đi $4$ lần so với mẫu gỗ tươi cùng khối lượng. Biết chu kì bán rã của $^{14}\text{C}$ là $5730$ năm. Tuổi của mẫu gỗ là bao nhiêu năm?", "11460",
         r"$H = H_0 \cdot 2^{-t/T} = \frac{H_0}{4} \Rightarrow t = 2T = 2 \cdot 5730 = 11460$ năm."),
    ]
    for idx, (top, les, comp, lvl, stem, ans_txt, exp) in enumerate(short_specs, 23):
        qs.append(
            short_q(
                f"sc04/q{idx}", top, les, comp, lvl, 0.25, stem, ans_txt, exp,
                doc_id=did, location=f"Phần III · Câu {idx}", section_id="phan-3-short",
            )
        )

    return build_exam(
        "SC-04",
        title="Đề thi thử tốt nghiệp THPT — Vật lí 12 (CV 7991)",
        school="TRƯỜNG THPT LÊ LỢI (MẪU)",
        department="Tổ Vật lí – Kĩ thuật",
        subject="Vật lí",
        grade="12",
        minutes=50,
        instructions="Đề gồm 28 câu (18 trắc nghiệm 4 lựa chọn, 4 Đúng–Sai, 6 trả lời ngắn). Sử dụng g = 10 m/s² khi cần.",
        questions=qs,
        docs=[doc],
    )


def _make_sc05() -> dict[str, Any]:
    """SC-05: Hóa học 11 (24 câu: 16 MCQ + 2 Đúng-Sai + 4 TLN + 2 Tự luận, phương trình \\ce{...} + bảng NTK)."""
    doc = make_doc(
        "sc05/doc",
        "Tu_lieu_Hoa_hoc_11.txt",
        "Tài liệu Hóa học 11 tự biên soạn: Cân bằng hóa học, Nitơ – Lưu huỳnh, Đại cương hữu cơ và Hiđrocacbon.\n"
        "Cho biết nguyên tử khối: H=1, C=12, N=14, O=16, Na=23, S=32, Cl=35,5, Fe=56, Cu=64, Ag=108.",
    )
    did = doc["id"]
    ntk_table = {
        "rows": [
            ["Nguyên tố", "H", "C", "N", "O", "Na", "S", "Cl", "Fe", "Cu"],
            ["Nguyên tử khối (amu)", "1", "12", "14", "16", "23", "32", "35,5", "56", "64"],
        ]
    }
    qs: list[dict[str, Any]] = []
    mcq_specs = [
        ("Cân bằng hóa học", "Bài 1: Khái niệm cân bằng hóa học", "Nhận biết trạng thái cân bằng động", 0,
         r"Trong một hệ phản ứng thuận nghịch đạt trạng thái cân bằng hóa học thì đặc điểm nào đúng?",
         ["Tốc độ phản ứng thuận bằng tốc độ phản ứng nghịch", "Phản ứng thuận và phản ứng nghịch dừng hẳn", "Nồng độ chất đầu luôn bằng nồng độ sản phẩm", "Áp suất hệ giảm về không"],
         "Ở trạng thái cân bằng động, $v_{\\text{thuận}} = v_{\\text{nghịch}} \\ne 0$."),
        ("Cân bằng hóa học", "Bài 2: Cân bằng trong dung dịch nước", "Tính pH dung dịch axit mạnh", 1,
         r"Dung dịch $\ce{HCl}$ có nồng độ $0{,}01\text{ M}$ ở $25^\circ\text{C}$ có giá trị $\text{pH}$ bằng bao nhiêu?",
         ["$2$", "$1$", "$12$", "$0{,}01$"],
         r"$[\ce{H+}] = 10^{-2}\text{ M} \Rightarrow \text{pH} = -\log(10^{-2}) = 2$."),
        ("Cân bằng hóa học", "Bài 2: Chất điện li", "Phân biệt chất điện li mạnh và yếu", 0,
         r"Chất nào sau đây là chất điện li mạnh khi tan trong nước?",
         [r"$\ce{NaCl}$", r"$\ce{CH3COOH}$", r"$\ce{C2H5OH}$", r"$\ce{HF}$"],
         r"$\ce{NaCl}$ là muối tan phân li hoàn toàn thành $\ce{Na+}$ và $\ce{Cl-}$."),
        ("Cân bằng hóa học", "Bài 3: Nguyên lí Le Chatelier", "Dự đoán chiều chuyển dịch cân bằng", 1,
         r"Cho cân bằng $\ce{N2(g) + 3H2(g) <=> 2NH3(g)}$ ($\Delta_r H^\circ_{298} = -92\text{ kJ}$). Khi tăng áp suất chung của hệ, cân bằng chuyển dịch theo chiều nào?",
         ["Chiều thuận tạo thêm $\\ce{NH3}$", "Chiều nghịch tạo thêm $\\ce{N2}$ và $\\ce{H2}$", "Không chuyển dịch", "Tăng tốc độ nghịch và dừng thuận"],
         "Tăng áp suất làm cân bằng chuyển dịch về phía giảm số mol khí ($4\\text{ mol} \\to 2\\text{ mol}$), tức chiều thuận."),
        ("Nitrogen và Sulfur", "Bài 4: Đơn chất nitơ", "Giải thích tính trơ của phân tử N2 ở nhiệt độ thường", 0,
         r"Ở điều kiện thường, phân tử $\ce{N2}$ khá trơ về mặt hóa học là do nguyên nhân nào?",
         ["Chứa liên kết ba bền vững với năng lượng liên kết lớn", "Nguyên tử nitơ có bán kính lớn nhất chu kì 2", "Độ âm điện của nitơ rất nhỏ", "Phân tử $\\ce{N2}$ phân cực mạnh"],
         r"Liên kết ba $\ce{N#N}$ có năng lượng liên kết tới $945\text{ kJ/mol}$ rất khó bị phá vỡ ở nhiệt độ thường."),
        ("Nitrogen và Sulfur", "Bài 5: Amoniac và muối amoni", "Nhận biết ion amoni bằng kiềm", 0,
         r"Nhỏ dung dịch $\ce{NaOH}$ vào ống nghiệm chứa dung dịch $\ce{NH4Cl}$ và đun nhẹ, hiện tượng thu được là?",
         ["Có khí mùi khai bay ra làm xanh giấy quỳ ẩm", "Xuất hiện kết tủa trắng không tan", "Dung dịch chuyển màu đỏ thẫm", "Có khí màu nâu đỏ thoát ra"],
         r"$\ce{NH4+ + OH- -> NH3 ^ + H2O}$; khí $\ce{NH3}$ có mùi khai đặc trưng và tính bazơ."),
        ("Nitrogen và Sulfur", "Bài 6: Axit sunfuric", "Nhận biết tính háo nước của H2SO4 đặc", 1,
         r"Cho đường mía ($\ce{C12H22O11}$) tiếp xúc với $\ce{H2SO4}$ đặc, đường hóa đen rồi sủi bọt trào ra khỏi cốc do $\ce{H2SO4}$ đặc có tính chất nào?",
         ["Tính oxi hóa mạnh và tính háo nước", "Chỉ có tính axit yếu", "Tính khử mạnh đối với cacbon", "Khả năng tạo phức bền"],
         r"$\ce{H2SO4}$ đặc lấy nước tạo $\ce{C}$ đen rồi oxi hóa một phần $\ce{C}$ sinh khí $\ce{CO2}, \ce{SO2}$."),
        ("Nitrogen và Sulfur", "Bài 7: Pha loãng axit sunfuric", "Quy tắc an toàn phòng thí nghiệm", 0,
         r"Cách pha loãng dung dịch $\ce{H2SO4}$ đặc an toàn trong phòng thí nghiệm là?",
         ["Rót từ từ axit đặc vào nước và khuấy đều", "Rót nhanh nước cất vào axit đặc", "Đun sôi axit đặc trước khi thêm nước", "Cho trực tiếp nước đá vào lọ axit đặc"],
         "Rót từ từ axit nặng hơn vào nước giúp nhiệt tỏa ra được nước hấp thụ an toàn."),
        ("Đại cương hữu cơ", "Bài 8: Nhóm chức và phổ hồng ngoại", "Nhận biết nhóm chức hữu cơ qua nhóm nguyên tử", 0,
         r"Nhóm chức đặc trưng của hợp chất ancol no đơn chức mạch hở là nhóm nào?",
         [r"$\ce{-OH}$ liên kết với nguyên tử C no", r"$\ce{-CHO}$", r"$\ce{-COOH}$", r"$\ce{-COO-}$"],
         "Ancol có nhóm hiđroxyl $\\ce{-OH}$ gắn vào nguyên tử cacbon no."),
        ("Đại cương hữu cơ", "Bài 9: Đồng phân và đồng đẳng", "Nhận biết cặp chất đồng đẳng", 1,
         r"Cặp chất nào sau đây thuộc cùng dãy đồng đẳng ankan?",
         [r"$\ce{CH4}$ và $\ce{C3H8}$", r"$\ce{C2H4}$ và $\ce{C2H6}$", r"$\ce{C2H2}$ và $\ce{C4H6}$", r"$\ce{C6H6}$ và $\ce{C2H4}$"],
         r"$\ce{CH4}$ và $\ce{C3H8}$ đều có công thức chung $\ce{C_nH_{2n+2}}$, hơn kém nhau $2$ nhóm $\ce{CH2}$."),
        ("Hiđrocacbon", "Bài 10: Phản ứng thế của ankan", "Viết công thức sản phẩm thế clo của metan", 0,
         r"Đốt nóng hỗn hợp khí metan và clo theo tỉ lệ mol $1:1$ ngoài ánh sáng thu được sản phẩm hữu cơ chính là?",
         [r"$\ce{CH3Cl}$", r"$\ce{CCl4}$", r"$\ce{CH2Cl2}$", r"$\ce{CH3OH}$"],
         r"$\ce{CH4 + Cl2 ->[as] CH3Cl + HCl}$."),
        ("Hiđrocacbon", "Bài 11: Anken và phản ứng cộng", "Tính khối lượng brom phản ứng với etilen", 1,
         r"Dẫn $0{,}2\text{ mol}$ khí etilen ($\ce{C2H4}$) sục từ từ vào dung dịch $\ce{Br2}$ dư. Số mol $\ce{Br2}$ đã tham gia phản ứng cộng là?",
         [r"$0{,}2\text{ mol}$", r"$0{,}4\text{ mol}$", r"$0{,}1\text{ mol}$", r"$0{,}3\text{ mol}$"],
         r"$\ce{C2H4 + Br2 -> C2H4Br2}$ theo tỉ lệ mol $1:1$ nên $n_{\ce{Br2}} = 0{,}2\text{ mol}$."),
        ("Hiđrocacbon", "Bài 12: Ankin và phản ứng thế kim loại", "Nhận biết ank-1-in bằng thuốc thử Tollens", 1,
         r"Chất nào sau đây tác dụng với dung dịch $\ce{AgNO3}$ trong $\ce{NH3}$ tạo kết tủa vàng nhạt?",
         [r"$\ce{CH#CH}$", r"$\ce{CH2=CH2}$", r"$\ce{CH3-C#C-CH3}$", r"$\ce{CH3-CH3}$"],
         r"Axetilen $\ce{CH#CH}$ có nguyên tử H linh động gắn với C mang liên kết ba đầu mạch."),
        ("Hiđrocacbon", "Bài 13: Aren – Benzen", "Tính chất đặc trưng của vòng benzen", 1,
         r"Trong điều kiện có bột sắt xúc tác và đun nóng, benzen phản ứng với brom lỏng theo loại phản ứng nào?",
         ["Phản ứng thế nguyên tử H ở vòng thơm", "Phản ứng cộng mở vòng hoàn toàn", "Phản ứng trùng hợp", "Phản ứng tách hiđro"],
         r"$\ce{C6H6 + Br2 ->[FeBr3, t^o] C6H5Br + HBr}$ là phản ứng thế."),
        ("Nitrogen và Sulfur", "Bài 6: Muối sunfat", "Nhận biết ion sunfat trong dung dịch", 0,
         r"Để phân biệt dung dịch $\ce{Na2SO4}$ và $\ce{NaNO3}$, thuốc thử thích hợp nhất là dung dịch nào?",
         [r"$\ce{BaCl2}$", r"$\ce{NaCl}$", r"$\ce{HCl}$", r"$\ce{KOH}$"],
         r"Ion $\ce{Ba^2+}$ kết hợp $\ce{SO4^2-}$ tạo kết tủa trắng $\ce{BaSO4}$ bền trong axit."),
        ("Cân bằng hóa học", "Bài 2: Chuẩn độ axit-bazơ", "Tính nồng độ dung dịch qua điểm tương đương", 2,
         r"Chuẩn độ $20{,}0\text{ mL}$ dung dịch $\ce{NaOH}$ cần vừa đủ $25{,}0\text{ mL}$ dung dịch $\ce{HCl}$ $0{,}10\text{ M}$. Nồng độ mol của dung dịch $\ce{NaOH}$ là?",
         [r"$0{,}125\text{ M}$", r"$0{,}080\text{ M}$", r"$0{,}100\text{ M}$", r"$0{,}250\text{ M}$"],
         r"$C_{\ce{NaOH}} = \frac{25{,}0 \cdot 0{,}10}{20{,}0} = 0{,}125\text{ M}$."),
    ]
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(mcq_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc05/q{idx + 1}", top, les, comp, lvl, 0.25, stem, p_opts, ans, exp,
                doc_id=did, location="Phần I · Trắc nghiệm",
                tables=[ntk_table] if idx == 0 else None, section_id="phan-1-mcq",
            )
        )

    qs.append(
        tf(
            "sc05/q17",
            "Cân bằng hóa học",
            "Bài 3: Hằng số cân bằng KC",
            "Phân tích cân bằng tổng hợp khí NH3",
            2,
            1.0,
            r"Xét phản ứng thuận nghịch trong bình kín dung tích không đổi: $\ce{N2(g) + 3H2(g) <=> 2NH3(g)}$ ($\Delta_r H^\circ_{298} < 0$). Xét các phát biểu:",
            [
                r"a) Biểu thức hằng số cân bằng là $K_C = \frac{[\ce{NH3}]^2}{[\ce{N2}][\ce{H2}]^3}$.",
                "b) Khi tăng nhiệt độ của bình phản ứng, cân bằng chuyển dịch theo chiều thuận.",
                "c) Sử dụng chất xúc tác sắt làm tăng tốc độ cả phản ứng thuận và phản ứng nghịch.",
                "d) Giá trị $K_C$ chỉ phụ thuộc vào nhiệt độ mà không phụ thuộc vào nồng độ ban đầu.",
            ],
            [True, False, True, True],
            "a, c, d) Đúng. b) Sai: phản ứng thuận tỏa nhiệt nên tăng nhiệt độ làm cân bằng dịch chuyển theo chiều nghịch.",
            doc_id=did, location="Phần II · Câu 17", section_id="phan-2-tf",
        )
    )
    qs.append(
        tf(
            "sc05/q18",
            "Hiđrocacbon",
            "Bài 11: Đốt cháy hiđrocacbon",
            "Biện luận dãy đồng đẳng qua số mol CO2 và H2O",
            2,
            1.0,
            r"Đốt cháy hoàn toàn $0{,}1\text{ mol}$ một hiđrocacbon mạch hở $X$, dẫn sản phẩm cháy thu được $0{,}3\text{ mol}$ $\ce{CO2}$ và $0{,}3\text{ mol}$ $\ce{H2O}$. Xét các khẳng định:",
            [
                r"a) Vì $n_{\ce{CO2}} = n_{\ce{H2O}}$ nên $X$ thuộc dãy đồng đẳng anken.",
                r"b) Công thức phân tử của $X$ là $\ce{C3H6}$.",
                r"c) Có $0{,}45\text{ mol}$ khí $\ce{O2}$ đã tham gia phản ứng đốt cháy trên.",
                "d) Chất $X$ không làm mất màu dung dịch nước brom ở điều kiện thường.",
            ],
            [True, True, True, False],
            r"a, b, c) Đúng: $\ce{C3H6 + \frac{9}{2}O2 -> 3CO2 + 3H2O}$, $n_{\ce{O2}} = 0{,}1 \cdot 4{,}5 = 0{,}45\text{ mol}$. d) Sai: anken mạch hở làm mất màu dung dịch $\ce{Br2}$.",
            doc_id=did, location="Phần II · Câu 18", section_id="phan-2-tf",
        )
    )

    short_specs = [
        ("Cân bằng hóa học", "Bài 2: Tính hằng số cân bằng", "Tính KC tại trạng thái cân bằng", 2,
         r"Trong bình $1{,}0\text{ L}$ ở trạng thái cân bằng $\ce{H2(g) + I2(g) <=> 2HI(g)}$, đo được $[\ce{H2}] = 0{,}2\text{ M}$, $[\ce{I2}] = 0{,}2\text{ M}$ và $[\ce{HI}] = 1{,}6\text{ M}$. Tính hằng số cân bằng $K_C$.", "64",
         r"$K_C = \frac{1{,}6^2}{0{,}2 \cdot 0{,}2} = \frac{2{,}56}{0{,}04} = 64$."),
        ("Nitrogen và Sulfur", "Bài 6: Tính khối lượng đồng phản ứng HNO3", "Bảo toàn electron với HNO3 đặc", 2,
         r"Hòa tan hoàn toàn $6{,}4\text{ g}$ bột $\ce{Cu}$ trong dung dịch $\ce{HNO3}$ đặc dư thu được khí $\ce{NO2}$ duy nhất. Thể tích khí $\ce{NO2}$ ở điều kiện chuẩn ($24{,}79\text{ L/mol}$) bằng bao nhiêu lít (làm tròn hai chữ số thập phân)?", "4,96",
         r"$n_{\ce{Cu}} = 0{,}1\text{ mol} \Rightarrow n_{\ce{NO2}} = 0{,}2\text{ mol} \Rightarrow V = 0{,}2 \cdot 24{,}79 = 4{,}958 \approx 4{,}96\text{ L}$."),
        ("Đại cương hữu cơ", "Bài 8: Tìm công thức phân tử hợp chất hữu cơ", "Tính khối lượng phân tử từ dữ kiện đốt cháy", 2,
         r"Đốt cháy hoàn toàn $0{,}2\text{ mol}$ ankan $Y$ thu được $17{,}6\text{ g}$ $\ce{CO2}$. Số nguyên tử cacbon trong phân tử $Y$ là bao nhiêu?", "2",
         r"$n_{\ce{CO2}} = \frac{17{,}6}{44} = 0{,}4\text{ mol} \Rightarrow C = \frac{0{,}4}{0{,}2} = 2$ ($\ce{C2H6}$)."),
        ("Hiđrocacbon", "Bài 11: Phản ứng cộng hiđro của ankin", "Tính lượng sản phẩm cộng hoàn toàn", 1,
         r"Hiđro hóa hoàn toàn $0{,}15\text{ mol}$ propin ($\ce{C3H4}$) với xúc tác Ni đun nóng để thu được propan ($\ce{C3H8}$). Số mol khí $\ce{H2}$ đã phản ứng là bao nhiêu?", "0,3",
         r"$\ce{C3H4 + 2H2 ->[Ni, t^o] C3H8} \Rightarrow n_{\ce{H2}} = 2 \cdot 0{,}15 = 0{,}3\text{ mol}$."),
    ]
    for idx, (top, les, comp, lvl, stem, ans_txt, exp) in enumerate(short_specs, 19):
        qs.append(
            short_q(
                f"sc05/q{idx}", top, les, comp, lvl, 0.5, stem, ans_txt, exp,
                doc_id=did, location=f"Phần III · Câu {idx}", section_id="phan-3-short",
            )
        )

    qs.append(
        essay(
            "sc05/q23",
            "Nitrogen và Sulfur",
            "Bài 6: Cân bằng phản ứng oxi hóa khử và tính toán",
            "Viết phương trình hóa học và tính nồng độ axit dư",
            2,
            1.0,
            r"Cho $5{,}6\text{ g}$ bột $\ce{Fe}$ tác dụng hoàn toàn với $200\text{ mL}$ dung dịch $\ce{H2SO4}$ loãng nồng độ $1{,}0\text{ M}$. Viết phương trình hóa học của phản ứng và tính nồng độ mol của muối $\ce{FeSO4}$ sau phản ứng (coi thể tích dung dịch không đổi).",
            r"$\ce{Fe + H2SO4 -> FeSO4 + H2}$. $n_{\ce{Fe}} = 0{,}1\text{ mol}$, $n_{\ce{H2SO4}} = 0{,}2\text{ mol}$ nên $\ce{Fe}$ hết. $C_{\ce{FeSO4}} = \frac{0{,}1}{0{,}2} = 0{,}5\text{ M}$.",
            [
                (r"Viết đúng phương trình $\ce{Fe + H2SO4 -> FeSO4 + H2}$ và tính $n_{\ce{Fe}} = 0{,}1\text{ mol}, n_{\ce{H2SO4}} = 0{,}2\text{ mol}$", 0.5),
                (r"Biện luận $\ce{Fe}$ phản ứng hết, tính $C_M(\ce{FeSO4}) = \frac{0{,}1}{0{,}2} = 0{,}5\text{ M}$", 0.5),
            ],
            doc_id=did, location="Phần IV · Bài 23", tables=[ntk_table], section_id="phan-4-essay",
        )
    )
    qs.append(
        essay(
            "sc05/q24",
            "Hiđrocacbon",
            "Bài 12: Xác định công thức và viết đồng phân",
            "Lập công thức phân tử chất hữu cơ và viết đồng phân cấu tạo",
            3,
            1.0,
            r"Một hiđrocacbon $X$ có phần trăm khối lượng cacbon là $85{,}71\%$ và có phân tử khối bằng $56\text{ amu}$. Xác định công thức phân tử của $X$ và viết công thức cấu tạo các đồng phân anken mạch hở của $X$.",
            r"Số nguyên tử C là $\frac{56 \cdot 0{,}8571}{12} = 4$; số nguyên tử H là $\frac{56 - 48}{1} = 8 \Rightarrow \ce{C4H8}$. Ba đồng phân anken mạch hở: but-1-ene, but-2-ene (cis/trans) và 2-methylpropene.",
            [
                (r"Tính được công thức phân tử $X$ là $\ce{C4H8}$", 0.5),
                (r"Viết đúng công thức cấu tạo 3 đồng phân anken mạch hở: $\ce{CH2=CH-CH2-CH3}$, $\ce{CH3-CH=CH-CH3}$, $\ce{CH2=C(CH3)2}$", 0.5),
            ],
            doc_id=did, location="Phần IV · Bài 24", section_id="phan-4-essay",
        )
    )

    return build_exam(
        "SC-05",
        title="Đề kiểm tra cuối học kì I — Hóa học 11",
        school="TRƯỜNG THPT NGUYỄN DU (MẪU)",
        department="Tổ Hóa – Sinh",
        subject="Hoá học",
        grade="11",
        minutes=50,
        instructions="Học sinh sử dụng Bảng nguyên tử khối đính kèm để giải các bài tập tính toán.",
        questions=qs,
        docs=[doc],
    )


def _make_sc06() -> dict[str, Any]:
    """SC-06: Tiếng Anh 12 GDPT 2018 (40 câu: Listening audio, gạch chân <u>, Ngữ pháp, Sắp xếp, Cloze [1]..[6], 2 Reading 15 câu với 3 passageId)."""
    listening_script = (
        "[Audio Track 1: Green Campus Initiative]\n"
        "Presenter: Welcome to our weekly school sustainability podcast. Today we speak with Lan, "
        "student coordinator of the Green Campus Initiative at Binh Minh High School. "
        "Lan explains that the team began by placing color-coded recycling bins beside every staircase "
        "and organizing monthly repair workshops for broken bicycles and umbrellas."
    )
    cloze_text = (
        "Urban Community Gardens\n"
        "In many crowded cities, unused rooftop spaces are gradually being turned into thriving vegetable gardens. "
        "Residents work together every weekend to prepare soil beds [1] _____ install rainwater barrels. "
        "These shared plots not only supply fresh produce [2] _____ also strengthen social bonds among neighbors of all ages. "
        "Schools located nearby often bring students to the rooftops [3] _____ learn practical lessons in plant biology. "
        "Although maintaining a rooftop garden requires careful planning, [4] _____ benefits far outweigh the initial cost. "
        "Local authorities have begun offering small grants to neighborhoods [5] _____ wish to launch similar projects, "
        "proving that sustainable habits can take root [6] _____ in densely populated districts."
    )
    reading1_text = (
        "Reading Passage 1: Quiet Libraries in a Hyper-Connected World\n"
        "For decades, public libraries were viewed mainly as silent warehouses for printed volumes. "
        "Today, however, neighborhood libraries are reinventing themselves as flexible civic hubs while preserving quiet study rooms. "
        "Visitors can borrow audiobooks, reserve soundproof booths for online interviews, or attend free workshops on digital literacy.\n\n"
        "Research conducted across twelve municipal branches showed that teenagers visited libraries most frequently when quiet reading zones "
        "were paired with collaborative project tables. Rather than replacing printed books, digital catalogs actually boosted borrowing rates "
        "because readers could locate niche titles within seconds. Librarians increasingly act as information guides who help citizens "
        "verify online sources and distinguish evidence-based reporting from misleading claims."
    )
    reading2_text = (
        "Reading Passage 2: Coastal Mangrove Restoration and Local Livelihoods\n"
        "Along tropical estuaries, mangrove forests serve as living buffers that absorb storm waves and trap river sediment before it clouds offshore reefs. "
        "Between 1990 and 2010, rapid pond construction cleared wide belts of coastal trees, leaving nearby villages vulnerable to high tides and coastal erosion.\n\n"
        "Recent community-led programs have shifted from top-down fencing toward integrated mangrove-aquaculture systems. "
        "Under this approach, farmers maintain at least sixty percent natural tree cover around tidal channels, allowing shrimp and mud crabs "
        "to feed on fallen leaves without artificial chemical feeds. Field measurements over five years revealed that restored belts reduced "
        "wave energy by nearly half while generating steadier household incomes than intensive open ponds. "
        "Planners note that long-term success depends on clear land-use agreements and shared monitoring between villagers and marine scientists."
    )
    doc = make_doc(
        "sc06/doc",
        "English_12_Original_Source_Pack.txt",
        "\n\n".join([listening_script, cloze_text, reading1_text, reading2_text]),
    )
    did = doc["id"]
    audio_meta = {
        "fileId": det_uuid("sc06/audio-track-1"),
        "filename": "sc06-green-campus-talk.mp3",
        "mimeType": "audio/mpeg",
        "maxPlays": 2,
        "durationSeconds": 110,
        "title": "Listening Track 1 — Green Campus Initiative",
    }

    qs: list[dict[str, Any]] = []
    # 1..5: Listening group (groupId + audio metadata) -> 5 câu
    listening_items = [
        ("What is the main topic of the student podcast interview?",
         ["A school sustainability project", "A national sports festival", "A city bus expansion plan", "A science museum renovation"],
         0, "The presenter introduces Lan as the coordinator of the Green Campus Initiative."),
        ("Where did the student team first place color-coded recycling bins?",
         ["Beside every staircase", "Inside the main kitchen", "Along the football field", "Behind the parking lot"],
         0, "The script states the bins were placed beside every staircase."),
        ("How often does the club organize repair workshops?",
         ["Monthly", "Daily", "Every two years", "Only in summer"],
         0, "They organize monthly repair workshops for broken bicycles and umbrellas."),
        ("Which items are mentioned as repaired during the workshops?",
         ["Bicycles and umbrellas", "Laptops and printers", "Desks and blackboards", "Cameras and radios"],
         0, "Broken bicycles and umbrellas are explicitly listed."),
        ("What is Lan's role in the Green Campus Initiative?",
         ["Student coordinator", "School principal", "Bus driver", "Guest scientist"],
         0, "Lan is introduced as the student coordinator of the initiative."),
    ]
    for idx, (stem, opts, _, exp) in enumerate(listening_items):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc06/q{idx + 1}", "Listening Comprehension", "Unit 1: Sustainable Living",
                "Extract key details from an informational audio talk", idx % 2, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Listening Track 1",
                section_id="sec-listening", group_id="eng12-listening-1",
                passage_title="Listening: Green Campus Initiative (Audio Track)" if idx == 0 else None,
                passage_text=listening_script if idx == 0 else None,
                audio=audio_meta, lock_position=(idx == 0),
            )
        )

    # 6..7: Pronunciation with <u> underline marks via optionDocs
    pron_specs = [
        ("Mark the letter A, B, C, or D to indicate the word whose underlined digraph 'ea' differs in vowel pronunciation.",
         [("m", "ea", "sure"), ("tr", "ea", "sure"), ("f", "ea", "ther"), ("f", "ea", "ture")],
         3, "'feature' pronounces 'ea' as /iː/, whereas 'measure', 'treasure', 'feather' use /e/."),
        ("Identify the English item in which the highlighted single vowel 'a' has a distinct sound from the others.",
         [("pl", "a", "ne"), ("st", "a", "ge"), ("sh", "a", "pe"), ("pl", "a", "n")],
         3, "'plan' pronounces 'a' as /æ/, whereas 'plane', 'stage', 'shape' use /eɪ/."),
    ]
    for _p_idx, (stem, parts, correct_idx_orig, exp) in enumerate(pron_specs):
        built = [underline_option(pre, u, suf) for pre, u, suf in parts]
        raw_opts = [txt for txt, _ in built]
        raw_docs = [doc_obj for _, doc_obj in built]
        target_idx = _ans_cycle(len(qs))
        # Put differing word first then permute both options and optionDocs identically
        raw_opts[0], raw_opts[correct_idx_orig] = raw_opts[correct_idx_orig], raw_opts[0]
        raw_docs[0], raw_docs[correct_idx_orig] = raw_docs[correct_idx_orig], raw_docs[0]
        raw_opts[0], raw_opts[target_idx] = raw_opts[target_idx], raw_opts[0]
        raw_docs[0], raw_docs[target_idx] = raw_docs[target_idx], raw_docs[0]
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Phonetics", "Pronunciation: Vowel contrasts",
                "Distinguish vowel pronunciation in English words", 0, 0.25,
                stem,
                raw_opts, target_idx, exp, doc_id=did, location="Section II · Phonetics",
                option_docs=raw_docs, section_id="sec-phonetics",
            )
        )

    # 8..9: Stress
    stress_specs = [
        ("Mark the disyllabic noun or verb whose primary stress falls on a different syllable.",
         ["collect", "window", "garden", "paper"], "collect stresses syllable 2; window, garden, paper stress syllable 1."),
        ("Which three-syllable vocabulary word carries its main stress on the third syllable instead of the first?",
         ["engineer", "scientist", "manager", "resident"], "engineer stresses syllable 3; the others stress syllable 1."),
    ]
    for stem, opts, exp in stress_specs:
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Phonetics", "Word Stress Patterns",
                "Identify primary stress placement", 0, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Section II · Stress", section_id="sec-phonetics",
            )
        )

    # 10..14: Grammar & Vocabulary (5 câu)
    grammar_specs = [
        ("Rarely _____ such an enthusiastic group of student volunteers during a coastal cleanup.",
         ["have organizers met", "organizers have met", "did organizers met", "organizers met"],
         "Negative adverb 'Rarely' at the beginning requires subject-auxiliary inversion."),
        ("The solar microgrid _____ last autumn now powers every classroom computer lab.",
         ["installed", "installing", "was installed", "installs"],
         "Reduced passive relative clause: '(which was) installed last autumn'."),
        ("Students are encouraged to _____ old textbooks at the library exchange shelf instead of discarding them.",
         ["pass on", "turn down", "break out", "put off"],
         "'Pass on' means to give something you have used to someone else."),
        ("Had the municipal team checked the bridge sensors earlier, the traffic delay _____ avoided.",
         ["could have been", "will be", "has been", "can be"],
         "Inverted third conditional describing an unreal past result."),
        ("Clear communication is essential _____ building trust between mentors and first-year apprentices.",
         ["for", "with", "over", "into"],
         "The adjective 'essential' collocates with 'for' or 'to'."),
    ]
    for stem, opts, exp in grammar_specs:
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Grammar and Vocabulary", "Core Academic Structures",
                "Apply inversion, reduced clauses, conditionals, and collocations", 1, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Section III · Grammar", section_id="sec-grammar",
            )
        )

    # 15..19: Dialogue & Paragraph Arrangement (5 câu)
    arrange_specs = [
        ("Arrange the turns to make a natural conversation:\na. Mai: Would you like to join our museum audio-guide project?\nb. Nam: That sounds great! When do we meet?\nc. Mai: Every Thursday afternoon in the media room.",
         ["a - b - c", "b - a - c", "c - a - b", "a - c - b"],
         "Invitation (a) -> acceptance and question (b) -> schedule answer (c)."),
        ("Arrange the turns to make a coherent exchange:\na. Teacher: Have you uploaded your lab summary yet?\nb. Minh: Yes, I submitted the PDF five minutes ago.\nc. Teacher: Thank you, I will review it before Friday.",
         ["a - b - c", "b - c - a", "c - b - a", "a - c - b"],
         "Question (a) -> confirmation (b) -> acknowledgment (c)."),
        ("Arrange the sentences into a cohesive short note about bicycle commuting:\na. First, dedicated bike lanes keep morning commuters separated from heavy trucks.\nb. Riding a bicycle to school benefits both personal fitness and air quality.\nc. In addition, covered racks near school gates protect bikes from sudden rain.\nd. Therefore, expanding safe cycling routes is a smart investment for towns.",
         ["b - a - c - d", "a - b - d - c", "d - b - a - c", "b - d - a - c"],
         "Topic sentence (b) -> supporting reasons (a, c) -> conclusion (d)."),
        ("Arrange the sentences to form a logical thank-you email:\na. Dear Dr. Linh, thank you for mentoring our robotics club this term.\nb. Your feedback on our sensor calibration helped us reach the regional finals.\nc. We would be honored to invite you to our showcase next Saturday.\nd. Best regards, Hoang Anh.",
         ["a - b - c - d", "b - a - c - d", "a - c - b - d", "d - a - b - c"],
         "Greeting & thanks (a) -> specific detail (b) -> invitation (c) -> sign-off (d)."),
        ("Arrange the sentences into an informational paragraph about wetlands:\na. As water slows down through dense reeds, suspended mud settles naturally.\nb. Freshwater wetlands filter agricultural runoff before it reaches main rivers.\nc. Consequently, downstream communities enjoy cleaner water and lower treatment costs.",
         ["b - a - c", "a - c - b", "c - b - a", "b - c - a"],
         "Claim (b) -> mechanism (a) -> consequence (c)."),
    ]
    for stem, opts, exp in arrange_specs:
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Discourse Arrangement", "Coherence and Cohesion",
                "Sequence conversational turns and paragraph sentences logically", 2, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Section IV · Arrangement", section_id="sec-arrangement",
            )
        )

    # 20..25: Cloze test [1]..[6] (6 câu, passageId #1 = "eng12-cloze-1")
    cloze_specs = [
        ("Select the conjunction for blank [1] linking soil preparation and rainwater barrels.", ["and", "but", "or", "yet"], "Parallel actions 'prepare soil beds and install rainwater barrels'."),
        ("Which correlative word completes '[2]' after 'not only fresh tomatoes'?", ["but", "so", "for", "nor"], "Correlative pair 'not only ... but also'."),
        ("Fill gap [3] before 'learn practical science lessons about composting'.", ["to", "for", "with", "from"], "Infinitive of purpose 'to learn practical lessons'."),
        ("Supply the grammatical determiner at [4] preceding 'benefits of rooftop farms'.", ["the", "a", "an", "one"], "Definite article 'the benefits' referring to specific garden gains."),
        ("Pick the subject relative pronoun needed at [5] referring to 'neighborhoods'.", ["that", "whom", "where", "what"], "Subject relative pronoun referring to 'neighborhoods'."),
        ("What adverb belongs in slot [6] before 'in densely populated districts'?", ["even", "hardly", "never", "neither"], "'even in densely populated districts' emphasizes contrast."),
    ]
    for idx, (stem, opts, exp) in enumerate(cloze_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Cloze Reading", "Urban Community Gardens",
                "Select grammatically and contextually accurate words for cloze blanks", 1, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Cloze Passage [1]..[6]",
                section_id="sec-cloze", passage_id="eng12-cloze-1",
                passage_title="Cloze Test: Urban Community Gardens [1]–[6]" if idx == 0 else None,
                passage_text=cloze_text if idx == 0 else None,
            )
        )

    # 26..32: Reading 1 (7 câu, passageId #2 = "eng12-reading-1")
    r1_specs = [
        ("What is the main idea of Reading Passage 1?",
         ["Public libraries are evolving into modern civic hubs while keeping quiet reading spaces.",
          "Public libraries have stopped lending printed books altogether.",
          "Teenagers only visit libraries when music concerts are held.",
          "Digital catalogs make human librarians unnecessary."],
         1, "Paragraph 1 explains that libraries reinvent themselves as civic hubs while preserving quiet study rooms."),
        ("According to Paragraph 1, which service can visitors now find at neighborhood libraries?",
         ["Soundproof booths for online interviews", "Free bicycle repair licenses", "Commercial restaurant kitchens", "Overnight hotel accommodation"],
         0, "Paragraph 1 explicitly mentions reserving soundproof booths for online interviews."),
        ("The word 'boosted' in Paragraph 2 is closest in meaning to which option?",
         ["increased", "delayed", "restricted", "canceled"],
         1, "Digital catalogs increased ('boosted') borrowing rates by helping readers find titles quickly."),
        ("What did the survey of twelve municipal branches show about teenagers?",
         ["They visited more when quiet zones coexisted with group tables.",
          "They refused to use digital search terminals.",
          "They preferred empty warehouses without tables.",
          "They only borrowed audio equipment on weekends."],
         1, "Teenagers visited most frequently when quiet reading zones were paired with collaborative tables."),
        ("In Paragraph 2, what enabled readers to locate niche titles within seconds?",
         ["Digital catalogs", "Soundproof booths", "Printed newspapers", "Civic permits"],
         1, "Digital catalogs allowed readers to locate niche titles within seconds."),
        ("Which role do modern librarians increasingly take on according to the last sentence?",
         ["Helping citizens verify online sources", "Designing building roofs", "Printing city tax forms", "Managing subway tickets"],
         1, "They act as information guides helping citizens verify online sources."),
        ("Which statement is TRUE according to Reading Passage 1?",
         ["Printed books remain actively borrowed alongside digital tools.",
          "All quiet study rooms were closed in the twelve branches.",
          "Digital literacy workshops charge high tuition fees.",
          "Readers wait several days to search digital catalogs."],
         2, "Paragraph 2 notes digital catalogs actually boosted borrowing of printed books."),
    ]
    for idx, (stem, opts, lvl, exp) in enumerate(r1_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Reading Comprehension 1", "Quiet Libraries in a Hyper-Connected World",
                "Identify main idea, vocabulary in context, and supporting facts", lvl, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Reading Passage 1",
                section_id="sec-reading-1", passage_id="eng12-reading-1",
                passage_title="Reading Passage 1: Quiet Libraries" if idx == 0 else None,
                passage_text=reading1_text if idx == 0 else None,
            )
        )

    # 33..40: Reading 2 (8 câu, passageId #3 = "eng12-reading-2")
    r2_specs = [
        ("What ecological function of mangrove forests is highlighted in Paragraph 1?",
         ["Absorbing storm waves and trapping river sediment",
          "Increasing salinity in freshwater wells",
          "Blocking ocean currents across deep trenches",
          "Preventing rainfall along tropical coasts"],
         1, "Paragraph 1 states mangroves absorb storm waves and trap river sediment."),
        ("What left coastal villages vulnerable to erosion between 1990 and 2010?",
         ["Clearing mangrove belts for pond construction", "Natural snowfall during winter", "Building too many offshore reefs", "Banning all local fishing boats"],
         1, "Rapid pond construction cleared wide belts of coastal trees."),
        ("In integrated mangrove-aquaculture systems, how much natural tree cover do farmers keep?",
         ["At least sixty percent", "Exactly ten percent", "Less than twenty percent", "Zero percent around channels"],
         0, "Farmers maintain at least sixty percent natural tree cover around tidal channels."),
        ("Why do shrimp and mud crabs thrive in these integrated channels?",
         ["They feed naturally on fallen mangrove leaves", "They receive imported synthetic pellets daily", "Water temperature stays frozen year-round", "Tidal channels are sealed off from sea water"],
         1, "They feed on fallen leaves without artificial chemical feeds."),
        ("The word 'buffers' in Paragraph 1 is closest in meaning to which term?",
         ["protective barriers", "pollution sources", "shipping harbors", "mineral deposits"],
         2, "'Living buffers' act as protective barriers absorbing storm waves."),
        ("What did five years of field measurements show about restored mangrove belts?",
         ["They cut wave energy nearly in half and stabilized incomes.",
          "They doubled coastal wave height during storms.",
          "They reduced household income compared with open ponds.",
          "They eliminated mud crabs from tidal estuaries."],
         2, "Wave energy fell by nearly half while household incomes became steadier."),
        ("What do planners emphasize as necessary for long-term program success?",
         ["Clear land-use agreements and joint monitoring", "Complete removal of local aquaculture", "Top-down fencing without village input", "Replacing mangroves with concrete walls"],
         2, "The final sentence cites clear land-use agreements and shared monitoring."),
        ("Which title best summarizes Reading Passage 2?",
         ["Balancing Coastal Protection and Aquaculture through Mangroves",
          "The Decline of Urban Rooftop Gardening",
          "How Offshore Reefs Form Deep Ocean Trenches",
          "Replacing Fishing Villages with Industrial Ports"],
         2, "The passage centers on mangrove restoration supporting both coastal protection and livelihoods."),
    ]
    for idx, (stem, opts, lvl, exp) in enumerate(r2_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(len(qs)))
        qs.append(
            mcq(
                f"sc06/q{len(qs) + 1}", "Reading Comprehension 2", "Coastal Mangrove Restoration",
                "Infer meaning, synthesize data, and summarize academic prose", lvl, 0.25,
                stem, p_opts, ans, exp, doc_id=did, location="Reading Passage 2",
                section_id="sec-reading-2", passage_id="eng12-reading-2",
                passage_title="Reading Passage 2: Coastal Mangrove Restoration" if idx == 0 else None,
                passage_text=reading2_text if idx == 0 else None,
            )
        )

    return build_exam(
        "SC-06",
        title="Đề thi thử tốt nghiệp THPT — Tiếng Anh 12 (GDPT 2018)",
        school="TRƯỜNG THPT CHU VĂN AN (MẪU)",
        department="Tổ Ngoại ngữ",
        subject="Tiếng Anh",
        grade="12",
        minutes=50,
        instructions="Read the questions carefully and choose the best option A, B, C, or D. Listening track allows at most 2 plays.",
        questions=qs,
        docs=[doc],
        mcq_columns=2,
    )


def _make_sc07() -> dict[str, Any]:
    """SC-07: KHTN 9 liên môn Lý–Hóa–Sinh (26 câu: 16 MCQ 4,0đ + 3 ĐS 3,0đ + 4 TLN 1,0đ + 3 TL 2,0đ)."""
    doc = make_doc(
        "sc07/doc",
        "Tu_lieu_KHTN_9_lien_mon.txt",
        "Tư liệu KHTN 9 tự biên soạn gồm 3 phân môn: Vật lí (Quang, Điện, Năng lượng), Hóa học (Kim loại, Phi kim, Hữu cơ), Sinh học (Di truyền Mendel, ADN).",
    )
    did = doc["id"]
    qs: list[dict[str, Any]] = []
    mcq_specs = [
        # 6 Lý
        ("Năng lượng cơ học", "Lý 9 · Động năng và thế năng", "Tính động năng của vật chuyển động", 0, "phan-vat-li",
         r"Một vật khối lượng $m = 2{,}0\text{ kg}$ chuyển động với tốc độ $v = 3{,}0\text{ m/s}$. Động năng của vật bằng bao nhiêu?",
         [r"$9{,}0\text{ J}$", r"$6{,}0\text{ J}$", r"$18{,}0\text{ J}$", r"$4{,}5\text{ J}$"], r"$W_{\text{đ}} = \frac{1}{2}mv^2 = 0{,}5 \cdot 2 \cdot 9 = 9{,}0\text{ J}$."),
        ("Quang học", "Lý 9 · Khúc xạ ánh sáng", "Nhận biết chiết suất tuyệt đối", 0, "phan-vat-li",
         "Khi tia sáng truyền xiên góc từ không khí vào thủy tinh thì góc khúc xạ có đặc điểm nào so với góc tới?",
         ["Nhỏ hơn góc tới", "Lớn hơn góc tới", "Luôn bằng $90^\\circ$", "Bằng góc tới"], "Do chiết suất thủy tinh lớn hơn không khí nên tia khúc xạ lệch gần pháp tuyến hơn."),
        ("Quang học", "Lý 9 · Thấu kính hội tụ", "Nhận biết tính chất ảnh vật ngoài tiêu cự", 1, "phan-vat-li",
         r"Đặt vật sáng nhỏ vuông góc với trục chính của thấu kính hội tụ tiêu cự $f = 15\text{ cm}$, cách thấu kính $40\text{ cm}$. Ảnh thu được có tính chất gì?",
         ["Ảnh thật, ngược chiều, nhỏ hơn vật", "Ảnh ảo, cùng chiều, lớn hơn vật", "Ảnh thật, ngược chiều, lớn hơn vật", "Ảnh ảo, ngược chiều, bằng vật"], "Vì $d > 2f$ nên cho ảnh thật ngược chiều và nhỏ hơn vật."),
        ("Điện học", "Lý 9 · Định luật Ohm", "Tính điện trở dây dẫn", 0, "phan-vat-li",
         r"Đặt hiệu điện thế $U = 12\text{ V}$ vào hai đầu điện trở $R$ thì dòng điện qua nó là $0{,}6\text{ A}$. Giá trị của $R$ bằng bao nhiêu?",
         [r"$20\,\Omega$", r"$7{,}2\,\Omega$", r"$12\,\Omega$", r"$2\,\Omega$"], r"$R = \frac{U}{I} = \frac{12}{0{,}6} = 20\,\Omega$."),
        ("Điện học", "Lý 9 · Đoạn mạch nối tiếp", "Tính điện trở tương đương nối tiếp", 1, "phan-vat-li",
         r"Hai điện trở $R_1 = 8\,\Omega$ và $R_2 = 12\,\Omega$ mắc nối tiếp với nhau. Điện trở tương đương của đoạn mạch bằng?",
         [r"$20\,\Omega$", r"$4{,}8\,\Omega$", r"$4\,\Omega$", r"$96\,\Omega$"], r"$R_{\text{nt}} = R_1 + R_2 = 20\,\Omega$."),
        ("Điện từ", "Lý 9 · Truyền tải điện năng", "Giảm hao phí bằng tăng điện áp", 1, "phan-vat-li",
         "Khi tăng hiệu điện thế ở nơi phát điện lên $5$ lần (giữ nguyên công suất phát và điện trở dây), công suất hao phí do tỏa nhiệt trên đường dây thay đổi như thế nào?",
         ["Giảm đi $25$ lần", "Giảm đi $5$ lần", "Tăng lên $25$ lần", "Tăng lên $5$ lần"], r"$P_{\text{hp}} = \frac{P^2 R}{U^2}$ tỉ lệ nghịch với $U^2$."),
        # 5 Hóa
        ("Kim loại", "Hóa 9 · Dãy hoạt động hóa học", "Phân biệt kim loại phản ứng được với HCl", 0, "phan-hoa-hoc",
         r"Kim loại nào sau đây không tác dụng với dung dịch $\ce{HCl}$ loãng ở điều kiện thường?",
         [r"$\ce{Cu}$", r"$\ce{Zn}$", r"$\ce{Fe}$", r"$\ce{Mg}$"], r"Đồng đứng sau hiđro trong dãy hoạt động hóa học của kim loại."),
        ("Kim loại", "Hóa 9 · Tính chất vật lí kim loại", "Nhận biết kim loại dẫn điện tốt nhất", 0, "phan-hoa-hoc",
         "Trong các kim loại sau, kim loại nào dẫn điện tốt nhất ở nhiệt độ phòng?",
         ["Bạc ($\\ce{Ag}$)", "Sắt ($\\ce{Fe}$)", "Chì ($\\ce{Pb}$)", "Thủy ngân ($\\ce{Hg}$)"], "Thứ tự dẫn điện tốt nhất là $\\ce{Ag} > \\ce{Cu} > \\ce{Au} > \\ce{Al} > \\ce{Fe}$."),
        ("Hợp chất hữu cơ", "Hóa 9 · Etilen và nhiên liệu", "Nhận biết phản ứng trùng hợp etilen", 1, "phan-hoa-hoc",
         r"Sản phẩm thu được khi thực hiện phản ứng trùng hợp monome $\ce{CH2=CH2}$ là polime nào?",
         ["Polietilen (PE)", "Polipropilen (PP)", "Polistiren (PS)", "Tinh bột"], r"$n\ce{CH2=CH2 ->[t^o, xt, p] (-CH2-CH2-)_n}$."),
        ("Hợp chất hữu cơ", "Hóa 9 · Rượu etylic", "Xác định nhóm nguyên tử đặc trưng của etanol", 0, "phan-hoa-hoc",
         r"Độ rượu $40^\circ$ có nghĩa là trong $100\text{ mL}$ dung dịch rượu etylic có chứa bao nhiêu mL rượu etylic nguyên chất?",
         [r"$40\text{ mL}$", r"$60\text{ mL}$", r"$40\text{ g}$", r"$20\text{ mL}$"], "Độ rượu là số mL etanol nguyên chất trong $100\\text{ mL}$ hỗn hợp rượu và nước."),
        ("Hợp chất hữu cơ", "Hóa 9 · Axit axetic", "Phản ứng este hóa giữa CH3COOH và C2H5OH", 1, "phan-hoa-hoc",
         r"Đun nóng axit axetic với rượu etylic có mặt $\ce{H2SO4}$ đặc làm xúc tác thu được este nào?",
         [r"$\ce{CH3COOC2H5}$", r"$\ce{HCOOC2H5}$", r"$\ce{C2H5COOCH3}$", r"$\ce{CH3COOCH3}$"], r"$\ce{CH3COOH + C2H5OH <=> CH3COOC2H5 + H2O}$."),
        # 5 Sinh
        ("Di truyền Mendel", "Sinh 9 · Quy luật phân li", "Xác định tỉ lệ kiểu hình F2 phép lai một cặp", 0, "phan-sinh-hoc",
         "Theo quy luật phân li của Mendel, khi cho $F_1$ dị hợp một cặp gen ($Aa \\times Aa$, trội hoàn toàn) tự thụ phấn thì đời $F_2$ có tỉ lệ kiểu hình là?",
         ["$3$ trội : $1$ lặn", "$1$ trội : $1$ lặn", "$1$ trội : $2$ trung gian : $1$ lặn", "$9 : 3 : 3 : 1$"], "Tổ hợp kiểu gen $1AA : 2Aa : 1aa$ cho tỉ lệ kiểu hình $3$ trội : $1$ lặn."),
        ("Cơ sở vật chất di truyền", "Sinh 9 · Cấu trúc ADN", "Nguyên tắc bổ sung trong phân tử ADN", 0, "phan-sinh-hoc",
         "Trong phân tử ADN mạch kép, các nuclêôtit giữa hai mạch liên kết với nhau theo nguyên tắc bổ sung như thế nào?",
         ["$A$ liên kết $T$, $G$ liên kết $X$", "$A$ liên kết $U$, $G$ liên kết $X$", "$A$ liên kết $G$, $T$ liên kết $X$", "$A$ liên kết $X$, $G$ liên kết $T$"], "Trên ADN mạch kép có $A=T$ và $G=X$."),
        ("Cơ sở vật chất di truyền", "Sinh 9 · Phiên mã mARN", "Nhận biết đơn phân cấu tạo ARN", 1, "phan-sinh-hoc",
         "Loại đơn phân nào chỉ có ở phân tử ARN mà không có trong phân tử ADN?",
         ["Uraxin ($U$)", "Timin ($T$)", "Ađênin ($A$)", "Guanin ($G$)"], "ARN gồm $A, U, G, X$, thay $T$ bằng $U$."),
        ("Di truyền Mendel", "Sinh 9 · Lai hai cặp tính trạng", "Đếm số loại kiểu hình phép lai phân li độc lập", 1, "phan-sinh-hoc",
         "Cho phép lai hai cơ thể dị hợp hai cặp gen phân li độc lập $AaBb \\times AaBb$ (trội hoàn toàn). Số loại kiểu hình tối đa ở đời con là?",
         ["$4$", "$9$", "$16$", "$2$"], "Mỗi cặp tính trạng cho $2$ kiểu hình nên hai cặp cho $2 \\times 2 = 4$ kiểu hình."),
        ("Ứng dụng di truyền", "Sinh 9 · Đột biến số lượng NST", "Phân biệt thể dị bội và đa bội", 1, "phan-sinh-hoc",
         "Tế bào sinh dưỡng của một loài thực vật có bộ nhiễm sắc thể lưỡng bội $2n = 14$. Thể ba ($2n + 1$) của loài này có số lượng nhiễm sắc thể là?",
         ["$15$", "$21$", "$13$", "$28$"], "Thể ba có $2n + 1 = 14 + 1 = 15$ nhiễm sắc thể."),
    ]
    for idx, (top, les, comp, lvl, sec, stem, opts, exp) in enumerate(mcq_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc07/q{idx + 1}", top, les, comp, lvl, 0.25, stem, p_opts, ans, exp,
                doc_id=did, location=f"Phần I · {sec}", section_id=sec,
            )
        )

    # 3 Đúng-Sai (Lý, Hóa, Sinh mỗi phần 1 câu × 1.0đ = 3.0đ)
    qs.append(
        tf(
            "sc07/q17", "Điện học", "Lý 9 · Công suất điện", "Tính điện năng tiêu thụ và cường độ định mức", 2, 1.0,
            "Một ấm điện ghi $220\\text{ V} - 1100\\text{ W}$ được sử dụng đúng hiệu điện thế $220\\text{ V}$ trong $10$ phút mỗi ngày. Xét các nhận định:",
            [
                "a) Cường độ dòng điện chạy qua ấm khi hoạt động bình thường là $5\\text{ A}$.",
                "b) Điện trở của dây nung trong ấm là $44\\,\\Omega$.",
                "c) Điện năng ấm tiêu thụ trong $10$ phút là $660\\text{ kJ}$.",
                "d) Trong $30$ ngày, số tiền điện phải trả ở mức $2000$ đồng/kWh là $20\\,000$ đồng.",
            ],
            [True, True, True, False],
            "a) $I = 1100/220 = 5\\text{ A}$. b) $R = 220/5 = 44\\,\\Omega$. c) $A = 1100 \\cdot 600 = 660\\,000\\text{ J}$. d) $30$ ngày tiêu thụ $1{,}1 \\cdot \\frac{10}{60} \\cdot 30 = 5{,}5\\text{ kWh}$, tiền điện $11\\,000$ đồng.",
            doc_id=did, location="Phần II · Vật lí", section_id="phan-vat-li",
        )
    )
    qs.append(
        tf(
            "sc07/q18", "Kim loại", "Hóa 9 · Sắt tác dụng muối đồng", "Đánh giá phản ứng đẩy kim loại và tăng giảm khối lượng", 2, 1.0,
            r"Ngâm một đinh sắt sạch nặng $10{,}0\text{ g}$ vào dung dịch $\ce{CuSO4}$ dư, sau một thời gian thấy có $0{,}05\text{ mol}$ $\ce{Fe}$ đã phản ứng. Xét các mệnh đề:",
            [
                r"a) Phương trình hóa học xảy ra là $\ce{Fe + CuSO4 -> FeSO4 + Cu}$.",
                r"b) Khối lượng đồng sinh ra bám lên đinh sắt là $3{,}2\text{ g}$.",
                "c) Màu xanh của dung dịch nhạt dần trong quá trình phản ứng.",
                "d) Khối lượng thanh kim loại lấy ra nặng nhỏ hơn $10{,}0\text{ g}$.",
            ],
            [True, True, True, False],
            r"a, b, c) Đúng ($m_{\ce{Cu}} = 0{,}05 \cdot 64 = 3{,}2\text{ g}$). d) Sai: thanh sắt tăng thêm $0{,}05 \cdot (64 - 56) = 0{,}4\text{ g}$ thành $10{,}4\text{ g}$.",
            doc_id=did, location="Phần II · Hóa học", section_id="phan-hoa-hoc",
        )
    )
    qs.append(
        tf(
            "sc07/q19", "Cơ sở vật chất di truyền", "Sinh 9 · Bảng thành phần nuclêôtit ADN", "Phân tích bảng số liệu nuclêôtit trong gen", 2, 1.0,
            "Một đoạn gen mạch kép có tổng số $2400$ nuclêôtit, kết quả phân tích một số loại nuclêôtit được ghi ở bảng kèm theo. Xét các khẳng định:",
            [
                "a) Số nuclêôtit loại T của đoạn gen là $480$.",
                "b) Số nuclêôtit loại G bằng $720$.",
                "c) Chiều dài của đoạn gen trên bằng $4080\\text{ \u00c5}$ ($408\\text{ nm}$).",
                "d) Số liên kết hiđrô của đoạn gen trên bằng $2880$.",
            ],
            [True, True, True, False],
            "Tổng $N = 2400$: $A = T = 480$ ($20\\%$), $G = X = 720$ ($30\\%$). Chiều dài $L = \\frac{2400}{2} \\cdot 3{,}4 = 4080\\text{ \u00c5}$. Số liên kết H là $2A + 3G = 960 + 2160 = 3120$.",
            doc_id=did, location="Phần II · Sinh học",
            tables=[{"rows": [["Loại nuclêôtit", "A", "T", "G", "X"], ["Tỉ lệ (%)", "20%", "?", "?", "30%"]]}],
            section_id="phan-sinh-hoc",
        )
    )

    # 4 Trả lời ngắn (0.25đ × 4 = 1.0đ)
    short_specs = [
        ("Năng lượng cơ học", "Lý 9 · Thế năng trọng trường", "Tính thế năng trọng trường", 1, "phan-vat-li",
         r"Một quả cầu khối lượng $0{,}5\text{ kg}$ được giữ ở độ cao $4\text{ m}$ so với mặt đất ($g = 10\text{ m/s}^2$). Thế năng trọng trường của quả cầu bằng bao nhiêu jun?", "20",
         r"$W_{\text{t}} = mgh = 0{,}5 \cdot 10 \cdot 4 = 20\text{ J}$."),
        ("Kim loại", "Hóa 9 · Nhôm tác dụng với axit", "Tính thể tích khí H2 sinh ra", 1, "phan-hoa-hoc",
         r"Hòa tan $5{,}4\text{ g}$ bột nhôm ($\ce{Al} = 27$) trong dung dịch $\ce{HCl}$ dư. Số mol khí $\ce{H2}$ thu được bằng bao nhiêu?", "0,3",
         r"$n_{\ce{Al}} = 0{,}2\text{ mol} \Rightarrow n_{\ce{H2}} = 1{,}5 \cdot 0{,}2 = 0{,}3\text{ mol}$."),
        ("Hợp chất hữu cơ", "Hóa 9 · Đốt cháy rượu etylic", "Tính số mol CO2 đốt cháy etanol", 2, "phan-hoa-hoc",
         r"Đốt cháy hoàn toàn $0{,}25\text{ mol}$ $\ce{C2H5OH}$ thu được bao nhiêu mol khí $\ce{CO2}$?", "0,5",
         r"$\ce{C2H5OH + 3O2 -> 2CO2 + 3H2O} \Rightarrow n_{\ce{CO2}} = 0{,}5\text{ mol}$."),
        ("Di truyền Mendel", "Sinh 9 · Xác suất di truyền", "Tính tỉ lệ đồng hợp lặn", 2, "phan-sinh-hoc",
         "Ở phép lai $Aa \\times Aa$ (trội hoàn toàn), tỉ lệ cây mang kiểu gen đồng hợp lặn ở đời con bằng bao nhiêu phần trăm?", "25",
         "Kiểu gen $aa$ chiếm $\\frac{1}{4} = 25\\%$."),
    ]
    for idx, (top, les, comp, lvl, sec, stem, ans_txt, exp) in enumerate(short_specs, 20):
        qs.append(
            short_q(
                f"sc07/q{idx}", top, les, comp, lvl, 0.25, stem, ans_txt, exp,
                doc_id=did, location=f"Phần III · {sec}", section_id=sec,
            )
        )

    # 3 Tự luận liên môn Lý (0.75đ) + Hóa (0.75đ) + Sinh (0.50đ) = 2.00đ
    qs.append(
        essay(
            "sc07/q24", "Điện học", "Lý 9 · Mạch điện hỗn hợp", "Tính điện trở và công suất đoạn mạch song song", 2, 0.75,
            r"Cho hai điện trở $R_1 = 6\,\Omega$ và $R_2 = 12\,\Omega$ mắc song song vào nguồn có hiệu điện thế không đổi $U = 12\text{ V}$. Tính điện trở tương đương của đoạn mạch và cường độ dòng điện qua mạch chính.",
            r"$R_{\text{ss}} = \frac{6 \cdot 12}{6 + 12} = 4\,\Omega$; $I = \frac{U}{R_{\text{ss}}} = \frac{12}{4} = 3\text{ A}$.",
            [
                (r"Tính đúng điện trở tương đương $R_{\text{ss}} = \frac{R_1 R_2}{R_1 + R_2} = 4\,\Omega$", 0.5),
                (r"Tính đúng cường độ dòng điện mạch chính $I = \frac{12}{4} = 3\text{ A}$", 0.25),
            ],
            doc_id=did, location="Phần IV · Vật lí", section_id="phan-vat-li",
        )
    )
    qs.append(
        essay(
            "sc07/q25", "Hợp chất hữu cơ", "Hóa 9 · Axit axetic tác dụng muối cacbonat", "Tính khối lượng muối và thể tích CO2", 2, 0.75,
            r"Cho $100\text{ g}$ dung dịch $\ce{CH3COOH}$ $12\%$ tác dụng vừa đủ với bột $\ce{CaCO3}$. Viết phương trình hóa học và tính khối lượng $\ce{CaCO3}$ đã phản ứng.",
            r"$n_{\ce{CH3COOH}} = \frac{12}{60} = 0{,}2\text{ mol}$. Theo $\ce{2CH3COOH + CaCO3 -> (CH3COO)2Ca + CO2 + H2O}$, $n_{\ce{CaCO3}} = 0{,}1\text{ mol} \Rightarrow m = 10{,}0\text{ g}$.",
            [
                (r"Viết đúng phương trình phản ứng và tính $n_{\ce{CH3COOH}} = 0{,}2\text{ mol}$", 0.5),
                (r"Tính được $n_{\ce{CaCO3}} = 0{,}1\text{ mol}$ và $m = 10{,}0\text{ g}$", 0.25),
            ],
            doc_id=did, location="Phần IV · Hóa học", section_id="phan-hoa-hoc",
        )
    )
    qs.append(
        essay(
            "sc07/q26", "Di truyền Mendel", "Sinh 9 · Lai phân tích", "Giải thích mục đích và kết quả phép lai phân tích", 1, 0.5,
            "Trình bày khái niệm phép lai phân tích và viết sơ đồ lai khi cho cây đậu hoa đỏ dị hợp ($Aa$) lai phân tích.",
            "Lai phân tích là phép lai giữa cá thể mang tính trạng trội cần xác định kiểu gen với cá thể đồng hợp lặn. P: $Aa$ (hoa đỏ) $\\times$ $aa$ (hoa trắng) $\\to F_1$: $1Aa : 1aa$ ($50\\%$ đỏ : $50\\%$ trắng).",
            [
                ("Nêu đúng khái niệm và ý nghĩa của phép lai phân tích", 0.25),
                ("Viết đúng sơ đồ lai $Aa \\times aa \\to 1Aa : 1aa$ ($1$ đỏ : $1$ trắng)", 0.25),
            ],
            doc_id=did, location="Phần IV · Sinh học", section_id="phan-sinh-hoc",
        )
    )

    return build_exam(
        "SC-07",
        title="Đề kiểm tra cuối năm — Khoa học tự nhiên 9 (Liên môn Lý–Hóa–Sinh)",
        school="TRƯỜNG THCS HÒA BÌNH (MẪU)",
        department="Tổ Khoa học Tự nhiên",
        subject="Khoa học tự nhiên",
        grade="9",
        minutes=90,
        instructions="Học sinh làm 26 câu hỏi gồm 3 phân môn Vật lí, Hóa học và Sinh học.",
        questions=qs,
        docs=[doc],
    )


def _make_sc08() -> dict[str, Any]:
    """SC-08: Lịch sử & Địa lí 9 (24 câu, 2 nhánh choiceGroup + bảng dữ kiện dataLinked)."""
    doc = make_doc(
        "sc08/doc",
        "Tu_lieu_Lich_su_Dia_li_9.txt",
        "Tư liệu tự biên soạn Lịch sử và Địa lí 9: Thế giới và Việt Nam từ 1945 đến nay; "
        "Địa lí dân cư, vùng kinh tế trọng điểm và Bảng 1 sản lượng thủy sản nuôi trồng theo vùng.",
    )
    did = doc["id"]
    linked_data = [
        {"label": "Đồng bằng sông Cửu Long", "value": 3650},
        {"label": "Đồng bằng sông Hồng", "value": 920},
        {"label": "Bắc Trung Bộ", "value": 410},
        {"label": "Duyên hải Nam Trung Bộ", "value": 340},
    ]
    qs: list[dict[str, Any]] = []
    # Phần chung: 16 câu = 12 MCQ (0.25=3.0) + 2 TF (1.0=2.0) + 2 Short (0.5=1.0) = 6.00đ
    common_mcq = [
        ("Lịch sử thế giới hiện đại", "LS 9 · Trật tự thế giới sau 1945", "Nhận biết mục tiêu tổ chức Liên hợp quốc", 0,
         "Một trong những mục tiêu hàng đầu được nêu trong Hiến chương Liên hợp quốc năm 1945 là gì?",
         ["Duy trì hòa bình và an ninh quốc tế", "Thành lập liên minh quân sự đơn phương", "Thiết lập một đồng tiền chung toàn cầu", "Chia lại thuộc địa giữa các nước thắng trận"],
         "Hiến chương Liên hợp quốc đề cao việc duy trì hòa bình, an ninh quốc tế và hợp tác bình đẳng."),
        ("Lịch sử Việt Nam 1945–1975", "LS 9 · Cách mạng tháng Tám", "Nhận biết sự kiện thành lập nước Việt Nam Dân chủ Cộng hòa", 0,
         "Ngày 2/9/1945 tại Quảng trường Ba Đình (Hà Nội), Chủ tịch Hồ Chí Minh đã đọc văn kiện lịch sử nào?",
         ["Tuyên ngôn Độc lập", "Lời kêu gọi toàn quốc kháng chiến", "Chính cương vắn tắt", "Cương lĩnh tháng Mười"],
         "Ngày 2/9/1945, Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập khai sinh nước Việt Nam Dân chủ Cộng hòa."),
        ("Lịch sử Việt Nam 1945–1975", "LS 9 · Kháng chiến chống Pháp", "Nhận biết ý nghĩa chiến dịch Điện Biên Phủ", 0,
         "Chiến thắng Điện Biên Phủ năm 1954 đã dẫn trực tiếp tới việc kí kết văn bản ngoại giao nào?",
         ["Hiệp định Giơ-ne-vơ về Đông Dương", "Hiệp định Pa-ri về Việt Nam", "Hiệp ước Nhâm Tuất", "Hiệp ước Pốt-xđam"],
         "Sau Điện Biên Phủ, Hiệp định Giơ-ne-vơ được kí ngày 21/7/1954."),
        ("Lịch sử Việt Nam 1975–nay", "LS 9 · Công cuộc Đổi mới 1986", "Nhận biết dấu mốc mở đầu Đổi mới", 0,
         "Đường lối Đổi mới đất nước ở Việt Nam được đề ra đầu tiên tại Đại hội đại biểu toàn quốc lần thứ mấy của Đảng Cộng sản Việt Nam?",
         ["Đại hội lần thứ VI (năm 1986)", "Đại hội lần thứ IV (năm 1976)", "Đại hội lần thứ V (năm 1982)", "Đại hội lần thứ VII (năm 1991)"],
         "Đại hội VI (12/1986) khởi xướng công cuộc Đổi mới toàn diện."),
        ("Lịch sử thế giới hiện đại", "LS 9 · Hiệp hội ASEAN", "Nhận biết năm Việt Nam gia nhập ASEAN", 0,
         "Việt Nam chính thức trở thành thành viên thứ 7 của Hiệp hội các quốc gia Đông Nam Á (ASEAN) vào năm nào?",
         ["Năm 1995", "Năm 1967", "Năm 1986", "Năm 2007"],
         "Việt Nam gia nhập ASEAN ngày 28/7/1995."),
        ("Lịch sử Việt Nam 1945–1975", "LS 9 · Kháng chiến chống Mỹ", "Nhận biết kết quả Hiệp định Pa-ri 1973", 1,
         "Nội dung quan trọng nào được ghi nhận trong Hiệp định Pa-ri năm 1973 về Việt Nam?",
         ["Hoa Kỳ cam kết tôn trọng độc lập, chủ quyền và rút hết quân viễn chinh", "Chia cắt lâu dài hai miền Nam – Bắc Việt Nam", "Quân đồng minh tiếp tục đóng quân tại miền Nam", "Thành lập liên bang Đông Dương mới"],
         "Hiệp định Pa-ri (27/1/1973) buộc Hoa Kỳ và các nước cam kết tôn trọng độc lập, thống nhất và rút quân."),
        ("Địa lí dân cư Việt Nam", "ĐL 9 · Phân bố dân cư", "Nhận biết vùng có mật độ dân số cao nhất", 0,
         "Vùng nào của Việt Nam hiện nay có mật độ dân số cao nhất cả nước?",
         ["Đồng bằng sông Hồng", "Tây Nguyên", "Trung du và miền núi Bắc Bộ", "Bắc Trung Bộ"],
         "Đồng bằng sông Hồng có mật độ dân số cao nhất nhờ địa hình bằng phẳng và lịch sử khai thác lâu đời."),
        ("Địa lí các ngành kinh tế", "ĐL 9 · Nông – lâm – thủy sản", "Nhận biết thế mạnh cây công nghiệp Tây Nguyên", 0,
         "Loại cây công nghiệp lâu năm nào chiếm diện tích lớn nhất và là mặt hàng xuất khẩu chủ lực của vùng Tây Nguyên?",
         ["Cà phê", "Đay và cói", "Dừa nước", "Mía đường ôn đới"],
         "Đất badan màu mỡ cùng khí hậu cận xích đạo giúp Tây Nguyên dẫn đầu cả nước về cà phê."),
        ("Địa lí các ngành kinh tế", "ĐL 9 · Giao thông vận tải", "Phân biệt vai trò tuyến đường sắt Bắc – Nam", 1,
         "Loại hình vận tải nào giữ vai trò chủ đạo trong việc chuyên chở hàng hóa xuất nhập khẩu đường biển quốc tế của nước ta?",
         ["Đường biển", "Đường sông nội địa", "Đường ống dẫn khí", "Đường sắt đô thị"],
         "Đường biển có khối lượng luân chuyển lớn và phù hợp giao thương quốc tế."),
        ("Địa lí các vùng kinh tế", "ĐL 9 · Vùng Đông Nam Bộ", "Xác định đặc điểm kinh tế Đông Nam Bộ", 1,
         "Yếu tố nào thúc đẩy Đông Nam Bộ trở thành vùng dẫn đầu cả nước về thu hút đầu tư và giá trị sản xuất công nghiệp?",
         ["Vị trí cửa ngõ kinh tế, hạ tầng phát triển và nguồn lao động dồi dào", "Diện tích đất phù sa ngọt lớn nhất cả nước", "Trữ lượng than đá tập trung lớn nhất cả nước", "Khí hậu ôn hòa có mùa đông lạnh kéo dài"],
         "Đông Nam Bộ hội tụ lợi thế vị trí, cảng biển, sân bay và nhân lực kỹ thuật cao."),
        ("Địa lí các vùng kinh tế", "ĐL 9 · Vùng Trung du và miền núi Bắc Bộ", "Nhận biết thế mạnh thủy điện", 1,
         "Nhà máy thủy điện Sơn La và Hòa Bình được xây dựng trên hệ thống sông nào của nước ta?",
         ["Sông Đà (hệ thống sông Hồng)", "Sông Tiền (hệ thống sông Mê Kông)", "Sông Đồng Nai", "Sông Thu Bồn"],
         "Các bậc thang thủy điện lớn Hòa Bình, Sơn La, Lai Châu đều nằm trên sông Đà."),
        ("Địa lí thủy sản Việt Nam", "ĐL 9 · Đọc bảng dữ kiện Bảng 1", "Xác định vùng đứng đầu từ Bảng 1 dữ kiện liên kết", 0,
         "Theo Bảng 1 (số liệu giả định đơn vị nghìn tấn), vùng nào có sản lượng thủy sản nuôi trồng cao nhất?",
         ["Đồng bằng sông Cửu Long", "Đồng bằng sông Hồng", "Bắc Trung Bộ", "Duyên hải Nam Trung Bộ"],
         "Từ Bảng 1, Đồng bằng sông Cửu Long đạt 3650 nghìn tấn, cao nhất trong bốn vùng."),
    ]
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(common_mcq):
        if idx == 11:
            # Câu rule="max" giữ Đồng bằng sông Cửu Long tại vị trí A hoặc B, khớp answer
            p_opts, ans = _permute_options(opts, 1)
        else:
            p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc08/q{idx + 1}", top, les, comp, lvl, 0.25, stem, p_opts, ans, exp,
                doc_id=did, location="Phần chung · Trắc nghiệm", section_id="phan-chung",
                data_linked=(idx == 11), rule=("max" if idx == 11 else None),
            )
        )

    qs.append(
        tf(
            "sc08/q13", "Lịch sử Việt Nam 1975–nay", "LS 9 · Thành tựu Đổi mới", "Đánh giá thành tựu hội nhập kinh tế từ 1986", 1, 1.0,
            "Dựa vào tư liệu về công cuộc Đổi mới ở Việt Nam từ năm 1986 đến nay, xét các nhận định sau:",
            [
                "a) Việt Nam chuyển từ cơ chế tập trung bao cấp sang kinh tế thị trường định hướng xã hội chủ nghĩa.",
                "b) Từ nước thiếu lương thực, Việt Nam đã vươn lên trở thành một trong các nước xuất khẩu gạo hàng đầu.",
                "c) Chính sách đối ngoại Đổi mới là khép kín, hạn chế giao lưu quốc tế.",
                "d) Gia nhập WTO năm 2007 mở rộng thị trường xuất khẩu cho hàng hóa Việt Nam.",
            ],
            [True, True, False, True],
            "a, b, d) Đúng. c) Sai: đường lối đối ngoại là đa phương hóa, đa dạng hóa và chủ động hội nhập quốc tế.",
            doc_id=did, location="Phần chung · Câu 13", section_id="phan-chung",
        )
    )
    qs.append(
        tf(
            "sc08/q14", "Địa lí các vùng kinh tế", "ĐL 9 · Đồng bằng sông Cửu Long", "Phân tích thách thức biến đổi khí hậu tại ĐBSCL", 2, 1.0,
            "Quan sát các đặc điểm tự nhiên và kinh tế vùng Đồng bằng sông Cửu Long, xét các khẳng định sau:",
            [
                "a) Là vùng trọng điểm sản xuất lúa gạo và nuôi trồng thủy sản lớn nhất cả nước.",
                "b) Biến đổi khí hậu làm gia tăng nguy cơ xâm nhập mặn vào mùa khô.",
                "c) Khoảng cách từ vùng tới thị trường quốc tế không bị ảnh hưởng bởi mùa lũ.",
                "d) Phục hồi rừng ngập mặn ven biển góp phần bảo vệ đê điều trước nước biển dâng.",
            ],
            [True, True, False, True],
            "a, b, d) Đúng. c) Sai: mùa khô thiếu nước ngọt gây xâm nhập mặn và mùa lũ ảnh hưởng trực tiếp tới mùa vụ, vận tải thủy.",
            doc_id=did, location="Phần chung · Câu 14", section_id="phan-chung",
        )
    )
    qs.append(
        short_q(
            "sc08/q15", "Địa lí thủy sản Việt Nam", "ĐL 9 · So sánh số liệu Bảng 1", "Tính hiệu sản lượng giữa hai vùng dẫn đầu ở Bảng 1", 2, 0.5,
            "Theo Bảng 1 dữ kiện liên kết, sản lượng của Đồng bằng sông Cửu Long nhiều hơn Đồng bằng sông Hồng bao nhiêu nghìn tấn?",
            "2730",
            "Từ Bảng 1: $3650 - 920 = 2730$ nghìn tấn.",
            doc_id=did, location="Phần chung · Câu 15", section_id="phan-chung", data_linked=True,
        )
    )
    qs.append(
        short_q(
            "sc08/q16", "Lịch sử Việt Nam 1945–1975", "LS 9 · Mốc thời gian thống nhất", "Xác định năm hoàn thành giải phóng miền Nam", 0, 0.5,
            "Cuộc Tổng tiến công và nổi dậy mùa Xuân giải phóng hoàn toàn miền Nam, thống nhất đất nước diễn ra vào năm nào?",
            "1975",
            "Chiến dịch Hồ Chí Minh toàn thắng vào ngày 30/4/1975.",
            doc_id=did, location="Phần chung · Câu 16", section_id="phan-chung",
        )
    )

    # Nhánh 1: Phân môn Lịch sử (4 câu = 2 MCQ×0.5 + 2 Essay×1.5 = 4.0đ)
    qs.append(
        mcq(
            "sc08/q17", "Chuyên đề Lịch sử 9", "LS 9 · Hội nghị thành lập Đảng", "Xác định người chủ trì hội nghị hợp nhất 1930", 0, 0.5,
            "Hội nghị hợp nhất các tổ chức cộng sản thành Đảng Cộng sản Việt Nam đầu năm 1930 do ai chủ trì?",
            *_permute_options(["Nguyễn Ái Quốc", "Trần Phú", "Lê Hồng Phong", "Hà Huy Tập"], _ans_cycle(12)),
            "Nguyễn Ái Quốc triệu tập và chủ trì Hội nghị hợp nhất tại Cửu Long (Hương Cảng).",
            doc_id=did, location="Nhánh Lịch sử · Câu 17", section_id="nhanh-lich-su", choice_group="Phân môn Lịch sử",
        )
    )
    qs.append(
        mcq(
            "sc08/q18", "Chuyên đề Lịch sử 9", "LS 9 · Đường lối toàn quốc kháng chiến", "Nhận biết phương châm kháng chiến chống Pháp", 1, 0.5,
            "Đường lối kháng chiến chống thực dân Pháp giai đoạn 1946–1954 mang tính chất nào sau đây?",
            *_permute_options(["Toàn dân, toàn diện, trường kì, tự lực cánh sinh", "Chỉ đánh nhanh thắng nhanh ở đô thị", "Chủ yếu dựa vào lực lượng ngoại viện", "Chỉ đấu tranh trên mặt trận ngoại giao"], _ans_cycle(13)),
            "Đường lối xuyên suốt là kháng chiến toàn dân, toàn diện, lâu dài và tự lực cánh sinh.",
            doc_id=did, location="Nhánh Lịch sử · Câu 18", section_id="nhanh-lich-su", choice_group="Phân môn Lịch sử",
        )
    )
    qs.append(
        essay(
            "sc08/q19", "Chuyên đề Lịch sử 9", "LS 9 · Cách mạng tháng Tám", "Phân tích nguyên nhân thắng lợi của Cách mạng tháng Tám", 2, 1.5,
            "Phân tích những nguyên nhân chủ quan dẫn tới thắng lợi nhanh chóng và ít đổ máu của Cách mạng tháng Tám năm 1945.",
            "Nguyên nhân chủ quan: truyền thống yêu nước của dân tộc; sự lãnh đạo đúng đắn, sáng suốt của Đảng và Chủ tịch Hồ Chí Minh; quá trình chuẩn bị lực lượng chính trị, vũ trang chu đáo suốt 15 năm.",
            [
                ("Nêu được truyền thống yêu nước và khối đại đoàn kết toàn dân qua Mặt trận Việt Minh", 0.5),
                ("Phân tích vai trò lãnh đạo nhạy bén của Đảng trong việc chớp thời cơ lịch sử", 0.5),
                ("Nêu được quá trình chuẩn bị lực lượng lâu dài qua các cao trào cách mạng", 0.5),
            ],
            doc_id=did, location="Nhánh Lịch sử · Câu 19", section_id="nhanh-lich-su", choice_group="Phân môn Lịch sử",
        )
    )
    qs.append(
        essay(
            "sc08/q20", "Chuyên đề Lịch sử 9", "LS 9 · Ý nghĩa bài học Đổi mới", "Rút ra bài học kinh nghiệm từ công cuộc Đổi mới", 3, 1.5,
            "Từ thực tiễn công cuộc Đổi mới từ năm 1986 đến nay, hãy nêu bài học kinh nghiệm nổi bật đối với công cuộc xây dựng và phát triển đất nước hiện nay.",
            "Xuất phát từ thực tiễn khách quan, kiên định mục tiêu độc lập dân tộc gắn liền phát triển kinh tế số – kinh tế xanh, phát huy nội lực kết hợp sức mạnh thời đại.",
            [
                ("Nhấn mạnh nguyên tắc tôn trọng quy luật khách quan, xuất phát từ thực tiễn đời sống", 0.75),
                ("Phân tích sự kết hợp nội lực dân tộc với hội nhập quốc tế sâu rộng", 0.75),
            ],
            doc_id=did, location="Nhánh Lịch sử · Câu 20", section_id="nhanh-lich-su", choice_group="Phân môn Lịch sử",
        )
    )

    # Nhánh 2: Phân môn Địa lí (4 câu = 2 MCQ×0.5 + 2 Essay×1.5 = 4.0đ)
    qs.append(
        mcq(
            "sc08/q21", "Chuyên đề Địa lí 9", "ĐL 9 · Kinh tế biển đảo", "Nhận biết thế mạnh tổng hợp kinh tế biển", 0, 0.5,
            "Ngành nào sau đây không thuộc bốn trụ cột kinh tế biển tổng hợp của nước ta?",
            *_permute_options(["Khai thác than bùn vùng đồi trung du", "Khai thác và nuôi trồng hải sản", "Giao thông vận tải biển và cảng nước sâu", "Du lịch biển – đảo"], _ans_cycle(14)),
            "Kinh tế biển gồm thủy sản, du lịch biển, hàng hải và khai thác khoáng sản biển.",
            doc_id=did, location="Nhánh Địa lí · Câu 21", section_id="nhanh-dia-li", choice_group="Phân môn Địa lí",
        )
    )
    qs.append(
        mcq(
            "sc08/q22", "Chuyên đề Địa lí 9", "ĐL 9 · Chuyển dịch cơ cấu kinh tế", "Đọc hiểu xu hướng tỉ trọng các khu vực kinh tế", 1, 0.5,
            "Xu hướng chuyển dịch cơ cấu GDP theo ngành của nước ta trong thời kì công nghiệp hóa là gì?",
            *_permute_options(["Giảm tỉ trọng nông – lâm – thủy sản, tăng tỉ trọng công nghiệp và dịch vụ", "Tăng nhanh tỉ trọng thuần nông", "Loại bỏ hoàn toàn khu vực dịch vụ", "Giữ nguyên tỉ trọng giữa ba khu vực"], _ans_cycle(15)),
            "Tỉ trọng khu vực I giảm dần trong khi khu vực II và III tăng lên.",
            doc_id=did, location="Nhánh Địa lí · Câu 22", section_id="nhanh-dia-li", choice_group="Phân môn Địa lí",
        )
    )
    qs.append(
        essay(
            "sc08/q23", "Chuyên đề Địa lí 9", "ĐL 9 · Phát triển thủy sản Bảng 1", "Phân tích số liệu Bảng 1 và giải thích thế mạnh ĐBSCL", 2, 1.5,
            "Dựa vào Bảng 1 dữ kiện liên kết, nhận xét sản lượng thủy sản nuôi trồng giữa các vùng và giải thích vì sao Đồng bằng sông Cửu Long dẫn đầu cả nước.",
            "ĐBSCL dẫn đầu tuyệt đối (3650 nghìn tấn, gấp gần 4 lần ĐBSH) nhờ mạng lưới sông rạch dày đặc, vùng bãi triều rộng, nguồn thức ăn dồi dào và công nghiệp chế biến phát triển.",
            [
                ("Nhận xét sự chênh lệch lớn từ Bảng 1 (ĐBSCL đứng đầu, gấp gần 4 lần ĐBSH)", 0.5),
                ("Giải thích điều kiện tự nhiên thuận lợi (sông Cửu Long, diện tích mặt nước lợ – ngọt lớn)", 0.5),
                ("Giải thích điều kiện kinh tế – xã hội (thị trường xuất khẩu, nhà máy chế biến)", 0.5),
            ],
            doc_id=did, location="Nhánh Địa lí · Câu 23", section_id="nhanh-dia-li",
            choice_group="Phân môn Địa lí", data_linked=True,
        )
    )
    qs.append(
        essay(
            "sc08/q24", "Chuyên đề Địa lí 9", "ĐL 9 · Bảo vệ tài nguyên biển đảo", "Đề xuất giải pháp phát triển bền vững vùng biển", 3, 1.5,
            "Trình bày ba giải pháp quan trọng giúp phát triển bền vững kinh tế biển gắn với bảo vệ môi trường biển đảo Việt Nam.",
            "Đánh bắt xa bờ hợp lí kết hợp bảo vệ nguồn lợi thủy sản, kiểm soát chất thải công nghiệp/du lịch ven bờ, phục hồi rạn san hô và rừng ngập mặn.",
            [
                ("Giải pháp khai thác hợp lí, chuyển sang nuôi trồng công nghệ cao", 0.5),
                ("Giải pháp kiểm soát ô nhiễm từ đất liền và giao thông hàng hải", 0.5),
                ("Giải pháp bảo tồn đa dạng sinh học biển và thích ứng thiên tai", 0.5),
            ],
            doc_id=did, location="Nhánh Địa lí · Câu 24", section_id="nhanh-dia-li", choice_group="Phân môn Địa lí",
        )
    )

    return build_exam(
        "SC-08",
        title="Đề kiểm tra cuối học kì I — Lịch sử và Địa lí 9",
        school="TRƯỜNG THCS QUANG TRUNG (MẪU)",
        department="Tổ Lịch sử – Địa lí",
        subject="Lịch sử và Địa lí",
        grade="9",
        minutes=60,
        instructions="Học sinh làm bắt buộc Phần chung (16 câu, 6,0 điểm) và chọn 01 trong 02 nhánh: Phân môn Lịch sử hoặc Phân môn Địa lí (4 câu, 4,0 điểm).",
        questions=qs,
        docs=[doc],
        data=linked_data,
    )


def _make_sc09() -> dict[str, Any]:
    """SC-09: Tin học 12 GDPT 2018 (28 câu hiệu lực: 24 chung + 2 nhánh KHMT/THUD 4 câu, codeBlock Python/SQL, điểm 0,20/0,40)."""
    doc = make_doc(
        "sc09/doc",
        "Tu_lieu_Tin_hoc_12.txt",
        "Tư liệu Tin học 12 tự biên soạn: Trí tuệ nhân tạo, Mạng máy tính, HTML/CSS, Python học máy cơ bản (KHMT) và CSDL SQL (THUD).",
    )
    did = doc["id"]
    qs: list[dict[str, Any]] = []

    # 15 MCQ × 0.20 = 3.00đ (Phần chung)
    common_mcq_020 = [
        ("Trí tuệ nhân tạo", "Bài 1: Khái niệm AI", "Nhận biết đặc trưng học từ dữ liệu của AI", 0,
         "Khả năng nào sau đây thể hiện đặc trưng nổi bật của hệ thống Trí tuệ nhân tạo (AI)?",
         ["Học từ dữ liệu, suy luận và tự điều chỉnh quyết định", "Chỉ thực hiện phép cộng cố định không đổi", "Không cần nguồn điện hoặc phần cứng tính toán", "Hoàn toàn không sử dụng thuật toán"],
         "AI có khả năng học từ dữ liệu để nhận dạng mẫu, suy luận và giải quyết vấn đề."),
        ("Trí tuệ nhân tạo", "Bài 2: AI và đạo đức số", "Nhận biết nguyên tắc sử dụng AI có trách nhiệm", 0,
         "Hành vi nào thể hiện việc sử dụng công cụ AI tạo sinh có trách nhiệm trong học tập?",
         ["Kiểm chứng lại thông tin bằng nguồn tin cậy và ghi rõ phần tham khảo", "Nộp nguyên văn bài do AI viết mà không kiểm tra", "Dùng AI tạo ảnh giả mạo người khác", "Nhập mật khẩu cá nhân vào mọi trang web lạ"],
         "Người học cần kiểm chứng thông tin và tôn trọng tính trung thực học thuật."),
        ("Mạng máy tính", "Bài 3: Thiết bị mạng cơ bản", "Phân biệt chức năng Switch và Access Point", 0,
         "Thiết bị nào dùng để kết nối các máy tính trong cùng mạng cục bộ LAN qua cáp xoắn đôi?",
         ["Switch (Bộ chuyển mạch)", "Máy quét ảnh (Scanner)", "Ổ cứng di động (SSD)", "Bàn phím cơ"],
         "Switch chuyển tiếp khung dữ liệu đúng cổng đích trong mạng LAN."),
        ("Mạng máy tính", "Bài 4: Giao thức IP và DNS", "Nhận biết vai trò hệ thống DNS", 0,
         "Hệ thống phân giải tên miền (DNS) trên Internet thực hiện nhiệm vụ chính nào?",
         ["Chuyển đổi tên miền dễ nhớ sang địa chỉ IP tương ứng", "Mã hóa toàn bộ ổ cứng máy trạm", "Nén video trực tuyến thành âm thanh", "Tăng tốc độ quay quạt tản nhiệt"],
         "DNS ánh xạ tên miền sang địa chỉ IP để trình duyệt tìm đúng máy chủ."),
        ("Mạng máy tính", "Bài 4: Giao thức TCP/IP", "Phân biệt vai trò TCP và IP", 1,
         "Trong bộ giao thức TCP/IP, giao thức TCP đảm bảo tính chất nào khi truyền gói tin?",
         ["Truyền dữ liệu tin cậy, đúng thứ tự và kiểm tra lỗi", "Cấp địa chỉ MAC cố định cho card mạng", "Hiển thị hình ảnh lên màn hình trình chiếu", "Xóa tệp tin cũ trên đĩa quang"],
         "TCP thiết lập kết nối và xác nhận gói tin để đảm bảo toàn vẹn thứ tự dữ liệu."),
        ("Đạo đức và pháp luật số", "Bài 5: Giao tiếp văn minh trên không gian mạng", "Nhận biết quy tắc ứng xử an toàn", 0,
         "Khi nhận được liên kết rút gọn lạ kèm yêu cầu đăng nhập tài khoản ngân hàng để nhận thưởng, người dùng nên làm gì?",
         ["Không nhấp liên kết và kiểm tra trực tiếp trên kênh chính thức", "Điền ngay thông tin thẻ để thử vận may", "Chia sẻ liên kết lên nhóm lớp", "Tắt phần mềm diệt virus rồi mở lại"],
         "Đây là dấu hiệu lừa đảo (phishing) đánh cắp thông tin đăng nhập."),
        ("HTML và biểu mẫu", "Bài 6: Cấu trúc trang web HTML", "Nhận biết cặp thẻ định nghĩa đoạn văn và tiêu đề", 0,
         "Thẻ HTML ngữ nghĩa nào dùng để đánh dấu vùng nội dung điều hướng chính của trang web?",
         ["`<nav>`", "`<tfoot>`", "`<br>`", "`<style>`"],
         "Thẻ `<nav>` bao bọc danh sách liên kết điều hướng."),
        ("HTML và biểu mẫu", "Bài 7: Danh sách và bảng HTML", "Phân biệt thẻ hàng và ô dữ liệu trong bảng", 0,
         "Trong bảng HTML (`<table>`), cặp thẻ nào tạo nên một hàng dữ liệu?",
         ["`<tr>...</tr>`", "`<td>...</td>`", "`<ul>...</ul>`", "`<li>...</li>`"],
         "`<tr>` (table row) tạo hàng; `<td>` tạo ô dữ liệu."),
        ("HTML và biểu mẫu", "Bài 8: Siêu liên kết và đa phương tiện", "Chọn thuộc tính đúng của thẻ <a>", 0,
         "Thuộc tính nào trong thẻ `<a>` dùng để chỉ định đường dẫn URL đích khi người dùng nhấp vào liên kết?",
         ["`href`", "`src`", "`alt`", "`cols`"],
         "Thẻ `<a href=\"...\">` khai báo địa chỉ đích; `src` dùng cho ảnh/video."),
        ("HTML và biểu mẫu", "Bài 9: Biểu mẫu web <form>", "Chọn kiểu input che ký tự mật khẩu", 0,
         "Thuộc tính `type` nào của thẻ `<input>` giúp ẩn các ký tự mật khẩu khi người dùng gõ trên biểu mẫu?",
         ["`type=\"password\"`", "`type=\"text\"`", "`type=\"hidden\"`", "`type=\"checkbox\"`"],
         "`type=\"password\"` che dấu ký tự nhập vào trên màn hình."),
        ("HTML và biểu mẫu", "Bài 9: Nhãn truy cập biểu mẫu", "Gắn nhãn label đúng cho ô nhập liệu", 1,
         "Để khi nhấp chuột vào nhãn chữ thì con trỏ tự nhảy vào ô `<input id=\"ho-ten\">`, thẻ `<label>` cần khai báo thuộc tính nào?",
         ["`for=\"ho-ten\"`", "`name=\"ho-ten\"`", "`class=\"ho-ten\"`", "`value=\"ho-ten\"`"],
         "`for` trên `<label>` khớp với `id` của phần tử điều khiển."),
        ("HTML và biểu mẫu", "Bài 6: Thuộc tính mô tả ảnh", "Đảm bảo khả năng tiếp cận web cho thẻ <img>", 0,
         "Thuộc tính `alt` trong thẻ `<img src=\"do-thi.png\" alt=\"...\">` có vai trò gì?",
         ["Hiển thị văn bản thay thế khi ảnh lỗi và hỗ trợ trình đọc màn hình", "Đổi định dạng ảnh sang PDF", "Tự động căn giữa bảng tính", "Khóa quyền tải trang web"],
         "Thuộc tính `alt` tăng khả năng tiếp cận (accessibility) và dự phòng khi ảnh không tải được."),
        ("Thiết kế CSS cơ bản", "Bài 10: Cú pháp bộ chọn CSS", "Nhận biết kí hiệu bộ chọn theo lớp (class)", 0,
         "Trong tệp CSS, bộ chọn nào áp dụng định dạng cho tất cả các phần tử HTML có thuộc tính `class=\"card\"`?",
         ["`.card`", "`#card`", "`card`", "`*card`"],
         "Dấu chấm `.` dùng cho bộ chọn lớp (`class`), dấu `#` dùng cho định danh (`id`)."),
        ("Thiết kế CSS cơ bản", "Bài 11: Mô hình hộp CSS", "Phân biệt padding và margin", 1,
         "Trong mô hình hộp (Box Model) của CSS, vùng khoảng trống nằm giữa nội dung phần tử và đường viền `border` gọi là gì?",
         ["`padding`", "`margin`", "`outline`", "`z-index`"],
         "Thứ tự từ trong ra ngoài: content -> padding -> border -> margin."),
        ("Thiết kế CSS cơ bản", "Bài 12: Bố cục trang web", "Nhận biết thuộc tính kích hoạt Flexbox", 0,
         "Khai báo CSS nào biến một phần tử chứa thành lưới co giãn theo hàng hoặc cột (Flexbox)?",
         ["`display: flex;`", "`position: fixed;`", "`float: none;`", "`overflow: hidden;`"],
         "`display: flex;` bật mô hình bố cục Flexbox cho phần tử cha."),
    ]
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(common_mcq_020):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc09/q{idx + 1}", top, les, comp, lvl, 0.2, stem, p_opts, ans, exp,
                doc_id=did, location="Phần chung · I", section_id="phan-chung",
            )
        )

    # 5 MCQ × 0.40 = 2.00đ (Phần chung: mức độ cao hơn, chủ đề riêng để không lẫn 0.20đ)
    common_mcq_040 = [
        ("Ưu tiên CSS nâng cao", "Bài 11: Độ đặc hiệu bộ chọn CSS", "Tính độ ưu tiên giữa id, class và thẻ", 2,
         "Cho đoạn HTML `<p id=\"tieu-de\" class=\"noi-bat\">Xin chào</p>`. Nếu CSS đồng thời đặt `p { color: black; }`, `.noi-bat { color: blue; }`, `#tieu-de { color: teal; }`, chữ hiển thị màu gì?",
         ["Màu xanh cổ vịt (teal)", "Màu xanh dương (blue)", "Màu đen (black)", "Không hiển thị màu"],
         "Độ đặc hiệu của `#id` (`100`) lớn hơn `.class` (`10`) và tên thẻ (`1`)."),
        ("Mạng và bảo mật nâng cao", "Bài 4: Chia dải mạng và HTTPS", "Hiểu cơ chế mã hóa truyền tải HTTPS", 1,
         "Giao thức HTTPS bảo vệ dữ liệu trao đổi giữa trình duyệt và máy chủ web bằng cách nào?",
         ["Mã hóa kênh truyền qua tầng TLS/SSL và xác thực chứng thư số", "Ẩn hoàn toàn địa chỉ IP khỏi bộ định tuyến", "Chuyển mọi tệp HTML thành ảnh PNG", "Nén gói tin bỏ qua phần kiểm tra lỗi"],
         "HTTPS kết hợp HTTP với TLS để đảm bảo tính bí mật và toàn vẹn dữ liệu truyền."),
        ("Đánh giá hệ thống AI", "Bài 2: Học có giám sát", "Phân biệt tập huấn luyện và tập kiểm thử", 1,
         "Trong quy trình xây dựng mô hình phân loại ảnh bằng học có giám sát, tập dữ liệu kiểm thử (test set) dùng để làm gì?",
         ["Đánh giá độ chính xác tổng quát trên dữ liệu chưa từng thấy", "Gắn nhãn thủ công cho toàn bộ tệp gốc", "Xóa bớt trọng số âm của mạng", "Thay thế hoàn toàn bước thu thập dữ liệu"],
         "Test set độc lập giúp phát hiện hiện tượng học vẹt (overfitting)."),
        ("Xử lí xung đột biểu mẫu web", "Bài 9: Xác thực dữ liệu form", "Chọn thuộc tính HTML5 kiểm tra bắt buộc", 1,
         "Để trình duyệt kiểm tra ô nhập email không được để trống và đúng định dạng trước khi gửi biểu mẫu, cặp thuộc tính chuẩn nào được dùng?",
         ["`type=\"email\" required`", "`type=\"text\" readonly`", "`type=\"submit\" disabled`", "`type=\"number\" checked`"],
         "`type=\"email\"` kiểm tra định dạng email và `required` bắt buộc nhập."),
        ("Kiến trúc trang web đáp ứng", "Bài 12: Media Query", "Áp dụng CSS cho màn hình nhỏ hơn 600px", 2,
         "Quy tắc CSS `@media (max-width: 600px)` được kích hoạt trong điều kiện nào sau đây?",
         ["Khi chiều rộng vùng hiển thị trình duyệt nhỏ hơn hoặc bằng 600px", "Khi người dùng phóng to trang vượt 600%", "Chỉ khi xuất bản in sang giấy khổ A0", "Khi trang có hơn 600 thẻ div"],
         "`max-width: 600px` áp dụng cho các thiết bị màn hình hẹp tối đa 600px."),
    ]
    for idx, (top, les, comp, lvl, stem, opts, exp) in enumerate(common_mcq_040, 16):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx - 1))
        qs.append(
            mcq(
                f"sc09/q{idx}", top, les, comp, lvl, 0.4, stem, p_opts, ans, exp,
                doc_id=did, location="Phần chung · II", section_id="phan-chung",
            )
        )

    # 2 TF × 1.00 = 2.00đ (Phần chung)
    qs.append(
        tf(
            "sc09/q21", "Mạng máy tính", "Bài 4: Địa chỉ IPv4 và cổng dịch vụ", "Phân tích cấu hình mạng cục bộ", 2, 1.0,
            "Một phòng máy trường học sử dụng dải địa chỉ IPv4 `192.168.10.0/24`, máy chủ nội bộ có địa chỉ `192.168.10.10` chạy dịch vụ web trên cổng `8000`. Xét các nhận định:",
            [
                "a) Bốn cụm số của địa chỉ IPv4 được phân tách bằng dấu chấm, mỗi cụm từ 0 đến 255.",
                "b) Địa chỉ `192.168.10.300` là một địa chỉ IPv4 hợp lệ trong mạng trên.",
                "c) Máy trạm `192.168.10.25` nằm cùng lớp mạng `/24` với máy chủ `192.168.10.10`.",
                "d) Hai máy cùng truy cập máy chủ trên phải dùng chung giao thức tầng vận chuyển TCP.",
            ],
            [True, False, True, True],
            "a, c, d) Đúng. b) Sai: mỗi octet tối đa là 255 nên `.300` không hợp lệ.",
            doc_id=did, location="Phần chung · Câu 21", section_id="phan-chung",
        )
    )
    qs.append(
        tf(
            "sc09/q22", "HTML và biểu mẫu", "Bài 10: Phân tích đoạn mã HTML và CSS", "Đọc hiểu kết quả hiển thị đoạn mã web", 2, 1.0,
            "Cho đoạn mã HTML: `<div class=\"box\"><p id=\"note\">Thông báo</p></div>` cùng quy tắc `.box p { font-size: 16px; }`. Xét các phát biểu:",
            [
                "a) Bộ chọn `.box p` chọn các thẻ `<p>` là hậu duệ nằm bên trong phần tử có `class=\"box\"`.",
                "b) Thuộc tính `id=\"note\"` nên là duy nhất trong một tài liệu HTML.",
                "c) Nội dung chữ `Thông báo` được hiển thị với cỡ chữ 16 pixel.",
                "d) Bộ chọn `.box > div` khớp với phần tử `<p id=\"note\">`.",
            ],
            [True, True, True, False],
            "a, b, c) Đúng. d) Sai: `.box > div` chọn thẻ con là `<div>`, không phải `<p>`.",
            doc_id=did, location="Phần chung · Câu 22", section_id="phan-chung",
        )
    )

    # 2 Tự luận chung × 0.50 = 1.00đ
    q23_stem, q23_doc = code_doc(
        "Quan sát đoạn mã HTML và CSS sau và giải thích kết quả hiển thị màu chữ của hai đoạn văn:",
        "<div class=\"panel\">\n  <p class=\"lead\">Đoạn A</p>\n  <p>Đoạn B</p>\n</div>\n\n<style>\n  .panel p { color: #1f2937; }\n  p.lead { color: #0f766e; }\n</style>",
    )
    qs.append(
        essay(
            "sc09/q23", "Thiết kế CSS nâng cao", "Bài 11: Giải thích độ ưu tiên CSS", "Phân tích kết quả áp dụng độ đặc hiệu CSS", 2, 0.5,
            q23_stem,
            "Cả hai bộ chọn .panel p và p.lead đều có độ đặc hiệu (0, 1, 1); theo thứ tự khai báo sau thắng trước, Đoạn A có màu #0f766e còn Đoạn B có màu #1f2937.",
            [
                ("Nêu được cả hai bộ chọn .panel p và p.lead có cùng độ đặc hiệu (1 class + 1 tag)", 0.25),
                ("Kết luận đúng Đoạn A màu #0f766e (khai báo sau) và Đoạn B màu #1f2937", 0.25),
            ],
            doc_id=did, location="Phần chung · Câu 23", rich_doc=q23_doc, section_id="phan-chung",
        )
    )
    qs.append(
        essay(
            "sc09/q24", "Mạng máy tính", "Bài 3: Thiết kế sơ đồ LAN trường học", "Đề xuất giải pháp kết nối LAN an toàn cho phòng học", 2, 0.5,
            "Một trường THPT muốn mở rộng mạng Wi-Fi cho 12 phòng học từ đường truyền cáp quang chính ở phòng máy chủ. Trình bày ngắn gọn hai thiết bị cần dùng và một biện pháp bảo mật Wi-Fi nội bộ.",
            "Cần dùng Router cân bằng tải / Switch kết nối cáp mạng tới các Access Point đặt ở hành lang các tầng; bật chuẩn mã hóa WPA2/WPA3 và tách VLAN khách với VLAN giáo viên.",
            [
                ("Nêu đúng vai trò Switch và Access Point (hoặc Router) trong việc phủ sóng và chia cổng", 0.25),
                ("Đề xuất biện pháp bảo mật phù hợp (chuẩn WPA2/WPA3 mạnh hoặc tách VLAN)", 0.25),
            ],
            doc_id=did, location="Phần chung · Câu 24", section_id="phan-chung",
        )
    )

    # Nhánh 1: KHMT (4 câu = 2.00đ: 1 MCQ×0.40 + 1 TF×1.00 + 1 Short×0.20 + 1 Essay×0.40)
    khmt_mcq_stem, khmt_mcq_doc = code_doc(
        "Cho đoạn mã Python xử lí danh sách điểm số sau:",
        "def dem_dat(ds, nguong=5.0):\n    dem = 0\n    for x in ds:\n        if x >= nguong:\n            dem += 1\n    return dem\n\nprint(dem_dat([4.5, 5.0, 7.2, 3.8, 8.0]))",
        "Giá trị được in ra màn hình là bao nhiêu?",
    )
    qs.append(
        mcq(
            "sc09/khmt1", "Khoa học máy tính · Python", "KHMT · Hàm và danh sách Python", "Đọc hiểu hàm xử lí danh sách", 1, 0.4,
            khmt_mcq_stem, *_permute_options(["3", "2", "4", "5"], 2),
            "Các phần tử >= 5.0 gồm 5.0, 7.2, 8.0 nên hàm trả về 3.",
            doc_id=did, location="Nhánh KHMT · Câu 25", rich_doc=khmt_mcq_doc,
            section_id="nhanh-khmt", choice_group="KHMT",
        )
    )
    khmt_tf_stem, khmt_tf_doc = code_doc(
        "Xét đoạn mã Python thực hiện thuật toán tìm kiếm nhị phân trên mảng đã sắp xếp tăng dần:",
        "def binary_search(a, x):\n    left, right = 0, len(a) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if a[mid] == x:\n            return mid\n        elif a[mid] < x:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1",
        "Xét các nhận định về thuật toán trên:",
    )
    qs.append(
        tf(
            "sc09/khmt2", "Khoa học máy tính · Thuật toán", "KHMT · Tìm kiếm nhị phân", "Phân tích đúng/sai thuật toán tìm kiếm nhị phân", 2, 1.0,
            khmt_tf_stem,
            [
                "a) Thuật toán đòi hỏi mảng `a` phải được sắp xếp thứ tự trước khi tìm kiếm.",
                "b) Khi gọi `binary_search([2, 5, 8, 12, 19], 12)`, giá trị trả về là `3`.",
                "c) Độ phức tạp thời gian trường hợp xấu nhất là $O(n^2)$.",
                "d) Nếu phần tử `x` không có trong `a`, hàm trả về `-1`.",
            ],
            [True, True, False, True],
            "a, b, d) Đúng. c) Sai: độ phức tạp tìm kiếm nhị phân là $O(\\log_2 n)$.",
            doc_id=did, location="Nhánh KHMT · Câu 26", rich_doc=khmt_tf_doc,
            section_id="nhanh-khmt", choice_group="KHMT",
        )
    )
    khmt_short_stem, khmt_short_doc = code_doc(
        "Cho đoạn mã Python tính tổng tích lũy sau:",
        "s = 0\nfor i in range(1, 6):\n    if i % 2 == 1:\n        s += i * i\nprint(s)",
        "Kết quả in ra màn hình là số nguyên nào?",
    )
    qs.append(
        short_q(
            "sc09/khmt3", "Khoa học máy tính · Vòng lặp", "KHMT · Theo dõi giá trị biến Python", "Tính đầu ra vòng lặp có điều kiện", 2, 0.2,
            khmt_short_stem, "35",
            "Các số lẻ trong range(1, 6) là 1, 3, 5; tổng bình phương $1^2 + 3^2 + 5^2 = 1 + 9 + 25 = 35$.",
            doc_id=did, location="Nhánh KHMT · Câu 27", rich_doc=khmt_short_doc,
            section_id="nhanh-khmt", choice_group="KHMT",
        )
    )
    qs.append(
        essay(
            "sc09/khmt4", "Khoa học máy tính · Phân tích thuật toán", "KHMT · Sắp xếp và độ phức tạp", "So sánh độ phức tạp và viết hàm Python kiểm tra số nguyên tố", 3, 0.4,
            "Viết hàm Python `la_nguyen_to(n)` trả về `True` nếu số nguyên `n` là số nguyên tố (ngược lại trả về `False`), với điều kiện vòng lặp chỉ kiểm tra tới $\\lfloor\\sqrt{n}\\rfloor$.",
            "Kiểm tra $n < 2$ trả `False`; duyệt `d` từ $2$ đến `int(n ** 0.5) + 1`, nếu `n % d == 0` trả `False`, hết vòng lặp trả `True`.",
            [
                ("Xử lí đúng điều kiện biên `n < 2` trả về `False`", 0.2),
                ("Duyệt ước từ `2` tới `int(n ** 0.5) + 1` và kết luận chính xác", 0.2),
            ],
            doc_id=did, location="Nhánh KHMT · Câu 28", section_id="nhanh-khmt", choice_group="KHMT",
        )
    )

    # Nhánh 2: THUD (4 câu = 2.00đ: 1 MCQ×0.40 + 1 TF×1.00 + 1 Short×0.20 + 1 Essay×0.40)
    thud_mcq_stem, thud_mcq_doc = code_doc(
        "Cho câu lệnh SQL truy vấn dữ liệu trên bảng `HOC_SINH(MaHS, HoTen, Lop, DiemTB)`:",
        "SELECT Lop, COUNT(*) AS SiSo\nFROM HOC_SINH\nWHERE DiemTB >= 8.0\nGROUP BY Lop\nORDER BY SiSo DESC;",
        "Câu lệnh trên thực hiện công việc gì?",
    )
    qs.append(
        mcq(
            "sc09/thud1", "Tin học ứng dụng · CSDL SQL", "THUD · Truy vấn gom nhóm SQL", "Đọc hiểu mệnh đề WHERE và GROUP BY", 1, 0.4,
            thud_mcq_stem,
            *_permute_options(
                [
                    "Đếm số học sinh có điểm TB từ 8,0 trở lên theo từng lớp và sắp giảm dần",
                    "Tính điểm trung bình toàn trường rồi xóa các lớp điểm thấp",
                    "Cập nhật điểm TB tất cả học sinh thành 8,0",
                    "Liệt kê tên từng học sinh theo thứ tự chữ cái",
                ],
                3,
            ),
            "`WHERE DiemTB >= 8.0` lọc trước khi `GROUP BY Lop` và `ORDER BY SiSo DESC`.",
            doc_id=did, location="Nhánh THUD · Câu 25", rich_doc=thud_mcq_doc,
            section_id="nhanh-thud", choice_group="THUD",
        )
    )
    thud_tf_stem, thud_tf_doc = code_doc(
        "Cho lược đồ cơ sở dữ liệu thư viện gồm hai bảng quan hệ sau:",
        "CREATE TABLE SACH (\n  MaSach VARCHAR(10) PRIMARY KEY,\n  TenSach VARCHAR(120) NOT NULL,\n  MaTL VARCHAR(6) REFERENCES THE_LOAI(MaTL)\n);\nCREATE TABLE MUON_TRA (\n  MaPhieu INT PRIMARY KEY,\n  MaSach VARCHAR(10) REFERENCES SACH(MaSach),\n  NgayMuon DATE\n);",
        "Xét các nhận định về thiết kế cơ sở dữ liệu trên:",
    )
    qs.append(
        tf(
            "sc09/thud2", "Tin học ứng dụng · Thiết kế CSDL", "THUD · Khóa chính và khóa ngoại", "Kiểm tra tính toàn vẹn tham chiếu CSDL", 2, 1.0,
            thud_tf_stem,
            [
                "a) `MaSach` là khóa chính của bảng `SACH` nên không được chứa giá trị trùng lặp hoặc NULL.",
                "b) Cột `MaSach` trong bảng `MUON_TRA` đóng vai trò là khóa ngoại.",
                "c) Có thể chèn bản ghi vào `MUON_TRA` với `MaSach` chưa từng tồn tại trong bảng `SACH`.",
                "d) Hai bảng `SACH` và `MUON_TRA` liên kết với nhau theo quan hệ 1–nhiều.",
            ],
            [True, True, False, True],
            "a, b, d) Đúng. c) Sai: ràng buộc toàn vẹn tham chiếu (FOREIGN KEY) chặn giá trị chưa có ở bảng cha.",
            doc_id=did, location="Nhánh THUD · Câu 26", rich_doc=thud_tf_doc,
            section_id="nhanh-thud", choice_group="THUD",
        )
    )
    qs.append(
        short_q(
            "sc09/thud3", "Tin học ứng dụng · Bảng tính nâng cao", "THUD · Công thức SUMIF", "Đọc kết quả hàm thống kê có điều kiện", 1, 0.2,
            "Trong bảng tính Excel, vùng `B2:B6` chứa tên lớp `[\"9A\", \"9B\", \"9A\", \"9C\", \"9A\"]` và vùng `C2:C6` chứa số quyển sách quyên góp `[12, 8, 15, 10, 13]`. Công thức `=SUMIF(B2:B6, \"9A\", C2:C6)` trả về giá trị bao nhiêu?",
            "40",
            "Các hàng có giá trị `\"9A\"` là hàng 2, 4, 6 tương ứng $12 + 15 + 13 = 40$.",
            doc_id=did, location="Nhánh THUD · Câu 27", section_id="nhanh-thud", choice_group="THUD",
        )
    )
    qs.append(
        essay(
            "sc09/thud4", "Tin học ứng dụng · Truy vấn SQL", "THUD · Viết câu lệnh JOIN", "Viết truy vấn SQL kết nối hai bảng và lọc điều kiện", 3, 0.4,
            "Dựa trên hai bảng `SACH(MaSach, TenSach, MaTL)` và `MUON_TRA(MaPhieu, MaSach, NgayMuon)`, hãy viết câu lệnh SQL hiển thị mã phiếu, tên sách và ngày mượn đối với các lượt mượn từ ngày `'2026-10-01'` trở đi.",
            "`SELECT M.MaPhieu, S.TenSach, M.NgayMuon FROM MUON_TRA M INNER JOIN SACH S ON M.MaSach = S.MaSach WHERE M.NgayMuon >= '2026-10-01';`",
            [
                ("Dùng đúng `INNER JOIN` (hoặc `JOIN`) qua khóa `M.MaSach = S.MaSach`", 0.2),
                ("Chọn đủ 3 cột và lọc đúng điều kiện `M.NgayMuon >= '2026-10-01'`", 0.2),
            ],
            doc_id=did, location="Nhánh THUD · Câu 28", section_id="nhanh-thud", choice_group="THUD",
        )
    )

    return build_exam(
        "SC-09",
        title="Đề thi thử tốt nghiệp THPT — Tin học 12 (GDPT 2018)",
        school="TRƯỜNG THPT LÝ TỰ TRỌNG (MẪU)",
        department="Tổ Tin học – Công nghệ",
        subject="Tin học",
        grade="12",
        minutes=50,
        instructions="Thí sinh làm bắt buộc 24 câu Phần chung (8,00 điểm) và chọn 01 trong 02 định hướng KHMT hoặc THUD (4 câu, 2,00 điểm). Tổng 28 câu hiệu lực.",
        questions=qs,
        docs=[doc],
    )


def _make_sc10() -> dict[str, Any]:
    """SC-10: Tiểu học Toán lớp 5 (10 câu: 6 MCQ 4,0đ + 4 TL 6,0đ, tỉ số/tỷ số phần trăm, phân số)."""
    doc = make_doc(
        "sc10/doc",
        "Tu_lieu_Toan_5_tieu_hoc.txt",
        "Tư liệu Toán lớp 5 tự biên soạn: Phân số, hỗn số, số thập phân, tỉ số phần trăm, diện tích hình thang và thể tích hình hộp chữ nhật.",
    )
    did = doc["id"]
    qs: list[dict[str, Any]] = []

    mcq_specs = [
        ("Số thập phân", "Bài 1: Đọc và viết số thập phân", "Nhận biết giá trị chữ số theo hàng thập phân", 0, 0.5,
         "Trong số thập phân $42{,}758$, chữ số $5$ thuộc hàng nào?",
         ["Hàng phần trăm", "Hàng phần mười", "Hàng phần nghìn", "Hàng chục"],
         "Sau dấu phẩy lần lượt là hàng phần mười (7), hàng phần trăm (5), hàng phần nghìn (8)."),
        ("Phân số và hỗn số", "Bài 2: Chuyển đổi phân số và hỗn số", "Đổi hỗn số sang phân số", 0, 0.5,
         r"Hỗn số $3\frac{2}{5}$ viết dưới dạng phân số là?",
         [r"$\frac{17}{5}$", r"$\frac{13}{5}$", r"$\frac{15}{2}$", r"$\frac{11}{5}$"],
         r"$3\frac{2}{5} = \frac{3 \cdot 5 + 2}{5} = \frac{17}{5}$."),
        ("Tỉ số và tỉ số phần trăm", "Bài 3: Tính tỉ số phần trăm của hai số", "Viết tỉ số dưới dạng phần trăm", 1, 0.5,
         "Lớp 5A có $18$ bạn nữ và tổng cộng $30$ học sinh. Tỉ số phần trăm của số bạn nữ so với số học sinh cả lớp là?",
         [r"$60\%$", r"$40\%$", r"$54\%$", r"$18\%$"],
         r"$\frac{18}{30} = 0{,}6 = 60\%$."),
        ("Đo lường và đơn vị", "Bài 4: Đổi đơn vị diện tích và thể tích", "Chuyển đổi đề-xi-mét khối sang lít", 0, 0.5,
         r"Số thích hợp điền vào chỗ chấm: $2\text{ m}^3\; 45\text{ dm}^3 = \dots \text{ m}^3$ là?",
         [r"$2{,}045$", r"$2{,}45$", r"$2045$", r"$2{,}0045$"],
         r"$45\text{ dm}^3 = 0{,}045\text{ m}^3$, nên $2\text{ m}^3\; 45\text{ dm}^3 = 2{,}045\text{ m}^3$."),
        ("Phân số và phép tính", "Bài 5: Phép nhân chia phân số", "Tìm phân số của một số cho trước", 1, 1.0,
         r"Một cửa hàng có $120\text{ kg}$ gạo, buổi sáng đã bán $\frac{3}{5}$ số gạo đó. Số ki-lô-gam gạo còn lại sau buổi sáng là?",
         [r"$48\text{ kg}$", r"$72\text{ kg}$", r"$36\text{ kg}$", r"$60\text{ kg}$"],
         r"Số gạo đã bán là $120 \cdot \frac{3}{5} = 72\text{ kg}$; số gạo còn lại là $120 - 72 = 48\text{ kg}$."),
        ("Tỉ số và tỉ số phần trăm", "Bài 6: Tìm một số biết giá trị phần trăm", "Tìm giá gốc trước khi giảm giá", 2, 1.0,
         r"Một chiếc cặp sách sau khi giảm giá $20\%$ thì có giá bán là $160\,000$ đồng. Giá ban đầu của chiếc cặp sách là?",
         [r"$200\,000$ đồng", r"$192\,000$ đồng", r"$128\,000$ đồng", r"$180\,000$ đồng"],
         r"$160\,000$ đồng ứng với $100\% - 20\% = 80\%$ giá ban đầu, nên giá gốc là $160\,000 : 80 \cdot 100 = 200\,000$ đồng."),
    ]
    for idx, (top, les, comp, lvl, pts, stem, opts, exp) in enumerate(mcq_specs):
        p_opts, ans = _permute_options(opts, _ans_cycle(idx))
        qs.append(
            mcq(
                f"sc10/q{idx + 1}", top, les, comp, lvl, pts, stem, p_opts, ans, exp,
                doc_id=did, location="Phần I · Trắc nghiệm", section_id="phan-1-mcq",
            )
        )

    # 4 Tự luận (1.0 + 1.5 + 2.0 + 1.5 = 6.0đ)
    qs.append(
        essay(
            "sc10/q7", "Phân số và số thập phân", "Bài 5: Đặt tính và tìm x", "Tính giá trị biểu thức phân số và tìm thành phần chưa biết", 1, 1.0,
            "a) Tính giá trị biểu thức: $\\left(\\frac{3}{4} + \\frac{5}{8}\\right) \\times \\frac{4}{11}$.\nb) Tìm $x$ biết: $x \\times 2{,}5 = 12{,}5 - 5$.",
            "a) $\\frac{11}{8} \\times \\frac{4}{11} = \\frac{1}{2}$. b) $x \\times 2{,}5 = 7{,}5 \\Rightarrow x = 3$.",
            [
                (r"a) Cộng hai phân số $\frac{3}{4} + \frac{5}{8} = \frac{11}{8}$ và nhân ra $\frac{1}{2}$", 0.5),
                ("b) Tính $12{,}5 - 5 = 7{,}5$ và tìm đúng $x = 3$", 0.5),
            ],
            doc_id=did, location="Phần II · Bài 7", section_id="phan-2-essay",
        )
    )
    qs.append(
        essay(
            "sc10/q8", "Tỉ số và tỉ số phần trăm", "Bài 6: Bài toán hiệu tỉ và phần trăm", "Giải bài toán tìm hai số khi biết hiệu và tỉ số", 2, 1.5,
            "Một mảnh vườn hình chữ nhật có chiều dài hơn chiều rộng $18\\text{ m}$ và chiều rộng bằng $\\frac{3}{5}$ chiều dài. Tính diện tích mảnh vườn đó bằng mét vuông.",
            "Hiệu số phần bằng nhau: $5 - 3 = 2$ phần. Chiều rộng $18 : 2 \\times 3 = 27\\text{ m}$, chiều dài $27 + 18 = 45\\text{ m}$. Diện tích $45 \\times 27 = 1215\\text{ m}^2$.",
            [
                ("Tìm đúng hiệu số phần bằng nhau: $5 - 3 = 2$ (phần) và tính chiều rộng $27\\text{ m}$", 0.5),
                ("Tính đúng chiều dài $45\\text{ m}$", 0.5),
                ("Tính đúng diện tích $45 \\times 27 = 1215\\text{ m}^2$ và ghi đáp số", 0.5),
            ],
            doc_id=did, location="Phần II · Bài 8", section_id="phan-2-essay",
        )
    )
    qs.append(
        essay(
            "sc10/q9", "Hình học trực quan", "Bài 7: Diện tích hình thang vuông", "Tính diện tích hình thang kết hợp tỉ số phần trăm", 2, 2.0,
            "Một thửa ruộng hình thang $ABCD$ có đáy nhỏ $AB = 24\\text{ m}$, đáy lớn $CD = 36\\text{ m}$ và chiều cao $AH = 15\\text{ m}$.\na) Tính diện tích thửa ruộng hình thang đó.\nb) Người ta dành $40\\%$ diện tích thửa ruộng để trồng hoa màu, phần còn lại trồng lúa. Tính diện tích trồng lúa.",
            "a) $S = \\frac{(24 + 36) \\times 15}{2} = 450\\text{ m}^2$. b) Tỉ lệ trồng lúa là $60\\%$, diện tích trồng lúa là $450 \\times 60 : 100 = 270\\text{ m}^2$.",
            [
                ("a) Viết đúng công thức và tính diện tích hình thang $S = \\frac{(24+36) \\times 15}{2} = 450\\text{ m}^2$", 1.0),
                ("b) Tính đúng tỉ lệ phần trăm diện tích trồng lúa $100\\% - 40\\% = 60\\%$", 0.5),
                ("b) Tính đúng diện tích trồng lúa $450 \\times 60\\% = 270\\text{ m}^2$", 0.5),
            ],
            doc_id=did, location="Phần II · Bài 9",
            figure={
                "points": {"A": {"x": 1, "y": 3}, "B": {"x": 5, "y": 3}, "C": {"x": 6, "y": 0}, "D": {"x": 0, "y": 0}},
                "constraints": ["H=foot(A,D,C)"],
                "objects": ["segment(A,B)", "segment(B,C)", "segment(C,D)", "segment(D,A)", {"type": "segment", "points": ["A", "H"], "dashed": True}, "rightAngle(A,H,C)"],
                "labels": {"A": "above", "B": "above", "C": "right", "D": "left", "H": "below"},
                "caption": "Hình thang ABCD với đáy nhỏ AB, đáy lớn CD và đường cao AH",
                "width": 460,
                "align": "center",
            },
            section_id="phan-2-essay",
        )
    )
    qs.append(
        essay(
            "sc10/q10", "Tỉ số và tỉ số phần trăm", "Bài 8: Bài toán chuyển động và phần trăm", "Giải bài toán hai xe đi ngược chiều", 3, 1.5,
            "Quãng đường từ tỉnh $A$ đến tỉnh $B$ dài $165\\text{ km}$. Lúc $7$ giờ sáng, một xe máy đi từ $A$ đến $B$ với vận tốc $35\\text{ km/h}$, cùng lúc đó một ô tô đi từ $B$ về $A$ với vận tốc $47{,}5\\text{ km/h}$. Hỏi hai xe gặp nhau lúc mấy giờ?",
            "Tổng vận tốc $35 + 47{,}5 = 82{,}5\\text{ km/h}$. Thời gian đi để gặp nhau: $165 : 82{,}5 = 2$ giờ. Hai xe gặp nhau lúc $7 + 2 = 9$ giờ.",
            [
                ("Tính đúng tổng vận tốc hai xe: $35 + 47{,}5 = 82{,}5\\text{ km/h}$", 0.5),
                ("Tính thời gian hai xe đi đến khi gặp nhau: $165 : 82{,}5 = 2$ giờ", 0.5),
                ("Tính đúng thời điểm gặp nhau lúc $9$ giờ sáng và ghi đáp số", 0.5),
            ],
            doc_id=did, location="Phần II · Bài 10", section_id="phan-2-essay",
        )
    )

    return build_exam(
        "SC-10",
        title="Đề kiểm tra cuối năm — Toán lớp 5 (Tiểu học)",
        school="TRƯỜNG TIỂU HỌC HOA SEN (MẪU)",
        department="Tổ Chuyên môn Khối 5",
        subject="Toán",
        grade="5",
        minutes=40,
        instructions="Học sinh khoanh vào chữ đặt trước câu trả lời đúng ở Phần I và trình bày bài giải chi tiết ở Phần II.",
        questions=qs,
        docs=[doc],
    )


def _save_deterministic_docx(doc: Document, path: Path) -> None:
    doc.core_properties.author = "SoanDeThi Corpus Builder"
    doc.core_properties.created = FIXED_DT
    doc.core_properties.modified = FIXED_DT
    buf = io.BytesIO()
    doc.save(buf)
    raw = io.BytesIO(buf.getvalue())
    out = io.BytesIO()
    with zipfile.ZipFile(raw, "r") as zin, zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info in sorted(zin.infolist(), key=lambda i: i.filename):
            clean = zipfile.ZipInfo(filename=info.filename, date_time=FIXED_ZIP_DT)
            clean.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(clean, zin.read(info.filename))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.getvalue())


def _set_cell_text(cell: Any, text: str) -> None:
    cell.text = text


def _build_merged_header_docx(path: Path) -> None:
    """Tạo matrix-cv7991-merged-header.docx với 3 hàng tiêu đề gộp ô gridSpan + vMerge, đủ 4 loại câu và 0,40 + 9,60."""
    doc = Document()
    doc.add_heading("MA TRẬN ĐỀ KIỂM TRA ĐỊNH KÌ THEO CÔNG VĂN 7991", level=1)
    doc.add_paragraph("Ví dụ kiểm thử tiêu đề gộp 3 tầng, đủ 3 dạng TNKQ + Tự luận và điểm biên 0,40 / 9,60.")

    # 9 cột: TT | Chủ đề | Loại câu | Điểm/câu | Nhóm chọn | Nhận biết | Thông hiểu | Vận dụng | Vận dụng cao
    # 3 hàng tiêu đề + 5 hàng dữ liệu + 1 hàng Tổng = 9 hàng
    table = doc.add_table(rows=9, cols=9)
    table.style = "Table Grid"

    # Gộp ngang w:gridSpan cho hàng 0 (cột 5..8) và hàng 1 (cột 5..6 và 7..8)
    table.cell(0, 5).merge(table.cell(0, 8))
    table.cell(1, 5).merge(table.cell(1, 6))
    table.cell(1, 7).merge(table.cell(1, 8))

    # Gộp dọc w:vMerge cho 5 cột đầu qua 3 hàng tiêu đề (0..2)
    for col_idx in range(5):
        table.cell(0, col_idx).merge(table.cell(2, col_idx))

    # Ghi nhãn cho 3 tầng tiêu đề
    top_headers = ["TT", "Chủ đề", "Loại câu", "Điểm/câu", "Nhóm chọn"]
    for col_idx, label in enumerate(top_headers):
        _set_cell_text(table.cell(0, col_idx), label)
    _set_cell_text(table.cell(0, 5), "Mức độ nhận thức (Số câu theo từng mức)")
    _set_cell_text(table.cell(1, 5), "TNKQ & Tự luận cơ bản")
    _set_cell_text(table.cell(1, 7), "TNKQ & Tự luận nâng cao")
    for col_idx, lvl_name in enumerate(["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"], 5):
        _set_cell_text(table.cell(2, col_idx), lvl_name)

    data_rows = [
        ["1", "Đọc hiểu văn bản nền tảng", "Tự luận", "0,40", "", "1", "0", "0", "0"],
        ["2", "Bài viết nghị luận tổng hợp", "Tự luận", "9,60", "Nhánh Tự luận", "0", "0", "1", "0"],
        ["3", "Kiến thức cơ bản trắc nghiệm", "Nhiều lựa chọn", "0,25", "Nhánh TNKQ", "8", "8", "0", "0"],
        ["4", "Phân tích nhận định Đúng-sai", "Đúng-sai", "1,00", "Nhánh TNKQ", "0", "2", "2", "0"],
        ["5", "Tính toán trả lời ngắn", "Trả lời ngắn", "0,40", "Nhánh TNKQ", "0", "0", "2", "2"],
        ["", "Tổng", "", "", "", "9", "10", "5", "2"],
    ]
    for r_offset, row_vals in enumerate(data_rows, 3):
        for c_idx, val in enumerate(row_vals):
            _set_cell_text(table.cell(r_offset, c_idx), val)

    # Bảo đảm rõ thuộc tính w:gridSpan và w:vMerge chuẩn OOXML
    tbl_xml = table._tbl
    assert tbl_xml.find(".//" + qn("w:gridSpan")) is not None
    assert tbl_xml.find(".//" + qn("w:vMerge")) is not None
    _save_deterministic_docx(doc, path)


def _col_ref(col_idx: int, row_idx: int) -> str:
    label = ""
    n = col_idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return f"{label}{row_idx}"


def _write_xlsx(
    path: Path,
    sheets: list[tuple[str, list[str], list[str]]],
    shared_strings: list[str],
) -> None:
    """Ghi tệp OOXML .xlsx thuần Python (không openpyxl) với đầy đủ sharedStrings, mergeCells và công thức."""
    ss_items = "".join(f"<si><t>{xml_escape(s)}</t></si>" for s in shared_strings)
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        f"{ss_items}</sst>"
    )

    sheet_entries = "".join(
        f'<sheet name="{xml_escape(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, (name, _, _) in enumerate(sheets, 1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_entries}</sheets></workbook>"
    )
    rel_items = [
        f'<Relationship Id="rId{idx}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{idx}.xml"/>'
        for idx in range(1, len(sheets) + 1)
    ]
    rel_items.append(
        f'<Relationship Id="rId{len(sheets) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
        'Target="sharedStrings.xml"/>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(rel_items)}</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}"
        '<Override PartName="/xl/sharedStrings.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        def put(arcname: str, data: str) -> None:
            info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data.encode("utf-8"))

        put("[Content_Types].xml", content_types)
        put("_rels/.rels", root_rels)
        put("xl/workbook.xml", workbook_xml)
        put("xl/_rels/workbook.xml.rels", workbook_rels)
        put("xl/sharedStrings.xml", shared_xml)
        for idx, (_name, row_xmls, merges) in enumerate(sheets, 1):
            merge_block = (
                f'<mergeCells count="{len(merges)}">'
                + "".join(f'<mergeCell ref="{m}"/>' for m in merges)
                + "</mergeCells>"
                if merges
                else ""
            )
            ws_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"<sheetData>{''.join(row_xmls)}</sheetData>{merge_block}</worksheet>"
            )
            put(f"xl/worksheets/sheet{idx}.xml", ws_xml)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())


def _build_merged_formulas_xlsx(path: Path) -> None:
    """Tạo matrix-cv7991-merged-formulas.xlsx gồm 2 sheet (Ma tran, Dac ta), mergeCells, =SUM() có cached và uncached, dấu phẩy thập phân."""
    strings: list[str] = []
    idx_map: dict[str, int] = {}

    def ss(text: str) -> int:
        if text not in idx_map:
            idx_map[text] = len(strings)
            strings.append(text)
        return idx_map[text]

    def str_cell(col: int, row: int, val: str) -> str:
        return f'<c r="{_col_ref(col, row)}" t="s"><v>{ss(val)}</v></c>'

    def num_cell(col: int, row: int, val: int | float) -> str:
        return f'<c r="{_col_ref(col, row)}"><v>{val}</v></c>'

    def formula_cell(col: int, row: int, formula: str, cached: int | float | None) -> str:
        v_tag = f"<v>{cached}</v>" if cached is not None else ""
        return f'<c r="{_col_ref(col, row)}"><f>{xml_escape(formula)}</f>{v_tag}</c>'

    # Sheet 1: Ma tran (2-row merged header + 5 rows + Tổng row)
    # Cols: A=Chủ đề, B=Loại câu, C=Điểm/câu, D=Nhóm chọn, E=Nhận biết, F=Thông hiểu, G=Vận dụng, H=Vận dụng cao, I=Tổng câu
    s1_rows: list[str] = []
    r1 = "".join([
        str_cell(0, 1, "Chủ đề"),
        str_cell(1, 1, "Loại câu"),
        str_cell(2, 1, "Điểm/câu"),
        str_cell(3, 1, "Nhóm chọn"),
        str_cell(4, 1, "Mức độ nhận thức"),
        str_cell(8, 1, "Tổng câu"),
    ])
    s1_rows.append(f'<row r="1">{r1}</row>')
    r2 = "".join([
        str_cell(4, 2, "Nhận biết"),
        str_cell(5, 2, "Thông hiểu"),
        str_cell(6, 2, "Vận dụng"),
        str_cell(7, 2, "Vận dụng cao"),
    ])
    s1_rows.append(f'<row r="2">{r2}</row>')

    data = [
        ("Đọc hiểu nền tảng", "Tự luận", "0,40", "", [1, 0, 0, 0]),
        ("Nghị luận chuyên sâu", "Tự luận", "9,60", "Nhánh Tự luận", [0, 0, 1, 0]),
        ("Kiến thức cơ bản", "Nhiều lựa chọn", "0,25", "Nhánh TNKQ", [8, 8, 0, 0]),
        ("Nhận định Đúng-sai", "Đúng-sai", "1,00", "Nhánh TNKQ", [0, 2, 2, 0]),
        ("Bài tập trả lời ngắn", "Trả lời ngắn", "0,40", "Nhánh TNKQ", [0, 0, 2, 2]),
    ]
    for row_num, (top, typ, pts_vi, grp, cnts) in enumerate(data, 3):
        cells = [
            str_cell(0, row_num, top),
            str_cell(1, row_num, typ),
            str_cell(2, row_num, pts_vi),
            str_cell(3, row_num, grp),
            *[num_cell(4 + j, row_num, cnts[j]) for j in range(4)],
            formula_cell(8, row_num, f"SUM(E{row_num}:H{row_num})", sum(cnts)),
        ]
        s1_rows.append(f'<row r="{row_num}">{"".join(cells)}</row>')

    # Hàng 8: Tổng — các cột E8..H8 có cached <v>, cột I8 là công thức không có <v> (uncached)
    col_sums = [sum(row[4][j] for row in data) for j in range(4)]
    tot_cells = [
        str_cell(0, 8, "Tổng"),
        *[formula_cell(4 + j, 8, f"SUM({chr(69 + j)}3:{chr(69 + j)}7)", col_sums[j]) for j in range(4)],
        formula_cell(8, 8, "SUM(I3:I7)", None),
    ]
    s1_rows.append(f'<row r="8">{"".join(tot_cells)}</row>')
    s1_merges = ["A1:A2", "B1:B2", "C1:C2", "D1:D2", "E1:H1", "I1:I2"]

    # Sheet 2: Dac ta
    s2_rows = [
        f'<row r="1">{str_cell(0, 1, "BẢNG ĐẶC TẢ ĐỀ KIỂM TRA CV 7991")}</row>',
        f'<row r="2">{"".join([str_cell(0, 2, "TT"), str_cell(1, 2, "Chủ đề"), str_cell(2, 2, "Yêu cầu cần đạt"), str_cell(3, 2, "Số câu")])}</row>',
        f'<row r="3">{"".join([num_cell(0, 3, 1), str_cell(1, 3, "Đọc hiểu nền tảng"), str_cell(2, 3, "Nêu được thông điệp và phân tích ngữ liệu"), num_cell(3, 3, 1)])}</row>',
        f'<row r="4">{"".join([num_cell(0, 4, 2), str_cell(1, 4, "Kiến thức cơ bản"), str_cell(2, 4, "Nhận biết và thông hiểu các khái niệm chuẩn"), num_cell(3, 4, 16)])}</row>',
        f'<row r="5">{"".join([str_cell(0, 5, "Tổng"), formula_cell(3, 5, "SUM(D3:D4)", 17)])}</row>',
    ]
    s2_merges = ["A1:D1"]

    _write_xlsx(path, [("Ma tran", s1_rows, s1_merges), ("Dac ta", s2_rows, s2_merges)], strings)


def _build_tuyensinh10_2pages_pdf(path: Path) -> None:
    """Tạo matrix-tuyensinh10-2pages.pdf 2 trang hợp lệ chứa dòng chủ đề xuống dòng và y = ax² (a ≠ 0)."""
    writer = PdfWriter()
    cmap_data = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
1 beginbfrange
<0020> <FFFF> <0020>
endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""
    cmap = DecodedStreamObject()
    cmap.set_data(cmap_data)
    cmap_ref = writer._add_object(cmap)

    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType2"),
            NameObject("/BaseFont"): NameObject("/CourierNew"),
            NameObject("/CIDSystemInfo"): DictionaryObject(
                {
                    NameObject("/Registry"): TextStringObject("Adobe"),
                    NameObject("/Ordering"): TextStringObject("Identity"),
                    NameObject("/Supplement"): NumberObject(0),
                }
            ),
            NameObject("/DW"): NumberObject(500),
        }
    )
    desc_ref = writer._add_object(descendant)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/CourierNew"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject([desc_ref]),
            NameObject("/ToUnicode"): cmap_ref,
        }
    )
    font_ref = writer._add_object(font)

    def add_page(lines: list[tuple[int, int, str]]) -> None:
        page = writer.add_blank_page(width=842, height=595)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        cmds = ["BT", "/F1 9 Tf"]
        for x, y, txt in lines:
            hex_str = txt.encode("utf-16-be").hex().upper()
            cmds.append(f"1 0 0 1 {x} {y} Tm <{hex_str}> Tj")
        cmds.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(cmds).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)

    # Tọa độ x chọn sao cho cột Nhận biết (~360), Thông hiểu (~460), Vận dụng (~560), Vận dụng cao (~660) tách rõ
    add_page(
        [
            (40, 550, "MA TRẬN ĐỀ THI TUYỂN SINH LỚP 10 THPT · MÔN TOÁN · Thời gian: 120 phút"),
            (40, 510, "Nội dung/Đơn vị kiến thức"),
            (360, 510, "Nhận biết"),
            (460, 510, "Thông hiểu"),
            (560, 510, "Vận dụng"),
            (660, 510, "Vận dụng cao"),
            (360, 492, "TL"),
            (460, 492, "TL"),
            (560, 492, "TL"),
            (660, 492, "TL"),
            (40, 464, "1. Biểu thức chứa căn và"),
            (360, 464, "2 câu"),
            (460, 464, "1 câu"),
            (40, 448, "rút gọn biểu thức đại số"),
            (360, 448, "(1,0 điểm)"),
            (460, 448, "(1,0 điểm)"),
            (40, 416, "2. Hệ phương trình và bài toán"),
            (360, 416, "1 câu"),
            (460, 416, "1 câu"),
            (40, 400, "thực tế chuyển động, năng suất"),
            (360, 400, "(0,5 điểm)"),
            (460, 400, "(1,5 điểm)"),
            (40, 368, "3. Hàm số bậc hai"),
            (360, 368, "1 câu"),
            (460, 368, "1 câu"),
            (40, 352, "y = ax² (a ≠ 0) và Vi-ét"),
            (360, 352, "(0,5 điểm)"),
            (460, 352, "(1,0 điểm)"),
        ]
    )
    add_page(
        [
            (40, 510, "Nội dung/Đơn vị kiến thức"),
            (360, 510, "Nhận biết"),
            (460, 510, "Thông hiểu"),
            (560, 510, "Vận dụng"),
            (660, 510, "Vận dụng cao"),
            (360, 492, "TL"),
            (460, 492, "TL"),
            (560, 492, "TL"),
            (660, 492, "TL"),
            (40, 464, "4. Đường tròn ngoại tiếp tam giác"),
            (460, 464, "2 câu"),
            (560, 464, "2 câu"),
            (40, 448, "và góc nội tiếp, tứ giác nội tiếp đường tròn (O)"),
            (460, 448, "(1,5 điểm)"),
            (560, 448, "(2,0 điểm)"),
            (40, 416, "5. Bất đẳng thức và bài toán"),
            (660, 416, "2 câu"),
            (40, 400, "cực trị đại số phân loại"),
            (660, 400, "(1,0 điểm)"),
            (40, 366, "Tổng"),
            (360, 366, "4 Câu"),
            (460, 366, "5 Câu"),
            (560, 366, "2 Câu"),
            (660, 366, "2 Câu"),
            (750, 366, "13 Câu"),
            (40, 320, "II. ĐẶC TẢ ĐỀ THI TUYỂN SINH LỚP 10 MÔN TOÁN"),
            (40, 302, "Phạm vi chuẩn: Căn thức, hàm số y = ax² (a ≠ 0), phương trình bậc hai, đường tròn."),
        ]
    )

    writer._ID = ArrayObject([ByteStringObject(b"soandethi-sc-pdf"), ByteStringObject(b"soandethi-sc-pdf")])
    writer.add_metadata({"/Producer": "SoanDeThi Corpus Generator", "/Title": "Ma tran Tuyen sinh 10 (2 trang)"})
    buf = io.BytesIO()
    writer.write(buf)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    # Xác thực đọc lại ngay bằng PdfReader(strict=True)
    reader = PdfReader(io.BytesIO(path.read_bytes()), strict=True)
    assert len(reader.pages) == 2


def _build_messy_edge_cases(edge_dir: Path) -> None:
    """Tạo 3 ca biên thực tế: (a) 2-table .docx, (b) spec-only .docx, (c) mismatched-sum .xlsx."""
    edge_dir.mkdir(parents=True, exist_ok=True)

    # (a) 2-table .docx: Bảng 1 = chú giải quy ước điểm, Bảng 2 = ma trận hợp lệ 10,00đ
    doc_2tbl = Document()
    doc_2tbl.add_heading("MA TRẬN ĐỀ KIỂM TRA CÓ BẢNG QUY ƯỚC ĐIỂM", level=1)
    doc_2tbl.add_paragraph("Bảng 1. Quy ước mức điểm theo dạng thức câu hỏi")
    legend = doc_2tbl.add_table(rows=5, cols=4)
    legend.style = "Table Grid"
    legend_rows = [
        ["Phần", "Dạng thức câu hỏi", "Quy ước điểm", "Ghi chú"],
        ["I", "Nhiều lựa chọn (MCQ)", "0,25 điểm / câu", "4 phương án A, B, C, D"],
        ["II", "Đúng-sai", "1,00 điểm / câu", "4 nhận định a, b, c, d"],
        ["III", "Trả lời ngắn", "0,50 điểm / câu", "Điền giá trị số"],
        ["IV", "Tự luận", "1,00 điểm / bài", "Có hướng dẫn chấm chi tiết"],
    ]
    for r_i, row_vals in enumerate(legend_rows):
        for c_i, val in enumerate(row_vals):
            legend.cell(r_i, c_i).text = val

    doc_2tbl.add_paragraph("Bảng 2. Ma trận số câu theo chủ đề và mức độ nhận thức")
    mat_tbl = doc_2tbl.add_table(rows=6, cols=7)
    mat_tbl.style = "Table Grid"
    mat_rows = [
        ["Chủ đề", "Loại câu", "Điểm/câu", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"],
        ["Biểu thức và phương trình", "Nhiều lựa chọn", "0,25", "6", "6", "0", "0"],
        ["Hàm số và đồ thị", "Đúng-sai", "1,00", "0", "1", "1", "0"],
        ["Hệ thức lượng", "Trả lời ngắn", "0,50", "0", "2", "2", "0"],
        ["Hình học đường tròn", "Tự luận", "1,50", "0", "0", "1", "1"],
        ["Tổng", "", "", "6", "9", "4", "1"],
    ]
    for r_i, row_vals in enumerate(mat_rows):
        for c_i, val in enumerate(row_vals):
            mat_tbl.cell(r_i, c_i).text = val
    _save_deterministic_docx(doc_2tbl, edge_dir / "two-tables-legend-and-matrix.docx")

    # (b) spec-only .docx: chỉ có bảng đặc tả, không có ma trận số câu -> kích hoạt spec_only_matrix
    doc_spec = Document()
    doc_spec.add_heading("BẢNG ĐẶC TẢ ĐỀ KIỂM TRA HỌC KÌ II", level=1)
    spec_tbl = doc_spec.add_table(rows=4, cols=6)
    spec_tbl.style = "Table Grid"
    spec_rows = [
        ["TT", "Chủ đề", "Nội dung kiến thức", "Yêu cầu cần đạt", "Mức độ đánh giá", "Ghi chú"],
        ["1", "Hàm số bậc hai", "Đồ thị y = ax²", "Vẽ được đồ thị parabol và nêu tính chất đối xứng.", "Thông hiểu", "Không nêu số câu"],
        ["2", "Đường tròn", "Tứ giác nội tiếp", "Chứng minh được tứ giác nội tiếp đường tròn.", "Vận dụng", "Bảng đặc tả thuần"],
        ["3", "Xác suất", "Biến cố ngẫu nhiên", "Xác định được không gian mẫu của phép thử.", "Nhận biết", "Chỉ báo năng lực"],
    ]
    for r_i, row_vals in enumerate(spec_rows):
        for c_i, val in enumerate(row_vals):
            spec_tbl.cell(r_i, c_i).text = val
    _save_deterministic_docx(doc_spec, edge_dir / "spec-only-no-counts.docx")

    # (c) mismatched-sum .xlsx: tổng cột và tổng điểm lệch 10,00 (9,50đ và Tổng ghi sai) -> phải báo lỗi sạch
    strings: list[str] = []
    idx_map: dict[str, int] = {}

    def ss(text: str) -> int:
        if text not in idx_map:
            idx_map[text] = len(strings)
            strings.append(text)
        return idx_map[text]

    def sc(c: int, r: int, v: str) -> str:
        return f'<c r="{_col_ref(c, r)}" t="s"><v>{ss(v)}</v></c>'

    def nc(c: int, r: int, v: int) -> str:
        return f'<c r="{_col_ref(c, r)}"><v>{v}</v></c>'

    bad_rows = [
        f'<row r="1">{"".join([sc(0, 1, "Chủ đề"), sc(1, 1, "Loại câu"), sc(2, 1, "Điểm/câu"), sc(3, 1, "Nhận biết"), sc(4, 1, "Thông hiểu"), sc(5, 1, "Vận dụng")])}</row>',
        f'<row r="2">{"".join([sc(0, 2, "Đại số"), sc(1, 2, "Nhiều lựa chọn"), sc(2, 2, "0,25"), nc(3, 2, 4), nc(4, 2, 4), nc(5, 2, 0)])}</row>',
        f'<row r="3">{"".join([sc(0, 3, "Hình học"), sc(1, 3, "Tự luận"), sc(2, 3, "2,50"), nc(3, 3, 0), nc(4, 3, 1), nc(5, 3, 2)])}</row>',
        # Tổng điểm thực là 8*0.25 + 3*2.50 = 9.50 != 10.00, đồng thời dòng Tổng ghi sai thành 5 / 5 / 3
        f'<row r="4">{"".join([sc(0, 4, "Tổng"), nc(3, 4, 5), nc(4, 4, 5), nc(5, 4, 3)])}</row>',
    ]
    _write_xlsx(edge_dir / "mismatched-sum.xlsx", [("Ma tran loi", bad_rows, [])], strings)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    exams = [
        ("SC-01.json", _make_sc01()),
        ("SC-02.json", _make_sc02()),
        ("SC-03.json", _make_sc03()),
        ("SC-04.json", _make_sc04()),
        ("SC-05.json", _make_sc05()),
        ("SC-06.json", _make_sc06()),
        ("SC-07.json", _make_sc07()),
        ("SC-08.json", _make_sc08()),
        ("SC-09.json", _make_sc09()),
        ("SC-10.json", _make_sc10()),
    ]
    for filename, payload in exams:
        target = OUT_DIR / filename
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    _build_merged_header_docx(OUT_DIR / "matrix-cv7991-merged-header.docx")
    _build_merged_formulas_xlsx(OUT_DIR / "matrix-cv7991-merged-formulas.xlsx")
    _build_tuyensinh10_2pages_pdf(OUT_DIR / "matrix-tuyensinh10-2pages.pdf")
    _build_messy_edge_cases(OUT_DIR / "matrix-messy-edge-cases")

    print(f"Đã tạo {len(exams)} đề thi SC-01..SC-10 và 4 nhóm ma trận tại {OUT_DIR}")


if __name__ == "__main__":
    main()
