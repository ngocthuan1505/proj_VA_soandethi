"""Xuất Word rich với ngữ liệu tự viết; fixture trình bày không dùng AI hoặc mạng."""

import base64
import io
import zipfile
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import exam_html, export_file
from mach_backend.math_word import M, omml
from mach_backend.rich_patch import project
from mach_backend.word_export import export_docx, image_bytes

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MATHML = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><mrow><mi>x</mi><mo>+</mo><mn>1</mn></mrow><mn>2</mn></mfrac></math>'


def data_image(fmt="PNG", color="green"):
    out = io.BytesIO()
    Image.new("RGB", (90, 60), color).save(out, format=fmt)
    return (
        "data:image/"
        + {"PNG": "png", "JPEG": "jpeg", "WEBP": "webp"}[fmt]
        + ";base64,"
        + base64.b64encode(out.getvalue()).decode()
    )


def p(text, marks=None):
    return {"type": "paragraph", "content": [{"type": "text", "text": text, "marks": marks or []}]}


def cell(text, colspan=1, rowspan=1):
    return {
        "type": "tableCell",
        "attrs": {"colspan": colspan, "rowspan": rowspan},
        "content": [p(text)],
    }


@pytest.fixture
def rich_exam():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "attrs": {"textAlign": "center"},
                "content": [
                    {
                        "type": "text",
                        "text": "CHỮ ĐẬM ",
                        "marks": [
                            {"type": "bold"},
                            {
                                "type": "textStyle",
                                "attrs": {"color": "#123456", "fontSize": "16pt"},
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": "chữ nghiêng",
                        "marks": [
                            {"type": "italic"},
                            {"type": "highlight", "attrs": {"color": "#ffff00"}},
                        ],
                    },
                    {"type": "hardBreak"},
                    {"type": "mathInline", "attrs": {"latex": r"\frac{x+1}{2}", "display": False}},
                ],
            },
            {
                "type": "table",
                "content": [
                    {"type": "tableRow", "content": [cell("Ô gộp ngang", 2), cell("Cột 3")]},
                    {
                        "type": "tableRow",
                        "content": [cell("Ô gộp dọc", rowspan=2), cell("A"), cell("B")],
                    },
                    {"type": "tableRow", "content": [cell("C"), cell("D")]},
                ],
            },
            {
                "type": "orderedList",
                "attrs": {"start": 3},
                "content": [{"type": "listItem", "content": [p("Mục thứ ba")]}],
            },
            {
                "type": "bulletList",
                "content": [{"type": "listItem", "content": [p("Gạch đầu dòng")]}],
            },
        ],
    }
    return {
        "title": "ĐỀ RICH TỰ VIẾT",
        "subject": "Toán",
        "grade": "9",
        "minutes": 45,
        "instructions": "Làm bài theo yêu cầu.",
        "questions": [
            {
                "type": "mcq",
                "stem": project(doc, []),
                "richDoc": doc,
                "points": 2.5,
                "options": ["Một", "Hai", "Ba", "Bốn"],
                "answer": 1,
                "optionDocs": [
                    None,
                    {"type": "doc", "content": [p("Hai", [{"type": "underline"}])]},
                ],
                "explanation": "ĐÁP_ÁN_KÍN $x^2$",
                "rubric": [{"text": "BAREM_KÍN", "points": 2.5}],
                "evidence": [{"quote": "NGUỒN_KIỂM_KÍN"}],
                "check": {"problems": ["CHECK_KÍN"]},
                "images": [{"data": data_image(), "caption": "Ảnh tự tạo"}],
            }
        ],
    }


@pytest.fixture
def renderer(monkeypatch):
    calls = []

    def render(math, figures, _chrome):
        calls.append((math, figures))
        return {"math": {latex: MATHML for latex in math}, "figures": []}

    monkeypatch.setattr("mach_backend.word_export.render_assets", render)
    return calls


def xml_from(binary):
    with zipfile.ZipFile(io.BytesIO(binary)) as z:
        assert z.testzip() is None
        return (
            ET.fromstring(z.read("word/document.xml")),
            z.namelist(),
            z.read("word/numbering.xml"),
        )


def test_rich_word_keeps_equations_marks_merge_lists_images_and_student_secrets(
    rich_exam, renderer
):
    before = deepcopy(rich_exam)
    binary = export_docx(rich_exam, False, None)
    root, files, numbers = xml_from(binary)
    text = "".join(root.itertext())
    assert all(
        secret not in text for secret in ("ĐÁP_ÁN_KÍN", "BAREM_KÍN", "NGUỒN_KIỂM_KÍN", "CHECK_KÍN")
    )
    assert rich_exam == before
    assert root.find(".//" + M + "f") is not None
    assert root.find(".//" + W + "b") is not None and root.find(".//" + W + "i") is not None
    assert root.find(".//" + W + "color").get(W + "val") == "123456"
    assert root.find(".//" + W + "shd").get(W + "fill") == "ffff00"
    assert root.find(".//" + W + "gridSpan").get(W + "val") == "2"
    assert root.find(".//" + W + "vMerge").get(W + "val") == "restart"
    assert root.find(".//" + W + "u") is not None
    assert b'w:val="3"' in numbers and b'numFmt w:val="bullet"' in numbers
    assert any(f.startswith("word/media/") for f in files)
    assert r"\frac" not in text and r"x^2" not in renderer[0][0]


def test_teacher_word_preserves_barem_and_explanation(rich_exam, renderer):
    root, _, _ = xml_from(export_docx(rich_exam, True, None))
    text = "".join(root.itertext())
    assert "ĐÁP_ÁN_KÍN" in text and "BAREM_KÍN" in text and "NGUỒN_KIỂM_KÍN" in text
    assert "Nội dung / lời giải" in text and "Điểm" in text and "2,5" in text
    assert "x^2" in renderer[0][0]
    assert len(root.findall(".//" + W + "tbl")) == 2


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_image_formats_become_valid_word_png(fmt):
    binary, w, h = image_bytes(data_image(fmt))
    assert binary.startswith(b"\x89PNG") and (w, h) == (90, 60)


@pytest.mark.parametrize(
    "data",
    [
        "https://example.test/private.png",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "data:image/png;base64,YmFk",
    ],
)
def test_invalid_image_is_not_fetched_or_silently_dropped(data):
    with pytest.raises(AIError, match="ảnh|Ảnh"):
        image_bytes(data)


def test_stale_rich_and_bad_table_leave_no_file(rich_exam, renderer, tmp_path):
    rich_exam["questions"][0]["stem"] += " ĐÃ ĐỔI"
    with pytest.raises(AIError, match="chưa khớp"):
        export_file(
            {"type": "exam", "exam": rich_exam, "format": "docx"}, tmp_path, "http://localhost"
        )
    assert list(tmp_path.iterdir()) == []
    rich_exam["questions"][0]["stem"] = project(rich_exam["questions"][0]["richDoc"], [])
    rich_exam["questions"][0]["richDoc"]["content"][1]["content"][0]["content"][0]["attrs"][
        "colspan"
    ] = 99
    rich_exam["questions"][0]["stem"] = project(rich_exam["questions"][0]["richDoc"], [])
    with pytest.raises(AIError, match="Ô gộp"):
        export_docx(rich_exam, False, None)


def test_rich_html_keeps_math_marks_merge_lists_and_never_inserts_teacher_secret(rich_exam):
    output = exam_html(rich_exam, False, "http://localhost")
    assert 'class="math"' in output and 'colspan="2"' in output and 'rowspan="2"' in output
    assert "color:#123456" in output and "background-color:#ffff00" in output
    assert 'start="3"' in output and "mhchem.mjs" in output
    assert "ĐÁP_ÁN_KÍN" not in output and "BAREM_KÍN" not in output


def test_omml_fraction_fence_matrix_and_vietnamese_text_are_editable_without_source():
    xml = ET.tostring(omml(MATHML), encoding="unicode")
    assert "<m:f>" in xml and "annotation" not in xml
    source = (
        '<math><mrow><mo fence="true">{</mo><mtable>'
        "<mtr><mtd><mn>1</mn></mtd></mtr></mtable></mrow></math>"
    )
    root = omml(source)
    assert root.find(".//" + M + "d") is not None and root.find(".//" + M + "m") is not None
    text = '<math><mover accent="true"><mtext>a</mtext><mo>ˆ</mo></mover></math>'
    assert "â" in "".join(omml(text).itertext())


@pytest.mark.parametrize("source", ["<!DOCTYPE math><math/>", "<math><unknown/></math>", "notxml"])
def test_bad_math_is_reported(source):
    with pytest.raises(AIError):
        omml(source)


def test_word_roundtrip_preserves_fraction_structure_as_latex(rich_exam, renderer):
    from mach_backend.local_documents import extract_text

    binary = export_docx(rich_exam, False, None)
    source = extract_text(
        "rich.docx", "data:application/octet-stream;base64," + base64.b64encode(binary).decode()
    )
    assert r"$\frac{x+1}{2}$" in source["pages"][0]["text"]
    assert "Ô gộp ngang" in source["pages"][0]["text"]


def test_numbering_declarations_precede_instances_for_word_compatibility(rich_exam, renderer):
    _, _, data = xml_from(export_docx(rich_exam, False, None))
    root = ET.fromstring(data)
    kinds = [n.tag for n in root]
    assert max(i for i, tag in enumerate(kinds) if tag == W + "abstractNum") < min(
        i for i, tag in enumerate(kinds) if tag == W + "num"
    )


def test_chemistry_subscript_has_real_base_in_word():
    source = (
        '<math><mi mathvariant="normal">H</mi><msub><mpadded>'
        "<mphantom><mi>X</mi></mphantom></mpadded><mn>2</mn></msub></math>"
    )
    root = omml(source)
    base = root.find(".//" + M + "sSub/" + M + "e/" + M + "r/" + M + "t")
    assert base.text == "H"
    assert "X" not in "".join(root.itertext())


def test_ooxml_shading_numbering_and_zoom_use_required_attributes_and_order(rich_exam, renderer):
    binary = export_docx(rich_exam, False, None)
    with zipfile.ZipFile(io.BytesIO(binary)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        settings = ET.fromstring(z.read("word/settings.xml"))
    assert root.find(".//" + W + "shd").get(W + "val") == "clear"
    assert settings.find(W + "zoom").get(W + "percent") == "100"
    for para in root.findall(".//" + W + "pPr"):
        tags = [n.tag for n in para]
        if W + "numPr" in tags and W + "ind" in tags:
            assert tags.index(W + "numPr") < tags.index(W + "ind")


def test_math_text_operators_keep_upright_style_on_roundtrip():
    from mach_backend.word_math_read import latex

    root = omml("<math><mi>sin</mi><mi>x</mi><mtext>m</mtext></math>")
    value = latex(root)
    assert r"\sin" in value and r"\mathrm{m}" in value


def test_word_determinant_delimiter_roundtrip_uses_valid_latex_bar():
    from mach_backend.word_math_read import latex

    source = (
        '<math><mrow><mo fence="true">∣</mo><mtable><mtr><mtd>'
        '<mi>a</mi></mtd></mtr></mtable><mo fence="true">∣</mo></mrow></math>'
    )
    result = latex(omml(source))
    assert result.startswith(r"\left|") and result.endswith(r"\right|")


def test_renderer_math_error_is_not_mislabeled_as_timeout(monkeypatch):
    from types import SimpleNamespace

    from mach_backend.export_assets import render_assets

    monkeypatch.setattr(
        "mach_backend.export_assets.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=b'<pre id="result">{"error":"fixture invalid formula"}</pre>'
        ),
    )
    with pytest.raises(AIError) as error:
        render_assets(["fixture"], [], "fixture-browser")
    assert error.value.code == "export_render_failed"
    assert "fixture invalid formula" in str(error.value)


def test_exam_rejects_unknown_format_before_render_or_creating_files(rich_exam, tmp_path):
    with pytest.raises(AIError, match="Word, PDF"):
        export_file(
            {"type": "exam", "exam": rich_exam, "format": "json"}, tmp_path, "http://localhost"
        )
    assert list(tmp_path.iterdir()) == []


def test_group_braces_and_mathematical_fonts_survive_word_roundtrip():
    from mach_backend.word_math_read import latex

    source = (
        "<math><munder><mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow>"
        '<mo>⏟</mo></munder><mi mathvariant="script">F</mi>'
        '<mi mathvariant="bold">v</mi></math>'
    )
    root = omml(source)
    assert root.find(".//" + M + "groupChr") is not None
    assert root.find(".//" + M + "scr").get(M + "val") == "script"
    result = latex(root)
    assert r"\underbrace{a+b}" in result and r"\mathcal{F}" in result and r"\mathbf{v}" in result


@pytest.mark.parametrize("fmt", ["html", "pdf"])
def test_bad_math_in_html_pdf_is_rejected_before_creating_file(
    rich_exam, tmp_path, monkeypatch, fmt
):
    calls = []

    def reject(math, figures, chrome):
        calls.append(math)
        raise AIError("export_render_failed", "Công thức chưa hợp lệ")

    monkeypatch.setattr("mach_backend.local_documents.render_assets", reject)
    with pytest.raises(AIError, match="Công thức"):
        export_file(
            {"type": "exam", "exam": rich_exam, "format": fmt}, tmp_path, "http://localhost"
        )
    assert r"\frac{x+1}{2}" in calls[0] and "x^2" not in calls[0]
    assert list(tmp_path.iterdir()) == []


def test_math_in_passage_instructions_and_table_is_rendered_in_html(rich_exam):
    rich_exam["quote"] = {"text": "Cho $x^2$"}
    rich_exam["instructions"] = "Tính $a+b$"
    rich_exam["questions"][0]["tables"] = [{"rows": [["$y^3$"]]}]
    output = exam_html(rich_exam, False, "http://localhost")
    assert '<span class="math">x^2</span>' in output
    assert '<span class="math">a+b</span>' in output
    assert '<span class="math">y^3</span>' in output


def test_linked_data_is_a_real_table_and_chart_in_word_and_html(rich_exam, monkeypatch):
    rich_exam["questions"][0]["dataLinked"] = True
    rich_exam["data"] = [{"label": "A", "value": 120}, {"label": "B", "value": 240}]
    svg = '<svg aria-label="Biểu đồ dữ kiện Bảng 1"></svg>'
    calls = []

    def render(math, figures, chrome):
        calls.append(figures)
        return {
            "math": {text: MATHML for text in math},
            "figures": [{"svg": svg, "png": data_image(color="red")}],
        }

    monkeypatch.setattr("mach_backend.word_export.render_assets", render)
    root, files, _ = xml_from(export_docx(rich_exam, False, None))
    assert "Bảng 1" in "".join(root.itertext()) and "240" in "".join(root.itertext())
    assert len(root.findall(".//" + W + "drawing")) == 2
    assert calls[0][0]["dataChart"] == rich_exam["data"]
    output = exam_html(rich_exam, False, "http://localhost", [{"svg": svg}])
    assert "linked-data" in output and "240" in output and svg in output


@pytest.mark.parametrize("value", [True, -1, float("nan"), 10**400])
def test_invalid_linked_data_does_not_reach_renderer(value):
    from mach_backend.word_export import data_chart

    with pytest.raises(AIError):
        data_chart({"data": [{"label": "A", "value": value}]})


@pytest.mark.parametrize(
    "kind,fields,label",
    [
        ("short", {"answerText": "DAP_AN_NGAN_42"}, "DAP_AN_NGAN_42"),
        (
            "truefalse",
            {"truthValues": [True, False, True, False]},
            "1. Đúng · 2. Sai · 3. Đúng · 4. Sai",
        ),
    ],
)
def test_mixed_answers_are_preserved_in_word_html_and_not_in_student_output(
    rich_exam, renderer, kind, fields, label
):
    q = rich_exam["questions"][0]
    q.update(type=kind, answer=0, answerKnown=True, **fields)
    q["options"] = q["options"] if kind == "truefalse" else []
    root, _, _ = xml_from(export_docx(rich_exam, True, None))
    assert label in "".join(root.itertext())
    assert label in exam_html(rich_exam, True, "http://localhost")
    root, _, _ = xml_from(export_docx(rich_exam, False, None))
    assert label not in "".join(root.itertext())
    assert label not in exam_html(rich_exam, False, "http://localhost")


def test_short_answer_formula_is_rendered_as_editable_math_only_in_teacher_copy(
    rich_exam, renderer
):
    from mach_backend.word_export import export_inputs

    q = rich_exam["questions"][0]
    q.update(type="short", answer=0, answerKnown=True, answerText=r"$\sqrt{49}$", options=[])
    assert r"\sqrt{49}" in export_inputs(rich_exam, True)[0]
    assert r"\sqrt{49}" not in export_inputs(rich_exam, False)[0]
    teacher, _, _ = xml_from(export_docx(rich_exam, True, None))
    student, _, _ = xml_from(export_docx(rich_exam, False, None))
    assert len(teacher.findall(".//" + M + "oMath")) > len(student.findall(".//" + M + "oMath"))
    assert r'<span class="math">\sqrt{49}</span>' in exam_html(rich_exam, True, "http://localhost")


def test_b4_default_15pt_chrome_page_numbers_watermark_codeblock_table_image_and_zero_leak(
    rich_exam, renderer
):
    # 1. Cỡ chữ mặc định phải là 15pt (30 half-points)
    with zipfile.ZipFile(io.BytesIO(export_docx(rich_exam, False, None))) as default_zf:
        styles_xml = ET.fromstring(default_zf.read("word/styles.xml"))
    normal_sz = styles_xml.find(f".//{W}style[@{W}styleId='Normal']//{W}sz")
    assert normal_sz is not None and normal_sz.get(W + "val") == "30"

    # 2. Header/Footer/Số trang PAGE-NUMPAGES/Watermark/codeBlock monospace/ảnh trong ô bảng
    exam = deepcopy(rich_exam)
    exam["layout"] = {
        "headerText": "ĐỀ THI THỬ TOÁN 10",
        "footerText": "Tổ Toán - Tin",
        "showPageNumbers": True,
        "watermarkText": "BẢN CHÍNH THỨC",
    }
    exam["questions"][0]["tables"] = [
        {"rows": [["STT", "Hình minh họa"], ["1", {"data": data_image("PNG", "blue")}]]}
    ]
    code_text = "def solve(x):\n    return x * 2"
    # Cập nhật stem theo codeBlock để project khớp tuyệt đối
    exam["questions"].append(
        {
            "id": "q-code",
            "v": 1,
            "type": "essay",
            "stem": code_text,
            "options": [],
            "answer": 0,
            "explanation": "LOI_GIAI_CODE_BI_MAT",
            "rubric": [{"text": "BAREM_CODE_BI_MAT", "points": 1.0}],
            "richDoc": {
                "type": "doc",
                "content": [
                    {
                        "type": "codeBlock",
                        "content": [{"type": "text", "text": code_text}],
                    }
                ],
            },
        }
    )

    student_bytes = export_docx(exam, False, None)
    with zipfile.ZipFile(io.BytesIO(student_bytes)) as zf:
        files = zf.namelist()
        doc_bytes = zf.read("word/document.xml")
        root = ET.fromstring(doc_bytes)
        doc_xml = doc_bytes.decode("utf-8")
        header_xml = zf.read("word/header1.xml").decode("utf-8")
        footer_xml = zf.read("word/footer1.xml").decode("utf-8")

    # Header, Watermark, Footer, PAGE/NUMPAGES
    assert "ĐỀ THI THỬ TOÁN 10" in header_xml
    assert "BẢN CHÍNH THỨC" in header_xml
    assert "Tổ Toán - Tin" in footer_xml
    assert "PAGE" in footer_xml and "NUMPAGES" in footer_xml

    # CodeBlock monospace + shading
    assert "Consolas" in doc_xml
    assert "def solve(x):" in doc_xml

    # Ảnh nằm thực sự bên trong ô bảng <w:tbl>...<w:tc>...<w:drawing>
    tbl_drawings = root.findall(f".//{W}tbl//{W}tc//{W}drawing")
    assert len(tbl_drawings) == 1
    assert any(name.startswith("word/media/") for name in files)

    # Bất biến 0 rò đáp án/lời giải trên toàn bộ XML bản học sinh
    all_xml_text = doc_xml + header_xml + footer_xml
    assert "LOI_GIAI_CODE_BI_MAT" not in all_xml_text
    assert "BAREM_CODE_BI_MAT" not in all_xml_text
    assert "Đáp án đúng" not in all_xml_text


def test_pdf_export_keeps_table_cell_images_and_separates_student_solutions(rich_exam, tmp_path):
    from pypdf import PdfReader

    from mach_backend.local_documents import chrome_path

    if not chrome_path():
        pytest.skip("Cần Chrome/Edge để chạy ca PDF thật")

    cell_img = data_image("PNG", "navy")
    doc_img = data_image("PNG", "purple")
    exam = deepcopy(rich_exam)
    exam["questions"][0]["tables"] = [
        {"rows": [["Cot_Bang_A", "Cot_Hinh_B"], ["Dong_1", {"data": cell_img, "caption": "Anh ô"}]]}
    ]
    exam["questions"][0]["explanation"] = "LOI_GIAI_PDF_BI_MAT_991"
    exam["questions"][0]["rubric"] = [{"text": "BAREM_PDF_BI_MAT_992", "points": 2.0}]
    exam["questions"].append(
        {
            "id": "q-rich-cell-img",
            "v": 1,
            "type": "essay",
            "stem": "O_Rich_Text | \nminh_hoa_code",
            "options": [],
            "answer": 0,
            "explanation": "LOI_GIAI_ESSAY_BI_MAT_993",
            "rubric": [{"text": "BAREM_ESSAY_BI_MAT_994", "points": 1.0}],
            "richDoc": {
                "type": "doc",
                "content": [
                    {
                        "type": "table",
                        "content": [
                            {
                                "type": "tableRow",
                                "content": [
                                    {
                                        "type": "tableCell",
                                        "content": [p("O_Rich_Text")],
                                    },
                                    {
                                        "type": "tableCell",
                                        "content": [{"type": "image", "attrs": {"src": doc_img}}],
                                    },
                                ],
                            }
                        ],
                    },
                    {"type": "codeBlock", "content": [{"type": "text", "text": "minh_hoa_code"}]},
                ],
            },
        }
    )

    student_html = exam_html(exam, False, "http://127.0.0.1")
    assert "<td><img " in student_html
    assert "{'data':" not in student_html
    assert '<pre class="code-block">' in student_html
    for secret in (
        "LOI_GIAI_PDF_BI_MAT_991",
        "BAREM_PDF_BI_MAT_992",
        "LOI_GIAI_ESSAY_BI_MAT_993",
        "BAREM_ESSAY_BI_MAT_994",
        "Hướng dẫn chấm",
        "Lời giải tham khảo",
    ):
        assert secret not in student_html

    pdf_res = export_file(
        {"type": "exam", "exam": exam, "format": "pdf", "teacher": False},
        tmp_path,
        "http://127.0.0.1",
    )
    reader = PdfReader(str(tmp_path / pdf_res["filename"]))
    pdf_images = sum(len(page.images) for page in reader.pages)
    pdf_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert pdf_images >= 2
    assert "Cot_Bang_A" in pdf_text and "O_Rich_Text" in pdf_text and "minh_hoa_code" in pdf_text
    assert "LOI_GIAI_PDF_BI_MAT_991" not in pdf_text
    assert "BAREM_ESSAY_BI_MAT_994" not in pdf_text
    assert "Lời giải tham khảo" not in pdf_text

    teacher_res = export_file(
        {"type": "exam", "exam": exam, "format": "pdf", "teacher": True},
        tmp_path,
        "http://127.0.0.1",
    )
    teacher_text = "\n".join(
        (page.extract_text() or "")
        for page in PdfReader(str(tmp_path / teacher_res["filename"])).pages
    )
    assert "LOI_GIAI_PDF_BI_MAT_991" in teacher_text
    assert "BAREM_ESSAY_BI_MAT_994" in teacher_text
