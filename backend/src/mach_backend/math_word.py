"""MathML từ KaTeX → phương trình Word sửa được; không giữ annotation LaTeX trong bản xuất."""

import unicodedata
from xml.etree import ElementTree as ET

from mach_backend.ai_contract import AIError

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
ET.register_namespace("m", M[1:-1])


def element(name, children=(), value=None):
    node = ET.Element(M + name)
    if value is not None:
        node.set(M + "val", str(value))
    node.extend(children)
    return node


def omml(source):
    if not isinstance(source, str) or len(source) > 1_000_000 or "<!" in source:
        raise AIError("invalid_math", "Dữ liệu công thức chưa hợp lệ để xuất Word.")
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        raise AIError("invalid_math", "Chưa đọc được công thức MathML.") from None

    def run(text, variant=None, script=None):
        t = element("t")
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = text
        properties = ([element("scr", value=script)] if script else []) + (
            [element("sty", value=variant)] if variant else []
        )
        props = [element("rPr", properties)] if properties else []
        return element("r", [*props, t])

    def all_children(node):
        result = []
        for child in node:
            parts = convert(child)
            for part in parts:
                base = part.find(M + "e")
                if (
                    part.tag in {M + "sSub", M + "sSup", M + "sSubSup"}
                    and base is not None
                    and not len(base)
                    and result
                ):
                    text = result[-1].find(M + "t")
                    if (
                        result[-1].tag == M + "r"
                        and text is not None
                        and (text.text or "").isalpha()
                    ):
                        base.append(result.pop())
                result.append(part)
        return result

    def accented_text(node):
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "mtext":
            return "".join(node.itertext())
        children = list(node)
        if tag == "mover" and node.get("accent") == "true" and len(children) == 2:
            base = accented_text(children[0])
            accent = {
                "ˋ": "\u0300",
                "ˊ": "\u0301",
                "˘": "\u0306",
                "ˆ": "\u0302",
                "~": "\u0303",
            }.get("".join(children[1].itertext()))
            if base is not None and accent:
                return unicodedata.normalize("NFC", base.replace("ı", "i") + accent)
        return None

    def convert(node):
        tag = node.tag.rsplit("}", 1)[-1]
        children = [child for child in node if "".join(child.itertext()) != "\u2061"]
        if tag in {"annotation", "annotation-xml"}:
            return []
        if tag in {"mi", "mn", "mo", "mtext"}:
            value = node.get("mathvariant", "")
            variant = {"normal": "p", "bold": "b", "bold-italic": "bi"}.get(value)
            script = next(
                (
                    x
                    for x in ("double-struck", "sans-serif", "monospace", "fraktur", "script")
                    if x in value
                ),
                None,
            )
            if script:
                variant = (
                    "bi"
                    if "bold" in value and "italic" in value
                    else ("b" if "bold" in value else "i" if "italic" in value else "p")
                )
            text = "".join(node.itertext())
            if tag == "mtext" or text in {
                "sin",
                "cos",
                "tan",
                "cot",
                "log",
                "ln",
                "lim",
                "max",
                "min",
                "det",
            }:
                variant = variant or "p"
            return [run(text, variant, script)]
        if tag == "mspace":
            return [run(" ")]
        if tag in {"msup", "msub", "msubsup"}:
            if len(children) != (3 if tag == "msubsup" else 2):
                raise AIError("invalid_math", "Chỉ số/số mũ chưa hợp lệ.")
            parts = [element("e", convert(children[0]))]
            if tag != "msup":
                parts.append(element("sub", convert(children[1])))
            if tag != "msub":
                parts.append(element("sup", convert(children[-1])))
            return [element({"msup": "sSup", "msub": "sSub", "msubsup": "sSubSup"}[tag], parts)]
        if tag in {"msqrt", "mroot"}:
            return [
                element(
                    "rad",
                    [
                        element(
                            "radPr", [element("degHide", value="1" if tag == "msqrt" else "0")]
                        ),
                        element("deg", convert(children[1]) if tag == "mroot" else []),
                        element(
                            "e", convert(children[0]) if tag == "mroot" else all_children(node)
                        ),
                    ],
                )
            ]
        if tag == "mfrac":
            props = (
                [element("fPr", [element("type", value="noBar")])]
                if node.get("linethickness") in {"0", "0px"}
                else []
            )
            return [
                element(
                    "f",
                    [
                        *props,
                        element("num", convert(children[0])),
                        element("den", convert(children[1])),
                    ],
                )
            ]
        if tag == "mtable":
            rows = [
                element("mr", [element("e", all_children(cell)) for cell in row])
                for row in children
            ]
            return [element("m", rows)]
        if tag in {"mover", "munder", "munderover"}:
            if (text := accented_text(node)) is not None:
                return [run(text, "p")]
            symbol = "".join(children[1].itertext()) if len(children) > 1 else ""
            if tag in {"mover", "munder"} and symbol in {"⏞", "⏟"}:
                top = tag == "mover"
                return [
                    element(
                        "groupChr",
                        [
                            element(
                                "groupChrPr",
                                [
                                    element("chr", value=symbol),
                                    element("pos", value="top" if top else "bot"),
                                    element("vertJc", value="bot" if top else "top"),
                                ],
                            ),
                            element("e", convert(children[0])),
                        ],
                    )
                ]
            if tag == "mover" and "".join(children[1].itertext()) in {
                "→",
                "¯",
                "^",
                "ˆ",
                "˙",
                "¨",
                "⏞",
            }:
                return [
                    element(
                        "acc",
                        [
                            element(
                                "accPr", [element("chr", value="".join(children[1].itertext()))]
                            ),
                            element("e", convert(children[0])),
                        ],
                    )
                ]
            base = convert(children[0])
            if tag in {"munder", "munderover"}:
                base = [
                    element("limLow", [element("e", base), element("lim", convert(children[1]))])
                ]
            if tag in {"mover", "munderover"}:
                base = [
                    element("limUpp", [element("e", base), element("lim", convert(children[-1]))])
                ]
            return base
        if tag == "menclose":
            if node.get("notation") not in {None, "box"}:
                raise AIError("unsupported_math", "Kiểu khung công thức chưa hỗ trợ trong Word.")
            return [element("borderBox", [element("e", all_children(node))])]
        if tag == "mphantom":
            # mhchem dùng phantom chỉ để căn chỉ số; không xuất chữ X giữ chỗ.
            return []
        if tag in {"math", "semantics", "mrow", "mstyle", "mpadded"}:
            if tag == "mrow" and len(children) >= 2 and children[0].get("fence") == "true":
                closed = children[-1].get("fence") == "true"
                inside = children[1:-1] if closed else children[1:]
                return [
                    element(
                        "d",
                        [
                            element(
                                "dPr",
                                [
                                    element("begChr", value="".join(children[0].itertext())),
                                    element(
                                        "endChr",
                                        value="".join(children[-1].itertext()) if closed else "",
                                    ),
                                ],
                            ),
                            element("e", [p for child in inside for p in convert(child)]),
                        ],
                    )
                ]
            return all_children(node)
        raise AIError("unsupported_math", "Word chưa chuyển được ký hiệu MathML: " + tag)

    return element("oMath", convert(root))
