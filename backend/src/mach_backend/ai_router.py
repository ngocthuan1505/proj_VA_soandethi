"""Bộ điều phối AI cố định 11 đầu việc vi mô (M01..M11) kèm giải mù chéo và Circuit Breaker."""

from __future__ import annotations

import inspect
import json
import time
from collections.abc import Callable
from typing import Any

from mach_backend.ai_contract import AIError
from mach_backend.ai_safety import redact_secrets

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
    "cost_budget",
    "provider_unconfigured",
    "provider_auth",
    "provider_http_error",
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
    """Ngắt mạch tạm thời họ provider gặp lỗi liên tiếp trong cửa sổ thời gian."""

    def __init__(
        self,
        failure_threshold: int = 3,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 120.0,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.window_seconds = float(window_seconds)
        self.cooldown_seconds = float(cooldown_seconds)
        self._failures: dict[str, list[float]] = {}
        self._open_until: dict[str, float] = {}

    def is_open(self, family: str) -> bool:
        until = self._open_until.get(family)
        if until is None:
            return False
        if time.monotonic() >= until:
            self._open_until.pop(family, None)
            self._failures.pop(family, None)
            return False
        return True

    def record_success(self, family: str) -> None:
        self._failures.pop(family, None)
        self._open_until.pop(family, None)

    def record_failure(self, family: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        recent = [ts for ts in self._failures.get(family, []) if ts >= cutoff]
        recent.append(now)
        self._failures[family] = recent
        if len(recent) >= self.failure_threshold:
            self._open_until[family] = now + self.cooldown_seconds


class FixedTaskRouter:
    """Điều phối viên cố định 11 đầu việc vi mô M01..M11 với giải mù chéo họ model."""

    def __init__(
        self,
        providers: dict[str, Callable[..., Any]],
        log: Any = None,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self.providers = dict(providers)
        self.log = log
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def candidate_chain(self, task_code: str, *, generator_family: str = "") -> list[str]:
        gen = str(generator_family or "").strip().casefold()
        if task_code == M06_BLIND_SOLVE:
            if gen.startswith("deepseek"):
                base = [
                    "agy",
                    "gemini_hydrogen",
                    "gemini_flash",
                    "gateway_cross",
                    "deepseek_reasoner",
                    "deepseek_chat",
                    "ollama",
                ]
            elif gen in {"agy", "gemini", "gemini_flash", "gemini_hydrogen"}:
                base = [
                    "deepseek_reasoner",
                    "deepseek_chat",
                    "gateway_cross",
                    "agy",
                    "gemini_hydrogen",
                    "gemini_flash",
                    "ollama",
                ]
            else:
                base = [
                    "deepseek_reasoner",
                    "gemini_hydrogen",
                    "gateway_cross",
                    "agy",
                    "deepseek_chat",
                    "gemini_flash",
                    "ollama",
                ]
        elif task_code == M11_FLEXIBLE_CHAT:
            base = [
                "agy",
                "gemini_hydrogen",
                "gemini_flash",
                "deepseek_reasoner",
                "deepseek_chat",
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
    ) -> dict[str, Any]:
        task_code = classify_micro_task(
            purpose,
            body,
            hard_hint=hard_hint,
            repair_round=repair_round,
        )
        chain = self.candidate_chain(task_code, generator_family=generator_family)
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
        for idx, family in enumerate(available):
            provider_fn = self.providers[family]
            try:
                outcome = provider_fn(purpose, body)
                if inspect.isawaitable(outcome):
                    result = await outcome
                else:
                    result = outcome
                self.circuit_breaker.record_success(family)
                if isinstance(result, dict):
                    result = dict(result)
                    result["routedTask"] = task_code
                    result["providerFamily"] = family
                if self.log is not None:
                    self.log.emit(
                        "router_decision",
                        purpose=purpose,
                        taskCode=task_code,
                        providerFamily=family,
                        attempt=idx + 1,
                        generatorFamily=generator_family or None,
                    )
                return result
            except AIError as error:
                safe_msg = str(redact_secrets(str(error)))
                sanitized_error = AIError(error.code, safe_msg, http_status=error.http_status)
                if error.code not in FALLBACK_ERROR_CODES:
                    raise sanitized_error from None
                self.circuit_breaker.record_failure(family)
                last_error = sanitized_error
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
