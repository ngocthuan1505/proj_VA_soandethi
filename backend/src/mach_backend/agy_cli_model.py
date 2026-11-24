"""Hộp cát Lớp 1 cho AGY CLI: thư mục tạm rỗng, lọc biến môi trường và diệt tiến trình."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from mach_backend.ai_contract import AIError
from mach_backend.ai_router import structured_tool_request, structured_tool_response
from mach_backend.ai_safety import redact_secrets, sanitize_json_latex_escapes

SAFE_ENV_KEYS = (
    "SYSTEMROOT",
    "WINDIR",
    "PATH",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "APPDATA",
    "LANG",
    "LC_ALL",
)

_FORBIDDEN_ENV_SUBSTRINGS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "DEEPSEEK",
    "GEMINI",
)

_ALLOWED_EXE_NAMES = {"agy", "agy.exe", "agy.cmd", "agy.bat"}
VALID_EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
_VALID_AGY_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_ENVELOPE_KEYS = ("response", "result", "content", "text", "output")
_DOMAIN_PAYLOAD_KEYS = {
    "message",
    "questions",
    "reviews",
    "edits",
    "pages",
    "slots",
    "matrix",
    "stem",
    "action",
    "arguments",
}


def _is_windows() -> bool:
    return os.name == "nt"


def detect_agy_cli(custom_path: str = "") -> str | None:
    """Phát hiện đường dẫn thực thi AGY CLI hợp lệ trên máy."""
    cleaned = str(custom_path or "").strip()
    if cleaned:
        candidate = Path(cleaned)
        if candidate.is_file() and candidate.name.lower() in _ALLOWED_EXE_NAMES:
            return str(candidate.resolve())
        return None
    found = shutil.which("agy")
    if found:
        return found
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        local_candidate = Path(local_app) / "agy" / "bin" / "agy.exe"
        if local_candidate.is_file():
            return str(local_candidate.resolve())
    home_candidate = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe"
    if home_candidate.is_file():
        return str(home_candidate.resolve())
    return None


def build_sanitized_env(source_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Chỉ giữ các biến môi trường hệ thống tối thiểu và tước bỏ hoàn toàn khóa/token bí mật."""
    env_map = os.environ if source_env is None else source_env
    allowed = {k.upper() for k in SAFE_ENV_KEYS}
    sanitized: dict[str, str] = {}
    for key, value in env_map.items():
        upper = key.upper()
        if upper not in allowed:
            continue
        if any(token in upper for token in _FORBIDDEN_ENV_SUBSTRINGS):
            continue
        sanitized[key] = str(value)
    return sanitized


def _decode_json_stream(text: str) -> list[dict[str, Any]]:
    """Giải mã chuỗi chứa một hoặc nhiều JSON object nối tiếp nhau trên stdout."""
    decoder = json.JSONDecoder()
    best: list[dict[str, Any]] = []
    for candidate in (text, sanitize_json_latex_escapes(text)):
        parsed_list: list[dict[str, Any]] = []
        pos = 0
        n = len(candidate)
        while pos < n:
            while pos < n and candidate[pos].isspace():
                pos += 1
            if pos >= n:
                break
            try:
                obj, next_pos = decoder.raw_decode(candidate, pos)
            except ValueError:
                next_brace = candidate.find("{", pos + 1)
                if next_brace < 0:
                    break
                pos = next_brace
                continue
            pos = next_pos
            if isinstance(obj, dict):
                parsed_list.append(obj)
        if len(parsed_list) > len(best):
            best = parsed_list
    return best


def _score_domain_dict(obj: dict[str, Any], schema_keys: set[str]) -> tuple[int, int, int] | None:
    domain_keys = schema_keys | _DOMAIN_PAYLOAD_KEYS
    hits = len(domain_keys.intersection(obj.keys()))
    if not hits:
        return None
    has_msg = 1 if isinstance(obj.get("message"), str) and bool(obj["message"].strip()) else 0
    return (has_msg, hits, len(obj))


def _unwrap_cli_envelope(text: str, expected_schema: dict[str, Any] | None) -> str:
    if not text.startswith("{"):
        return text
    schema_keys: set[str] = set()
    if isinstance(expected_schema, dict):
        props = expected_schema.get("properties")
        if isinstance(props, dict):
            schema_keys = set(props.keys())
    objects = _decode_json_stream(text)
    if not objects:
        return text
    candidates: list[dict[str, Any]] = []
    for obj in objects:
        candidates.append(obj)
        for key in _ENVELOPE_KEYS:
            inner = obj.get(key)
            if isinstance(inner, dict):
                candidates.append(inner)
            elif isinstance(inner, str) and "{" in inner:
                candidates.extend(_decode_json_stream(inner))
    best_obj: dict[str, Any] | None = None
    best_score: tuple[int, int, int] | None = None
    for item in candidates:
        score = _score_domain_dict(item, schema_keys)
        if score is not None and (best_score is None or score > best_score):
            best_score = score
            best_obj = item
    if best_obj is not None:
        return json.dumps(best_obj, ensure_ascii=False)
    for obj in objects:
        for key in _ENVELOPE_KEYS:
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False)
    return json.dumps(objects[0], ensure_ascii=False) if len(objects) > 1 else text


def _extract_output_content(
    raw_stdout: str,
    expect_json: bool,
    expected_schema: dict[str, Any] | None = None,
) -> str:
    text = raw_stdout.strip()
    text = _unwrap_cli_envelope(text, expected_schema)
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
        text = _unwrap_cli_envelope(text, expected_schema)
    elif expect_json and not text.startswith(("{", "[")):
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if 0 <= start_obj < end_obj:
            text = _unwrap_cli_envelope(text[start_obj : end_obj + 1], expected_schema)
    if text.startswith("{"):
        text = _unwrap_cli_envelope(text, expected_schema)
    if text.startswith(("{", "[")):
        text = sanitize_json_latex_escapes(text)
    return str(redact_secrets(text))


class AgyCliModel:
    """Adapter gọi AGY CLI trong hộp cát thư mục tạm trống, không cấp quyền ghi repo hay lộ env."""

    def __init__(
        self,
        log: Any,
        *,
        custom_path: str = "",
        budget: Any = None,
        timeout_seconds: int = 180,
        runner: Callable[..., Any] | None = None,
        effort: str | None = None,
        model: str | None = None,
    ) -> None:
        self.log = log
        self.custom_path = custom_path
        self.budget = budget
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.runner = runner
        cleaned_effort = str(effort).strip().lower() if isinstance(effort, str) else ""
        self.effort: str | None = cleaned_effort if cleaned_effort in VALID_EFFORT_LEVELS else None
        cleaned_model = str(model).strip() if isinstance(model, str) else ""
        self.model: str | None = cleaned_model or None

    def _build_prompt(self, purpose: str, body: dict[str, Any]) -> str:
        parts = [
            "[CHẾ ĐỘ HỘP CÁT CHỈ ĐỌC - KHÔNG CHẠY LỆNH HỆ THỐNG - KHÔNG GHI TỆP]",
            f"Tác vụ: {purpose}",
        ]
        for msg in body.get("messages", []):
            role = str(msg.get("role", "user")).upper()
            content = str(msg.get("content", ""))
            parts.append(f"[{role}]\n{content}")
        if "format" in body:
            schema_text = json.dumps(body["format"], ensure_ascii=False)
            parts.append(
                "[YÊU CẦU ĐẦU RA]\n"
                "Chỉ trả về đúng một chuỗi JSON hợp lệ khớp hoàn toàn với JSON Schema sau, "
                "không bọc markdown, không giải thích ngoài JSON:\n" + schema_text
            )
        return "\n\n".join(parts)

    async def __call__(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        exe = detect_agy_cli(self.custom_path)
        if not exe:
            raise AIError(
                "provider_unconfigured",
                "Chưa tìm thấy AGY CLI trên máy; tự động chuyển sang kênh dự phòng.",
            )
        if self.budget is not None:
            self.budget.spend()

        eff_timeout = self.timeout_seconds
        if self.budget is not None and hasattr(self.budget, "remaining"):
            eff_timeout = max(5, min(self.timeout_seconds, int(self.budget.remaining())))

        raw_req_model = str(body.get("model") or "").strip() if isinstance(body, dict) else ""
        effective_model = self.model
        if (
            raw_req_model
            and raw_req_model != "agy-cli"
            and _VALID_AGY_MODEL_RE.fullmatch(raw_req_model)
        ):
            effective_model = raw_req_model
        model_label = effective_model or "agy-cli"

        has_tools = isinstance(body, dict) and bool(body.get("tools"))
        allowed_tools = (
            [
                t["function"]["name"]
                for t in body.get("tools", [])
                if isinstance(t, dict)
                and isinstance(t.get("function"), dict)
                and t["function"].get("name")
            ]
            if has_tools
            else []
        )
        effective_body = structured_tool_request(body) if has_tools else body

        prompt_text = self._build_prompt(purpose, effective_body)
        prompt_bytes = prompt_text.encode("utf-8")
        sanitized_env = build_sanitized_env()

        if self.log is not None:
            self.log.index += 1
            index = self.log.index
            self.log.write(
                f"call-{index:02}-request.json",
                redact_secrets({"purpose": purpose, "provider": "agy", "body": effective_body}),
            )
            self.log.emit(
                "model_start",
                modelCall=index,
                purpose=purpose,
                model=model_label,
                provider="agy",
            )
        else:
            index = 1

        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(
                prefix="mach-agy-sandbox-", ignore_cleanup_errors=True
            ) as sandbox_dir:
                if len(prompt_text) > 5500:
                    cli_prompt = (
                        "Xử lý yêu cầu đầy đủ được truyền qua stdin và trả đúng định dạng yêu cầu."
                    )
                    stdin_bytes = prompt_bytes
                else:
                    cli_prompt = prompt_text
                    stdin_bytes = b""
                cmd = [
                    exe,
                    "-p",
                    cli_prompt,
                    "--output-format",
                    "json",
                    "--mode",
                    "plan",
                    "--sandbox",
                    "--disable-slash-commands",
                    "--print-timeout",
                    f"{eff_timeout}s",
                ]
                if self.effort in VALID_EFFORT_LEVELS:
                    cmd.extend(["--effort", self.effort])
                if effective_model:
                    cmd.extend(["--model", effective_model])
                expected_schema = (
                    effective_body.get("format")
                    if isinstance(effective_body.get("format"), dict)
                    else None
                )
                if expected_schema is not None:
                    schema_path = Path(sandbox_dir) / "schema.json"
                    schema_path.write_text(
                        json.dumps(expected_schema, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    cmd.extend(["--json-schema", str(schema_path)])
                run_fn = self.runner or subprocess.run
                try:
                    completed = await asyncio.to_thread(
                        run_fn,
                        cmd,
                        input=stdin_bytes,
                        cwd=sandbox_dir,
                        env=sanitized_env,
                        timeout=eff_timeout,
                        shell=False,
                        capture_output=True,
                        check=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except subprocess.TimeoutExpired as exc:
                    pid = getattr(exc, "pid", None)
                    if _is_windows() and pid is not None:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True,
                            check=False,
                        )
                    raise AIError(
                        "provider_timeout",
                        "AGY CLI quá thời gian xử lý; chuyển sang kênh dự phòng.",
                    ) from None
                except (OSError, subprocess.SubprocessError) as exc:
                    raise AIError(
                        "provider_unavailable",
                        "AGY CLI tạm thời không phản hồi: " + str(redact_secrets(str(exc)))[:240],
                    ) from None

            stdout_raw = getattr(completed, "stdout", b"")
            if isinstance(stdout_raw, bytes):
                stdout_str = stdout_raw.decode("utf-8", errors="replace")
            else:
                stdout_str = str(stdout_raw or "")

            content = _extract_output_content(
                stdout_str,
                expect_json="format" in effective_body,
                expected_schema=expected_schema,
            )
            if not content:
                raise AIError("invalid_response", "AGY CLI trả về phản hồi rỗng.")

            if has_tools:
                result = structured_tool_response(
                    {"content": content, "provider": "agy", "model": model_label},
                    allowed_tools=allowed_tools or None,
                    include_call_id=True,
                    raise_code="invalid_response",
                )
            else:
                result = {
                    "role": "assistant",
                    "content": content,
                    "provider": "agy",
                    "model": model_label,
                }
            if self.log is not None:
                self.log.write(f"call-{index:02}-response.json", redact_secrets(result))
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=model_label,
                    provider="agy",
                    ok=True,
                    seconds=round(time.perf_counter() - started, 6),
                )
            return result
        except BaseException:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=model_label,
                    provider="agy",
                    ok=False,
                    seconds=round(time.perf_counter() - started, 6),
                )
            raise
