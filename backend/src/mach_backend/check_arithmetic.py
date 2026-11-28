"""Kiểm trắc nghiệm bằng phép thay số cho dạng đề nhận diện được."""

import re
from fractions import Fraction
from operator import add, mul, sub, truediv

from mach_backend.ai_questions import BlindQuestion

_SIGNED_INT = r"[+\-−]?\s*[0-9]{1,9}"
FRAC_LATEX = rf"[+\-−]?\s*\\d?frac\{{\s*{_SIGNED_INT}\s*\}}\{{\s*{_SIGNED_INT}\s*\}}"
PLAIN_FRAC = r"[+\-−]?[0-9]{1,9}/[0-9]{1,9}"
PLAIN_DEC = r"[+\-−]?[0-9]{1,9}(?:[.,][0-9]{1,2})?"
NUMBER = rf"(?:{FRAC_LATEX}|{PLAIN_FRAC}|{PLAIN_DEC})"
_FRAC_MATCH = re.compile(
    rf"([+\-−]?)\s*\\d?frac\{{\s*({_SIGNED_INT})\s*\}}\{{\s*({_SIGNED_INT})\s*\}}"
)
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
    cleaned = text.strip().replace("−", "-")
    if m := _FRAC_MATCH.fullmatch(cleaned):
        sign = -1 if m.group(1).replace("−", "-") == "-" else 1
        num = int(m.group(2).replace("−", "-").replace(" ", ""))
        den = int(m.group(3).replace("−", "-").replace(" ", ""))
        return Fraction(sign * num, den)
    return Fraction(cleaned.replace(",", "."))


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
        try:
            options.append(number(option[1] or option[2]))
        except ZeroDivisionError:
            return None, "Phương án chứa phân số có mẫu bằng 0. Cần xem lại đề."

    try:
        value = number(stem[2])
        lhs, rhs = (value if operand == "x" else number(operand) for operand in (left, right))
        operation, display = OPERATORS[symbol]
        result = operation(lhs, rhs)
    except ZeroDivisionError:
        return None, "Thay giá trị x thì phép chia hoặc phân số có mẫu bằng 0. Cần xem lại đề."
    explanation = f"Thay x = {value}, tính ({lhs}) {display} ({rhs}) = {result}."
    matches = [index for index, option in enumerate(options) if option == result]
    if not matches:
        return None, explanation + " Không có phương án mang giá trị này."
    if len(matches) != 1:
        return None, explanation + " Có nhiều phương án mang cùng giá trị."
    return matches[0], explanation
