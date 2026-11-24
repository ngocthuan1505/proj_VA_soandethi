"""Chạy PoC không cần UI, lưu JSONL và phản hồi nguyên gốc để kiểm lại."""

import argparse
import asyncio
import hashlib
import io
import json
import platform
import sys
import time
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from pydantic import ValidationError

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import GenerateJob
from mach_backend.ai_router import structured_tool_request, structured_tool_response
from mach_backend.ai_service import MAX_RESPONSE_BYTES, OllamaProvider
from mach_backend.matrix_agent import run_matrix_agent, sha256_json

API = "http://127.0.0.1:11434"


class RunLog:
    def __init__(self, directory: Path, *, on_event=None):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.at = time.perf_counter()
        self.index = 0
        self.calls = []
        self.on_event = on_event

    def emit(self, event, **fields):
        if event == "model_end":
            self.calls.append(dict(fields))
        value = {
            "event": event,
            "utc": datetime.now(UTC).isoformat(),
            "elapsedSeconds": round(time.perf_counter() - self.at, 6),
            **fields,
        }
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(value, ensure_ascii=False) + "\n")
        if self.on_event:
            self.on_event(value)
        # Terminal Windows có thể dùng cp1252; lỗi hiển thị không được làm hỏng tác vụ.
        print(json.dumps(value, ensure_ascii=True), flush=True)

    def write(self, name, value):
        (self.directory / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )


class LocalModel:
    def __init__(
        self,
        client: httpx.AsyncClient | None,
        model: str,
        log: RunLog | None = None,
        *,
        protocol="native",
        budget=None,
        base_url: str = API,
    ):
        OllamaProvider(model)
        self.client, self.model, self.log = client, model, log
        self.protocol = protocol
        self.budget = budget
        self.base_url = (base_url or API).rstrip("/")

    async def __call__(self, purpose, body):
        if self.budget:
            self.budget.spend()
        original_body = body
        use_structured_tools = self.protocol == "structured" and (
            purpose == "agent" or "tools" in original_body
        )
        if use_structured_tools:
            body = structured_tool_request(original_body)
        if self.log is not None:
            self.log.index += 1
            index = self.log.index
        else:
            index = 1
        schema_props = (
            body.get("format", {}).get("properties", {})
            if isinstance(body.get("format"), dict)
            else {}
        )
        is_batch_call = (
            use_structured_tools
            or any(k in schema_props for k in ("questions", "slots"))
            or str(purpose).startswith(("batch", "generate", "matrix", "M03", "M04", "M05"))
        )
        default_predict = 4096 if is_batch_call else 2400
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": "5m",
            **body,
            "options": {
                "temperature": 0,
                "num_ctx": 8192,
                "num_predict": default_predict,
                **body.get("options", {}),
            },
        }
        if self.protocol == "structured" and self.model.partition(":")[0] == "qwen3":
            # Qwen3 can spend the entire output limit on thinking before emitting any JSON.
            payload.setdefault("think", False)
        if self.log is not None:
            self.log.write(f"call-{index:02}-request.json", payload)
            self.log.emit("model_start", modelCall=index, purpose=purpose, model=self.model)
        at = time.perf_counter()
        data = bytearray()
        try:
            assert self.client is not None
            timeout = httpx.Timeout(self.budget.remaining(), connect=5) if self.budget else 300
            async with self.client.stream(
                "POST", self.base_url + "/api/chat", json=payload, timeout=timeout
            ) as response:
                if response.status_code == 429:
                    raise AIError(
                        "provider_quota",
                        "Ollama đang quá tải hoặc gặp giới hạn 429.",
                        http_status=429,
                    )
                if response.status_code >= 500:
                    raise AIError(
                        "provider_unavailable",
                        f"Ollama tạm gián đoạn (HTTP {response.status_code}).",
                        http_status=response.status_code,
                    )
                if response.status_code >= 400:
                    raise AIError(
                        "provider_http_error",
                        f"Ollama trả HTTP {response.status_code}.",
                        http_status=response.status_code,
                    )
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AIError("result_limit", "Phản hồi model vượt giới hạn.")
                    data.extend(chunk)
            raw = json.loads(data)
            if self.log is not None:
                self.log.write(f"call-{index:02}-response.json", raw)
            if raw.get("done") is not True or raw.get("done_reason") == "length":
                raise AIError("incomplete_response", "Model chưa hoàn tất đầu ra.")
            message = raw.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise AIError("invalid_response", "Phản hồi thiếu message của assistant.")
            metrics = {
                key: raw.get(key)
                for key in (
                    "total_duration",
                    "load_duration",
                    "prompt_eval_count",
                    "prompt_eval_duration",
                    "eval_count",
                    "eval_duration",
                )
            }
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    ok=True,
                    seconds=round(time.perf_counter() - at, 6),
                    metrics=metrics,
                )
            if use_structured_tools:
                allowed_tools = [
                    t["function"]["name"]
                    for t in original_body.get("tools", [])
                    if isinstance(t, dict)
                    and isinstance(t.get("function"), dict)
                    and t["function"].get("name")
                ]
                return structured_tool_response(
                    message,
                    allowed_tools=allowed_tools or None,
                )
            return message
        except httpx.TimeoutException:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    ok=False,
                    seconds=round(time.perf_counter() - at, 6),
                )
            raise AIError(
                "provider_timeout", "Ollama quá thời gian xử lý; chuyển kênh dự phòng."
            ) from None
        except httpx.HTTPError as exc:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    ok=False,
                    seconds=round(time.perf_counter() - at, 6),
                )
            raise AIError(
                "provider_unavailable",
                f"Không kết nối được Ollama cục bộ: {exc}",
            ) from None
        except BaseException:
            if self.log is not None:
                self.log.emit(
                    "model_end",
                    modelCall=index,
                    purpose=purpose,
                    ok=False,
                    seconds=round(time.perf_counter() - at, 6),
                )
            raise

    async def stream_chat(
        self, messages: Sequence[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Phát luồng từng token văn bản từ Ollama /api/chat (NDJSON)."""
        if self.budget:
            self.budget.spend()
        target_model = str(kwargs.get("model") or self.model).strip() or self.model
        OllamaProvider(target_model)
        eff_base = str(kwargs.get("base_url") or self.base_url).rstrip("/")
        options = {
            "temperature": kwargs.get("temperature", 0.2),
            "num_ctx": int(kwargs.get("num_ctx", 8192)),
            "num_predict": int(kwargs.get("num_predict", 4096)),
        }
        payload: dict[str, Any] = {
            "model": target_model,
            "stream": True,
            "keep_alive": "5m",
            "messages": list(messages),
            "options": options,
        }
        if "think" in kwargs:
            payload["think"] = kwargs["think"]
        elif target_model.partition(":")[0] == "qwen3":
            payload["think"] = False

        full_parts: list[str] = []
        usage: dict[str, Any] = {}
        client = self.client or httpx.AsyncClient(trust_env=False, follow_redirects=False)
        owns_client = self.client is None
        timeout = httpx.Timeout(self.budget.remaining(), connect=5) if self.budget else 300
        try:
            async with client.stream(
                "POST", eff_base + "/api/chat", json=payload, timeout=timeout
            ) as response:
                if response.status_code == 429:
                    raise AIError("provider_quota", "Ollama gặp giới hạn 429.", http_status=429)
                if response.status_code >= 500:
                    raise AIError(
                        "provider_unavailable",
                        f"Ollama tạm gián đoạn (HTTP {response.status_code}).",
                        http_status=response.status_code,
                    )
                if response.status_code >= 400:
                    raise AIError(
                        "provider_http_error",
                        f"Ollama trả HTTP {response.status_code}.",
                        http_status=response.status_code,
                    )
                async for line in response.aiter_lines():
                    raw_line = line.strip()
                    if not raw_line:
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except ValueError:
                        continue
                    msg = chunk.get("message")
                    if isinstance(msg, dict):
                        delta = str(msg.get("content") or "")
                        if delta:
                            full_parts.append(delta)
                            yield {"type": "delta", "text": delta}
                    if chunk.get("done") is True:
                        usage = {
                            k: chunk.get(k)
                            for k in (
                                "total_duration",
                                "load_duration",
                                "prompt_eval_count",
                                "eval_count",
                            )
                            if chunk.get(k) is not None
                        }
                        break
        except httpx.TimeoutException:
            raise AIError("provider_timeout", "Ollama stream quá thời gian.") from None
        except httpx.HTTPError as exc:
            raise AIError("provider_unavailable", f"Lỗi kết nối stream Ollama: {exc}") from None
        finally:
            if owns_client:
                await client.aclose()

        yield {
            "type": "done",
            "text": "".join(full_parts),
            "provider": "ollama",
            "model": target_model,
            "usage": usage,
        }

    async def vision_ocr(
        self,
        images_b64: list[str],
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Đọc OCR ảnh đề/tài liệu bằng mô hình Vision qua Ollama /api/chat (messages[].images)."""
        cleaned_images = [str(img).strip() for img in images_b64 if str(img).strip()]
        if not cleaned_images:
            raise AIError("invalid_request", "Thiếu dữ liệu ảnh base64 để OCR.")
        if self.budget:
            self.budget.spend()
        target_model = str(model or self.model).strip() or self.model
        OllamaProvider(target_model)
        eff_base = str(base_url or self.base_url).rstrip("/")
        payload = {
            "model": target_model,
            "stream": False,
            "keep_alive": "5m",
            "messages": [
                {
                    "role": "user",
                    "content": str(
                        prompt
                        or (
                            "Trích xuất chính xác toàn bộ nội dung văn bản, công thức LaTeX "
                            "và bảng biểu từ ảnh."
                        )
                    ),
                    "images": cleaned_images,
                }
            ],
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 4096},
        }
        client = self.client or httpx.AsyncClient(trust_env=False, follow_redirects=False)
        owns_client = self.client is None
        timeout = httpx.Timeout(self.budget.remaining(), connect=5) if self.budget else 300
        data = bytearray()
        try:
            async with client.stream(
                "POST", eff_base + "/api/chat", json=payload, timeout=timeout
            ) as response:
                if response.status_code == 429:
                    raise AIError(
                        "provider_quota", "Ollama Vision gặp giới hạn 429.", http_status=429
                    )
                if response.status_code >= 500:
                    raise AIError(
                        "provider_unavailable",
                        f"Ollama Vision tạm gián đoạn (HTTP {response.status_code}).",
                        http_status=response.status_code,
                    )
                if response.status_code >= 400:
                    raise AIError(
                        "provider_http_error",
                        f"Ollama Vision trả HTTP {response.status_code}.",
                        http_status=response.status_code,
                    )
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AIError("result_limit", "Phản hồi Ollama Vision vượt giới hạn.")
                    data.extend(chunk)
            raw = json.loads(data)
            if raw.get("done") is not True:
                raise AIError("incomplete_response", "Ollama Vision chưa hoàn tất phản hồi.")
            msg = raw.get("message")
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                raise AIError("invalid_response", "Phản hồi Ollama Vision không hợp lệ.")
            text = str(msg.get("content") or "")
            return {
                "role": "assistant",
                "content": text,
                "text": text,
                "provider": "ollama",
                "model": target_model,
                "usage": {
                    k: raw.get(k)
                    for k in ("total_duration", "prompt_eval_count", "eval_count")
                    if raw.get(k) is not None
                },
            }
        except httpx.TimeoutException:
            raise AIError("provider_timeout", "Ollama Vision quá thời gian xử lý.") from None
        except httpx.HTTPError as exc:
            raise AIError(
                "provider_unavailable", f"Không kết nối được Ollama Vision: {exc}"
            ) from None
        finally:
            if owns_client:
                await client.aclose()


async def run(args):
    log = RunLog(args.output)
    trial_id = str(uuid4())
    result = {"status": "not_started", "saved": False}
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8-sig"))
        job = GenerateJob.model_validate_json(json.dumps(raw, ensure_ascii=False))
        log.write("input.json", raw)
        source_hashes = {}
        for path in sorted(Path(__file__).parent.glob("*.py")):
            name, content = path.name, path.read_bytes()
            source_hashes[name] = hashlib.sha256(content).hexdigest()
            snapshot = log.directory / "source-snapshot"
            snapshot.mkdir(exist_ok=True)
            (snapshot / name).write_bytes(content)
        async with httpx.AsyncClient(
            trust_env=False, follow_redirects=False, timeout=180
        ) as client:
            version = (await client.get(API + "/api/version")).json()
            tags = (await client.get(API + "/api/tags")).json()
            selected = [m for m in tags.get("models", []) if m.get("name") == args.model]
            if len(selected) != 1 or selected[0].get("remote_host"):
                raise AIError("model_not_local", "Chọn đúng model đã tải trên laptop.")
            show = (await client.post(API + "/api/show", json={"model": args.model})).json()
            capabilities = show.get("capabilities", [])
            log.emit(
                "run_start",
                trialId=trial_id,
                model=args.model,
                inputSha256=sha256_json(raw),
                maxGenerationAttempts=args.max_attempts,
                timeoutSeconds=args.timeout,
                mode="real_local_model",
                toolProtocol=args.protocol,
            )
            log.write(
                "environment.json",
                {
                    "trialId": trial_id,
                    "python": sys.version,
                    "platform": platform.platform(),
                    "ollamaVersion": version,
                    "model": selected[0],
                    "capabilities": capabilities,
                    "sourceCodeSha256": source_hashes,
                    "inputSha256": sha256_json(raw),
                    "semanticCheck": "model_assisted_not_ground_truth",
                    "toolProtocol": args.protocol,
                },
            )
            if args.protocol == "native" and "tools" not in capabilities:
                raise AIError("tools_unsupported", "Model không công bố hỗ trợ tool calling.")
            model = LocalModel(client, args.model, log, protocol=args.protocol)
            async with asyncio.timeout(args.timeout):
                result = await run_matrix_agent(
                    job, model, log.emit, max_attempts=args.max_attempts
                )
            active = (await client.get(API + "/api/ps")).json()
            log.write("runtime-final.json", active)
    except TimeoutError:
        result = {"status": "timeout", "saved": False}
    except asyncio.CancelledError:
        result = {"status": "cancelled", "saved": False}
    except (AIError, ValidationError, httpx.HTTPError, OSError, ValueError, KeyError) as error:
        result = {
            "status": "failed",
            "saved": False,
            "errorCode": error.code if isinstance(error, AIError) else type(error).__name__,
        }
    result = {
        "trialId": trial_id,
        **result,
        "saved": False,
        "modelCalls": log.index,
        "elapsedSeconds": round(time.perf_counter() - log.at, 6),
        "qualityClaim": "Chưa thay đánh giá sư phạm độc lập.",
    }
    log.write("result.json", result)
    log.emit("run_end", **result)
    return 0 if result["status"] == "ready_for_teacher_review" else 2


def main():
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="PoC sinh bộ câu, gọi công cụ kiểm và ghi log thật."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--protocol", choices=("native", "structured"), default="structured")
    parser.add_argument("--max-attempts", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 1800:
        parser.error("Giới hạn thời gian từ 1 đến 1800 giây.")
    try:
        code = asyncio.run(run(args))
    except FileExistsError:
        parser.error("Thư mục đầu ra đã tồn tại; chọn thư mục mới để giữ log cũ.")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
