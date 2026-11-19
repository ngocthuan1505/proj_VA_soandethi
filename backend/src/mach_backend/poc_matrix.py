"""Chạy PoC không cần UI, lưu JSONL và phản hồi nguyên gốc để kiểm lại."""

import argparse
import asyncio
import hashlib
import io
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import ValidationError

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import GenerateJob
from mach_backend.ai_service import MAX_RESPONSE_BYTES, OllamaProvider
from mach_backend.matrix_agent import run_matrix_agent, sha256_json

API = "http://127.0.0.1:11434"


def structured_tool_request(body):
    """Mã hóa yêu cầu công cụ bằng JSON; không giả thành native tool calling."""
    choices = []
    definitions = {}
    for tool in body["tools"]:
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
    schema = {"oneOf": choices}
    if definitions:
        schema["$defs"] = definitions
    history = body["messages"]
    restart = (
        len(history) >= 4
        and history[-1].get("tool_name") == "check_exam"
        and json.loads(history[-1]["content"]).get("reusedFromAttempt") is not None
    )
    if restart:
        # Mẫu trả lời trùng trong lịch sử khiến model tiếp tục chép lại cả bộ cũ.
        history = [*history[:2], history[-1]]
    messages = []
    for message in history:
        if message["role"] == "tool":
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "toolResult": message["tool_name"],
                            "result": json.loads(message["content"]),
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        elif "tool_calls" in message:
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
    messages[0]["content"] += (
        " Giao thức lượt này là JSON action, không phải native tool calling. "
        "Bạn chọn action và tự viết arguments. Python chỉ thực thi công cụ được phép "
        "rồi trả toolResult để bạn tự sửa. Khi result.ok=false, xử lý result.errors "
        "và làm theo result.repairInstruction nếu có trước khi nộp lại. "
        "Trả đúng JSON theo schema: " + json.dumps(schema, ensure_ascii=False)
    )
    if restart:
        messages[0]["content"] += (
            " Bộ câu trước bị nộp lặp và đã rút khỏi ngữ cảnh. "
            "Hãy soạn lại toàn bộ từ ma trận và nguồn ban đầu. Với mỗi lỗi có ordinal "
            "(đếm từ 0), đặt câu hỏi mới cho đúng ô đó, dùng dữ kiện hoặc cách hỏi khác. "
            "Tự giải từng câu mới rồi mới nộp qua check_exam."
        )
    request = {"messages": messages, "format": schema}
    if "options" in body:
        request["options"] = body["options"]
    return request


def structured_tool_response(message):
    action = json.loads(message["content"])
    if (
        not isinstance(action, dict)
        or set(action) != {"action", "arguments"}
        or action["action"] not in {"check_exam", "finish_exam"}
        or not isinstance(action["arguments"], dict)
    ):
        raise AIError("invalid_action", "Model trả yêu cầu công cụ không hợp lệ.")
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": action["action"], "arguments": action["arguments"]}}],
    }


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
        self, client: httpx.AsyncClient, model: str, log: RunLog, *, protocol="native", budget=None
    ):
        OllamaProvider(model)
        self.client, self.model, self.log = client, model, log
        self.protocol = protocol
        self.budget = budget

    async def __call__(self, purpose, body):
        if self.budget:
            self.budget.spend()
        if purpose == "agent" and self.protocol == "structured":
            body = structured_tool_request(body)
        self.log.index += 1
        index = self.log.index
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": "5m",
            **body,
            "options": {
                "temperature": 0,
                "num_ctx": 8192,
                "num_predict": 2400,
                **body.get("options", {}),
            },
        }
        self.log.write(f"call-{index:02}-request.json", payload)
        self.log.emit("model_start", modelCall=index, purpose=purpose, model=self.model)
        at = time.perf_counter()
        data = bytearray()
        try:
            timeout = httpx.Timeout(self.budget.remaining(), connect=5) if self.budget else 300
            async with self.client.stream(
                "POST", API + "/api/chat", json=payload, timeout=timeout
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise AIError("result_limit", "Phản hồi model vượt giới hạn.")
                    data.extend(chunk)
            raw = json.loads(data)
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
            self.log.emit(
                "model_end",
                modelCall=index,
                purpose=purpose,
                ok=True,
                seconds=round(time.perf_counter() - at, 6),
                metrics=metrics,
            )
            if purpose == "agent" and self.protocol == "structured":
                return structured_tool_response(message)
            return message
        except BaseException:
            self.log.emit(
                "model_end",
                modelCall=index,
                purpose=purpose,
                ok=False,
                seconds=round(time.perf_counter() - at, 6),
            )
            raise


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
