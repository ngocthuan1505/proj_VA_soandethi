"""Xuất rich document bằng Python; Word sửa được công thức/bảng/chữ, hình nhúng tại máy."""

import base64
import binascii
import io
import json
import math
import re
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

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
            for row in table["rows"]:
                for cell in row:
                    if isinstance(cell, dict):
                        if cell.get("type") == "doc":
                            yield "", cell, None
                    else:
                        yield cell, None, None
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


def watermark_image_bytes(data: Any, *, fade_alpha: float = 0.16) -> tuple[bytes, int, int]:
    """Xác thực ảnh hình mờ PNG/JPEG qua Pillow và tạo bản PNG an toàn."""
    if (
        not isinstance(data, str)
        or len(data) > 20 * 1024 * 1024
        or not re.fullmatch(r"data:image/(?:png|jpeg);base64,[A-Za-z0-9+/=]+", data)
    ):
        raise AIError("invalid_image", "Ảnh hình mờ phải là định dạng PNG hoặc JPEG hợp lệ.")
    try:
        raw = base64.b64decode(data.split(",", 1)[1], validate=True)
        if len(raw) > 15 * 1024 * 1024:
            raise ValueError
        with Image.open(io.BytesIO(raw), formats=("PNG", "JPEG")) as image:
            if image.width * image.height > 20_000_000 or getattr(image, "n_frames", 1) != 1:
                raise ValueError
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1200, 1200))
            rgba = image.convert("RGBA")
            if 0.0 < fade_alpha < 1.0:
                alpha = rgba.getchannel("A").point(lambda px: int(px * fade_alpha))
                rgba.putalpha(alpha)
            out = io.BytesIO()
            rgba.save(out, format="PNG")
            return out.getvalue(), rgba.width, rgba.height
    except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
        raise AIError(
            "invalid_image", "Ảnh hình mờ PNG/JPEG bị hỏng hoặc vượt giới hạn cho phép."
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
        size = min(22, max(10, float(layout.get("fontSize") or 15)))
        raw_line_height = layout.get("lineHeight")
        line_height: float | None = None
        if (
            not isinstance(raw_line_height, bool)
            and isinstance(raw_line_height, (int, float))
            and math.isfinite(raw_line_height)
        ):
            line_height = min(2.5, max(1.0, float(raw_line_height)))
        self.font_name = font
        self.font_size = size
        self.mcq_columns = 2 if layout.get("mcqColumns") == 2 else 1
        self._apply_page_chrome(section, layout)
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
            if line_height is not None and name in {"Normal", "List Bullet", "List Number"}:
                style.paragraph_format.line_spacing = line_height
        for border in self.doc.styles.element.findall(".//" + qn("w:pBdr")):
            border.getparent().remove(border)
        self.num_id = (
            max(
                int(n.get(qn("w:numId")))
                for n in self.doc.part.numbering_part.element.findall(qn("w:num"))
            )
            + 1
        )

    @staticmethod
    def _append_field(paragraph, field_name: str) -> None:
        for kind, text in (("begin", None), ("instr", f" {field_name} "), ("separate", None)):
            r = paragraph.add_run()
            if kind == "instr":
                instr = OxmlElement("w:instrText")
                instr.set(qn("xml:space"), "preserve")
                instr.text = text
                r._r.append(instr)
            else:
                fc = OxmlElement("w:fldChar")
                fc.set(qn("w:fldCharType"), kind)
                r._r.append(fc)
        paragraph.add_run("1")
        r_end = paragraph.add_run()
        fc_end = OxmlElement("w:fldChar")
        fc_end.set(qn("w:fldCharType"), "end")
        r_end._r.append(fc_end)

    def _apply_page_chrome(self, section, layout: dict[str, Any]) -> None:
        header_text = str(layout.get("headerText") or "").strip()
        footer_text = str(layout.get("footerText") or "").strip()
        show_pages = bool(layout.get("showPageNumbers"))
        watermark = str(layout.get("watermarkText") or "").strip()
        watermark_image = layout.get("watermarkImage")
        has_wm_image = isinstance(watermark_image, str) and bool(watermark_image.strip())

        if header_text or watermark or has_wm_image:
            section.header.is_linked_to_previous = False
            hp = section.header.paragraphs[0]
            used_first = False
            if header_text:
                hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                hp.add_run(header_text).font.size = Pt(10)
                used_first = True
            if watermark:
                wp = section.header.add_paragraph() if used_first else hp
                used_first = True
                wp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                escaped_wm = xml_escape(watermark[:80], {'"': "&quot;", "'": "&apos;"})
                pict_xml = (
                    '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                    ' xmlns:v="urn:schemas-microsoft-com:vml"'
                    ' xmlns:o="urn:schemas-microsoft-com:office:office">'
                    '<v:shape id="MachWatermark" o:spid="_x0000_s2049" '
                    'style="position:absolute;margin-left:0;margin-top:0;width:468pt;height:140pt;'
                    "rotation:315;z-index:-251654144;mso-position-horizontal:center;"
                    "mso-position-horizontal-relative:margin;mso-position-vertical:center;"
                    'mso-position-vertical-relative:margin" '
                    'fillcolor="#d8d8d8" stroked="f">'
                    f'<v:textpath style="font-family:&quot;Times New Roman&quot;;font-size:1pt" '
                    f'string="{escaped_wm}"/>'
                    "</v:shape></w:pict>"
                )
                r = wp.add_run()
                r._r.append(parse_xml(pict_xml))
            if has_wm_image:
                wm_bytes, wm_w, wm_h = watermark_image_bytes(watermark_image, fade_alpha=0.16)
                wp_img = section.header.add_paragraph() if used_first else hp
                wp_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                scale = min(3.4 / max(1, wm_w), 1.6 / max(1, wm_h), 1 / 96)
                shape = wp_img.add_run().add_picture(
                    io.BytesIO(wm_bytes),
                    width=Inches(max(0.4, wm_w * scale)),
                    height=Inches(max(0.4, wm_h * scale)),
                )
                shape._inline.docPr.set("descr", "Hình mờ đề thi")

        if footer_text or show_pages:
            section.footer.is_linked_to_previous = False
            fp = section.footer.paragraphs[0]
            fp.alignment = (
                WD_ALIGN_PARAGRAPH.RIGHT
                if show_pages and not footer_text
                else (WD_ALIGN_PARAGRAPH.CENTER)
            )
            if footer_text:
                fr = fp.add_run(footer_text + ("   |   " if show_pages else ""))
                fr.font.size = Pt(10)
            if show_pages:
                fp.add_run("Trang ").font.size = Pt(10)
                self._append_field(fp, "PAGE")
                fp.add_run(" / ").font.size = Pt(10)
                self._append_field(fp, "NUMPAGES")

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
            elif kind == "codeBlock":
                p = container.add_paragraph()
                p.paragraph_format.left_indent = Mm(7 * (indent + 1))
                shade = OxmlElement("w:shd")
                shade.set(qn("w:val"), "clear")
                shade.set(qn("w:fill"), "f4f6f5")
                p._p.get_or_add_pPr().append(shade)
                code_size = Pt(max(9, self.font_size - 2))
                for child in node.get("content", []):
                    if child.get("type") == "hardBreak":
                        p.add_run().add_break()
                    else:
                        run = p.add_run(str(child.get("text", "")))
                        run.font.name = "Consolas"
                        run.font.size = code_size
            elif kind == "image":
                src = attrs.get("src") or attrs.get("data")
                caption = attrs.get("alt") or attrs.get("caption") or ""
                align = attrs.get("align", "center")
                self.picture(src, caption, align, container=container)
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

    def picture(self, data, caption="", align="center", container=None):
        binary, width, height = image_bytes(data)
        max_w = 2.4 if container is not None and container is not self.doc else 6.85
        scale = min(max_w / width, 3.2 / height, 1 / 96)
        target = container if container is not None else self.doc
        p = target.add_paragraph()
        p.alignment = ALIGN.get(align, WD_ALIGN_PARAGRAPH.CENTER)
        shape = p.add_run().add_picture(
            io.BytesIO(binary), width=Inches(width * scale), height=Inches(height * scale)
        )
        shape._inline.docPr.set("descr", caption or "Hình câu hỏi")
        if caption:
            p = target.add_paragraph(caption)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.italic = True

    def _write_mcq_two_column(self, options: list[str], docs: list[Any]) -> None:
        tbl = self.doc.add_table(rows=2, cols=2)
        tbl.autofit = False
        tbl_pr = tbl._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "none")
            borders.append(el)
        tbl_pr.append(borders)
        col_width = Mm(87)
        for col in tbl.columns:
            col.width = col_width
        for j, option in enumerate(options[:4]):
            cell = tbl.cell(j // 2, j % 2)
            cell.width = col_width
            cell._tc.clear_content()
            self.field(
                option,
                docs[j] if j < len(docs) else None,
                prefix=f"{'ABCD'[j]}. ",
                container=cell,
            )
            if len(cell._tc) == 0 or cell._tc[-1].tag != qn("w:p"):
                cell.add_paragraph()

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
                                (
                                    {
                                        "type": "tableCell",
                                        "content": [
                                            {
                                                "type": "image",
                                                "attrs": {
                                                    "src": cell["data"],
                                                    "caption": cell.get("caption", ""),
                                                },
                                            }
                                        ],
                                    }
                                    if isinstance(cell, dict) and cell.get("data")
                                    else {
                                        "type": "tableCell",
                                        "content": (
                                            cell["content"]
                                            if isinstance(cell, dict) and cell.get("type") == "doc"
                                            else field_document(cell)["content"]
                                        ),
                                    }
                                )
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
            options = q.get("options", [])
            docs = q.get("optionDocs") or []
            if (
                self.mcq_columns == 2
                and q.get("type", "mcq") == "mcq"
                and isinstance(options, list)
                and len(options) == 4
            ):
                self._write_mcq_two_column(options, docs)
            else:
                for j, option in enumerate(options):
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
