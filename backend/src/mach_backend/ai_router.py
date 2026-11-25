"""Bộ điều phối AI cố định 11 đầu việc vi mô (M01..M11) kèm giải mù chéo và Circuit Breaker."""

from __future__ import annotations

import inspect
import json
import re
import threading
import time
from collections.abc import Callable, Iterable
from typing import Any
from uuid import uuid4

from mach_backend.ai_contract import AIError
from mach_backend.ai_safety import redact_secrets, sanitize_json_latex_escapes

_TOOL_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_DEFAULT_ALLOWED_TOOLS = frozenset({"check_exam", "finish_exam"})


def structured_tool_request(body: dict[str, Any]) -> dict[str, Any]:
    """Mã hóa yêu cầu gọi công cụ bằng JSON schema hợp nhất cho mọi họ model."""
    tools = body.get("tools") or []
    if not tools:
        return dict(body)
    choices = []
    definitions: dict[str, Any] = {}
    for tool in tools:
        function = tool["function"]
        parameters = dict(function["parameters"])
        # Tham chiếu của Pydantic bắt đầu từ gốc schema đã bọc.
        definitions.update(parameters.pop("$defs", {}))
        choices.append(
            {
                "type": "object",
                "properties": {
                    "action": {"const": function["name"]},
                    "arguments": parameters,
                },
                "required": ["action", "arguments"],
                "additionalProperties": False,
            }
        )
    schema: dict[str, Any] = {"oneOf": choices}
    if definitions:
        schema["$defs"] = definitions
    history = list(body.get("messages", []))
    restart = False
    if len(history) >= 4 and history[-1].get("tool_name") == "check_exam":
        try:
            last_tool_payload = json.loads(str(history[-1].get("content", "")))
            restart = isinstance(last_tool_payload, dict) and (
                last_tool_payload.get("reusedFromAttempt") is not None
            )
        except (ValueError, TypeError):
            restart = False
    if restart:
        # Mẫu trả lời trùng trong lịch sử khiến model tiếp tục chép lại cả bộ cũ.
        history = [*history[:2], history[-1]]
    messages: list[dict[str, Any]] = []
    for message in history:
        if message.get("role") == "tool":
            raw_tool_content = message.get("content", "{}")
            try:
                parsed_result = (
                    raw_tool_content
                    if isinstance(raw_tool_content, dict)
                    else json.loads(str(raw_tool_content))
                )
            except (ValueError, TypeError):
                parsed_result = {"raw": str(raw_tool_content)}
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "toolResult": message.get("tool_name", "check_exam"),
                            "result": parsed_result,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        elif "tool_calls" in message and message["tool_calls"]:
            call = message["tool_calls"][0]["function"]
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {"action": call["name"], "arguments": call["arguments"]},
                        ensure_ascii=False,
                    ),
                }
            )
        else:
            messages.append(dict(message))
    if not messages:
        messages = [{"role": "system", "content": ""}]
    protocol_note = (
        " Giao thức lượt này là JSON action, không phải native tool calling. "
        "Bạn chọn action và tự viết arguments. Python chỉ thực thi công cụ được phép "
        "rồi trả toolResult để bạn tự sửa. Khi result.ok=false, xử lý result.errors "
        "và làm theo result.repairInstruction nếu có trước khi nộp lại. "
        "Trả đúng JSON theo schema: " + json.dumps(schema, ensure_ascii=False)
    )
    first_content = str(messages[0].get("content", ""))
    if "Giao thức lượt này là JSON action" not in first_content:
        first_content += protocol_note
    if restart and "đặt câu hỏi mới cho đúng ô đó" not in first_content:
        first_content += (
            " Bộ câu trước bị nộp lặp và đã rút khỏi ngữ cảnh. "
            "Hãy soạn lại toàn bộ từ ma trận và nguồn ban đầu. Với mỗi lỗi có ordinal "
            "(đếm từ 0), đặt câu hỏi mới cho đúng ô đó, dùng dữ kiện hoặc cách hỏi khác. "
            "Tự giải từng câu mới rồi mới nộp qua check_exam."
        )
    messages[0]["content"] = first_content
    request: dict[str, Any] = {"messages": messages, "format": schema}
    if "options" in body:
        request["options"] = body["options"]
    return request


def _parse_json_action_payload(raw_text: str) -> Any:
    text = raw_text.strip()
    fenced = _TOOL_FENCE_RE.search(text)
    candidates = [text]
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if 0 <= start_obj < end_obj:
        candidates.append(text[start_obj : end_obj + 1])
    for cand in candidates:
        if not cand:
            continue
        for attempt in (cand, sanitize_json_latex_escapes(cand)):
            try:
                return json.loads(attempt)
            except (ValueError, TypeError):
                continue
    return None


def structured_tool_response(
    message: dict[str, Any] | str,
    *,
    allowed_tools: Iterable[str] | None = None,
    include_call_id: bool = False,
    raise_code: str = "invalid_action",
) -> dict[str, Any]:
    """Chuyển phản hồi JSON {action, arguments} thành tool_calls chuẩn cho run_matrix_agent."""
    raw_content = message.get("content", "") if isinstance(message, dict) else message
    action = _parse_json_action_payload(str(raw_content or ""))
    allowed = frozenset(allowed_tools) if allowed_tools is not None else _DEFAULT_ALLOWED_TOOLS
    if (
        not isinstance(action, dict)
        or set(action) != {"action", "arguments"}
        or action["action"] not in allowed
    ):
        raise AIError(raise_code, "Model trả yêu cầu công cụ không hợp lệ.")
    arguments = action["arguments"]
    if isinstance(arguments, str):
        try:
            arguments = json.loads(sanitize_json_latex_escapes(arguments))
        except (ValueError, TypeError):
            arguments = None
    if not isinstance(arguments, dict):
        raise AIError(raise_code, "Model trả yêu cầu công cụ không hợp lệ.")
    tool_call: dict[str, Any] = {"function": {"name": action["action"], "arguments": arguments}}
    if include_call_id:
        tool_call["id"] = f"call_{uuid4().hex[:12]}"
        tool_call["type"] = "function"
    result: dict[str, Any] = {
        "role": "assistant",
        "content": "",
        "tool_calls": [tool_call],
    }
    if isinstance(message, dict):
        for meta_key in ("provider", "model", "costUsd", "reasoning_content"):
            if meta_key in message and message[meta_key] is not None:
                result[meta_key] = message[meta_key]
    return result


M01_OCR = "M01_OCR"
M02_SOURCE_INDEX = "M02_SOURCE_INDEX"
M03_EXAM_BLUEPRINT = "M03_EXAM_BLUEPRINT"
M04_GEN_STANDARD = "M04_GEN_STANDARD"
M05_GEN_HARD = "M05_GEN_HARD"
M06_BLIND_SOLVE = "M06_BLIND_SOLVE"
M07_DISTRACTOR_CHECK = "M07_DISTRACTOR_CHECK"
M08_DUPLICATE_SCOPE_CHECK = "M08_DUPLICATE_SCOPE_CHECK"
M09_SURGICAL_REPAIR = "M09_SURGICAL_REPAIR"
M10_SCOPED_PATCH = "M10_SCOPED_PATCH"
M11_FLEXIBLE_CHAT = "M11_FLEXIBLE_CHAT"

MICRO_TASKS: dict[str, dict[str, str]] = {
    M01_OCR: {"code": M01_OCR, "label": "Đọc OCR tài liệu/ảnh đề"},
    M02_SOURCE_INDEX: {"code": M02_SOURCE_INDEX, "label": "Lập chỉ mục & trích đoạn học liệu"},
    M03_EXAM_BLUEPRINT: {"code": M03_EXAM_BLUEPRINT, "label": "Thiết kế ma trận & bản thiết kế đề"},
    M04_GEN_STANDARD: {
        "code": M04_GEN_STANDARD,
        "label": "Biên soạn câu hỏi Nhận biết / Thông hiểu",
    },
    M05_GEN_HARD: {"code": M05_GEN_HARD, "label": "Biên soạn câu hỏi Vận dụng / Vận dụng cao"},
    M06_BLIND_SOLVE: {"code": M06_BLIND_SOLVE, "label": "Giải mù độc lập chéo họ model"},
    M07_DISTRACTOR_CHECK: {
        "code": M07_DISTRACTOR_CHECK,
        "label": "Kiểm định phương án nhiễu & barem",
    },
    M08_DUPLICATE_SCOPE_CHECK: {
        "code": M08_DUPLICATE_SCOPE_CHECK,
        "label": "Kiểm trùng lặp & phạm vi chương trình",
    },
    M09_SURGICAL_REPAIR: {"code": M09_SURGICAL_REPAIR, "label": "Tự sửa phẫu thuật câu lỗi"},
    M10_SCOPED_PATCH: {"code": M10_SCOPED_PATCH, "label": "Sửa cục bộ theo phạm vi chọn"},
    M11_FLEXIBLE_CHAT: {
        "code": M11_FLEXIBLE_CHAT,
        "label": "Trợ lý chat linh hoạt có thẻ hành động",
    },
}

TIME_PRESETS: dict[str, dict[str, Any]] = {
    "fast": {
        "label": "Nhanh (2 phút)",
        "timeoutSeconds": 120,
        "maxModelCalls": 12,
        "maxRepairRounds": 1,
    },
    "standard": {
        "label": "Tiêu chuẩn (5 phút)",
        "timeoutSeconds": 300,
        "maxModelCalls": 30,
        "maxRepairRounds": 3,
    },
    "deep": {
        "label": "Kỹ sâu (20 phút)",
        "timeoutSeconds": 1200,
        "maxModelCalls": 80,
        "maxRepairRounds": 5,
    },
    "extended": {
        "label": "Chuyên sâu (60 phút)",
        "timeoutSeconds": 3600,
        "maxModelCalls": 200,
        "maxRepairRounds": 8,
    },
}

FALLBACK_ERROR_CODES = {
    "provider_quota",
    "provider_unavailable",
    "provider_timeout",
    "incomplete_response",
    "cost_budget",
    "provider_unconfigured",
    "provider_auth",
    "provider_http_error",
    "invalid_response",
    "invalid_result",
    "result_limit",
    "rate_limited",
    "unsupported_model",
}


def classify_micro_task(
    purpose: str,
    body: dict[str, Any] | None = None,
    *,
    hard_hint: bool = False,
    repair_round: int = 0,
) -> str:
    """Phân loại tự động lời gọi model vào 1 trong 11 đầu việc vi mô M01..M11."""
    raw = str(purpose or "").strip()
    if raw in MICRO_TASKS:
        return raw
    p = raw.casefold()
    if "source_ocr" in p or "ocr" in p or (body and "document" in body and "matrix" not in p):
        return M01_OCR
    if "source_index" in p or "index" in p:
        return M02_SOURCE_INDEX
    if "blueprint" in p or "plan" in p or "matrix" in p:
        return M03_EXAM_BLUEPRINT
    if "verify_options" in p or "distractor" in p:
        return M07_DISTRACTOR_CHECK
    if "check_duplicates" in p or "duplicate" in p or "scope_check" in p:
        return M08_DUPLICATE_SCOPE_CHECK
    if "solve_blind" in p or "blind" in p or "check" in p:
        return M06_BLIND_SOLVE
    if "scoped_patch" in p or "patch" in p:
        return M10_SCOPED_PATCH
    if "chat" in p:
        return M11_FLEXIBLE_CHAT
    if "repair" in p or repair_round > 0:
        return M09_SURGICAL_REPAIR

    if hard_hint:
        return M05_GEN_HARD
    if body:
        serialized = json.dumps(body.get("messages", []), ensure_ascii=False).casefold()
        if any(
            token in serialized
            for token in ("van_dung", "van_dung_cao", "vận dụng", '"level": 2', '"level": 3')
        ):
            return M05_GEN_HARD
    return M04_GEN_STANDARD


class CircuitBreaker:
    """Ngắt mạch tạm thời họ provider gặp lỗi liên tiếp (an toàn đa luồng)."""

    def __init__(
        self,
        failure_threshold: int = 3,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 120.0,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.window_seconds = float(window_seconds)
        self.cooldown_seconds = float(cooldown_seconds)
        self._lock = threading.RLock()
        self._failures: dict[str, list[float]] = {}
        self._open_until: dict[str, float] = {}

    def is_open(self, family: str) -> bool:
        with self._lock:
            until = self._open_until.get(family)
            if until is None:
                return False
            if time.monotonic() >= until:
                self._open_until.pop(family, None)
                self._failures.pop(family, None)
                return False
            return True

    def record_success(self, family: str) -> None:
        with self._lock:
            self._failures.pop(family, None)
            self._open_until.pop(family, None)

    def record_failure(self, family: str) -> None:
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window_seconds
            recent = [ts for ts in self._failures.get(family, []) if ts >= cutoff]
            recent.append(now)
            self._failures[family] = recent
            if len(recent) >= self.failure_threshold:
                self._open_until[family] = now + self.cooldown_seconds


_SHARED_CIRCUIT_LOCK = threading.Lock()
_SHARED_CIRCUIT_BREAKER: CircuitBreaker | None = None


def get_shared_circuit_breaker() -> CircuitBreaker:
    """Trả về một CircuitBreaker dùng chung toàn tiến trình giữa các lượt gọi AI."""
    global _SHARED_CIRCUIT_BREAKER
    with _SHARED_CIRCUIT_LOCK:
        if _SHARED_CIRCUIT_BREAKER is None:
            _SHARED_CIRCUIT_BREAKER = CircuitBreaker()
        return _SHARED_CIRCUIT_BREAKER


def reset_shared_circuit_breaker() -> CircuitBreaker:
    """Đặt lại CircuitBreaker dùng chung (dùng khi đổi cấu hình hoặc trong kiểm thử)."""
    global _SHARED_CIRCUIT_BREAKER
    with _SHARED_CIRCUIT_LOCK:
        _SHARED_CIRCUIT_BREAKER = CircuitBreaker()
        return _SHARED_CIRCUIT_BREAKER


class FixedTaskRouter:
    """Điều phối viên cố định 11 đầu việc vi mô M01..M11 với giải mù chéo họ model."""

    def __init__(
        self,
        providers: dict[str, Callable[..., Any]],
        log: Any = None,
        circuit_breaker: CircuitBreaker | None = None,
        *,
        fast_chat: bool | None = None,
        time_preset: str = "standard",
    ) -> None:
        self.providers = dict(providers)
        self.log = log
        self.circuit_breaker = circuit_breaker if circuit_breaker is not None else CircuitBreaker()
        self.fast_chat: bool | None = fast_chat
        self.time_preset: str = str(time_preset or "standard").strip().casefold() or "standard"

    def candidate_chain(
        self,
        task_code: str,
        *,
        generator_family: str = "",
        fast_chat: bool | None = None,
        time_preset: str | None = None,
    ) -> list[str]:
        gen = str(generator_family or "").strip().casefold()
        eff_preset = (
            str(time_preset).strip().casefold() if time_preset is not None else self.time_preset
        ) or "standard"
        non_fast_mode = "deep" if eff_preset in {"deep", "extended"} else "standard"
        if fast_chat is not None:
            m11_mode = "fast" if fast_chat else non_fast_mode
        elif time_preset is not None:
            m11_mode = "fast" if eff_preset == "fast" else non_fast_mode
        elif self.fast_chat is not None:
            m11_mode = "fast" if self.fast_chat else non_fast_mode
        else:
            m11_mode = "fast" if eff_preset == "fast" else non_fast_mode
        if task_code == M06_BLIND_SOLVE:
            if gen.startswith("deepseek"):
                base = [
                    "agy",
                    "gemini_hydrogen",
                    "gemini_flash",
                    "gemini_pro",
                    "gateway_cross",
                    "deepseek_reasoner",
                    "deepseek_chat",
                    "ollama",
                ]
            elif gen in {"agy", "gemini", "gemini_flash", "gemini_pro", "gemini_hydrogen"}:
                base = [
                    "deepseek_reasoner",
                    "deepseek_chat",
                    "gateway_cross",
                    "agy",
                    "gemini_hydrogen",
                    "gemini_pro",
                    "gemini_flash",
                    "ollama",
                ]
            else:
                base = [
                    "deepseek_reasoner",
                    "gemini_hydrogen",
                    "gemini_pro",
                    "gateway_cross",
                    "agy",
                    "deepseek_chat",
                    "gemini_flash",
                    "ollama",
                ]
        elif task_code == M11_FLEXIBLE_CHAT:
            if m11_mode == "fast":
                base = [
                    "deepseek_chat",
                    "gemini_flash",
                    "agy",
                    "ollama",
                    "gemini_pro",
                    "gemini_hydrogen",
                    "gemini",
                    "deepseek_reasoner",
                    "gateway_cross",
                ]
            elif m11_mode == "standard":
                base = [
                    "agy",
                    "deepseek_chat",
                    "gemini_flash",
                    "deepseek_reasoner",
                    "gemini_pro",
                    "gemini_hydrogen",
                    "gemini",
                    "gateway_cross",
                    "ollama",
                ]
            else:
                base = [
                    "agy",
                    "deepseek_reasoner",
                    "gemini_pro",
                    "gemini_hydrogen",
                    "deepseek_chat",
                    "gemini_flash",
                    "gemini",
                    "gateway_cross",
                    "ollama",
                ]
        elif task_code in {
            M03_EXAM_BLUEPRINT,
            M05_GEN_HARD,
            M09_SURGICAL_REPAIR,
        }:
            base = [
                "agy",
                "gemini_hydrogen",
                "gemini_pro",
                "deepseek_reasoner",
                "gemini_flash",
                "deepseek_chat",
                "ollama",
            ]
        elif task_code == M04_GEN_STANDARD:
            base = [
                "deepseek_chat",
                "gemini_flash",
                "agy",
                "gemini_pro",
                "gemini_hydrogen",
                "deepseek_reasoner",
                "ollama",
            ]
        else:
            # M01_OCR, M02_SOURCE_INDEX, M07, M08, M10_SCOPED_PATCH
            base = [
                "gemini_flash",
                "deepseek_chat",
                "agy",
                "gemini_pro",
                "gemini_hydrogen",
                "deepseek_reasoner",
                "ollama",
            ]

        for extra in self.providers:
            if extra not in base:
                base.append(extra)
        return base

    async def __call__(
        self,
        purpose: str,
        body: dict[str, Any],
        *,
        generator_family: str = "",
        hard_hint: bool = False,
        repair_round: int = 0,
        fast_chat: bool | None = None,
        time_preset: str | None = None,
    ) -> dict[str, Any]:
        forwarded_body = body
        use_fast_chat = fast_chat
        use_time_preset = time_preset
        if isinstance(body, dict) and (
            "fast_chat" in body or "time_preset" in body or "timePreset" in body
        ):
            forwarded_body = {
                k: v for k, v in body.items() if k not in {"fast_chat", "time_preset", "timePreset"}
            }
            if use_fast_chat is None and "fast_chat" in body:
                use_fast_chat = bool(body.get("fast_chat"))
            if use_time_preset is None and (
                body.get("time_preset") is not None or body.get("timePreset") is not None
            ):
                raw_preset = body.get("time_preset") or body.get("timePreset")
                use_time_preset = str(raw_preset).strip().casefold()
        task_code = classify_micro_task(
            purpose,
            forwarded_body,
            hard_hint=hard_hint,
            repair_round=repair_round,
        )
        chain = self.candidate_chain(
            task_code,
            generator_family=generator_family,
            fast_chat=use_fast_chat,
            time_preset=use_time_preset,
        )
        available = [
            family
            for family in chain
            if family in self.providers and not self.circuit_breaker.is_open(family)
        ]
        if not available:
            # Nếu mọi provider đều đang mở circuit breaker, thử lại các provider có trong dict
            available = [family for family in chain if family in self.providers]
        if not available:
            raise AIError(
                "provider_unconfigured",
                "Chưa có kênh AI khả dụng trong bộ điều phối cố định.",
            )

        last_error: AIError | None = None
        attempted_providers: list[str] = []
        fallback_from: str | None = None
        fallback_reason: str | None = None
        for idx, family in enumerate(available):
            attempted_providers.append(family)
            provider_fn = self.providers[family]
            try:
                outcome = provider_fn(purpose, forwarded_body)
                if inspect.isawaitable(outcome):
                    result = await outcome
                else:
                    result = outcome
                self.circuit_breaker.record_success(family)
                if isinstance(result, dict):
                    result = dict(result)
                    result["routedTask"] = task_code
                    result["providerFamily"] = family
                    result["attemptedProviders"] = list(attempted_providers)
                    if fallback_from is not None:
                        result["fallbackFrom"] = fallback_from
                        result["fallbackReason"] = fallback_reason
                if self.log is not None:
                    self.log.emit(
                        "router_decision",
                        purpose=purpose,
                        taskCode=task_code,
                        providerFamily=family,
                        attempt=idx + 1,
                        generatorFamily=generator_family or None,
                        fallbackFrom=fallback_from,
                    )
                return result
            except AIError as error:
                safe_msg = str(redact_secrets(str(error)))
                sanitized_error = AIError(error.code, safe_msg, http_status=error.http_status)
                if error.code not in FALLBACK_ERROR_CODES:
                    raise sanitized_error from None
                self.circuit_breaker.record_failure(family)
                last_error = sanitized_error
                if fallback_from is None:
                    fallback_from = family
                    fallback_reason = safe_msg
                next_family = available[idx + 1] if idx + 1 < len(available) else None
                if self.log is not None:
                    self.log.emit(
                        "router_fallback",
                        purpose=purpose,
                        taskCode=task_code,
                        fromFamily=family,
                        toFamily=next_family,
                        reason=error.code,
                        httpStatus=error.http_status,
                    )
                continue

        if last_error is not None:
            raise last_error
        raise AIError("provider_unavailable", "Tất cả kênh AI trong chuỗi điều phối đều thất bại.")
