"""Đọc bảng PDF có lớp chữ và cột rõ; chỉ nhận khi tổng câu/điểm khớp."""

import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, TypedDict

from pypdf import PdfReader

from mach_backend.ai_contract import AIError
from mach_backend.local_documents import pdf_pages
from mach_backend.matrix_import import checked_matrix, normalized


class PDFRow(TypedDict, total=False):
    topic: str
    type: str
    targets: list[int]
    pointsByLevelQ4: list[int | None]
    pointsByLevel: list[float | None]


_PLACEHOLDER_PATTERNS = (
    re.compile(r"[\ufffd\ue000-\uf8ff\u25a1\u25af]"),
    re.compile(r"(?:[=≠≤≥]\s{2,}(?:\(|$)|[=≠≤≥]\s*$)"),
    re.compile(r"\[\s*\]|\{\s*\}"),
)


def _has_math_placeholder(raw_label: str) -> bool:
    return any(pat.search(raw_label) for pat in _PLACEHOLDER_PATTERNS)


def _is_pdf_subheader_line(line: str) -> bool:
    norm = normalized(line)
    if not norm:
        return True
    if re.search(r"\d+\s*cau", norm):
        return False
    if re.search(r"\b(?:TL|TN|TNKQ|TLN|ĐS|DS)\b", line):
        return True
    tokens = set(norm.split())
    return bool(tokens) and tokens <= {
        "cao",
        "so",
        "cau",
        "diem",
        "muc",
        "do",
        "tt",
        "stt",
        "chu",
        "de",
        "noi",
        "dung",
        "kien",
        "thuc",
        "don",
        "vi",
        "loai",
        "ti",
        "le",
        "%",
    }


def _row_points_complete(row: PDFRow) -> bool:
    targets = row.get("targets", [])
    if not any(targets):
        return False
    q4 = row.get("pointsByLevelQ4", [])
    dec = row.get("pointsByLevel", [])
    for idx, n in enumerate(targets):
        if not n:
            continue
        has_q4 = idx < len(q4) and q4[idx] is not None
        has_dec = idx < len(dec) and dec[idx] is not None
        if not has_q4 and not has_dec:
            return False
    return True


def read_pdf_matrix(data):
    pages = pdf_pages(data)
    if len(pages) > 12:
        return None
    reader = PdfReader(io.BytesIO(data), strict=True)
    metadata: dict[str, Any] = {}
    total: list[int] | None = None
    active_starts: list[int] | None = None
    active_bounds: list[float] | None = None
    body_entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_placeholder_warning = False

    for page in reader.pages:
        layout = page.extract_text(extraction_mode="layout")
        if len(layout) > 40000:
            return None
        if re.search(r"II\s*\.\s*ĐẶC TẢ", layout, re.I):
            layout = re.split(r"II\s*\.\s*ĐẶC TẢ", layout, maxsplit=1, flags=re.I)[0]

        lines = layout.splitlines()
        header_idx = next(
            (i for i, line in enumerate(lines) if "Nhận biết" in line and "Thông hiểu" in line),
            None,
        )
        if header_idx is not None:
            header = lines[header_idx]
            levels = list(re.finditer(r"Nhận biết|Thông hiểu|Vận dụng(?:\s+cao)?", header))
            norm_header = normalized(header)
            if len(levels) not in (3, 4) or not any(
                k in norm_header for k in ("noi dung", "chu de", "don vi kien thuc")
            ):
                continue
            active_starts = [m.start() for m in levels]
            active_bounds = [
                (active_starts[i] + active_starts[i + 1]) / 2 for i in range(len(active_starts) - 1)
            ]
            scan_start = header_idx + 1
            while scan_start < len(lines) and scan_start <= header_idx + 2:
                if _is_pdf_subheader_line(lines[scan_start]):
                    scan_start += 1
                else:
                    break
        elif active_starts is not None and active_bounds is not None:
            scan_start = 0
        else:
            continue

        assert active_starts is not None and active_bounds is not None
        first_level_x = active_starts[0]
        last_level_x = active_starts[-1]

        for line in lines[scan_start:]:
            if not line.strip():
                continue
            counts = list(re.finditer(r"(\d+)\s+câu", line, re.I))
            points = list(re.finditer(r"\(([\d,.]+)\s*điểm\)", line, re.I))
            level_matches = [
                m.start() for m in (*counts, *points) if m.start() >= first_level_x - 8
            ]
            if level_matches:
                cutoff = min(level_matches)
            else:
                # Dòng chữ thuần (tiêu đề hoặc toán học xuống dòng): không cắt cột/công thức.
                trailing_pct = re.search(r"\s+\d+(?:[,.]\d+)?\s*%\s*$", line)
                if trailing_pct and trailing_pct.start() >= last_level_x:
                    cutoff = trailing_pct.start()
                else:
                    cutoff = len(line)
            raw_label = line[:cutoff]
            label = " ".join(raw_label.split())
            if not seen_placeholder_warning and _has_math_placeholder(raw_label):
                seen_placeholder_warning = True
                warnings.append(
                    {
                        "code": "pdf_math_font_placeholder",
                        "message": (
                            "Phát hiện ký hiệu hoặc khoảng trống công thức có thể bị thiếu do font "
                            "toán/vector trong PDF; hãy đối chiếu lại với bản gốc."
                        ),
                    }
                )
            body_entries.append(
                {
                    "label": label,
                    "raw_label": raw_label,
                    "line": line,
                    "counts": counts,
                    "points": points,
                    "bounds": active_bounds,
                    "first_level_x": first_level_x,
                    "level_count": len(active_starts),
                }
            )

    rows: list[PDFRow] = []
    pending: PDFRow | None = None
    pre_label_parts: list[str] = []

    for idx, entry in enumerate(body_entries):
        label = entry["label"]
        line = entry["line"]
        counts = entry["counts"]
        points = entry["points"]
        bounds = entry["bounds"]
        first_level_x = entry["first_level_x"]
        n_levels = entry["level_count"]

        if normalized(label) in {"tong", "tong cong", "tong so", "total"}:
            total_counts = list(re.finditer(r"(\d+)\s*[Cc]âu", line))
            if len(total_counts) not in {n_levels, n_levels + 1}:
                return None
            total = [int(m[1]) for m in total_counts]
            break

        if counts:
            if pending is not None:
                rows.append(pending)
            topic_parts = [*pre_label_parts, label]
            pre_label_parts = []
            topic = " ".join(p for p in topic_parts if p).strip()
            pending = {
                "topic": topic,
                "type": "essay",
                "targets": [0] * n_levels,
                "pointsByLevelQ4": [None] * n_levels,
            }
            for match in counts:
                level = sum(match.start() > bound for bound in bounds)
                if match.start() < first_level_x - 8 or pending["targets"][level]:
                    return None
                pending["targets"][level] = int(match[1])
        elif label and not label.startswith(("Tỉ lệ", "Mức độ")):
            if re.fullmatch(r"(?:Trang\s*)?\d+", label, re.I):
                continue
            if pending is None:
                pre_label_parts.append(label)
            elif not points and _row_points_complete(pending):
                next_count_entry = next(
                    (
                        e
                        for e in body_entries[idx + 1 :]
                        if e["counts"]
                        or normalized(e["label"]) in {"tong", "tong cong", "tong so", "total"}
                    ),
                    None,
                )
                starts_new = bool(re.match(r"^(?:Chủ đề|Chương|Bài|Phần|\d+[.)])\s", label, re.I))
                if next_count_entry is not None and (not next_count_entry["label"] or starts_new):
                    rows.append(pending)
                    pending = None
                    pre_label_parts.append(label)
                else:
                    pending["topic"] = (pending["topic"] + " " + label).strip()
            else:
                pending["topic"] = (pending["topic"] + " " + label).strip()

        for match in points:
            level = sum(match.start() > bound for bound in bounds)
            if pending is None or not pending["targets"][level]:
                return None
            try:
                total_cell = Decimal(match[1].replace(",", "."))
                per_q = total_cell / Decimal(pending["targets"][level])
                scaled_q4 = per_q * Decimal("4")
                scaled_p100 = per_q * Decimal("100")
            except (InvalidOperation, ZeroDivisionError):
                return None
            if scaled_q4 == scaled_q4.to_integral_value():
                if (
                    pending.get("pointsByLevel") is not None
                    or pending["pointsByLevelQ4"][level] is not None
                ):
                    return None
                pending["pointsByLevelQ4"][level] = int(scaled_q4)
            elif scaled_p100 == scaled_p100.to_integral_value() and Decimal(
                "0.05"
            ) <= per_q <= Decimal("10"):
                dec_list = pending.setdefault("pointsByLevel", [None] * n_levels)
                if dec_list[level] is not None:
                    return None
                dec_list[level] = float(per_q)
            else:
                return None

    if pending is not None:
        rows.append(pending)

    for row in rows:
        if "pointsByLevel" in row:
            q4_vals = row.pop("pointsByLevelQ4", [])
            dec_vals = row["pointsByLevel"]
            merged_dec: list[float | None] = []
            for q4_v, dec_v in zip(q4_vals, dec_vals, strict=True):
                if dec_v is not None:
                    merged_dec.append(dec_v)
                elif q4_v is not None:
                    merged_dec.append(q4_v / 4)
                else:
                    merged_dec.append(None)
            row["pointsByLevel"] = merged_dec

    if not total or not rows:
        return None
    n_levels = len(rows[0]["targets"])
    col_sums = [sum(r["targets"][i] for r in rows) for i in range(n_levels)]
    if col_sums != total[:n_levels]:
        return None
    if len(total) == n_levels + 1 and sum(total[:n_levels]) != total[n_levels]:
        return None

    for r in rows:
        if not r["topic"]:
            return None
        pts_list = r.get("pointsByLevel") or r.get("pointsByLevelQ4") or []
        if any(n and p is None for n, p in zip(r["targets"], pts_list, strict=True)):
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
    notes = (
        "Đọc bảng ma trận có lớp chữ tại máy; đối chiếu tên chủ đề/ký "
        "hiệu với PDF gốc. Không cộng lặp phần đặc tả. Tổng câu và điểm "
        "đã khớp."
    )
    if warnings:
        notes += " " + warnings[0]["message"]
    try:
        checked = checked_matrix({"matrix": rows, "notes": notes})
    except AIError:
        return None
    return {
        **checked,
        "metadata": metadata,
        **({"warnings": warnings} if warnings else {}),
    }
