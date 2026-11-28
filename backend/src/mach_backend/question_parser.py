"""Tách câu hỏi từ văn bản đề cũ phía Python kèm chẩn đoán lỗi theo từng trang và câu."""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_PARSE_TEXT = 1_000_000
MAX_PARSE_PAGES = 200
MAX_IMAGES = 50
MAX_IMAGE_DATA_LENGTH = 12_000_000

_MARKER_RE = re.compile(r"^\[\[HINH:[\w-]+\]\]$")
_IMAGE_DATA_RE = re.compile(r"^data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$")
_ANSWER_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:HƯỚNG DẪN CHẤM(?: VÀ (?:BIỂU|THANG) ĐIỂM)?|ĐÁP ÁN VÀ THANG ĐIỂM)\s*(?:\n|$)"
)
_BLOCK_SPLIT_RE = re.compile(r"(?=^\s*(?:Câu|Bài)\s+\d+\s*[:.(])", re.MULTILINE)
_BLOCK_START_RE = re.compile(r"^\s*(Câu|Bài)\s+(\d+)\s*[:.(]")
_HEADER_STRIP_RE = re.compile(r"^\s*(?:Câu|Bài)\s+\d+\s*[.:)]?\s*")
_ANY_MARKER_RE = re.compile(r"\[\[HINH:[\w-]+\]\]")
_END_MARKER_RE = re.compile(r"[—-]\s*Hết\s*[—-][\s\S]*$", re.IGNORECASE)
_POINTS_RE = re.compile(r"^\((-?\d+(?:[.,]\d+)?)\s*điểm\)[.:]?\s*")
_OPTION_SPLIT_RE = re.compile(r"(?:^|\n|\t+|\s{2,})([ABCD])[.)]\s*")
_OCR_UNCERTAIN_RE = re.compile(r"\[(?:không|chưa)\s+rõ[^\]]*\]|\ufffd", re.IGNORECASE)


def _reject_bool_int(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Số trang phải là số nguyên dương.")
    return value


class ParsePageInput(BaseModel):
    """Một trang văn bản nguồn gửi lên để tách câu và báo lỗi theo trang."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=5000)
    text: str = Field(default="", max_length=MAX_PARSE_TEXT)
    images: list[dict[str, Any]] = Field(default_factory=list, max_length=200)

    @field_validator("number", mode="before")
    @classmethod
    def check_number_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)


class ParseQuestionsRequest(BaseModel):
    """Yêu cầu tách câu từ văn bản đơn hoặc nhiều trang."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=MAX_PARSE_TEXT)
    images: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    page: int | None = Field(default=None, ge=1, le=5000)
    pages: list[ParsePageInput] | None = Field(default=None, max_length=MAX_PARSE_PAGES)

    @field_validator("page", mode="before")
    @classmethod
    def check_page_not_bool(cls, value: Any) -> Any:
        if value is None:
            return None
        return _reject_bool_int(value)

    @model_validator(mode="after")
    def validate_total_size(self) -> ParseQuestionsRequest:
        if self.pages is not None and sum(len(item.text) for item in self.pages) > MAX_PARSE_TEXT:
            raise ValueError("Tổng dung lượng văn bản các trang vượt quá 1.000.000 ký tự.")
        return self


def _sanitize_images(images: Any) -> list[dict[str, str]]:
    if not isinstance(images, list):
        return []
    safe: list[dict[str, str]] = []
    for item in images[:MAX_IMAGES]:
        if not isinstance(item, dict):
            continue
        marker = item.get("marker")
        data = item.get("data") or ""
        if (
            isinstance(marker, str)
            and isinstance(data, str)
            and _MARKER_RE.fullmatch(marker)
            and len(data) < MAX_IMAGE_DATA_LENGTH
            and _IMAGE_DATA_RE.fullmatch(data)
        ):
            caption = item.get("caption")
            safe.append(
                {
                    "marker": marker,
                    "data": data,
                    "caption": caption
                    if isinstance(caption, str) and caption
                    else "Hình từ tài liệu gốc",
                }
            )
    return safe


def _has_unbalanced_math(texts: list[str]) -> bool:
    combined = "\n".join(texts)
    unescaped_dollars = 0
    brace_depth = 0
    escaped = False
    for ch in combined:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "$":
            unescaped_dollars += 1
        elif ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth < 0:
                return True
    return unescaped_dollars % 2 != 0 or brace_depth != 0


def _location_prefix(page: int | None, source_label: str) -> str:
    return f"Trang {page} · {source_label}" if page is not None else source_label


def _add_issue(
    issues: list[dict[str, Any]],
    warnings: list[str],
    *,
    code: str,
    severity: str,
    page: int | None,
    question_number: int | None,
    label: str,
    message: str,
) -> None:
    issues.append(
        {
            "code": code,
            "severity": severity,
            "page": page,
            "questionNumber": question_number,
            "label": label,
            "message": message,
        }
    )
    warnings.append(message)


def _parse_single_text(
    raw_text: str,
    raw_images: Any,
    *,
    page: int | None,
    seen_numbers: set[tuple[str, int]],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    safe_images = _sanitize_images(raw_images)
    source = _ANSWER_SECTION_RE.split(raw_text, maxsplit=1)[0]
    blocks = [
        item.strip()
        for item in _BLOCK_SPLIT_RE.split(source)
        if item.strip() and _BLOCK_START_RE.match(item.strip())
    ]
    parsed: list[dict[str, Any]] = []
    for block in blocks:
        header = _BLOCK_START_RE.match(block)
        assert header is not None
        kind_word = header.group(1)
        q_number = int(header.group(2))
        source_label = f"{kind_word} {q_number}"
        essay = kind_word == "Bài"
        loc = _location_prefix(page, source_label)
        warnings: list[str] = []
        needs_review = False

        if (kind_word, q_number) in seen_numbers:
            _add_issue(
                issues,
                warnings,
                code="duplicate_question_number",
                severity="warning",
                page=page,
                question_number=q_number,
                label=source_label,
                message=f"{loc}: Trùng số hiệu {source_label} trong tài liệu nhập.",
            )
        seen_numbers.add((kind_word, q_number))

        attached = [
            {"data": im["data"], "caption": im["caption"]}
            for im in safe_images
            if im["marker"] in block
        ]
        body = _HEADER_STRIP_RE.sub("", block)
        body = _ANY_MARKER_RE.sub("", body)
        body = _END_MARKER_RE.sub("", body).strip()

        points: float | None = None
        points_match = _POINTS_RE.match(body)
        if points_match:
            points = float(points_match.group(1).replace(",", "."))
            body = body[points_match.end() :].strip()
            if points <= 0 or abs(round(points * 4) - points * 4) > 1e-6:
                _add_issue(
                    issues,
                    warnings,
                    code="invalid_points_step",
                    severity="warning",
                    page=page,
                    question_number=q_number,
                    label=source_label,
                    message=f"{loc}: Điểm ({points:g}) phải dương và là bội của 0,25.",
                )
                needs_review = True

        if _OCR_UNCERTAIN_RE.search(block):
            needs_review = True
            _add_issue(
                issues,
                warnings,
                code="ocr_uncertain",
                severity="warning",
                page=page,
                question_number=q_number,
                label=source_label,
                message=f"{loc}: Có ký tự mờ từ OCR cần đối chiếu bản gốc.",
            )

        option_matches = list(_OPTION_SPLIT_RE.finditer(body))
        has_abcd = (
            len(option_matches) == 4 and "".join(m.group(1) for m in option_matches) == "ABCD"
        )
        item: dict[str, Any]
        if not has_abcd:
            stem = body
            if essay:
                item: dict[str, Any] = {
                    "stem": stem,
                    "type": "essay",
                    "options": [],
                    "answer": 0,
                    "rubric": [],
                    "incomplete": False,
                }
            else:
                item = {
                    "stem": stem,
                    "type": "mcq",
                    "options": ["", "", "", ""],
                    "answer": 0,
                    "incomplete": True,
                }
                _add_issue(
                    issues,
                    warnings,
                    code="missing_options",
                    severity="warning",
                    page=page,
                    question_number=q_number,
                    label=source_label,
                    message=f"{loc}: Trắc nghiệm chưa đủ 4 phương án A, B, C, D.",
                )
        else:
            stem = body[: option_matches[0].start()].strip()
            options = [
                body[
                    option_matches[idx].end() : (
                        option_matches[idx + 1].start()
                        if idx + 1 < len(option_matches)
                        else len(body)
                    )
                ].strip()
                for idx in range(4)
            ]
            item = {
                "stem": stem,
                "type": "mcq",
                "options": options,
                "answer": 0,
                "incomplete": False,
            }

        if not stem.strip():
            needs_review = True
            _add_issue(
                issues,
                warnings,
                code="empty_stem",
                severity="warning",
                page=page,
                question_number=q_number,
                label=source_label,
                message=f"{loc}: Nội dung đề bài đang trống.",
            )

        if _has_unbalanced_math([item["stem"], *item["options"]]):
            needs_review = True
            _add_issue(
                issues,
                warnings,
                code="unbalanced_math",
                severity="warning",
                page=page,
                question_number=q_number,
                label=source_label,
                message=f"{loc}: Công thức LaTeX thiếu cặp dấu $ hoặc ngoặc {{}}.",
            )

        if attached:
            item["images"] = attached
        if points is not None and points > 0:
            item["points"] = points
        if page is not None:
            item["sourcePage"] = page
        item["sourceLabel"] = source_label
        item["questionNumber"] = q_number
        item["needsReview"] = needs_review or item["incomplete"]
        if warnings:
            item["warnings"] = warnings
        parsed.append(item)
    return parsed


def parse_questions_with_diagnostics(
    text: str,
    images: Any = None,
    *,
    page: int | None = None,
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Tách câu hỏi theo cấu trúc legacy và trả kèm chẩn đoán chi tiết từng trang/câu."""
    seen_numbers: set[tuple[str, int]] = set()
    issues: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    pages_scanned = 1

    if pages:
        pages_scanned = len(pages)
        for entry in pages:
            page_num = entry["number"]
            questions.extend(
                _parse_single_text(
                    entry.get("text", ""),
                    entry.get("images", []),
                    page=page_num,
                    seen_numbers=seen_numbers,
                    issues=issues,
                )
            )
    else:
        questions.extend(
            _parse_single_text(
                text,
                images or [],
                page=page,
                seen_numbers=seen_numbers,
                issues=issues,
            )
        )

    if not questions:
        scope_label = f"Trang {page}" if page is not None else "Văn bản nhập"
        issues.append(
            {
                "code": "no_questions_found",
                "severity": "error",
                "page": page,
                "questionNumber": None,
                "label": scope_label,
                "message": (f"{scope_label}: Chưa tách được câu đánh số “Câu 1.” hoặc “Bài 1.”."),
            }
        )

    incomplete_count = sum(1 for q in questions if q["incomplete"])
    needs_review_count = sum(1 for q in questions if q["needsReview"])
    return {
        "questions": questions,
        "issues": issues,
        "summary": {
            "totalQuestions": len(questions),
            "completeCount": len(questions) - incomplete_count,
            "incompleteCount": incomplete_count,
            "needsReviewCount": needs_review_count,
            "pagesScanned": pages_scanned,
            "issueCount": len(issues),
        },
    }


def install_question_parser(app: FastAPI) -> None:
    """Đăng ký endpoint `POST /api/parse-questions` thuần Python trên FastAPI."""

    @app.post("/api/parse-questions")
    def parse_questions_endpoint(body: ParseQuestionsRequest) -> dict[str, Any]:
        pages_payload = (
            [item.model_dump() for item in body.pages] if body.pages is not None else None
        )
        return parse_questions_with_diagnostics(
            body.text,
            body.images,
            page=body.page,
            pages=pages_payload,
        )
