"""Chỉ đưa nội dung được chọn vào bản chia sẻ; không sao chép toàn workspace."""

import base64
import json
import math
import re

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer
from mach_backend.paragraph_format import page_break_before, paragraph_layout
from mach_backend.word_export import field_document, image_bytes, uses_table


def fields(value, names):
    result = {}
    for name in names.split():
        if name in value:
            item = value[name]
            if item is not None and type(item) not in {str, int, float, bool}:
                raise AIError("invalid_document", "Trường nội dung chưa hợp lệ: " + name)
            if isinstance(item, float) and not math.isfinite(item):
                raise AIError("invalid_document", "Số trong nội dung phải hữu hạn.")
            result[name] = item
    return result


def rich_copy(node, *, depth=0, budget=None):
    if node is None:
        return None
    budget = budget if budget is not None else [50000]
    budget[0] -= 1
    if not isinstance(node, dict) or depth > 64 or budget[0] < 0:
        raise AIError("export_limit", "Rich document không hợp lệ hoặc lồng quá sâu.")
    result = fields(node, "type text")
    attrs = node.get("attrs")
    if attrs:
        result["attrs"] = fields(attrs, "textAlign level start colspan rowspan latex display")
        if page_break_before(attrs):
            result["attrs"]["pageBreakBefore"] = True
        if node.get("type") in {"paragraph", "heading"}:
            result["attrs"].update(paragraph_layout(attrs))
        if "colwidth" in attrs and attrs["colwidth"] is not None:
            widths = attrs["colwidth"]
            if (
                not isinstance(widths, list)
                or len(widths) > 20
                or any(type(n) is not int or not 0 <= n <= 10000 for n in widths)
            ):
                raise AIError("invalid_table", "Độ rộng cột chưa hợp lệ.")
            result["attrs"]["colwidth"] = widths[:]
    if "content" in node:
        result["content"] = [
            rich_copy(child, depth=depth + 1, budget=budget) for child in node["content"]
        ]
    if "marks" in node:
        result["marks"] = []
        for mark in node["marks"]:
            kind = mark["type"]
            if kind not in {
                "bold",
                "italic",
                "underline",
                "strike",
                "textStyle",
                "highlight",
                "link",
            }:
                raise AIError(
                    "unsupported_document", "Kiểu định dạng chưa chia sẻ được: " + str(kind)
                )
            names = {
                "textStyle": "color fontFamily fontSize script",
                "highlight": "color",
                "link": "href",
            }.get(kind, "")
            attrs = fields(mark.get("attrs") or {}, names)
            if "script" in attrs and attrs["script"] not in {"super", "sub"}:
                raise AIError("invalid_document", "Chỉ số chữ chưa hợp lệ.")
            if "color" in attrs and (
                not isinstance(attrs["color"], str)
                or not re.fullmatch(r"#[0-9a-fA-F]{6}", attrs["color"])
            ):
                raise AIError("invalid_document", "Màu chữ hoặc nền chưa hợp lệ để chia sẻ.")
            if "fontSize" in attrs and (
                not isinstance(attrs["fontSize"], str)
                or not re.fullmatch(r"\d{1,2}(?:\.\d)?(?:px|pt)", attrs["fontSize"])
            ):
                raise AIError("invalid_document", "Cỡ chữ chưa hợp lệ để chia sẻ.")
            if kind == "link" and not re.match(r"https?://", attrs.get("href", "")):
                raise AIError(
                    "invalid_document", "Liên kết trong nội dung cần bắt đầu bằng http/https."
                )
            result["marks"].append({"type": kind, **({"attrs": attrs} if attrs else {})})
    return result


def figure_copy(spec):
    result = fields(spec, "caption width align")
    result["points"] = {
        name: fields(point, "x y") if isinstance(point, dict) else point
        for name, point in spec["points"].items()
    }
    for key, allowed in (("constraints", "name type point"), ("objects", "type dashed")):
        result[key] = []
        for item in spec.get(key, []):
            if isinstance(item, str):
                result[key].append(item)
            else:
                entry = fields(item, allowed)
                for ref in ("points", "line"):
                    if ref in item:
                        if not isinstance(item[ref], list) or any(
                            not isinstance(n, str) for n in item[ref]
                        ):
                            raise AIError("invalid_document", "Tên điểm chưa hợp lệ.")
                        entry[ref] = item[ref][:]
                result[key].append(entry)
    result["conditions"] = list(spec.get("conditions", []))
    result["labels"] = {
        name: position
        for name, position in spec.get("labels", {}).items()
        if re.fullmatch(r"[A-Z][A-Za-z0-9_]{0,8}", name)
        and position in {"above", "below", "left", "right"}
    }
    return result


def snapshot(exam, answers):
    try:
        result = fields(exam, "id revision title school subject grade minutes instructions updated")
        if exam.get("bodyText") or exam.get("bodyTextDoc"):
            result["bodyText"] = str(exam.get("bodyText", ""))
            result["bodyTextDoc"] = rich_copy(
                field_document(exam.get("bodyText", ""), exam.get("bodyTextDoc"))
            )
        result.update(
            layout=fields(exam.get("layout") or {}, "font fontSize"),
            quote={"text": exam.get("quote", {}).get("text", ""), "chosen": None, "versions": []},
            data=[fields(row, "id label value unit") for row in exam.get("data", [])]
            if any(uses_table(q) for q in exam["questions"])
            else [],
            questions=[],
            docs=[],
            chat=[],
            history=[],
            undo=[],
            redo=[],
            appliedPrefs=[],
            matrix=[],
            matrixConfirmed=False,
        )
        if len(exam["questions"]) > 300:
            raise AIError("export_limit", "Đề vượt giới hạn 300 câu.")
        for original in exam["questions"]:
            q = fields(original, "id v type stem points topic level pageBreak")
            q.update(answer=None, answerKnown=False, explanation="", rubric=[], check=None)
            if uses_table(original):
                q["dataLinked"] = True
            q["options"] = original.get("options", [])[:]
            if any(not isinstance(text, str) for text in q["options"]):
                raise AIError("invalid_document", "Phương án cần là văn bản.")
            q["richDoc"] = rich_copy(
                field_document(original.get("stem"), original.get("richDoc"), original.get("runs"))
            )
            if answers and original.get("explanationDoc"):
                q["explanationDoc"] = rich_copy(original["explanationDoc"])
            if "optionDocs" in original:
                q["optionDocs"] = [rich_copy(doc) for doc in original["optionDocs"] or []]
            q["formulas"] = [fields(f, "id latex display") for f in original.get("formulas", [])]
            q["tables"] = []
            for table in original.get("tables", []):
                rows = []
                for row in table.get("rows", []):
                    if any(type(cell) not in {str, float, int} for cell in row):
                        raise AIError("invalid_table", "Ô bảng cần là chữ hoặc số.")
                    rows.append([str(cell) for cell in row])
                q["tables"].append({"rows": rows})
            q["images"] = []
            for image in original.get("images", []):
                binary, _, _ = image_bytes(image.get("data"))
                q["images"].append(
                    {
                        **fields(image, "id caption"),
                        "data": "data:image/png;base64," + base64.b64encode(binary).decode(),
                    }
                )
            if original.get("figure"):
                q["figure"] = figure_copy(original["figure"])
            if answers:
                answer = saved_answer(original)
                q.update(fields(original, "answerKnown explanation"))
                q["answerKnown"] = answer is not None
                q["answer"] = answer if q.get("type", "mcq") == "mcq" else 0
                if q.get("type") == "short":
                    q["answerText"] = answer or ""
                elif q.get("type") == "truefalse":
                    q["truthValues"] = list(answer) if isinstance(answer, tuple) else []
                q["rubric"] = [
                    {
                        **fields(step, "id text points"),
                        **({"richDoc": rich_copy(step["richDoc"])} if step.get("richDoc") else {}),
                    }
                    for step in original.get("rubric", [])
                ]
                if original.get("approval"):
                    q["approval"] = fields(original["approval"], "version status")
            result["questions"].append(q)
        if len(json.dumps(result, ensure_ascii=False, allow_nan=False)) > 25_000_000:
            raise AIError("export_limit", "Bản chia sẻ vượt 25 MB.")
        return result
    except AIError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
        raise AIError("invalid_document", "Nội dung chưa hợp lệ để chia sẻ.") from None
