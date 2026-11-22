"""Kiểm thử xuất gói khóa đáp án & QR chuẩn chung (.xlsx sheet DapAn + QR PNG ISO-18004)."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient
from PIL import Image

from mach_backend.local_workspace import create_app
from mach_backend.tnmaker_export import _QR_SPECS, _format_bits, _gf_mul, encode_qr_png

S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _decode_qr_png_and_verify_ecc(png_bytes: bytes, box_size: int = 8, border: int = 4) -> str:
    """Giải mã bit QR từ ảnh PNG và kiểm tra toàn bộ syndrome Reed-Solomon == 0."""
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    size = img.width // box_size - 2 * border
    px = img.load()
    assert px is not None
    mat = [
        [
            px[(c + border) * box_size + box_size // 2, (r + border) * box_size + box_size // 2]
            < 128
            for c in range(size)
        ]
        for r in range(size)
    ]

    spec = next(s for s in _QR_SPECS if s[1] == size)
    version, _, aligns, n_blocks, block_data, block_ec = spec

    # Đọc Format Info trên cạnh trái-trên (tổng 15 bit) và chọn mask khớp BCH hợp lệ nhất
    raw_fmt = 0
    for i in range(15):
        if i < 6:
            bit = mat[8][i]
        elif i == 6:
            bit = mat[8][7]
        elif i == 7:
            bit = mat[8][8]
        elif i == 8:
            bit = mat[7][8]
        else:
            bit = mat[14 - i][8]
        raw_fmt = (raw_fmt << 1) | int(bit)

    mask_id = next(m for m in range(8) if _format_bits(m) == raw_fmt)

    fixed = [[False] * size for _ in range(size)]
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                if 0 <= r0 + dr < size and 0 <= c0 + dc < size:
                    fixed[r0 + dr][c0 + dc] = True
    for i in range(8, size - 8):
        fixed[6][i] = True
        fixed[i][6] = True
    for ar in aligns:
        for ac in aligns:
            if not fixed[ar][ac]:
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        fixed[ar + dr][ac + dc] = True
    fixed[size - 8][8] = True
    for i in range(9):
        fixed[8][i] = True
        fixed[i][8] = True
    for i in range(size - 8, size):
        fixed[8][i] = True
        fixed[i][8] = True
    if version >= 7:
        for i in range(6):
            for j in range(3):
                fixed[i][size - 11 + j] = True
                fixed[size - 11 + j][i] = True

    mask_fns = (
        lambda r, c: (r + c) % 2 == 0,
        lambda r, c: r % 2 == 0,
        lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0,
        lambda r, c: ((r // 2) + (c // 3)) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
        lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    )
    unmask = mask_fns[mask_id]

    bits: list[int] = []
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                if not fixed[r][col + dc]:
                    bits.append(int(mat[r][col + dc] ^ unmask(r, col + dc)))
        upward = not upward
        col -= 2

    total_cw = n_blocks * (block_data + block_ec)
    cws = [sum(bits[i * 8 + k] << (7 - k) for k in range(8)) for i in range(total_cw)]

    # Tái lập từng block data + ECC và kiểm tra toàn bộ RS syndrome == 0
    blocks = [[0] * block_data for _ in range(n_blocks)]
    ec_blocks = [[0] * block_ec for _ in range(n_blocks)]
    pos = 0
    for i in range(block_data):
        for b in range(n_blocks):
            blocks[b][i] = cws[pos]
            pos += 1
    for i in range(block_ec):
        for b in range(n_blocks):
            ec_blocks[b][i] = cws[pos]
            pos += 1

    from mach_backend.tnmaker_export import _GF_EXP

    for blk, ec in zip(blocks, ec_blocks, strict=True):
        poly = blk + ec
        for root_idx in range(block_ec):
            val = 0
            x = _GF_EXP[root_idx]
            for coef in poly:
                val = _gf_mul(val, x) ^ coef
            assert val == 0, f"RS syndrome khác 0 ở root {root_idx}"

    data_bits = [(cw >> s) & 1 for blk in blocks for cw in blk for s in range(7, -1, -1)]
    assert data_bits[:4] == [0, 1, 0, 0]
    length = sum(data_bits[4 + k] << (7 - k) for k in range(8))
    out_bytes = bytes(
        sum(data_bits[12 + i * 8 + k] << (7 - k) for k in range(8)) for i in range(length)
    )
    return out_bytes.decode("utf-8")


def test_qr_encoder_roundtrip_multiple_versions():
    for text in (
        "KEY|V1|101:ABCD",  # Version 1
        "KEY|V1|101:" + "ABCD" * 8 + "|102:" + "DCBA" * 8,  # Version 3
        "KEY|V1|101:" + "A" * 160,  # Version 7+ (>= 7 co version info bits)
    ):
        png = encode_qr_png(text)
        assert _decode_qr_png_and_verify_ecc(png) == text


def test_tnmaker_pack_endpoint_exports_valid_dapan_xlsx_qr_and_blocks_missing_key(tmp_path):
    exam = {
        "id": "ex-tnm-1",
        "title": "Đề Hóa 10",
        "questions": [
            {"id": "q1", "type": "mcq", "stem": "Q1", "options": ["1", "2", "3", "4"], "answer": 0},
            {"id": "q2", "type": "mcq", "stem": "Q2", "options": ["A", "B", "C", "D"], "answer": 2},
            {"id": "q3", "type": "essay", "stem": "Tự luận", "options": [], "answer": 0},
        ],
    }
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        ok = client.post(
            "/api/exports/tnmaker-pack",
            json={"exam": exam, "questionIds": ["q1", "q2"], "shuffleOptions": True},
        )
        assert ok.status_code == 200, ok.text
        data = ok.json()
        assert data["codes"] == ["101", "102"]
        assert data["label"] == "Gói khóa đáp án & QR chuẩn chung"
        assert data["formatId"] == "generic_answer_key_qr_v1"
        assert data["tnmakerVerified"] is False

        dl = client.get(data["url"])
        assert dl.status_code == 200
        with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
            assert set(zf.namelist()) == {"DapAn.xlsx", "QR_DapAn.png"}
            decoded_qr = _decode_qr_png_and_verify_ecc(zf.read("QR_DapAn.png"))
            assert decoded_qr == data["qrPayload"]
            assert "TNM" not in decoded_qr
            assert "?" not in decoded_qr and "101:DC|102:CC" == decoded_qr.removeprefix("KEY|V1|")

            with zipfile.ZipFile(io.BytesIO(zf.read("DapAn.xlsx"))) as xf:
                wb = xf.read("xl/workbook.xml").decode("utf-8")
                assert 'name="DapAn"' in wb
                sheet = ET.fromstring(xf.read("xl/worksheets/sheet1.xml"))
                cells = sheet.findall(f".//{S}c")
                assert all(c.get("t") == "inlineStr" for c in cells)
                texts = ["".join(c.itertext()) for c in cells]
                assert "101" in texts and "D" in texts and "C" in texts and "?" not in texts

        # Thiếu đáp án xác nhận -> 400 và tuyệt đối không tạo ? hoặc khẳng định tương thích TNMaker
        broken = {
            **exam,
            "questions": [
                *exam["questions"][:1],
                {
                    "id": "q2",
                    "type": "mcq",
                    "stem": "Chưa chốt",
                    "options": ["1", "2", "3", "4"],
                    "answer": 0,
                    "answerKnown": False,
                },
            ],
        }
        err = client.post("/api/exports/tnmaker-pack", json={"exam": broken})
        assert err.status_code == 400
        assert err.json()["code"] == "missing_answer_key"
        assert "Câu 2" in err.json()["error"]
        assert "TNMaker" not in err.json()["error"]
