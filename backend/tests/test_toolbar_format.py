import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import rich
from mach_backend.paragraph_format import paragraph_layout
from mach_backend.share_snapshot import rich_copy
from mach_backend.word_export import export_docx


def document():
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {
                    "textAlign": "right",
                    "layoutEdited": True,
                    "lineHeight": 1.5,
                    "spaceBefore": 4,
                    "spaceAfter": 12,
                    "leftIndent": 0.5,
                    "firstIndent": 0.2,
                    "borderWidth": 1,
                    "borderColor": "#123456",
                    "paragraphBackground": "#fff2cc",
                },
                "content": [
                    {
                        "type": "text",
                        "text": "Nội dung tự viết",
                        "marks": [
                            {"type": "strike"},
                            {"type": "textStyle", "attrs": {"script": "super", "color": "#ff0000"}},
                        ],
                    }
                ],
            }
        ],
    }


def test_toolbar_format_survives_html_share_and_word(monkeypatch):
    doc = document()
    shared = rich_copy(doc)
    assert shared["content"][0]["attrs"]["leftIndent"] == 0.5
    assert shared["content"][0]["content"][0]["marks"][1]["attrs"]["script"] == "super"
    markup = rich(shared)
    assert "margin-left:0.5cm" in markup
    assert "line-height:1.5" in markup
    assert "background-color:#fff2cc" in markup
    assert "vertical-align:super" in markup
    monkeypatch.setattr(
        "mach_backend.word_export.render_assets", lambda *_: {"math": {}, "figures": []}
    )
    exam = {
        "title": "Đề tự viết",
        "subject": "Sinh học",
        "grade": "9",
        "minutes": 45,
        "questions": [
            {
                "type": "essay",
                "stem": "Nội dung tự viết",
                "richDoc": doc,
                "points": 10,
                "options": [],
                "explanation": "",
                "rubric": [],
            }
        ],
    }
    with zipfile.ZipFile(io.BytesIO(export_docx(exam, False, None))) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    assert root.find(".//w:vertAlign[@w:val='superscript']", ns) is not None
    assert root.find(".//w:pBdr/w:top[@w:color='123456']", ns) is not None
    assert root.find(".//w:shd[@w:fill='fff2cc']", ns) is not None
    assert root.find(".//w:spacing[@w:after='180']", ns) is not None


@pytest.mark.parametrize(
    "attrs",
    [{"lineHeight": float("nan")}, {"leftIndent": 100}, {"borderColor": "red;position:fixed"}],
)
def test_invalid_paragraph_format_is_rejected(attrs):
    with pytest.raises(AIError):
        paragraph_layout(attrs)


def test_all_six_heading_levels_can_be_exported():
    for level in range(1, 7):
        markup = rich(
            {
                "type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": "Tiêu đề"}],
            }
        )
        assert markup.startswith(f"<h{level}")


def test_blank_document_text_is_kept_in_word_and_share(monkeypatch):
    from mach_backend.share_snapshot import snapshot

    monkeypatch.setattr(
        "mach_backend.word_export.render_assets", lambda *_: {"math": {}, "figures": []}
    )
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Nội dung trên trang trắng",
                        "marks": [{"type": "bold"}],
                    }
                ],
            }
        ],
    }
    exam = {
        "title": "Đề trắng",
        "questions": [],
        "bodyText": "Nội dung trên trang trắng",
        "bodyTextDoc": doc,
    }
    shared = snapshot(exam, False)
    assert shared["bodyText"] == exam["bodyText"]
    assert shared["bodyTextDoc"]["content"][0]["content"][0]["marks"] == [{"type": "bold"}]
    with zipfile.ZipFile(io.BytesIO(export_docx(exam, False, None))) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    assert "Nội dung trên trang trắng" in "".join(root.itertext())


def test_manual_page_break_survives_word_html_and_sharing(monkeypatch):
    from mach_backend.share_snapshot import snapshot

    monkeypatch.setattr(
        "mach_backend.word_export.render_assets", lambda *_: {"math": {}, "figures": []}
    )
    doc = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Trang một"}]},
            {
                "type": "paragraph",
                "attrs": {"pageBreakBefore": True},
                "content": [{"type": "text", "text": "Trang hai"}],
            },
            {"type": "paragraph", "attrs": {"pageBreakBefore": True}},
        ],
    }
    exam = {
        "title": "Đề ngắt trang",
        "questions": [],
        "bodyText": "Trang một\nTrang hai\n",
        "bodyTextDoc": doc,
    }
    shared = snapshot(exam, False)
    assert shared["bodyTextDoc"]["content"][1]["attrs"]["pageBreakBefore"] is True
    assert shared["bodyTextDoc"]["content"][2]["attrs"]["pageBreakBefore"] is True
    markup = rich(shared["bodyTextDoc"])
    assert markup.count("break-before:page") == 2
    assert "<br>" in markup
    with zipfile.ZipFile(io.BytesIO(export_docx(exam, False, None))) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    assert len(root.findall(".//w:pageBreakBefore", ns)) == 2
    assert "Trang một" in "".join(root.itertext())
    assert "Trang hai" in "".join(root.itertext())


@pytest.mark.parametrize("value", ["true", 1, {}, []])
def test_invalid_page_break_flag_is_rejected(value):
    with pytest.raises(AIError):
        rich_copy({"type": "paragraph", "attrs": {"pageBreakBefore": value}})
