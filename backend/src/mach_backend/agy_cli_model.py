"""Hộp cát Lớp 1 cho AGY CLI: thư mục tạm rỗng, lọc biến môi trường và diệt tiến trình."""

from __future__ import annotations

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
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def detect_agy_cli(custom_path: str = "") -> str | None:
    """Phát hiện đường dẫn thực thi AGY CLI hợp lệ trên máy."""
    cleaned = str(custom_path or "").strip()
    if cleaned:
        candidate = Path(cleaned)
        if candidate.is_file() and candidate.name.lower() in _ALLOWED_EXE_NAMES:
            return str(candidate.resolve())
        return None
    return shutil.which("agy")


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


def _extract_output_content(raw_stdout: str, expect_json: bool) -> str:
    text = raw_stdout.strip()
    fenced = _FENCED_JSON_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    elif expect_json and not text.startswith(("{", "[")):
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if 0 <= start_obj < end_obj:
            text = text[start_obj : end_obj + 1]
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
    ) -> None:
        self.log = log
        self.custom_path = custom_path
        self.budget = budget
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.runner = runner

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

        prompt_text = self._build_prompt(purpose, body)
        prompt_bytes = prompt_text.encode("utf-8")
        sanitized_env = build_sanitized_env()

        if self.log is not None:
            self.log.index += 1
            index = self.log.index
            self.log.write(
                f"call-{index:02}-request.json",
                redact_secrets({"purpose": purpose, "provider": "agy", "body": body}),
            )
            self.log.emit(
                "model_start",
                modelCall=index,
                purpose=purpose,
                model="agy-cli",
                provider="agy",
            )
        else:
            index = 1

        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="mach-agy-sandbox-") as sandbox_dir:
                cmd = [exe]
                run_fn = self.runner or subprocess.run
                try:
                    completed = run_fn(
                        cmd,
                        input=prompt_bytes,
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
                    if os.name == "nt" and pid is not None:
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

            content = _extract_output_content(stdout_str, expect_json="format" in body)
            if not content:
                raise AIError("invalid_response", "AGY CLI trả về phản hồi rỗng.")

            result = {
                "role": "assistant",
                "content": content,
                "provider": "agy",
                "model": "agy-cli",
            }
            if self.log is not None:
                self.log.write(f"call-{index:02}-response.json", redact_secrets(result))
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model="agy-cli",
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
                    model="agy-cli",
                    provider="agy",
                    ok=False,
                    seconds=round(time.perf_counter() - started, 6),
                )
            raise
