"""Xuất rich document bằng Python; Word sửa được công thức/bảng/chữ, hình nhúng tại máy."""

import base64
import binascii
import io
import json
import math
import re
from typing import Any
from xml.etree import ElementTree as ET

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from PIL import Image, ImageOps

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer_label
from mach_backend.export_assets import render_assets
from mach_backend.math_word import omml
from mach_backend.rich_patch import project

MATH = re.compile(r"\$\$(.+?)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$|\\\[(.+?)\\\]|\\\((.+?)\\\)", re.S)
FONTS = {"Times New Roman", "Arial", "Calibri"}
ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def recipient_line(teacher):
    if teacher:
        return "BẢN GIÁO VIÊN · ĐÁP ÁN VÀ HƯỚNG DẪN CHẤM"
    return "Họ và tên: ........................................ Lớp: .................."


def math_parts(text):
    at = 0
    for match in MATH.finditer(text):
        if match.start() > at:
            yield False, text[at : match.start()]
        yield True, next(x for x in match.groups() if x is not None)
        at = match.end()
    if at < len(text):
        yield False, text[at:]


def field_document(text, doc=None, runs=None):
    text = str(text or "")
    if doc:
        if project(doc, []) != text:
            raise AIError(
                "stale_document", "Văn bản và rich document chưa khớp; lưu lại câu trước khi xuất."
            )
        return doc
    if runs:
        if "".join(r["text"] for r in runs) != text:
            raise AIError("stale_document", "Các đoạn định dạng chưa khớp thân câu.")
        content = []
        for r in runs:
            marks: list[dict[str, Any]] = [
                {"type": k} for k in ("bold", "italic", "underline") if r.get(k)
            ]
            if r.get("color"):
                marks.append({"type": "textStyle", "attrs": {"color": r["color"]}})
            if r.get("highlight"):
                marks.append({"type": "highlight", "attrs": {"color": r["highlight"]}})
            if r["text"]:
                content.append({"type": "text", "text": r["text"], "marks": marks})
        return {"type": "doc", "content": [{"type": "paragraph", "content": content}]}
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def field_inputs(exam, teacher):
    yield from ((exam.get(k, ""), None, None) for k in ("title", "school", "instructions"))
    yield exam.get("quote", {}).get("text", ""), None, None
    for q in exam["questions"]:
        yield q.get("stem", ""), q.get("richDoc"), q.get("runs")
        for i, text in enumerate(q.get("options", [])):
            docs = q.get("optionDocs") or []
            yield text, docs[i] if i < len(docs) else None, None
        for table in q.get("tables", []):
            yield from ((cell, None, None) for row in table["rows"] for cell in row)
        if teacher:
            yield saved_answer_label(q), None, None
            yield q.get("explanation", ""), q.get("explanationDoc"), None
            yield from ((r.get("text", ""), r.get("richDoc"), None) for r in q.get("rubric", []))


def uses_table(question):
    return question.get("dataLinked") is True or question.get("rule") in {"max", "difference"}


def data_chart(exam):
    data = exam.get("data")
    if not isinstance(data, list) or not 1 <= len(data) <= 100:
        raise AIError("missing_data", "Câu liên kết Bảng 1 cần từ 1 đến 100 dòng dữ kiện.")
    for row in data:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("label"), str)
            or type(row.get("value")) not in {int, float}
            or not 0 <= row["value"] <= 1e12
            or not math.isfinite(row["value"])
        ):
            raise AIError("invalid_table", "Nhãn hoặc số liệu Bảng 1 chưa hợp lệ.")
    return {"dataChart": [{"label": r["label"], "value": r["value"]} for r in data]}


def image_bytes(data):
    if (
        not isinstance(data, str)
        or len(data) > 20 * 1024 * 1024
        or not re.fullmatch(r"data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+", data)
    ):
        raise AIError("invalid_image", "Chỉ xuất ảnh PNG/JPEG/WebP nhúng trong đề, tối đa 15 MB.")
    try:
        raw = base64.b64decode(data.split(",", 1)[1], validate=True)
        if len(raw) > 15 * 1024 * 1024:
            raise ValueError
        with Image.open(io.BytesIO(raw), formats=("PNG", "JPEG", "WEBP")) as image:
            if image.width * image.height > 20_000_000 or getattr(image, "n_frames", 1) != 1:
                raise ValueError
            image = ImageOps.exif_transpose(image)
            image.thumbnail((2560, 2560))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            out = io.BytesIO()
            image.save(out, format="PNG")
            return out.getvalue(), image.width, image.height
    except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
        raise AIError(
            "invalid_image", "Ảnh hỏng, ảnh động hoặc vượt 20 triệu pixel; chưa xuất tệp."
        ) from None


def export_inputs(exam, teacher):
    if len(exam["questions"]) > 300 or len(json.dumps(exam, ensure_ascii=False)) > 25_000_000:
        raise AIError("export_limit", "Đề vượt giới hạn 300 câu hoặc 25 MB.")
    formulas = []
    node_count = 0

    def collect(n, depth=0):
        nonlocal node_count
        node_count += 1
        if node_count > 50000 or depth > 64:
            raise AIError("export_limit", "Rich document lồng quá sâu.")
        if n.get("type") == "mathInline":
            formulas.append(n["attrs"]["latex"])
        elif n.get("type") == "text":
            formulas.extend(value for is_math, value in math_parts(n.get("text", "")) if is_math)
        for child in n.get("content", []):
            collect(child, depth + 1)

    for text, doc, runs in field_inputs(exam, teacher):
        collect(field_document(text, doc, runs))
    for q in exam["questions"]:
        formulas.extend(f["latex"] for f in q.get("formulas", []))
    figures = [data_chart(exam)] if any(uses_table(q) for q in exam["questions"]) else []
    figures.extend(q["figure"] for q in exam["questions"] if q.get("figure"))
    return formulas, figures


class WordWriter:
    def __init__(self, exam, teacher, chrome):
        self.exam, self.teacher = exam, teacher
        formulas, figures = export_inputs(exam, teacher)
        self.assets = render_assets(formulas, figures, chrome)
        self.figure_at = 0
        self.doc = Document()
        zoom = self.doc.settings.element.find(qn("w:zoom"))
        if zoom is not None:
            zoom.set(qn("w:percent"), "100")
        section = self.doc.sections[0]
        section.page_width, section.page_height = Mm(210), Mm(297)
        section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = (
            Mm(18)
        )
        layout = exam.get("layout") or {}
        font = layout.get("font") if layout.get("font") in FONTS else "Times New Roman"
        size = min(22, max(10, float(layout.get("fontSize") or 13)))
        for name in (
            "Normal",
            "Title",
            "Heading 1",
            "Heading 2",
            "Heading 3",
            "List Bullet",
            "List Number",
        ):
            style = self.doc.styles[name]
            style.font.name, style.font.size = (
                font,
                Pt(size if name not in {"Title", "Heading 1"} else size + 2),
            )
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(6)
        for border in self.doc.styles.element.findall(".//" + qn("w:pBdr")):
            border.getparent().remove(border)
        self.num_id = (
            max(
                int(n.get(qn("w:numId")))
                for n in self.doc.part.numbering_part.element.findall(qn("w:num"))
            )
            + 1
        )

    def inline(self, p, node, bold=False):
        kind = node["type"]
        if kind == "hardBreak":
            p.add_run().add_break()
            return
        if kind == "mathInline":
            latex = node["attrs"]["latex"]
            p._p.append(parse_xml(ET.tostring(omml(self.assets["math"][latex]))))
            return
        if kind != "text":
            raise AIError("unsupported_document", "Nút trong dòng chưa xuất được: " + str(kind))
        marks = node.get("marks", [])
        for is_math, value in math_parts(node.get("text", "")):
            if is_math:
                p._p.append(parse_xml(ET.tostring(omml(self.assets["math"][value]))))
                continue
            run = p.add_run(value.replace(r"\$", "$"))
            if bold:
                run.bold = True
            for mark in marks:
                t, attrs = mark["type"], mark.get("attrs", {})
                if t in {"bold", "italic", "underline", "strike"}:
                    setattr(run.font, t, True)
                elif t == "textStyle":
                    if re.fullmatch(r"#[0-9a-fA-F]{6}", attrs.get("color", "")):
                        run.font.color.rgb = RGBColor.from_string(attrs["color"][1:])
                    if attrs.get("fontFamily") in FONTS:
                        run.font.name = attrs["fontFamily"]
                    if match := re.fullmatch(
                        r"(\d{1,2}(?:\.\d)?)(pt|px)", str(attrs.get("fontSize", ""))
                    ):
                        run.font.size = Pt(
                            min(72, max(6, float(match[1]) * (0.75 if match[2] == "px" else 1)))
                        )
                elif t == "highlight":
                    if re.fullmatch(r"#[0-9a-fA-F]{6}", attrs.get("color", "")):
                        shade = OxmlElement("w:shd")
                        shade.set(qn("w:val"), "clear")
                        shade.set(qn("w:fill"), attrs["color"][1:])
                        run._r.get_or_add_rPr().append(shade)
                elif t == "link":
                    href = attrs.get("href", "")
                    if not re.match(r"^https?://", href, re.I):
                        raise AIError("invalid_link", "Liên kết trong đề chưa hợp lệ.")
                    link = OxmlElement("w:hyperlink")
                    link.set(qn("r:id"), p.part.relate_to(href, RT.HYPERLINK, is_external=True))
                    link.append(run._r)
                    p._p.append(link)
                else:
                    raise AIError("unsupported_document", "Định dạng chưa hỗ trợ: " + str(t))

    def numbered(self, start, bullet):
        root = self.doc.part.numbering_part.element
        number = self.num_id
        self.num_id += 1
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(number + 100))
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), "0")
        for name, value in (
            ("start", start),
            ("numFmt", "bullet" if bullet else "decimal"),
            ("lvlText", "•" if bullet else "%1."),
        ):
            prop = OxmlElement("w:" + name)
            prop.set(qn("w:val"), str(value))
            lvl.append(prop)
        abstract.append(lvl)
        first_num = root.find(qn("w:num"))
        root.insert(root.index(first_num) if first_num is not None else len(root), abstract)
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(number))
        aid = OxmlElement("w:abstractNumId")
        aid.set(qn("w:val"), str(number + 100))
        num.append(aid)
        root.append(num)
        return number

    def blocks(self, container, nodes, prefix="", bold=False, list_id=None, indent=0):
        first = True
        for node in nodes:
            kind, attrs = node["type"], node.get("attrs", {})
            if kind in {"paragraph", "heading"}:
                p = (
                    container.add_paragraph(
                        style="Heading " + str(min(3, max(1, int(attrs.get("level", 2)))))
                    )
                    if kind == "heading"
                    else container.add_paragraph()
                )
                p.alignment = ALIGN.get(attrs.get("textAlign"), WD_ALIGN_PARAGRAPH.LEFT)
                if indent:
                    p.paragraph_format.left_indent = Mm(7 * indent)
                if first and prefix:
                    p.add_run(prefix).bold = True
                if list_id is not None and first:
                    num = p._p.get_or_add_pPr().get_or_add_numPr()
                    num.get_or_add_ilvl().val = 0
                    num.get_or_add_numId().val = list_id
                for child in node.get("content", []):
                    self.inline(p, child, bold)
            elif kind == "table":
                if first and prefix:
                    container.add_paragraph(prefix)
                self.table(container, node.get("content", []))
            elif kind in {"bulletList", "orderedList"}:
                if first and prefix:
                    container.add_paragraph(prefix)
                number = self.numbered(attrs.get("start", 1), kind == "bulletList")
                for item in node.get("content", []):
                    self.blocks(
                        container,
                        item.get("content", []),
                        bold=bold,
                        list_id=number,
                        indent=indent + 1,
                    )
            elif kind in {"blockquote", "listItem"}:
                self.blocks(
                    container,
                    node.get("content", []),
                    prefix if first else "",
                    bold,
                    indent=indent + 1,
                )
            elif kind == "horizontalRule":
                p = container.add_paragraph()
                borders = OxmlElement("w:pBdr")
                border = OxmlElement("w:bottom")
                border.set(qn("w:val"), "single")
                border.set(qn("w:sz"), "4")
                borders.append(border)
                p._p.get_or_add_pPr().append(borders)
            else:
                raise AIError("unsupported_document", "Cấu trúc chưa xuất được: " + str(kind))
            first = False

    def table(self, container, rows):
        if not rows or len(rows) > 200:
            raise AIError("invalid_table", "Bảng cần1–200hàng.")
        positions, occupied, columns = [], set(), 0
        for r, row in enumerate(rows):
            col = 0
            for cell in row.get("content", []):
                while (r, col) in occupied:
                    col += 1
                attrs = cell.get("attrs", {})
                width, height = attrs.get("colspan", 1), attrs.get("rowspan", 1)
                if (
                    type(width) is not int
                    or type(height) is not int
                    or not 1 <= width <= 20
                    or not 1 <= height <= 200
                    or r + height > len(rows)
                    or col + width > 20
                ):
                    raise AIError("invalid_table", "Ô gộp hoặc kích thước bảng chưa hợp lệ.")
                points = {(y, x) for y in range(r, r + height) for x in range(col, col + width)}
                if points & occupied:
                    raise AIError("invalid_table", "Các ô gộp trong bảng bị chồng.")
                occupied |= points
                positions.append((r, col, height, width, cell))
                columns = max(columns, col + width)
                col += width
        if not columns:
            raise AIError("invalid_table", "Bảng chưa có ô.")
        table = container.add_table(rows=len(rows), cols=columns)
        table.style = "Table Grid"
        table.autofit = False
        available = getattr(container, "width", None) or Mm(174)
        for col in table.columns:
            col.width = Inches(available / 914400 / columns)
        for row in table.rows:
            for cell in row.cells:
                cell.width = Inches(available / 914400 / columns)
        for r, c, height, width, node in positions:
            cell = table.cell(r, c)
            if height > 1 or width > 1:
                cell = cell.merge(table.cell(r + height - 1, c + width - 1))
            cell._tc.clear_content()
            self.blocks(cell, node.get("content", []), bold=node["type"] == "tableHeader")
            if len(cell._tc) == 0 or cell._tc[-1].tag != qn("w:p"):
                cell.add_paragraph()
        return table

    def field(self, text, document=None, runs=None, prefix="", container=None):
        self.blocks(
            container if container is not None else self.doc,
            field_document(text, document, runs).get("content", []),
            prefix,
        )

    def picture(self, data, caption="", align="center"):
        binary, width, height = image_bytes(data)
        scale = min(6.85 / width, 3.2 / height, 1 / 96)
        p = self.doc.add_paragraph()
        p.alignment = ALIGN.get(align, WD_ALIGN_PARAGRAPH.CENTER)
        shape = p.add_run().add_picture(
            io.BytesIO(binary), width=Inches(width * scale), height=Inches(height * scale)
        )
        shape._inline.docPr.set("descr", caption or "Hình câu hỏi")
        if caption:
            p = self.doc.add_paragraph(caption)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.italic = True

    def write(self):
        e = self.exam
        self.doc.add_paragraph(str(e.get("school", ""))).alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.doc.add_paragraph(
            str(e.get("title", "Đề thi")), style="Title"
        ).alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.doc.add_paragraph(
            f"Môn {e.get('subject', '')} · Lớp {e.get('grade', '')} · {e.get('minutes', '')} phút"
        ).alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.doc.add_paragraph(recipient_line(self.teacher))
        self.field(e.get("instructions", ""))
        if e.get("quote", {}).get("text"):
            self.field(e["quote"]["text"])
        if any(uses_table(q) for q in e["questions"]):
            data = e["data"]
            self.doc.add_paragraph("Bảng 1. Dữ kiện liên kết")
            self.table(
                self.doc,
                [
                    {
                        "content": [
                            {"type": "tableHeader", "content": field_document(text)["content"]}
                            for text in ("Mục", "Giá trị")
                        ]
                    },
                    *[
                        {
                            "content": [
                                {
                                    "type": "tableCell",
                                    "content": field_document(str(value))["content"],
                                }
                                for value in (row["label"], row["value"])
                            ]
                        }
                        for row in data
                    ],
                ],
            )
            self.picture(self.assets["figures"][self.figure_at]["png"], "Biểu đồ dữ kiện Bảng 1")
            self.figure_at += 1
        for i, q in enumerate(e["questions"], 1):
            if q.get("pageBreak"):
                self.doc.add_page_break()
            score = " (" + str(q["points"]).replace(".", ",") + " điểm)" if "points" in q else ""
            self.field(
                q.get("stem", ""),
                q.get("richDoc"),
                q.get("runs"),
                prefix=f"{'Bài' if q.get('type') == 'essay' else 'Câu'} {i}{score}. ",
            )
            for f in q.get("formulas", []):
                self.inline(self.doc.add_paragraph(), {"type": "mathInline", "attrs": f})
            for table in q.get("tables", []):
                self.table(
                    self.doc,
                    [
                        {
                            "content": [
                                {"type": "tableCell", "content": field_document(cell)["content"]}
                                for cell in row
                            ]
                        }
                        for row in table["rows"]
                    ],
                )
            for image in q.get("images", []):
                self.picture(image["data"], image.get("caption", ""))
            if q.get("figure"):
                self.picture(
                    self.assets["figures"][self.figure_at]["png"],
                    q["figure"].get("caption", ""),
                    q["figure"].get("align", "center"),
                )
                self.figure_at += 1
            for j, option in enumerate(q.get("options", [])):
                docs = q.get("optionDocs") or []
                self.field(option, docs[j] if j < len(docs) else None, prefix=f"{'ABCD'[j]}. ")
            if self.teacher:
                answer = saved_answer_label(q)
                self.field("Lời giải tham khảo" if q.get("type") == "essay" else "Đáp án " + answer)
                self.field(q.get("explanation", ""), q.get("explanationDoc"))
                if q.get("rubric"):
                    self.doc.add_heading("Hướng dẫn chấm", level=2)
                    rows = [
                        {
                            "content": [
                                {"type": "tableHeader", "content": field_document(x)["content"]}
                                for x in ("Bước", "Nội dung / lời giải", "Điểm")
                            ]
                        }
                    ]
                    for j, step in enumerate(q["rubric"], 1):
                        rows.append(
                            {
                                "content": [
                                    {
                                        "type": "tableCell",
                                        "content": field_document(str(j))["content"],
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": field_document(
                                            step.get("text", ""), step.get("richDoc")
                                        )["content"],
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": field_document(
                                            str(step.get("points", "")).replace(".", ",")
                                        )["content"],
                                    },
                                ]
                            }
                        )
                    marking = self.table(self.doc, rows)
                    for column, width in zip(marking.columns, (16, 132, 26), strict=True):
                        column.width = Mm(width)
                    for row in marking.rows:
                        for cell, width in zip(row.cells, (16, 132, 26), strict=True):
                            cell.width = Mm(width)
                for evidence in q.get("evidence", []):
                    self.field(evidence.get("quote", ""))
        self.doc.add_paragraph("— Hết —").alignment = WD_ALIGN_PARAGRAPH.CENTER
        output = io.BytesIO()
        self.doc.save(output)
        if output.tell() > 30 * 1024 * 1024:
            raise AIError("export_limit", "Tệp Word vượt 30 MB; tách bớt nội dung.")
        return output.getvalue()


def export_docx(exam, teacher, chrome):
    try:
        return WordWriter(exam, teacher, chrome).write()
    except AIError:
        raise
    except (ValueError, TypeError, KeyError, IndexError):
        raise AIError(
            "invalid_document", "Nội dung rich/bảng/hình chưa hợp lệ; chưa xuất Word."
        ) from None
