"""Giới hạn và giữ định dạng đoạn do thanh công cụ lưu trong rich document."""

import math
import re

from mach_backend.ai_contract import AIError


def page_break_before(attrs):
    value = attrs.get("pageBreakBefore")
    if value is not None and type(value) is not bool:
        raise AIError("invalid_document", "Dấu ngắt trang chưa hợp lệ.")
    return value is True


def paragraph_layout(attrs):
    result = {}
    for name, low, high in (
        ("lineHeight", 0.5, 5),
        ("spaceBefore", 0, 200),
        ("spaceAfter", 0, 200),
        ("firstIndent", -5, 10),
        ("leftIndent", 0, 10),
        ("rightIndent", 0, 10),
        ("borderWidth", 0, 10),
    ):
        value = attrs.get(name)
        if value is None:
            continue
        if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high:
            raise AIError("invalid_document", "Định dạng đoạn chưa hợp lệ: " + name)
        result[name] = value
    for name in ("borderColor", "paragraphBackground"):
        value = attrs.get(name)
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise AIError("invalid_document", "Màu đoạn chưa hợp lệ.")
            result[name] = value
    if attrs.get("layoutEdited") is True:
        result["layoutEdited"] = True
    if page_break_before(attrs):
        result["pageBreakBefore"] = True
    return result


def paragraph_css(attrs):
    values = paragraph_layout(attrs)
    styles = []
    if values.get("pageBreakBefore"):
        styles.append("break-before:page;page-break-before:always")
    for name, prop, unit in (
        ("lineHeight", "line-height", ""),
        ("spaceBefore", "margin-top", "px"),
        ("spaceAfter", "margin-bottom", "px"),
        ("firstIndent", "text-indent", "cm"),
        ("leftIndent", "margin-left", "cm"),
        ("rightIndent", "margin-right", "cm"),
    ):
        if name in values:
            styles.append(f"{prop}:{values[name]}{unit}")
    if "borderWidth" in values:
        styles.append(
            f"border:{values['borderWidth']}px solid {values.get('borderColor', '#000000')}"
        )
    if values.get("paragraphBackground"):
        styles.append("background-color:" + values["paragraphBackground"])
    return ";".join(styles)
