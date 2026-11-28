"""Kiểm thử định tuyến AGY chat, chống lặp model và chuẩn hóa tool-call."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mach_backend import local_workspace, poc_connections
from mach_backend.agy_cli_model import DEFAULT_AGY_FAST_MODEL, DEFAULT_AGY_ORCHESTRATOR_MODEL
from mach_backend.ai_contract import AIError
from mach_backend.ai_router import (
    M01_OCR,
    M03_EXAM_BLUEPRINT,
    M04_GEN_STANDARD,
    M05_GEN_HARD,
    M06_BLIND_SOLVE,
    M07_DISTRACTOR_CHECK,
    M08_DUPLICATE_SCOPE_CHECK,
    M09_SURGICAL_REPAIR,
    M10_SCOPED_PATCH,
    M11_FLEXIBLE_CHAT,
    FixedTaskRouter,
    reset_shared_circuit_breaker,
    structured_tool_response,
)
from mach_backend.local_workspace import create_app
from mach_backend.poc_connections import install_poc_connections
from mach_backend.workspace_agent import AgentGeneration

ORIGIN = {"Origin": "http://testserver"}


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        ev_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                ev_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            events.append((ev_name, json.loads("\n".join(data_lines))))
    return events


def test_chat_and_stream_pick_tier_specific_agy_models(tmp_path, monkeypatch):
    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_bytes(b"MZ")
    captured: list[dict[str, str | None]] = []

    class FakeTieredAgy:
        def __init__(self, _log, *, custom_path="", budget=None, model=None, effort=None):
            assert custom_path == str(fake_agy)
            self.model = model
            captured.append({"model": model, "effort": effort})

        async def __call__(self, _purpose, _body):
            used = self.model or "agy-cli"
            return {
                "content": json.dumps({"message": f"Đang dùng {used}"}),
                "provider": "agy",
                "model": used,
            }

    monkeypatch.setattr(local_workspace, "AgyCliModel", FakeTieredAgy)
    reset_shared_circuit_breaker()
    try:
        app = create_app(tmp_path / "ws")
        with TestClient(app, headers=ORIGIN) as client:
            client.post(
                "/api/config",
                json={
                    "saveLocally": False,
                    "fixedRouter": {"enabled": True, "agyCustomPath": str(fake_agy)},
                },
            ).raise_for_status()

            r_std = client.post(
                "/api/assistant/chat",
                json={"text": "Xin chào", "consent": True, "timePreset": "standard"},
            )
            assert r_std.status_code == 200, r_std.text
            d_std = r_std.json()
            assert d_std["providerUsed"] == "agy"
            assert d_std["modelUsed"] == DEFAULT_AGY_FAST_MODEL
            assert captured[-1] == {"model": DEFAULT_AGY_FAST_MODEL, "effort": "low"}

            r_deep = client.post(
                "/api/assistant/chat",
                json={"text": "Phân tích ma trận", "consent": True, "timePreset": "deep"},
            )
            assert r_deep.status_code == 200, r_deep.text
            d_deep = r_deep.json()
            assert d_deep["providerUsed"] == "agy"
            assert d_deep["modelUsed"] == DEFAULT_AGY_ORCHESTRATOR_MODEL
            assert captured[-1] == {"model": DEFAULT_AGY_ORCHESTRATOR_MODEL, "effort": "medium"}

            with client.stream(
                "POST",
                "/api/assistant/chat/stream",
                json={"text": "Chào stream", "consent": True, "timePreset": "standard"},
            ) as s_std:
                assert s_std.status_code == 200
                ev_std = _parse_sse(s_std.read().decode("utf-8"))
            done_std = next(payload for ev, payload in ev_std if ev == "done")
            assert done_std["providerUsed"] == "agy"
            assert done_std["modelUsed"] == DEFAULT_AGY_FAST_MODEL

            with client.stream(
                "POST",
                "/api/assistant/chat/stream",
                json={"text": "Sâu stream", "consent": True, "timePreset": "extended"},
            ) as s_ext:
                assert s_ext.status_code == 200
                ev_ext = _parse_sse(s_ext.read().decode("utf-8"))
            done_ext = next(payload for ev, payload in ev_ext if ev == "done")
            assert done_ext["providerUsed"] == "agy"
            assert done_ext["modelUsed"] == DEFAULT_AGY_ORCHESTRATOR_MODEL
            assert captured[-1] == {"model": DEFAULT_AGY_ORCHESTRATOR_MODEL, "effort": "high"}
    finally:
        reset_shared_circuit_breaker()


def test_tiered_router_omits_duplicate_agy_alias():
    tiered = FixedTaskRouter(
        {
            "agy_orchestrator": lambda *_: {},
            "agy_fast": lambda *_: {},
            "agy": lambda *_: {},
            "deepseek_chat": lambda *_: {},
            "deepseek_reasoner": lambda *_: {},
            "gemini_flash": lambda *_: {},
            "ollama": lambda *_: {},
        }
    )
    tasks = (
        M01_OCR,
        M03_EXAM_BLUEPRINT,
        M04_GEN_STANDARD,
        M05_GEN_HARD,
        M06_BLIND_SOLVE,
        M07_DISTRACTOR_CHECK,
        M08_DUPLICATE_SCOPE_CHECK,
        M09_SURGICAL_REPAIR,
        M10_SCOPED_PATCH,
    )
    for task in tasks:
        chain = tiered.candidate_chain(task, generator_family="agy_orchestrator")
        assert "agy" not in chain, f"{task} vẫn gọi trùng alias agy: {chain}"
    for preset in ("fast", "standard", "deep", "extended"):
        chain = tiered.candidate_chain(M11_FLEXIBLE_CHAT, time_preset=preset)
        assert "agy" not in chain, f"M11 {preset} vẫn gọi trùng alias agy: {chain}"

    legacy = FixedTaskRouter({"agy": lambda *_: {}, "ollama": lambda *_: {}})
    assert legacy.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="standard")[0] == "agy"


def test_structured_tool_response_tolerates_extra_keys_and_direct_questions():
    extra = structured_tool_response(
        {
            "content": json.dumps(
                {"action": "check_exam", "arguments": {"questions": []}, "note": "meta"}
            )
        }
    )
    assert extra["tool_calls"][0]["function"]["name"] == "check_exam"

    named = structured_tool_response(
        {"content": json.dumps({"name": "finish_exam", "arguments": {}})}
    )
    assert named["tool_calls"][0]["function"] == {"name": "finish_exam", "arguments": {}}

    direct = structured_tool_response(
        {
            "content": json.dumps(
                {
                    "questions": [
                        {
                            "stem": "Tính 1 + 1.",
                            "options": ["1", "2", "3", "4"],
                            "answer": 1,
                            "explanation": "1 + 1 = 2.",
                            "evidenceIds": [],
                        }
                    ]
                }
            )
        },
        allowed_tools={"check_exam", "finish_exam"},
        raise_code="invalid_response",
    )
    assert direct["tool_calls"][0]["function"]["name"] == "check_exam"
    assert len(direct["tool_calls"][0]["function"]["arguments"]["questions"]) == 1

    for bad_payload in (
        {"action": "execute_shell", "arguments": {}},
        {"action": "auto_save", "arguments": {}},
        {"questions": "not-a-list"},
        {"questions": []},
    ):
        with pytest.raises(AIError, match="không hợp lệ"):
            structured_tool_response({"content": json.dumps(bad_payload)})


def test_install_poc_connections_migrates_empty_saved_agy_models(tmp_path, monkeypatch):
    class FakeStore:
        available = True

        def __init__(self, _root):
            self.path = tmp_path / "conn.bin"

        def load(self):
            return {
                "provider": "ollama",
                "fixedRouter": {"enabled": True, "agyModel": "", "agyFastModel": "  "},
            }

        def save(self, _data):
            pass

    monkeypatch.setattr(poc_connections, "LocalConnectionStore", FakeStore)
    provider = AgentGeneration(
        store=None, model="qwen3:4b", directory=tmp_path / "ai", job_status=None
    )
    install_poc_connections(FastAPI(), provider)
    assert provider.agy_model == DEFAULT_AGY_ORCHESTRATOR_MODEL
    assert provider.agy_fast_model == DEFAULT_AGY_FAST_MODEL
