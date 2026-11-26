"""Kiểm tra đáp án & barem 0,25 điểm, lập Ma trận & Đặc tả, xuất HTML A4 và DOCX chuẩn."""

from __future__ import annotations

import html
import io
import math
import re
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, NoReturn
from xml.etree import ElementTree as ET

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import QuestionType, saved_answer_label
from mach_backend.math_word import omml
from mach_backend.ocr_structured import structure_ocr_reading
from mach_backend.word_export import math_parts


def format_points_vi(value: int | float | None) -> str:
    """Định dạng điểm số tiếng Việt chuẩn 2 chữ số thập phân (ví dụ: 0,40 điểm; 10,00 điểm)."""
    if value is None:
        return ""
    return f"{float(value):.2f}".replace(".", ",") + " điểm"


MATHML_NS = "http://www.w3.org/1998/Math/MathML"
LEVEL_NAMES: tuple[str, str, str, str] = (
    "Nhận biết",
    "Thông hiểu",
    "Vận dụng",
    "Vận dụng cao",
)
LEVEL_ALIASES: dict[str, int] = {
    "0": 0,
    "nhận biết": 0,
    "nhan biet": 0,
    "nb": 0,
    "remember": 0,
    "1": 1,
    "thông hiểu": 1,
    "thong hieu": 1,
    "th": 1,
    "understand": 1,
    "2": 2,
    "vận dụng": 2,
    "van dung": 2,
    "vd": 2,
    "apply": 2,
    "3": 3,
    "vận dụng cao": 3,
    "van dung cao": 3,
    "vdc": 3,
    "analyze": 3,
    "evaluate": 3,
    "create": 3,
}
TYPE_ALIASES: dict[str, QuestionType] = {
    "mcq": "mcq",
    "multiple_choice": "mcq",
    "trắc nghiệm": "mcq",
    "trac nghiem": "mcq",
    "nhiều lựa chọn": "mcq",
    "nhieu lua chon": "mcq",
    "truefalse": "truefalse",
    "true_false": "truefalse",
    "đúng/sai": "truefalse",
    "đúng - sai": "truefalse",
    "dung sai": "truefalse",
    "dung/sai": "truefalse",
    "short": "short",
    "short_answer": "short",
    "trả lời ngắn": "short",
    "tra loi ngan": "short",
    "essay": "essay",
    "tự luận": "essay",
    "tu luan": "essay",
}
TYPE_LABELS: dict[QuestionType, str] = {
    "mcq": "Trắc nghiệm (A/B/C/D)",
    "truefalse": "Đúng / Sai",
    "short": "Trả lời ngắn",
    "essay": "Tự luận",
}
LATEX_SYMBOLS: dict[str, str] = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "vartheta": "ϑ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "varphi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
    "pm": "±",
    "mp": "∓",
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "ast": "∗",
    "star": "⋆",
    "circ": "∘",
    "degree": "°",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "ne": "≠",
    "neq": "≠",
    "approx": "≈",
    "equiv": "≡",
    "sim": "∼",
    "cong": "≅",
    "propto": "∝",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "supset": "⊃",
    "supseteq": "⊇",
    "cup": "∪",
    "cap": "∩",
    "setminus": "∖",
    "emptyset": "∅",
    "varnothing": "∅",
    "forall": "∀",
    "exists": "∃",
    "neg": "¬",
    "land": "∧",
    "lor": "∨",
    "infty": "∞",
    "partial": "∂",
    "nabla": "∇",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "leftrightarrow": "↔",
    "Rightarrow": "⇒",
    "Leftarrow": "⇐",
    "Leftrightarrow": "⇔",
    "implies": "⇒",
    "iff": "⇔",
    "mapsto": "↦",
    "sum": "∑",
    "prod": "∏",
    "int": "∫",
    "oint": "∮",
    "bigcup": "⋃",
    "bigcap": "⋂",
    "angle": "∠",
    "triangle": "△",
    "perp": "⊥",
    "parallel": "∥",
    "ldots": "…",
    "cdots": "⋯",
    "vdots": "⋮",
    "ddots": "⋱",
    "prime": "′",
    "%": "%",
    "$": "$",
    "{": "{",
    "}": "}",
    "&": "&",
    "_": "_",
    "#": "#",
}
TEXT_FUNCTIONS: frozenset[str] = frozenset(
    {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "log", "ln", "lg"}
)
LIMIT_OPERATORS: frozenset[str] = frozenset(
    {"sum", "prod", "int", "oint", "lim", "max", "min", "sup", "inf", "bigcup", "bigcap"}
)
ACCENT_COMMANDS: dict[str, str] = {
    "vec": "→",
    "bar": "¯",
    "overline": "¯",
    "hat": "ˆ",
    "widehat": "ˆ",
    "dot": "˙",
    "ddot": "¨",
    "overbrace": "⏞",
}
MATH_VARIANTS: dict[str, str] = {
    "mathrm": "normal",
    "mathbf": "bold",
    "boldsymbol": "bold-italic",
    "mathcal": "script",
    "mathbb": "double-struck",
    "mathsf": "sans-serif",
    "mathtt": "monospace",
    "mathfrak": "fraktur",
}
DELIM_MAP: dict[str, str] = {
    "(": "(",
    ")": ")",
    "[": "[",
    "]": "]",
    "|": "∣",
    r"\|": "‖",
    r"\{": "{",
    r"\}": "}",
    r"\langle": "⟨",
    r"\rangle": "⟩",
    r"\lfloor": "⌊",
    r"\rfloor": "⌋",
    r"\lceil": "⌈",
    r"\rceil": "⌉",
    ".": "",
}

A4_PRINT_CSS = """
@page { size: A4; margin: 18mm 18mm 20mm 20mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 16px;
  background: #f3f4f6;
  color: #111827;
  font-family: "Times New Roman", Times, serif;
  font-size: 12pt;
  line-height: 1.45;
}
.a4-sheet {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto 16px;
  padding: 18mm 18mm 20mm 20mm;
  background: #ffffff;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
}
.sheet-header {
  text-align: center;
  border-bottom: 1.5px solid #1f2937;
  padding-bottom: 8px;
  margin-bottom: 12px;
}
.sheet-header .school {
  font-size: 11pt;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
.sheet-header h1 {
  margin: 4px 0;
  font-size: 15pt;
  text-transform: uppercase;
}
.sheet-header .meta {
  font-size: 11pt;
  color: #374151;
}
.audience-badge {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 10px;
  border: 1px solid #1f2937;
  font-size: 10pt;
  font-weight: bold;
}
h2 {
  font-size: 13pt;
  margin: 14px 0 8px;
  break-after: avoid;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0 14px;
  font-size: 11pt;
  break-inside: avoid;
}
thead { display: table-header-group; }
tr, .rubric-block, .no-break {
  break-inside: avoid;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #374151;
  padding: 5px 7px;
  vertical-align: top;
  text-align: left;
}
th {
  background: #f3f4f6;
  font-weight: bold;
  text-align: center;
}
.num { text-align: center; }
.total-row td {
  font-weight: bold;
  background: #f9fafb;
}
.rubric-block {
  border: 1px solid #9ca3af;
  padding: 8px 10px;
  margin-bottom: 10px;
}
.math {
  font-style: italic;
  white-space: nowrap;
}
.notes {
  font-size: 10.5pt;
  color: #374151;
  margin-top: 8px;
}
@media print {
  body { background: #ffffff; padding: 0; }
  .a4-sheet {
    width: auto;
    min-height: auto;
    margin: 0;
    padding: 0;
    box-shadow: none;
    page-break-after: always;
    break-after: page;
  }
  .a4-sheet:last-child {
    page-break-after: auto;
    break-after: auto;
  }
}
""".strip()


def _mm(tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    elem = ET.Element(f"{{{MATHML_NS}}}{tag}", attrs)
    if text is not None:
        elem.text = text
    return elem


def _wrap_mrow(nodes: list[ET.Element]) -> ET.Element:
    if not nodes:
        return _mm("mrow")
    if len(nodes) == 1:
        return nodes[0]
    row = _mm("mrow")
    row.extend(nodes)
    return row


def _non_empty_mrow(nodes: list[ET.Element]) -> ET.Element:
    if not nodes:
        return _mm("mspace")
    return _wrap_mrow(nodes)


class _LatexMathMLParser:
    """Bộ phân tích LaTeX thuần Python sang MathML tương thích mach_backend.math_word.omml."""

    def __init__(self, source: str) -> None:
        self.src = source.strip()
        self.pos = 0
        self.length = len(self.src)

    def _skip_ws(self) -> None:
        while self.pos < self.length and self.src[self.pos].isspace():
            self.pos += 1

    def _read_braced_raw(self) -> str:
        self._skip_ws()
        if self.pos >= self.length:
            return ""
        if self.src[self.pos] != "{":
            if self.src[self.pos] == "\\":
                start = self.pos
                self.pos += 1
                while self.pos < self.length and self.src[self.pos].isalpha():
                    self.pos += 1
                if self.pos == start + 1 and self.pos < self.length:
                    self.pos += 1
                return self.src[start : self.pos]
            ch = self.src[self.pos]
            self.pos += 1
            return ch
        self.pos += 1
        depth = 1
        start = self.pos
        while self.pos < self.length and depth > 0:
            ch = self.src[self.pos]
            if ch == "\\":
                self.pos += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    content = self.src[start : self.pos]
                    self.pos += 1
                    return content
            self.pos += 1
        return self.src[start:]

    def _read_group_nodes(self) -> list[ET.Element]:
        self._skip_ws()
        if self.pos >= self.length:
            return [_mm("mspace")]
        if self.src[self.pos] == "{":
            inner = self._read_braced_raw()
            sub = _LatexMathMLParser(inner).parse_nodes()
            return sub or [_mm("mspace")]
        atom = self._parse_atom()
        return [atom] if atom is not None else [_mm("mspace")]

    def _read_optional_bracket_nodes(self) -> list[ET.Element] | None:
        self._skip_ws()
        if self.pos >= self.length or self.src[self.pos] != "[":
            return None
        self.pos += 1
        depth = 1
        start = self.pos
        while self.pos < self.length and depth > 0:
            ch = self.src[self.pos]
            if ch == "\\":
                self.pos += 2
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    inner = self.src[start : self.pos]
                    self.pos += 1
                    return _LatexMathMLParser(inner).parse_nodes() or [_mm("mspace")]
            self.pos += 1
        return _LatexMathMLParser(self.src[start:]).parse_nodes() or [_mm("mspace")]

    def _read_command(self) -> str:
        self.pos += 1  # qua ký tự '\'
        if self.pos >= self.length:
            return ""
        if not self.src[self.pos].isalpha():
            ch = self.src[self.pos]
            self.pos += 1
            return ch
        start = self.pos
        while self.pos < self.length and self.src[self.pos].isalpha():
            self.pos += 1
        return self.src[start : self.pos]

    def _read_delim(self) -> str:
        self._skip_ws()
        if self.pos >= self.length:
            return ""
        if self.src[self.pos] == "\\":
            token = "\\" + self._read_command()
            return DELIM_MAP.get(token, token.lstrip("\\"))
        ch = self.src[self.pos]
        self.pos += 1
        return DELIM_MAP.get(ch, ch)

    def _parse_chemistry(self, formula: str) -> ET.Element:
        nodes: list[ET.Element] = []
        tokens = re.findall(r"<->|->|[A-Za-z]+|\d+|\^?[+-]|[^\s]", formula)
        for token in tokens:
            if token == "->":
                nodes.append(_mm("mo", "→"))
            elif token == "<->":
                nodes.append(_mm("mo", "⇌"))
            elif token.isdigit() and nodes and nodes[-1].tag.endswith(("mi", "mrow")):
                base = nodes.pop()
                msub = _mm("msub")
                msub.append(base)
                msub.append(_mm("mn", token))
                nodes.append(msub)
            elif token.isdigit():
                nodes.append(_mm("mn", token))
            elif token.isalpha():
                nodes.append(_mm("mi", token, mathvariant="normal"))
            else:
                nodes.append(_mm("mo", token))
        return _non_empty_mrow(nodes)

    def _parse_environment(self, env_name: str) -> ET.Element:
        end_marker = f"\\end{{{env_name}}}"
        end_idx = self.src.find(end_marker, self.pos)
        if end_idx == -1:
            body = self.src[self.pos :]
            self.pos = self.length
        else:
            body = self.src[self.pos : end_idx]
            self.pos = end_idx + len(end_marker)

        table = _mm("mtable")
        raw_rows = re.split(r"\\\\", body.strip())
        for raw_row in raw_rows:
            if not raw_row.strip():
                continue
            mtr = _mm("mtr")
            for raw_cell in raw_row.split("&"):
                mtd = _mm("mtd")
                cell_nodes = _LatexMathMLParser(raw_cell).parse_nodes()
                mtd.extend(cell_nodes or [_mm("mspace")])
                mtr.append(mtd)
            table.append(mtr)

        fences = {
            "cases": ("{", ""),
            "pmatrix": ("(", ")"),
            "bmatrix": ("[", "]"),
            "vmatrix": ("∣", "∣"),
            "Vmatrix": ("‖", "‖"),
        }.get(env_name)
        if fences is not None:
            left_ch, right_ch = fences
            row = _mm("mrow")
            row.append(_mm("mo", left_ch, fence="true"))
            row.append(table)
            if right_ch:
                row.append(_mm("mo", right_ch, fence="true"))
            return row
        return table

    def _parse_left_right(self) -> ET.Element:
        beg = self._read_delim()
        inner_nodes: list[ET.Element] = []
        end = ""
        while self.pos < self.length:
            self._skip_ws()
            if self.src.startswith(r"\right", self.pos):
                self.pos += len(r"\right")
                end = self._read_delim()
                break
            node = self._parse_scripted_atom()
            if node is not None:
                inner_nodes.append(node)
            else:
                break
        row = _mm("mrow")
        row.append(_mm("mo", beg or ".", fence="true"))
        row.extend(inner_nodes or [_mm("mspace")])
        if end:
            row.append(_mm("mo", end, fence="true"))
        return row

    def _parse_atom(self) -> ET.Element | None:
        self._skip_ws()
        if self.pos >= self.length:
            return None
        ch = self.src[self.pos]

        if ch == "{":
            inner = self._read_braced_raw()
            return _non_empty_mrow(_LatexMathMLParser(inner).parse_nodes())

        if ch == "}":
            self.pos += 1
            return None

        if ch == "\\":
            if self.src.startswith(r"\left", self.pos):
                self.pos += len(r"\left")
                return self._parse_left_right()
            cmd = self._read_command()
            if not cmd:
                return None
            if cmd in {",", ";", ":", "!", "quad", "qquad", " "}:
                return _mm("mspace")
            if cmd in {"frac", "dfrac", "tfrac"}:
                num = _non_empty_mrow(self._read_group_nodes())
                den = _non_empty_mrow(self._read_group_nodes())
                frac = _mm("mfrac")
                frac.extend([num, den])
                return frac
            if cmd == "binom":
                num = _non_empty_mrow(self._read_group_nodes())
                den = _non_empty_mrow(self._read_group_nodes())
                frac = _mm("mfrac", linethickness="0")
                frac.extend([num, den])
                row = _mm("mrow")
                row.extend([_mm("mo", "(", fence="true"), frac, _mm("mo", ")", fence="true")])
                return row
            if cmd == "sqrt":
                deg = self._read_optional_bracket_nodes()
                body = _non_empty_mrow(self._read_group_nodes())
                if deg is not None:
                    root = _mm("mroot")
                    root.extend([body, _non_empty_mrow(deg)])
                    return root
                sqrt = _mm("msqrt")
                sqrt.append(body)
                return sqrt
            if cmd in {"text", "mbox"}:
                content = self._read_braced_raw()
                return _mm("mtext", content)
            if cmd in MATH_VARIANTS:
                content = self._read_braced_raw()
                variant = MATH_VARIANTS[cmd]
                if cmd == "mathrm":
                    return _mm("mtext", content)
                return _mm("mi", content, mathvariant=variant)
            if cmd == "boxed":
                inner = self._read_group_nodes()
                box = _mm("menclose", notation="box")
                box.append(_non_empty_mrow(inner))
                return box
            if cmd == "ce":
                return self._parse_chemistry(self._read_braced_raw())
            if cmd in ACCENT_COMMANDS:
                inner = _non_empty_mrow(self._read_group_nodes())
                mover = _mm("mover", accent="true")
                mover.extend([inner, _mm("mo", ACCENT_COMMANDS[cmd])])
                return mover
            if cmd == "underbrace":
                inner = _non_empty_mrow(self._read_group_nodes())
                munder = _mm("munder")
                munder.extend([inner, _mm("mo", "⏟")])
                return munder
            if cmd == "begin":
                env_name = self._read_braced_raw().strip()
                return self._parse_environment(env_name)
            if cmd == "end":
                _ = self._read_braced_raw()
                return None
            if cmd in TEXT_FUNCTIONS or cmd in LIMIT_OPERATORS:
                sym = LATEX_SYMBOLS.get(cmd, cmd)
                return _mm("mo" if cmd in {"sum", "prod", "int", "oint"} else "mi", sym)
            if cmd in LATEX_SYMBOLS:
                sym = LATEX_SYMBOLS[cmd]
                tag = "mi" if sym.isalpha() else "mo"
                return _mm(tag, sym)
            return _mm("mi", cmd)

        if ch.isdigit():
            start = self.pos
            while self.pos < self.length and (
                self.src[self.pos].isdigit() or self.src[self.pos] == "."
            ):
                if (
                    self.src[self.pos] == "."
                    and self.pos + 1 < self.length
                    and not self.src[self.pos + 1].isdigit()
                ):
                    break
                self.pos += 1
            return _mm("mn", self.src[start : self.pos])

        if ch.isalpha():
            self.pos += 1
            return _mm("mi", ch)

        self.pos += 1
        return _mm("mo", ch)

    def _parse_scripted_atom(self) -> ET.Element | None:
        base = self._parse_atom()
        if base is None:
            return None
        sub_nodes: list[ET.Element] | None = None
        sup_nodes: list[ET.Element] | None = None
        while True:
            self._skip_ws()
            if self.pos >= self.length:
                break
            marker = self.src[self.pos]
            if marker == "_" and sub_nodes is None:
                self.pos += 1
                sub_nodes = self._read_group_nodes()
            elif marker == "^" and sup_nodes is None:
                self.pos += 1
                sup_nodes = self._read_group_nodes()
            else:
                break

        if sub_nodes is None and sup_nodes is None:
            return base

        is_limit_base = (base.text or "") in {"∑", "∏", "∫", "∮", "lim", "max", "min", "⋃", "⋂"}
        if sub_nodes is not None and sup_nodes is not None:
            tag = "munderover" if is_limit_base else "msubsup"
            elem = _mm(tag)
            elem.extend([base, _non_empty_mrow(sub_nodes), _non_empty_mrow(sup_nodes)])
            return elem
        if sub_nodes is not None:
            tag = "munder" if is_limit_base else "msub"
            elem = _mm(tag)
            elem.extend([base, _non_empty_mrow(sub_nodes)])
            return elem
        assert sup_nodes is not None
        tag = "mover" if is_limit_base else "msup"
        elem = _mm(tag)
        elem.extend([base, _non_empty_mrow(sup_nodes)])
        return elem

    def parse_nodes(self) -> list[ET.Element]:
        nodes: list[ET.Element] = []
        while self.pos < self.length:
            self._skip_ws()
            if self.pos >= self.length:
                break
            if self.src[self.pos] == "}":
                self.pos += 1
                continue
            node = self._parse_scripted_atom()
            if node is not None:
                nodes.append(node)
        return nodes


def latex_to_mathml(latex: str) -> str:
    """Chuyển đổi công thức LaTeX phổ biến sang MathML thuần Python để đưa vào omml()."""
    if not isinstance(latex, str) or len(latex) > 12000:
        raise AIError("invalid_math", "Công thức không hợp lệ hoặc quá dài.", http_status=422)
    nodes = _LatexMathMLParser(latex).parse_nodes()
    root = _mm("math")
    root.extend(nodes or [_mm("mspace")])
    return ET.tostring(root, encoding="unicode")


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True).replace("\n", "<br>")


def _inline_html_safe(value: Any) -> str:
    text = str(value or "")
    parts: list[str] = []
    for is_math, chunk in math_parts(text):
        escaped = _esc(chunk)
        if is_math:
            parts.append(f'<span class="math">{escaped}</span>')
        else:
            parts.append(escaped)
    return "".join(parts)


def _valid_q4(value: Any) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= 0
        and abs(value * 25 - round(value * 25)) < 1e-9
    )


def _q4_from_p100(p100: int) -> int | float:
    return p100 // 25 if p100 % 25 == 0 else p100 / 25


def _add_q4(a: int | float, b: int | float) -> int | float:
    return _q4_from_p100(round(a * 25) + round(b * 25))


def _to_quarter_points(value: Any, *, field_name: str) -> int | float:
    if isinstance(value, bool) or value is None:
        raise AIError(
            "invalid_points",
            f"Trường {field_name} phải là số điểm hợp lệ (tối đa 2 chữ số thập phân).",
            http_status=422,
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise AIError("invalid_points", f"Trường {field_name} phải là số hữu hạn.", http_status=422)
    try:
        dec = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise AIError(
            "invalid_points",
            f"Trường {field_name} không đúng định dạng số điểm.",
            http_status=422,
        ) from None
    if not dec.is_finite() or dec < Decimal("0"):
        raise AIError(
            "invalid_points",
            f"Trường {field_name} không được âm.",
            http_status=422,
        )
    scaled_p100 = dec * Decimal("100")
    if scaled_p100 != scaled_p100.to_integral_value():
        raise AIError(
            "invalid_points",
            f"Điểm ở {field_name} ({value}) chỉ được có tối đa 2 chữ số thập phân (bước 0,01).",
            http_status=422,
        )
    return _q4_from_p100(int(scaled_p100))


def _question_quarter_points(question: dict[str, Any], index: int) -> int | float:
    has_points = "points" in question and question["points"] is not None
    has_q4 = "pointsQ4" in question and question["pointsQ4"] is not None
    q4_from_points: int | float | None = None
    if has_points:
        q4_from_points = _to_quarter_points(question["points"], field_name=f"câu {index}")
    q4_from_field: int | float | None = None
    if has_q4:
        raw_q4 = question["pointsQ4"]
        if not _valid_q4(raw_q4):
            raise AIError(
                "invalid_points",
                f"Trường pointsQ4 ở câu {index} phải là số không âm, chính xác đến 0,01 điểm.",
                http_status=422,
            )
        q4_from_field = _q4_from_p100(round(raw_q4 * 25))
    if (
        q4_from_points is not None
        and q4_from_field is not None
        and round(q4_from_points * 25) != round(q4_from_field * 25)
    ):
        raise AIError(
            "invalid_points",
            f"Câu {index} có points và pointsQ4 không khớp nhau.",
            http_status=422,
        )
    explicit_q4 = q4_from_points if q4_from_points is not None else q4_from_field

    raw_rubric = question.get("rubric")
    if raw_rubric is not None and not isinstance(raw_rubric, list):
        raise AIError(
            "invalid_rubric",
            f"Barem ở câu {index} phải là danh sách các ý chấm.",
            http_status=422,
        )
    if raw_rubric:
        rubric_p100 = 0
        for step_idx, step in enumerate(raw_rubric, 1):
            if not isinstance(step, dict):
                raise AIError(
                    "invalid_rubric",
                    f"Ý barem {step_idx} ở câu {index} không hợp lệ.",
                    http_status=422,
                )
            if "pointsQ4" in step and step["pointsQ4"] is not None:
                raw_step_q4 = step["pointsQ4"]
                if not _valid_q4(raw_step_q4):
                    raise AIError(
                        "invalid_points",
                        f"Điểm thành phần ý {step_idx} câu {index} không hợp lệ.",
                        http_status=422,
                    )
                step_q4: int | float = _q4_from_p100(round(raw_step_q4 * 25))
            elif "points" in step and step["points"] is not None:
                step_q4 = _to_quarter_points(
                    step["points"], field_name=f"barem câu {index} ý {step_idx}"
                )
            else:
                raise AIError(
                    "invalid_points",
                    f"Ý {step_idx} trong barem câu {index} thiếu điểm thành phần.",
                    http_status=422,
                )
            rubric_p100 += round(step_q4 * 25)
        if explicit_q4 is not None and rubric_p100 != round(explicit_q4 * 25):
            raise AIError(
                "invalid_rubric",
                f"Câu {index}: tổng điểm barem ({rubric_p100 / 100:.2f}) "
                f"không khớp tổng điểm câu ({_q4_to_float(explicit_q4):.2f}).",
                http_status=422,
            )
        return explicit_q4 if explicit_q4 is not None else _q4_from_p100(rubric_p100)

    return explicit_q4 if explicit_q4 is not None else 0


def _q4_to_float(q4: int | float) -> float:
    return round(round(q4 * 25) / 100, 2)


def _normalize_type(raw_type: Any, index: int) -> QuestionType:
    if raw_type is None:
        return "mcq"
    if not isinstance(raw_type, str):
        raise AIError("invalid_question", f"Loại câu ở câu {index} không hợp lệ.", http_status=422)
    normalized = TYPE_ALIASES.get(raw_type.strip().casefold())
    if normalized is None:
        raise AIError(
            "invalid_question",
            f"Loại câu '{raw_type}' ở câu {index} chưa được hỗ trợ.",
            http_status=422,
        )
    return normalized


def _normalize_level(raw_level: Any, index: int) -> int:
    if raw_level is None:
        return 0
    if isinstance(raw_level, bool):
        raise AIError("invalid_level", f"Mức độ nhận thức ở câu {index} sai kiểu.", http_status=422)
    if isinstance(raw_level, int):
        if 0 <= raw_level <= 3:
            return raw_level
        raise AIError(
            "invalid_level",
            f"Mức độ ở câu {index} phải nằm trong 0..3.",
            http_status=422,
        )
    if isinstance(raw_level, str):
        mapped = LEVEL_ALIASES.get(raw_level.strip().casefold())
        if mapped is not None:
            return mapped
    raise AIError(
        "invalid_level",
        f"Mức độ '{raw_level}' ở câu {index} phải thuộc 4 mức "
        "Nhận biết/Thông hiểu/Vận dụng/Vận dụng cao.",
        http_status=422,
    )


def _choice_group_name(question: dict[str, Any]) -> str:
    raw_group = question.get("choiceGroup")
    return raw_group.strip() if isinstance(raw_group, str) and raw_group.strip() else ""


def _effective_totals_by_choice_group(
    entries: list[tuple[str, int | float]],
) -> dict[str, Any]:
    """Tính tổng câu và tổng điểm hiệu lực theo nhánh choiceGroup (chung + nhánh lớn nhất)."""
    common_q4: int | float = 0
    common_count = 0
    track_q4: dict[str, int | float] = {}
    track_counts: dict[str, int] = {}
    for grp_raw, q4 in entries:
        grp_key = grp_raw.strip().casefold() if grp_raw.strip() else ""
        if grp_key:
            track_q4[grp_key] = _add_q4(track_q4.get(grp_key, 0), q4)
            track_counts[grp_key] = track_counts.get(grp_key, 0) + 1
        else:
            common_q4 = _add_q4(common_q4, q4)
            common_count += 1
    if not track_counts:
        return {
            "primary_track": None,
            "effective_q4": common_q4,
            "effective_questions": common_count,
        }
    primary_track = max(
        track_counts.keys(),
        key=lambda k: (float(track_q4.get(k, 0)), track_counts[k]),
    )
    return {
        "primary_track": primary_track,
        "effective_q4": _add_q4(common_q4, track_q4.get(primary_track, 0)),
        "effective_questions": common_count + track_counts[primary_track],
    }


def _normalize_objective_question_for_label(question: dict[str, Any], kind: QuestionType) -> dict:
    copied = dict(question)
    copied["type"] = kind
    if kind == "mcq":
        raw_options = copied.get("options")
        opt_count = len(raw_options) if isinstance(raw_options, list) else 4
        max_opts = max(4, min(opt_count, 8))
        letters = "ABCDEFGH"[:max_opts]
        ans = copied.get("answer")
        if isinstance(ans, str):
            letter = ans.strip().upper()
            if letter in letters:
                copied["answer"] = letters.index(letter)
            else:
                allowed = "A/B/C/D" if max_opts == 4 else f"A..{letters[-1]}"
                raise AIError(
                    "invalid_answer",
                    f"Đáp án trắc nghiệm phải là {allowed} hoặc chỉ số 0..{max_opts - 1}.",
                    http_status=422,
                )
    elif kind == "truefalse":
        raw_tf = copied.get("truthValues")
        if raw_tf is None:
            raw_tf = copied.get("answer")
        if isinstance(raw_tf, (list, tuple)) and len(raw_tf) == 4:
            converted: list[bool] = []
            for item in raw_tf:
                if type(item) is bool:
                    converted.append(item)
                elif isinstance(item, str) and item.strip().casefold() in {"đ", "đúng", "true"}:
                    converted.append(True)
                elif isinstance(item, str) and item.strip().casefold() in {"s", "sai", "false"}:
                    converted.append(False)
                else:
                    raise AIError(
                        "invalid_answer",
                        "Đáp án đúng/sai phải gồm 4 giá trị boolean hoặc Đúng/Sai.",
                        http_status=422,
                    )
            copied["truthValues"] = tuple(converted)
        elif raw_tf is not None:
            raise AIError(
                "invalid_answer",
                "Câu đúng/sai phải có đủ 4 mệnh đề Đúng/Sai.",
                http_status=422,
            )
    elif kind == "short":
        raw_short = copied.get("answerText")
        if raw_short is None:
            raw_short = copied.get("answer")
        if isinstance(raw_short, (int, float)) and not isinstance(raw_short, bool):
            copied["answerText"] = str(raw_short)
    return copied


def _extract_rubric_steps(
    question: dict[str, Any], index: int, total_q4: int | float
) -> list[dict[str, Any]]:
    raw_rubric = question.get("rubric") or []
    steps: list[dict[str, Any]] = []
    for step_idx, step in enumerate(raw_rubric, 1):
        if "pointsQ4" in step and step["pointsQ4"] is not None:
            raw_step_q4 = step["pointsQ4"]
            if not _valid_q4(raw_step_q4):
                raise AIError(
                    "invalid_points",
                    f"Điểm thành phần ý {step_idx} câu {index} không hợp lệ.",
                    http_status=422,
                )
            step_q4: int | float = _q4_from_p100(round(raw_step_q4 * 25))
        else:
            step_q4 = _to_quarter_points(
                step["points"], field_name=f"barem câu {index} ý {step_idx}"
            )
        text = str(
            step.get("text")
            or step.get("criterion")
            or step.get("content")
            or step.get("step")
            or ""
        ).strip()
        if not text:
            raise AIError(
                "invalid_rubric",
                f"Ý {step_idx} trong barem câu {index} chưa có nội dung tiêu chí.",
                http_status=422,
            )
        steps.append(
            {
                "step": step_idx,
                "text": text,
                "points": _q4_to_float(step_q4),
                "points_q4": step_q4,
                "points_label": format_points_vi(_q4_to_float(step_q4)),
            }
        )
    if not steps:
        fallback = str(
            question.get("explanation")
            or question.get("answerText")
            or question.get("solution")
            or ""
        ).strip()
        if fallback:
            steps.append(
                {
                    "step": 1,
                    "text": fallback,
                    "points": _q4_to_float(total_q4),
                    "points_q4": total_q4,
                    "points_label": format_points_vi(_q4_to_float(total_q4)),
                }
            )
    return steps


def _validate_exam_base(exam: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(exam, dict):
        raise AIError("invalid_exam", "Dữ liệu đề thi phải là đối tượng JSON.", http_status=422)
    questions = exam.get("questions")
    if not isinstance(questions, list) or not questions:
        raise AIError(
            "invalid_exam",
            "Đề thi phải có danh sách câu hỏi không rỗng.",
            http_status=422,
        )
    for idx, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            raise AIError(
                "invalid_question", f"Câu {idx} không phải đối tượng JSON.", http_status=422
            )
    return exam, questions


def redact_exam_for_student(exam: dict[str, Any]) -> dict[str, Any]:
    """Tạo bản sao đề thi sạch cho học sinh, xóa sạch đáp án, lời giải và barem."""
    cleaned = deepcopy(exam)
    for secret_key in ("chat", "history", "aiConfig", "apiKey", "secret", "token", "notes"):
        cleaned.pop(secret_key, None)
    questions = cleaned.get("questions")
    if isinstance(questions, list):
        for q in questions:
            if not isinstance(q, dict):
                continue
            q["answer"] = None
            q["answerKnown"] = False
            for key in (
                "answerText",
                "truthValues",
                "explanation",
                "explanationDoc",
                "rubric",
                "solution",
                "evidence",
                "check",
                "approval",
            ):
                q.pop(key, None)
    return cleaned


def validate_and_normalize_answer_key(
    exam: dict[str, Any], *, teacher: bool = True
) -> dict[str, Any]:
    """Kiểm tra điểm bước 0,25 và tách phần đáp án trắc nghiệm với barem tự luận cho giáo viên."""
    if not teacher:
        raise AIError(
            "teacher_only",
            "Đáp án và barem cả đề bắt buộc chỉ dành cho giáo viên; bản học sinh bị từ chối.",
            http_status=403,
        )
    exam_obj, questions = _validate_exam_base(exam)

    objective_answers: list[dict[str, Any]] = []
    essay_rubrics: list[dict[str, Any]] = []
    objective_entries: list[tuple[str, int | float]] = []
    essay_entries: list[tuple[str, int | float]] = []
    all_entries: list[tuple[str, int | float]] = []

    for idx, raw_q in enumerate(questions, 1):
        q_type = _normalize_type(raw_q.get("type"), idx)
        level_idx = _normalize_level(raw_q.get("level"), idx)
        q4 = _question_quarter_points(raw_q, idx)
        pts = _q4_to_float(q4)
        choice_group = _choice_group_name(raw_q)
        all_entries.append((choice_group, q4))
        topic = str(raw_q.get("topic") or raw_q.get("chapter") or "Chủ đề chung").strip()
        lesson = str(
            raw_q.get("lesson") or raw_q.get("unit") or raw_q.get("subtopic") or ""
        ).strip()
        explanation = str(raw_q.get("explanation") or "").strip()
        q_id = str(raw_q.get("id") or f"q-{idx}")

        if q_type in {"mcq", "truefalse", "short"}:
            normalized_q = _normalize_objective_question_for_label(raw_q, q_type)
            try:
                label = saved_answer_label(normalized_q)
            except AIError as err:
                raise AIError(err.code, f"Câu {idx}: {err}", http_status=422) from None
            if normalized_q.get("answerKnown") is False or label == "Chưa nhập đáp án":
                raise AIError(
                    "missing_answer_key",
                    f"Câu {idx} chưa có đáp án; không xuất bản đáp án rỗng cho giáo viên.",
                    http_status=422,
                )
            if q_type == "mcq":
                ans = normalized_q.get("answer")
                options = raw_q.get("options")
                if isinstance(options, list) and type(ans) is int and ans >= 0:
                    if (
                        ans >= len(options)
                        or not isinstance(options[ans], str)
                        or not options[ans].strip()
                    ):
                        raise AIError(
                            "empty_selected_option",
                            f"Câu {idx} đang chọn đáp án "
                            f"{chr(65 + ans) if ans < 8 else ans + 1} "
                            "nhưng phương án bị trống.",
                            http_status=400,
                        )
            rubric_steps = _extract_rubric_steps(raw_q, idx, q4) if raw_q.get("rubric") else []
            objective_entries.append((choice_group, q4))
            objective_answers.append(
                {
                    "index": idx,
                    "id": q_id,
                    "type": q_type,
                    "type_label": TYPE_LABELS[q_type],
                    "topic": topic,
                    "lesson": lesson,
                    "level": LEVEL_NAMES[level_idx],
                    "stem": str(raw_q.get("stem") or "").strip(),
                    "points": pts,
                    "points_q4": q4,
                    "points_label": format_points_vi(pts),
                    "answer_label": label,
                    "explanation": explanation,
                    "rubric": rubric_steps,
                }
            )
        else:
            rubric_steps = _extract_rubric_steps(raw_q, idx, q4)
            if not rubric_steps:
                raise AIError(
                    "missing_rubric",
                    f"Câu tự luận {idx} chưa có barem chấm hoặc lời giải tham khảo.",
                    http_status=422,
                )
            essay_entries.append((choice_group, q4))
            essay_rubrics.append(
                {
                    "index": idx,
                    "id": q_id,
                    "type": "essay",
                    "type_label": TYPE_LABELS["essay"],
                    "topic": topic,
                    "lesson": lesson,
                    "level": LEVEL_NAMES[level_idx],
                    "stem": str(raw_q.get("stem") or "").strip(),
                    "points": pts,
                    "points_q4": q4,
                    "points_label": format_points_vi(pts),
                    "explanation": explanation,
                    "rubric": rubric_steps,
                }
            )

    objective_q4 = _effective_totals_by_choice_group(objective_entries)["effective_q4"]
    essay_q4 = _effective_totals_by_choice_group(essay_entries)["effective_q4"]
    total_info = _effective_totals_by_choice_group(all_entries)
    total_q4 = total_info["effective_q4"]
    total_pts = _q4_to_float(total_q4)
    obj_pts = _q4_to_float(objective_q4)
    ess_pts = _q4_to_float(essay_q4)
    return {
        "audience": "teacher",
        "title": str(exam_obj.get("title") or "Đề kiểm tra").strip(),
        "school": str(exam_obj.get("school") or "").strip(),
        "subject": str(exam_obj.get("subject") or "").strip(),
        "grade": str(exam_obj.get("grade") or "").strip(),
        "minutes": exam_obj.get("minutes"),
        "total_questions": len(questions),
        "effective_questions": total_info["effective_questions"],
        "total_points": total_pts,
        "total_points_q4": total_q4,
        "total_points_label": format_points_vi(total_pts),
        "objective_points": obj_pts,
        "objective_points_label": format_points_vi(obj_pts),
        "essay_points": ess_pts,
        "essay_points_label": format_points_vi(ess_pts),
        "objective_answers": objective_answers,
        "essay_rubrics": essay_rubrics,
    }


def _extract_competency(question: dict[str, Any], topic: str, lesson: str, level_name: str) -> str:
    for key in (
        "competency",
        "competence",
        "indicator",
        "specification",
        "objective",
        "yccd",
        "learningObjective",
        "specNote",
    ):
        value = question.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    target = f"{topic} — {lesson}" if lesson else topic
    return f"Đạt yêu cầu mức {level_name} đối với nội dung {target}"


def _allocate_percentages(weights: list[int | float]) -> list[float]:
    """Phân bổ phần trăm (bội 0.01%) theo largest-remainder sao cho tổng đúng 100.00%."""
    scaled_weights = [max(0, round(w * 25)) for w in weights]
    total_w = sum(scaled_weights)
    if total_w <= 0:
        return [0.0] * len(weights)
    floors: list[int] = []
    remainders: list[tuple[int, int]] = []
    for idx, w in enumerate(scaled_weights):
        exact = w * 10000
        floors.append(exact // total_w)
        if w > 0:
            remainders.append((exact % total_w, -idx))
    remainders.sort(reverse=True)
    needed = 10000 - sum(floors)
    for _, neg_idx in remainders[:needed]:
        floors[-neg_idx] += 1
    return [round(fp / 100.0, 2) for fp in floors]


def build_matrix_and_specification(exam: dict[str, Any]) -> dict[str, Any]:
    """Lập bảng Ma trận & Đặc tả cả đề theo chủ đề/bài học, 4 mức nhận thức và tỷ lệ %."""
    exam_obj, questions = _validate_exam_base(exam)

    parsed_items: list[tuple[dict[str, Any], QuestionType, int, int | float, str]] = []
    entries: list[tuple[str, int | float]] = []
    for idx, raw_q in enumerate(questions, 1):
        q_type = _normalize_type(raw_q.get("type"), idx)
        level_idx = _normalize_level(raw_q.get("level"), idx)
        q4 = _question_quarter_points(raw_q, idx)
        choice_group = _choice_group_name(raw_q)
        parsed_items.append((raw_q, q_type, level_idx, q4, choice_group))
        entries.append((choice_group, q4))

    total_info = _effective_totals_by_choice_group(entries)
    primary_track: str | None = total_info["primary_track"]
    total_q4: int | float = total_info["effective_q4"]
    total_questions: int = total_info["effective_questions"]

    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    level_counts = [0, 0, 0, 0]
    level_q4: list[int | float] = [0, 0, 0, 0]
    type_counts: dict[QuestionType, int] = {"mcq": 0, "truefalse": 0, "short": 0, "essay": 0}
    type_q4: dict[QuestionType, int | float] = {"mcq": 0, "truefalse": 0, "short": 0, "essay": 0}

    for idx, (raw_q, q_type, level_idx, q4, choice_group) in enumerate(parsed_items, 1):
        topic = str(raw_q.get("topic") or raw_q.get("chapter") or "Chủ đề chung").strip()
        lesson = str(
            raw_q.get("lesson") or raw_q.get("unit") or raw_q.get("subtopic") or ""
        ).strip()
        competency = _extract_competency(raw_q, topic, lesson, LEVEL_NAMES[level_idx])

        grp_key = choice_group.casefold()
        group_key = (topic.casefold(), lesson.casefold(), grp_key)
        group: dict[str, Any] | None = groups.get(group_key)
        if group is None:
            levels_map: dict[str, dict[str, Any]] = {
                name: {
                    "count": 0,
                    "points_q4": 0,
                    "points": 0.0,
                    "points_label": format_points_vi(0.0),
                    "question_indices": [],
                    "question_types": [],
                    "competencies": [],
                }
                for name in LEVEL_NAMES
            }
            group = {
                "topic": topic,
                "lesson": lesson,
                "choice_group": choice_group,
                "levels": levels_map,
                "question_types": [],
                "competencies": [],
                "total_questions": 0,
                "total_points_q4": 0,
            }
            groups[group_key] = group

        level_name = LEVEL_NAMES[level_idx]
        cell: dict[str, Any] = group["levels"][level_name]
        cell["count"] += 1
        cell["points_q4"] = _add_q4(cell["points_q4"], q4)
        cell["points"] = _q4_to_float(cell["points_q4"])
        cell["points_label"] = format_points_vi(cell["points"])
        cell["question_indices"].append(idx)
        if TYPE_LABELS[q_type] not in cell["question_types"]:
            cell["question_types"].append(TYPE_LABELS[q_type])
        if competency not in cell["competencies"]:
            cell["competencies"].append(competency)

        if q_type not in group["question_types"]:
            group["question_types"].append(q_type)
        if competency not in group["competencies"]:
            group["competencies"].append(competency)

        group["total_questions"] += 1
        group["total_points_q4"] = _add_q4(group["total_points_q4"], q4)

        if primary_track is None or not grp_key or grp_key == primary_track:
            level_counts[level_idx] += 1
            level_q4[level_idx] = _add_q4(level_q4[level_idx], q4)
            type_counts[q_type] += 1
            type_q4[q_type] = _add_q4(type_q4[q_type], q4)

    rows: list[dict[str, Any]] = []
    specification_rows: list[dict[str, Any]] = []

    def calc_pct(part_q4: int | float, part_count: int) -> float:
        if total_q4 > 0:
            return round(part_q4 * 100.0 / total_q4, 2)
        if total_questions > 0:
            return round(part_count * 100.0 / total_questions, 2)
        return 0.0

    for order, group in enumerate(groups.values(), 1):
        row_pts = _q4_to_float(group["total_points_q4"])
        row_pct = calc_pct(group["total_points_q4"], group["total_questions"])
        rows.append(
            {
                "order": order,
                "topic": group["topic"],
                "lesson": group["lesson"],
                "choice_group": group["choice_group"],
                "levels": group["levels"],
                "question_types": group["question_types"],
                "question_type_labels": [TYPE_LABELS[t] for t in group["question_types"]],
                "competencies": group["competencies"],
                "total_questions": group["total_questions"],
                "total_points": row_pts,
                "total_points_q4": group["total_points_q4"],
                "total_points_label": format_points_vi(row_pts),
                "percentage": row_pct,
            }
        )
        for level_name in LEVEL_NAMES:
            cell = group["levels"][level_name]
            if cell["count"] > 0:
                specification_rows.append(
                    {
                        "order": len(specification_rows) + 1,
                        "topic": group["topic"],
                        "lesson": group["lesson"],
                        "choice_group": group["choice_group"],
                        "level": level_name,
                        "question_types": cell["question_types"],
                        "competencies": cell["competencies"],
                        "count": cell["count"],
                        "question_indices": cell["question_indices"],
                        "points": cell["points"],
                        "points_q4": cell["points_q4"],
                        "points_label": format_points_vi(cell["points"]),
                        "percentage": calc_pct(cell["points_q4"], cell["count"]),
                    }
                )

    by_level = {
        name: {
            "count": level_counts[idx],
            "points": _q4_to_float(level_q4[idx]),
            "points_q4": level_q4[idx],
            "points_label": format_points_vi(_q4_to_float(level_q4[idx])),
            "percentage": calc_pct(level_q4[idx], level_counts[idx]),
        }
        for idx, name in enumerate(LEVEL_NAMES)
    }
    by_type = {
        q_type: {
            "label": TYPE_LABELS[q_type],
            "count": type_counts[q_type],
            "points": _q4_to_float(type_q4[q_type]),
            "points_q4": type_q4[q_type],
            "points_label": format_points_vi(_q4_to_float(type_q4[q_type])),
            "percentage": calc_pct(type_q4[q_type], type_counts[q_type]),
        }
        for q_type in ("mcq", "truefalse", "short", "essay")
        if type_counts[q_type] > 0
    }

    for row, pct in zip(
        rows,
        _allocate_percentages(
            [
                g["total_points_q4"] if total_q4 > 0 else g["total_questions"]
                for g in groups.values()
            ]
        ),
        strict=True,
    ):
        row["percentage"] = pct
    for row, pct in zip(
        specification_rows,
        _allocate_percentages(
            [r["points_q4"] if total_q4 > 0 else r["count"] for r in specification_rows]
        ),
        strict=True,
    ):
        row["percentage"] = pct
    for name, pct in zip(
        LEVEL_NAMES,
        _allocate_percentages(
            [
                level_q4[idx] if total_q4 > 0 else level_counts[idx]
                for idx in range(len(LEVEL_NAMES))
            ]
        ),
        strict=True,
    ):
        by_level[name]["percentage"] = pct
    active_types: list[QuestionType] = [
        q_t for q_t in ("mcq", "truefalse", "short", "essay") if type_counts[q_t] > 0
    ]
    for qt, pct in zip(
        active_types,
        _allocate_percentages(
            [type_q4[q_t] if total_q4 > 0 else type_counts[q_t] for q_t in active_types]
        ),
        strict=True,
    ):
        by_type[qt]["percentage"] = pct

    return {
        "title": str(exam_obj.get("title") or "Đề kiểm tra").strip(),
        "school": str(exam_obj.get("school") or "").strip(),
        "subject": str(exam_obj.get("subject") or "").strip(),
        "grade": str(exam_obj.get("grade") or "").strip(),
        "minutes": exam_obj.get("minutes"),
        "total_questions": total_questions,
        "total_points": _q4_to_float(total_q4),
        "total_points_q4": total_q4,
        "total_points_label": format_points_vi(_q4_to_float(total_q4)),
        "rows": rows,
        "specification_rows": specification_rows,
        "by_level": by_level,
        "by_type": by_type,
    }


def _html_shell(title: str, sheets_html: str) -> str:
    return (
        "<!doctype html>"
        '<html lang="vi">'
        "<head>"
        '<meta charset="utf-8">'
        f"<title>{_esc(title)}</title>"
        f"<style>{A4_PRINT_CSS}</style>"
        "</head>"
        f"<body>{sheets_html}</body>"
        "</html>"
    )


def _header_block(data: dict[str, Any], subtitle: str, badge: str) -> str:
    school_html = f'<div class="school">{_esc(data["school"])}</div>' if data.get("school") else ""
    parts = []
    if data.get("subject"):
        parts.append(f"Môn: {_esc(data['subject'])}")
    if data.get("grade"):
        parts.append(f"Lớp: {_esc(data['grade'])}")
    if data.get("minutes") is not None:
        parts.append(f"Thời gian: {_esc(data['minutes'])} phút")
    parts.append(f"Tổng điểm: {_esc(format_points_vi(data['total_points']))}")
    meta = " · ".join(parts)
    return (
        '<header class="sheet-header">'
        f"{school_html}"
        f"<h1>{_esc(subtitle)} — {_esc(data['title'])}</h1>"
        f'<div class="meta">{meta}</div>'
        f'<div class="audience-badge">{_esc(badge)}</div>'
        "</header>"
    )


def export_answer_key_rubric_html(exam: dict[str, Any], *, teacher: bool = True) -> str:
    """Xuất HTML in A4 cho Đáp án & Barem cả đề (chỉ dành cho giáo viên, chặn XSS)."""
    data = validate_and_normalize_answer_key(exam, teacher=teacher)
    sections: list[str] = [
        _header_block(data, "ĐÁP ÁN VÀ HƯỚNG DẪN CHẤM", "BẢN DÀNH CHO GIÁO VIÊN")
    ]

    if data["objective_answers"]:
        rows_html = []
        for item in data["objective_answers"]:
            topic_text = f"{item['topic']} ({item['lesson']})" if item["lesson"] else item["topic"]
            note_html = _inline_html_safe(item["explanation"]) if item["explanation"] else "—"
            rows_html.append(
                "<tr>"
                f'<td class="num">Câu {_esc(item["index"])}</td>'
                f"<td>{_esc(item['type_label'])}</td>"
                f"<td>{_inline_html_safe(topic_text)}</td>"
                f'<td class="num">{_esc(item["level"])}</td>'
                f"<td><strong>{_inline_html_safe(item['answer_label'])}</strong></td>"
                f'<td class="num">{_esc(item["points_label"])}</td>'
                f"<td>{note_html}</td>"
                "</tr>"
            )
        sections.append(
            "<h2>I. Đáp án phần trắc nghiệm &amp; trả lời ngắn</h2>"
            "<table>"
            "<thead><tr>"
            "<th>Câu</th><th>Loại câu</th><th>Chủ đề / Bài</th><th>Mức độ</th>"
            "<th>Đáp án</th><th>Điểm</th><th>Giải thích</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody>"
            '<tfoot><tr class="total-row">'
            '<td colspan="5">Tổng điểm phần trắc nghiệm</td>'
            f'<td class="num">{_esc(format_points_vi(data["objective_points"]))}</td>'
            "<td></td></tr></tfoot>"
            "</table>"
        )

    if data["essay_rubrics"]:
        rubric_blocks: list[str] = ["<h2>II. Hướng dẫn chấm &amp; barem tự luận</h2>"]
        for item in data["essay_rubrics"]:
            step_rows = "".join(
                "<tr>"
                f'<td class="num">Ý {_esc(step["step"])}</td>'
                f"<td>{_inline_html_safe(step['text'])}</td>"
                f'<td class="num">{_esc(step["points_label"])}</td>'
                "</tr>"
                for step in item["rubric"]
            )
            explanation_html = (
                '<p class="notes"><strong>Ghi chú:</strong> '
                f"{_inline_html_safe(item['explanation'])}</p>"
                if item["explanation"]
                else ""
            )
            rubric_blocks.append(
                '<div class="rubric-block">'
                f"<p><strong>Câu {_esc(item['index'])} ({_esc(item['points_label'])}):</strong> "
                f"{_inline_html_safe(item['stem'])}</p>"
                "<table>"
                "<thead><tr><th>Bước</th><th>Nội dung yêu cầu / đáp án thành phần</th>"
                "<th>Điểm</th></tr></thead>"
                f"<tbody>{step_rows}</tbody>"
                '<tfoot><tr class="total-row">'
                '<td colspan="2">Tổng điểm câu</td>'
                f'<td class="num">{_esc(item["points_label"])}</td>'
                "</tr></tfoot>"
                "</table>"
                f"{explanation_html}"
                "</div>"
            )
        sections.extend(rubric_blocks)

    sheet = f'<section class="a4-sheet">{"".join(sections)}</section>'
    return _html_shell(f"Đáp án & Barem — {data['title']}", sheet)


def export_student_exam_html(exam: dict[str, Any]) -> str:
    """Xuất HTML in A4 bản học sinh: ẩn hoàn toàn đáp án, lời giải và barem."""
    _, questions = _validate_exam_base(exam)
    total_q4 = _effective_totals_by_choice_group(
        [
            (_choice_group_name(q), _question_quarter_points(q, idx))
            for idx, q in enumerate(questions, 1)
        ]
    )["effective_q4"]
    redacted = redact_exam_for_student(exam)
    header_data = {
        "title": str(redacted.get("title") or "Đề kiểm tra").strip(),
        "school": str(redacted.get("school") or "").strip(),
        "subject": str(redacted.get("subject") or "").strip(),
        "grade": str(redacted.get("grade") or "").strip(),
        "minutes": redacted.get("minutes"),
        "total_points": _q4_to_float(total_q4),
    }
    blocks: list[str] = [
        _header_block(header_data, "ĐỀ KIỂM TRA", "BẢN HỌC SINH · KHÔNG KÈM ĐÁP ÁN & BAREM")
    ]
    for idx, q in enumerate(redacted["questions"], 1):
        q4 = _question_quarter_points(q, idx)
        pts_label = format_points_vi(_q4_to_float(q4))
        options_html = ""
        if q.get("options"):
            items = "".join(
                f"<li>{_inline_html_safe(opt)}</li>" for opt in q["options"] if opt is not None
            )
            options_html = f'<ol type="A">{items}</ol>'
        blocks.append(
            '<div class="rubric-block">'
            f"<p><strong>Câu {_esc(idx)} ({_esc(pts_label)}):</strong> "
            f"{_inline_html_safe(q.get('stem', ''))}</p>"
            f"{options_html}"
            "</div>"
        )
    sheet = f'<section class="a4-sheet">{"".join(blocks)}</section>'
    return _html_shell(f"Đề kiểm tra — {header_data['title']}", sheet)


def export_matrix_specification_html(
    exam: dict[str, Any], *, orientation: Literal["portrait", "landscape"] = "portrait"
) -> str:
    """Xuất HTML in A4 cho Bảng Ma trận & Bảng Đặc tả cả đề (chống rách bảng, escape XSS)."""
    data = build_matrix_and_specification(exam)

    matrix_rows_html = []
    for row in data["rows"]:
        grp_badge = (
            f" <small>[{_esc(row['choice_group'])}]</small>" if row.get("choice_group") else ""
        )
        topic_cell = (
            f"<strong>{_inline_html_safe(row['topic'])}</strong>{grp_badge}<br>"
            f"<small>{_inline_html_safe(row['lesson'])}</small>"
            if row["lesson"]
            else f"<strong>{_inline_html_safe(row['topic'])}</strong>{grp_badge}"
        )
        level_cells = []
        for level_name in LEVEL_NAMES:
            cell = row["levels"][level_name]
            if cell["count"] > 0:
                level_cells.append(
                    f'<td class="num">{cell["count"]} câu<br>'
                    f"({_esc(format_points_vi(cell['points']))})</td>"
                )
            else:
                level_cells.append('<td class="num">—</td>')
        matrix_rows_html.append(
            "<tr>"
            f'<td class="num">{row["order"]}</td>'
            f"<td>{topic_cell}</td>"
            f"<td>{_esc(', '.join(row['question_type_labels']))}</td>"
            f"{''.join(level_cells)}"
            f'<td class="num">{row["total_questions"]}</td>'
            f'<td class="num">{_esc(row["total_points_label"])}</td>'
            f'<td class="num">{row["percentage"]:.2f}%</td>'
            "</tr>"
        )

    level_total_cells = "".join(
        f'<td class="num">{data["by_level"][name]["count"]} câu<br>'
        f"({_esc(data['by_level'][name]['points_label'])})</td>"
        for name in LEVEL_NAMES
    )
    level_pct_cells = "".join(
        f'<td class="num">{data["by_level"][name]["percentage"]:.2f}%</td>' for name in LEVEL_NAMES
    )

    matrix_sheet = (
        '<section class="a4-sheet">'
        + _header_block(data, "MA TRẬN ĐỀ KIỂM TRA", "BẢNG MA TRẬN 4 MỨC ĐỘ")
        + "<h2>I. Bảng ma trận phân bố câu hỏi và điểm</h2>"
        + "<table>"
        + "<thead><tr>"
        + "<th>TT</th><th>Chủ đề / Bài học</th><th>Loại câu hỏi</th>"
        + "".join(f"<th>{_esc(name)}</th>" for name in LEVEL_NAMES)
        + "<th>Tổng câu</th><th>Tổng điểm</th><th>Tỷ lệ %</th>"
        + "</tr></thead>"
        + f"<tbody>{''.join(matrix_rows_html)}</tbody>"
        + "<tfoot>"
        + '<tr class="total-row">'
        + '<td colspan="3">Tổng cộng</td>'
        + level_total_cells
        + f'<td class="num">{data["total_questions"]}</td>'
        + f'<td class="num">{_esc(data["total_points_label"])}</td>'
        + '<td class="num">100.00%</td>'
        + "</tr>"
        + '<tr class="total-row">'
        + '<td colspan="3">Tỷ lệ % theo mức độ</td>'
        + level_pct_cells
        + '<td colspan="3" class="num">Tổng tỷ lệ: 100.00%</td>'
        + "</tr>"
        + "</tfoot>"
        + "</table>"
        + "</section>"
    )

    spec_rows_html = []
    for row in data["specification_rows"]:
        grp_badge = (
            f" <small>[{_esc(row['choice_group'])}]</small>" if row.get("choice_group") else ""
        )
        topic_cell = (
            f"<strong>{_inline_html_safe(row['topic'])}</strong>{grp_badge}<br>"
            f"<small>{_inline_html_safe(row['lesson'])}</small>"
            if row["lesson"]
            else f"<strong>{_inline_html_safe(row['topic'])}</strong>{grp_badge}"
        )
        competencies_html = "<br>".join(_inline_html_safe(c) for c in row["competencies"])
        q_indices = ", ".join(f"Câu {i}" for i in row["question_indices"])
        spec_rows_html.append(
            "<tr>"
            f'<td class="num">{row["order"]}</td>'
            f"<td>{topic_cell}</td>"
            f'<td class="num">{_esc(row["level"])}</td>'
            f"<td>{_esc(', '.join(row['question_types']))}</td>"
            f"<td>{competencies_html}</td>"
            f'<td class="num">{row["count"]} ({_esc(q_indices)})</td>'
            f'<td class="num">{_esc(row["points_label"])}</td>'
            f'<td class="num">{row["percentage"]:.2f}%</td>'
            "</tr>"
        )

    spec_sheet = (
        '<section class="a4-sheet">'
        + _header_block(data, "BẢNG ĐẶC TẢ ĐỀ KIỂM TRA", "CHỈ BÁO ĐÁNH GIÁ & NĂNG LỰC")
        + "<h2>II. Bảng đặc tả chi tiết theo chủ đề và năng lực</h2>"
        + "<table>"
        + "<thead><tr>"
        + "<th>TT</th><th>Chủ đề / Bài học</th><th>Mức độ</th><th>Loại câu</th>"
        + "<th>Phạm vi năng lực / Chỉ báo đặc tả</th><th>Số câu (Vị trí)</th>"
        + "<th>Tổng điểm</th><th>Tỷ lệ %</th>"
        + "</tr></thead>"
        + f"<tbody>{''.join(spec_rows_html)}</tbody>"
        + '<tfoot><tr class="total-row">'
        + '<td colspan="5">Tổng hợp toàn đề</td>'
        + f'<td class="num">{data["total_questions"]} câu</td>'
        + f'<td class="num">{_esc(data["total_points_label"])}</td>'
        + '<td class="num">100.00%</td>'
        + "</tr></tfoot>"
        + "</table>"
        + "</section>"
    )
    html_out = _html_shell(f"Ma trận & Đặc tả — {data['title']}", matrix_sheet + spec_sheet)
    if orientation == "landscape":
        html_out = html_out.replace("</style>", "@page{size:A4 landscape;}</style>", 1)
    return html_out


class _DocxSpecBuilder:
    """Tạo tệp DOCX khổ A4 giữ công thức m:oMath qua mach_backend.math_word.omml."""

    def __init__(self, *, orientation: Literal["portrait", "landscape"] = "portrait") -> None:
        self.doc = Document()
        zoom = self.doc.settings.element.find(qn("w:zoom"))
        if zoom is not None:
            zoom.set(qn("w:percent"), "100")
        section = self.doc.sections[0]
        if orientation == "landscape":
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = Mm(297)
            section.page_height = Mm(210)
        else:
            section.page_width = Mm(210)
            section.page_height = Mm(297)
        section.top_margin = Mm(18)
        section.right_margin = Mm(18)
        section.bottom_margin = Mm(20)
        section.left_margin = Mm(20)
        for style_name in ("Normal", "Title", "Heading 1", "Heading 2"):
            style = self.doc.styles[style_name]
            style.font.name = "Times New Roman"
            style.font.size = Pt(14 if style_name in {"Title", "Heading 1"} else 12)
            style.font.color.rgb = RGBColor(0, 0, 0)
            style.paragraph_format.space_before = Pt(0)
            style.paragraph_format.space_after = Pt(4)

    def add_rich_paragraph(
        self,
        text: str,
        *,
        container: Any | None = None,
        bold: bool = False,
        italic: bool = False,
        align: WD_ALIGN_PARAGRAPH | None = None,
        style: str | None = None,
    ) -> Any:
        target = container if container is not None else self.doc
        p = target.add_paragraph(style=style) if style else target.add_paragraph()
        if align is not None:
            p.alignment = align
        self.append_rich_runs(p, text, bold=bold, italic=italic)
        return p

    def append_rich_runs(
        self, paragraph: Any, text: str, *, bold: bool = False, italic: bool = False
    ) -> None:
        for is_math, chunk in math_parts(str(text or "")):
            if is_math:
                mathml = latex_to_mathml(chunk)
                omml_element = omml(mathml)
                paragraph._p.append(parse_xml(ET.tostring(omml_element, encoding="unicode")))
            elif chunk:
                run = paragraph.add_run(chunk.replace(r"\$", "$"))
                if bold:
                    run.bold = True
                if italic:
                    run.italic = True

    def set_cell_rich_text(
        self,
        cell: Any,
        text: str,
        *,
        bold: bool = False,
        align: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.LEFT,
    ) -> None:
        cell._tc.clear_content()
        lines = str(text or "").splitlines() or [""]
        for line in lines:
            self.add_rich_paragraph(line, container=cell, bold=bold, align=align)

    def add_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths_mm: list[float],
        *,
        footer_rows: list[list[str]] | None = None,
        center_cols: set[int] | None = None,
    ) -> Any:
        total_rows = 1 + len(rows) + len(footer_rows or [])
        table = self.doc.add_table(rows=total_rows, cols=len(headers))
        table.style = "Table Grid"
        table.autofit = False
        centered = center_cols or set()

        def populate_row(
            row_idx: int, values: list[str], *, is_header: bool = False, is_footer: bool = False
        ) -> None:
            row = table.rows[row_idx]
            tr_pr = row._tr.get_or_add_trPr()
            tr_pr.append(OxmlElement("w:cantSplit"))
            if is_header:
                tr_pr.append(OxmlElement("w:tblHeader"))
            for col_idx, val in enumerate(values):
                cell = row.cells[col_idx]
                cell.width = Mm(col_widths_mm[col_idx])
                align = (
                    WD_ALIGN_PARAGRAPH.CENTER
                    if is_header or col_idx in centered
                    else WD_ALIGN_PARAGRAPH.LEFT
                )
                self.set_cell_rich_text(cell, val, bold=is_header or is_footer, align=align)

        for col_idx, width in enumerate(col_widths_mm):
            table.columns[col_idx].width = Mm(width)

        populate_row(0, headers, is_header=True)
        for idx, row_values in enumerate(rows, 1):
            populate_row(idx, row_values)
        for offset, foot_values in enumerate(footer_rows or [], 1 + len(rows)):
            populate_row(offset, foot_values, is_footer=True)
        return table

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        self.doc.save(buf)
        return buf.getvalue()


def export_answer_key_rubric_docx(exam: dict[str, Any], *, teacher: bool = True) -> bytes:
    """Xuất DOCX chuẩn OOXML (w:tbl + m:oMath) cho Đáp án & Barem cả đề giáo viên."""
    data = validate_and_normalize_answer_key(exam, teacher=teacher)
    builder = _DocxSpecBuilder()
    if data["school"]:
        builder.add_rich_paragraph(data["school"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    builder.add_rich_paragraph(
        f"ĐÁP ÁN VÀ HƯỚNG DẪN CHẤM — {data['title']}",
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        style="Title",
    )
    meta_parts = []
    if data["subject"]:
        meta_parts.append(f"Môn: {data['subject']}")
    if data["grade"]:
        meta_parts.append(f"Lớp: {data['grade']}")
    if data["minutes"] is not None:
        meta_parts.append(f"Thời gian: {data['minutes']} phút")
    meta_parts.append(f"Tổng điểm: {format_points_vi(data['total_points'])}")
    builder.add_rich_paragraph(" · ".join(meta_parts), align=WD_ALIGN_PARAGRAPH.CENTER)
    builder.add_rich_paragraph("BẢN DÀNH CHO GIÁO VIÊN", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)

    if data["objective_answers"]:
        builder.add_rich_paragraph(
            "I. Đáp án phần trắc nghiệm & trả lời ngắn", bold=True, style="Heading 2"
        )
        rows = [
            [
                f"Câu {item['index']}",
                item["type_label"],
                f"{item['topic']} ({item['lesson']})" if item["lesson"] else item["topic"],
                item["level"],
                item["answer_label"],
                item["points_label"],
                item["explanation"] or "—",
            ]
            for item in data["objective_answers"]
        ]
        builder.add_table(
            ["Câu", "Loại câu", "Chủ đề / Bài", "Mức độ", "Đáp án", "Điểm", "Giải thích"],
            rows,
            [16, 26, 30, 20, 28, 18, 34],
            footer_rows=[
                [
                    "Tổng trắc nghiệm",
                    "",
                    "",
                    "",
                    "",
                    format_points_vi(data["objective_points"]),
                    "",
                ]
            ],
            center_cols={0, 3, 5},
        )

    if data["essay_rubrics"]:
        builder.add_rich_paragraph(
            "II. Hướng dẫn chấm & barem tự luận", bold=True, style="Heading 2"
        )
        for item in data["essay_rubrics"]:
            builder.add_rich_paragraph(
                f"Câu {item['index']} ({item['points_label']}): {item['stem']}", bold=True
            )
            step_rows = [
                [f"Ý {step['step']}", step["text"], step["points_label"]] for step in item["rubric"]
            ]
            builder.add_table(
                ["Bước", "Nội dung yêu cầu / đáp án thành phần", "Điểm"],
                step_rows,
                [20, 124, 28],
                footer_rows=[["Tổng câu", "", item["points_label"]]],
                center_cols={0, 2},
            )
            if item["explanation"]:
                builder.add_rich_paragraph(f"Ghi chú: {item['explanation']}", italic=True)

    return builder.to_bytes()


def export_matrix_specification_docx(
    exam: dict[str, Any], *, orientation: Literal["portrait", "landscape"] = "portrait"
) -> bytes:
    """Xuất DOCX chuẩn OOXML (w:tbl + m:oMath) cho Bảng Ma trận & Bảng Đặc tả cả đề."""
    data = build_matrix_and_specification(exam)
    builder = _DocxSpecBuilder(orientation=orientation)
    is_landscape = orientation == "landscape"
    if data["school"]:
        builder.add_rich_paragraph(data["school"], bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    builder.add_rich_paragraph(
        f"MA TRẬN VÀ BẢNG ĐẶC TẢ ĐỀ KIỂM TRA — {data['title']}",
        bold=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        style="Title",
    )
    meta_parts = []
    if data["subject"]:
        meta_parts.append(f"Môn: {data['subject']}")
    if data["grade"]:
        meta_parts.append(f"Lớp: {data['grade']}")
    if data["minutes"] is not None:
        meta_parts.append(f"Thời gian: {data['minutes']} phút")
    meta_parts.append(f"Tổng câu: {data['total_questions']}")
    meta_parts.append(f"Tổng điểm: {data['total_points_label']}")
    builder.add_rich_paragraph(" · ".join(meta_parts), align=WD_ALIGN_PARAGRAPH.CENTER)

    builder.add_rich_paragraph("I. Bảng ma trận đề kiểm tra", bold=True, style="Heading 2")
    matrix_rows: list[list[str]] = []
    for row in data["rows"]:
        title = (
            f"{row['topic']} [{row['choice_group']}]" if row.get("choice_group") else row["topic"]
        )
        topic_cell = f"{title}\n{row['lesson']}" if row["lesson"] else title
        level_cells = [
            f"{row['levels'][name]['count']} câu\n"
            f"({format_points_vi(row['levels'][name]['points'])})"
            if row["levels"][name]["count"] > 0
            else "—"
            for name in LEVEL_NAMES
        ]
        matrix_rows.append(
            [
                str(row["order"]),
                topic_cell,
                ", ".join(row["question_type_labels"]),
                *level_cells,
                str(row["total_questions"]),
                row["total_points_label"],
                f"{row['percentage']:.2f}%",
            ]
        )

    level_totals = [
        f"{data['by_level'][name]['count']} câu\n({data['by_level'][name]['points_label']})"
        for name in LEVEL_NAMES
    ]
    level_pcts = [f"{data['by_level'][name]['percentage']:.2f}%" for name in LEVEL_NAMES]
    builder.add_table(
        [
            "TT",
            "Chủ đề / Bài học",
            "Loại câu",
            *LEVEL_NAMES,
            "Tổng câu",
            "Tổng điểm",
            "Tỷ lệ %",
        ],
        matrix_rows,
        (
            [12, 52, 35, 25, 25, 25, 25, 18, 22, 20]
            if is_landscape
            else [10, 32, 24, 17, 17, 17, 17, 12, 14, 12]
        ),
        footer_rows=[
            [
                "Tổng",
                "Toàn đề",
                "",
                *level_totals,
                str(data["total_questions"]),
                data["total_points_label"],
                "100.00%",
            ],
            ["%", "Tỷ lệ mức độ", "", *level_pcts, "", "", "100.00%"],
        ],
        center_cols={0, 3, 4, 5, 6, 7, 8, 9},
    )

    builder.add_rich_paragraph("II. Bảng đặc tả chi tiết", bold=True, style="Heading 2")
    spec_rows = [
        [
            str(row["order"]),
            (
                f"{row['topic']} [{row['choice_group']}]\n{row['lesson']}"
                if row.get("choice_group") and row["lesson"]
                else f"{row['topic']} [{row['choice_group']}]"
                if row.get("choice_group")
                else f"{row['topic']}\n{row['lesson']}"
                if row["lesson"]
                else row["topic"]
            ),
            row["level"],
            ", ".join(row["question_types"]),
            "\n".join(row["competencies"]),
            f"{row['count']} ({', '.join(f'Câu {i}' for i in row['question_indices'])})",
            row["points_label"],
            f"{row['percentage']:.2f}%",
        ]
        for row in data["specification_rows"]
    ]
    builder.add_table(
        [
            "TT",
            "Chủ đề / Bài học",
            "Mức độ",
            "Loại câu",
            "Phạm vi năng lực / Chỉ báo đặc tả",
            "Số câu",
            "Điểm",
            "Tỷ lệ %",
        ],
        spec_rows,
        [12, 42, 26, 30, 81, 26, 21, 21] if is_landscape else [10, 28, 18, 22, 48, 18, 14, 14],
        footer_rows=[
            [
                "Tổng",
                "Toàn đề",
                "",
                "",
                "",
                f"{data['total_questions']} câu",
                data["total_points_label"],
                "100.00%",
            ]
        ],
        center_cols={0, 2, 5, 6, 7},
    )

    return builder.to_bytes()


class OCRPageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int = Field(ge=1, le=200)
    text: str = Field(max_length=200000)
    uncertain: bool = False
    needsOCR: bool | None = None
    needsReview: bool | None = None
    method: str | None = None


class OCRReadingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pages: list[OCRPageInput] = Field(min_length=1, max_length=200)
    notes: str = ""
    method: str | None = None
    sentToAI: bool | None = None
    needsReview: bool | None = None


class OCRStructureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reading: OCRReadingPayload | None = None
    pages: list[OCRPageInput] | None = Field(default=None, min_length=1, max_length=200)
    notes: str = ""
    method: str | None = None
    sentToAI: bool | None = None
    needsReview: bool | None = None


class AnswerKeyRubricRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exam: dict[str, Any]
    format: Literal["html", "docx"] | None = None
    teacher: bool = True
    audience: Literal["teacher", "student"] = "teacher"


class MatrixSpecificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exam: dict[str, Any]
    format: Literal["html", "docx"] | None = None
    orientation: Literal["portrait", "landscape"] = "portrait"


def _raise_http_for_ai_error(err: AIError) -> NoReturn:
    raise HTTPException(
        status_code=err.http_status or 422,
        detail={"error": str(err), "code": err.code},
    ) from None


def _resolve_export_format(
    body_format: Literal["html", "docx"] | None,
    query_format: Literal["html", "docx"] | None,
) -> Literal["html", "docx"]:
    if body_format is not None and query_format is not None and body_format != query_format:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Định dạng trong query và JSON body không khớp.",
                "code": "invalid_format",
            },
        )
    return body_format or query_format or "html"


def install_extended_exports(
    app: FastAPI,
    *,
    owner_resolver: Callable[[Request], str] | None = None,
) -> None:
    """Đăng ký các route mở rộng: chuẩn hóa OCR, xuất đáp án/barem và ma trận/đặc tả A4."""

    def resolve_owner(request: Request) -> str:
        return owner_resolver(request) if owner_resolver is not None else "local"

    @app.post("/api/ocr/structure")
    def ocr_structure_endpoint(body: OCRStructureRequest, request: Request) -> dict[str, Any]:
        owner_id = resolve_owner(request)
        if body.reading is not None and body.pages is not None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Chỉ truyền 'reading' hoặc 'pages', không truyền đồng thời cả hai.",
                    "code": "invalid_document_reading",
                },
            )
        if body.reading is not None:
            reading_dict = body.reading.model_dump()
        elif body.pages is not None:
            reading_dict = {
                "pages": [p.model_dump() for p in body.pages],
                "notes": body.notes,
                "method": body.method,
            }
        else:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Cần truyền danh sách trang OCR trong 'reading' hoặc 'pages'.",
                    "code": "invalid_document_reading",
                },
            )
        try:
            structured = structure_ocr_reading(reading_dict)
        except AIError as err:
            _raise_http_for_ai_error(err)
        return {**structured, "ownerId": owner_id}

    @app.post("/api/exports/answer-key-rubric")
    def answer_key_rubric_endpoint(
        body: AnswerKeyRubricRequest,
        request: Request,
        format: Literal["html", "docx"] | None = Query(default=None),
    ) -> Response:
        _ = resolve_owner(request)
        fmt = _resolve_export_format(body.format, format)
        is_teacher = body.teacher and body.audience == "teacher"
        try:
            if fmt == "html":
                content = export_answer_key_rubric_html(body.exam, teacher=is_teacher)
                return HTMLResponse(
                    content,
                    headers={
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            binary = export_answer_key_rubric_docx(body.exam, teacher=is_teacher)
            return Response(
                content=binary,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                headers={
                    "Content-Disposition": 'attachment; filename="Dap_an_barem.docx"',
                    "Cache-Control": "no-store",
                },
            )
        except AIError as err:
            _raise_http_for_ai_error(err)

    @app.post("/api/exports/matrix-specification")
    def matrix_specification_endpoint(
        body: MatrixSpecificationRequest,
        request: Request,
        format: Literal["html", "docx"] | None = Query(default=None),
    ) -> Response:
        _ = resolve_owner(request)
        fmt = _resolve_export_format(body.format, format)
        try:
            if fmt == "html":
                content = export_matrix_specification_html(body.exam, orientation=body.orientation)
                return HTMLResponse(
                    content,
                    headers={
                        "Cache-Control": "no-store",
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            binary = export_matrix_specification_docx(body.exam, orientation=body.orientation)
            return Response(
                content=binary,
                media_type=(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                headers={
                    "Content-Disposition": 'attachment; filename="Ma_tran_dac_ta.docx"',
                    "Cache-Control": "no-store",
                },
            )
        except AIError as err:
            _raise_http_for_ai_error(err)
