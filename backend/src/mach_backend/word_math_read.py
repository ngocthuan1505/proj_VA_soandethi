"""Đọc phương trình OMML do exporter ghi, giữ cấu trúc khi dùng Word làm nguồn."""

import re

from mach_backend.ai_contract import AIError
from mach_backend.math_word import M

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def latex(node):
    kind = node.tag.rsplit("}", 1)[-1]

    def child(name):
        found = node.find(M + name)
        return latex(found) if found is not None else ""

    if kind.endswith("Pr") or kind in {"ctrlPr", "degHide", "sty", "chr"}:
        return ""
    if kind == "r":
        text = "".join(latex(c) for c in node if c.tag == M + "t")
        style = node.find(M + "rPr/" + M + "sty")
        script = node.find(M + "rPr/" + M + "scr")
        if script is not None:
            command = {
                "script": r"\mathcal",
                "fraktur": r"\mathfrak",
                "double-struck": r"\mathbb",
                "sans-serif": r"\mathsf",
                "monospace": r"\mathtt",
            }.get(script.get(M + "val"))
            if command:
                text = command + "{" + text + "}"
        if style is not None and style.get(M + "val") in {"b", "bi"}:
            return (
                (r"\mathbf" if style.get(M + "val") == "b" else r"\boldsymbol") + "{" + text + "}"
            )
        if style is not None and style.get(M + "val") == "p" and text.isascii() and text.isalpha():
            if text in {"sin", "cos", "tan", "cot", "log", "ln", "lim", "max", "min", "det"}:
                return "\\" + text + " "
            return r"\mathrm{" + text + "}"
        return text
    if kind == "t":
        text = node.text or ""
        if re.search(r"\s", text):
            return (
                r"\text{"
                + text.replace("\\", r"\backslash ").replace("{", r"\{").replace("}", r"\}")
                + "}"
            )
        return text.replace("%", r"\%")
    if kind == "f":
        num, den = child("num"), child("den")
        style = node.find(M + "fPr/" + M + "type")
        return (
            (
                r"\genfrac{}{}{0pt}{}"
                if style is not None and style.get(M + "val") == "noBar"
                else r"\frac"
            )
            + "{"
            + num
            + "}{"
            + den
            + "}"
        )
    if kind == "rad":
        degree = child("deg")
        return r"\sqrt" + ("[" + degree + "]" if degree else "") + "{" + child("e") + "}"
    if kind in {"sSup", "sSub", "sSubSup"}:
        return (
            "{"
            + child("e")
            + "}"
            + ("_{" + child("sub") + "}" if kind != "sSup" else "")
            + ("^{" + child("sup") + "}" if kind != "sSub" else "")
        )
    if kind == "m":
        rows = [
            " & ".join(latex(cell) for cell in row.findall(M + "e"))
            for row in node.findall(M + "mr")
        ]
        return r"\begin{matrix}" + r"\\".join(rows) + r"\end{matrix}"
    if kind == "d":
        left, right = node.find(M + "dPr/" + M + "begChr"), node.find(M + "dPr/" + M + "endChr")
        start = left.get(M + "val", "(") if left is not None else "("
        end = right.get(M + "val", ")") if right is not None else ")"
        value = child("e")
        if (
            start == "{"
            and not end
            and value.startswith(r"\begin{matrix}")
            and value.endswith(r"\end{matrix}")
        ):
            return (
                value.replace(r"\begin{matrix}", r"\begin{cases}", 1).removesuffix(r"\end{matrix}")
                + r"\end{cases}"
            )
        start, end = (
            (r"\{" if start == "{" else start or "."),
            (r"\}" if end == "}" else end or "."),
        )
        delimiters = {
            "∣": "|",
            "‖": r"\Vert",
            "∥": r"\Vert",
            "⟨": r"\langle",
            "⟩": r"\rangle",
            "⌊": r"\lfloor",
            "⌋": r"\rfloor",
            "⌈": r"\lceil",
            "⌉": r"\rceil",
        }
        start, end = delimiters.get(start, start), delimiters.get(end, end)
        return r"\left" + start + value + r"\right" + end
    if kind in {"limLow", "limUpp"}:
        return "{" + child("e") + "}" + ("_{" if kind == "limLow" else "^{") + child("lim") + "}"
    if kind == "acc":
        mark = node.find(M + "accPr/" + M + "chr")
        symbol = mark.get(M + "val", "ˆ") if mark is not None else "ˆ"
        command = {
            "→": r"\vec",
            "¯": r"\bar",
            "^": r"\hat",
            "ˆ": r"\hat",
            "˙": r"\dot",
            "¨": r"\ddot",
            "⏞": r"\overbrace",
        }.get(symbol)
        if command is None:
            raise AIError("unsupported_document", "Dấu công thức trong Word chưa đọc được.")
        return command + "{" + child("e") + "}"
    if kind == "borderBox":
        return r"\boxed{" + child("e") + "}"
    if kind == "groupChr":
        position = node.find(M + "groupChrPr/" + M + "pos")
        return (
            (
                r"\overbrace{"
                if position is not None and position.get(M + "val") == "top"
                else r"\underbrace{"
            )
            + child("e")
            + "}"
        )
    if kind in {"oMath", "oMathPara", "r", "e", "num", "den", "deg", "sub", "sup", "lim"}:
        return "".join(latex(c) for c in node)
    raise AIError("unsupported_document", "Cấu trúc công thức Word chưa hỗ trợ: " + kind)


def paragraph_text(node):
    if node.tag == M + "oMath":
        return "$" + latex(node) + "$"
    if node.tag in {W + "t", M + "t"}:
        return node.text or ""
    if node.tag == W + "br":
        return "\n"
    if node.tag == W + "tab":
        return "\t"
    return "".join(paragraph_text(c) for c in node)
