"""Kiểm hợp đồng Gemini bằng transport giả lập, không gọi dịch vụ hay dùng khóa thật."""

import asyncio
import copy
import json

import httpx
import pytest

from mach_backend.gemini_model import GEMINI_ENDPOINT, GeminiKeyPool, GeminiModel, gemini_messages
from mach_backend.poc_matrix import RunLog

KEY = "fake-secret-for-test"


def test_scoped_edit_with_rubric_uses_json_mode_and_keeps_schema_instruction(tmp_path):
    from mach_backend.poc_scoped_patch import Draft

    schema = Draft.model_json_schema()

    def respond(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "RubricRow" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"edits":[],"message":"Chưa có thay đổi"}',
                        },
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            body = {
                "messages": [{"role": "system", "content": "Sửa đúng phạm vi."}],
                "format": schema,
            }
            before = copy.deepcopy(body)
            response = await GeminiModel(client, KEY, RunLog(tmp_path / "rubric"))(
                "scoped_patch", body
            )
            assert body == before
            # JSON hợp lệ chưa có nghĩa đúng hợp đồng: bỏ trống thay đổi vẫn bị Python chặn.
            with pytest.raises(ValueError):
                Draft.model_validate_json(response["content"])

    asyncio.run(run())


@pytest.mark.parametrize("model", ["gemini-4-hydrogen", "gemini-3.6-flash"])
def test_hydrogen_has_room_for_thinking_without_changing_flash(tmp_path, model):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] == (16384 if model == "gemini-4-hydrogen" else 4096)
        assert payload.get("reasoning_effort") == ("low" if model == "gemini-4-hydrogen" else None)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(client, KEY, RunLog(tmp_path / "tokens"), model=model)(
                "agent", {"messages": []}
            )

    asyncio.run(run())


def test_tool_ids_and_opaque_signature_survive_feedback_roundtrip():
    calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "check_exam", "arguments": {"questions": []}},
            "extra_content": {"google": {"thought_signature": "opaque-fixture"}},
        }
    ]
    messages = [
        {"role": "assistant", "content": "", "tool_calls": calls},
        {"role": "tool", "tool_name": "check_exam", "content": '{"ok":false}'},
    ]
    before = copy.deepcopy(messages)
    result = gemini_messages(messages)
    assert result[1]["tool_call_id"] == "call-1"
    assert result[0]["tool_calls"][0]["extra_content"] == calls[0]["extra_content"]
    assert json.loads(result[0]["tool_calls"][0]["function"]["arguments"]) == {"questions": []}
    assert messages == before
    with pytest.raises(ValueError, match="không khớp"):
        gemini_messages([messages[1]])


@pytest.mark.parametrize("status,finish", [(200, "tool_calls"), (200, "length"), (429, None)])
def test_api_boundaries_and_logs_do_not_include_key(tmp_path, status, finish):
    def respond(request):
        assert str(request.url) == GEMINI_ENDPOINT
        assert request.headers["authorization"] == "Bearer " + KEY
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        if status == 429:
            return httpx.Response(status, json=[{"error": {"message": KEY}}])
        return httpx.Response(
            status,
            json={
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {"name": "finish_exam", "arguments": "{}"},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"completion_tokens": 12},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await GeminiModel(client, KEY, RunLog(tmp_path / "log"))(
                "test", {"messages": [{"role": "user", "content": "Dữ liệu thử."}], "format": {}}
            )

    if status == 200 and finish == "tool_calls":
        result = asyncio.run(run())
        assert result["tool_calls"][0]["function"]["arguments"] == {}
    else:
        with pytest.raises(ValueError):
            asyncio.run(run())
    assert all(KEY not in p.read_text(encoding="utf8") for p in (tmp_path / "log").glob("*"))


def test_key_and_model_are_explicit_and_calls_are_bounded(tmp_path):
    log = RunLog(tmp_path / "log")
    with pytest.raises(ValueError):
        GeminiModel(None, "", log)
    with pytest.raises(ValueError):
        GeminiModel(None, KEY, log, model="https://other-host.invalid")
    log.index = 8
    with pytest.raises(ValueError, match="tám"):
        asyncio.run(GeminiModel(None, KEY, log)("agent", {"messages": []}))


def test_invalid_key_has_actionable_error_and_is_not_echoed(tmp_path):
    from mach_backend.ai_contract import AIError

    def respond(_request):
        return httpx.Response(
            400, json={"error": {"message": "Please pass a valid API key " + KEY}}
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(client, KEY, RunLog(tmp_path / "log"))(
                "agent", {"messages": [{"role": "user", "content": "Fixture"}]}
            )

    with pytest.raises(AIError) as error:
        asyncio.run(run())
    assert error.value.code == "provider_auth"
    assert KEY not in str(error.value)
    assert all(KEY not in f.read_text(encoding="utf8") for f in (tmp_path / "log").glob("*"))


@pytest.mark.parametrize(
    "statuses,expected_calls", [([503, 200], 2), ([503, 503], 2), ([429], 1), ([400], 1)]
)
def test_transient_retry_is_bounded_and_spends_same_budget(
    tmp_path, monkeypatch, statuses, expected_calls
):
    from mach_backend.ai_contract import AIError
    from mach_backend.poc_policy import CallBudget

    async def no_wait(_):
        return None

    monkeypatch.setattr("mach_backend.gemini_model.asyncio.sleep", no_wait)
    replies = iter(statuses)
    budget = CallBudget(4, 30)

    def respond(_):
        status = next(replies)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "Fixture dịch vụ."}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Fixture"},
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await GeminiModel(
                client, KEY, RunLog(tmp_path / "log"), budget=budget, auto_fallback=False
            )("agent", {"messages": [{"role": "user", "content": "Fixture"}]})

    if statuses[-1] == 200:
        assert asyncio.run(run())["content"] == "Fixture"
    else:
        with pytest.raises(AIError):
            asyncio.run(run())
    assert budget.calls == expected_calls


def test_retry_cannot_go_past_remaining_call_budget(tmp_path, monkeypatch):
    from mach_backend.ai_contract import AIError
    from mach_backend.poc_policy import CallBudget

    async def no_wait(_):
        return None

    monkeypatch.setattr("mach_backend.gemini_model.asyncio.sleep", no_wait)
    budget = CallBudget(1, 30)
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(503, json={"error": {"message": "Fixture"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(
                client, KEY, RunLog(tmp_path / "log"), budget=budget, auto_fallback=False
            )("agent", {"messages": []})

    with pytest.raises(AIError) as error:
        asyncio.run(run())
    assert error.value.code == "call_budget" and len(seen) == 1


@pytest.mark.parametrize(
    "statuses,slots,error_code",
    [
        ([200, 200, 200], [1, 2, 1], None),
        ([429, 200, 200], [1, 2, 2], None),
        ([429, 429], [1, 2], "provider_quota"),
        ([401, 401], [1, 2], "provider_auth"),
        ([403], [1], "provider_http_error"),
    ],
)
def test_shared_key_pool_alternates_and_skips_quota_without_leaking_keys(
    tmp_path, statuses, slots, error_code
):
    from mach_backend.ai_contract import AIError
    from mach_backend.poc_policy import CallBudget

    backup = "fake-backup-secret-for-test"
    pool, budget, seen = GeminiKeyPool(KEY, backup), CallBudget(8, 30), []
    replies = iter(statuses)
    log = RunLog(tmp_path / "pool")

    def respond(request):
        seen.append(pool.keys.index(request.headers["authorization"][7:]) + 1)
        status = next(replies)
        return httpx.Response(
            status,
            json=(
                {"error": {"message": KEY + " " + backup}}
                if status != 200
                else {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "Fixture"},
                        }
                    ]
                }
            ),
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            generator = GeminiModel(
                client, KEY, log, key_pool=pool, budget=budget, auto_fallback=False
            )
            reviewer = GeminiModel(
                client, KEY, log, key_pool=pool, budget=budget, auto_fallback=False
            )
            await generator("agent", {"messages": []})
            await reviewer("review", {"messages": []})
            if len(statuses) == 3 and 429 not in statuses:
                await generator("agent", {"messages": []})

    if error_code:
        with pytest.raises(AIError) as error:
            asyncio.run(run())
        assert error.value.code == error_code
        assert KEY not in str(error.value) and backup not in str(error.value)
    else:
        asyncio.run(run())
    assert seen == slots and budget.calls == len(slots)
    events = [
        json.loads(line) for line in (log.directory / "events.jsonl").read_text().splitlines()
    ]
    assert [e["keySlot"] for e in events if e["event"] == "model_start"] == slots
    for file in log.directory.glob("*"):
        assert KEY not in file.read_text(encoding="utf8")
        assert backup not in file.read_text(encoding="utf8")


def test_quota_switch_cannot_exceed_budget(tmp_path):
    from mach_backend.ai_contract import AIError
    from mach_backend.poc_policy import CallBudget

    seen, budget = [], CallBudget(1, 30)

    def respond(request):
        seen.append(request)
        return httpx.Response(429, json={"error": {"message": "Fixture quota"}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(
                client,
                KEY,
                RunLog(tmp_path / "budget"),
                budget=budget,
                key_pool=GeminiKeyPool(KEY, "fake-backup-for-budget"),
            )("agent", {"messages": []})

    with pytest.raises(AIError) as error:
        asyncio.run(run())
    assert error.value.code == "call_budget" and len(seen) == 1 and budget.calls == 1


def test_five_question_batch_has_more_output_room(tmp_path):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] >= 7000
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(client, KEY, RunLog(tmp_path / "five"))(
                "agent",
                {
                    "messages": [],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "check_exam",
                                "parameters": {
                                    "properties": {"questions": {"minItems": 5, "maxItems": 5}}
                                },
                            },
                        }
                    ],
                },
            )

    asyncio.run(run())


@pytest.mark.parametrize("count", [1, 4, 5, 30])
def test_batch_output_reserves_thinking_room_and_remains_bounded(tmp_path, count):
    def respond(request):
        payload = json.loads(request.content)
        # Lượt thật bốn dạng đã hết5.600token mà không trả lời gọi tool nào.
        assert 8192 < payload["max_tokens"] <= 32768
        assert "reasoning_effort" not in payload
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(client, KEY, RunLog(tmp_path / str(count)))(
                "agent",
                {
                    "messages": [],
                    "tools": [
                        {
                            "function": {
                                "parameters": {"properties": {"questions": {"maxItems": count}}}
                            }
                        }
                    ],
                },
            )

    asyncio.run(run())


def test_question_check_uses_json_mode_with_schema_and_validates_stop(tmp_path):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "optionVerdicts" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"fixture":true}'},
                    }
                ]
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await GeminiModel(client, KEY, RunLog(tmp_path / "check"))(
                "question_check",
                {
                    "messages": [{"role": "system", "content": "Giải độc lập."}],
                    "format": {
                        "type": "object",
                        "properties": {"optionVerdicts": {"type": "array"}},
                    },
                },
            )
            assert json.loads(result["content"]) == {"fixture": True}

    asyncio.run(run())
