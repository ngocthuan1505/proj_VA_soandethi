"""Kiểm tra trước khi xuất/in A4: đối chiếu ngắt trang bàn soạn ↔ A4 và rà thành phần OCR."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mach_backend.ai_contract import AIError, validate_math_markers, validate_math_structure
from mach_backend.ai_questions import saved_answer_label
from mach_backend.exam_spec_export import (
    _add_q4,
    _normalize_objective_question_for_label,
    _normalize_type,
    _q4_to_float,
    _question_quarter_points,
)
from mach_backend.ocr_structured import structure_ocr_reading

type OwnerResolver = Callable[[Request], str | None]

# Quy đổi chiều cao vùng in hữu ích khổ A4 (297mm - lề trên 18mm - lề dưới 20mm ≈ 255mm).
A4_CONTENT_HEIGHT_MM = 255.0
BASE_HEADER_HEIGHT_MM = 32.0
QUESTION_BASE_HEIGHT_MM = 10.0
LINE_HEIGHT_MM = 6.2
CHARS_PER_LINE = 78
OPTION_CHARS_PER_LINE = 72
RUBRIC_CHARS_PER_LINE = 68
TABLE_BASE_HEIGHT_MM = 8.0
TABLE_ROW_MIN_HEIGHT_MM = 8.5
IMAGE_HEIGHT_MM = 68.0
FIGURE_HEIGHT_MM = 62.0
DISPLAY_FORMULA_HEIGHT_MM = 14.0
INLINE_FORMULA_HEIGHT_MM = 7.5
ESSAY_EMPTY_SPACE_MM = 12.0

_LOCATION_PAGE_RE = re.compile(r"\b(?:trang|slide|page)\s*(\d+)\b", re.IGNORECASE)
_MATH_UNCERTAIN_REASONS: frozenset[str] = frozenset(
    {"unbalanced_dollar", "unbalanced_math_delimiter", "unbalanced_braces"}
)

_OCR_REASON_LABELS: dict[str, str] = {
    "page_needs_review": "trang OCR được đánh dấu cần giáo viên duyệt",
    "needs_ocr": "trang chưa được nhận dạng chữ (needsOCR)",
    "uncertain_tokens": "có đoạn/từ không chắc chắn từ OCR",
    "page_marked_uncertain": "trang được OCR đánh dấu không chắc chắn",
    "unknown_marker": "chứa nhãn [không rõ]",
    "replacement_char": "chứa ký tự lỗi mã hóa (\\ufffd)",
    "unbalanced_dollar": "công thức thiếu cặp dấu $",
    "unbalanced_math_delimiter": "dấu mở/đóng công thức không khớp",
    "unbalanced_braces": "ngoặc nhọn {} trong công thức không cân",
    "invalid_math": "công thức LaTeX lỗi cú pháp",
    "unclosed_figure_tag": "thẻ <figure> mở/đóng không khớp",
    "unclosed_svg_tag": "thẻ <svg> mở/đóng không khớp",
    "figure_placeholder": "chứa mốc hình giữ chỗ [HÌNH ...]",
    "source_page_needs_review": "liên kết tới trang nguồn OCR cần duyệt",
    "question_ocr_needs_review": "câu hỏi được gắn cờ ocrNeedsReview",
    "question_needs_review": "câu hỏi được gắn cờ needsReview",
}


def _reject_bool_int(value: Any, *, field_name: str) -> Any:
    if isinstance(value, bool):
        raise ValueError(f"Trường {field_name} phải là số nguyên dương.")
    return value


class EditorPageSnapshot(BaseModel):
    """Ảnh chụp phân trang trên bàn soạn của trình duyệt để đối chiếu với bản in A4."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1, le=5000)
    questionIds: list[str] = Field(max_length=500)
    oversize: bool = False

    @field_validator("page", mode="before")
    @classmethod
    def check_page_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value, field_name="page")


class ExportPreflightRequest(BaseModel):
    """Dữ liệu đầu vào kiểm tra tiền xuất bản in cho `POST /api/exports/preflight`."""

    model_config = ConfigDict(extra="forbid")

    exam: dict[str, Any]
    editorPages: list[EditorPageSnapshot] | None = Field(default=None, max_length=500)

    @field_validator("exam")
    @classmethod
    def check_exam_has_questions(cls, value: dict[str, Any]) -> dict[str, Any]:
        questions = value.get("questions")
        if not isinstance(questions, list):
            raise ValueError("Đề thi bắt buộc phải có trường questions dạng danh sách.")
        for idx, item in enumerate(questions, 1):
            if not isinstance(item, dict):
                raise ValueError(f"Câu {idx} trong exam.questions phải là đối tượng JSON.")
        return value


def _add_unique(target: list[str], item: str) -> None:
    if item not in target:
        target.append(item)


def _walk_rich_doc(node: Any, depth: int = 0) -> tuple[list[str], list[tuple[str, bool]], int]:
    """Duyệt TipTap richDoc an toàn độ sâu: trả về chữ, mathInline và số hàng bảng."""
    if not isinstance(node, dict) or depth > 64:
        return [], [], 0
    kind = node.get("type")
    if kind == "text":
        text = node.get("text")
        return ([text] if isinstance(text, str) else []), [], 0
    if kind == "mathInline":
        attrs = node.get("attrs")
        if isinstance(attrs, dict):
            latex = str(attrs.get("latex") or "")
            display = bool(attrs.get("display"))
            marker = f"$${latex}$$" if display else f"${latex}$"
            return [marker], [(latex, display)], 0
        return [], [], 0
    if kind == "hardBreak":
        return ["\n"], [], 0

    texts: list[str] = []
    maths: list[tuple[str, bool]] = []
    table_rows = 1 if kind == "tableRow" else 0
    children = node.get("content")
    if isinstance(children, list):
        for child in children:
            c_texts, c_maths, c_rows = _walk_rich_doc(child, depth + 1)
            texts.extend(c_texts)
            maths.extend(c_maths)
            table_rows += c_rows
    if kind in {"paragraph", "heading", "listItem", "blockquote"} and texts:
        texts.append("\n")
    return texts, maths, table_rows


def _question_stem_text(question: dict[str, Any]) -> str:
    raw = question.get("stem")
    if isinstance(raw, str) and raw.strip():
        return raw
    rich_doc = question.get("richDoc")
    if isinstance(rich_doc, dict):
        texts, _, _ = _walk_rich_doc(rich_doc)
        return "".join(texts).strip()
    return raw if isinstance(raw, str) else ""


def _font_scale(exam: dict[str, Any]) -> float:
    layout = exam.get("layout")
    if not isinstance(layout, dict):
        return 1.0
    raw_size = layout.get("fontSize")
    if isinstance(raw_size, bool) or not isinstance(raw_size, (int, float)):
        return 1.0
    if not math.isfinite(raw_size):
        return 1.0
    clamped = min(22.0, max(10.0, float(raw_size)))
    return clamped / 13.0


def _estimate_text_height_mm(
    text: str,
    *,
    chars_per_line: int = CHARS_PER_LINE,
    scale: float = 1.0,
) -> float:
    cleaned = text.strip()
    if not cleaned:
        return LINE_HEIGHT_MM * scale
    effective_chars = max(24, int(chars_per_line / max(0.8, scale)))
    total_lines = 0
    for paragraph in cleaned.splitlines():
        line = paragraph.strip()
        total_lines += max(1, math.ceil(len(line) / effective_chars)) if line else 1
    height = total_lines * LINE_HEIGHT_MM * scale
    # Cộng thêm khoảng đệm cho công thức hiển thị khối hoặc phân số/căn bậc cao trong văn bản.
    display_chunks = cleaned.count("$$") // 2 + cleaned.count(r"\[")
    height += display_chunks * 8.0 * scale
    return height


def _estimate_header_height_mm(exam: dict[str, Any], *, scale: float) -> float:
    height = BASE_HEADER_HEIGHT_MM * scale
    instructions = exam.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        height += _estimate_text_height_mm(instructions, scale=scale) + 3.0
    quote = exam.get("quote")
    if isinstance(quote, dict):
        quote_text = quote.get("text")
        if isinstance(quote_text, str) and quote_text.strip():
            height += 10.0 + _estimate_text_height_mm(quote_text, scale=scale)
    data_rows = exam.get("data")
    questions = exam.get("questions") or []
    uses_linked_table = any(
        isinstance(q, dict)
        and (q.get("dataLinked") is True or q.get("rule") in {"max", "difference"})
        for q in questions
    )
    if uses_linked_table and isinstance(data_rows, list) and data_rows:
        height += 12.0 + len(data_rows) * 7.5 + 42.0
    return height


def _estimate_question_height_mm(
    question: dict[str, Any],
    q_type: str,
    *,
    scale: float,
) -> float:
    height = QUESTION_BASE_HEIGHT_MM * scale

    stem_text = _question_stem_text(question)
    height += _estimate_text_height_mm(stem_text, scale=scale)

    # Nếu richDoc chứa bảng hoặc công thức display nhúng thì tính thêm chiều cao tương ứng.
    rich_doc = question.get("richDoc")
    if isinstance(rich_doc, dict):
        _, rich_maths, rich_table_rows = _walk_rich_doc(rich_doc)
        if rich_table_rows > 0:
            height += TABLE_BASE_HEIGHT_MM + rich_table_rows * TABLE_ROW_MIN_HEIGHT_MM * scale
        display_in_rich = sum(1 for _, is_display in rich_maths if is_display)
        if display_in_rich > 0:
            height += display_in_rich * 6.0 * scale

    # Công thức tách khối ở q.formulas.
    formulas = question.get("formulas")
    if isinstance(formulas, list):
        for formula in formulas:
            if not isinstance(formula, dict):
                continue
            latex = str(formula.get("latex") or "")
            is_display = formula.get("display") is not False
            if is_display:
                extra_rows = latex.count(r"\\")
                height += (DISPLAY_FORMULA_HEIGHT_MM + extra_rows * 6.5) * scale
            else:
                height += INLINE_FORMULA_HEIGHT_MM * scale

    # Bảng dữ liệu đính kèm ở q.tables.
    tables = question.get("tables")
    if isinstance(tables, list):
        for table in tables:
            if not isinstance(table, dict):
                continue
            rows = table.get("rows")
            if not isinstance(rows, list) or not rows:
                height += TABLE_BASE_HEIGHT_MM
                continue
            height += TABLE_BASE_HEIGHT_MM
            for row in rows:
                if not isinstance(row, list) or not row:
                    height += TABLE_ROW_MIN_HEIGHT_MM * scale
                    continue
                col_width = max(12, int(CHARS_PER_LINE / max(1, len(row))))
                max_cell_lines = max(
                    max(1, math.ceil(len(str(cell or "").strip()) / col_width)) for cell in row
                )
                height += max(TABLE_ROW_MIN_HEIGHT_MM, max_cell_lines * 5.8 + 2.8) * scale

    # Ảnh nhúng q.images và hình hình học q.figure.
    images = question.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                continue
            caption = str(image.get("caption") or "").strip()
            caption_extra = (
                _estimate_text_height_mm(caption, scale=scale) - LINE_HEIGHT_MM * scale
                if len(caption) > CHARS_PER_LINE
                else 0.0
            )
            height += IMAGE_HEIGHT_MM + max(0.0, caption_extra)

    if isinstance(question.get("figure"), dict):
        height += FIGURE_HEIGHT_MM

    # Các phương án A/B/C/D hoặc mệnh đề Đúng/Sai.
    options = question.get("options")
    if isinstance(options, list) and options:
        height += 4.0 * scale
        for opt in options:
            opt_text = str(opt or "")
            height += _estimate_text_height_mm(
                opt_text, chars_per_line=OPTION_CHARS_PER_LINE, scale=scale
            )
            height += 1.6 * scale

    # Barem chấm điểm (ảnh hưởng trực tiếp độ dài bản giáo viên / hướng dẫn chấm A4).
    rubric = question.get("rubric")
    if isinstance(rubric, list) and rubric:
        height += 8.0 * scale
        for step in rubric:
            if not isinstance(step, dict):
                continue
            step_text = str(
                step.get("text")
                or step.get("criterion")
                or step.get("content")
                or step.get("step")
                or ""
            )
            height += (
                _estimate_text_height_mm(
                    step_text, chars_per_line=RUBRIC_CHARS_PER_LINE, scale=scale
                )
                + 2.5 * scale
            )
    elif q_type == "essay":
        height += ESSAY_EMPTY_SPACE_MM * scale

    return round(height, 2)


def _is_question_approved(question: dict[str, Any]) -> bool:
    if question.get("approved") is True:
        return True
    version = question.get("v")
    approval = question.get("approval")
    if isinstance(approval, dict) and approval.get("status") == "approved":
        if version is None or approval.get("version") == version:
            return True
    verification = question.get("check")
    if isinstance(verification, dict) and verification.get("status") == "approved":
        if version is None or verification.get("version") == version:
            return True
    return False


def data_snapshot_hash(data: Any) -> str:
    """Tính mã băm chuẩn cho bảng dữ kiện liên kết (UC8)."""
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _data_hash_matches(given_hash: str, data: Any) -> bool:
    if given_hash == data_snapshot_hash(data):
        return True
    alt = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return given_hash == hashlib.sha256(alt.encode("utf-8")).hexdigest()


def _extract_explanation_numbers(text: str) -> list[float]:
    if not text:
        return []
    cleaned = re.sub(r"\b(?:Bảng|Câu|Bài|Hình|Mục)\s+\d+\b", " ", text, flags=re.IGNORECASE)
    nums: list[float] = []
    for raw in re.findall(r"(?<![A-Za-zÀ-ỹ0-9_])(-?\d+(?:[.,]\d+)?)", cleaned):
        try:
            val = float(raw.replace(",", "."))
        except ValueError:
            continue
        if math.isfinite(val):
            nums.append(val)
    return nums


def _parse_numeric_option(option: Any) -> float | None:
    if not isinstance(option, str):
        return None
    m = re.fullmatch(
        r"\s*(-?\d+(?:[.,]\d+)?)\s*(?:[A-Za-zÀ-ỹ%/°]+(?:\s+[A-Za-zÀ-ỹ%/°]+)*)?\s*",
        option.replace("−", "-"),
    )
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return val if math.isfinite(val) else None


def _audit_linked_data_question(
    question: dict[str, Any],
    ordinal: int,
    q_id: str,
    exam: dict[str, Any],
) -> list[dict[str, Any]]:
    """UC8: đối chiếu câu hỏi liên kết Bảng 1 về giá trị tính lại, đáp án, hash và giải thích."""
    rule = question.get("rule")
    is_linked = question.get("dataLinked") is True or rule in {"max", "difference"}
    if not is_linked:
        return []

    issues: list[dict[str, Any]] = []
    raw_data = exam.get("data")
    data_rows: list[tuple[str, float]] = []
    if isinstance(raw_data, list):
        for row in raw_data:
            if not isinstance(row, dict):
                continue
            val = row.get("value")
            if isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val):
                data_rows.append((str(row.get("label") or "").strip(), float(val)))

    if not data_rows:
        issues.append(
            {
                "code": "linked_data_mismatch",
                "severity": "blocking",
                "questionId": q_id,
                "ordinal": ordinal,
                "field": "data",
                "message": f"Câu {ordinal} liên kết bảng dữ kiện nhưng bảng dữ liệu đang trống.",
            }
        )
        return issues

    snap_hash = question.get("dataSnapshotHash")
    if (
        isinstance(snap_hash, str)
        and snap_hash.strip()
        and not _data_hash_matches(snap_hash.strip(), raw_data)
    ):
        issues.append(
            {
                "code": "linked_data_mismatch",
                "severity": "blocking",
                "questionId": q_id,
                "ordinal": ordinal,
                "field": "dataSnapshotHash",
                "message": (
                    f"Câu {ordinal} có mã đối chiếu dữ liệu (dataSnapshotHash) đã cũ so với "
                    "Bảng 1 hiện tại."
                ),
            }
        )

    check_obj = question.get("check")
    if isinstance(check_obj, dict) and check_obj.get("status") == "review":
        issues.append(
            {
                "code": "linked_data_mismatch",
                "severity": "blocking",
                "questionId": q_id,
                "ordinal": ordinal,
                "field": "check",
                "message": (
                    f"Câu {ordinal} liên kết dữ liệu đang ở trạng thái cần rà soát "
                    "(check.status='review')."
                ),
            }
        )

    raw_options = question.get("options")
    options: list[Any] = raw_options if isinstance(raw_options, list) else []
    ans = question.get("answer")
    explanation = str(question.get("explanation") or "")
    exp_nums = _extract_explanation_numbers(explanation)
    valid_data_vals = [v for _, v in data_rows]

    def _in_vals(target: float, pool: list[float]) -> bool:
        return any(math.isclose(target, item, rel_tol=0.0, abs_tol=1e-6) for item in pool)

    if rule == "max":
        max_val = max(valid_data_vals)
        max_indices = [
            i
            for i, (_, v) in enumerate(data_rows)
            if math.isclose(v, max_val, rel_tol=0.0, abs_tol=1e-6)
        ]
        if len(max_indices) != 1:
            issues.append(
                {
                    "code": "linked_data_mismatch",
                    "severity": "blocking",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "options",
                    "message": f"Câu {ordinal}: có nhiều mục cùng giá trị lớn nhất trong Bảng 1.",
                }
            )
        else:
            expected_label = data_rows[max_indices[0]][0]
            opt_matches = [
                i
                for i, opt in enumerate(options)
                if isinstance(opt, str) and opt.strip().casefold() == expected_label.casefold()
            ]
            if len(opt_matches) != 1 or (type(ans) is int and ans != opt_matches[0]):
                issues.append(
                    {
                        "code": "linked_data_mismatch",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "answer",
                        "message": (
                            f"Câu {ordinal}: đáp án/phương án chưa khớp mục lớn nhất "
                            f"({expected_label}) theo Bảng 1."
                        ),
                    }
                )
        if exp_nums:
            stale = not _in_vals(max_val, exp_nums) or any(
                not _in_vals(n, valid_data_vals)
                and not math.isclose(n, len(data_rows), abs_tol=1e-6)
                for n in exp_nums
            )
            if stale:
                issues.append(
                    {
                        "code": "linked_data_explanation_stale",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "explanation",
                        "message": (
                            f"Câu {ordinal}: lời giải chứa số liệu cũ chưa khớp giá trị lớn nhất "
                            f"({max_val:g}) của Bảng 1."
                        ),
                    }
                )

    elif rule == "difference":
        if len(data_rows) < 2:
            issues.append(
                {
                    "code": "linked_data_mismatch",
                    "severity": "blocking",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "data",
                    "message": f"Câu {ordinal}: Bảng 1 thiếu hai dòng dữ kiện để so sánh hiệu số.",
                }
            )
        else:
            stem_cf = _question_stem_text(question).casefold()
            mentioned: list[tuple[int, float]] = []
            for label, val in data_rows:
                if label and label.casefold() in stem_cf:
                    mentioned.append((stem_cf.index(label.casefold()), val))
            mentioned.sort(key=lambda pair: pair[0])
            if len(mentioned) >= 2:
                val1, val2 = mentioned[0][1], mentioned[1][1]
                expected_diff = (val2 - val1) if "ít hơn" in stem_cf else (val1 - val2)
                operands = [val1, val2]
            else:
                val_a, val_b = data_rows[0][1], data_rows[1][1]
                expected_diff = val_b - val_a
                operands = [val_a, val_b]

            if expected_diff <= 0:
                issues.append(
                    {
                        "code": "linked_data_mismatch",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "data",
                        "message": (
                            f"Câu {ordinal}: hiệu số Bảng 1 không dương ({expected_diff:g})."
                        ),
                    }
                )
            else:
                opt_matches = [
                    i
                    for i, opt in enumerate(options)
                    if (num := _parse_numeric_option(opt)) is not None
                    and math.isclose(num, expected_diff, rel_tol=0.0, abs_tol=1e-6)
                ]
                if len(opt_matches) != 1 or (type(ans) is int and ans != opt_matches[0]):
                    issues.append(
                        {
                            "code": "linked_data_mismatch",
                            "severity": "blocking",
                            "questionId": q_id,
                            "ordinal": ordinal,
                            "field": "answer",
                            "message": (
                                f"Câu {ordinal}: đáp án/phương án chưa khớp hiệu số "
                                f"{expected_diff:g} từ Bảng 1."
                            ),
                        }
                    )
                if exp_nums:
                    allowed = [*operands, expected_diff, *valid_data_vals]
                    stale = not _in_vals(expected_diff, exp_nums) or any(
                        not _in_vals(n, allowed)
                        and not math.isclose(n, len(data_rows), abs_tol=1e-6)
                        for n in exp_nums
                    )
                    if stale:
                        issues.append(
                            {
                                "code": "linked_data_explanation_stale",
                                "severity": "blocking",
                                "questionId": q_id,
                                "ordinal": ordinal,
                                "field": "explanation",
                                "message": (
                                    f"Câu {ordinal}: lời giải chứa số liệu cũ chưa khớp hiệu "
                                    f"({expected_diff:g}) của Bảng 1."
                                ),
                            }
                        )
    elif explanation:
        eq_match = re.search(
            r"(-?\d+(?:[.,]\d+)?)\s*[-−+]\s*(-?\d+(?:[.,]\d+)?)\s*=\s*(-?\d+(?:[.,]\d+)?)",
            explanation,
        )
        if eq_match:
            lhs = float(eq_match.group(1).replace(",", "."))
            rhs = float(eq_match.group(2).replace(",", "."))
            if not _in_vals(lhs, valid_data_vals) or not _in_vals(rhs, valid_data_vals):
                issues.append(
                    {
                        "code": "linked_data_explanation_stale",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "explanation",
                        "message": (
                            f"Câu {ordinal}: phép tính trong lời giải không khớp số liệu Bảng 1."
                        ),
                    }
                )

    return issues


def _audit_question_evidence_staleness(
    question: dict[str, Any],
    ordinal: int,
    q_id: str,
    exam: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """UC9: kiểm tra chứng cứ bị đánh dấu stale hoặc lệch nguồn/trang/phiên bản/ngữ liệu."""
    evidence_list = question.get("evidence")
    has_evidence = isinstance(evidence_list, list) and len(evidence_list) > 0

    has_exam_docs_list = isinstance(exam, dict) and isinstance(exam.get("docs"), list)
    docs_by_id: dict[str, dict[str, Any]] = {}
    if has_exam_docs_list:
        assert isinstance(exam, dict)
        for doc in exam["docs"]:
            if not isinstance(doc, dict):
                continue
            for id_field in ("id", "sourceId"):
                raw_id = doc.get(id_field)
                if raw_id is not None and str(raw_id).strip():
                    docs_by_id[str(raw_id).strip()] = doc

    src_obj = question.get("source")
    src_doc_id = (
        src_obj["docId"].strip()
        if isinstance(src_obj, dict)
        and isinstance(src_obj.get("docId"), str)
        and src_obj["docId"].strip()
        else None
    )
    src_obj_ver = (
        (
            src_obj.get("version")
            if src_obj.get("version") is not None
            else src_obj.get("sourceVersion")
        )
        if isinstance(src_obj, dict)
        else None
    )
    src_page: int | None = None
    if isinstance(src_obj, dict):
        for pkey in ("page", "pageNumber"):
            cand = src_obj.get(pkey)
            if type(cand) is int and cand >= 1:
                src_page = cand
                break
        if src_page is None and isinstance(src_obj.get("location"), str):
            loc_match = _LOCATION_PAGE_RE.search(src_obj["location"])
            if loc_match:
                parsed = int(loc_match.group(1))
                if parsed >= 1:
                    src_page = parsed
    if src_page is None and type(question.get("sourcePage")) is int and question["sourcePage"] >= 1:
        src_page = question["sourcePage"]

    reasons: list[str] = []

    if not has_evidence:
        if has_exam_docs_list and src_doc_id is not None:
            if src_doc_id not in docs_by_id:
                _add_unique(reasons, "tài liệu nguồn không còn trong đề (đã bị gỡ hoặc thay thế)")
            else:
                doc = docs_by_id[src_doc_id]
                doc_ver = (
                    doc.get("version")
                    if doc.get("version") is not None
                    else doc.get("sourceVersion")
                )
                if (
                    doc_ver is not None
                    and src_obj_ver is not None
                    and str(doc_ver) != str(src_obj_ver)
                ):
                    _add_unique(
                        reasons,
                        f"nguồn câu hỏi thuộc phiên bản v{src_obj_ver} "
                        f"(tài liệu hiện tại v{doc_ver})",
                    )
        if not reasons:
            return None
        return {
            "code": "stale_quote_evidence",
            "severity": "warning",
            "questionId": q_id,
            "ordinal": ordinal,
            "field": "evidence",
            "requiresReverification": True,
            "message": f"Câu {ordinal} có trích dẫn nguồn cần rà lại: {'; '.join(reasons)}.",
        }

    q_version = question.get("v")
    is_quote_question = question.get("quote") is True
    exam_quote_obj = exam.get("quote") if isinstance(exam, dict) else None
    raw_exam_quote = exam_quote_obj.get("text") if isinstance(exam_quote_obj, dict) else None
    norm_exam_quote = " ".join(raw_exam_quote.split()) if isinstance(raw_exam_quote, str) else ""

    for ev in evidence_list:
        if not isinstance(ev, dict):
            continue
        if ev.get("stale") is True:
            _add_unique(reasons, "trích dẫn được đánh dấu đã cũ (stale)")
        raw_ev_doc = ev.get("sourceId") if ev.get("sourceId") is not None else ev.get("docId")
        ev_doc_id = (
            str(raw_ev_doc).strip() if raw_ev_doc is not None and str(raw_ev_doc).strip() else None
        )
        ev_page: int | None = None
        ev_loc = ev.get("locator")
        if isinstance(ev_loc, dict) and ev_loc.get("kind") == "page":
            idx_val = ev_loc.get("index")
            if type(idx_val) is int and idx_val >= 1:
                ev_page = idx_val
        elif type(ev.get("page")) is int and ev["page"] >= 1:
            ev_page = ev["page"]

        if ev_doc_id != src_doc_id:
            if src_doc_id is None:
                _add_unique(
                    reasons,
                    "tài liệu nguồn đã gỡ hoặc chuyển sang bản nhập tay",
                )
            else:
                _add_unique(
                    reasons,
                    f"nguồn trích dẫn ({ev_doc_id or 'không rõ'}) "
                    f"lệch với tài liệu nguồn ({src_doc_id})",
                )
        elif (
            src_doc_id is not None
            and src_page is not None
            and ev_page is not None
            and ev_page != src_page
        ):
            _add_unique(
                reasons,
                f"trang trích dẫn ({ev_page}) lệch với trang nguồn ({src_page})",
            )

        ev_src_ver = ev.get("sourceVersion")
        if (
            src_obj_ver is not None
            and ev_src_ver is not None
            and str(src_obj_ver) != str(ev_src_ver)
        ):
            _add_unique(
                reasons,
                f"trích dẫn thuộc phiên bản nguồn v{ev_src_ver} (nguồn câu hỏi v{src_obj_ver})",
            )

        citation_doc_id = ev_doc_id or src_doc_id
        citation_version = ev_src_ver
        if citation_version is None and citation_doc_id == src_doc_id:
            citation_version = src_obj_ver
        if has_exam_docs_list and citation_doc_id is not None:
            if citation_doc_id not in docs_by_id:
                _add_unique(reasons, "tài liệu nguồn không còn trong đề (đã bị gỡ hoặc thay thế)")
            else:
                doc = docs_by_id[citation_doc_id]
                doc_ver = (
                    doc.get("version")
                    if doc.get("version") is not None
                    else doc.get("sourceVersion")
                )
                if (
                    doc_ver is not None
                    and citation_version is not None
                    and str(doc_ver) != str(citation_version)
                ):
                    _add_unique(
                        reasons,
                        f"trích dẫn thuộc phiên bản nguồn v{citation_version} "
                        f"(tài liệu hiện tại v{doc_ver})",
                    )
                doc_pages = doc.get("pages")
                if ev_page is not None and isinstance(doc_pages, list) and doc_pages:
                    doc_page_nums = {
                        p.get("number")
                        if type(p.get("number")) is int
                        else (p.get("page") if type(p.get("page")) is int else idx)
                        for idx, p in enumerate(doc_pages, 1)
                        if isinstance(p, dict)
                    }
                    if ev_page not in doc_page_nums:
                        _add_unique(
                            reasons,
                            f"trang trích dẫn ({ev_page}) không còn trong tài liệu nguồn",
                        )

        ev_q_ver = ev.get("questionVersion")
        if ev_q_ver is not None and q_version is not None and ev_q_ver != q_version:
            _add_unique(
                reasons,
                f"trích dẫn thuộc phiên bản v{ev_q_ver} (câu hiện tại v{q_version})",
            )

        if is_quote_question and isinstance(exam, dict):
            raw_ev_quote = ev.get("quote")
            norm_ev_quote = " ".join(raw_ev_quote.split()) if isinstance(raw_ev_quote, str) else ""
            if norm_ev_quote and (not norm_exam_quote or norm_ev_quote not in norm_exam_quote):
                _add_unique(
                    reasons,
                    "đoạn trích dẫn không còn xuất hiện trong ngữ liệu hiện tại của đề",
                )

    if not reasons:
        return None
    return {
        "code": "stale_quote_evidence",
        "severity": "warning",
        "questionId": q_id,
        "ordinal": ordinal,
        "field": "evidence",
        "requiresReverification": True,
        "message": f"Câu {ordinal} có trích dẫn nguồn cần rà lại: {'; '.join(reasons)}.",
    }


def _extract_source_ref(question: dict[str, Any]) -> tuple[str | None, int | None]:
    doc_id: str | None = None
    page_num: int | None = None

    source = question.get("source")
    if isinstance(source, dict):
        raw_doc_id = source.get("docId")
        if isinstance(raw_doc_id, str) and raw_doc_id.strip():
            doc_id = raw_doc_id.strip()
        for key in ("page", "pageNumber"):
            candidate = source.get(key)
            if type(candidate) is int and candidate >= 1:
                page_num = candidate
                break
        if page_num is None:
            location = source.get("location")
            if isinstance(location, str):
                match = _LOCATION_PAGE_RE.search(location)
                if match:
                    parsed = int(match.group(1))
                    if parsed >= 1:
                        page_num = parsed

    if page_num is None:
        raw_source_page = question.get("sourcePage")
        if type(raw_source_page) is int and raw_source_page >= 1:
            page_num = raw_source_page

    if doc_id is None:
        evidence = question.get("evidence")
        if isinstance(evidence, list):
            for entry in evidence:
                if not isinstance(entry, dict):
                    continue
                ev_source = entry.get("sourceId")
                if ev_source is not None and str(ev_source).strip():
                    doc_id = str(ev_source).strip()
                    locator = entry.get("locator")
                    if (
                        page_num is None
                        and isinstance(locator, dict)
                        and locator.get("kind") == "page"
                        and type(locator.get("index")) is int
                        and locator["index"] >= 1
                    ):
                        page_num = locator["index"]
                    break

    return doc_id, page_num


def _format_reasons_vi(reasons: list[str]) -> str:
    return "; ".join(_OCR_REASON_LABELS.get(code, code) for code in reasons)


def _scan_ocr_source_docs(
    exam: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[tuple[str, int]], dict[str, str], set[str]]:
    """Quét `exam.docs[*].pages[*]` bằng `structure_ocr_reading` để đánh dấu trang OCR cần duyệt."""
    ocr_items: list[dict[str, Any]] = []
    flagged_pages: set[tuple[str, int]] = set()
    doc_names: dict[str, str] = {}
    flagged_single_page_docs: set[str] = set()

    raw_docs = exam.get("docs")
    if not isinstance(raw_docs, list):
        return ocr_items, flagged_pages, doc_names, flagged_single_page_docs

    for doc_idx, doc in enumerate(raw_docs, 1):
        if not isinstance(doc, dict):
            continue
        doc_id = (
            str(doc["id"]).strip()
            if isinstance(doc.get("id"), str) and doc["id"].strip()
            else f"doc-{doc_idx}"
        )
        doc_name = str(doc.get("name") or f"Tài liệu {doc_idx}").strip()
        doc_names[doc_id] = doc_name
        doc_needs_review = doc.get("needsReview") is True

        raw_pages = doc.get("pages")
        pages_list: list[dict[str, Any]] = []
        if isinstance(raw_pages, list) and raw_pages:
            pages_list = [p for p in raw_pages if isinstance(p, dict)]
        elif isinstance(doc.get("text"), str) and doc["text"]:
            pages_list = [
                {
                    "number": 1,
                    "text": doc["text"],
                    "uncertain": doc.get("uncertain", False),
                    "needsReview": doc.get("needsReview"),
                }
            ]

        for page_idx, page in enumerate(pages_list, 1):
            raw_number = page.get("number")
            if type(raw_number) is not int or raw_number < 1:
                alt_page = page.get("page")
                raw_number = alt_page if type(alt_page) is int and alt_page >= 1 else page_idx
            page_num = raw_number
            page_text = page.get("text") if isinstance(page.get("text"), str) else ""

            raw_uncertain = page.get("uncertain", False)
            uncertain_tokens_count = 0
            if isinstance(raw_uncertain, bool):
                page_uncertain_bool = raw_uncertain
            elif isinstance(raw_uncertain, list):
                page_uncertain_bool = False
                uncertain_tokens_count += len(raw_uncertain)
            else:
                page_uncertain_bool = bool(raw_uncertain)

            extra_tokens = page.get("uncertainTokens")
            if isinstance(extra_tokens, list):
                uncertain_tokens_count += len(extra_tokens)

            structured = structure_ocr_reading(
                {
                    "pages": [
                        {
                            "number": page_num,
                            "text": page_text,
                            "uncertain": page_uncertain_bool,
                        }
                    ],
                    "method": page.get("method") or doc.get("method"),
                }
            )
            sp = structured["pages"][0]
            math_blocks = sp["math_blocks"]
            figures = sp["figures"]
            uncertain_regions = sp["uncertain_regions"]
            has_placeholder_figure = any(fig.get("kind") == "placeholder" for fig in figures)

            raw_page_review = page.get("needsReview")
            page_needs_review = (
                raw_page_review if isinstance(raw_page_review, bool) else doc_needs_review
            )

            reasons: list[str] = []
            if page_needs_review:
                _add_unique(reasons, "page_needs_review")
            if page.get("needsOCR") is True:
                _add_unique(reasons, "needs_ocr")
            if uncertain_tokens_count > 0:
                _add_unique(reasons, "uncertain_tokens")
            for region in uncertain_regions:
                _add_unique(reasons, str(region["reason"]))
            if has_placeholder_figure:
                _add_unique(reasons, "figure_placeholder")

            if reasons:
                flagged_pages.add((doc_id, page_num))
                if len(pages_list) == 1:
                    flagged_single_page_docs.add(doc_id)
                ocr_items.append(
                    {
                        "kind": "source_page",
                        "docId": doc_id,
                        "docName": doc_name,
                        "page": page_num,
                        "questionId": None,
                        "ordinal": None,
                        "reasons": reasons,
                        "mathBlockCount": len(math_blocks),
                        "figureCount": len(figures),
                        "uncertainCount": len(uncertain_regions) + uncertain_tokens_count,
                        "message": (
                            f"Tài liệu “{doc_name}” (Trang {page_num}) cần duyệt OCR: "
                            f"{_format_reasons_vi(reasons)}."
                        ),
                    }
                )

    return ocr_items, flagged_pages, doc_names, flagged_single_page_docs


def _validate_question_math(
    question: dict[str, Any],
    ordinal: int,
    q_id: str,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Kiểm tra cú pháp công thức trong văn bản, `formulas` và `mathInline` bằng `ai_contract`."""
    math_errors: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    standalone_formula_count = 0
    invalid_formula_count = 0
    standalone_invalid_count = 0

    def record_error(field: str, err: AIError, *, standalone: bool = False) -> None:
        nonlocal invalid_formula_count, standalone_invalid_count
        key = (field, str(err))
        if key in seen_keys:
            return
        seen_keys.add(key)
        invalid_formula_count += 1
        if standalone:
            standalone_invalid_count += 1
        math_errors.append(
            {
                "code": err.code,
                "severity": "blocking",
                "questionId": q_id,
                "ordinal": ordinal,
                "field": field,
                "message": f"Câu {ordinal} ({field}): {err}",
            }
        )

    def check_text_field(field: str, text: Any) -> None:
        if not isinstance(text, str) or not text:
            return
        try:
            validate_math_markers(text)
        except AIError as err:
            record_error(field, err)

    check_text_field("stem", question.get("stem"))
    check_text_field("explanation", question.get("explanation"))
    check_text_field("answerText", question.get("answerText"))

    options = question.get("options")
    if isinstance(options, list):
        for opt_idx, opt in enumerate(options, 1):
            check_text_field(f"options[{opt_idx}]", opt)

    rubric = question.get("rubric")
    if isinstance(rubric, list):
        for step_idx, step in enumerate(rubric, 1):
            if isinstance(step, dict):
                check_text_field(
                    f"rubric[{step_idx}]",
                    step.get("text")
                    or step.get("criterion")
                    or step.get("content")
                    or step.get("step"),
                )
                step_doc = step.get("richDoc")
                if isinstance(step_doc, dict):
                    _, step_maths, _ = _walk_rich_doc(step_doc)
                    for latex, _ in step_maths:
                        try:
                            validate_math_structure(latex)
                        except AIError as err:
                            record_error(f"rubric[{step_idx}]", err, standalone=True)

    tables = question.get("tables")
    if isinstance(tables, list):
        for tbl_idx, tbl in enumerate(tables, 1):
            if isinstance(tbl, dict) and isinstance(tbl.get("rows"), list):
                for row in tbl["rows"]:
                    if isinstance(row, list):
                        for cell in row:
                            check_text_field(f"tables[{tbl_idx}]", cell)

    formulas = question.get("formulas")
    if isinstance(formulas, list):
        for formula in formulas:
            if not isinstance(formula, dict):
                continue
            latex = formula.get("latex")
            if isinstance(latex, str):
                standalone_formula_count += 1
                try:
                    validate_math_structure(latex)
                except AIError as err:
                    record_error("formulas", err, standalone=True)

    for doc_field in ("richDoc", "explanationDoc"):
        doc = question.get(doc_field)
        if isinstance(doc, dict):
            _, doc_maths, _ = _walk_rich_doc(doc)
            for latex, _ in doc_maths:
                try:
                    validate_math_structure(latex)
                except AIError as err:
                    record_error(doc_field, err, standalone=True)

    option_docs = question.get("optionDocs")
    if isinstance(option_docs, list):
        for opt_idx, opt_doc in enumerate(option_docs, 1):
            if isinstance(opt_doc, dict):
                _, opt_maths, _ = _walk_rich_doc(opt_doc)
                for latex, _ in opt_maths:
                    try:
                        validate_math_structure(latex)
                    except AIError as err:
                        record_error(f"optionDocs[{opt_idx}]", err, standalone=True)

    return math_errors, standalone_formula_count, invalid_formula_count, standalone_invalid_count


def _collect_question_scan_text(question: dict[str, Any]) -> str:
    parts: list[str] = []
    stem = _question_stem_text(question)
    if stem:
        parts.append(stem)
    options = question.get("options")
    if isinstance(options, list):
        parts.extend(str(opt) for opt in options if isinstance(opt, str) and opt)
    for key in ("answerText", "explanation"):
        val = question.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    rubric = question.get("rubric")
    if isinstance(rubric, list):
        for step in rubric:
            if isinstance(step, dict):
                text = (
                    step.get("text")
                    or step.get("criterion")
                    or step.get("content")
                    or step.get("step")
                )
                if isinstance(text, str) and text:
                    parts.append(text)
    tables = question.get("tables")
    if isinstance(tables, list):
        for tbl in tables:
            if isinstance(tbl, dict) and isinstance(tbl.get("rows"), list):
                for row in tbl["rows"]:
                    if isinstance(row, list):
                        parts.extend(str(cell) for cell in row if isinstance(cell, str) and cell)
    images = question.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, dict) and isinstance(image.get("caption"), str):
                parts.append(image["caption"])
    figure = question.get("figure")
    if isinstance(figure, dict) and isinstance(figure.get("caption"), str):
        parts.append(figure["caption"])
    return "\n".join(parts)


def _validate_editor_pages_arg(
    editor_pages: list[dict[str, Any]] | None,
) -> tuple[int | None, dict[str, int], set[int], set[str]]:
    if editor_pages is None:
        return None, {}, set(), set()
    if not isinstance(editor_pages, list):
        raise AIError(
            "invalid_editor_pages",
            "Danh sách trang bàn soạn (editorPages) phải là mảng đối tượng.",
            http_status=422,
        )

    editor_page_by_qid: dict[str, int] = {}
    editor_oversize_pages: set[int] = set()
    editor_oversize_qids: set[str] = set()
    max_page = 0

    for entry in editor_pages:
        if not isinstance(entry, dict):
            raise AIError(
                "invalid_editor_pages",
                "Mỗi phần tử trong editorPages phải là đối tượng JSON.",
                http_status=422,
            )
        page_num = entry.get("page")
        if type(page_num) is not int or page_num < 1:
            raise AIError(
                "invalid_editor_pages",
                "Số trang trong editorPages phải là số nguyên dương (>= 1).",
                http_status=422,
            )
        qids = entry.get("questionIds")
        if not isinstance(qids, list) or any(not isinstance(qid, str) for qid in qids):
            raise AIError(
                "invalid_editor_pages",
                f"Trang {page_num} trong editorPages phải có questionIds là danh sách chuỗi.",
                http_status=422,
            )
        oversize = entry.get("oversize", False)
        if not isinstance(oversize, bool):
            raise AIError(
                "invalid_editor_pages",
                f"Trường oversize ở trang {page_num} phải là kiểu boolean.",
                http_status=422,
            )
        max_page = max(max_page, page_num)
        if oversize:
            editor_oversize_pages.add(page_num)
        for qid in qids:
            if qid not in editor_page_by_qid:
                editor_page_by_qid[qid] = page_num
            if oversize:
                editor_oversize_qids.add(qid)

    return max_page, editor_page_by_qid, editor_oversize_pages, editor_oversize_qids


def audit_export_preflight(
    exam: dict[str, Any],
    editor_pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Kiểm tra toàn diện đề thi trước khi xuất bản in A4 mà không làm biến đổi đầu vào."""
    if not isinstance(exam, dict):
        raise AIError("invalid_exam", "Dữ liệu đề thi phải là đối tượng JSON.", http_status=422)
    questions = exam.get("questions")
    if not isinstance(questions, list):
        raise AIError(
            "invalid_exam",
            "Đề thi phải có danh sách câu hỏi (questions).",
            http_status=422,
        )
    for idx, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            raise AIError(
                "invalid_question",
                f"Câu {idx} trong đề thi phải là đối tượng JSON.",
                http_status=422,
            )

    (
        editor_page_count,
        editor_page_by_qid,
        editor_oversize_pages,
        editor_oversize_qids,
    ) = _validate_editor_pages_arg(editor_pages)

    blocking_issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # 1. Quét tài liệu nguồn OCR trong exam.docs[*].pages[*].
    ocr_review_items, flagged_source_pages, doc_names, flagged_single_page_docs = (
        _scan_ocr_source_docs(exam)
    )

    # Kiểm tra công thức lỗi ở phần ngữ liệu chung (nếu có).
    quote = exam.get("quote")
    if isinstance(quote, dict) and isinstance(quote.get("text"), str) and quote["text"].strip():
        try:
            validate_math_markers(quote["text"])
        except AIError as err:
            blocking_issues.append(
                {
                    "code": err.code,
                    "severity": "blocking",
                    "questionId": None,
                    "ordinal": None,
                    "field": "quote",
                    "message": f"Ngữ liệu chung của đề có lỗi công thức: {err}",
                }
            )

    if not questions:
        blocking_issues.append(
            {
                "code": "empty_exam",
                "severity": "blocking",
                "questionId": None,
                "ordinal": None,
                "field": "questions",
                "message": "Đề thi chưa có câu hỏi nào để xuất bản in.",
            }
        )

    # 2. Ước lượng phân trang A4, rà câu hỏi về điểm/đáp án/barem/công thức/duyệt & OCR.
    scale = _font_scale(exam)
    header_height = _estimate_header_height_mm(exam, scale=scale)
    current_page = 1 if questions else 0
    used_height = header_height
    while used_height > A4_CONTENT_HEIGHT_MM and questions:
        current_page += 1
        used_height -= A4_CONTENT_HEIGHT_MM
    page_has_questions = False

    explicit_page_break_ordinals: list[int] = []
    oversize_pages_set: set[int] = set(editor_oversize_pages)
    oversize_question_ids: list[str] = []
    page_map: list[dict[str, Any]] = []
    page_mismatches: list[dict[str, Any]] = []

    approved_count = 0
    unapproved_count = 0
    raw_total_points_q4: int | float = 0
    common_points_q4: int | float = 0
    common_count = 0
    track_points_q4: dict[str, int | float] = {}
    track_counts: dict[str, int] = {}

    for ordinal, q in enumerate(questions, 1):
        raw_id = q.get("id")
        q_id = str(raw_id).strip() if isinstance(raw_id, str) and raw_id.strip() else f"q-{ordinal}"
        raw_group = q.get("choiceGroup")
        group_key = (
            raw_group.strip().casefold() if isinstance(raw_group, str) and raw_group.strip() else ""
        )

        # 2a. Chuẩn hóa dạng câu.
        try:
            q_type = _normalize_type(q.get("type"), ordinal)
        except AIError as err:
            blocking_issues.append(
                {
                    "code": err.code,
                    "severity": "blocking",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "type",
                    "message": str(err),
                }
            )
            q_type = "mcq"

        # 2b. Kiểm tra trạng thái duyệt giáo viên.
        if _is_question_approved(q):
            approved_count += 1
        else:
            unapproved_count += 1
            warnings.append(
                {
                    "code": "unapproved_question",
                    "severity": "warning",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "approval",
                    "message": f"Câu {ordinal} chưa được giáo viên duyệt bản hiện tại.",
                }
            )

        # 2c. Kiểm tra nội dung đề bài.
        stem_text = _question_stem_text(q)
        if not stem_text.strip():
            blocking_issues.append(
                {
                    "code": "empty_stem",
                    "severity": "blocking",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "stem",
                    "message": f"Câu {ordinal} đang trống nội dung đề bài.",
                }
            )

        # 2d. Kiểm tra điểm hợp lệ (tối đa 2 chữ số thập phân) và tổng barem.
        try:
            q4 = _question_quarter_points(q, ordinal)
            raw_total_points_q4 = _add_q4(raw_total_points_q4, q4)
            if group_key:
                track_points_q4[group_key] = _add_q4(track_points_q4.get(group_key, 0), q4)
                track_counts[group_key] = track_counts.get(group_key, 0) + 1
            else:
                common_points_q4 = _add_q4(common_points_q4, q4)
                common_count += 1
        except AIError as err:
            if group_key:
                track_counts[group_key] = track_counts.get(group_key, 0) + 1
            else:
                common_count += 1
            blocking_issues.append(
                {
                    "code": err.code,
                    "severity": "blocking",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "rubric" if err.code == "invalid_rubric" else "points",
                    "message": str(err),
                }
            )

        # 2e. Kiểm tra phương án / đáp án / barem theo dạng câu.
        if q_type in {"mcq", "truefalse"}:
            raw_options = q.get("options")
            min_opts, max_opts = (4, 8) if q_type == "mcq" else (4, 4)
            if (
                not isinstance(raw_options, list)
                or not (min_opts <= len(raw_options) <= max_opts)
                or any(not isinstance(opt, str) or not opt.strip() for opt in raw_options)
            ):
                opt_msg = (
                    f"Câu {ordinal} cần đủ 4 phương án có nội dung rõ ràng trước khi in."
                    if q_type == "truefalse"
                    else f"Câu {ordinal} cần từ 4 đến 8 phương án có nội dung rõ ràng trước khi in."
                )
                blocking_issues.append(
                    {
                        "code": "missing_options",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "options",
                        "message": opt_msg,
                    }
                )
            else:
                normalized_opts = {" ".join(opt.split()).casefold() for opt in raw_options}
                if len(normalized_opts) != len(raw_options):
                    warnings.append(
                        {
                            "code": "duplicate_options",
                            "severity": "warning",
                            "questionId": q_id,
                            "ordinal": ordinal,
                            "field": "options",
                            "message": f"Câu {ordinal} có phương án bị trùng nội dung.",
                        }
                    )

        if q_type in {"mcq", "truefalse", "short"}:
            if q.get("answerKnown") is False:
                blocking_issues.append(
                    {
                        "code": "missing_answer",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "answer",
                        "message": f"Câu {ordinal} chưa xác nhận đáp án đúng.",
                    }
                )
            else:
                try:
                    normalized_q = _normalize_objective_question_for_label(q, q_type)
                    label = saved_answer_label(normalized_q)
                    if label == "Chưa nhập đáp án":
                        blocking_issues.append(
                            {
                                "code": "missing_answer",
                                "severity": "blocking",
                                "questionId": q_id,
                                "ordinal": ordinal,
                                "field": "answer",
                                "message": f"Câu {ordinal} đang thiếu đáp án đúng.",
                            }
                        )
                except AIError as err:
                    if err.code != "invalid_math":
                        blocking_issues.append(
                            {
                                "code": err.code,
                                "severity": "blocking",
                                "questionId": q_id,
                                "ordinal": ordinal,
                                "field": "answer",
                                "message": f"Câu {ordinal}: {err}",
                            }
                        )
        else:
            raw_rubric = q.get("rubric")
            if raw_rubric is None or (isinstance(raw_rubric, list) and len(raw_rubric) == 0):
                blocking_issues.append(
                    {
                        "code": "missing_rubric",
                        "severity": "blocking",
                        "questionId": q_id,
                        "ordinal": ordinal,
                        "field": "rubric",
                        "message": f"Câu tự luận {ordinal} chưa có barem chấm điểm.",
                    }
                )
            elif isinstance(raw_rubric, list):
                for step_idx, step in enumerate(raw_rubric, 1):
                    if not isinstance(step, dict):
                        continue
                    step_text = str(
                        step.get("text")
                        or step.get("criterion")
                        or step.get("content")
                        or step.get("step")
                        or ""
                    ).strip()
                    if not step_text:
                        blocking_issues.append(
                            {
                                "code": "invalid_rubric",
                                "severity": "blocking",
                                "questionId": q_id,
                                "ordinal": ordinal,
                                "field": "rubric",
                                "message": (
                                    f"Ý {step_idx} trong barem câu {ordinal} chưa có nội dung."
                                ),
                            }
                        )

        # 2f. Kiểm tra cú pháp công thức bằng validate_math_markers / validate_math_structure.
        (
            math_errors,
            standalone_formula_count,
            invalid_formula_count,
            standalone_invalid_count,
        ) = _validate_question_math(q, ordinal, q_id)
        blocking_issues.extend(math_errors)

        # 2f-bis. UC8 (dữ kiện liên kết Bảng 1) và UC9 (trích dẫn nguồn cũ/lệch trang).
        blocking_issues.extend(_audit_linked_data_question(q, ordinal, q_id, exam))
        stale_evidence_warn = _audit_question_evidence_staleness(q, ordinal, q_id, exam)
        if stale_evidence_warn is not None:
            warnings.append(stale_evidence_warn)

        # 2g. Quét thành phần OCR cần duyệt trên câu hỏi và liên kết nguồn.
        q_scan_text = _collect_question_scan_text(q)
        q_structured = structure_ocr_reading(
            {"pages": [{"number": 1, "text": q_scan_text, "uncertain": False}]}
        )
        q_sp = q_structured["pages"][0]
        q_math_blocks = q_sp["math_blocks"]
        q_figures = q_sp["figures"]
        q_uncertain_regions = q_sp["uncertain_regions"]
        q_has_placeholder = any(fig.get("kind") == "placeholder" for fig in q_figures)

        # Nếu có công thức trần lỗi ngoặc ngoài dấu $ mà validate_math_markers chưa báo, ghi chặn.
        if not math_errors:
            for region in q_uncertain_regions:
                if region["reason"] in _MATH_UNCERTAIN_REASONS:
                    blocking_issues.append(
                        {
                            "code": "invalid_math",
                            "severity": "blocking",
                            "questionId": q_id,
                            "ordinal": ordinal,
                            "field": "stem",
                            "message": f"Câu {ordinal}: {region['detail']}",
                        }
                    )
                    break

        doc_id, source_page = _extract_source_ref(q)
        doc_name = doc_names.get(doc_id) if doc_id is not None else None

        q_ocr_reasons: list[str] = []
        if doc_id is not None and (
            (source_page is not None and (doc_id, source_page) in flagged_source_pages)
            or (source_page is None and doc_id in flagged_single_page_docs)
        ):
            _add_unique(q_ocr_reasons, "source_page_needs_review")
        if q.get("ocrNeedsReview") is True:
            _add_unique(q_ocr_reasons, "question_ocr_needs_review")
        if q.get("needsReview") is True:
            _add_unique(q_ocr_reasons, "question_needs_review")
        for region in q_uncertain_regions:
            _add_unique(q_ocr_reasons, str(region["reason"]))
        if standalone_invalid_count > 0 or (
            invalid_formula_count > 0
            and not any(r in _MATH_UNCERTAIN_REASONS for r in q_ocr_reasons)
        ):
            _add_unique(q_ocr_reasons, "invalid_math")
        if q_has_placeholder:
            _add_unique(q_ocr_reasons, "figure_placeholder")

        if q_ocr_reasons:
            source_hint = ""
            if doc_name is not None and source_page is not None:
                source_hint = f" ({doc_name} · Trang {source_page})"
            elif doc_name is not None:
                source_hint = f" ({doc_name})"
            elif source_page is not None:
                source_hint = f" (Trang {source_page})"
            uncertain_total = len(q_uncertain_regions) + standalone_invalid_count
            if invalid_formula_count > 0 and uncertain_total == 0:
                uncertain_total = invalid_formula_count
            ocr_review_items.append(
                {
                    "kind": "question",
                    "docId": doc_id,
                    "docName": doc_name,
                    "page": source_page,
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "reasons": q_ocr_reasons,
                    "mathBlockCount": len(q_math_blocks) + standalone_formula_count,
                    "figureCount": len(q_figures),
                    "uncertainCount": uncertain_total,
                    "message": (
                        f"Câu {ordinal}{source_hint} cần rà soát OCR: "
                        f"{_format_reasons_vi(q_ocr_reasons)}."
                    ),
                }
            )

        # 2h. Ước lượng vị trí trang A4 và đối chiếu với editorPages.
        explicit_break = q.get("pageBreak") is True
        if explicit_break:
            explicit_page_break_ordinals.append(ordinal)

        q_height = _estimate_question_height_mm(q, q_type, scale=scale)
        if explicit_break and (page_has_questions or used_height > 0.0):
            current_page += 1
            used_height = 0.0
            page_has_questions = False
        elif page_has_questions and used_height + q_height > A4_CONTENT_HEIGHT_MM:
            current_page += 1
            used_height = 0.0
            page_has_questions = False
        elif (
            not page_has_questions
            and used_height > 0.0
            and used_height + q_height > A4_CONTENT_HEIGHT_MM
            and q_height <= A4_CONTENT_HEIGHT_MM
        ):
            current_page += 1
            used_height = 0.0
            page_has_questions = False

        estimated_page = current_page
        used_height += q_height
        page_has_questions = True

        estimated_oversize = q_height > A4_CONTENT_HEIGHT_MM
        editor_page = editor_page_by_qid.get(q_id)
        is_oversize = estimated_oversize or (q_id in editor_oversize_qids)

        if estimated_oversize:
            oversize_pages_set.add(estimated_page)
        if is_oversize and q_id not in oversize_question_ids:
            oversize_question_ids.append(q_id)

        page_map.append(
            {
                "questionId": q_id,
                "ordinal": ordinal,
                "editorPage": editor_page,
                "estimatedA4Page": estimated_page,
                "explicitBreakBefore": explicit_break,
                "oversize": is_oversize,
            }
        )

        mismatch_reasons: list[str] = []
        if is_oversize:
            mismatch_reasons.append("oversize_page")
        if editor_page is not None and editor_page != estimated_page:
            mismatch_reasons.append("page_number_mismatch")
        elif editor_pages is not None and editor_page is None:
            mismatch_reasons.append("missing_from_editor_pages")

        if mismatch_reasons:
            details: list[str] = []
            if "oversize_page" in mismatch_reasons:
                details.append("vượt chiều cao một trang A4 (.oversize-page)")
            if "page_number_mismatch" in mismatch_reasons:
                details.append(
                    f"bàn soạn đặt ở trang {editor_page}, bản A4 dự kiến trang {estimated_page}"
                )
            if "missing_from_editor_pages" in mismatch_reasons:
                details.append("chưa có trong ảnh chụp phân trang bàn soạn")
            mismatch_message = f"Câu {ordinal}: {'; '.join(details)}."
            page_mismatches.append(
                {
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "editorPage": editor_page,
                    "estimatedA4Page": estimated_page,
                    "oversize": is_oversize,
                    "reasons": mismatch_reasons,
                    "message": mismatch_message,
                }
            )
            warnings.append(
                {
                    "code": (
                        "oversize_page"
                        if "oversize_page" in mismatch_reasons
                        else "page_break_mismatch"
                    ),
                    "severity": "warning",
                    "questionId": q_id,
                    "ordinal": ordinal,
                    "field": "pageBreak",
                    "message": mismatch_message,
                }
            )

    estimated_a4_page_count = current_page if questions else 0
    oversize_pages = sorted(oversize_pages_set)

    # Cảnh báo thêm nếu trang oversize không gắn câu hỏi nào vẫn tồn tại trong editorPages.
    if editor_oversize_pages and not oversize_question_ids:
        pages_text = ", ".join(str(p) for p in sorted(editor_oversize_pages))
        warnings.append(
            {
                "code": "oversize_page",
                "severity": "warning",
                "questionId": None,
                "ordinal": None,
                "field": "pageBreak",
                "message": f"Trang bàn soạn {pages_text} vượt chiều cao A4 (.oversize-page).",
            }
        )
    if (
        editor_page_count is not None
        and editor_page_count != estimated_a4_page_count
        and not page_mismatches
    ):
        warnings.append(
            {
                "code": "page_break_mismatch",
                "severity": "warning",
                "questionId": None,
                "ordinal": None,
                "field": "pageBreak",
                "message": (
                    f"Tổng số trang bàn soạn ({editor_page_count}) khác dự kiến bản A4 "
                    f"({estimated_a4_page_count})."
                ),
            }
        )

    page_break_alignment = {
        "editorPageCount": editor_page_count,
        "estimatedA4PageCount": estimated_a4_page_count,
        "explicitPageBreakOrdinals": explicit_page_break_ordinals,
        "oversizePages": oversize_pages,
        "oversizeQuestionIds": oversize_question_ids,
        "pageMismatches": page_mismatches,
        "pageMap": page_map,
    }

    if track_counts:
        primary_key = max(
            track_counts.keys(),
            key=lambda k: (float(track_points_q4.get(k, 0)), track_counts[k]),
        )
        effective_points_q4 = _add_q4(common_points_q4, track_points_q4.get(primary_key, 0))
        effective_questions = common_count + track_counts[primary_key]
    else:
        effective_points_q4 = common_points_q4
        effective_questions = common_count

    summary = {
        "totalQuestions": len(questions),
        "effectiveQuestions": effective_questions,
        "approvedCount": approved_count,
        "unapprovedCount": unapproved_count,
        "totalPoints": _q4_to_float(effective_points_q4),
        "totalPointsQ4": effective_points_q4,
        "rawTotalPoints": _q4_to_float(raw_total_points_q4),
        "blockingCount": len(blocking_issues),
        "warningCount": len(warnings),
        "ocrReviewCount": len(ocr_review_items),
        "pageMismatchCount": len(page_mismatches),
        "oversizePageCount": len(oversize_pages),
        "editorPageCount": editor_page_count,
        "estimatedA4PageCount": estimated_a4_page_count,
    }

    return {
        "ready": len(blocking_issues) == 0,
        "needsAttention": len(warnings) > 0 or len(ocr_review_items) > 0,
        "pageBreakAlignment": page_break_alignment,
        "ocrReviewItems": ocr_review_items,
        "blockingIssues": blocking_issues,
        "warnings": warnings,
        "summary": summary,
    }


def install_export_preflight(
    app: FastAPI,
    *,
    owner_resolver: OwnerResolver | None = None,
) -> None:
    """Đăng ký endpoint `POST /api/exports/preflight` tương thích cả local và team workspace."""

    def resolve_owner(request: Request) -> str:
        if owner_resolver is None:
            return "local"
        owner = owner_resolver(request)
        if owner is None or (isinstance(owner, str) and not owner.strip()):
            raise AIError(
                "auth_required",
                "Cần đăng nhập trước khi kiểm bản in.",
                http_status=401,
            )
        return owner.strip()

    @app.post("/api/exports/preflight")
    def export_preflight_endpoint(
        body: ExportPreflightRequest,
        request: Request,
    ) -> JSONResponse:
        try:
            owner_id = resolve_owner(request)
            editor_pages = (
                [page.model_dump() for page in body.editorPages]
                if body.editorPages is not None
                else None
            )
            report = audit_export_preflight(body.exam, editor_pages)
        except AIError as err:
            return JSONResponse(
                {"error": str(err), "code": err.code},
                status_code=err.http_status or 422,
                headers={
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        return JSONResponse(
            {**report, "ownerId": owner_id},
            status_code=200,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
