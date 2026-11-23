"""7 lớp bọc an toàn AI: chống prompt injection, lọc XSS, ẩn khóa, vá LaTeX JSON, trần chi phí."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Sequence
from typing import Any

from mach_backend.ai_contract import AIError

LATEX_COMMANDS = (
    "frac",
    "sqrt",
    "alpha",
    "beta",
    "gamma",
    "delta",
    "Delta",
    "pi",
    "omega",
    "Omega",
    "sigma",
    "theta",
    "lambda",
    "mu",
    "cdot",
    "times",
    "div",
    "pm",
    "mp",
    "leq",
    "geq",
    "neq",
    "approx",
    "infty",
    "text",
    "mathrm",
    "mathbf",
    "left",
    "right",
    "begin",
    "end",
    "overline",
    "underline",
    "vec",
    "hat",
    "int",
    "sum",
    "prod",
    "lim",
    "sin",
    "cos",
    "tan",
    "log",
    "ln",
)

_LATEX_ESCAPE_RE = re.compile(r"(?<!\\)\\(?=(?:" + "|".join(LATEX_COMMANDS) + r")(?![A-Za-z]))")
_INVALID_JSON_ESCAPE_RE = re.compile(r"(?<!\\)\\(?![/\"\\bfnrtu])")

_INJECTION_PATTERNS = (
    re.compile(r"</?\s*untrusted_source_document[^>]*>", re.IGNORECASE),
    re.compile(r"IGNORE\s+ALL\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"IGNORE\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"DISREGARD\s+ALL\s+PREVIOUS\s+INSTRUCTIONS", re.IGNORECASE),
    re.compile(r"BỎ\s+QUA\s+MỌI\s+CHỈ\s+DẪN\s+TRƯỚC", re.IGNORECASE),
    re.compile(r"BỎ\s+QUA\s+CÁC\s+CHỈ\s+DẪN\s+TRƯỚC", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
)

_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_SCRIPT_TAG_RE = re.compile(r"</?\s*script\b[^>]*>", re.IGNORECASE)
_JS_PROTO_RE = re.compile(r"(?:javascript|vbscript)\s*:", re.IGNORECASE)

_SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{16,}"),
)

DEEPSEEK_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input_per_1m": 0.27, "output_per_1m": 1.10},
    "deepseek-reasoner": {"input_per_1m": 0.55, "output_per_1m": 2.19},
}


def wrap_untrusted_source(text: str, *, source_id: str = "", locator: str = "") -> str:
    """Bọc tài liệu nguồn vào thẻ cách ly và vô hiệu hóa mẫu prompt injection."""
    cleaned = str(text or "")
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[filtered_directive]", cleaned)
    safe_id = html.escape(str(source_id or ""), quote=True)
    safe_locator = html.escape(str(locator or ""), quote=True)
    return (
        f'<untrusted_source_document id="{safe_id}" locator="{safe_locator}">\n'
        f"{cleaned}\n"
        f"</untrusted_source_document>"
    )


def sanitize_ai_output_text(text: str) -> str:
    """Loại bỏ thẻ script và giao thức javascript:/vbscript: khỏi văn bản AI trả về."""
    cleaned = str(text or "")
    cleaned = _SCRIPT_BLOCK_RE.sub("", cleaned)
    cleaned = _SCRIPT_TAG_RE.sub("", cleaned)
    cleaned = _JS_PROTO_RE.sub("", cleaned)
    return cleaned


def redact_secrets(payload: Any, extra_secrets: Sequence[str] = ()) -> Any:
    """Quét đệ quy dict/list/tuple/str và thay khóa bí mật bằng [REDACTED]."""
    valid_secrets = tuple(
        s.strip() for s in extra_secrets if isinstance(s, str) and len(s.strip()) >= 8
    )
    return _redact_value(payload, valid_secrets)


def _redact_value(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {k: _redact_value(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, secrets) for item in value)
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED]")
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def sanitize_json_latex_escapes(raw_json: str) -> str:
    """Tự động nhân đôi dấu \\ đơn lẻ trước các lệnh LaTeX trong JSON khi model quên escape."""
    if not isinstance(raw_json, str):
        return str(raw_json or "")
    has_raw_latex = bool(_LATEX_ESCAPE_RE.search(raw_json))
    if not has_raw_latex:
        try:
            json.loads(raw_json)
            return raw_json
        except json.JSONDecodeError:
            pass
    candidate = _LATEX_ESCAPE_RE.sub(r"\\\\", raw_json)
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass
    fallback = _INVALID_JSON_ESCAPE_RE.sub(r"\\\\", candidate)
    try:
        json.loads(fallback)
        return fallback
    except json.JSONDecodeError:
        return raw_json


class CostTracker:
    """Theo dõi và chặn trần chi phí USD theo phiên và tổng tích lũy cho DeepSeek."""

    def __init__(
        self,
        session_limit_usd: float = 0.50,
        total_limit_usd: float = 5.00,
        initial_total_usd: float = 0.0,
    ) -> None:
        self.session_limit_usd = float(session_limit_usd)
        self.total_limit_usd = float(total_limit_usd)
        self.session_spent_usd = 0.0
        self.total_spent_usd = float(initial_total_usd)

    def check_available(self) -> None:
        if (
            self.session_spent_usd >= self.session_limit_usd
            or self.total_spent_usd >= self.total_limit_usd
        ):
            raise AIError(
                "cost_budget",
                "Đã chạm trần chi phí DeepSeek an toàn; tự động chuyển sang kênh dự phòng.",
            )

    def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = DEEPSEEK_PRICING.get(model, DEEPSEEK_PRICING["deepseek-chat"])
        p_tokens = max(0, int(prompt_tokens or 0))
        c_tokens = max(0, int(completion_tokens or 0))
        cost_usd = (
            p_tokens * pricing["input_per_1m"] + c_tokens * pricing["output_per_1m"]
        ) / 1_000_000.0
        self.session_spent_usd += cost_usd
        self.total_spent_usd += cost_usd
        return cost_usd
