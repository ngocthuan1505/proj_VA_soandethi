"""Gọi DeepSeek & cổng OpenAI-compatible tùy chỉnh kèm kiểm soát chi phí USD và bọc an toàn."""

from __future__ import annotations

import copy
import json
import re
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from mach_backend.ai_contract import AIError
from mach_backend.ai_router import structured_tool_request, structured_tool_response
from mach_backend.ai_safety import (
    CostTracker,
    extract_api_key_token,
    normalize_openai_base_url,
    redact_secrets,
    sanitize_json_latex_escapes,
)
from mach_backend.ai_service import MAX_RESPONSE_BYTES
from mach_backend.gemini_model import gemini_messages

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODELS = ("deepseek-chat", "deepseek-reasoner")
_VALID_MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{2,80}$")


def is_valid_gateway_model(model: str) -> bool:
    return isinstance(model, str) and bool(_VALID_MODEL_RE.fullmatch(model.strip()))


def clean_deepseek_key(key: str) -> str:
    if not isinstance(key, str) or "\n" in key or "\r" in key:
        raise AIError(
            "provider_unconfigured",
            "Nhập DeepSeek API key hợp lệ trong phần Quản trị khóa.",
        )
    cleaned = extract_api_key_token(key)
    if not 8 <= len(cleaned) <= 300:
        raise AIError(
            "provider_unconfigured",
            "Nhập DeepSeek API key hợp lệ trong phần Quản trị khóa.",
        )
    return cleaned


class DeepSeekModel:
    """Adapter gọi DeepSeek hoặc cổng OpenAI-compatible tùy chỉnh Base URL & đa model."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        log: Any,
        *,
        model: str = "deepseek-chat",
        base_url: str = DEEPSEEK_BASE_URL,
        backup_models: Sequence[str] = (),
        budget: Any = None,
        cost_tracker: CostTracker | None = None,
        auto_fallback: bool = True,
    ) -> None:
        self.key = clean_deepseek_key(key)
        self.base_url = normalize_openai_base_url(base_url)
        self.endpoint = self.base_url + "/chat/completions"
        cleaned_model = model.strip() if isinstance(model, str) else ""
        if self.base_url == DEEPSEEK_BASE_URL:
            if cleaned_model not in DEEPSEEK_MODELS:
                raise AIError(
                    "unsupported_model",
                    "Chọn model DeepSeek hợp lệ (deepseek-chat hoặc deepseek-reasoner).",
                )
        elif not is_valid_gateway_model(cleaned_model):
            raise AIError(
                "unsupported_model",
                "Tên model cổng API không hợp lệ (2–80 ký tự chữ/số/._:/-).",
            )
        self.client = client
        self.log = log
        self.model = cleaned_model
        cleaned_backups: list[str] = []
        for item in backup_models:
            if not isinstance(item, str):
                continue
            cand = item.strip()
            if not cand or cand == self.model or cand in cleaned_backups:
                continue
            if self.base_url == DEEPSEEK_BASE_URL:
                if cand in DEEPSEEK_MODELS:
                    cleaned_backups.append(cand)
            elif is_valid_gateway_model(cand):
                cleaned_backups.append(cand)
        self.backup_models: tuple[str, ...] = tuple(cleaned_backups)
        self.budget = budget
        self.cost_tracker = cost_tracker
        self.auto_fallback = auto_fallback

    def _merge_system_messages_for_gateway(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Gộp role='system' vào tin nhắn user đầu khi dùng cổng OpenAI-compatible tùy chỉnh."""
        if (
            self.base_url == DEEPSEEK_BASE_URL
            or not any(m.get("role") == "system" for m in messages)
            or not any(m.get("role") == "user" for m in messages)
        ):
            return messages
        system_parts = [
            str(m.get("content", "")).strip()
            for m in messages
            if m.get("role") == "system" and str(m.get("content", "")).strip()
        ]
        merged_messages: list[dict[str, Any]] = []
        merged_prefix = "[Hướng dẫn hệ thống]\n" + "\n\n".join(system_parts) + "\n\n"
        injected = False
        for m in messages:
            if m.get("role") == "system":
                continue
            if not injected and m.get("role") == "user":
                item = dict(m)
                item["content"] = merged_prefix + str(item.get("content", ""))
                merged_messages.append(item)
                injected = True
            else:
                merged_messages.append(m)
        return merged_messages

    async def __call__(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.auto_fallback:
            ordered = [self.model, *self.backup_models]
            if self.model == "deepseek-reasoner" and "deepseek-chat" not in ordered:
                ordered.append("deepseek-chat")
            candidates = tuple(ordered)
        else:
            candidates = (self.model,)
        last_status = 429
        for idx, actual_model in enumerate(candidates):
            if idx > 0 and self.log is not None:
                self.log.emit(
                    "provider_model_switch",
                    purpose=purpose,
                    fromModel=candidates[idx - 1],
                    toModel=actual_model,
                    httpStatus=last_status,
                    reason="fallback",
                )
            try:
                return await self._call_once(purpose, body, actual_model)
            except AIError as error:
                has_next = idx + 1 < len(candidates)
                can_fallback = (
                    has_next
                    and self.auto_fallback
                    and (
                        error.http_status in {404, 429}
                        or (error.http_status is not None and error.http_status >= 500)
                        or error.code in {"provider_quota", "provider_unavailable"}
                    )
                )
                if can_fallback:
                    last_status = error.http_status or 429
                    continue
                raise
        raise AIError("provider_unavailable", "Không thể gọi DeepSeek ở thời điểm hiện tại.")

    async def _call_once(
        self, purpose: str, body: dict[str, Any], actual_model: str
    ) -> dict[str, Any]:
        if self.cost_tracker is not None:
            self.cost_tracker.check_available()
        if self.budget is not None:
            self.budget.spend()

        use_structured_tools = bool(body.get("tools")) and actual_model == "deepseek-reasoner"
        allowed_tools = (
            [
                t["function"]["name"]
                for t in body.get("tools", [])
                if isinstance(t, dict)
                and isinstance(t.get("function"), dict)
                and t["function"].get("name")
            ]
            if use_structured_tools
            else []
        )
        effective_body = structured_tool_request(body) if use_structured_tools else body

        messages = gemini_messages(effective_body.get("messages", []))
        if "format" in effective_body and not use_structured_tools:
            schema_instruction = " Trả JSON đúng schema sau, không dùng markdown: " + json.dumps(
                effective_body["format"], ensure_ascii=False
            )
            if not messages:
                messages = [{"role": "system", "content": schema_instruction.strip()}]
            elif schema_instruction not in str(messages[0].get("content", "")):
                messages[0]["content"] = str(messages[0].get("content", "")) + schema_instruction

        # Một số cổng OpenAI-compatible bỏ qua role="system"; gộp vào user đầu
        # để bảo toàn chỉ dẫn tiếng Việt và JSON schema.
        messages = self._merge_system_messages_for_gateway(messages)

        lower_model = actual_model.lower()
        schema_props = (
            effective_body.get("format", {}).get("properties", {})
            if isinstance(effective_body.get("format"), dict)
            else {}
        )
        needs_8k = (
            "reasoner" in lower_model
            or "v4" in lower_model
            or bool(body.get("tools"))
            or (
                actual_model == "deepseek-chat"
                and (
                    purpose.startswith(("batch", "generate", "matrix", "M03", "M04", "M05"))
                    or any(k in schema_props for k in ("questions", "slots"))
                )
            )
        )
        payload: dict[str, Any] = {
            "model": actual_model,
            "stream": False,
            "messages": messages,
            "max_tokens": 8192 if needs_8k else 4096,
        }
        if actual_model != "deepseek-reasoner":
            payload["temperature"] = 0
        if "tools" in effective_body and not use_structured_tools:
            payload["tools"] = effective_body["tools"]
        if "format" in effective_body:
            payload["response_format"] = {"type": "json_object"}

        if self.log is not None:
            self.log.index += 1
            index = self.log.index
            self.log.write(
                f"call-{index:02}-request.json",
                redact_secrets(payload, [self.key]),
            )
            self.log.emit(
                "model_start",
                modelCall=index,
                purpose=purpose,
                model=actual_model,
                provider="deepseek",
            )
        else:
            index = 1

        started = time.perf_counter()
        headers = {"Authorization": "Bearer " + self.key}
        try:
            data = bytearray()
            async with self.client.stream(
                "POST",
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=180,
                follow_redirects=False,
            ) as response:
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AIError("result_limit", "Phản hồi DeepSeek vượt giới hạn.")
                    data.extend(chunk)
                if response.status_code >= 300:
                    details: dict[str, Any] = {"httpStatus": response.status_code}
                    try:
                        failure = json.loads(data)
                        if isinstance(failure, list) and failure:
                            failure = failure[0]
                        err_obj = failure.get("error", {}) if isinstance(failure, dict) else {}
                        msg = (
                            err_obj.get("message", "")
                            if isinstance(err_obj, dict)
                            else str(err_obj)
                        )
                        details["message"] = str(redact_secrets(str(msg), [self.key]))[:600]
                    except (ValueError, KeyError, TypeError, IndexError):
                        pass
                    if self.log is not None:
                        self.log.write(
                            f"call-{index:02}-error.json",
                            redact_secrets(details, [self.key]),
                        )
                    if response.status_code in {401, 403}:
                        raise AIError(
                            "provider_auth",
                            "Khóa DeepSeek chưa hợp lệ. Mở Quản trị khóa để cập nhật.",
                            http_status=response.status_code,
                        )
                    if response.status_code == 402:
                        raise AIError(
                            "cost_budget",
                            "Tài khoản DeepSeek hết số dư; tự động chuyển sang kênh dự phòng.",
                            http_status=response.status_code,
                        )
                    if response.status_code == 429:
                        raise AIError(
                            "provider_quota",
                            "DeepSeek gặp giới hạn 429; tự động chuyển sang kênh dự phòng.",
                            http_status=response.status_code,
                        )
                    if response.status_code >= 500:
                        raise AIError(
                            "provider_unavailable",
                            f"DeepSeek tạm gián đoạn (HTTP {response.status_code}).",
                            http_status=response.status_code,
                        )
                    raise AIError(
                        "provider_http_error",
                        f"DeepSeek trả HTTP {response.status_code}: "
                        + str(details.get("message", "")),
                        http_status=response.status_code,
                    )

            raw = json.loads(data)
            if self.log is not None:
                self.log.write(
                    f"call-{index:02}-response.json",
                    redact_secrets(raw, [self.key]),
                )

            usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
            cost_usd = 0.0
            if self.cost_tracker is not None:
                cost_usd = self.cost_tracker.record_usage(
                    actual_model,
                    int(usage.get("prompt_tokens", 0) or 0),
                    int(usage.get("completion_tokens", 0) or 0),
                )

            choices = raw.get("choices", [])
            if len(choices) != 1 or choices[0].get("finish_reason") not in {"stop", "tool_calls"}:
                raise AIError("incomplete_response", "DeepSeek chưa hoàn tất phản hồi.")
            source_message = choices[0].get("message")
            if not isinstance(source_message, dict):
                raise AIError("invalid_response", "DeepSeek chưa trả nội dung trợ lý hợp lệ.")

            message = copy.deepcopy(source_message)
            if message.get("role") != "assistant":
                raise AIError("invalid_response", "DeepSeek chưa trả kết quả trợ lý hợp lệ.")

            if message.get("reasoning_content"):
                reasoning_summary = str(
                    redact_secrets(str(message["reasoning_content"]), [self.key])
                )[:600]
                message["reasoning_content"] = reasoning_summary
                if self.log is not None:
                    self.log.emit(
                        "deepseek_reasoning",
                        modelCall=index,
                        purpose=purpose,
                        model=actual_model,
                        summary=reasoning_summary,
                    )

            tool_calls = message.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                raise AIError("invalid_response", "Danh sách công cụ DeepSeek không hợp lệ.")
            for call in tool_calls:
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not call["id"]
                ):
                    raise AIError("invalid_response", "DeepSeek thiếu mã lời gọi công cụ.")
                arguments = call.get("function", {}).get("arguments")
                if isinstance(arguments, str):
                    arguments = json.loads(sanitize_json_latex_escapes(arguments))
                if not isinstance(arguments, dict):
                    raise AIError("invalid_response", "Tham số công cụ DeepSeek không hợp lệ.")
                call["function"]["arguments"] = arguments

            raw_content = str(message.get("content") or "")
            if raw_content.strip().startswith(("{", "[")):
                raw_content = sanitize_json_latex_escapes(raw_content)
            message["content"] = str(redact_secrets(raw_content, [self.key]))
            message["provider"] = "deepseek"
            message["model"] = actual_model
            message["costUsd"] = round(cost_usd, 6)

            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=actual_model,
                    provider="deepseek",
                    ok=True,
                    seconds=round(time.perf_counter() - started, 6),
                    costUsd=round(cost_usd, 6),
                    metrics=usage,
                )
            if use_structured_tools and not message.get("tool_calls"):
                return structured_tool_response(
                    message,
                    allowed_tools=allowed_tools or None,
                    include_call_id=True,
                    raise_code="invalid_response",
                )
            return message
        except httpx.TimeoutException:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=actual_model,
                    provider="deepseek",
                    ok=False,
                    seconds=round(time.perf_counter() - started, 6),
                )
            raise AIError(
                "provider_timeout", "DeepSeek quá thời gian phản hồi; chuyển kênh dự phòng."
            ) from None
        except httpx.HTTPError as exc:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=actual_model,
                    provider="deepseek",
                    ok=False,
                    seconds=round(time.perf_counter() - started, 6),
                )
            raise AIError(
                "provider_unavailable",
                "Không kết nối được DeepSeek: " + str(redact_secrets(str(exc), [self.key])),
            ) from None
        except BaseException:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=actual_model,
                    provider="deepseek",
                    ok=False,
                    seconds=round(time.perf_counter() - started, 6),
                )
            raise

    async def stream_chat(
        self, messages: Sequence[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Phát luồng từng token DeepSeek / OpenAI-compatible qua SSE (`stream: True`)."""
        if self.cost_tracker is not None:
            self.cost_tracker.check_available()
        if self.budget is not None:
            self.budget.spend()

        actual_model = str(kwargs.get("model") or self.model).strip() or self.model
        lower_model = actual_model.lower()
        prepared_messages = self._merge_system_messages_for_gateway(gemini_messages(list(messages)))
        payload: dict[str, Any] = {
            "model": actual_model,
            "stream": True,
            "messages": prepared_messages,
            "max_tokens": int(
                kwargs.get(
                    "max_tokens",
                    8192 if ("reasoner" in lower_model or "v4" in lower_model) else 4096,
                )
            ),
        }
        if actual_model != "deepseek-reasoner":
            payload["temperature"] = kwargs.get("temperature", 0)
        headers = {"Authorization": "Bearer " + self.key}

        full_parts: list[str] = []
        reasoning_parts: list[str] = []
        usage: dict[str, Any] = {}
        try:
            async with self.client.stream(
                "POST",
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=180,
                follow_redirects=False,
            ) as response:
                if response.status_code >= 300:
                    raw_err = await response.aread()
                    err_msg = ""
                    try:
                        parsed = json.loads(raw_err)
                        if isinstance(parsed, dict):
                            err_obj = parsed.get("error", {})
                            err_msg = (
                                err_obj.get("message", "")
                                if isinstance(err_obj, dict)
                                else str(err_obj)
                            )
                    except ValueError:
                        pass
                    safe_msg = str(redact_secrets(err_msg, [self.key]))[:400]
                    if response.status_code in {401, 403}:
                        raise AIError(
                            "provider_auth",
                            "Khóa DeepSeek chưa hợp lệ.",
                            http_status=response.status_code,
                        )
                    if response.status_code == 402:
                        raise AIError(
                            "cost_budget",
                            "Tài khoản DeepSeek hết số dư.",
                            http_status=402,
                        )
                    if response.status_code == 429:
                        raise AIError(
                            "provider_quota",
                            "DeepSeek gặp giới hạn 429.",
                            http_status=429,
                        )
                    if response.status_code >= 500:
                        raise AIError(
                            "provider_unavailable",
                            f"DeepSeek tạm gián đoạn (HTTP {response.status_code}).",
                            http_status=response.status_code,
                        )
                    raise AIError(
                        "provider_http_error",
                        f"DeepSeek stream trả HTTP {response.status_code}: {safe_msg}",
                        http_status=response.status_code,
                    )

                async for line in response.aiter_lines():
                    stripped = line.strip()
                    if not stripped or not stripped.startswith("data:"):
                        continue
                    data_part = stripped[5:].strip()
                    if not data_part or data_part == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data_part)
                    except ValueError:
                        continue
                    if isinstance(chunk.get("usage"), dict):
                        usage = chunk["usage"]
                    for choice in chunk.get("choices", []):
                        if not isinstance(choice, dict):
                            continue
                        delta = choice.get("delta") or {}
                        if not isinstance(delta, dict):
                            continue
                        reasoning_text = delta.get("reasoning_content")
                        if isinstance(reasoning_text, str) and reasoning_text:
                            safe_reasoning = str(redact_secrets(reasoning_text, [self.key]))
                            reasoning_parts.append(safe_reasoning)
                            yield {
                                "type": "status",
                                "phase": "reasoning",
                                "text": safe_reasoning,
                            }
                        token_text = delta.get("content")
                        if isinstance(token_text, str) and token_text:
                            safe_delta = str(redact_secrets(token_text, [self.key]))
                            full_parts.append(safe_delta)
                            yield {"type": "delta", "text": safe_delta}
        except httpx.TimeoutException:
            raise AIError("provider_timeout", "DeepSeek stream quá thời gian phản hồi.") from None
        except httpx.HTTPError as exc:
            raise AIError(
                "provider_unavailable",
                "Lỗi kết nối stream DeepSeek: " + str(redact_secrets(str(exc), [self.key])),
            ) from None

        if self.cost_tracker is not None and usage:
            self.cost_tracker.record_usage(
                actual_model,
                int(usage.get("prompt_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or 0),
            )
        done_event: dict[str, Any] = {
            "type": "done",
            "text": str(redact_secrets("".join(full_parts), [self.key])),
            "provider": "deepseek",
            "model": actual_model,
            "usage": usage,
        }
        if reasoning_parts:
            done_event["reasoning_content"] = str(
                redact_secrets("".join(reasoning_parts), [self.key])
            )[:600]
        yield done_event
