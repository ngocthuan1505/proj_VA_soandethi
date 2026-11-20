"""Nhập nguồn văn bản và xuất bản đề local, không gọi dịch vụ bên ngoài."""

import base64
import binascii
import html
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import TypedDict
from uuid import uuid4
from xml.etree import ElementTree as ET

from pypdf import PdfReader, apply_configuration
from pypdf.errors import PyPdfError

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer, saved_answer_label
from mach_backend.export_assets import render_assets
from mach_backend.matrix_import import validate_raster
from mach_backend.presentation import PRESENTATION_CONTROLS, PRESENTATION_CSS, PRESENTATION_SCRIPT
from mach_backend.word_export import (
    export_docx,
    export_inputs,
    field_document,
    image_bytes,
    math_parts,
    recipient_line,
    uses_table,
)
from mach_backend.word_math_read import paragraph_text

MAX_DOCUMENT = 15 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


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


def extract_text(name, data_url):
    if not isinstance(name, str) or not isinstance(data_url, str):
        raise AIError("invalid_document", "Tệp nguồn chưa hợp lệ.")
    if len(data_url) > MAX_DOCUMENT * 4 // 3 + 200:
        raise AIError("invalid_document", "Tệp nguồn vượt15MB.")
    try:
        header, encoded = data_url.split(",", 1)
        if not header.startswith("data:") or not header.endswith(";base64"):
            raise ValueError
        data = base64.b64decode(encoded, validate=True)
        if len(data) > MAX_DOCUMENT:
            raise ValueError
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
        elif ext in {".docx", ".pptx"}:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = [
                    n
                    for n in archive.namelist()
                    if (ext == ".docx" and n == "word/document.xml")
                    or (ext == ".pptx" and re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
                ]
                if not members or sum(archive.getinfo(n).file_size for n in members) > MAX_DOCUMENT:
                    raise ValueError
                if ext == ".pptx":
                    members.sort(key=lambda n: int(Path(n).stem.removeprefix("slide")))
                pages = [
                    {
                        "number": int(Path(n).stem.removeprefix("slide")) if ext == ".pptx" else 1,
                        "text": "\n".join(
                            paragraph_text(p) if ext == ".docx" else "".join(p.itertext())
                            for p in ET.fromstring(archive.read(n)).iter()
                            if p.tag
                            in {W + "p", "{http://schemas.openxmlformats.org/drawingml/2006/main}p"}
                        ),
                    }
                    for n in members
                ]
        else:
            raise AIError(
                "unsupported_document",
                "Chọn TXT, MD, DOCX, PPTX, PDF hoặc ảnh PNG/JPEG/WebP.",
            )
    except AIError:
        raise
    except (ValueError, UnicodeError, binascii.Error, zipfile.BadZipFile, ET.ParseError, KeyError):
        raise AIError(
            "invalid_document", "Không đọc được tệp hoặc tệp vượt giới hạn 15 MB."
        ) from None
    if not any(page["text"].strip() for page in pages):
        raise AIError("empty_document", "Không tìm thấy chữ trong tệp. Hãy dán nội dung nguồn.")
    if sum(len(page["text"]) for page in pages) > 200000:
        raise AIError("document_limit", "Văn bản vượt200.000ký tự. Hãy tách phần cần dùng.")
    return {
        "pages": pages,
        "method": "pypdf_local_text" if ext == ".pdf" else "python_local_text",
        "sentToAI": False,
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


def exam_html(exam, teacher, origin, figures=None, *, rendered_math=None):
    figures = list(figures or [])
    if (
        not isinstance(exam, dict)
        or not isinstance(exam.get("questions"), list)
        or any(not isinstance(question, dict) for question in exam["questions"])
    ):
        raise AIError("invalid_exam", "Đề xuất chưa hợp lệ.")
    body = (
        f"<h1>{inline_html(exam.get('title'))}</h1><p>{inline_html(exam.get('school'))}</p>"
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
    if presenting and has_reference:
        body += "</div>"
    for i, q in enumerate(exam["questions"]):
        if q.get("figure") and not figures:
            raise AIError("unsupported_export", "Chưa có bản dựng hình để xuất; không bỏ hình.")
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
        for table in q.get("tables", []):
            body += (
                "<table>"
                + "".join(
                    "<tr>" + "".join("<td>" + inline_html(v) + "</td>" for v in row) + "</tr>"
                    for row in table.get("rows", [])
                )
                + "</table>"
            )
        for image in q.get("images", []):
            data = image.get("data", "")
            if (
                not isinstance(data, str)
                or len(data) > MAX_DOCUMENT * 2
                or not re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+", data)
            ):
                raise AIError("invalid_image", "Hình trong câu chưa có dữ liệu hợp lệ để xuất.")
            binary, _, _ = image_bytes(data)
            data = "data:image/png;base64," + base64.b64encode(binary).decode()
            body += (
                '<figure><img style="max-width:100%;max-height:250px" src="'
                + html.escape(data, quote=True)
                + '" alt="'
                + html.escape(str(image.get("caption") or "Hình câu hỏi"), quote=True)
                + '"><figcaption>'
                + plain(image.get("caption"))
                + "</figcaption></figure>"
            )
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
            body += (
                '<ol type="A">'
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
    layout = exam.get("layout") or {}
    font = (
        layout.get("font")
        if layout.get("font") in {"Times New Roman", "Arial", "Calibri"}
        else "Times New Roman"
    )
    size = min(22, max(10, float(layout.get("fontSize") or 15)))
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
        f'body{{font:{size}pt "{font}",serif;max-width:760px;margin:30px auto;color:#111}}'
        "h1{font-size:18pt;text-align:center}section{margin:20px 0}"
        "section>b{display:block;break-after:avoid}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid;padding:6px}"
        "figure svg{max-width:100%;height:auto}"
        "figure{break-inside:avoid;text-align:center;margin:12px 0}"
        "figure img{display:block;margin:auto}li>p,td>p,th>p{margin:0}tr{break-inside:avoid}"
        "blockquote,small{font-size:11pt;color:#444}@page{size:A4;margin:18mm}"
        ".page-break{break-before:page}"
        "@media print{body{margin:0}section,ol,ul{break-inside:avoid}"
        ".rubric-title{break-after:avoid}}"
        + (PRESENTATION_CSS if presenting else "")
        + "</style><body>"
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
    r"\b[A-D]\b|(?i:cả (?:hai|ba|bốn)|(?:tất cả|không có).{0,30}(?:trên|sau)|"
    r"phương án (?:trên|dưới|[a-d]\b)|(?:chọn|đáp án)\s*\(?[a-d]\b|all of|none of|both)",
)
_QUESTION_REFERENCE = re.compile(r"\b(?:câu|bài)\s*(?:số\s*)?(\d+)\b", re.IGNORECASE)


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
    ids = variant.get("questionIds") if isinstance(variant, dict) else None
    offset = variant.get("offset") if isinstance(variant, dict) else None
    shuffle = variant.get("shuffleOptions", False) if isinstance(variant, dict) else False
    if (
        not isinstance(ids, list)
        or not 2 <= len(ids) <= 300
        or any(not isinstance(value, str) or not value for value in ids)
        or len(set(ids)) != len(ids)
        or type(offset) is not int
        or not 0 <= offset < min(6, len(ids))
        or type(shuffle) is not bool
        or any(not isinstance(q, dict) for q in questions)
    ):
        raise AIError("invalid_variant", "Chọn ít nhất hai câu và một mã đề hợp lệ.")
    selected = set(ids)
    positions = [i for i, q in enumerate(questions) if q.get("id") in selected]
    if len(positions) != len(ids) or {questions[i]["id"] for i in positions} != selected:
        raise AIError("invalid_variant", "Danh sách câu đã thay đổi. Chọn lại câu cần trộn.")
    selected_numbers = {str(i + 1) for i in positions}
    if any(
        selected_numbers.intersection(_QUESTION_REFERENCE.findall(text))
        for question in questions
        for text in (
            question.get("stem"),
            *(question["options"] if isinstance(question.get("options"), list) else []),
            question.get("explanation"),
        )
        if isinstance(text, str)
    ):
        raise AIError("invalid_variant", "Có câu được nhắc theo số trong đề. Hãy bỏ chọn câu đó.")
    group = [questions[i] for i in positions]
    first = group[0]
    if any(
        q.get("type", "mcq") != first.get("type", "mcq")
        or uses_table(q) != uses_table(first)
        or q.get("sectionId") != first.get("sectionId")
        or q.get("groupId") != first.get("groupId")
        or q.get("passageId") != first.get("passageId")
        for q in questions[positions[0] : positions[-1] + 1]
    ):
        raise AIError(
            "invalid_variant",
            "Chọn câu trong cùng phần, cùng dạng và cùng ngữ liệu bảng.",
        )
    reordered = questions.copy()
    for index, question in zip(positions, group[offset:] + group[:offset], strict=True):
        candidate = shuffle_variant_question(question, offset) if shuffle else question
        reordered[index] = {**candidate, "pageBreak": questions[index].get("pageBreak", False)}
    code = str(101 + offset)
    return {
        **exam,
        "title": f"{exam.get('title') or 'Đề thi'} · Mã đề {code}",
        "questions": reordered,
    }


def preview_exam_variant(payload):
    exam = payload.get("exam")
    if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
        raise AIError("invalid_exam", "Đề cần danh sách câu để xem trước.")
    variant = exam_variant(exam, payload.get("variant"))
    original = {
        q["id"]: i + 1 for i, q in enumerate(exam["questions"]) if isinstance(q.get("id"), str)
    }
    return {
        "title": variant["title"],
        "questions": [
            {
                "originalNumber": original.get(q.get("id"), i + 1)
                if isinstance(q.get("id"), str)
                else i + 1,
                "stem": q.get("stem", ""),
                "options": q.get("options", []),
            }
            for i, q in enumerate(variant["questions"])
        ],
    }


def export_variant_pack(payload, directory, origin):
    exam = payload.get("exam")
    ids = payload.get("questionIds")
    format_ = payload.get("format", "docx")
    if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
        raise AIError("invalid_exam", "Đề cần danh sách câu để xuất.")
    if format_ not in ("docx", "pdf", "html"):
        raise AIError("unsupported_export", "Chọn Word, PDF hoặc HTML để xuất bộ mã.")
    settings = {"questionIds": ids, "shuffleOptions": payload.get("shuffleOptions", False)}
    first = exam_variant(exam, {**settings, "offset": 0})
    variants = [
        first,
        *[
            exam_variant(exam, {**settings, "offset": offset})
            for offset in range(1, min(6, len(ids)))
        ],
    ]
    headings = "".join(f"<th scope='col'>Mã {101 + i}</th>" for i in range(len(variants)))
    original_numbers = {
        question["id"]: i + 1
        for i, question in enumerate(exam["questions"])
        if question.get("id") in ids
    }
    rows = []
    for i in range(len(exam["questions"])):
        answers = []
        for variant in variants:
            question = variant["questions"][i]
            source = original_numbers.get(question.get("id"), i + 1)
            answer = (
                "Xem hướng dẫn chấm"
                if question.get("type") == "essay"
                else saved_answer_label(question)
            )
            answers.append(f"<td>{html.escape(answer)} <small>(gốc: {source})</small></td>")
        rows.append(f"<tr><th scope='row'>{i + 1}</th>{''.join(answers)}</tr>")
    title = html.escape(str(exam.get("title") or "Đề thi"))
    answer_key = (
        '<!doctype html><html lang="vi"><meta charset="utf-8">'
        "<title>Đối chiếu đáp án · Bản giáo viên</title>"
        "<style>@page{size:A4;margin:18mm}body{font:16px system-ui}"
        "table{border-collapse:collapse}th,td{border:1px solid;padding:8px}</style>"
        f"<h1>Đối chiếu đáp án · Bản giáo viên</h1><p>{title}</p>"
        "<p>Số trong ngoặc chỉ câu tương ứng trên đề gốc; dùng số này để tra hướng dẫn chấm.</p>"
        f'<table><thead><tr><th scope="col">Câu</th>{headings}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></html>"
    )
    directory.mkdir(parents=True, exist_ok=True)
    name = "De_thi_" + str(uuid4()) + ".zip"
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


def export_file(payload, directory, origin):
    kind = payload.get("type")
    format_ = payload.get("format", "html")
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
        rendered = {"figures": [], "math": {}}
        if format_ != "docx":
            formulas, figures = export_inputs(exam, payload.get("teacher") is True)
            rendered = render_assets(formulas, figures, chrome_path())
        content = (
            exam_html(
                exam,
                payload.get("teacher") is True,
                Path(__file__).resolve().parents[3].as_uri() if format_ == "pdf" else origin,
                rendered["figures"],
                rendered_math=rendered["math"] if format_ == "html" else None,
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
    name = "De_thi_" + str(uuid4()) + "." + format_
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
            try:
                subprocess.run(
                    [
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
                    ],
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
        target.write_bytes(export_docx(exam, payload.get("teacher") is True, chrome_path()))
    else:
        raise AIError("unsupported_export", "Định dạng xuất chưa được hỗ trợ.")
    return {"filename": name, "bytes": target.stat().st_size, "url": "/api/exports/" + name}
