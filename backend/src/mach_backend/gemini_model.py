"""Gọi Gemini qua REST tương thích; giữ cùng vòng công cụ và bộ kiểm Python."""

import asyncio
import copy
import json
import time

import httpx

from mach_backend.ai_contract import AIError
from mach_backend.ai_service import MAX_RESPONSE_BYTES

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_MODELS = (GEMINI_MODEL, "gemini-3.8-flash", "gemini-4-hydrogen")


def clean_api_key(key):
    if not isinstance(key, str) or not 8 <= len(key.strip()) <= 300 or "\n" in key or "\r" in key:
        raise AIError("provider_unconfigured", "Nhập Gemini API key trong phần kết nối của app.")
    return key.strip()


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
    """Luân phiên hai project đã được chấp thuận; bỏ key gặp 429 trong tác vụ hiện tại."""

    def __init__(self, key, backup_key=""):
        self.keys = tuple(dict.fromkeys(clean_api_key(k) for k in (key, backup_key) if k))
        if not self.keys:
            clean_api_key("")
        self.index, self.exhausted = 0, set()
        self.invalid = set()

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
        candidates = (
            (self.model, *(m for m in GEMINI_MODELS if m != self.model))
            if self.auto_fallback
            else (self.model,)
        )
        previous_model = self.model
        for actual_model in candidates:
            try:
                slot = self.key_pool.next_slot(actual_model)
            except AIError as error:
                if error.code != "provider_quota":
                    raise
                continue
            if actual_model != previous_model:
                self.log.emit(
                    "provider_model_switch",
                    purpose=purpose,
                    fromModel=previous_model,
                    toModel=actual_model,
                    httpStatus=429,
                    reason="quota",
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
                            self.key_pool.exhausted.add((actual_model, slot))
                        try:
                            previous, slot = slot, self.key_pool.next_slot(actual_model)
                        except AIError as exhausted:
                            if exhausted.code != "provider_quota":
                                raise
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
        raise AIError(
            "provider_quota",
            "Các key/model Gemini được phép đã hết quota trong lượt này. "
            "Chờ quota phục hồi; đề cũ được giữ nguyên.",
        )

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
        headers = {"Authorization": "Bearer " + self.key_pool.keys[slot]}
        if "document" in body:
            # PDF/ảnh dùng inlineData của API native; không coi nhị phân là văn bản.
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{actual_model}:generateContent"
            headers = {"x-goog-api-key": self.key_pool.keys[slot]}
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
        self.log.write(f"call-{index:02}-request.json", payload)
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
                        message = str(error["message"])
                        for secret in self.key_pool.keys:
                            message = message.replace(secret, "[ĐÃ ẨN KHÓA]")
                        details["message"] = message[:600]
                    except (ValueError, KeyError, TypeError, IndexError):
                        pass
                    self.log.write(f"call-{index:02}-error.json", details)
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
            self.log.write(f"call-{index:02}-response.json", raw)
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
