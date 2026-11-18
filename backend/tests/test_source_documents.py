"""Nguồn tự tạo: PDF có chữ/scan/mật khẩu; nhận dạng dùng fixture, không gọi AI."""

import asyncio
import base64
import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import extract_text
from mach_backend.local_workspace import create_app
from mach_backend.source_ocr import read_source


def data_url(data, mime="application/pdf"):
    return "data:" + mime + ";base64," + base64.b64encode(data).decode()


def pdf(*texts, password=None):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=600, height=800)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        elif text is None:
            image = DecodedStreamObject()
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(8),
                    NameObject("/Height"): NumberObject(8),
                    NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                    NameObject("/BitsPerComponent"): NumberObject(1),
                }
            )
            # Chữ số 2 dưới dạng bitmap 8×8, mỗi byte là một hàng ảnh.
            image.set_data(bytes.fromhex("ff c3 bd fd f3 cf 81 ff"))
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject("/Scan"): writer._add_object(image)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(b"q 96 0 0 96 50 600 cm /Scan Do Q")
            page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def mixed_pdf():
    return pdf("Page one", None, "Page three")


def test_mixed_pdf_local_preserves_text_and_marks_only_scan_for_ocr(mixed_pdf):
    result = extract_text("mixed.pdf", data_url(mixed_pdf))

    assert result["sentToAI"] is False
    assert result["pages"] == [
        {"number": 1, "text": "Page one", "needsOCR": False},
        {"number": 2, "text": "", "needsOCR": True},
        {"number": 3, "text": "Page three", "needsOCR": False},
    ]


def test_mixed_pdf_ocr_preserves_original_page_order(mixed_pdf):
    expected_pages = [(1, "Page one"), (2, "2"), (3, "Page three")]

    async def model(purpose, body):
        assert purpose == "source_ocr"
        assert body["document"]["mimeType"] == "application/pdf"
        assert base64.b64decode(body["document"]["data"]) == mixed_pdf
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {"number": number, "text": text, "uncertain": False}
                        for number, text in expected_pages
                    ],
                    "notes": "",
                }
            )
        }

    result = asyncio.run(
        read_source({"name": "mixed.pdf", "consent": True}, data_url(mixed_pdf), model)
    )

    assert [(page["number"], page["text"]) for page in result["pages"]] == expected_pages


def test_pdf_text_local_preserves_pages_without_ai():
    result = extract_text("source.pdf", data_url(pdf("Page one", "Page two")))
    assert result["method"] == "pypdf_local_text" and result["sentToAI"] is False
    assert [p["number"] for p in result["pages"]] == [1, 2]
    assert "Page one" in result["pages"][0]["text"] and "Page two" in result["pages"][1]["text"]


@pytest.mark.parametrize(
    "binary,code",
    [
        (b"not a pdf", "invalid_document"),
        (pdf("", password="secret"), "encrypted_document"),
        (pdf(*[""] * 101), "document_limit"),
        (pdf(""), "document_ai_consent"),
    ],
)
def test_bad_encrypted_oversized_scan_pdf_never_silently_succeeds(binary, code):
    with pytest.raises(AIError) as e:
        extract_text("test.pdf", data_url(binary))
    assert e.value.code == code


@pytest.mark.parametrize(
    "name,content", [("scan.pdf", pdf("")), ("scan.png", b"\x89PNG\r\n\x1a\nfixture")]
)
def test_ocr_consent_preview_and_original_page_are_preserved(tmp_path, name, content):
    calls = []

    async def model(purpose, body):
        calls.append((purpose, body))
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {
                            "number": 1,
                            "text": "Nguồn tự viết [không rõ] cần đối chiếu.",
                            "uncertain": True,
                        }
                    ],
                    "notes": "Đối chiếu chữ mờ.",
                }
            )
        }

    with TestClient(
        create_app(tmp_path, agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        client.put(
            "/api/kv", json={"key": "file:sample", "value": data_url(content)}
        ).raise_for_status()
        request = {"fileId": "sample", "name": name}
        result = client.post("/api/extract", json=request)
        assert (
            result.status_code == 409
            and result.json()["code"] == "document_ai_consent"
            and not calls
        )
        result = client.post("/api/extract", json={**request, "consent": True})
        assert result.status_code == 200, result.text
        assert result.json()["needsReview"] and result.json()["sentToAI"]
        assert result.json()["pages"][0]["uncertain"] and result.json()["pages"][0]["number"] == 1
        assert len(calls) == 1 and calls[0][0] == "source_ocr"
        assert client.get("/api/kv?key=state").json()["value"] is None
        if name.endswith("pdf"):
            original = client.get("/api/source-file/sample")
            assert (
                original.content == content
                and original.headers["content-type"] == "application/pdf"
            )


@pytest.mark.parametrize("numbers", [[1, 1], [2], [1, 3]])
def test_ocr_cannot_drop_or_invent_page_numbers(tmp_path, numbers):
    async def model(*_):
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {"number": n, "text": "Nguồn thử", "uncertain": False} for n in numbers
                    ],
                    "notes": "",
                }
            )
        }

    with TestClient(
        create_app(tmp_path, agent_call=model), headers={"Origin": "http://testserver"}
    ) as client:
        client.put("/api/kv", json={"key": "file:sample", "value": data_url(pdf("", ""))})
        result = client.post(
            "/api/extract", json={"fileId": "sample", "name": "scan.pdf", "consent": True}
        )
        assert result.status_code == 409 and result.json()["code"] == "invalid_document_reading"


def test_ocr_rejects_large_pdf_before_ai(tmp_path):
    async def forbidden(*_):
        pytest.fail("Không được gửi PDF quá20trang tớiAI")

    with TestClient(
        create_app(tmp_path, agent_call=forbidden), headers={"Origin": "http://testserver"}
    ) as client:
        client.put("/api/kv", json={"key": "file:sample", "value": data_url(pdf(*[""] * 21))})
        result = client.post(
            "/api/extract", json={"fileId": "sample", "name": "scan.pdf", "consent": True}
        )
        assert result.status_code == 409 and result.json()["code"] == "document_limit"
