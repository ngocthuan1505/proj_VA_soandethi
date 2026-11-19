"""Sửa tài liệu định dạng theo vùng gốc và kiểm lại văn bản chiếu ra."""

from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

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
PARAGRAPH_PARENTS = {"doc", "blockquote", "listItem", "tableCell", "tableHeader"}


@dataclass
class Leaf:
    node: dict[str, JsonValue]
    siblings: list[JsonValue]
    index: int
    start: int
    end: int


def rich_error() -> AIError:
    return AIError("rich_document_conflict", "Hãy chọn một đoạn nhỏ để giữ định dạng và công thức.")


def child_separator(kind: str) -> str:
    return " | " if kind == "tableRow" else "\n" if kind in JOIN_LINES else ""


def project(
    node: JsonValue,
    leaves: list[Leaf],
    *,
    offset: int = 0,
    siblings: list[JsonValue] | None = None,
    index: int = 0,
    depth: int = 0,
) -> str:
    if not isinstance(node, dict) or depth > 64:
        raise rich_error()
    kind = node.get("type")
    if not isinstance(kind, str):
        raise rich_error()
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
    separator = child_separator(kind)
    parts: list[str] = []
    for child_index, child in enumerate(children):
        part = project(
            child, leaves, offset=offset, siblings=children, index=child_index, depth=depth + 1
        )
        parts.append(part)
        offset += len(part) + len(separator)
    return separator.join(parts)


def inline_slice(paragraph, start, end):
    result = []
    offset = 0
    for node in paragraph.get("content", []):
        text = project(node, [])
        next_offset = offset + len(text)
        left, right = max(start, offset), min(end, next_offset)
        if left < right:
            if left == offset and right == next_offset:
                result.append(node)
            elif node["type"] == "text":
                result.append({**node, "text": text[left - offset : right - offset]})
            else:
                raise rich_error()
        offset = next_offset
    return result


def replace_paragraphs(doc, start, end, changed):
    if MATH_DELIMITERS.search(changed):
        raise rich_error()
    blocks = doc.get("content", [])
    first = last = None
    offset = 0
    separator_length = len(child_separator(doc["type"]))
    for i, block in enumerate(blocks):
        stop = offset + len(project(block, []))
        if offset <= start <= end <= stop and block["type"] in JOIN_LINES | {"tableRow"}:
            replace_paragraphs(block, start - offset, end - offset, changed)
            return
        if offset <= start <= stop:
            first = (i, start - offset)
        if offset <= end <= stop:
            last = (i, end - offset, stop - offset)
        offset = stop + separator_length
    if doc["type"] not in PARAGRAPH_PARENTS or first is None or last is None:
        raise rich_error()
    i, left = first
    j, right, length = last
    span = blocks[i : j + 1]
    if not all(block["type"] == "paragraph" for block in span):
        raise rich_error()
    head, tail = span[0], span[-1]
    prefix, suffix = inline_slice(head, 0, left), inline_slice(tail, right, length)
    marks = prefix[-1].get("marks") if prefix else None
    result = []
    lines = changed.split("\n")
    for index, line in enumerate(lines):
        content = list(prefix) if index == 0 else []
        if line:
            node = {"type": "text", "text": line}
            if marks:
                node["marks"] = marks
            content.append(node)
        if index == len(lines) - 1:
            content.extend(suffix)
        if index == 0:
            block = {**head, "content": content}
        elif index == len(lines) - 1 and i != j:
            block = {**tail, "content": content}
        else:
            attrs = {**head.get("attrs", {}), "id": str(uuid4())}
            block = {"type": "paragraph", "attrs": attrs, "content": content}
        result.append(block)
    blocks[i : j + 1] = result


def update_rich(doc: JsonValue, target: BlockTarget, replacement: str) -> JsonValue:
    """Sửa một nút hoặc các đoạn văn liền nhau."""
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise rich_error()
    result = deepcopy(doc)
    leaves: list[Leaf] = []
    if project(result, leaves) != target.text:
        raise rich_error()

    prefix, suffix = selection_parts(target)
    if (
        len(replacement) < len(prefix) + len(suffix)
        or not replacement.startswith(prefix)
        or not replacement.endswith(suffix)
    ):
        raise rich_error()
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
    if len(candidates) != 1 or "\n" in changed:
        if any(
            leaf.node["type"] == "mathInline" and leaf.start < end and start < leaf.end
            for leaf in leaves
        ):
            raise rich_error()
        replace_paragraphs(result, start, end, changed)
    elif (leaf := candidates[0]).node["type"] == "text":
        value = target.text[leaf.start : start] + changed + target.text[end : leaf.end]
        if MATH_DELIMITERS.search(changed):
            raise rich_error()
        if value:
            leaf.node["text"] = value
        else:
            del leaf.siblings[leaf.index]
    else:
        value = target.text[leaf.start : start] + changed + target.text[end : leaf.end]
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
