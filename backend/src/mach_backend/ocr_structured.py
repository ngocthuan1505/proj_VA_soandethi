"""Chuẩn hóa kết quả OCR nhiều trang: giữ công thức LaTeX, mốc hình vẽ và vùng nghi ngờ."""

from __future__ import annotations

import re
from typing import Any

from mach_backend.ai_contract import AIError, validate_math_structure

UNKNOWN_LABEL_PATTERN = re.compile(r"\[không rõ[^\]]*\]", re.IGNORECASE)
REPLACEMENT_CHAR_PATTERN = re.compile(r"\ufffd+")
FIGURE_TAG_PATTERN = re.compile(r"<figure\b[^>]*>.*?</figure>", re.IGNORECASE | re.DOTALL)
SVG_TAG_PATTERN = re.compile(r"<svg\b[^>]*>.*?</svg>", re.IGNORECASE | re.DOTALL)
OPEN_FIGURE_TAG_PATTERN = re.compile(r"<figure\b[^>]*>", re.IGNORECASE)
CLOSE_FIGURE_TAG_PATTERN = re.compile(r"</figure>", re.IGNORECASE)
OPEN_SVG_TAG_PATTERN = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
CLOSE_SVG_TAG_PATTERN = re.compile(r"</svg>", re.IGNORECASE)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
PLACEHOLDER_FIGURE_PATTERN = re.compile(r"\[(?:HÌNH|HINH|SƠ\s*ĐỒ|SO\s*DO)\b[^\]]*\]", re.IGNORECASE)
CAPTION_FIGURE_PATTERN = re.compile(
    r"(?<!\[)\b(?:Hình|Hinh|Sơ\s*đồ|So\s*do)\s+\d+(?:\.\d+)*[a-zA-Z]?\s*[:.](?:[^\n]*)",
    re.IGNORECASE,
)
MATH_ENV_PATTERN = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|cases|matrix|pmatrix|bmatrix)\}"
    r"(.*?)\\end\{\1\}",
    re.DOTALL,
)
BARE_MATH_COMMAND_PATTERN = re.compile(r"\\(?:dfrac|tfrac|frac|sqrt)\b")
PLAIN_EQUATION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_\\/=])"
    r"([A-Za-z0-9()+\-*/^_.,\\]+(?:\s*[+\-*/^_,]\s*[A-Za-z0-9()+\-*/^_.,\\]+)*)"
    r"\s*(?:=|\\le|\\ge|\\neq|\\approx|<=|>=)\s*"
    r"([A-Za-z0-9()+\-*/^_.,\\]+(?:\s*[+\-*/^_,]\s*[A-Za-z0-9()+\-*/^_.,\\]+)*)"
)
MATH_INDICATOR_PATTERN = re.compile(r"[+\-*/^_()\\]|(?:\b[a-zA-Z]\b)")


def _snippet(text: str, start: int, end: int, radius: int = 36) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in spans)


def _extract_braced_group(text: str, start: int) -> tuple[int, bool]:
    if start >= len(text) or text[start] != "{":
        return start, False
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1, True
        i += 1
    return len(text), False


def _extract_figures(
    text: str, page_number: int
) -> tuple[list[dict[str, Any]], list[tuple[int, int]], list[dict[str, Any]]]:
    """Phát hiện mốc hình vẽ, sơ đồ và thẻ figure/svg gắn theo số trang."""
    candidates: list[tuple[int, int, str, str, str | None]] = []
    occupied: list[tuple[int, int]] = []
    excluded_from_math: list[tuple[int, int]] = []
    uncertain: list[dict[str, Any]] = []

    def try_add(start: int, end: int, kind: str, label: str, src: str | None = None) -> None:
        if _overlaps((start, end), occupied):
            return
        occupied.append((start, end))
        candidates.append((start, end, kind, label, src))

    for match in FIGURE_TAG_PATTERN.finditer(text):
        inner_caption = re.search(
            r"<figcaption\b[^>]*>(.*?)</figcaption>", match.group(0), re.IGNORECASE | re.DOTALL
        )
        label = (
            re.sub(r"<[^>]+>", "", inner_caption.group(1)).strip()
            if inner_caption
            else f"Hình (thẻ <figure> trang {page_number})"
        )
        try_add(match.start(), match.end(), "figure_tag", label)
        for svg_match in SVG_TAG_PATTERN.finditer(match.group(0)):
            excluded_from_math.append(
                (match.start() + svg_match.start(), match.start() + svg_match.end())
            )

    for match in SVG_TAG_PATTERN.finditer(text):
        excluded_from_math.append((match.start(), match.end()))
        if not _overlaps((match.start(), match.end()), occupied):
            label_match = re.search(r'aria-label="([^"]+)"', match.group(0))
            label = label_match.group(1).strip() if label_match else f"SVG trang {page_number}"
            try_add(match.start(), match.end(), "svg_tag", label)

    for match in MARKDOWN_IMAGE_PATTERN.finditer(text):
        alt = match.group(1).strip() or f"Hình ảnh trang {page_number}"
        src = match.group(2).strip()
        try_add(match.start(), match.end(), "markdown_image", alt, src)
        # Không quét công thức trong phần đường dẫn ảnh markdown.
        excluded_from_math.append((match.start(2), match.end(2)))

    for match in PLACEHOLDER_FIGURE_PATTERN.finditer(text):
        try_add(match.start(), match.end(), "placeholder", match.group(0).strip())

    for match in CAPTION_FIGURE_PATTERN.finditer(text):
        try_add(match.start(), match.end(), "caption", match.group(0).strip())

    # Kiểm tra thẻ <figure> hoặc <svg> bị mở mà thiếu thẻ đóng.
    open_figs = len(OPEN_FIGURE_TAG_PATTERN.findall(text))
    close_figs = len(CLOSE_FIGURE_TAG_PATTERN.findall(text))
    if open_figs != close_figs:
        pos = text.lower().find("<figure")
        pos = 0 if pos < 0 else pos
        uncertain.append(
            {
                "page": page_number,
                "reason": "unclosed_figure_tag",
                "detail": "Thẻ <figure> mở và đóng không khớp số lượng.",
                "snippet": _snippet(text, pos, min(len(text), pos + 40)),
                "start": pos,
                "end": min(len(text), pos + 8),
            }
        )

    open_svgs = len(OPEN_SVG_TAG_PATTERN.findall(text))
    close_svgs = len(CLOSE_SVG_TAG_PATTERN.findall(text))
    if open_svgs != close_svgs:
        pos = text.lower().find("<svg")
        pos = 0 if pos < 0 else pos
        uncertain.append(
            {
                "page": page_number,
                "reason": "unclosed_svg_tag",
                "detail": "Thẻ <svg> mở và đóng không khớp số lượng.",
                "snippet": _snippet(text, pos, min(len(text), pos + 40)),
                "start": pos,
                "end": min(len(text), pos + 5),
            }
        )

    candidates.sort(key=lambda item: item[0])
    figures = [
        {
            "id": f"fig-p{page_number}-{idx}",
            "page": page_number,
            "kind": kind,
            "label": label,
            "raw": text[start:end],
            "src": src,
            "start": start,
            "end": end,
        }
        for idx, (start, end, kind, label, src) in enumerate(candidates, 1)
    ]
    return figures, excluded_from_math, uncertain


def _check_balanced_math(body: str) -> tuple[bool, str | None]:
    try:
        validate_math_structure(body)
        return True, None
    except AIError as err:
        return False, str(err)


def _scan_math_and_uncertain(
    text: str, page_number: int, excluded_spans: list[tuple[int, int]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Tách khối công thức LaTeX/phương trình và ghi nhận mọi dấu $, ngoặc {} lệch."""
    math_blocks: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    covered_spans: list[tuple[int, int]] = list(excluded_spans)

    pending: str | None = None
    open_pos = 0
    body_start = 0

    def in_excluded(pos: int) -> bool:
        return any(start <= pos < end for start, end in excluded_spans)

    def add_block(
        start: int,
        end: int,
        *,
        kind: str,
        display: bool,
        delimiter: str,
        latex: str,
        balanced: bool = True,
        detail: str | None = None,
    ) -> None:
        idx = len(math_blocks) + 1
        math_blocks.append(
            {
                "id": f"math-p{page_number}-{idx}",
                "page": page_number,
                "kind": kind,
                "display": display,
                "delimiter": delimiter,
                "latex": latex,
                "raw": text[start:end],
                "start": start,
                "end": end,
                "balanced": balanced,
            }
        )
        covered_spans.append((start, end))
        if not balanced:
            uncertain.append(
                {
                    "page": page_number,
                    "reason": "unbalanced_braces",
                    "detail": detail or "Ngoặc nhóm hoặc môi trường trong công thức không cân.",
                    "snippet": _snippet(text, start, end),
                    "start": start,
                    "end": end,
                }
            )

    i = 0
    n = len(text)
    while i < n:
        if in_excluded(i):
            i += 1
            continue

        ch = text[i]
        if ch == "\n" and pending == "$":
            uncertain.append(
                {
                    "page": page_number,
                    "reason": "unbalanced_dollar",
                    "detail": "Dấu $ mở công thức trên dòng chưa có dấu $ đóng.",
                    "snippet": _snippet(text, open_pos, i),
                    "start": open_pos,
                    "end": i,
                }
            )
            covered_spans.append((open_pos, i))
            pending = None
            i += 1
            continue

        if ch == "\\":
            pair = text[i : i + 2]
            if pair in {r"\(", r"\["}:
                if pending is None:
                    pending = r"\)" if pair == r"\(" else r"\]"
                    open_pos = i
                    body_start = i + 2
                else:
                    uncertain.append(
                        {
                            "page": page_number,
                            "reason": "unbalanced_math_delimiter",
                            "detail": f"Gặp {pair} khi khối công thức trước chưa đóng.",
                            "snippet": _snippet(text, open_pos, i + 2),
                            "start": open_pos,
                            "end": i + 2,
                        }
                    )
                    covered_spans.append((open_pos, i + 2))
                    pending = None
                i += 2
                continue
            if pair in {r"\)", r"\]"}:
                if pending == pair:
                    latex_body = text[body_start:i]
                    balanced, detail = _check_balanced_math(latex_body)
                    add_block(
                        open_pos,
                        i + 2,
                        kind="display" if pair == r"\]" else "inline",
                        display=pair == r"\]",
                        delimiter=r"\[" if pair == r"\]" else r"\(",
                        latex=latex_body,
                        balanced=balanced,
                        detail=detail,
                    )
                    pending = None
                else:
                    start_at = open_pos if pending is not None else i
                    uncertain.append(
                        {
                            "page": page_number,
                            "reason": "unbalanced_math_delimiter",
                            "detail": f"Dấu đóng {pair} không khớp dấu mở công thức.",
                            "snippet": _snippet(text, start_at, i + 2),
                            "start": start_at,
                            "end": i + 2,
                        }
                    )
                    covered_spans.append((start_at, i + 2))
                    pending = None
                i += 2
                continue
            i += 2
            continue

        if text[i : i + 2] == "$$":
            if pending is None:
                pending = "$$"
                open_pos = i
                body_start = i + 2
            elif pending == "$$":
                latex_body = text[body_start:i]
                balanced, detail = _check_balanced_math(latex_body)
                add_block(
                    open_pos,
                    i + 2,
                    kind="display",
                    display=True,
                    delimiter="$$",
                    latex=latex_body,
                    balanced=balanced,
                    detail=detail,
                )
                pending = None
            else:
                uncertain.append(
                    {
                        "page": page_number,
                        "reason": "unbalanced_dollar",
                        "detail": "Dấu $$ và dấu mở công thức trước đó không khớp.",
                        "snippet": _snippet(text, open_pos, i + 2),
                        "start": open_pos,
                        "end": i + 2,
                    }
                )
                covered_spans.append((open_pos, i + 2))
                pending = None
            i += 2
            continue

        if ch == "$":
            if pending is None:
                pending = "$"
                open_pos = i
                body_start = i + 1
            elif pending == "$":
                latex_body = text[body_start:i]
                balanced, detail = _check_balanced_math(latex_body)
                add_block(
                    open_pos,
                    i + 1,
                    kind="inline",
                    display=False,
                    delimiter="$",
                    latex=latex_body,
                    balanced=balanced,
                    detail=detail,
                )
                pending = None
            else:
                uncertain.append(
                    {
                        "page": page_number,
                        "reason": "unbalanced_dollar",
                        "detail": "Dấu $ đơn không khớp dấu mở công thức trước đó.",
                        "snippet": _snippet(text, open_pos, i + 1),
                        "start": open_pos,
                        "end": i + 1,
                    }
                )
                covered_spans.append((open_pos, i + 1))
                pending = None
            i += 1
            continue

        i += 1

    if pending is not None:
        reason = "unbalanced_dollar" if pending in {"$", "$$"} else "unbalanced_math_delimiter"
        uncertain.append(
            {
                "page": page_number,
                "reason": reason,
                "detail": f"Công thức mở bằng {pending} chưa được đóng trước hết trang.",
                "snippet": _snippet(text, open_pos, n),
                "start": open_pos,
                "end": n,
            }
        )
        covered_spans.append((open_pos, n))

    # Môi trường LaTeX ngoài dấu $...$ (như \begin{equation}...\end{equation}).
    for match in MATH_ENV_PATTERN.finditer(text):
        if _overlaps((match.start(), match.end()), covered_spans):
            continue
        balanced, detail = _check_balanced_math(match.group(2))
        add_block(
            match.start(),
            match.end(),
            kind="environment",
            display=True,
            delimiter="",
            latex=match.group(0),
            balanced=balanced,
            detail=detail,
        )

    # Lệnh LaTeX trần ngoài dấu $...$ như \frac{...}{...}, \sqrt{...} hoặc \sqrt[n]{...}.
    for match in BARE_MATH_COMMAND_PATTERN.finditer(text):
        if _overlaps((match.start(), match.end()), covered_spans):
            continue
        cmd = match.group(0)
        cursor = match.end()
        while cursor < n and text[cursor].isspace():
            cursor += 1
        if cmd == r"\sqrt" and cursor < n and text[cursor] == "[":
            close_bracket = text.find("]", cursor + 1)
            if close_bracket != -1:
                cursor = close_bracket + 1
                while cursor < n and text[cursor].isspace():
                    cursor += 1
        groups_needed = 2 if cmd in {r"\frac", r"\dfrac", r"\tfrac"} else 1
        groups_ok = True
        end_pos = cursor
        for _ in range(groups_needed):
            while end_pos < n and text[end_pos].isspace():
                end_pos += 1
            if end_pos >= n or text[end_pos] != "{":
                groups_ok = False
                break
            end_pos, ok = _extract_braced_group(text, end_pos)
            if not ok:
                groups_ok = False
                break
        if groups_ok:
            latex_raw = text[match.start() : end_pos]
            balanced, detail = _check_balanced_math(latex_raw)
            add_block(
                match.start(),
                end_pos,
                kind="latex_command",
                display=False,
                delimiter="",
                latex=latex_raw,
                balanced=balanced,
                detail=detail,
            )
        else:
            uncertain.append(
                {
                    "page": page_number,
                    "reason": "unbalanced_braces",
                    "detail": f"Lệnh {cmd} thiếu ngoặc nhọn đóng/mở đầy đủ.",
                    "snippet": _snippet(text, match.start(), min(n, end_pos + 10)),
                    "start": match.start(),
                    "end": min(n, end_pos),
                }
            )
            covered_spans.append((match.start(), min(n, end_pos)))

    # Phương trình toán học ngoài các khối công thức đã tách.
    for match in PLAIN_EQUATION_PATTERN.finditer(text):
        span = (match.start(), match.end())
        if _overlaps(span, covered_spans):
            continue
        segment = match.group(0).strip()
        if not MATH_INDICATOR_PATTERN.search(segment):
            continue
        if segment.count("{") != segment.count("}"):
            continue
        add_block(
            match.start(),
            match.end(),
            kind="equation",
            display=False,
            delimiter="",
            latex=segment,
            balanced=True,
        )

    # Kiểm tra ngoặc {} không cân ở phần văn bản ngoài các khối công thức đã kiểm.
    brace_stack: list[int] = []
    idx = 0
    while idx < n:
        if any(s <= idx < e for s, e in covered_spans):
            idx += 1
            continue
        ch = text[idx]
        if ch == "\\":
            idx += 2
            continue
        if ch == "{":
            brace_stack.append(idx)
        elif ch == "}":
            if brace_stack:
                brace_stack.pop()
            else:
                uncertain.append(
                    {
                        "page": page_number,
                        "reason": "unbalanced_braces",
                        "detail": "Gặp ngoặc nhọn đóng '}' dư thừa trong nội dung OCR.",
                        "snippet": _snippet(text, idx, idx + 1),
                        "start": idx,
                        "end": idx + 1,
                    }
                )
        idx += 1

    for unclosed_pos in brace_stack:
        uncertain.append(
            {
                "page": page_number,
                "reason": "unbalanced_braces",
                "detail": "Ngoặc nhọn mở '{' chưa được đóng trong nội dung OCR.",
                "snippet": _snippet(text, unclosed_pos, n),
                "start": unclosed_pos,
                "end": unclosed_pos + 1,
            }
        )

    math_blocks.sort(key=lambda item: item["start"])
    for order, block in enumerate(math_blocks, 1):
        block["id"] = f"math-p{page_number}-{order}"
    return math_blocks, uncertain


def structure_ocr_reading(reading: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa đầu ra OCR nhiều trang; giữ nguyên văn bản, công thức, hình và vùng nghi ngờ."""
    if not isinstance(reading, dict):
        raise AIError(
            "invalid_document_reading",
            "Kết quả OCR phải là đối tượng JSON chứa danh sách trang.",
            http_status=422,
        )
    raw_pages = reading.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise AIError(
            "invalid_document_reading",
            "Kết quả OCR phải có ít nhất một trang hợp lệ.",
            http_status=422,
        )

    seen_numbers: set[int] = set()
    validated_pages: list[tuple[int, str, bool]] = []
    for item in raw_pages:
        if not isinstance(item, dict):
            raise AIError(
                "invalid_document_reading",
                "Mỗi trang OCR phải là một đối tượng gồm số trang và văn bản.",
                http_status=422,
            )
        number = item.get("number")
        text = item.get("text")
        uncertain = item.get("uncertain", False)
        if type(number) is not int or number < 1:
            raise AIError(
                "invalid_document_reading",
                "Số trang OCR phải là số nguyên dương.",
                http_status=422,
            )
        if number in seen_numbers:
            raise AIError(
                "invalid_document_reading",
                f"Số trang {number} bị trùng lặp trong kết quả OCR.",
                http_status=422,
            )
        if not isinstance(text, str):
            raise AIError(
                "invalid_document_reading",
                f"Trang {number} thiếu nội dung văn bản kiểu chuỗi.",
                http_status=422,
            )
        if not isinstance(uncertain, bool):
            raise AIError(
                "invalid_document_reading",
                f"Trường uncertain ở trang {number} phải là kiểu boolean.",
                http_status=422,
            )
        seen_numbers.add(number)
        validated_pages.append((number, text, uncertain))

    validated_pages.sort(key=lambda entry: entry[0])

    pages_out: list[dict[str, Any]] = []
    all_math: list[dict[str, Any]] = []
    all_figures: list[dict[str, Any]] = []
    all_uncertain: list[dict[str, Any]] = []

    for page_number, text, raw_uncertain in validated_pages:
        page_figures, fig_excluded, fig_uncertain = _extract_figures(text, page_number)
        page_math, math_uncertain = _scan_math_and_uncertain(text, page_number, fig_excluded)
        page_uncertain: list[dict[str, Any]] = [*fig_uncertain, *math_uncertain]

        for match in UNKNOWN_LABEL_PATTERN.finditer(text):
            page_uncertain.append(
                {
                    "page": page_number,
                    "reason": "unknown_marker",
                    "detail": "Phát hiện nhãn [không rõ] từ OCR; cần giáo viên đối chiếu bản gốc.",
                    "snippet": _snippet(text, match.start(), match.end()),
                    "start": match.start(),
                    "end": match.end(),
                }
            )

        for match in REPLACEMENT_CHAR_PATTERN.finditer(text):
            page_uncertain.append(
                {
                    "page": page_number,
                    "reason": "replacement_char",
                    "detail": "Phát hiện ký tự lỗi mã hóa (\\ufffd); cần giáo viên kiểm tra lại.",
                    "snippet": _snippet(text, match.start(), match.end()),
                    "start": match.start(),
                    "end": match.end(),
                }
            )

        if raw_uncertain:
            page_uncertain.append(
                {
                    "page": page_number,
                    "reason": "page_marked_uncertain",
                    "detail": "Trang được OCR đánh dấu không chắc chắn (uncertain=True).",
                    "snippet": text[:120].strip(),
                    "start": 0,
                    "end": len(text),
                }
            )

        page_uncertain.sort(key=lambda region: (region["start"], region["reason"]))

        pages_out.append(
            {
                "number": page_number,
                "text": text,
                "raw_uncertain": raw_uncertain,
                "uncertain": bool(raw_uncertain or page_uncertain),
                "math_blocks": page_math,
                "figures": page_figures,
                "uncertain_regions": page_uncertain,
            }
        )
        all_math.extend(page_math)
        all_figures.extend(page_figures)
        all_uncertain.extend(page_uncertain)

    notes = reading.get("notes")
    method = reading.get("method")
    return {
        "method": str(method) if isinstance(method, str) and method else "ocr_structured",
        "page_count": len(pages_out),
        "pages": pages_out,
        "math_blocks": all_math,
        "figures": all_figures,
        "uncertain_regions": all_uncertain,
        "needs_teacher_review": bool(all_uncertain),
        "notes": str(notes) if isinstance(notes, str) else "",
        "full_text": "\n\n".join(f"--- Trang {p['number']} ---\n{p['text']}" for p in pages_out),
    }
