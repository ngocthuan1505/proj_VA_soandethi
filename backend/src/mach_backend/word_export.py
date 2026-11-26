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
DRAFT_BANNER_TITLE = "BẢN NHÁP — CẦN RÀ SOÁT TRƯỚC KHI PHÁT"
DRAFT_WARNING_CODE_LABELS: dict[str, str] = {
    "linked_data_explanation_stale": "Số liệu lời giải liên kết Bảng 1 cần cập nhật",
    "linked_data_mismatch": "Đáp án hoặc phương án lệch dữ kiện Bảng 1",
    "stale_quote_evidence": "Trích dẫn nguồn cần rà lại",
}


def normalize_draft_warnings(
    draft_warnings: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not isinstance(draft_warnings, list):
        return []
    return [dict(item) for item in draft_warnings if isinstance(item, dict)]


def format_draft_warning(item: dict[str, Any]) -> str:
    code = str(item.get("code") or "").strip()
    label = DRAFT_WARNING_CODE_LABELS.get(code, "")
    raw_msg = str(item.get("message") or "").strip()
    ordinal = item.get("ordinal")
    prefix = f"Câu {ordinal}: " if type(ordinal) is int and ordinal >= 1 else ""
    if raw_msg:
        return f"{label} — {raw_msg}" if label else raw_msg
    if label:
        return f"{prefix}{label}."
    return f"{prefix}Cần rà soát nội dung trước khi phát."


def match_question_warnings(
    question: dict[str, Any],
    ordinal: int,
    draft_warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    qid = str(question.get("id") or "").strip()
    matched: list[dict[str, Any]] = []
    for item in draft_warnings:
        w_qid = str(item.get("questionId") or "").strip()
        w_ord = item.get("ordinal")
        if qid and w_qid:
            if w_qid == qid:
                matched.append(item)
        elif type(w_ord) is int and w_ord == ordinal:
            matched.append(item)
    return matched


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


def build_passages_catalog(exam: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Chuẩn hóa danh mục ngữ liệu từ exam['passages'] dạng list hoặc dict."""
    catalog: dict[str, dict[str, Any]] = {}
    raw = exam.get("passages")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id") is not None:
                pid = str(item["id"]).strip()
                if pid:
                    catalog[pid] = item
    elif isinstance(raw, dict):
        for key, item in raw.items():
            key_id = str(key).strip()
            if isinstance(item, dict):
                pid = str(item["id"]).strip() if item.get("id") is not None else key_id
                if pid:
                    catalog[pid] = item
                if key_id and key_id not in catalog:
                    catalog[key_id] = item
            elif isinstance(item, str) and key_id:
                catalog[key_id] = {"id": key_id, "text": item}
    return catalog


def resolve_question_passage(
    question: dict[str, Any],
    passages_catalog: dict[str, dict[str, Any]],
    rendered_passages: set[str],
) -> dict[str, Any] | None:
    """Lấy khối ngữ liệu trước câu đầu tiên của từng nhóm, không lặp ở các câu sau."""
    raw_pid = question.get("passageId")
    passage_id = str(raw_pid).strip() if raw_pid is not None and str(raw_pid).strip() else None
    raw_gid = question.get("groupId")
    group_id = str(raw_gid).strip() if raw_gid is not None and str(raw_gid).strip() else None
    dedup_key = f"p:{passage_id}" if passage_id else (f"g:{group_id}" if group_id else None)
    if dedup_key is not None and dedup_key in rendered_passages:
        return None

    p_title = question.get("passageTitle") or question.get("groupTitle")
    p_lead = question.get("passageLead") or question.get("groupLead") or question.get("lead")
    p_text = question.get("passageText")
    p_doc: dict[str, Any] | None = None

    if passage_id and passage_id in passages_catalog:
        p_cat = passages_catalog[passage_id]
        if not (isinstance(p_title, str) and p_title.strip()):
            p_title = p_cat.get("title") or p_cat.get("passageTitle")
        if not (isinstance(p_lead, str) and p_lead.strip()):
            p_lead = p_cat.get("lead") or p_cat.get("passageLead") or p_cat.get("groupLead")
        if not (isinstance(p_text, str) and p_text.strip()):
            p_text = p_cat.get("text") or p_cat.get("passageText") or p_cat.get("description")
        raw_doc = p_cat.get("richDoc")
        if isinstance(raw_doc, dict) and not (
            isinstance(question.get("passageText"), str) and question["passageText"].strip()
        ):
            plain_doc = project(raw_doc, [])
            if not (isinstance(p_text, str) and p_text.strip()) or plain_doc == str(p_text or ""):
                p_doc = raw_doc
                if not (isinstance(p_text, str) and p_text.strip()):
                    p_text = plain_doc

    clean_title = p_title.strip() if isinstance(p_title, str) and p_title.strip() else None
    clean_lead = p_lead.strip() if isinstance(p_lead, str) and p_lead.strip() else None
    clean_text = p_text if isinstance(p_text, str) and p_text.strip() else None
    if clean_lead and (clean_lead == clean_title or clean_lead == (clean_text or "").strip()):
        clean_lead = None
    if not (clean_title or clean_lead or clean_text or p_doc is not None):
        return None
    if dedup_key is not None:
        rendered_passages.add(dedup_key)
    return {
        "title": clean_title,
        "lead": clean_lead,
        "text": clean_text,
        "richDoc": p_doc,
    }


def format_points_vi(p100: int) -> str:
    if p100 % 100 == 0:
        return f"{p100 // 100} điểm"
    text = f"{p100 / 100:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " điểm"


def question_points_p100(question: dict[str, Any]) -> int:
    raw_pts = question.get("points")
    if raw_pts is not None and not isinstance(raw_pts, bool):
        try:
            val = float(raw_pts)
            if math.isfinite(val) and val > 0:
                return round(val * 100)
        except (TypeError, ValueError):
            pass
    raw_q4 = question.get("pointsQ4")
    if isinstance(raw_q4, (int, float)) and not isinstance(raw_q4, bool) and raw_q4 > 0:
        return round(float(raw_q4) * 25)
    return 0


def build_choice_track_plan(questions: list[dict[str, Any]]) -> dict[str, Any] | None:
    tracks: list[tuple[str, str]] = []
    seen_tracks: dict[str, str] = {}
    track_p100: dict[str, int] = {}
    common_p100 = 0
    has_common = False
    for q in questions:
        grp = str(q.get("choiceGroup") or "").strip()
        p100 = question_points_p100(q)
        if grp:
            key = grp.casefold()
            if key not in seen_tracks:
                seen_tracks[key] = grp
                tracks.append((key, grp))
            track_p100[key] = track_p100.get(key, 0) + p100
        else:
            has_common = True
            common_p100 += p100
    if not tracks:
        return None
    return {
        "has_common": has_common,
        "common_p100": common_p100,
        "tracks": tracks,
        "track_index": {key: idx for idx, (key, _) in enumerate(tracks, 1)},
        "track_names": seen_tracks,
        "track_p100": track_p100,
    }


def field_inputs(exam, teacher):
    yield from ((exam.get(k, ""), None, None) for k in ("title", "school", "instructions"))
    yield exam.get("quote", {}).get("text", ""), None, None
    passages_catalog = build_passages_catalog(exam)
    rendered_passages: set[str] = set()
    for q in exam["questions"]:
        passage = resolve_question_passage(q, passages_catalog, rendered_passages)
        if passage is not None:
            if passage["title"]:
                yield passage["title"], None, None
            if passage["lead"]:
                yield passage["lead"], None, None
            if passage["text"] or passage["richDoc"] is not None:
                yield passage["text"] or "", passage["richDoc"], None
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
    def __init__(
        self,
        exam,
        teacher,
        chrome,
        is_draft: bool = False,
        draft_warnings: list[dict[str, Any]] | None = None,
    ):
        self.exam, self.teacher = exam, teacher
        self.is_draft = bool(is_draft)
        self.draft_warnings = normalize_draft_warnings(draft_warnings)
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
                prefix=f"{chr(65 + j)}. ",
                container=cell,
            )
            if len(cell._tc) == 0 or cell._tc[-1].tag != qn("w:p"):
                cell.add_paragraph()

    @staticmethod
    def _apply_box_style(p_el: Any, border_xml: str, fill_hex: str) -> None:
        p_pr = p_el.find(qn("w:pPr"))
        if p_pr is None:
            p_pr = OxmlElement("w:pPr")
            p_el.insert(0, p_pr)
        p_bdr = parse_xml(border_xml)
        shd = parse_xml(
            '<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            f'w:val="clear" w:color="auto" w:fill="{fill_hex}"/>'
        )
        insert_at = len(p_pr)
        for idx, child in enumerate(list(p_pr)):
            if child.tag in {qn("w:spacing"), qn("w:ind"), qn("w:jc")}:
                insert_at = idx
                break
        p_pr.insert(insert_at, p_bdr)
        p_pr.insert(insert_at + 1, shd)
        if p_pr.find(qn("w:ind")) is None:
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), "140")
            ind.set(qn("w:right"), "140")
            p_pr.append(ind)

    def _add_draft_paragraph(self, prefix: str, body: str = "") -> None:
        p = self.doc.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        p_bdr = parse_xml(
            '<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:left w:val="single" w:sz="18" w:space="6" w:color="D97706"/>'
            "</w:pBdr>"
        )
        shd = parse_xml(
            '<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'w:val="clear" w:color="auto" w:fill="FFFBEB"/>'
        )
        p_pr.append(p_bdr)
        p_pr.append(shd)
        r_head = p.add_run(prefix)
        r_head.bold = True
        r_head.font.color.rgb = RGBColor(146, 64, 14)
        if body:
            r_body = p.add_run(body)
            r_body.font.color.rgb = RGBColor(120, 53, 15)

    def _add_section_heading(self, text: str) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(self.font_size + 1)
        run.font.color.rgb = RGBColor(15, 76, 129)

    def _add_choice_instruction_box(self, body: str) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(6)
        border_xml = (
            '<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:top w:val="single" w:sz="10" w:space="6" w:color="0F4C81"/>'
            '<w:left w:val="single" w:sz="18" w:space="8" w:color="0F4C81"/>'
            '<w:bottom w:val="single" w:sz="10" w:space="6" w:color="0F4C81"/>'
            '<w:right w:val="single" w:sz="10" w:space="6" w:color="0F4C81"/>'
            "</w:pBdr>"
        )
        self._apply_box_style(p._p, border_xml, "EFF6FF")
        r_head = p.add_run("PHẦN RIÊNG — ")
        r_head.bold = True
        r_head.font.color.rgb = RGBColor(15, 76, 129)
        r_body = p.add_run(body)
        r_body.bold = True
        r_body.font.color.rgb = RGBColor(15, 23, 42)

    def _add_passage_box(self, passage: dict[str, Any]) -> None:
        body_el = self.doc._body._body
        start_idx = len(body_el)
        if passage.get("title"):
            self.blocks(self.doc, field_document(passage["title"]).get("content", []), bold=True)
        if passage.get("lead"):
            self.field(passage["lead"])
        if passage.get("text") or passage.get("richDoc") is not None:
            self.field(passage.get("text") or "", passage.get("richDoc"))
        border_xml = (
            '<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:top w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
            '<w:left w:val="single" w:sz="18" w:space="8" w:color="0F4C81"/>'
            '<w:bottom w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
            '<w:right w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
            "</w:pBdr>"
        )
        added_paras = [el for el in list(body_el)[start_idx:] if el.tag == qn("w:p")]
        for idx, p_el in enumerate(added_paras):
            self._apply_box_style(p_el, border_xml, "F8FAFC")
            if idx == len(added_paras) - 1:
                p_pr = p_el.find(qn("w:pPr"))
                if p_pr is not None and p_pr.find(qn("w:spacing")) is None:
                    spacing = OxmlElement("w:spacing")
                    spacing.set(qn("w:after"), "140")
                    ind = p_pr.find(qn("w:ind"))
                    if ind is not None:
                        p_pr.insert(list(p_pr).index(ind), spacing)
                    else:
                        p_pr.append(spacing)

    def write(self):
        e = self.exam
        if bool(self.teacher) and (self.is_draft or self.draft_warnings):
            self._add_draft_paragraph(DRAFT_BANNER_TITLE)
            if self.draft_warnings:
                self._add_draft_paragraph(
                    f"Tóm tắt cảnh báo ({len(self.draft_warnings)} mục):",
                    " rà soát trước khi phát cho học sinh.",
                )
                for item in self.draft_warnings:
                    self._add_draft_paragraph("• ", format_draft_warning(item))
            else:
                self._add_draft_paragraph(
                    "Ghi chú: ",
                    "Đề thi đang ở trạng thái bản nháp; cần kiểm tra lại trước khi phát.",
                )
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
        passages_catalog = build_passages_catalog(e)
        rendered_passages: set[str] = set()
        track_plan = build_choice_track_plan(e["questions"])
        rendered_common = False
        rendered_elective_box = False
        current_track_key: str | None = None
        for i, q in enumerate(e["questions"], 1):
            if q.get("pageBreak"):
                self.doc.add_page_break()
            if track_plan is not None:
                grp = str(q.get("choiceGroup") or "").strip()
                grp_key = grp.casefold() if grp else ""
                if not grp_key:
                    if not rendered_common:
                        rendered_common = True
                        pts_suffix = (
                            f" ({format_points_vi(track_plan['common_p100'])})"
                            if track_plan["common_p100"] > 0
                            else ""
                        )
                        self._add_section_heading(f"PHẦN CHUNG{pts_suffix}")
                else:
                    if not rendered_elective_box:
                        rendered_elective_box = True
                        track_labels = " / ".join(
                            f"Hướng {idx}: {name}"
                            for idx, (_, name) in enumerate(track_plan["tracks"], 1)
                        )
                        self._add_choice_instruction_box(
                            f"Thí sinh chỉ chọn làm MỘT trong các hướng sau ({track_labels})."
                        )
                    if grp_key != current_track_key:
                        current_track_key = grp_key
                        idx = track_plan["track_index"][grp_key]
                        name = track_plan["track_names"][grp_key]
                        pts = track_plan["track_p100"].get(grp_key, 0)
                        pts_suffix = f" ({format_points_vi(pts)})" if pts > 0 else ""
                        self._add_section_heading(f"Hướng {idx}: {name}{pts_suffix}")
            passage = resolve_question_passage(q, passages_catalog, rendered_passages)
            if passage is not None:
                self._add_passage_box(passage)
            score = (
                " (" + str(q["points"]).replace(".", ",") + " điểm)"
                if q.get("points") is not None
                else ""
            )
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
                    self.field(
                        option,
                        docs[j] if j < len(docs) else None,
                        prefix=f"{chr(65 + j)}. ",
                    )
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
                for warn in match_question_warnings(q, i, self.draft_warnings):
                    self._add_draft_paragraph("Lưu ý rà soát: ", format_draft_warning(warn))
        self.doc.add_paragraph("— Hết —").alignment = WD_ALIGN_PARAGRAPH.CENTER
        output = io.BytesIO()
        self.doc.save(output)
        if output.tell() > 30 * 1024 * 1024:
            raise AIError("export_limit", "Tệp Word vượt 30 MB; tách bớt nội dung.")
        return output.getvalue()


def export_docx(
    exam,
    teacher,
    chrome,
    is_draft: bool = False,
    draft_warnings: list[dict[str, Any]] | None = None,
):
    try:
        return WordWriter(
            exam,
            teacher,
            chrome,
            is_draft=is_draft,
            draft_warnings=draft_warnings,
        ).write()
    except AIError:
        raise
    except (ValueError, TypeError, KeyError, IndexError):
        raise AIError(
            "invalid_document", "Nội dung rich/bảng/hình chưa hợp lệ; chưa xuất Word."
        ) from None
