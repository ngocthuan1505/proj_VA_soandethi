"""Xuất gói khóa đáp án & QR chuẩn chung (.xlsx 1 sheet DapAn dạng chuỗi + QR PNG ISO 18004)."""

from __future__ import annotations

import io
import math
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape

from PIL import Image

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer

# Tham số ISO 18004 ECC mức L (Versions 1–9: tới 230 byte payload UTF-8)
# (version, size, align_centers, num_blocks, data_per_block, ec_per_block)
_QR_SPECS: tuple[tuple[int, int, tuple[int, ...], int, int, int], ...] = (
    (1, 21, (), 1, 19, 7),
    (2, 25, (6, 18), 1, 34, 10),
    (3, 29, (6, 22), 1, 55, 15),
    (4, 33, (6, 26), 1, 80, 20),
    (5, 37, (6, 30), 1, 108, 26),
    (6, 41, (6, 34), 2, 68, 18),
    (7, 45, (6, 22, 38), 2, 78, 20),
    (8, 49, (6, 24, 42), 2, 97, 24),
    (9, 53, (6, 26, 46), 2, 116, 30),
)

_GF_EXP = [1] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(1, 256):
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
    _GF_EXP[_i] = _GF_EXP[_i + 255] = _x
    _GF_LOG[_x] = _i


def _gf_mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_encode(data: Sequence[int], ec_len: int) -> list[int]:
    gen = [1]
    for i in range(ec_len):
        root = _GF_EXP[i]
        nxt = [0] * (len(gen) + 1)
        for j, coef in enumerate(gen):
            nxt[j] ^= coef
            nxt[j + 1] ^= _gf_mul(coef, root)
        gen = nxt
    rem = list(data) + [0] * ec_len
    for i in range(len(data)):
        coef = rem[i]
        if coef != 0:
            for j in range(len(gen)):
                rem[i + j] ^= _gf_mul(gen[j], coef)
    return rem[len(data) :]


def _format_bits(mask: int) -> int:
    # ECC L = 0b01 -> 5-bit data = (01 << 3) | mask
    data = (0b01 << 3) | mask
    rem = data << 10
    for shift in range(4, -1, -1):
        if rem & (1 << (shift + 10)):
            rem ^= 0b10100110111 << shift
    return ((data << 10) | rem) ^ 0b101010000010010


def _version_bits(version: int) -> int:
    rem = version << 12
    for shift in range(5, -1, -1):
        if rem & (1 << (shift + 12)):
            rem ^= 0b1111100100101 << shift
    return (version << 12) | rem


def _build_qr_matrix(payload: str) -> tuple[list[list[bool]], int]:
    raw = payload.encode("utf-8")
    spec = next((s for s in _QR_SPECS if len(raw) <= s[3] * s[4] - 2), None)
    if spec is None:
        raw = raw[: _QR_SPECS[-1][3] * _QR_SPECS[-1][4] - 2]
        spec = _QR_SPECS[-1]
    version, size, aligns, n_blocks, block_data, block_ec = spec

    bits: list[int] = [0, 1, 0, 0]  # Byte mode
    for shift in range(7, -1, -1):
        bits.append((len(raw) >> shift) & 1)
    for b in raw:
        for shift in range(7, -1, -1):
            bits.append((b >> shift) & 1)

    total_data_bytes = n_blocks * block_data
    max_bits = total_data_bytes * 8
    for _ in range(min(4, max_bits - len(bits))):
        bits.append(0)
    while len(bits) % 8:
        bits.append(0)
    codewords = [sum(bits[i + k] << (7 - k) for k in range(8)) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    pad_idx = 0
    while len(codewords) < total_data_bytes:
        codewords.append(pad[pad_idx])
        pad_idx ^= 1

    blocks = [codewords[b * block_data : (b + 1) * block_data] for b in range(n_blocks)]
    ec_blocks = [_rs_encode(blk, block_ec) for blk in blocks]
    stream: list[int] = []
    for i in range(block_data):
        for blk in blocks:
            stream.append(blk[i])
    for i in range(block_ec):
        for ec in ec_blocks:
            stream.append(ec[i])

    stream_bits = [(cw >> shift) & 1 for cw in stream for shift in range(7, -1, -1)]
    grid: list[list[bool | None]] = [[None] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put_fixed(r: int, c: int, val: bool) -> None:
        grid[r][c] = val
        fixed[r][c] = True

    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r0 + dr, c0 + dc
                if 0 <= rr < size and 0 <= cc < size:
                    inside = (
                        0 <= dr <= 6
                        and 0 <= dc <= 6
                        and (dr in {0, 6} or dc in {0, 6} or (2 <= dr <= 4 and 2 <= dc <= 4))
                    )
                    put_fixed(rr, cc, inside)

    for i in range(8, size - 8):
        put_fixed(6, i, i % 2 == 0)
        put_fixed(i, 6, i % 2 == 0)

    for ar in aligns:
        for ac in aligns:
            if fixed[ar][ac]:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put_fixed(ar + dr, ac + dc, max(abs(dr), abs(dc)) in {0, 2})

    put_fixed(size - 8, 8, True)
    for i in range(9):
        if not fixed[8][i]:
            put_fixed(8, i, False)
        if not fixed[i][8]:
            put_fixed(i, 8, False)
    for i in range(size - 8, size):
        put_fixed(8, i, False)
        if not fixed[i][8]:
            put_fixed(i, 8, False)

    if version >= 7:
        v_bits = _version_bits(version)
        for i in range(18):
            bit = bool((v_bits >> i) & 1)
            r, c = i // 3, size - 11 + (i % 3)
            put_fixed(r, c, bit)
            put_fixed(c, r, bit)

    coords: list[tuple[int, int]] = []
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                if not fixed[r][col + dc]:
                    coords.append((r, col + dc))
        upward = not upward
        col -= 2

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

    def apply_mask(mask_id: int) -> list[list[bool]]:
        fn = mask_fns[mask_id]
        mat = [[bool(grid[r][c]) for c in range(size)] for r in range(size)]
        for idx, (r, c) in enumerate(coords):
            raw_bit = bool(stream_bits[idx]) if idx < len(stream_bits) else False
            mat[r][c] = raw_bit ^ fn(r, c)
        fb = _format_bits(mask_id)
        for i in range(15):
            bit = bool((fb >> (14 - i)) & 1)
            # ngang quanh top-left/top-right
            if i < 6:
                mat[8][i] = bit
            elif i == 6:
                mat[8][7] = bit
            elif i == 7:
                mat[8][8] = bit
            elif i == 8:
                mat[7][8] = bit
            else:
                mat[14 - i][8] = bit
            # dọc ở bottom-left & top-right
            if i < 7:
                mat[size - 1 - i][8] = bit
            else:
                mat[8][size - 15 + i] = bit
        return mat

    def penalty(mat: list[list[bool]]) -> int:
        score = 0
        for row in mat:
            run = 1
            for k in range(1, size):
                run = run + 1 if row[k] == row[k - 1] else 1
                if run == 5:
                    score += 3
                elif run > 5:
                    score += 1
        for c in range(size):
            run = 1
            for r in range(1, size):
                run = run + 1 if mat[r][c] == mat[r - 1][c] else 1
                if run == 5:
                    score += 3
                elif run > 5:
                    score += 1
        dark = sum(1 for row in mat for v in row if v)
        score += abs((dark * 100) // (size * size) - 50) // 5 * 10
        return score

    best_mat = min((apply_mask(mid) for mid in range(8)), key=penalty)
    return best_mat, size


def encode_qr_png(payload: str, *, box_size: int = 8, border: int = 4) -> bytes:
    """Sinh ảnh PNG mã QR chuẩn ISO 18004 (ECC L) thuần Python + PIL."""
    mat, size = _build_qr_matrix(payload)
    dim = (size + 2 * border) * box_size
    img = Image.new("L", (dim, dim), 255)
    px = img.load()
    assert px is not None
    for r, row in enumerate(mat):
        for c, dark in enumerate(row):
            if not dark:
                continue
            y0, x0 = (r + border) * box_size, (c + border) * box_size
            for dy in range(box_size):
                for dx in range(box_size):
                    px[x0 + dx, y0 + dy] = 0
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _col_ref(col_idx: int, row_idx: int) -> str:
    label = ""
    n = col_idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(65 + rem) + label
    return f"{label}{row_idx}"


_INVALID_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_INVALID_SHEET_CHARS = re.compile(r"[\\/?*\[\]:]")


def _clean_xml_text(text: str) -> str:
    return _INVALID_XML_CHARS.sub("", text)


def _sanitize_sheet_names(raw_names: Sequence[str]) -> list[str]:
    used: set[str] = set()
    cleaned: list[str] = []
    for idx, raw in enumerate(raw_names, 1):
        base = _INVALID_SHEET_CHARS.sub("_", _clean_xml_text(str(raw or ""))).strip(" '")
        if not base:
            base = f"Sheet{idx}"
        candidate = base[:31]
        if candidate.casefold() in used:
            suffix = f"_{idx}"
            candidate = f"{base[: 31 - len(suffix)]}{suffix}"
        counter = 2
        while candidate.casefold() in used:
            suffix = f"_{counter}"
            candidate = f"{base[: 31 - len(suffix)]}{suffix}"
            counter += 1
        used.add(candidate.casefold())
        cleaned.append(candidate)
    return cleaned


def _xlsx_cell_xml(col_idx: int, row_idx: int, val: Any) -> str:
    if val is None:
        return ""
    ref = _col_ref(col_idx, row_idx)
    if isinstance(val, bool):
        return f'<c r="{ref}" t="b"><v>{1 if val else 0}</v></c>'
    if isinstance(val, (int, float)):
        if math.isfinite(val):
            return f'<c r="{ref}"><v>{val}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t></t></is></c>'
    escaped = xml_escape(_clean_xml_text(str(val)))
    return f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def build_xlsx_workbook(sheets: Sequence[tuple[str, Sequence[Sequence[Any]]]]) -> bytes:
    """Tạo file OOXML .xlsx thuần Python hỗ trợ nhiều sheet, chuỗi inlineStr và ô số."""
    if not sheets:
        raise ValueError("Cần ít nhất một trang tính (sheet) để tạo workbook XLSX.")
    sheet_names = _sanitize_sheet_names([name for name, _ in sheets])
    sheet_xml_map: dict[str, str] = {}
    sheet_tags: list[str] = []
    wb_rels: list[str] = []
    ct_overrides: list[str] = []

    for idx, (sheet_name, rows) in enumerate(
        zip(sheet_names, [r for _, r in sheets], strict=True), 1
    ):
        sheet_rows: list[str] = []
        for r_idx, row in enumerate(rows, 1):
            cells = "".join(_xlsx_cell_xml(c_idx, r_idx, val) for c_idx, val in enumerate(row))
            sheet_rows.append(f'<row r="{r_idx}">{cells}</row>')
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(sheet_rows)}</sheetData>"
            "</worksheet>"
        )
        part_path = f"xl/worksheets/sheet{idx}.xml"
        sheet_xml_map[part_path] = sheet_xml
        sheet_tags.append(
            f'<sheet name="{xml_escape(sheet_name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        )
        wb_rels.append(
            f'<Relationship Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{idx}.xml"/>'
        )
        ct_overrides.append(
            f'<Override PartName="/{part_path}" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(sheet_tags)}</sheets>"
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(wb_rels)}"
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{''.join(ct_overrides)}"
        "</Types>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for part_path, xml_text in sheet_xml_map.items():
            zf.writestr(part_path, xml_text)
    return buf.getvalue()


def _build_dapan_xlsx(rows: list[list[str]]) -> bytes:
    """Tạo file XLSX 1 sheet tên 'DapAn', toàn bộ ô kiểu chuỗi inlineStr (không ép ngày)."""
    return build_xlsx_workbook([("DapAn", rows)])


def _mcq_keys_for_exam(exam_obj: dict[str, Any]) -> list[tuple[int, str]]:
    keys: list[tuple[int, str]] = []
    missing: list[int] = []
    for idx, q in enumerate(exam_obj.get("questions") or [], 1):
        if q.get("type", "mcq") != "mcq":
            continue
        if q.get("answerKnown") is False:
            missing.append(idx)
            continue
        ans = saved_answer(q)
        options = q.get("options") or []
        if type(ans) is not int or not 0 <= ans < len(options) or ans >= 26:
            missing.append(idx)
            continue
        if not isinstance(options[ans], str) or not options[ans].strip():
            raise AIError(
                "empty_selected_option",
                f"Câu {idx} đang chọn đáp án {chr(65 + ans)} nhưng phương án bị trống.",
                http_status=400,
            )
        keys.append((idx, chr(65 + ans)))
    if missing:
        raise AIError(
            "missing_answer_key",
            f"Câu {', '.join(map(str, missing))} chưa xác nhận đáp án đúng; "
            "cần chốt đáp án trước khi xuất gói khóa đáp án & QR (không xuất dấu ?).",
            http_status=400,
        )
    if not keys:
        raise AIError(
            "missing_answer_key",
            "Đề chưa có câu trắc nghiệm có đáp án để tạo gói khóa đáp án & QR.",
            http_status=400,
        )
    return keys


def export_tnmaker_pack(payload: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Xuất gói .zip gồm DapAn.xlsx (1 sheet DapAn) + QR PNG chuẩn chung; chặn nếu thiếu đáp án."""
    from mach_backend.local_documents import _plan_variant_units, exam_variant

    exam = payload.get("exam")
    if not isinstance(exam, dict) or not isinstance(exam.get("questions"), list):
        raise AIError("invalid_exam", "Đề cần danh sách câu hỏi hợp lệ.")

    ids = payload.get("questionIds")
    shuffle_options = bool(payload.get("shuffleOptions", False))
    variant_pairs: list[tuple[str, dict[str, Any]]]
    if isinstance(ids, list) and len(ids) >= 2:
        plan = _plan_variant_units(exam["questions"], ids)
        count = min(6, len(plan["units"]))
        variant_pairs = [
            (
                str(101 + offset),
                exam_variant(
                    exam, {"questionIds": ids, "shuffleOptions": shuffle_options, "offset": offset}
                ),
            )
            for offset in range(count)
        ]
    else:
        variant_pairs = [("101", exam)]

    excel_rows: list[list[str]] = [["MaDe", "Cau", "DapAn"]]
    keys_per_variant: list[tuple[str, list[tuple[int, str]]]] = []
    for code, var_exam in variant_pairs:
        keys = _mcq_keys_for_exam(var_exam)
        keys_per_variant.append((code, keys))
        for q_num, letter in keys:
            excel_rows.append([code, str(q_num), letter])

    is_contiguous = all(
        [q_num for q_num, _ in keys] == list(range(1, len(keys) + 1))
        for _, keys in keys_per_variant
    )
    if is_contiguous:
        qr_format = "V1_contiguous"
        qr_chunks = [
            f"{code}:{''.join(letter for _, letter in keys)}" for code, keys in keys_per_variant
        ]
        qr_payload = "KEY|V1|" + "|".join(qr_chunks)
    else:
        qr_format = "V2_indexed"
        qr_chunks = [
            f"{code}:{','.join(f'{q_num}{letter}' for q_num, letter in keys)}"
            for code, keys in keys_per_variant
        ]
        qr_payload = "KEY|V2|" + "|".join(qr_chunks)

    xlsx_bytes = _build_dapan_xlsx(excel_rows)
    qr_png = encode_qr_png(qr_payload)

    directory.mkdir(parents=True, exist_ok=True)
    name = "De_thi_" + str(uuid4()) + ".zip"
    target = directory / name
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("DapAn.xlsx", xlsx_bytes)
        archive.writestr("QR_DapAn.png", qr_png)
    return {
        "filename": name,
        "bytes": target.stat().st_size,
        "url": "/api/exports/" + name,
        "codes": [c for c, _ in variant_pairs],
        "qrPayload": qr_payload,
        "qrFormat": qr_format,
        "label": "Gói khóa đáp án & QR chuẩn chung",
        "formatId": "generic_answer_key_qr_v1",
        "tnmakerVerified": False,
        "note": (
            "Gói gồm DapAn.xlsx (cột MaDe, Cau, DapAn) và mã QR chuẩn chung; "
            "chưa xác minh tương thích trực tiếp với ứng dụng chấm thi bên thứ ba."
        ),
    }
