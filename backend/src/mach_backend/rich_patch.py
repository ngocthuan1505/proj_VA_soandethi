"""Sửa một nút rich text theo vùng gốc và kiểm lại văn bản chiếu ra."""

from copy import deepcopy
from dataclasses import dataclass

from pydantic import JsonValue

from mach_backend.ai_contract import MATH_DELIMITERS, AIError, BlockTarget, selection_parts

JOIN_LINES = {
    "doc",
    "blockquote",
    "listItem",
    "bulletList",
    "orderedList",
    "table",
    "tableCell",
    "tableHeader",
}


@dataclass
class Leaf:
    node: dict[str, JsonValue]
    siblings: list[JsonValue]
    index: int
    start: int
    end: int


def rich_error() -> AIError:
    return AIError("rich_document_conflict", "Hãy chọn một đoạn nhỏ để giữ định dạng và công thức.")


def project(
    node: JsonValue,
    leaves: list[Leaf],
    *,
    offset: int = 0,
    siblings: list[JsonValue] | None = None,
    index: int = 0,
    depth: int = 0,
) -> str:
    if not isinstance(node, dict) or depth > 64 or not isinstance(node.get("type"), str):
        raise rich_error()
    kind = node["type"]
    if kind == "hardBreak":
        return "\n"
    if kind in ("text", "mathInline"):
        if kind == "text":
            text = node.get("text")
            if not isinstance(text, str) or not text:
                raise rich_error()
        else:
            attrs = node.get("attrs")
            if not isinstance(attrs, dict):
                raise rich_error()
            latex = attrs.get("latex")
            if not isinstance(latex, str) or not latex:
                raise rich_error()
            marker = "$$" if attrs.get("display") else "$"
            text = marker + latex + marker
        if siblings is not None:
            leaves.append(Leaf(node, siblings, index, offset, offset + len(text)))
        return text

    children = node.get("content", [])
    if not isinstance(children, list):
        raise rich_error()
    separator = " | " if kind == "tableRow" else "\n" if kind in JOIN_LINES else ""
    parts: list[str] = []
    for child_index, child in enumerate(children):
        part = project(
            child, leaves, offset=offset, siblings=children, index=child_index, depth=depth + 1
        )
        parts.append(part)
        offset += len(part) + len(separator)
    return separator.join(parts)


def update_rich(doc: JsonValue, target: BlockTarget, replacement: str) -> JsonValue:
    """Sửa chữ trong một run hoặc LaTeX của một nút công thức đã có."""
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise rich_error()
    result = deepcopy(doc)
    leaves: list[Leaf] = []
    if project(result, leaves) != target.text:
        raise rich_error()

    prefix, suffix = selection_parts(target)
    start, end = len(prefix), len(target.text) - len(suffix)
    original = target.text[start:end]
    revised = replacement[start : len(replacement) - len(suffix)]
    left = 0
    while left < min(len(original), len(revised)) and original[left] == revised[left]:
        left += 1
    right = 0
    while (
        right < min(len(original), len(revised)) - left
        and original[-1 - right] == revised[-1 - right]
    ):
        right += 1
    start += left
    end -= right
    changed = revised[left : len(revised) - right]
    candidates = [leaf for leaf in leaves if leaf.start <= start <= end <= leaf.end]
    if len(candidates) != 1:
        raise rich_error()
    leaf = candidates[0]
    value = target.text[leaf.start : start] + changed + target.text[end : leaf.end]

    if leaf.node["type"] == "text":
        if MATH_DELIMITERS.search(changed):
            raise rich_error()
        if value:
            leaf.node["text"] = value
        else:
            del leaf.siblings[leaf.index]
    else:
        attrs = leaf.node["attrs"]
        if not isinstance(attrs, dict):
            raise rich_error()
        marker = "$$" if attrs.get("display") else "$"
        latex = value[len(marker) : -len(marker)]
        if (
            not value.startswith(marker)
            or not value.endswith(marker)
            or not latex.strip()
            or MATH_DELIMITERS.search(latex)
        ):
            raise rich_error()
        attrs["latex"] = latex

    if project(result, []) != replacement:
        raise rich_error()
    return result
