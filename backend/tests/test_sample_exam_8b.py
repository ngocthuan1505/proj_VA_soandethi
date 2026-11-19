"""Kiểm hồi quy câu 8b của đề mẫu Toán lớp 5: tách cận trên diện tích và điều kiện xếp ô."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DE_DEMO = ROOT / "docs" / "testing" / "DE_DEMO_TOAN_5.md"
DAP_AN_DEMO = ROOT / "docs" / "testing" / "DAP_AN_DEMO_TOAN_5.md"


def test_cau_8b_de_va_dap_an_giu_can_tren_va_nhac_hinh_dang():
    prompt_text = DE_DEMO.read_text(encoding="utf-8")
    answer_text = DAP_AN_DEMO.read_text(encoding="utf-8")

    # Đề phải hỏi cận trên ("không thể vượt quá bao nhiêu?") với ô vuông cạnh 4 m và chu vi 160 m.
    assert "## Câu 8 · Tự luận · Vận dụng cao · 2 điểm" in prompt_text
    assert "chu vi là 160 m" in prompt_text
    assert "20% diện tích mảnh đất ban đầu" in prompt_text
    assert "ô vuông cạnh 4 m" in prompt_text
    assert "không thể vượt quá bao nhiêu?" in prompt_text

    # Đáp án phải giữ đúng phép tính 1500 - 300 = 1200 (m²), 1200 : 16 = 75 ô và lưu ý hình dạng.
    assert "1500 - 300 = 1200 (m²)" in answer_text
    assert "1200 : 16 = 75" in answer_text
    assert (
        "Muốn biết xếp thực tế được bao nhiêu ô cần biết hình dạng và cách bố trí phần đất còn lại."
        in answer_text
    )
    assert "không vượt quá 75 ô nếu chỉ xét diện tích" in answer_text

    # Kiểm chứng nhất quán toán học cho số đo trong đề mẫu.
    initial_area = 50 * 30
    house_area = initial_area * 20 // 100
    remaining = initial_area - house_area
    max_plots_by_area = remaining // (4 * 4)
    assert initial_area == 1500
    assert house_area == 300
    assert remaining == 1200
    assert max_plots_by_area == 75

    # Tổng điểm các tiêu đề câu trong đề mẫu phải đúng 10 điểm.
    points = [
        float(m.replace(",", "."))
        for m in re.findall(r"·\s*([0-9]+(?:[.,][0-9]+)?)\s*điểm", prompt_text)
    ]
    assert len(points) == 8
    assert sum(points) == 10.0
