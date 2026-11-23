"""7 lớp bọc an toàn AI: chống prompt injection, lọc XSS, ẩn khóa, vá LaTeX JSON, trần chi phí."""

from __future__ import annotations

import html
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
    re.compile(r"AQ\.[A-Za-z0-9._\-]{12,}"),
)

DEEPSEEK_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input_per_1m": 0.27, "output_per_1m": 1.10},
    "deepseek-reasoner": {"input_per_1m": 0.55, "output_per_1m": 2.19},
    "deepseek-v4.1-flash": {"input_per_1m": 0.14, "output_per_1m": 0.28},
    "deepseek-v4-pro": {"input_per_1m": 0.55, "output_per_1m": 2.19},
    "qwen3.8-max": {"input_per_1m": 0.40, "output_per_1m": 1.20},
    "qwen3.8-flash": {"input_per_1m": 0.08, "output_per_1m": 0.24},
    "gemini-3.8-flash": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gemini-3.6-flash": {"input_per_1m": 0.10, "output_per_1m": 0.40},
}


def _strip_wrapping_quotes(value: str) -> str:
    cleaned = value.strip()
    while len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def extract_api_key_token(raw: str) -> str:
    """Bóc ngoặc/khoảng trắng và tách phần khóa sau dấu ':' nếu có nhãn tài khoản."""
    if not isinstance(raw, str):
        return ""
    cleaned = _strip_wrapping_quotes(raw)
    if ":" in cleaned:
        _, candidate = cleaned.rsplit(":", 1)
        candidate = _strip_wrapping_quotes(candidate)
        if candidate.startswith(("AQ.", "AIza", "sk-")):
            return candidate
    return cleaned


def normalize_openai_base_url(url: str) -> str:
    """Chuẩn hóa URL cổng API OpenAI-compatible; chỉ chấp nhận HTTPS hoặc localhost/127.0.0.1."""
    if not isinstance(url, str) or "\r" in url or "\n" in url:
        raise AIError("invalid_endpoint", "Địa chỉ cổng API phải dùng HTTPS hợp lệ.")
    cleaned = _strip_wrapping_quotes(url)
    if not cleaned or any(ch.isspace() for ch in cleaned):
        raise AIError("invalid_endpoint", "Địa chỉ cổng API phải dùng HTTPS hợp lệ.")
    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if parsed.query or parsed.fragment or not hostname:
        raise AIError("invalid_endpoint", "Địa chỉ cổng API phải dùng HTTPS hợp lệ.")
    try:
        _ = parsed.port
    except ValueError:
        raise AIError("invalid_endpoint", "Địa chỉ cổng API phải dùng HTTPS hợp lệ.") from None
    if scheme == "https":
        pass
    elif scheme == "http" and hostname in {"127.0.0.1", "localhost"}:
        pass
    else:
        raise AIError("invalid_endpoint", "Địa chỉ cổng API phải dùng HTTPS hợp lệ.")

    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[: -len("/chat/completions")].rstrip("/")
    if not (path == "/v1" or path.endswith("/v1") or "/v1/" in path):
        path = f"{path}/v1" if path else "/v1"
    return f"{scheme}://{parsed.netloc}{path}"


def load_local_secrets_env(
    path: Path | None = None, *, allow_in_pytest: bool = False
) -> dict[str, Any]:
    """Đọc cấu hình bí mật cục bộ từ tệp .env (chỉ nạp ngoài pytest trừ khi bật allow_in_pytest)."""
    if not allow_in_pytest and os.environ.get("PYTEST_CURRENT_TEST"):
        return {}
    if path is not None:
        target = Path(path)
    elif os.environ.get("MACH_SECRETS_FILE"):
        target = Path(os.environ["MACH_SECRETS_FILE"])
    else:
        target = Path.home() / ".mach-secrets" / "api-keys.env"
    if not target.is_file():
        return {}
    try:
        raw_text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    entries: dict[str, str] = {}
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key_part, val_part = line.split("=", 1)
        env_key = key_part.strip()
        if not env_key:
            continue
        entries[env_key] = _strip_wrapping_quotes(val_part)

    result: dict[str, Any] = {}

    gemini_raw_tokens: list[str] = []
    for idx in range(1, 9):
        val = entries.get(f"GEMINI_KEY_{idx}", "")
        if val:
            gemini_raw_tokens.append(val)
    bulk_gemini = entries.get("GEMINI_API_KEYS", "")
    if bulk_gemini:
        for line in bulk_gemini.replace("\\n", "\n").splitlines():
            for part in line.split(","):
                if part.strip():
                    gemini_raw_tokens.append(part.strip())

    gemini_keys: list[str] = []
    for token in gemini_raw_tokens:
        extracted = extract_api_key_token(token)
        if 8 <= len(extracted) <= 300 and "\r" not in extracted and "\n" not in extracted:
            if extracted not in gemini_keys:
                gemini_keys.append(extracted)
        if len(gemini_keys) >= 8:
            break
    if gemini_keys:
        result["geminiKeys"] = tuple(gemini_keys)

    base_url = entries.get("AI_GATEWAY_BASE_URL", "")
    if base_url:
        try:
            result["gatewayBaseUrl"] = normalize_openai_base_url(base_url)
        except AIError:
            pass

    gateway_key = entries.get("AI_GATEWAY_API_KEY", "")
    if gateway_key:
        extracted_gw = extract_api_key_token(gateway_key)
        if 8 <= len(extracted_gw) <= 300 and "\r" not in extracted_gw and "\n" not in extracted_gw:
            result["gatewayApiKey"] = extracted_gw

    for env_name, field_name in (
        ("AI_GATEWAY_FAST_MODEL", "gatewayFastModel"),
        ("AI_GATEWAY_PRO_MODEL", "gatewayProModel"),
        ("AI_GATEWAY_CROSS_MODEL", "gatewayCrossModel"),
    ):
        model_val = entries.get(env_name, "").strip()
        if model_val:
            result[field_name] = model_val

    backup_raw = entries.get("AI_GATEWAY_BACKUP_MODELS", "")
    if backup_raw:
        backups = tuple(
            dict.fromkeys(part.strip() for part in backup_raw.split(",") if part.strip())
        )
        if backups:
            result["gatewayBackupModels"] = backups

    for env_name, field_name, min_val, max_val in (
        ("AI_GATEWAY_SESSION_LIMIT_USD", "gatewaySessionLimitUsd", 0.05, 30.0),
        ("AI_GATEWAY_TOTAL_LIMIT_USD", "gatewayTotalLimitUsd", 0.10, 30.0),
    ):
        raw_num = entries.get(env_name, "").strip()
        if raw_num:
            try:
                num = float(raw_num)
                if min_val <= num <= max_val:
                    result[field_name] = round(num, 4)
            except ValueError:
                pass

    return result


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
