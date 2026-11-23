"""Gọi Gemini qua REST tương thích; giữ cùng vòng công cụ và bộ kiểm Python."""

import asyncio
import copy
import json
import time
from collections.abc import Sequence

import httpx

from mach_backend.ai_contract import AIError
from mach_backend.ai_safety import (
    extract_api_key_token,
    redact_secrets,
    sanitize_json_latex_escapes,
)
from mach_backend.ai_service import MAX_RESPONSE_BYTES

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
VERTEX_EXPRESS_BASE = "https://aiplatform.googleapis.com/v1/publishers/google/models"
VERTEX_FALLBACK_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_MODELS = (GEMINI_MODEL, "gemini-3.8-flash", "gemini-4-hydrogen")


def is_vertex_express_key(key: str) -> bool:
    return extract_api_key_token(key).startswith("AQ.")


def clean_api_key(key):
    if not isinstance(key, str) or "\n" in key or "\r" in key:
        raise AIError("provider_unconfigured", "Nhập Gemini API key trong phần kết nối của app.")
    cleaned = extract_api_key_token(key)
    if not 8 <= len(cleaned) <= 300:
        raise AIError("provider_unconfigured", "Nhập Gemini API key trong phần kết nối của app.")
    return cleaned


def gemini_messages(messages):
    converted, pending = [], []
    for source in messages:
        message = copy.deepcopy(source)
        if message["role"] == "tool":
            if not pending or message.get("tool_name") != pending[0][0]:
                raise AIError("invalid_history", "Phản hồi công cụ không khớp lời gọi Gemini.")
            _, call_id = pending.pop(0)
            message = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": message["content"],
            }
        else:
            for call in message.get("tool_calls", []):
                if not call.get("id"):
                    raise AIError("invalid_history", "Lời gọi Gemini thiếu mã công cụ.")
                function = call["function"]
                pending.append((function["name"], call["id"]))
                if isinstance(function["arguments"], dict):
                    function["arguments"] = json.dumps(function["arguments"], ensure_ascii=False)
        converted.append(message)
    if pending:
        raise AIError("invalid_history", "Lời gọi công cụ chưa có kết quả.")
    return converted


class GeminiKeyPool:
    """Luân phiên tối đa 8 khóa đã được chấp thuận; bỏ key gặp 429 và hồi phục sau cooldown."""

    def __init__(
        self,
        key,
        backup_key="",
        *extra_keys,
        cooldown_seconds: float | None = None,
    ):
        raw_keys = []
        for item in (key, backup_key, *extra_keys):
            if isinstance(item, (list, tuple)):
                raw_keys.extend(k for k in item if k)
            elif item:
                raw_keys.append(item)
        self.keys = tuple(dict.fromkeys(clean_api_key(k) for k in raw_keys))[:8]
        if not self.keys:
            clean_api_key("")
        self.index, self.exhausted = 0, set()
        self.invalid = set()
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_until: dict[tuple[str, int], float] = {}

    @classmethod
    def from_keys(
        cls,
        keys: Sequence[str],
        *,
        cooldown_seconds: float | None = 60.0,
    ) -> "GeminiKeyPool":
        cleaned = [k for k in keys if isinstance(k, str) and k.strip()]
        if not cleaned:
            return cls("", cooldown_seconds=cooldown_seconds)
        first = cleaned[0]
        second = cleaned[1] if len(cleaned) > 1 else ""
        rest = cleaned[2:]
        return cls(first, second, *rest, cooldown_seconds=cooldown_seconds)

    def mark_rate_limited(
        self,
        model: str,
        slot: int,
        retry_after: float | None = None,
    ) -> None:
        self.exhausted.add((model, slot))
        if self.cooldown_seconds is not None or retry_after is not None:
            delay = retry_after if retry_after is not None else (self.cooldown_seconds or 0.0)
            self.cooldown_until[(model, slot)] = time.monotonic() + float(delay)

    def refresh_cooldowns(self) -> None:
        if not self.cooldown_until:
            return
        now = time.monotonic()
        expired = [pair for pair, until in self.cooldown_until.items() if until <= now]
        for pair in expired:
            self.cooldown_until.pop(pair, None)
            self.exhausted.discard(pair)

    def next_slot(self, model=GEMINI_MODEL):
        for _ in self.keys:
            slot = self.index
            self.index = (self.index + 1) % len(self.keys)
            if slot not in self.invalid and (model, slot) not in self.exhausted:
                return slot
        if len(self.invalid) == len(self.keys):
            raise AIError("provider_auth", "Các key Gemini chưa hợp lệ. Mở Kết nối để thay khóa.")
        raise AIError(
            "provider_quota", "Các key Gemini đã gặp giới hạn 429. Chờ quota phục hồi rồi thử lại."
        )


class GeminiModel:
    def __init__(
        self,
        client: httpx.AsyncClient,
        key: str,
        log,
        *,
        model=GEMINI_MODEL,
        budget=None,
        key_pool=None,
        auto_fallback=True,
    ):
        key = clean_api_key(key)
        if model not in GEMINI_MODELS:
            raise AIError(
                "unsupported_model", "Chọn model Gemini trong danh sách Free tier đã kiểm."
            )
        self.client, self.log, self.model = client, log, model
        self.budget = budget
        self.key_pool = key_pool or GeminiKeyPool(key)
        self.auto_fallback = auto_fallback

    async def __call__(self, purpose, body):
        self.key_pool.refresh_cooldowns()
        has_vertex_key = any(is_vertex_express_key(k) for k in self.key_pool.keys)
        if self.auto_fallback:
            candidate_list = [self.model, *(m for m in GEMINI_MODELS if m != self.model)]
            if has_vertex_key and VERTEX_FALLBACK_MODEL not in candidate_list:
                candidate_list.append(VERTEX_FALLBACK_MODEL)
            candidates = tuple(candidate_list)
        else:
            candidates = (self.model,)
        previous_model = self.model
        last_switch_status = 429
        last_switch_reason = "quota"
        last_not_found: AIError | None = None
        for actual_model in candidates:
            try:
                slot = self.key_pool.next_slot(actual_model)
            except AIError as error:
                if error.code != "provider_quota":
                    raise
                continue
            if actual_model == VERTEX_FALLBACK_MODEL and not is_vertex_express_key(
                self.key_pool.keys[slot]
            ):
                continue
            if actual_model != previous_model:
                self.log.emit(
                    "provider_model_switch",
                    purpose=purpose,
                    fromModel=previous_model,
                    toModel=actual_model,
                    httpStatus=last_switch_status,
                    reason=last_switch_reason,
                )
            previous_model = actual_model
            retried = False
            while True:
                try:
                    return await self._call_once(purpose, body, slot, actual_model)
                except AIError as error:
                    if error.http_status == 429 or error.code == "provider_auth":
                        if error.code == "provider_auth":
                            self.key_pool.invalid.add(slot)
                        else:
                            self.key_pool.mark_rate_limited(actual_model, slot)
                        try:
                            previous, slot = slot, self.key_pool.next_slot(actual_model)
                        except AIError as exhausted:
                            if exhausted.code != "provider_quota":
                                raise
                            last_switch_status = 429
                            last_switch_reason = "quota"
                            break
                        self.log.emit(
                            "provider_key_switch",
                            purpose=purpose,
                            model=actual_model,
                            fromKeySlot=previous + 1,
                            toKeySlot=slot + 1,
                            httpStatus=error.http_status,
                            reason=error.code,
                        )
                    elif error.code == "provider_model_not_found" and self.auto_fallback:
                        last_not_found = error
                        last_switch_status = 404
                        last_switch_reason = "not_found"
                        break
                    elif (
                        not retried
                        and self.budget is not None
                        and error.http_status in {502, 503, 504}
                    ):
                        retried = True
                        self.log.emit(
                            "provider_retry",
                            purpose=purpose,
                            model=actual_model,
                            httpStatus=error.http_status,
                        )
                        await asyncio.sleep(min(1, self.budget.remaining()))
                    else:
                        raise
        if last_not_found is not None and not self.key_pool.exhausted:
            raise last_not_found
        raise AIError(
            "provider_quota",
            "Các key/model Gemini được phép đã hết quota trong lượt này. "
            "Chờ quota phục hồi; đề cũ được giữ nguyên.",
        )

    def _build_vertex_express_payload(self, body, output_limit: int, actual_model: str) -> dict:
        system_texts: list[str] = []
        contents: list[dict] = []
        for msg in body.get("messages", []):
            role = str(msg.get("role", "user"))
            text = str(msg.get("content") or "")
            if role == "system":
                if text:
                    system_texts.append(text)
                continue
            vertex_role = "model" if role == "assistant" else "user"
            parts: list[dict] = []
            if text:
                parts.append({"text": text})
            if parts:
                contents.append({"role": vertex_role, "parts": parts})
        if "format" in body:
            system_texts.append(
                "Trả về đúng một chuỗi JSON hợp lệ khớp hoàn toàn với JSON Schema sau, "
                "không dùng markdown: " + json.dumps(body["format"], ensure_ascii=False)
            )
        if "document" in body:
            doc = body["document"]
            inline_part = {
                "inlineData": {
                    "mimeType": doc["mimeType"],
                    "data": doc["data"],
                }
            }
            last_user = next(
                (item for item in reversed(contents) if item.get("role") == "user"),
                None,
            )
            if last_user is not None:
                last_user["parts"].append(inline_part)
            else:
                contents.append({"role": "user", "parts": [inline_part]})
        if not contents:
            contents.append(
                {
                    "role": "user",
                    "parts": [{"text": "Thực hiện yêu cầu theo chỉ dẫn hệ thống."}],
                }
            )
        options = body.get("options") if isinstance(body.get("options"), dict) else {}
        temperature = options.get("temperature", 0)
        max_out = (
            max(8192, output_limit)
            if "document" in body
            else (max(16384, output_limit) if actual_model == "gemini-4-hydrogen" else output_limit)
        )
        generation_config: dict = {
            "temperature": temperature,
            "maxOutputTokens": max_out,
        }
        if "format" in body:
            generation_config["responseMimeType"] = "application/json"
        payload: dict = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_texts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_texts)}]}
        return payload

    async def _call_once(self, purpose, body, slot, actual_model):
        if self.budget:
            self.budget.spend()
        elif self.log.index >= 8:
            raise AIError("model_call_limit", "Đã hết tám lần gọi API của tác vụ thử.")
        batch_size = 0
        for tool in body.get("tools", []):
            questions = (
                tool.get("function", {})
                .get("parameters", {})
                .get("properties", {})
                .get("questions", {})
            )
            batch_size = max(batch_size, questions.get("maxItems", 0))
        properties = body.get("format", {}).get("properties", {})
        for field in ("reviews", "slots", "matrix"):
            batch_size = max(batch_size, properties.get(field, {}).get("maxItems", 0))
        if purpose.startswith("scoped_patch"):
            batch_size = max(batch_size, 4)
        # Thinking và nội dung/công cụ dùng chung trần; không cắt phần trả lời để ép nhanh.
        output_limit = min(32768, 8192 + batch_size * 1400) if batch_size else 4096
        active_key = self.key_pool.keys[slot]
        is_vertex = is_vertex_express_key(active_key)

        if is_vertex:
            endpoint = f"{VERTEX_EXPRESS_BASE}/{actual_model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": active_key,
            }
            payload = self._build_vertex_express_payload(body, output_limit, actual_model)
        else:
            payload = {
                "model": actual_model,
                "stream": False,
                "temperature": 0,
                "max_tokens": output_limit,
                "messages": gemini_messages(body["messages"]),
            }
            if actual_model == "gemini-4-hydrogen":
                # Hydrogen tính cả thinking trong trần token; 4096 có thể hết trước lời gọi tool.
                payload.update(max_tokens=max(16384, output_limit), reasoning_effort="low")
            if "tools" in body:
                payload["tools"] = body["tools"]
            if "format" in body:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "review", "strict": True, "schema": body["format"]},
                }
                if purpose.startswith("scoped_patch") or purpose == "question_check":
                    # Union mảng phương án/barem bị API từ chối; Python vẫn kiểm toàn bộ schema.
                    payload["response_format"] = {"type": "json_object"}
                    payload["messages"][0]["content"] += (
                        " Trả JSON đúng schema sau, không dùng markdown: "
                        + json.dumps(body["format"], ensure_ascii=False)
                    )
            endpoint = GEMINI_ENDPOINT
            headers = {"Authorization": "Bearer " + active_key}
            if "document" in body:
                # PDF/ảnh dùng inlineData của API native; không coi nhị phân là văn bản.
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{actual_model}:generateContent"
                headers = {"x-goog-api-key": active_key}
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": "\n".join(m["content"] for m in body["messages"])},
                                {"inlineData": body["document"]},
                            ],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": max(8192, payload["max_tokens"]),
                        "responseMimeType": "application/json",
                        "responseJsonSchema": body["format"],
                    },
                }
        self.log.index += 1
        index, started = self.log.index, time.perf_counter()
        self.log.write(f"call-{index:02}-request.json", redact_secrets(payload, self.key_pool.keys))
        self.log.emit(
            "model_start", modelCall=index, purpose=purpose, model=actual_model, keySlot=slot + 1
        )
        try:
            data = bytearray()
            async with self.client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=headers,
                timeout=180,
                follow_redirects=False,
            ) as response:
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AIError("result_limit", "Phản hồi Gemini vượt giới hạn.")
                    data.extend(chunk)
                if response.status_code >= 300:
                    # Không giữ headers/body lỗi gốc; bỏ khóa khỏi lời báo trước khi ghi.
                    details = {"httpStatus": response.status_code}
                    try:
                        failure = json.loads(data)
                        if isinstance(failure, list):
                            failure = failure[0]
                        error = failure["error"]
                        message = str(redact_secrets(str(error["message"]), self.key_pool.keys))
                        details["message"] = message[:600]
                    except (ValueError, KeyError, TypeError, IndexError):
                        pass
                    self.log.write(
                        f"call-{index:02}-error.json",
                        redact_secrets(details, self.key_pool.keys),
                    )
                    if is_vertex and response.status_code in {401, 403}:
                        raise AIError(
                            "provider_auth",
                            "Khóa Vertex AI Express chưa hợp lệ hoặc bị từ chối.",
                            http_status=response.status_code,
                        )
                    if is_vertex and response.status_code == 404:
                        raise AIError(
                            "provider_model_not_found",
                            f"Model {actual_model} chưa mở trên Vertex AI Express (HTTP 404).",
                            http_status=404,
                        )
                    if response.status_code == 401 or (
                        response.status_code == 400
                        and "valid api key" in str(details.get("message", "")).casefold()
                    ):
                        raise AIError(
                            "provider_auth",
                            "Khóa Gemini chưa hợp lệ. Mở Kết nối để thay khóa; bản đề giữ nguyên.",
                            http_status=response.status_code,
                        )
                    code = (
                        "provider_quota" if response.status_code == 429 else "provider_http_error"
                    )
                    raise AIError(
                        code,
                        f"Gemini trả HTTP {response.status_code}; chưa đổi dịch vụ. "
                        + str(details.get("message", "")),
                        http_status=response.status_code,
                    )
            raw = json.loads(data)
            self.log.write(
                f"call-{index:02}-response.json", redact_secrets(raw, self.key_pool.keys)
            )
            if is_vertex:
                candidates_resp = raw.get("candidates", [])
                if not candidates_resp or candidates_resp[0].get("finishReason") not in {
                    "STOP",
                    None,
                    "",
                }:
                    raise AIError(
                        "incomplete_response",
                        "Vertex AI Express chưa hoàn tất phản hồi.",
                    )
                raw_text = "".join(
                    str(p.get("text", ""))
                    for p in candidates_resp[0].get("content", {}).get("parts", [])
                    if isinstance(p, dict) and not p.get("thought") and "text" in p
                )
                content = sanitize_json_latex_escapes(raw_text)
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    model=actual_model,
                    provider="vertex-express",
                    ok=True,
                    seconds=round(time.perf_counter() - started, 6),
                    keySlot=slot + 1,
                    metrics=raw.get("usageMetadata", {}),
                )
                return {
                    "role": "assistant",
                    "content": content,
                    "model": actual_model,
                    "provider": "vertex-express",
                }
            if "document" in body:
                candidates = raw.get("candidates", [])
                if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                    raise AIError(
                        "incomplete_response",
                        "Gemini chưa đọc xong tài liệu; chưa áp dụng ma trận.",
                    )
                raw = {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "".join(
                                    p.get("text", "")
                                    for p in candidates[0].get("content", {}).get("parts", [])
                                    if not p.get("thought")
                                ),
                            },
                        }
                    ],
                    "usage": raw.get("usageMetadata", {}),
                }
            choices = raw.get("choices", [])
            if len(choices) != 1 or choices[0].get("finish_reason") not in {"stop", "tool_calls"}:
                raise AIError("incomplete_response", "Gemini chưa hoàn tất phản hồi.")
            source_message = choices[0].get("message")
            if not isinstance(source_message, dict):
                raise AIError("invalid_response", "Gemini chưa trả nội dung trợ lý hợp lệ.")
            message = copy.deepcopy(source_message)
            if message.get("role") != "assistant" or message.get("refusal"):
                raise AIError("invalid_response", "Gemini chưa trả kết quả trợ lý hợp lệ.")
            tool_calls = message.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                raise AIError("invalid_response", "Danh sách công cụ Gemini không hợp lệ.")
            for call in tool_calls:
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not call["id"]
                ):
                    raise AIError("invalid_response", "Gemini thiếu mã lời gọi công cụ.")
                arguments = call["function"]["arguments"]
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if not isinstance(arguments, dict):
                    raise AIError("invalid_response", "Tham số công cụ Gemini không hợp lệ.")
                call["function"]["arguments"] = arguments
            message["content"] = message.get("content") or ""
            self.log.emit(
                "model_end",
                modelCall=index,
                purpose=purpose,
                model=actual_model,
                ok=True,
                seconds=round(time.perf_counter() - started, 6),
                keySlot=slot + 1,
                metrics=raw.get("usage", {}),
            )
            return message
        except BaseException:
            self.log.emit(
                "model_end",
                modelCall=index,
                purpose=purpose,
                model=actual_model,
                ok=False,
                seconds=round(time.perf_counter() - started, 6),
                keySlot=slot + 1,
            )
            raise
