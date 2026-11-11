"""Kiểm trắc nghiệm bằng phép thay số cho dạng đề nhận diện được."""

import re
from fractions import Fraction
from operator import add, mul, sub, truediv

from mach_backend.ai_questions import BlindQuestion

NUMBER = r"[+\-−]?[0-9]{1,9}(?:[.,][0-9]{1,2})?"
OPERAND = rf"(?:x|{NUMBER})"
EXPRESSION = re.compile(
    rf"\s*({OPERAND})\s*(\+|-|−|\*|×|/|÷|\\times|\\cdot|\\div)\s*({OPERAND})\s*"
)
STEM = re.compile(rf"Tính\s+\$([^$]+)\$\s+khi\s+\$\s*x\s*=\s*({NUMBER})\s*\$\s*[.?]?\s*")
OPTION = re.compile(rf"(?:({NUMBER})|\$\s*({NUMBER})\s*\$)")
OPERATORS = {
    "+": (add, "+"),
    "-": (sub, "−"),
    "−": (sub, "−"),
    "*": (mul, "×"),
    "×": (mul, "×"),
    r"\times": (mul, "×"),
    r"\cdot": (mul, "×"),
    "/": (truediv, "÷"),
    "÷": (truediv, "÷"),
    r"\div": (truediv, "÷"),
}


def number(text: str) -> Fraction:
    return Fraction(text.replace("−", "-").replace(",", "."))


def check_substitution(question: BlindQuestion) -> tuple[int | None, str] | None:
    # shortcut: chỉ khớp toàn bộ mẫu một phép tính, mở rộng khi có bộ ca cho dạng mới.
    if question.type != "mcq" or not (stem := STEM.fullmatch(question.stem.strip())):
        return None
    if not (expression := EXPRESSION.fullmatch(stem[1])):
        return None
    left, symbol, right = expression.groups()
    if "x" not in (left, right):
        return None
    options = []
    for text in question.options:
        option = OPTION.fullmatch(text.strip())
        if option is None:
            return None
        options.append(number(option[1] or option[2]))

    value = number(stem[2])
    lhs, rhs = (value if operand == "x" else number(operand) for operand in (left, right))
    operation, display = OPERATORS[symbol]
    try:
        result = operation(lhs, rhs)
    except ZeroDivisionError:
        return None, f"Thay x = {value} thì mẫu phép chia bằng 0. Cần xem lại đề."
    explanation = f"Thay x = {value}, tính ({lhs}) {display} ({rhs}) = {result}."
    matches = [index for index, option in enumerate(options) if option == result]
    if not matches:
        return None, explanation + " Không có phương án mang giá trị này."
    if len(matches) != 1:
        return None, explanation + " Có nhiều phương án mang cùng giá trị."
    return matches[0], explanation
