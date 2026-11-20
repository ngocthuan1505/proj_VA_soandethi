"""Bảng tự viết có cột mức/điểm; không đưa PDF người dùng vào fixture."""

from types import SimpleNamespace

import pytest

from mach_backend.matrix_import import matrix_slots
from mach_backend.pdf_matrix import read_pdf_matrix


def layout():
    def line(*cells):
        result = [" "] * 155
        for at, text in cells:
            result[at : at + len(text)] = text
        return "".join(result)

    lines = [
        line(
            (34, "Nội dung/Đơn vị kiến thức"),
            (74, "Nhận biết"),
            (90, "Thông hiểu"),
            (108, "Vận dụng"),
            (125, "Vận dụng"),
        ),
        line((74, "TL"), (90, "TL"), (108, "TL"), (125, "TL")),
    ]
    for label, col, count, points in [
        ("A", 77, 4, "2"),
        ("B", 94, 5, "5"),
        ("C", 111, 2, "1,5"),
        ("D", 128, 2, "1,5"),
    ]:
        lines += [line((30, label), (col, f"{count} câu")), line((col - 3, f"({points} điểm)"))]
    lines += [
        line(
            (30, "Tổng"),
            (77, "4 Câu"),
            (94, "5 Câu"),
            (111, "2 Câu"),
            (128, "2 Câu"),
            (144, "13 Câu"),
        )
    ]
    return "\n".join(lines)


def test_local_pdf_counts_and_per_level_points_without_ai(monkeypatch):
    monkeypatch.setattr(
        "mach_backend.pdf_matrix.pdf_pages", lambda _: [{"text": "Thời gian: 120 phút"}]
    )
    monkeypatch.setattr(
        "mach_backend.pdf_matrix.PdfReader",
        lambda *_a, **_kw: SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda **_kw: layout())]
        ),
    )
    result = read_pdf_matrix(b"fixture")
    assert result["count"] == 13 and result["metadata"]["minutes"] == 120
    slots = matrix_slots(result["matrix"])
    assert [sum(s.level == level for s in slots) for level in range(4)] == [4, 5, 2, 2]
    assert [sum(s.pointsQ4 for s in slots if s.level == level) for level in range(4)] == [
        8,
        20,
        6,
        6,
    ]
    assert all(s.type == "essay" for s in slots)


@pytest.mark.parametrize(
    "wrong",
    [
        lambda s: s.replace("13 Câu", "14 Câu"),
        lambda s: s.replace("(2 điểm)", "(1,9 điểm)"),
        lambda s: s.replace("(1,5 điểm)", ""),
    ],
)
def test_unclear_pdf_is_not_silently_accepted(monkeypatch, wrong):
    monkeypatch.setattr("mach_backend.pdf_matrix.pdf_pages", lambda _: [{"text": "Ma trận thử"}])
    monkeypatch.setattr(
        "mach_backend.pdf_matrix.PdfReader",
        lambda *_a, **_kw: SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda **_kw: wrong(layout()))]
        ),
    )
    assert read_pdf_matrix(b"fixture") is None
