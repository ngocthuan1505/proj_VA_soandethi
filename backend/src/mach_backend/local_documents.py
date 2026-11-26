"""Nhập nguồn văn bản và xuất bản đề local, không gọi dịch vụ bên ngoài."""

import base64
import binascii
import html
import io
import json
import math
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4
from xml.etree import ElementTree as ET

from pypdf import PdfReader, apply_configuration
from pypdf.errors import PyPdfError

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer, saved_answer_label
from mach_backend.export_assets import render_assets
from mach_backend.export_preflight import audit_export_preflight
from mach_backend.matrix_import import validate_raster
from mach_backend.presentation import PRESENTATION_CONTROLS, PRESENTATION_CSS, PRESENTATION_SCRIPT
from mach_backend.word_export import (
    DRAFT_BANNER_TITLE,
    export_docx,
    export_inputs,
    field_document,
    format_draft_warning,
    image_bytes,
    match_question_warnings,
    math_parts,
    normalize_draft_warnings,
    recipient_line,
    uses_table,
    watermark_image_bytes,
)
from mach_backend.word_math_read import paragraph_text

MAX_DOCUMENT = 15 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
PRESENTATION = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
SLIDE_PART = re.compile(r"ppt/slides/slide\d+\.xml")


class Page(TypedDict):
    number: int
    text: str


def pdf_pages(data):
    if not data.startswith(b"%PDF-"):
        raise AIError("invalid_document", "Nội dung tệp không phải PDF.")
    try:
        with apply_configuration(
            maximum_declared_stream_length=8_000_000,
            zlib_maximum_output_length=8_000_000,
            array_based_stream_maximum_output_length=8_000_000,
            lzw_maximum_output_length=8_000_000,
            run_length_maximum_output_length=8_000_000,
        ):
            reader = PdfReader(io.BytesIO(data), strict=True, xref_stream_maximum_entries=100000)
            if reader.is_encrypted:
                raise AIError(
                    "encrypted_document",
                    "PDF có mật khẩu. Hãy mở và lưu bản không khóa trước khi nhập.",
                )
            if not 1 <= len(reader.pages) <= 100:
                raise AIError("document_limit", "Chọn PDF từ1đến100trang; hãy tách tệp lớn.")
            pages, size = [], 0
            for number, page in enumerate(reader.pages, 1):
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > 8_000_000:
                    raise AIError(
                        "document_limit", "Trang PDF quá phức tạp; hãy tách hoặc làm nhẹ tệp."
                    )
                text = page.extract_text() or ""
                size += len(text)
                if size > 200000:
                    raise AIError(
                        "document_limit",
                        "Văn bản vượt200.000ký tự. Tách phần cần dùng trước khi nhập.",
                    )
                pages.append({"number": number, "text": text, "needsOCR": not bool(text.strip())})
            return pages
    except AIError:
        raise
    except (PyPdfError, ValueError, OSError, RecursionError):
        raise AIError(
            "invalid_document", "Không đọc được PDF hoặc tệp quá phức tạp. Hãy lưu lại PDF rồi thử."
        ) from None


def pptx_slides(archive):
    manifest = "ppt/presentation.xml"
    if manifest not in archive.namelist():
        # Một số gói cũ chỉ chứa phần văn bản các slide, không có thứ tự trình chiếu.
        slides = [
            (int(Path(name).stem.removeprefix("slide")), name)
            for name in archive.namelist()
            if SLIDE_PART.fullmatch(name)
        ]
        return sorted(slides)

    relationships = "ppt/_rels/presentation.xml.rels"
    if sum(archive.getinfo(name).file_size for name in (manifest, relationships)) > MAX_DOCUMENT:
        raise ValueError
    relation_xml = ET.fromstring(archive.read(relationships))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relation_xml.findall(PACKAGE_REL + "Relationship")
        if item.get("TargetMode", "Internal") == "Internal"
        and item.get("Type") == OFFICE_REL + "/slide"
    }
    presentation = ET.fromstring(archive.read(manifest))
    slides = []
    path = f"{PRESENTATION}sldIdLst/{PRESENTATION}sldId"
    for position, slide in enumerate(presentation.findall(path), 1):
        target = targets[slide.attrib[f"{{{OFFICE_REL}}}id"]]
        name = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "ppt/" + target)
        if not SLIDE_PART.fullmatch(name):
            raise ValueError
        slides.append((position, name))
    return slides


def _extract_zip_warnings(ext: str, slide_roots: list[tuple[int, ET.Element, str]]) -> list[dict]:
    warnings: list[dict] = []
    if ext == ".docx":
        ole_count = sum(
            1
            for _, root, _ in slide_roots
            for obj in root.iter(W + "object")
            if any(
                "Equation" in str(el.attrib) or el.tag.endswith("OLEObject") for el in obj.iter()
            )
        )
        if ole_count:
            warnings.append(
                {
                    "code": "mathtype_ole_formulas",
                    "count": ole_count,
                    "message": (
                        f"Phát hiện {ole_count} công thức MathType OLE (Equation.DSMT4) dạng đối "
                        "tượng nhúng nên chữ đọc trực tiếp có thể thiếu; "
                        "hãy kiểm tra hoặc dùng OCR ảnh."
                    ),
                }
            )
    elif ext == ".pptx":
        image_only_slides = [
            number
            for number, root, text in slide_roots
            if not text.strip()
            and any(el.tag in {PRESENTATION + "pic", DRAWING + "blip"} for el in root.iter())
        ]
        if image_only_slides:
            warnings.append(
                {
                    "code": "image_only_slides",
                    "slides": image_only_slides,
                    "message": (
                        "Slide chỉ có ảnh, không đọc được chữ trực tiếp: "
                        + ", ".join(str(number) for number in image_only_slides)
                        + ". Hãy đối chiếu bản gốc hoặc đọc bằng OCR."
                    ),
                }
            )
    return warnings


def extract_text(name, data_url):
    if not isinstance(name, str) or not isinstance(data_url, str):
        raise AIError("invalid_document", "Tệp nguồn chưa hợp lệ.")
    if len(data_url) > MAX_DOCUMENT * 4 // 3 + 200:
        raise AIError("invalid_document", "Tệp nguồn vượt giới hạn 15 MB.")
    warnings: list[dict] = []
    try:
        header, encoded = data_url.split(",", 1)
        if not header.startswith("data:") or not header.endswith(";base64"):
            raise ValueError
        data = base64.b64decode(encoded, validate=True)
        if len(data) > MAX_DOCUMENT:
            raise AIError("invalid_document", "Tệp nguồn vượt giới hạn 15 MB.")
        ext = Path(name).suffix.lower()
        pages: list[Page]
        if ext in {".txt", ".md"}:
            pages = [{"number": 1, "text": data.decode("utf-8-sig")}]
        elif ext == ".pdf":
            pages = pdf_pages(data)
            if not any(p["text"].strip() for p in pages):
                raise AIError(
                    "document_ai_consent",
                    "PDF này là bản scan hoặc không có chữ. Cần cho phép gửi "
                    "tới Gemini để đọc; chưa gửi tệp.",
                )
        elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
            validate_raster(data, ext)
            raise AIError(
                "document_ai_consent",
                "Ảnh cần được nhận dạng. Cần cho phép gửi tới Gemini để đọc; chưa gửi tệp.",
            )
        elif ext == ".xlsx":
            raise AIError(
                "unsupported_document",
                "Tệp Excel (.xlsx) dùng để nhập bảng ma trận. "
                "Hãy mở Ma trận → Nhập ma trận từ file để nạp tệp này.",
            )
        elif ext in {".docx", ".pptx"}:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    parts = pptx_slides(archive) if ext == ".pptx" else [(1, "word/document.xml")]
                    if not parts:
                        raise KeyError("missing_parts")
                    if sum(archive.getinfo(part_name).file_size for _, part_name in parts) > (
                        MAX_DOCUMENT
                    ):
                        raise AIError(
                            "invalid_document",
                            "Nội dung giải nén của tệp vượt giới hạn 15 MB.",
                        )
                    parsed_parts = [
                        (number, ET.fromstring(archive.read(part_name)))
                        for number, part_name in parts
                    ]
                    pages = []
                    slide_roots: list[tuple[int, ET.Element, str]] = []
                    for number, root in parsed_parts:
                        text = "\n".join(
                            paragraph_text(p)
                            if ext == ".docx"
                            else "".join(t.text or "" for t in p.iter(DRAWING + "t"))
                            for p in root.iter()
                            if p.tag in {W + "p", DRAWING + "p"}
                        )
                        pages.append({"number": number, "text": text})
                        slide_roots.append((number, root, text))
                    warnings = _extract_zip_warnings(ext, slide_roots)
            except AIError:
                raise
            except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError):
                if ext == ".docx":
                    raise AIError(
                        "invalid_document",
                        "Tệp Word (.docx) bị hỏng hoặc không đúng định dạng Word hiện đại. "
                        "Hãy mở tệp trong Word và lưu lại dạng .docx rồi thử lại.",
                    ) from None
                raise AIError(
                    "invalid_document",
                    "Tệp trình chiếu (.pptx) bị hỏng hoặc thiếu cấu trúc slide hợp lệ.",
                ) from None
        else:
            raise AIError(
                "unsupported_document",
                "Chọn TXT, MD, DOCX, PPTX, PDF hoặc ảnh PNG/JPEG/WebP.",
            )
    except AIError:
        raise
    except (ValueError, UnicodeError, binascii.Error, zipfile.BadZipFile, ET.ParseError, KeyError):
        raise AIError("invalid_document", "Không đọc được nội dung tệp nguồn.") from None
    if not any(page["text"].strip() for page in pages):
        if warnings:
            raise AIError("empty_document", warnings[0]["message"])
        raise AIError("empty_document", "Không tìm thấy chữ trong tệp. Hãy dán nội dung nguồn.")
    if sum(len(page["text"]) for page in pages) > 200000:
        raise AIError("document_limit", "Văn bản vượt 200.000 ký tự. Hãy tách phần cần dùng.")
    return {
        "pages": pages,
        "method": "pypdf_local_text" if ext == ".pdf" else "python_local_text",
        "sentToAI": False,
        "warnings": warnings,
    }


def plain(value):
    return html.escape(str(value or "")).replace("\n", "<br>")


def points(value):
    return str(value).replace(".", ",") + " điểm" if value is not None else ""


def inline_html(text):
    return "".join(
        '<span class="math">' + plain(value) + "</span>" if is_math else plain(value)
        for is_math, value in math_parts(str(text or ""))
    )


def _image_html(data: Any, caption: Any = "", *, in_cell: bool = False) -> str:
    if (
        not isinstance(data, str)
        or len(data) > MAX_DOCUMENT * 2
        or not re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+", data)
    ):
        raise AIError("invalid_image", "Hình trong câu chưa có dữ liệu hợp lệ để xuất.")
    binary, _, _ = image_bytes(data)
    encoded = "data:image/png;base64," + base64.b64encode(binary).decode()
    alt = html.escape(str(caption or "Hình câu hỏi"), quote=True)
    if in_cell:
        caption_text = str(caption or "").strip()
        caption_html = (
            f'<small class="cell-caption">{plain(caption_text)}</small>' if caption_text else ""
        )
        return f'<img src="{html.escape(encoded, quote=True)}" alt="{alt}">{caption_html}'
    return (
        f'<figure><img style="max-width:100%;max-height:250px" '
        f'src="{html.escape(encoded, quote=True)}" alt="{alt}">'
        f"<figcaption>{plain(caption)}</figcaption></figure>"
    )


def rich(node, depth=0):
    if not isinstance(node, dict) or depth > 64:
        return ""
    kind = node.get("type")
    if kind == "text":
        text = inline_html(node.get("text"))
        for mark in node.get("marks", []):
            tag = {"bold": "strong", "italic": "em", "underline": "u", "strike": "s"}.get(
                mark.get("type")
            )
            if tag:
                text = f"<{tag}>{text}</{tag}>"
            attrs = mark.get("attrs", {})
            if mark.get("type") in {"highlight", "textStyle"}:
                styles = []
                if re.fullmatch(r"#[0-9a-fA-F]{6}", attrs.get("color", "")):
                    styles.append(
                        ("background-color:" if mark["type"] == "highlight" else "color:")
                        + attrs["color"]
                    )
                if attrs.get("fontFamily") in {"Times New Roman", "Arial", "Calibri"}:
                    styles.append("font-family:" + attrs["fontFamily"])
                if re.fullmatch(r"\d{1,2}(?:\.\d)?(?:px|pt)", str(attrs.get("fontSize", ""))):
                    styles.append("font-size:" + attrs["fontSize"])
                text = (
                    '<span style="'
                    + html.escape(";".join(styles), quote=True)
                    + '">'
                    + text
                    + "</span>"
                )
            if mark.get("type") == "link" and re.match(r"https?://", attrs.get("href", "")):
                text = '<a href="' + html.escape(attrs["href"], quote=True) + '">' + text + "</a>"
        return text
    if kind == "mathInline":
        attrs = node.get("attrs", {})
        return (
            '<span class="math" data-display="'
            + str(bool(attrs.get("display"))).lower()
            + '">'
            + plain(attrs.get("latex"))
            + "</span>"
        )
    if kind == "hardBreak":
        return "<br>"
    if kind == "horizontalRule":
        return "<hr>"
    if kind == "image":
        attrs = node.get("attrs", {})
        return _image_html(
            attrs.get("src") or attrs.get("data"),
            attrs.get("alt") or attrs.get("caption") or "",
            in_cell=True,
        )
    if kind == "codeBlock":
        parts = [
            "<br>" if child.get("type") == "hardBreak" else plain(child.get("text"))
            for child in node.get("content", [])
        ]
        return f'<pre class="code-block"><code>{"".join(parts)}</code></pre>'
    children = "".join(rich(n, depth + 1) for n in node.get("content", []))
    tag = {
        "paragraph": "p",
        "heading": "h3",
        "blockquote": "blockquote",
        "bulletList": "ul",
        "orderedList": "ol",
        "listItem": "li",
        "table": "table",
        "tableRow": "tr",
        "tableCell": "td",
        "tableHeader": "th",
    }.get(kind)
    attrs = node.get("attrs", {})
    if kind == "doc":
        return children
    if tag is None:
        raise AIError("unsupported_document", "Cấu trúc chưa xuất được: " + str(kind))
    if kind == "heading":
        level = attrs.get("level", 2)
        if type(level) is not int or not 1 <= level <= 3:
            raise AIError("invalid_document", "Cấp tiêu đề chưa hợp lệ.")
        tag = "h" + str(level)
    style = (
        (' style="text-align:' + attrs["textAlign"] + '"')
        if attrs.get("textAlign") in {"left", "center", "right", "justify"}
        else ""
    )
    spans = ""
    if kind == "orderedList":
        start = attrs.get("start", 1)
        if type(start) is not int or not 1 <= start <= 10000:
            raise AIError("invalid_document", "Số bắt đầu danh sách chưa hợp lệ.")
        spans += f' start="{start}"'
    if kind in {"tableCell", "tableHeader"}:
        for key in ("colspan", "rowspan"):
            value = attrs.get(key, 1)
            if type(value) is not int or not 1 <= value <= 200:
                raise AIError("invalid_table", "Ô gộp chưa hợp lệ.")
            spans += f' {key}="{value}"'
    return f"<{tag}{style}{spans}>{children}</{tag}>" if tag else children


def field(text, document=None, runs=None):
    return rich(field_document(text, document, runs))


def exam_html(
    exam,
    teacher,
    origin,
    figures=None,
    *,
    rendered_math=None,
    is_draft: bool = False,
    draft_warnings: list[dict[str, Any]] | None = None,
):
    figures = list(figures or [])
    if (
        not isinstance(exam, dict)
        or not isinstance(exam.get("questions"), list)
        or any(not isinstance(question, dict) for question in exam["questions"])
    ):
        raise AIError("invalid_exam", "Đề xuất chưa hợp lệ.")
    normalized_warnings = normalize_draft_warnings(draft_warnings)
    show_draft_banner = bool(teacher) and (bool(is_draft) or bool(normalized_warnings))
    banner_html = ""
    if show_draft_banner:
        if normalized_warnings:
            items_html_parts: list[str] = []
            for w in normalized_warnings:
                raw_code = str(w.get("code") or "").strip()
                w_attr = (
                    f' data-warning-code="{html.escape(raw_code, quote=True)}"' if raw_code else ""
                )
                items_html_parts.append(f"<li{w_attr}>{plain(format_draft_warning(w))}</li>")
            items_html = "".join(items_html_parts)
            summary_html = (
                f"<p>Phát hiện {len(normalized_warnings)} cảnh báo cần kiểm tra trước khi phát:</p>"
                f"<ul>{items_html}</ul>"
            )
        else:
            summary_html = (
                "<p>Đề thi đang ở trạng thái bản nháp; cần rà soát nội dung và đáp án "
                "trước khi phát.</p>"
            )
        banner_html = (
            '<div class="draft-banner" role="alert">'
            f'<p class="draft-banner-title">{plain(DRAFT_BANNER_TITLE)}</p>'
            f"{summary_html}</div>"
        )
    body = (
        banner_html
        + f"<h1>{inline_html(exam.get('title'))}</h1><p>{inline_html(exam.get('school'))}</p>"
        f"<p>Môn {plain(exam.get('subject'))} · Lớp {plain(exam.get('grade'))}"
        f" · {plain(exam.get('minutes'))} phút</p>"
    )
    body += f"<p>{plain(recipient_line(teacher))}</p><p>{inline_html(exam.get('instructions'))}</p>"
    presenting = not teacher and rendered_math is not None and bool(exam["questions"])
    has_table = any(uses_table(q) for q in exam["questions"])
    has_passage = bool(exam.get("quote", {}).get("text"))
    has_reference = has_passage or has_table
    if presenting:
        body = PRESENTATION_CONTROLS + "<header data-exam-intro>" + body + "</header>"
        if has_reference:
            body += '<div id="exam-reading" role="region" aria-label="Ngữ liệu và dữ kiện của đề">'
    if has_passage:
        body += (
            '<div class="passage"><b>Đọc ngữ liệu sau</b><p>'
            + inline_html(exam["quote"]["text"])
            + "</p></div>"
        )
    if has_table:
        if not figures:
            raise AIError("unsupported_export", "Thiếu bản dựng biểu đồ Bảng 1; không bỏ dữ kiện.")
        body += (
            '<section class="linked-data"><p><b>Bảng 1. Dữ kiện liên kết</b></p>'
            "<table><tr><th>Mục</th><th>Giá trị</th></tr>"
        )
        body += "".join(
            "<tr><td>" + plain(row["label"]) + "</td><td>" + plain(row["value"]) + "</td></tr>"
            for row in exam["data"]
        )
        body += (
            "</table><figure>"
            + figures.pop(0)["svg"]
            + "<figcaption>Biểu đồ dữ kiện Bảng 1</figcaption></figure></section>"
        )
    layout = exam.get("layout") or {}
    mcq_two_cols = layout.get("mcqColumns") == 2
    if presenting and has_reference:
        body += "</div>"
    passages_catalog: dict[str, dict[str, Any]] = {}
    if isinstance(exam.get("passages"), list):
        for p in exam["passages"]:
            if isinstance(p, dict) and p.get("id"):
                passages_catalog[str(p["id"])] = p

    rendered_passages: set[str] = set()
    for i, q in enumerate(exam["questions"]):
        if q.get("figure") and not figures:
            raise AIError("unsupported_export", "Chưa có bản dựng hình để xuất; không bỏ hình.")
        p_title = q.get("passageTitle")
        p_text = q.get("passageText")
        passage_id = q.get("passageId")
        if (
            passage_id
            and str(passage_id) in passages_catalog
            and str(passage_id) not in rendered_passages
        ):
            p_cat = passages_catalog[str(passage_id)]
            if not p_title:
                p_title = p_cat.get("title")
            if not p_text:
                p_text = p_cat.get("text")

        if (p_title or p_text) and (passage_id is None or str(passage_id) not in rendered_passages):
            if passage_id:
                rendered_passages.add(str(passage_id))
            body += '<div class="passage">'
            if p_title:
                body += f"<b>{inline_html(p_title)}</b>"
            if p_text:
                body += f"<p>{inline_html(p_text)}</p>"
            body += "</div>"
        score = " (" + plain(points(q["points"])) + ")" if "points" in q else ""
        page_class = ' class="page-break"' if q.get("pageBreak") else ""
        slide_attr = " data-exam-question" if presenting else ""
        body += f"<section{page_class}{slide_attr}><b>Câu {i + 1}{score}.</b> " + field(
            q.get("stem"), q.get("richDoc"), q.get("runs")
        )
        for formula in q.get("formulas", []):
            body += (
                '<div class="math" data-display="true">' + plain(formula.get("latex")) + "</div>"
            )

        def table_cell_html(val: Any) -> str:
            if isinstance(val, dict):
                if val.get("type") == "doc":
                    return rich(val)
                if "data" in val or "src" in val:
                    return _image_html(
                        val.get("data") or val.get("src"), val.get("caption", ""), in_cell=True
                    )
            return inline_html(val)

        for table in q.get("tables", []):
            body += (
                "<table>"
                + "".join(
                    "<tr>" + "".join("<td>" + table_cell_html(v) + "</td>" for v in row) + "</tr>"
                    for row in table.get("rows", [])
                )
                + "</table>"
            )
        for image in q.get("images", []):
            body += _image_html(image.get("data", ""), image.get("caption", ""))
        if q.get("figure"):
            body += (
                '<figure style="text-align:center">'
                + figures.pop(0)["svg"]
                + "<figcaption>"
                + plain(q["figure"].get("caption"))
                + "</figcaption></figure>"
            )
        if q.get("options"):
            docs = q.get("optionDocs") or []
            opt_class = (
                ' class="mcq-cols-2"'
                if mcq_two_cols and q.get("type", "mcq") == "mcq" and len(q["options"]) == 4
                else ""
            )
            body += (
                f'<ol type="A"{opt_class}>'
                + "".join(
                    "<li>" + field(o, docs[j] if j < len(docs) else None) + "</li>"
                    for j, o in enumerate(q["options"])
                )
                + "</ol>"
            )
        if teacher:
            label = saved_answer_label(q)
            body += (
                "<p><b>"
                + (
                    "Lời giải tham khảo"
                    if q.get("type") == "essay"
                    else "Đáp án " + inline_html(label)
                )
                + ".</b> "
                + field(q.get("explanation"), q.get("explanationDoc"))
                + "</p>"
            )
            for e in q.get("evidence", []):
                body += "<blockquote>" + plain(e.get("quote")) + "</blockquote>"
            if q.get("rubric"):
                body += (
                    '<p class="rubric-title"><b>Hướng dẫn chấm</b></p><ul>'
                    + "".join(
                        "<li>"
                        + field(step.get("text"), step.get("richDoc"))
                        + " · "
                        + plain(points(step.get("points")))
                        + "</li>"
                        for step in q["rubric"]
                    )
                    + "</ul>"
                )
            approval, verification = q.get("approval") or {}, q.get("check") or {}
            approved = q.get("v") is not None and (
                (approval.get("version") == q["v"] and approval.get("status") == "approved")
                or (
                    verification.get("version") == q["v"]
                    and verification.get("status") == "approved"
                )
            )
            body += (
                "<small>"
                + (
                    "Giáo viên đã duyệt bản hiện tại."
                    if approved
                    else "Chưa được giáo viên duyệt bản hiện tại."
                )
                + "</small>"
            )
            if show_draft_banner:
                for warn in match_question_warnings(q, i + 1, normalized_warnings):
                    w_code = html.escape(str(warn.get("code") or "").strip(), quote=True)
                    code_attr = f' data-warning-code="{w_code}"' if w_code else ""
                    body += (
                        f'<div class="question-draft-note"{code_attr}>'
                        f"<strong>Lưu ý rà soát:</strong> {plain(format_draft_warning(warn))}"
                        "</div>"
                    )
        body += "</section>"
    origin = html.escape(origin.rstrip("/"), quote=True)
    math_css, math_script = "", ""
    if rendered_math is None:
        math_css = f'<link rel="stylesheet" href="{origin}/assets/katex/katex.min.css">'
        math_script = (
            f'<script type="module">import katex from "{origin}/assets/katex/katex.mjs";'
            f'import "{origin}/assets/katex/contrib/mhchem.mjs";'
            'for(const n of document.querySelectorAll(".math")){'
            "katex.render(n.textContent,n,{throwOnError:false,trust:false,"
            'displayMode:n.dataset.display==="true"});}</script>'
        )
    else:

        def embed_math(match):
            latex = html.unescape(match["text"].replace("<br>", "\n"))
            mathml = rendered_math.get(latex)
            if mathml is None:
                raise AIError("export_render_failed", "Thiếu công thức đã dựng; chưa xuất tệp.")
            if match["display"] == "true":
                mathml = mathml.replace("<math ", '<math display="block" ', 1)
            return mathml

        body = re.sub(
            r'<(?P<tag>span|div) class="math"(?: data-display="(?P<display>true|false)")?>'
            r"(?P<text>.*?)</(?P=tag)>",
            embed_math,
            body,
        )
    font = (
        layout.get("font")
        if layout.get("font") in {"Times New Roman", "Arial", "Calibri"}
        else "Times New Roman"
    )
    size = min(22, max(10, float(layout.get("fontSize") or 15)))
    raw_line_height = layout.get("lineHeight")
    line_height_css = ""
    if (
        not isinstance(raw_line_height, bool)
        and isinstance(raw_line_height, (int, float))
        and math.isfinite(raw_line_height)
    ):
        lh = min(2.5, max(1.0, float(raw_line_height)))
        line_height_css = f"line-height:{lh:g};"
    watermark_html = ""
    raw_wm_img = layout.get("watermarkImage")
    if isinstance(raw_wm_img, str) and raw_wm_img.strip():
        wm_png, _, _ = watermark_image_bytes(raw_wm_img, fade_alpha=1.0)
        wm_src = "data:image/png;base64," + base64.b64encode(wm_png).decode()
        watermark_html = (
            '<div class="watermark-img" aria-hidden="true">'
            f'<img src="{html.escape(wm_src, quote=True)}" alt=""></div>'
        )
    return (
        '<!doctype html><html lang="vi"><meta charset="utf-8"><title>'
        + plain(exam.get("title"))
        + "</title>"
        + (
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            if presenting
            else ""
        )
        + math_css
        + "<style>"
        f'body{{font:{size}pt "{font}",serif;{line_height_css}'
        "max-width:760px;margin:30px auto;color:#111}"
        "h1{font-size:18pt;text-align:center}section{margin:20px 0}"
        "section>b{display:block;break-after:avoid}"
        ".mcq-cols-2{display:grid;grid-template-columns:1fr 1fr;gap:4px 18px;padding-left:20px}"
        ".watermark-img{position:fixed;inset:0;display:flex;align-items:center;"
        "justify-content:center;pointer-events:none;z-index:-1;opacity:0.12}"
        ".watermark-img img{max-width:65%;max-height:65%;object-fit:contain}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid;padding:6px}"
        "figure svg{max-width:100%;height:auto}"
        "figure{break-inside:avoid;text-align:center;margin:12px 0}"
        "figure img{display:block;margin:auto}"
        "td img{max-width:100%;max-height:180px;display:block;margin:4px auto}"
        ".cell-caption{display:block;text-align:center;margin-top:4px}"
        ".code-block{background:#f4f6f5;padding:10px 12px;border-radius:6px;"
        'font-family:Consolas,"Courier New",monospace;white-space:pre-wrap;overflow-wrap:anywhere}'
        "li>p,td>p,th>p{margin:0}tr{break-inside:avoid}"
        "blockquote,small{font-size:11pt;color:#444}@page{size:A4;margin:18mm}"
        ".page-break{break-before:page}"
        "@media print{body{margin:0}section,ol,ul{break-inside:avoid}"
        ".rubric-title{break-after:avoid}}"
        + (
            ".draft-banner{border:2px solid #b45309;background:#fffbeb;color:#78350f;"
            "padding:10px 14px;margin:12px 0;border-radius:6px}"
            ".draft-banner-title{font-weight:700;margin:0 0 6px}"
            ".draft-banner ul{margin:4px 0 0 18px;padding:0}"
            ".question-draft-note{border-left:3px solid #d97706;background:#fffbeb;"
            "color:#78350f;padding:6px 10px;margin:8px 0;font-size:11pt}"
            if show_draft_banner
            else ""
        )
        + (PRESENTATION_CSS if presenting else "")
        + "</style><body>"
        + watermark_html
        + body
        + math_script
        + (PRESENTATION_SCRIPT if presenting else "")
        + "</body></html>"
    )


def chrome_path():
    import os

    candidates = [
        os.environ.get("BROWSER_PATH"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    ]
    return next((p for p in candidates if p and Path(p).is_file()), None)


# shortcut: recognize common positional wording until the editor can mark an option as fixed.
_POSITION_DEPENDENT = re.compile(
    r"\b[A-D]\b|(?i:(?:cả|hai|ba|bốn|tất cả|mọi|một trong (?:hai|ba))\s*"
    r"(?:hai|ba|bốn|ý|đáp án|phương án|lựa chọn|câu)|"
    r"(?:tất cả|không có).{0,30}(?:trên|sau|đầu|cuối)|"
    r"phương án (?:đầu|cuối|trên|dưới|[a-d]\b)|(?:chọn|đáp án)\s*\(?[a-d]\b|"
    r"(?:câu|bài|hình|bảng)\s*(?:trước|sau|trên|dưới)|all of|none of|both)",
)
_QUESTION_REFERENCE = re.compile(r"\b(?:câu|bài)\s*(?:số\s*)?(\d+)\b", re.IGNORECASE)
_RELATIVE_BACKWARD_REF = re.compile(
    r"\b(?:câu|bài)\s*(?:trước|trên|kế\s*trước|vừa\s*rồi)\b",
    re.IGNORECASE,
)
_RELATIVE_FORWARD_REF = re.compile(
    r"\b(?:câu|bài)\s*(?:sau|dưới)\b",
    re.IGNORECASE,
)
_PLURAL_RELATIVE_BACKWARD_REF = re.compile(
    r"\b(?:các|những|tất\s+cả(?:\s+(?:các|những))?)\s+(?:câu|bài)\s*"
    r"(?:trước|trên|kế\s*trước|vừa\s*rồi)\b",
    re.IGNORECASE,
)
_PLURAL_RELATIVE_FORWARD_REF = re.compile(
    r"\b(?:các|những|tất\s+cả(?:\s+(?:các|những))?)\s+(?:câu|bài)\s*(?:sau|dưới)\b",
    re.IGNORECASE,
)
_RELATIVE_QUESTION_REF = re.compile(
    r"\b(?:câu|bài)\s*(?:trước|sau|trên|dưới|kế\s*trước|vừa\s*rồi)\b",
    re.IGNORECASE,
)
_OPTION_LABELS = ("A", "B", "C", "D")


def _extract_rich_doc_text(node: Any, depth: int = 0) -> str:
    if not isinstance(node, dict) or depth > 64:
        return ""
    kind = node.get("type")
    if kind == "text":
        text = node.get("text")
        return text if isinstance(text, str) else ""
    if kind == "hardBreak":
        return "\n"
    if kind == "mathInline":
        attrs = node.get("attrs")
        if isinstance(attrs, dict):
            latex = attrs.get("latex")
            if isinstance(latex, str) and latex:
                return f"${latex}$"
        return ""
    children = node.get("content")
    if not isinstance(children, list):
        return ""
    parts = [_extract_rich_doc_text(child, depth + 1) for child in children]
    sep = (
        " | "
        if kind == "tableRow"
        else (
            "\n"
            if kind
            in {
                "doc",
                "bulletList",
                "orderedList",
                "listItem",
                "blockquote",
                "table",
                "tableCell",
                "tableHeader",
            }
            else ""
        )
    )
    return sep.join(part for part in parts if part)


def _question_reference_texts(question: Any) -> list[str]:
    """Thu thập văn bản câu hỏi phục vụ phát hiện tham chiếu vị trí khi trộn mã đề."""
    if not isinstance(question, dict):
        return []
    texts: list[str] = []
    for key in ("stem", "answerText", "explanation", "solution"):
        val = question.get(key)
        if isinstance(val, str) and val:
            texts.append(val)
    options = question.get("options")
    if isinstance(options, list):
        for opt in options:
            if isinstance(opt, str) and opt:
                texts.append(opt)
    for doc_key in ("richDoc", "explanationDoc"):
        doc_text = _extract_rich_doc_text(question.get(doc_key))
        if doc_text:
            texts.append(doc_text)
    option_docs = question.get("optionDocs")
    if isinstance(option_docs, list):
        for doc in option_docs:
            doc_text = _extract_rich_doc_text(doc)
            if doc_text:
                texts.append(doc_text)
    rubric = question.get("rubric")
    if isinstance(rubric, list):
        for step in rubric:
            if isinstance(step, str) and step:
                texts.append(step)
            elif isinstance(step, dict):
                for rkey in ("text", "criterion", "content", "step"):
                    rval = step.get(rkey)
                    if isinstance(rval, str) and rval:
                        texts.append(rval)
                rdoc_text = _extract_rich_doc_text(step.get("richDoc"))
                if rdoc_text:
                    texts.append(rdoc_text)
    return texts


def _normalize_block_token(value):
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if type(value) is int:
        return str(value)
    if value is None:
        return None
    raise AIError("invalid_variant", "Mã nhóm ngữ liệu chưa hợp lệ.", http_status=400)


def _block_identity(question):
    if not isinstance(question, dict):
        return None
    passage_id = _normalize_block_token(question.get("passageId"))
    group_id = _normalize_block_token(question.get("groupId"))
    if passage_id is None and group_id is None:
        return None
    return (passage_id, group_id)


def _update_range_in_text(text: str, start: int, end: int) -> str:
    if not isinstance(text, str) or not text.strip():
        return text

    def _repl(m: re.Match[str]) -> str:
        prefix = m.group(1) or ""
        sep = m.group(2)
        has_second_cau = bool(m.group(3))
        is_upper = m.group(0).lstrip().startswith("C") or (
            bool(prefix.strip()) and prefix.strip()[0].isupper()
        )
        cau_word = "Câu" if is_upper and not prefix.strip() else "câu"
        if start == end:
            return f"{prefix}{cau_word} {start}"
        second_cau = (f"{cau_word} " if is_upper else "câu ") if has_second_cau else ""
        return f"{prefix}{cau_word} {start}{sep}{second_cau}{end}"

    pattern = re.compile(r"(?i)\b(từ\s+)?câu\s+\d+(\s*(?:đến|–|-)\s*)(câu\s+)?\d+\b")
    return pattern.sub(_repl, text)


def _block_display_label(block_key, title=None):
    passage_id, group_id = block_key
    if passage_id is not None and group_id is not None and str(passage_id) != str(group_id):
        base = f"Ngữ liệu {passage_id} · Nhóm {group_id}"
    elif passage_id is not None:
        base = f"Ngữ liệu {passage_id}"
    else:
        base = f"Nhóm {group_id}"
    if isinstance(title, str) and title.strip():
        return f"{base} ({title.strip()})"
    return base


def _answer_code(question):
    if not isinstance(question, dict):
        return None
    ans = saved_answer(question)
    if ans is None:
        return None
    return saved_answer_label(question)


def describe_variant_option_mapping(original_question, variant_question):
    """Tính ánh xạ phương án MCQ giữa câu gốc và câu sau hoán vị mà không sửa dữ liệu câu."""
    original_answer = _answer_code(original_question)
    variant_answer = _answer_code(variant_question)
    if (
        not isinstance(original_question, dict)
        or not isinstance(variant_question, dict)
        or original_question.get("type", "mcq") != "mcq"
        or variant_question.get("type", "mcq") != "mcq"
    ):
        return {
            "optionsShuffled": False,
            "optionMapping": {},
            "originalAnswer": original_answer,
            "variantAnswer": variant_answer,
        }
    original_options = original_question.get("options")
    variant_options = variant_question.get("options")
    if (
        not isinstance(original_options, list)
        or not isinstance(variant_options, list)
        or len(original_options) != 4
        or len(variant_options) != 4
        or any(not isinstance(opt, str) or not opt.strip() for opt in original_options)
        or any(not isinstance(opt, str) or not opt.strip() for opt in variant_options)
        or len(set(original_options)) != 4
        or set(original_options) != set(variant_options)
    ):
        return {
            "optionsShuffled": False,
            "optionMapping": {},
            "originalAnswer": original_answer,
            "variantAnswer": variant_answer,
        }
    option_mapping = {
        _OPTION_LABELS[old_idx]: _OPTION_LABELS[variant_options.index(opt)]
        for old_idx, opt in enumerate(original_options)
    }
    return {
        "optionsShuffled": original_options != variant_options,
        "optionMapping": option_mapping,
        "originalAnswer": original_answer,
        "variantAnswer": variant_answer,
    }


def _summarize_passage_groups(original_questions, variant_questions):
    original_order = []
    original_numbers_by_key = {}
    titles_by_key = {}
    for idx, q in enumerate(original_questions, 1):
        key = _block_identity(q)
        if key is None:
            continue
        if key not in original_numbers_by_key:
            original_order.append(key)
            original_numbers_by_key[key] = []
        original_numbers_by_key[key].append(idx)
        title = q.get("passageTitle")
        if key not in titles_by_key and isinstance(title, str) and title.strip():
            titles_by_key[key] = title.strip()

    variant_numbers_by_key = {}
    for idx, q in enumerate(variant_questions, 1):
        key = _block_identity(q)
        if key is not None:
            variant_numbers_by_key.setdefault(key, []).append(idx)

    groups = []
    for key in original_order:
        v_nums = variant_numbers_by_key.get(key, [])
        contiguous = bool(v_nums) and v_nums == list(range(v_nums[0], v_nums[-1] + 1))
        groups.append(
            {
                "passageId": key[0],
                "groupId": key[1],
                "label": _block_display_label(key, titles_by_key.get(key)),
                "originalNumbers": original_numbers_by_key[key],
                "questionNumbers": v_nums,
                "contiguous": contiguous,
            }
        )
    return groups


def _validate_relative_question_refs(
    questions: list[dict[str, Any]],
    plan: dict[str, Any],
) -> None:
    mode = plan["mode"]
    positions = plan["positions"]
    units = plan["units"]
    unit_of: dict[int, int] = {}
    if mode in ("standalone", "intra_block"):
        unlocked = [i for i in positions if questions[i].get("lockPosition") is not True]
        moving = set(unlocked) if len(unlocked) >= 2 else set()
    else:
        locked_flags = [
            any(questions[idx].get("lockPosition") is True for idx in unit) for unit in units
        ]
        unlocked_units = [
            unit for unit, is_locked in zip(units, locked_flags, strict=True) if not is_locked
        ]
        if any(locked_flags) and len({len(u) for u in unlocked_units}) != 1:
            moving = set()
        elif len(unlocked_units) >= 2:
            moving = {idx for unit in unlocked_units for idx in unit}
        else:
            moving = set()
        for unit_idx, unit in enumerate(units):
            for idx in unit:
                unit_of[idx] = unit_idx

    if not moving:
        return

    def _pair_broken(a: int, b: int) -> bool:
        if a not in moving and b not in moving:
            return False
        if a in moving and b in moving:
            return not (mode == "multi_block" and a in unit_of and unit_of.get(a) == unit_of.get(b))
        return True

    for idx in range(len(questions)):
        texts = _question_reference_texts(questions[idx])
        if not texts:
            continue
        has_plural_backward = any(_PLURAL_RELATIVE_BACKWARD_REF.search(text) for text in texts)
        has_plural_forward = any(_PLURAL_RELATIVE_FORWARD_REF.search(text) for text in texts)
        has_backward = any(_RELATIVE_BACKWARD_REF.search(text) for text in texts)
        has_forward = any(_RELATIVE_FORWARD_REF.search(text) for text in texts)
        if not (has_plural_backward or has_plural_forward or has_backward or has_forward):
            continue

        broken = False
        if has_plural_backward and (any(m < idx for m in moving) or idx in moving):
            broken = True
        if has_plural_forward and (any(m > idx for m in moving) or idx in moving):
            broken = True
        if has_backward and (
            (idx == 0 and idx in moving) or (idx > 0 and _pair_broken(idx - 1, idx))
        ):
            broken = True
        if has_forward and (
            (idx == len(questions) - 1 and idx in moving)
            or (idx + 1 < len(questions) and _pair_broken(idx, idx + 1))
        ):
            broken = True

        if broken:
            raise AIError(
                "invalid_variant",
                f"Câu {idx + 1} có tham chiếu tương đối tới câu liền kề trước/sau trong vùng trộn. "
                "Hãy giữ cố định hoặc bỏ chọn câu liên quan.",
                http_status=400,
            )


def _plan_variant_units(questions, ids):
    selected = set(ids)
    positions = [i for i, q in enumerate(questions) if q.get("id") in selected]
    if len(positions) != len(ids) or {questions[i]["id"] for i in positions} != selected:
        raise AIError(
            "invalid_variant",
            "Danh sách câu đã thay đổi. Chọn lại câu cần trộn.",
            http_status=400,
        )
    selected_numbers = {str(i + 1) for i in positions}
    if any(
        selected_numbers.intersection(_QUESTION_REFERENCE.findall(text))
        for question in questions
        for text in _question_reference_texts(question)
    ):
        raise AIError(
            "invalid_variant",
            "Có câu được nhắc theo số hoặc vị trí trước/sau trong đề. Hãy bỏ chọn câu đó.",
            http_status=400,
        )
    first = questions[positions[0]]
    span_indices = list(range(positions[0], positions[-1] + 1))
    if any(
        questions[i].get("type", "mcq") != first.get("type", "mcq")
        or uses_table(questions[i]) != uses_table(first)
        or questions[i].get("sectionId") != first.get("sectionId")
        for i in span_indices
    ):
        raise AIError(
            "invalid_variant",
            "Chọn câu trong cùng phần, cùng dạng và cùng ngữ liệu bảng.",
            http_status=400,
        )
    span_keys = [_block_identity(questions[i]) for i in span_indices]
    unique_span_keys = set(span_keys)
    if len(unique_span_keys) == 1:
        single_key = next(iter(unique_span_keys))
        plan = {
            "mode": "intra_block" if single_key is not None else "standalone",
            "positions": positions,
            "units": [[i] for i in positions],
            "block_key": single_key,
            "contiguous_span": positions == span_indices,
        }
        _validate_relative_question_refs(questions, plan)
        return plan

    # Khi chọn qua nhiều khối: mỗi khối ngữ liệu/nhóm phải đầy đủ 100% và đứng liên tiếp.
    pos_set = set(positions)
    if any(i not in pos_set and _block_identity(questions[i]) is not None for i in span_indices):
        raise AIError(
            "invalid_variant",
            "Chọn câu trong cùng phần, cùng dạng và cùng ngữ liệu bảng.",
            http_status=400,
        )
    all_key_positions = {}
    for idx, question in enumerate(questions):
        key = _block_identity(question)
        if key is not None:
            all_key_positions.setdefault(key, []).append(idx)

    selected_keys = {_block_identity(questions[i]) for i in positions}
    for key in selected_keys:
        if key is None:
            continue
        full_indices = all_key_positions[key]
        if full_indices != list(range(full_indices[0], full_indices[-1] + 1)):
            raise AIError(
                "invalid_variant",
                "Nhóm ngữ liệu trong đề không liên tiếp; không thể hoán vị nguyên khối.",
                http_status=400,
            )
        if not set(full_indices).issubset(pos_set):
            raise AIError(
                "invalid_variant",
                "Không thể chọn một phần dở dang của nhóm ngữ liệu để trộn với câu ngoài nhóm.",
                http_status=400,
            )

    has_standalone = None in selected_keys
    has_bare_group = any(
        key is not None and key[0] is None and key[1] is not None for key in selected_keys
    )
    if has_standalone and has_bare_group:
        raise AIError(
            "invalid_variant",
            "Chọn câu trong cùng phần, cùng dạng và cùng ngữ liệu bảng.",
            http_status=400,
        )

    units = []
    idx = 0
    while idx < len(positions):
        pos = positions[idx]
        key = _block_identity(questions[pos])
        if key is None:
            units.append([pos])
            idx += 1
        else:
            full_indices = all_key_positions[key]
            units.append(list(full_indices))
            idx += len(full_indices)

    if len(units) < 2:
        raise AIError(
            "invalid_variant",
            "Chọn ít nhất hai câu hoặc hai khối ngữ liệu độc lập để tạo mã đề.",
            http_status=400,
        )
    contiguous_span = positions == span_indices
    if not contiguous_span and len({len(unit) for unit in units}) != 1:
        raise AIError(
            "invalid_variant",
            "Chọn các khối ngữ liệu liền nhau khi kích thước các khối khác nhau.",
            http_status=400,
        )
    plan = {
        "mode": "multi_block",
        "positions": positions,
        "units": units,
        "block_key": None,
        "contiguous_span": contiguous_span,
    }
    _validate_relative_question_refs(questions, plan)
    return plan


def shuffle_variant_question(question, offset):
    options = question.get("options")
    docs = question.get("optionDocs")
    if (
        question.get("type", "mcq") != "mcq"
        or not isinstance(options, list)
        or len(options) != 4
        or any(not isinstance(option, str) or not option.strip() for option in options)
        or len(set(options)) != 4
        or (docs is not None and (not isinstance(docs, list) or len(docs) > 4))
    ):
        return question
    texts = [question.get("stem"), question.get("explanation"), *options]
    if any(_POSITION_DEPENDENT.search(text) for text in texts if isinstance(text, str)):
        return question
    order = [(i + offset % 3 + 1) % 4 for i in range(4)]
    answer = saved_answer(question)
    result = {**question, "options": [options[i] for i in order]}
    if docs is not None:
        result["optionDocs"] = [docs[i] if i < len(docs) else None for i in order]
    if type(answer) is int:
        result["answer"] = order.index(answer)
    return result


def exam_variant(exam, variant):
    questions = exam["questions"]
    if (
        isinstance(variant, dict)
        and isinstance(variant.get("sections"), list)
        and variant["sections"]
    ):
        offset = variant.get("offset")
        if type(offset) is not int or offset < 0:
            raise AIError(
                "invalid_variant", "Chọn ít nhất hai câu và một mã đề hợp lệ.", http_status=400
            )
        seen_ids: set[str] = set()
        current_exam = {**exam, "questions": list(questions)}
        for sec in variant["sections"]:
            sec_ids = sec.get("questionIds") if isinstance(sec, dict) else None
            if (
                not isinstance(sec_ids, list)
                or len(sec_ids) < 2
                or any(i in seen_ids for i in sec_ids)
            ):
                raise AIError(
                    "invalid_variant",
                    "Mỗi phần trộn phải có ít nhất hai câu và không trùng câu giữa các phần.",
                    http_status=400,
                )
            seen_ids.update(sec_ids)
            current_exam = exam_variant(
                current_exam,
                {
                    "questionIds": sec_ids,
                    "shuffleOptions": bool(sec.get("shuffleOptions", False)),
                    "offset": offset % len(sec_ids),
                },
            )
        code = str(101 + offset)
        return {**current_exam, "title": f"{exam.get('title') or 'Đề thi'} · Mã đề {code}"}
    ids = variant.get("questionIds") if isinstance(variant, dict) else None
    offset = variant.get("offset") if isinstance(variant, dict) else None
    shuffle = variant.get("shuffleOptions", False) if isinstance(variant, dict) else False
    if (
        not isinstance(ids, list)
        or not 2 <= len(ids) <= 300
        or any(not isinstance(value, str) or not value for value in ids)
        or len(set(ids)) != len(ids)
        or type(offset) is not int
        or offset < 0
        or type(shuffle) is not bool
        or any(not isinstance(q, dict) for q in questions)
    ):
        raise AIError(
            "invalid_variant", "Chọn ít nhất hai câu và một mã đề hợp lệ.", http_status=400
        )
    plan = _plan_variant_units(questions, ids)
    units = plan["units"]
    if not 0 <= offset < min(6, len(units)):
        raise AIError(
            "invalid_variant", "Chọn ít nhất hai câu và một mã đề hợp lệ.", http_status=400
        )

    reordered = questions.copy()
    mode = plan["mode"]
    positions = plan["positions"]
    if mode in ("standalone", "intra_block"):
        locked_positions = [i for i in positions if questions[i].get("lockPosition") is True]
        unlocked_positions = [i for i in positions if questions[i].get("lockPosition") is not True]
        for pos in locked_positions:
            question = questions[pos]
            candidate = shuffle_variant_question(question, offset) if shuffle else question
            reordered[pos] = {
                **candidate,
                "pageBreak": questions[pos].get("pageBreak", False),
            }
        if unlocked_positions:
            group = [questions[i] for i in unlocked_positions]
            shift = offset % len(group) if len(group) >= 2 else 0
            rotated_group = group[shift:] + group[:shift]
            for index, question in zip(unlocked_positions, rotated_group, strict=True):
                candidate = shuffle_variant_question(question, offset) if shuffle else question
                reordered[index] = {
                    **candidate,
                    "pageBreak": questions[index].get("pageBreak", False),
                }
        if mode == "intra_block":
            block_key = plan["block_key"]
            block_indices = [i for i, q in enumerate(questions) if _block_identity(q) == block_key]
            head_idx = block_indices[0]
            if head_idx in set(positions):
                orig_head = questions[head_idx]
                orig_head_id = orig_head.get("id")
                moved_idx = next(
                    (idx for idx in positions if reordered[idx].get("id") == orig_head_id),
                    head_idx,
                )
                if moved_idx != head_idx:
                    for header_field in ("passageTitle", "passageText"):
                        header_value = orig_head.get(header_field)
                        if not (isinstance(header_value, str) and header_value.strip()):
                            continue
                        all_have_field = all(
                            isinstance(questions[i].get(header_field), str)
                            and bool(questions[i][header_field].strip())
                            for i in block_indices
                        )
                        if not all_have_field:
                            if not (
                                isinstance(reordered[head_idx].get(header_field), str)
                                and reordered[head_idx][header_field].strip()
                            ):
                                reordered[head_idx] = {
                                    **reordered[head_idx],
                                    header_field: header_value,
                                }
                            moved_copy = dict(reordered[moved_idx])
                            moved_copy.pop(header_field, None)
                            reordered[moved_idx] = moved_copy
    else:
        locked_flags = [
            any(questions[idx].get("lockPosition") is True for idx in unit) for unit in units
        ]
        if any(locked_flags):
            unlocked_slot_units = [
                unit for unit, is_locked in zip(units, locked_flags, strict=True) if not is_locked
            ]
            for unit, is_locked in zip(units, locked_flags, strict=True):
                if not is_locked:
                    continue
                for idx in unit:
                    question = questions[idx]
                    candidate = shuffle_variant_question(question, offset) if shuffle else question
                    reordered[idx] = {
                        **candidate,
                        "pageBreak": questions[idx].get("pageBreak", False),
                    }
            if unlocked_slot_units:
                shift = offset % len(unlocked_slot_units) if len(unlocked_slot_units) >= 2 else 0
                rotated_unlocked = unlocked_slot_units[shift:] + unlocked_slot_units[:shift]
                same_sizes = len({len(u) for u in unlocked_slot_units}) == 1
                if same_sizes:
                    for dest_unit, src_unit in zip(
                        unlocked_slot_units, rotated_unlocked, strict=True
                    ):
                        orig_start_break = questions[dest_unit[0]].get("pageBreak", False)
                        for local_idx, (dest_idx, src_idx) in enumerate(
                            zip(dest_unit, src_unit, strict=True)
                        ):
                            question = questions[src_idx]
                            candidate = (
                                shuffle_variant_question(question, offset) if shuffle else question
                            )
                            page_break = (
                                orig_start_break
                                if local_idx == 0
                                else candidate.get("pageBreak", False)
                            )
                            reordered[dest_idx] = {**candidate, "pageBreak": page_break}
                else:
                    # Khối tự do có kích thước khác nhau quanh khối khóa: giữ nguyên vị trí mỗi khối
                    for unit in unlocked_slot_units:
                        for idx in unit:
                            question = questions[idx]
                            candidate = (
                                shuffle_variant_question(question, offset) if shuffle else question
                            )
                            reordered[idx] = {
                                **candidate,
                                "pageBreak": questions[idx].get("pageBreak", False),
                            }
        else:
            rotated_units = units[offset:] + units[:offset]
            if plan["contiguous_span"]:
                cursor = positions[0]
                for unit_pos, src_unit in enumerate(rotated_units):
                    orig_start_break = questions[units[unit_pos][0]].get("pageBreak", False)
                    for local_idx, src_idx in enumerate(src_unit):
                        question = questions[src_idx]
                        candidate = (
                            shuffle_variant_question(question, offset) if shuffle else question
                        )
                        page_break = (
                            orig_start_break
                            if local_idx == 0
                            else candidate.get("pageBreak", False)
                        )
                        reordered[cursor] = {**candidate, "pageBreak": page_break}
                        cursor += 1
            else:
                for dest_unit, src_unit in zip(units, rotated_units, strict=True):
                    orig_start_break = questions[dest_unit[0]].get("pageBreak", False)
                    for local_idx, (dest_idx, src_idx) in enumerate(
                        zip(dest_unit, src_unit, strict=True)
                    ):
                        question = questions[src_idx]
                        candidate = (
                            shuffle_variant_question(question, offset) if shuffle else question
                        )
                        page_break = (
                            orig_start_break
                            if local_idx == 0
                            else candidate.get("pageBreak", False)
                        )
                        reordered[dest_idx] = {**candidate, "pageBreak": page_break}

    block_map: dict[tuple[Any, Any], list[int]] = {}
    for idx, q in enumerate(reordered):
        key = _block_identity(q)
        if key is not None:
            block_map.setdefault(key, []).append(idx)

    for _key, indices in block_map.items():
        if not indices:
            continue
        first_idx = indices[0]
        start_num = first_idx + 1
        end_num = indices[-1] + 1
        q_first = reordered[first_idx]
        updates = {}
        for header_field in ("passageTitle", "passageText", "passageLead", "lead", "groupLead"):
            val = q_first.get(header_field)
            if isinstance(val, str) and val.strip():
                new_val = _update_range_in_text(val, start_num, end_num)
                if new_val != val:
                    updates[header_field] = new_val
        if updates:
            reordered[first_idx] = {**q_first, **updates}

    code = str(101 + offset)
    res_exam = {
        **exam,
        "title": f"{exam.get('title') or 'Đề thi'} · Mã đề {code}",
        "questions": reordered,
    }
    if isinstance(exam.get("passages"), list):
        updated_passages = []
        for p in exam["passages"]:
            p_copy = dict(p)
            pid = p_copy.get("id")
            if pid is not None:
                p_indices = [
                    idx for idx, q in enumerate(reordered) if str(q.get("passageId")) == str(pid)
                ]
                if p_indices:
                    p_start = p_indices[0] + 1
                    p_end = p_indices[-1] + 1
                    for k in ("title", "text", "lead", "description"):
                        if isinstance(p_copy.get(k), str):
                            p_copy[k] = _update_range_in_text(p_copy[k], p_start, p_end)
            updated_passages.append(p_copy)
        res_exam["passages"] = updated_passages
    return res_exam


def preview_exam_variant(payload):
    exam = payload.get("exam")
    if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
        raise AIError("invalid_exam", "Đề cần danh sách câu để xem trước.")
    variant = exam_variant(exam, payload.get("variant"))
    original_by_id = {
        q["id"]: (i + 1, q) for i, q in enumerate(exam["questions"]) if isinstance(q.get("id"), str)
    }
    questions_out = []
    question_mappings = []
    for i, q in enumerate(variant["questions"]):
        qid = q.get("id")
        if isinstance(qid, str) and qid in original_by_id:
            orig_num, orig_q = original_by_id[qid]
        else:
            orig_num, orig_q = i + 1, exam["questions"][i]
        mapping = describe_variant_option_mapping(orig_q, q)
        q_item = {
            "originalNumber": orig_num,
            "stem": q.get("stem", ""),
            "options": q.get("options", []),
        }
        for field in ("passageTitle", "passageText", "passageId", "groupId"):
            if field in q:
                q_item[field] = q[field]
        questions_out.append(q_item)
        question_mappings.append(
            {
                "questionNumber": i + 1,
                "originalNumber": orig_num,
                "locked": bool(q.get("lockPosition") is True),
                "passageId": q.get("passageId"),
                "groupId": q.get("groupId"),
                "optionsShuffled": mapping["optionsShuffled"],
                "optionMapping": mapping["optionMapping"],
                "originalAnswer": mapping["originalAnswer"],
                "variantAnswer": mapping["variantAnswer"],
            }
        )
    return {
        "title": variant["title"],
        "questions": questions_out,
        "questionMappings": question_mappings,
        "passageGroups": _summarize_passage_groups(exam["questions"], variant["questions"]),
    }


def _ascii_slug(value: Any, *, max_len: int = 24) -> str:
    nfd = unicodedata.normalize("NFD", str(value or ""))
    no_marks = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    ascii_text = no_marks.replace("đ", "d").replace("Đ", "D")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    return cleaned[:max_len].strip("_")


def build_export_filename(
    exam: dict[str, Any] | None,
    *,
    teacher: bool = False,
    class_label: str = "",
    ext: str = "html",
    suffix_tag: str = "",
) -> str:
    """Tạo tên tệp xuất an toàn, có nghĩa, luôn bắt đầu bằng `De_thi_`."""
    hex8 = uuid4().hex[:8]
    if not isinstance(exam, dict):
        tag = _ascii_slug(suffix_tag, max_len=24) or "Sao_luu"
        return f"De_thi_{tag}_{hex8}.{ext}"
    subj = _ascii_slug(exam.get("subject"), max_len=24)
    grade = _ascii_slug(exam.get("grade"), max_len=12)
    subj_grade = "_".join(part for part in (subj, grade) if part) or "Chung"
    class_slug = _ascii_slug(class_label, max_len=20)
    rev = exam.get("revision")
    rev_part = f"v{rev}" if type(rev) is int and rev >= 1 else ""
    aud_part = suffix_tag or ("GV" if teacher else "HS")
    parts = ["De_thi", subj_grade]
    if class_slug:
        parts.append(class_slug)
    if rev_part:
        parts.append(rev_part)
    parts.append(aud_part)
    stem = "_".join(parts)[:118].strip("_")
    return f"{stem}_{hex8}.{ext}"


def export_variant_pack(payload, directory, origin):
    exam = payload.get("exam")
    ids = payload.get("questionIds")
    format_ = payload.get("format", "docx")
    if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
        raise AIError("invalid_exam", "Đề cần danh sách câu để xuất.")
    if format_ not in ("docx", "pdf", "html"):
        raise AIError("unsupported_export", "Chọn Word, PDF hoặc HTML để xuất bộ mã.")
    shuffle_options = payload.get("shuffleOptions", False)
    settings = {"questionIds": ids, "shuffleOptions": shuffle_options}
    first = exam_variant(exam, {**settings, "offset": 0})
    plan = _plan_variant_units(exam["questions"], ids)
    variant_count = min(6, len(plan["units"]))
    variants = [
        first,
        *[exam_variant(exam, {**settings, "offset": offset}) for offset in range(1, variant_count)],
    ]
    headings = "".join(f"<th scope='col'>Mã {101 + i}</th>" for i in range(len(variants)))
    original_by_id = {
        question["id"]: (i + 1, question)
        for i, question in enumerate(exam["questions"])
        if isinstance(question.get("id"), str)
    }
    block_titles = {}
    for q in exam["questions"]:
        key = _block_identity(q)
        title = q.get("passageTitle")
        if key is not None and key not in block_titles and isinstance(title, str) and title.strip():
            block_titles[key] = title.strip()
    has_passages = any(_block_identity(q) is not None for q in exam["questions"])
    rows = []
    for i in range(len(exam["questions"])):
        answers = []
        for variant in variants:
            question = variant["questions"][i]
            qid = question.get("id")
            if isinstance(qid, str) and qid in original_by_id:
                source, orig_q = original_by_id[qid]
            else:
                source, orig_q = i + 1, exam["questions"][i]
            answer = (
                "Xem hướng dẫn chấm"
                if question.get("type") == "essay"
                else saved_answer_label(question)
            )
            cell = f"{html.escape(answer)} <small>(gốc: {source})</small>"
            if shuffle_options:
                mapping = describe_variant_option_mapping(orig_q, question)
                if mapping["optionsShuffled"]:
                    pairs = ", ".join(
                        f"{old}→{new}" for old, new in mapping["optionMapping"].items()
                    )
                    if mapping["originalAnswer"] and mapping["variantAnswer"]:
                        map_text = (
                            f"PA gốc {mapping['originalAnswer']} → "
                            f"{mapping['variantAnswer']} ({pairs})"
                        )
                    else:
                        map_text = f"PA gốc {pairs}"
                    cell += f'<br><small class="option-mapping">{html.escape(map_text)}</small>'
            block_key = _block_identity(question)
            if block_key is not None:
                block_label = _block_display_label(block_key, block_titles.get(block_key))
                cell += f'<br><small class="passage-tag">{html.escape(block_label)}</small>'
            answers.append(f"<td>{cell}</td>")
        rows.append(f"<tr><th scope='row'>{i + 1}</th>{''.join(answers)}</tr>")

    passage_summary_html = ""
    if has_passages:
        summaries_per_variant = [
            _summarize_passage_groups(exam["questions"], variant["questions"])
            for variant in variants
        ]
        summary_items = []
        for group_idx, base_group in enumerate(summaries_per_variant[0]):
            parts = []
            all_contiguous = True
            for v_idx, groups in enumerate(summaries_per_variant):
                item = groups[group_idx]
                nums = item["questionNumbers"]
                span_label = (
                    f"Câu {nums[0]}–{nums[-1]}"
                    if len(nums) > 1
                    else (f"Câu {nums[0]}" if nums else "—")
                )
                status = "liên tục" if item["contiguous"] else "bị tách"
                if not item["contiguous"]:
                    all_contiguous = False
                parts.append(f"Mã {101 + v_idx}: {span_label} ({status})")
            verdict = (
                "Giữ nguyên liên tục qua tất cả các mã đề."
                if all_contiguous
                else "Cần kiểm tra thứ tự khối ngữ liệu."
            )
            summary_items.append(
                f"<li><strong>{html.escape(base_group['label'])}</strong>: "
                f"{html.escape(' · '.join(parts))} — {html.escape(verdict)}</li>"
            )
        passage_summary_html = (
            '<section class="passage-summary">'
            "<h2>Tóm tắt bảo toàn khối ngữ liệu</h2>"
            f"<ul>{''.join(summary_items)}</ul>"
            "</section>"
        )

    title = html.escape(str(exam.get("title") or "Đề thi"))
    answer_key = (
        '<!doctype html><html lang="vi"><meta charset="utf-8">'
        "<title>Đối chiếu đáp án · Bản giáo viên</title>"
        "<style>@page{size:A4;margin:18mm}body{font:16px system-ui}"
        "table{border-collapse:collapse}th,td{border:1px solid;padding:8px}"
        ".option-mapping,.passage-tag{color:#444;display:inline-block}</style>"
        f"<h1>Đối chiếu đáp án · Bản giáo viên</h1><p>{title}</p>"
        "<p>Số trong ngoặc chỉ câu tương ứng trên đề gốc; dùng số này để tra hướng dẫn chấm.</p>"
        f'<table><thead><tr><th scope="col">Câu</th>{headings}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>{passage_summary_html}</html>"
    )
    directory.mkdir(parents=True, exist_ok=True)
    class_label = str(payload.get("classLabel") or payload.get("class_label") or "")
    name = build_export_filename(
        exam,
        teacher=True,
        class_label=class_label,
        ext="zip",
        suffix_tag="BoMa",
    )
    target = directory / name
    with tempfile.TemporaryDirectory(prefix="ma-de-", dir=directory) as temp:
        staging = Path(temp)
        bundle = staging / name
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for i, variant in enumerate(variants):
                result = export_file(
                    {"type": "exam", "exam": variant, "format": format_}, staging, origin
                )
                archive.write(staging / result["filename"], f"HOC_SINH/Ma_{101 + i}.{format_}")
            archive.writestr("GIAO_VIEN/Doi_chieu_dap_an.html", answer_key)
        bundle.replace(target)
    return {"filename": name, "bytes": target.stat().st_size, "url": "/api/exports/" + name}


_DRAFT_PREFLIGHT_CODES = frozenset(
    {
        "linked_data_explanation_stale",
        "linked_data_mismatch",
        "stale_quote_evidence",
    }
)


def _collect_uc8_uc9_draft_warnings(exam: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        report = audit_export_preflight(exam)
    except AIError:
        return []
    return [
        dict(item)
        for item in (*report.get("blockingIssues", []), *report.get("warnings", []))
        if isinstance(item, dict) and item.get("code") in _DRAFT_PREFLIGHT_CODES
    ]


def export_file(payload, directory, origin):
    kind = payload.get("type")
    format_ = payload.get("format", "html")
    is_teacher = payload.get("teacher") is True
    is_draft = False
    draft_warnings: list[dict[str, Any]] | None = None
    if kind == "variant-pack":
        return export_variant_pack(payload, directory, origin)
    if kind == "exam":
        if format_ not in {"html", "pdf", "docx"}:
            raise AIError("unsupported_export", "Chọn Word, PDF hoặc HTML để xuất đề.")
        exam = payload.get("exam")
        if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
            raise AIError("invalid_exam", "Đề cần danh sách câu để xuất.")
        if "variant" in payload:
            exam = exam_variant(exam, payload["variant"])
        raw_is_draft = payload.get("isDraft") if "isDraft" in payload else payload.get("is_draft")
        is_draft = (
            bool(raw_is_draft)
            if raw_is_draft is not None
            else bool(exam.get("isDraft") is True or exam.get("saved") is False)
        )
        raw_warnings = (
            payload.get("draftWarnings")
            if "draftWarnings" in payload
            else payload.get("draft_warnings")
        )
        if raw_warnings is None and isinstance(exam.get("draftWarnings"), list):
            raw_warnings = exam.get("draftWarnings")
        if raw_warnings is not None:
            draft_warnings = normalize_draft_warnings(raw_warnings)
        elif is_teacher:
            draft_warnings = _collect_uc8_uc9_draft_warnings(exam)
        rendered = {"figures": [], "math": {}}
        if format_ != "docx":
            formulas, figures = export_inputs(exam, is_teacher)
            rendered = render_assets(formulas, figures, chrome_path())
        content = (
            exam_html(
                exam,
                is_teacher,
                Path(__file__).resolve().parents[3].as_uri() if format_ == "pdf" else origin,
                rendered["figures"],
                rendered_math=rendered["math"] if format_ == "html" else None,
                is_draft=is_draft,
                draft_warnings=draft_warnings,
            )
            if format_ != "docx"
            else ""
        )
    elif kind in {"backup", "json"}:
        format_, content = (
            "json",
            json.dumps(
                payload.get("backup", payload.get("state", payload.get("data"))),
                ensure_ascii=False,
                indent=2,
            ),
        )
    else:
        raise AIError("unsupported_export", "Chọn xuất đề hoặc sao lưu JSON.")
    directory.mkdir(parents=True, exist_ok=True)
    class_label = str(payload.get("classLabel") or payload.get("class_label") or "")
    name = build_export_filename(
        exam if kind == "exam" else None,
        teacher=payload.get("teacher") is True,
        class_label=class_label,
        ext=format_,
        suffix_tag="Sao_luu" if kind in {"backup", "json"} else "",
    )
    target = directory / name
    if format_ == "html" or format_ == "json":
        target.write_text(content, encoding="utf-8")
    elif format_ == "pdf":
        chrome = chrome_path()
        if not chrome:
            raise AIError(
                "pdf_unavailable", "Cần Chrome/Edge để xuất PDF. Có thể mở bản HTML và chọn In."
            )
        with tempfile.TemporaryDirectory(prefix="exam-pdf-") as temp:
            source = target.with_suffix(".html")
            source.write_text(content, encoding="utf-8")
            base_args = [
                chrome,
                "--headless",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--host-resolver-rules=MAP * ~NOTFOUND",
                "--no-proxy-server",
                "--no-pdf-header-footer",
                "--user-data-dir=" + str(Path(temp) / "profile"),
                "--print-to-pdf=" + str(target.resolve()),
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
                raise AIError(
                    "export_failed", "Chưa tạo được PDF. Hãy thử lại hoặc xuất HTML."
                ) from None
            finally:
                source.unlink(missing_ok=True)
        if not target.is_file() or not target.read_bytes().startswith(b"%PDF-"):
            raise AIError("export_failed", "Chưa tạo được PDF. Bản đề được giữ nguyên.")
    elif format_ == "docx":
        target.write_bytes(
            export_docx(
                exam,
                is_teacher,
                chrome_path(),
                is_draft=is_draft,
                draft_warnings=draft_warnings,
            )
        )
    else:
        raise AIError("unsupported_export", "Định dạng xuất chưa được hỗ trợ.")
    return {"filename": name, "bytes": target.stat().st_size, "url": "/api/exports/" + name}
