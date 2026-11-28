"""429 giả lập: đổi key trước model, vẫn cùng ngân sách và không đổi bộ kiểm."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from test_local_workspace import AgentModelFixture, generate
from test_local_workspace import workspace as workspace

from mach_backend.ai_contract import AIError
from mach_backend.gemini_model import GEMINI_MODEL, GEMINI_MODELS, GeminiKeyPool, GeminiModel
from mach_backend.local_workspace import create_app
from mach_backend.poc_matrix import RunLog
from mach_backend.poc_policy import CallBudget

KEY, BACKUP = "fake-primary-model-fallback", "fake-backup-model-fallback"


def response(status=200):
    return httpx.Response(
        status,
        json={
            "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant", "content": "Fixture"}}
            ]
        }
        if status == 200
        else {"error": {"message": "Fixture " + KEY + " " + BACKUP}},
    )


def test_quota_is_per_model_and_shared_by_generator_and_reviewer(tmp_path):
    pool, budget, seen, observed = GeminiKeyPool(KEY, BACKUP), CallBudget(8, 30), [], []
    log = RunLog(tmp_path / "run", on_event=observed.append)

    def respond(request):
        model = json.loads(request.content)["model"]
        seen.append((model, pool.keys.index(request.headers["authorization"][7:])))
        return response(429 if model == GEMINI_MODEL else 200)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            generator = GeminiModel(client, KEY, log, key_pool=pool, budget=budget)
            reviewer = GeminiModel(client, KEY, log, key_pool=pool, budget=budget)
            for model in (generator, reviewer):
                assert (await model("agent", {"messages": []}))["content"] == "Fixture"

    asyncio.run(run())
    assert [model for model, _ in seen] == [
        GEMINI_MODEL,
        GEMINI_MODEL,
        "gemini-3.8-flash",
        "gemini-3.8-flash",
    ]
    assert seen[0][1] != seen[1][1] and budget.calls == 4
    assert any(
        row["event"] == "provider_model_switch" and row["toModel"] == "gemini-3.8-flash"
        for row in observed
    )
    assert log.calls[-1]["model"] == "gemini-3.8-flash"
    assert all(
        KEY not in file.read_text(encoding="utf-8")
        and BACKUP not in file.read_text(encoding="utf-8")
        for file in log.directory.glob("*")
    )


@pytest.mark.parametrize(
    "auto,budget_limit,expected,code",
    [(True, 8, 6, "provider_quota"), (False, 8, 2, "provider_quota"), (True, 2, 2, "call_budget")],
)
def test_all_models_exhausted_or_budget_stops_without_looping(
    tmp_path, auto, budget_limit, expected, code
):
    budget, seen = CallBudget(budget_limit, 30), []

    def respond(request):
        seen.append(json.loads(request.content)["model"])
        return response(429)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(
                client,
                KEY,
                RunLog(tmp_path / "run"),
                key_pool=GeminiKeyPool(KEY, BACKUP),
                budget=budget,
                auto_fallback=auto,
            )("agent", {"messages": []})

    with pytest.raises(AIError) as error:
        asyncio.run(run())
    assert error.value.code == code and len(seen) == expected and budget.calls == expected
    assert "gemini-3.5-flash-lite" not in seen


@pytest.mark.parametrize("status", [400, 403, 503])
def test_other_failures_do_not_switch_models(tmp_path, status):
    seen = []

    def respond(request):
        seen.append(json.loads(request.content)["model"])
        return response(status)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await GeminiModel(client, KEY, RunLog(tmp_path / "run"))("agent", {"messages": []})

    with pytest.raises(AIError):
        asyncio.run(run())
    assert seen == [GEMINI_MODEL]


def test_invalid_key_tries_backup_and_is_not_retried_on_other_models(tmp_path):
    pool, seen = GeminiKeyPool(KEY, BACKUP), []

    def respond(request):
        key = request.headers["authorization"][7:]
        seen.append(key)
        return response(401 if key == KEY else 200)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            model = GeminiModel(client, KEY, RunLog(tmp_path / "run"), key_pool=pool)
            await model("agent", {"messages": []})
            await model("review", {"messages": []})

    asyncio.run(run())
    assert seen == [KEY, BACKUP, BACKUP]


def test_native_document_request_uses_actual_fallback_model(tmp_path):
    seen = []

    def respond(request):
        seen.append(str(request.url))
        if "gemini-3.6-flash:" in str(request.url):
            return response(429)
        return httpx.Response(
            200,
            json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await GeminiModel(client, KEY, RunLog(tmp_path / "native"))(
                "matrix_read",
                {
                    "messages": [{"role": "user", "content": "Fixture"}],
                    "document": {"mimeType": "image/png", "data": "fake"},
                    "format": {"type": "object"},
                },
            )

    assert asyncio.run(run())["content"] == "{}"
    assert len(seen) == 2 and "gemini-3.8-flash:" in seen[1]


def test_config_defaults_fallback_on_can_disable_and_never_offers_lite(tmp_path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        initial = client.get("/api/config").json()
        assert initial["gemini"]["autoFallback"] and "gemini-3.5-flash-lite" not in GEMINI_MODELS
        changed = client.post("/api/config", json={"gemini": {"autoFallback": False}})
        assert changed.status_code == 200 and not changed.json()["gemini"]["autoFallback"]
        assert initial["fingerprint"] != changed.json()["fingerprint"]
        assert (
            client.post(
                "/api/config", json={"gemini": {"model": "gemini-3.5-flash-lite"}}
            ).status_code
            == 400
        )
        assert (
            client.post("/api/config", json={"gemini": {"autoFallback": "yes"}}).status_code == 400
        )


def test_old_saved_lite_configuration_keeps_keys_and_uses_default_model(tmp_path, monkeypatch):
    saved = {
        "routes": {"generate": "gemini", "check": "gemini"},
        "gemini": {
            "key": KEY,
            "backupKey": BACKUP,
            "freeTierConfirmed": True,
            "model": "gemini-3.5-flash-lite",
            "checkModel": "gemini-3.5-flash-lite",
        },
    }
    monkeypatch.setattr("mach_backend.poc_connections.LocalConnectionStore.load", lambda _: saved)
    app = create_app(tmp_path)
    assert app.state.provider.gemini_model == GEMINI_MODEL
    assert app.state.provider.gemini_backup_key == BACKUP and app.state.provider.gemini_key == KEY


def test_fallback_keeps_agent_checks_audit_preview_and_teacher_confirmation(
    workspace, tmp_path, monkeypatch
):
    original, exam, _ = workspace
    fixture = AgentModelFixture()
    real_client = httpx.AsyncClient
    seen = []

    async def respond(request):
        payload = json.loads(request.content)
        seen.append(payload["model"])
        if payload["model"] == GEMINI_MODEL:
            return response(429)
        schema = json.dumps(payload.get("response_format", {}))
        purpose = (
            "agent"
            if "tools" in payload
            else "blind_content_check"
            if "observedLevel" in schema
            else "explanation_check"
        )
        message = await fixture(purpose, {"messages": payload["messages"]})
        message["role"] = "assistant"
        for call in message.get("tool_calls", []):
            call["id"] = "fixture-call-" + str(len(seen))
            call["function"]["arguments"] = json.dumps(call["function"]["arguments"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                        "message": message,
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "mach_backend.workspace_agent.httpx.AsyncClient",
        lambda **kw: real_client(**kw, transport=httpx.MockTransport(respond)),
    )
    app = create_app(tmp_path / "fallback-agent")
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        state = original.get("/api/kv?key=state").json()["value"]
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "routes": {"generate": "gemini", "check": "gemini"},
                "gemini": {"key": KEY, "backupKey": BACKUP, "freeTierConfirmed": True},
                "runBudget": {"maxModelCalls": 16, "timeoutSeconds": 60},
            },
        ).raise_for_status()
        base, result = generate(client, exam)
        assert (
            result["status"] == "complete"
            and client.get("/api/kv?key=state").json()["value"] == state
        )
        trace = client.get(base + "/trace").json()
        assert any(row["event"] == "provider_model_switch" for row in trace)
        assert any(
            row["event"] == "model_start" and row["model"] == "gemini-3.8-flash" for row in trace
        )
        report = client.get(base + "/report").json()
        assert report["summary"]["modelCalls"] == len(seen)
        assert any(call["model"] == "gemini-3.8-flash" for call in report["summary"]["calls"])
        audit = client.get(base + "/audit").json()
        assert audit["traceVerified"] and audit["successfulRepairObserved"], audit
        assert (
            client.post(
                base + "/confirm", json={"baseRevision": 1, "teacherConfirmation": True}
            ).status_code
            == 200
        )
        assert client.get("/api/kv?key=state").json()["value"]["exams"][0]["revision"] == 2
