"""Đọc bảng PDF có lớp chữ và cột rõ; chỉ nhận khi tổng câu/điểm khớp."""

import io
import re
from typing import TypedDict

from pypdf import PdfReader

from mach_backend.local_documents import pdf_pages
from mach_backend.matrix_import import checked_matrix, normalized


class PDFRow(TypedDict):
    topic: str
    type: str
    targets: list[int]
    pointsByLevelQ4: list[int | None]


def read_pdf_matrix(data):
    pages = pdf_pages(data)
    if len(pages) > 12:
        return None
    reader = PdfReader(io.BytesIO(data), strict=True)
    rows: list[PDFRow] = []
    pending: PDFRow | None = None
    metadata, total = {}, None
    for page in reader.pages:
        layout = page.extract_text(extraction_mode="layout")
        if len(layout) > 40000:
            return None
        if re.search(r"II\s*\.\s*ĐẶC TẢ", layout, re.I):
            layout = re.split(r"II\s*\.\s*ĐẶC TẢ", layout, maxsplit=1, flags=re.I)[0]
        header = next(
            (line for line in layout.splitlines() if "Nhận biết" in line and "Thông hiểu" in line),
            "",
        )
        levels = list(re.finditer(r"Nhận biết|Thông hiểu|Vận dụng", header))
        if len(levels) != 4 or "Nội dung" not in header:
            continue
        starts = [m.start() for m in levels]
        bounds = [(starts[i] + starts[i + 1]) / 2 for i in range(3)]
        left, right = header.index("Nội dung") - 4, starts[0] - 4
        body = False
        for line in layout.splitlines():
            if re.search(r"\bTL\s+TL\s+TL\s+TL\b", line):
                body = True
                continue
            if not body:
                continue
            label = " ".join(line[left:right].split())
            if normalized(label) == "tong":
                counts = list(re.finditer(r"(\d+)\s*[Cc]âu", line))
                if len(counts) != 5:
                    return None
                total = [int(m[1]) for m in counts]
                continue
            if total is not None:
                continue
            counts = list(re.finditer(r"(\d+)\s+câu", line, re.I))
            points = list(re.finditer(r"\(([\d,.]+)\s*điểm\)", line, re.I))
            if counts:
                if pending is not None:
                    rows.append(pending)
                pending = {
                    "topic": label,
                    "type": "essay",
                    "targets": [0] * 4,
                    "pointsByLevelQ4": [None] * 4,
                }
                for match in counts:
                    level = sum(match.start() > bound for bound in bounds)
                    if match.start() < right or pending["targets"][level]:
                        return None
                    pending["targets"][level] = int(match[1])
            elif label and pending is not None and not label.startswith(("Tỉ lệ", "Mức độ")):
                pending["topic"] += " " + label
            for match in points:
                level = sum(match.start() > bound for bound in bounds)
                if pending is None or not pending["targets"][level]:
                    return None
                value = float(match[1].replace(",", ".")) * 4 / pending["targets"][level]
                if not value.is_integer() or pending["pointsByLevelQ4"][level] is not None:
                    return None
                pending["pointsByLevelQ4"][level] = int(value)
    if pending is not None:
        rows.append(pending)
    if (
        not total
        or [sum(r["targets"][i] for r in rows) for i in range(4)] != total[:4]
        or sum(total[:4]) != total[4]
    ):
        return None
    if any(
        not r["topic"]
        or any(n and p is None for n, p in zip(r["targets"], r["pointsByLevelQ4"], strict=True))
        for r in rows
    ):
        return None
    text = "\n".join(p["text"] for p in pages)
    minutes = re.search(r"thoi gian.*?(\d+)\s*phut", normalized(text))
    if minutes:
        metadata["minutes"] = int(minutes[1])
    if re.search(r"TUYỂN SINH.*LỚP\s*10", text, re.I):
        metadata.update(
            subject="Toán" if "MÔN TOÁN" in text else "",
            grade="9",
            title="Đề thi tuyển sinh lớp 10",
        )
    return {
        **checked_matrix(
            {
                "matrix": rows,
                "notes": (
                    "Đọc bảng ma trận có lớp chữ tại máy; đối chiếu tên chủ đề/ký "
                    "hiệu với PDF gốc. Không cộng lặp phần đặc tả. Tổng câu và điểm "
                    "đã khớp."
                ),
            }
        ),
        "metadata": metadata,
    }
