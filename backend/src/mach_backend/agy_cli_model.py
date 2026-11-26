"""Hộp cát Lớp 1 cho AGY CLI: thư mục tạm rỗng, lọc biến môi trường và diệt tiến trình."""

from __future__ import annotations

import asyncio
import copy
import inspect
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

DEFAULT_AGY_ORCHESTRATOR_MODEL = "gemini-pro-orchestrator-neon"
DEFAULT_AGY_FAST_MODEL = "gemini-3.8-flash-medium"
AGY_RECOMMENDED_MODELS: tuple[str, ...] = (
    "gemini-pro-orchestrator-neon",
    "gemini-3.8-flash-medium",
    "gemini-4-neon-medium",
    "gemini-4-hydrogen-medium",
)

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
_ENVELOPE_KEYS = (
    "structured_output",
    "structuredOutput",
    "response",
    "result",
    "content",
    "text",
    "output",
    "data",
    "payload",
)
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


def is_blocked_agy_model(model: str | None) -> bool:
    """Chặn các mô hình thử nghiệm không được phép dùng trong cấu hình AGY CLI."""
    if not isinstance(model, str):
        return False
    return "argon" in model.casefold()


def validate_agy_model(
    model: str | None,
    *,
    default: str | None = None,
) -> str | None:
    """Kiểm tra tên mô hình AGY CLI hợp lệ và chủ động chặn mô hình không được phép."""
    if model is None:
        return default
    if not isinstance(model, str) or "\r" in model or "\n" in model:
        raise AIError("unsupported_model", "Tên mô hình AGY CLI không hợp lệ.")
    cleaned = model.strip()
    if not cleaned:
        return default
    if is_blocked_agy_model(cleaned):
        raise AIError(
            "unsupported_model",
            "Mô hình AGY đã chọn không được hỗ trợ; hãy chọn mô hình gợi ý hợp lệ.",
        )
    if not _VALID_AGY_MODEL_RE.fullmatch(cleaned):
        raise AIError(
            "unsupported_model",
            "Tên mô hình AGY CLI không hợp lệ (2–80 ký tự chữ/số/._:/-).",
        )
    return cleaned


_EFFORT_SUFFIXES = ("-low", "-medium", "-high", "-xhigh", "-max")


def model_supports_effort_flag(model_name: str | None) -> bool:
    """AGY CLI 1.5.17 từ chối --effort khi dùng alias orchestrator hoặc model đã gắn mức sẵn."""
    if not model_name:
        return True
    lowered = str(model_name).strip().casefold()
    if "orchestrator" in lowered:
        return False
    return not lowered.endswith(_EFFORT_SUFFIXES)


def resolve_agy_effort(
    purpose: str,
    *,
    tier: str = "orchestrator",
    time_preset: str = "standard",
    default_effort: str = "medium",
) -> str:
    """Chọn mức --effort rõ ràng cho mọi lời gọi AGY CLI."""
    base = str(default_effort or "medium").strip().lower()
    if base not in VALID_EFFORT_LEVELS:
        base = "medium"
    if str(tier or "").strip().lower() == "fast":
        return "low"
    p = str(purpose or "").strip().casefold()
    preset = str(time_preset or "standard").strip().casefold()
    if any(tok in p for tok in ("repair", "m09", "m05", "hard")) or preset in {"deep", "extended"}:
        return "high"
    if any(
        tok in p for tok in ("check", "blind", "explanation", "level_recheck", "m06", "m08", "fast")
    ):
        return "low"
    if any(tok in p for tok in ("plan", "blueprint", "m03", "patch", "m10", "agent", "standard")):
        return base
    return base


def _normalize_action_property(props: dict[str, Any]) -> None:
    action_spec = props.get("action")
    if isinstance(action_spec, dict) and isinstance(action_spec.get("const"), str):
        props["action"] = {"type": "string", "enum": [action_spec["const"]]}


def normalize_agy_json_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Chuẩn hóa JSON schema gốc sang object schema hợp lệ cho AGY CLI --json-schema."""
    if not isinstance(schema, dict):
        return None
    normalized = copy.deepcopy(schema)

    for union_key in ("oneOf", "anyOf"):
        raw_branches = normalized.get(union_key)
        if not isinstance(raw_branches, list) or not raw_branches:
            continue
        branches = [b for b in raw_branches if isinstance(b, dict)]
        if not branches:
            break
        if len(branches) == 1:
            single = copy.deepcopy(branches[0])
            single["type"] = "object"
            if isinstance(single.get("properties"), dict):
                _normalize_action_property(single["properties"])
            if "$defs" in normalized and "$defs" not in single:
                single["$defs"] = copy.deepcopy(normalized["$defs"])
            return single

        action_names: list[str] = []
        all_tool_actions = True
        for branch in branches:
            props = branch.get("properties")
            if not isinstance(props, dict) or "action" not in props or "arguments" not in props:
                all_tool_actions = False
                break
            act_spec = props["action"]
            if isinstance(act_spec, dict):
                if isinstance(act_spec.get("const"), str):
                    action_names.append(act_spec["const"])
                elif isinstance(act_spec.get("enum"), list):
                    action_names.extend(x for x in act_spec["enum"] if isinstance(x, str))
        if all_tool_actions and action_names:
            return {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": list(dict.fromkeys(action_names))},
                    "arguments": {"type": "object"},
                },
                "required": ["action", "arguments"],
            }
        merged_props: dict[str, Any] = {}
        for branch in branches:
            if isinstance(branch.get("properties"), dict):
                merged_props.update(branch["properties"])
        result_obj: dict[str, Any] = {"type": "object"}
        if merged_props:
            result_obj["properties"] = merged_props
        if "$defs" in normalized:
            result_obj["$defs"] = copy.deepcopy(normalized["$defs"])
        return result_obj

    if normalized.get("type") != "object":
        if isinstance(normalized.get("properties"), dict):
            normalized["type"] = "object"
            return normalized
        return {
            "type": "object",
            "properties": {"result": normalized},
            "required": ["result"],
        }
    return normalized


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


def _collect_schema_keys(expected_schema: dict[str, Any] | None) -> set[str]:
    schema_keys: set[str] = set()
    if not isinstance(expected_schema, dict):
        return schema_keys
    props = expected_schema.get("properties")
    if isinstance(props, dict):
        schema_keys.update(props.keys())
    for union_key in ("oneOf", "anyOf"):
        branches = expected_schema.get(union_key)
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, dict) and isinstance(branch.get("properties"), dict):
                    schema_keys.update(branch["properties"].keys())
    return schema_keys


def _score_domain_dict(
    obj: dict[str, Any],
    schema_keys: set[str],
    *,
    prefer_tool_action: bool = False,
) -> tuple[int, int, int, int] | None:
    is_tool_action = (
        1
        if (
            isinstance(obj.get("action"), str)
            and bool(obj["action"].strip())
            and isinstance(obj.get("arguments"), dict)
        )
        else 0
    )
    domain_keys = schema_keys | _DOMAIN_PAYLOAD_KEYS
    hits = len(domain_keys.intersection(obj.keys()))
    if not hits and not is_tool_action:
        return None
    schema_hits = len(schema_keys.intersection(obj.keys()))
    has_msg = 1 if isinstance(obj.get("message"), str) and bool(obj["message"].strip()) else 0
    if prefer_tool_action:
        if is_tool_action:
            return (3, schema_hits, hits, len(obj))
        has_envelope_key = any(k in obj for k in _ENVELOPE_KEYS)
        tier = 0 if has_envelope_key else 1
        return (tier, schema_hits, hits, len(obj))
    return (schema_hits, has_msg, hits, len(obj))


def _collect_envelope_candidates(
    objects: list[dict[str, Any]],
    *,
    max_depth: int = 4,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    queue: list[tuple[dict[str, Any], int]] = [(obj, 0) for obj in objects]
    while queue:
        obj, depth = queue.pop(0)
        candidates.append(obj)
        if depth >= max_depth:
            continue
        for key in _ENVELOPE_KEYS:
            inner = obj.get(key)
            if isinstance(inner, dict):
                queue.append((inner, depth + 1))
            elif isinstance(inner, str) and "{" in inner:
                for decoded in _decode_json_stream(inner):
                    queue.append((decoded, depth + 1))
    return candidates


def _unwrap_cli_envelope(
    text: str,
    expected_schema: dict[str, Any] | None,
    *,
    prefer_tool_action: bool = False,
) -> str:
    if not text.startswith("{"):
        return text
    schema_keys = _collect_schema_keys(expected_schema)
    objects = _decode_json_stream(text)
    if not objects:
        return text
    candidates = _collect_envelope_candidates(objects)
    best_obj: dict[str, Any] | None = None
    best_score: tuple[int, int, int, int] | None = None
    for item in candidates:
        score = _score_domain_dict(item, schema_keys, prefer_tool_action=prefer_tool_action)
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
    *,
    prefer_tool_action: bool = False,
) -> str:
    text = raw_stdout.strip()
    text = _unwrap_cli_envelope(text, expected_schema, prefer_tool_action=prefer_tool_action)
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
        text = _unwrap_cli_envelope(text, expected_schema, prefer_tool_action=prefer_tool_action)
    elif expect_json and not text.startswith(("{", "[")):
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if 0 <= start_obj < end_obj:
            text = _unwrap_cli_envelope(
                text[start_obj : end_obj + 1],
                expected_schema,
                prefer_tool_action=prefer_tool_action,
            )
    if text.startswith("{"):
        text = _unwrap_cli_envelope(text, expected_schema, prefer_tool_action=prefer_tool_action)
    if text.startswith(("{", "[")):
        text = sanitize_json_latex_escapes(text)
    return str(redact_secrets(text))


def _parse_stream_json_event(raw_line: str) -> tuple[str | None, str | None]:
    """Tách (delta_text, final_payload_json) từ một dòng NDJSON của --output-format stream-json."""
    line = raw_line.strip()
    if not line:
        return None, None
    try:
        event = json.loads(line)
    except ValueError:
        try:
            event = json.loads(sanitize_json_latex_escapes(line))
        except ValueError:
            return None, None
    if not isinstance(event, dict):
        return None, None

    ev_type = str(event.get("type") or "").strip().casefold()
    # Kiểm tra kết quả hoàn chỉnh / structured_output trước
    for structured_key in ("structured_output", "structuredOutput"):
        if structured_key in event and event[structured_key] is not None:
            val = event[structured_key]
            final_str = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
            return None, final_str

    if ev_type in {"result", "done", "final", "complete"}:
        for key in ("response", "result", "data", "payload", "content", "text", "output"):
            val = event.get(key)
            if isinstance(val, str) and val.strip():
                return None, val
            if isinstance(val, (dict, list)):
                return None, json.dumps(val, ensure_ascii=False)
        return None, json.dumps(event, ensure_ascii=False)

    # Tách phần delta văn bản theo dòng
    delta = event.get("delta")
    if isinstance(delta, str) and delta:
        return delta, None
    if isinstance(delta, dict):
        for k in ("text", "content"):
            if isinstance(delta.get(k), str) and delta[k]:
                return delta[k], None

    if ev_type in {"delta", "chunk", "text", "content_block_delta", "assistant_delta"}:
        for k in ("text", "content", "chunk"):
            if isinstance(event.get(k), str) and event[k]:
                return event[k], None

    msg = event.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("content"), str) and msg["content"]:
        return msg["content"], None

    if "action" in event and "arguments" in event:
        return None, json.dumps(event, ensure_ascii=False)
    return None, None


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
        self.model: str | None = validate_agy_model(model, default=None)

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

    async def _dispatch_delta(self, on_delta: Callable[[str], Any] | None, chunk: str) -> None:
        if on_delta is None or not chunk:
            return
        safe_chunk = str(redact_secrets(chunk))
        out = on_delta(safe_chunk)
        if inspect.isawaitable(out):
            await out

    async def _run_streaming_subprocess(
        self,
        cmd: list[str],
        *,
        stdin_bytes: bytes,
        cwd: str,
        env: dict[str, str],
        timeout: int,
        on_delta: Callable[[str], Any] | None,
    ) -> str:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
        raw_lines: list[str] = []
        deltas: list[str] = []
        final_payload: str | None = None
        try:
            async with asyncio.timeout(timeout):
                if stdin_bytes:
                    proc.stdin.write(stdin_bytes)
                    await proc.stdin.drain()
                proc.stdin.close()
                while True:
                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    line_str = line_bytes.decode("utf-8", errors="replace")
                    raw_lines.append(line_str)
                    delta_txt, final_txt = _parse_stream_json_event(line_str)
                    if delta_txt:
                        deltas.append(delta_txt)
                        await self._dispatch_delta(on_delta, delta_txt)
                    if final_txt:
                        final_payload = final_txt
                stderr_bytes = await proc.stderr.read()
                returncode = await proc.wait()
        except TimeoutError:
            pid = proc.pid
            if _is_windows() and pid is not None:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                proc.kill()
                await proc.wait()
            raise AIError(
                "provider_timeout",
                "AGY CLI quá thời gian xử lý; chuyển sang kênh dự phòng.",
            ) from None
        if returncode != 0:
            err_text = stderr_bytes.decode("utf-8", errors="replace")[:240]
            raise AIError(
                "provider_unavailable",
                "AGY CLI tạm thời không phản hồi: " + str(redact_secrets(err_text)),
            )
        if final_payload:
            return final_payload
        if deltas:
            return "".join(deltas)
        return "".join(raw_lines)

    async def __call__(
        self,
        purpose: str,
        body: dict[str, Any],
        *,
        stream: bool = False,
        on_delta: Callable[[str], Any] | None = None,
    ) -> dict[str, Any]:
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
        if raw_req_model and raw_req_model != "agy-cli":
            effective_model = validate_agy_model(raw_req_model, default=self.model)
        model_label = effective_model or "agy-cli"

        use_stream = bool(stream or (isinstance(body, dict) and body.get("stream") is True))
        req_body = (
            {k: v for k, v in body.items() if k != "stream"} if isinstance(body, dict) else body
        )

        has_tools = isinstance(req_body, dict) and bool(req_body.get("tools"))
        allowed_tools = (
            [
                t["function"]["name"]
                for t in req_body.get("tools", [])
                if isinstance(t, dict)
                and isinstance(t.get("function"), dict)
                and t["function"].get("name")
            ]
            if has_tools
            else []
        )
        effective_body = structured_tool_request(req_body) if has_tools else req_body

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
                    "stream-json" if use_stream else "json",
                    "--mode",
                    "plan",
                    "--sandbox",
                    "--disable-slash-commands",
                    "--print-timeout",
                    f"{eff_timeout}s",
                ]
                if self.effort in VALID_EFFORT_LEVELS and model_supports_effort_flag(
                    effective_model
                ):
                    cmd.extend(["--effort", self.effort])
                if effective_model:
                    cmd.extend(["--model", effective_model])
                expected_schema = (
                    effective_body.get("format")
                    if isinstance(effective_body.get("format"), dict)
                    else None
                )
                if expected_schema is not None:
                    cli_schema = normalize_agy_json_schema(expected_schema)
                    if cli_schema is not None:
                        schema_path = Path(sandbox_dir) / "schema.json"
                        schema_path.write_text(
                            json.dumps(cli_schema, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        cmd.extend(["--json-schema", str(schema_path)])

                if use_stream and self.runner is None:
                    stdout_str = await self._run_streaming_subprocess(
                        cmd,
                        stdin_bytes=stdin_bytes,
                        cwd=sandbox_dir,
                        env=sanitized_env,
                        timeout=eff_timeout,
                        on_delta=on_delta,
                    )
                else:
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
                        raw_stderr = getattr(exc, "stderr", b"")
                        if isinstance(raw_stderr, bytes):
                            detail_msg = raw_stderr.decode("utf-8", errors="replace").strip()
                        elif isinstance(raw_stderr, str):
                            detail_msg = raw_stderr.strip()
                        else:
                            detail_msg = ""
                        if not detail_msg:
                            detail_msg = str(exc)
                        raise AIError(
                            "provider_unavailable",
                            "AGY CLI tạm thời không phản hồi: "
                            + str(redact_secrets(detail_msg))[:240],
                        ) from None

                    stdout_raw = getattr(completed, "stdout", b"")
                    if isinstance(stdout_raw, bytes):
                        raw_out_str = stdout_raw.decode("utf-8", errors="replace")
                    else:
                        raw_out_str = str(stdout_raw or "")

                    if use_stream:
                        deltas: list[str] = []
                        final_payload: str | None = None
                        for raw_line in raw_out_str.splitlines():
                            delta_txt, final_txt = _parse_stream_json_event(raw_line)
                            if delta_txt:
                                deltas.append(delta_txt)
                                await self._dispatch_delta(on_delta, delta_txt)
                            if final_txt:
                                final_payload = final_txt
                        stdout_str = final_payload or "".join(deltas) or raw_out_str
                    else:
                        stdout_str = raw_out_str

            content = _extract_output_content(
                stdout_str,
                expect_json="format" in effective_body,
                expected_schema=expected_schema,
                prefer_tool_action=has_tools,
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
