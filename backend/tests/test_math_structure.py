"""Kiểm cấu trúc công thức, không dùng cặp dấu $ thay bằng chứng render."""

import json
from pathlib import Path

import pytest

from mach_backend.ai_contract import AIError, validate_ai_text

SHARED = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/ai-math-structure.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", SHARED, ids=lambda case: case["id"])
def test_node_and_python_share_math_structure_cases(case):
    text = "$" + case["latex"] + "$"
    if case["accepted"]:
        validate_ai_text(text)
    else:
        with pytest.raises(AIError) as error:
            validate_ai_text(text)
        assert error.value.code == "invalid_math"


@pytest.mark.parametrize(
    "formula",
    [
        r"\ce{2H2 + O2 ->[nhiệt] 2H2O}",
        r"\text{Giá \$5, ký hiệu \{ và \}} +x",
        r"\\{x}",
        r"\{x\}",
        "x % {chú thích\n+1",
    ],
)
def test_valid_nested_escaped_chemistry_and_literal_groups_are_preserved(formula):
    validate_ai_text("Lời giải $" + formula + "$.")


def test_plain_text_braces_are_not_treated_as_latex():
    validate_ai_text("Giữ văn bản {chưa khép, không phải công thức. Giá \\$5.")
