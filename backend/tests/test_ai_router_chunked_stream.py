"""Kiểm thử thống nhất giao thức công cụ, điều phối, sinh đề chia batch, SSE và hybrid retrieval."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mach_backend.agy_cli_model import AgyCliModel
from mach_backend.ai_contract import AIError, Locator, SourceFragment
from mach_backend.ai_questions import ExamSlot, GenerateJob, GenerationPlan
from mach_backend.ai_router import (
    FALLBACK_ERROR_CODES,
    M11_FLEXIBLE_CHAT,
    FixedTaskRouter,
    get_shared_circuit_breaker,
    reset_shared_circuit_breaker,
    structured_tool_request,
    structured_tool_response,
)
from mach_backend.curriculum_sources import install_curriculum_sources
from mach_backend.deepseek_model import DeepSeekModel
from mach_backend.gemini_model import (
    GEMINI_MODELS,
    GeminiKeyPool,
    GeminiModel,
    reset_vertex_disabled_cache,
)
from mach_backend.hybrid_retrieval import (
    chunk_document_pages,
    index_document_chunks,
    normalize_vi_search,
    search_hybrid_chunks,
)
from mach_backend.lesson_catalog import search_lesson_catalog
from mach_backend.local_workspace import create_app
from mach_backend.matrix_agent import partition_slots_into_batches, run_matrix_agent
from mach_backend.patch_jobs import PatchJobRunner
from mach_backend.patch_routes import build_patch_job_router
from mach_backend.poc_connections import probe_providers_health
from mach_backend.poc_connections import test_single_provider as check_single_provider
from mach_backend.poc_matrix import LocalModel, RunLog
from mach_backend.poc_policy import CallBudget
from mach_backend.poc_scoped_patch import _build_default_patch_router
from mach_backend.workspace_agent import AgentGeneration, apply_surgical_repair


def _sample_source(owner_id: str = "local") -> SourceFragment:
    return SourceFragment(
        ownerId=owner_id,
        sourceId=uuid4(),
        sourceVersion=1,
        locator=Locator(kind="page", index=1),
        text=(
            "Phương trình bậc hai ax^2 + bx + c = 0 có biệt thức Delta = b^2 - 4ac. "
            "Khi Delta > 0 phương trình có hai nghiệm phân biệt. "
            "Hệ hai phương trình bậc nhất hai ẩn giải bằng phương pháp thế hoặc cộng đại số. "
            "Tỉ số lượng giác của góc nhọn gồm sin, cos, tan, cot."
        ),
    )


def _sample_mcq_question(idx: int, *, stem: str | None = None, answer: int = 0) -> dict:
    return {
        "stem": stem or f"Trong bài học chuẩn, câu hỏi số {idx + 1} yêu cầu xác định giá trị nào?",
        "options": [
            f"Giá trị chuẩn {idx + 1}.A",
            f"Nhiễu {idx + 1}.B",
            f"Nhiễu {idx + 1}.C",
            f"Nhiễu {idx + 1}.D",
        ],
        "answer": answer,
        "explanation": f"Căn cứ trực tiếp vào đoạn nguồn cho câu {idx + 1}.",
        "evidenceIds": [0],
    }


def _make_check_response(
    arguments: dict,
    slots: list[dict],
    *,
    wrong_ordinals: set[int] | None = None,
    mixed: bool = False,
):
    bad = wrong_ordinals or set()
    reviews = []
    for idx, slot in enumerate(slots):
        qtype = slot.get("type", "mcq")
        is_wrong = idx in bad
        item: dict[str, object] = {
            "ordinal": idx,
            "answer": (
                1
                if (qtype == "mcq" and is_wrong)
                else (
                    0 if (qtype == "mcq" and not mixed) else ("0" if qtype == "mcq" else "Đáp án")
                )
            ),
            "observedLevel": slot["level"],
            "supported": True,
            "topicMatches": True,
            "uncertain": False,
            "optionVerdicts": (
                ["incorrect", "correct", "incorrect", "incorrect"]
                if (qtype == "mcq" and is_wrong)
                else (["correct", "incorrect", "incorrect", "incorrect"] if qtype == "mcq" else [])
            ),
            "duplicateWith": [],
            "duplicateUncertain": False,
            "reason": "Kiểm định khớp." if not is_wrong else "Đáp án mâu thuẫn.",
        }
        if mixed:
            item["solution"] = f"Lời giải độc lập câu {idx + 1}."
        reviews.append(item)
    return json.dumps({"reviews": reviews}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 1. Unified Tool Protocol across AGY, DeepSeek Reasoner, Vertex Gemini, Ollama
# ---------------------------------------------------------------------------


def test_structured_tool_roundtrip_and_agy_vertex_reasoner_ollama(tmp_path):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_exam",
                "parameters": {
                    "type": "object",
                    "properties": {"questions": {"type": "array"}},
                    "required": ["questions"],
                },
            },
        },
        {
            "type": "function",
            "function": {"name": "finish_exam", "parameters": {"type": "object", "properties": {}}},
        },
    ]
    req = structured_tool_request(
        {
            "messages": [
                {"role": "system", "content": "Soạn đề."},
                {"role": "user", "content": "{}"},
            ],
            "tools": tools,
        }
    )
    assert "format" in req and "oneOf" in req["format"]

    # Default structured_tool_response omits call id for existing matrix_agent tests,
    # while include_call_id=True attaches OpenAI-compatible id for cross-provider history.
    bare = structured_tool_response(
        {"content": '```json\n{"action": "check_exam", "arguments": {"questions": []}}\n```'}
    )
    assert "id" not in bare["tool_calls"][0]
    with_id = structured_tool_response(
        {"content": json.dumps({"action": "finish_exam", "arguments": {}})},
        include_call_id=True,
    )
    assert with_id["tool_calls"][0]["id"].startswith("call_")
    assert with_id["tool_calls"][0]["function"]["name"] == "finish_exam"

    job = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        sources=(_sample_source(),),
        requireEvidence=True,
        subject="Toán",
        grade="9",
        slots=(ExamSlot(type="mcq", topic="Phương trình", level=2, points=10.0),),
    )

    async def _run_provider_matrix_loop(call_fn):
        events: list[tuple[str, dict]] = []
        return await run_matrix_agent(
            job,
            call_fn,
            lambda ev, **kw: events.append((ev, kw)),
            max_attempts=2,
        )

    # (a) AGY CLI adapter
    agy_cmds: list[list[str]] = []

    def fake_agy_runner(cmd, **kwargs):
        agy_cmds.append(list(cmd))
        raw_input = kwargs.get("input", b"")
        stdin_text = (
            raw_input.decode("utf-8", errors="replace")
            if isinstance(raw_input, bytes)
            else str(raw_input or "")
        )
        full_prompt = cmd[cmd.index("-p") + 1] + "\n" + stdin_text
        if '"toolResult"' in full_prompt or '"ok": true' in full_prompt:
            payload = {"response": json.dumps({"action": "finish_exam", "arguments": {}})}
        else:
            payload = {
                "response": json.dumps(
                    {"action": "check_exam", "arguments": {"questions": [_sample_mcq_question(0)]}},
                    ensure_ascii=False,
                )
            }
        return SimpleNamespace(stdout=json.dumps(payload).encode("utf-8"), returncode=0)

    async def call_via_agy(purpose, body):
        if purpose == "agent":
            agy = AgyCliModel(
                RunLog(tmp_path / f"agy-{uuid4().hex[:6]}"),
                custom_path=r"C:\fake\agy.exe",
                runner=fake_agy_runner,
                model="gemini-3.6-pro",
            )
            return await agy(purpose, {**body, "model": "claude-sonnet-4"})
        if purpose == "blind_content_check":
            data = json.loads(body["messages"][1]["content"])
            return {"content": _make_check_response({}, [{"level": 2} for _ in data["questions"]])}
        data = json.loads(body["messages"][1]["content"])
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {"ordinal": i, "consistent": True, "reason": "Khớp."}
                        for i in range(len(data["questions"]))
                    ]
                }
            )
        }

    # Bypass path.is_file() in detect_agy_cli via monkeypatch below.
    mp = pytest.MonkeyPatch()
    mp.setattr("mach_backend.agy_cli_model.detect_agy_cli", lambda _p="": r"C:\fake\agy.exe")
    try:
        agy_res = asyncio.run(_run_provider_matrix_loop(call_via_agy))
        assert agy_res["status"] == "ready_for_teacher_review"
        assert "--sandbox" in agy_cmds[0] and "--mode" in agy_cmds[0] and "--model" in agy_cmds[0]
        assert agy_cmds[0][agy_cmds[0].index("--model") + 1] == "claude-sonnet-4"
    finally:
        mp.undo()

    # (b) Vertex Express Gemini (AQ.* key)
    vertex_payloads: list[dict] = []

    def vertex_transport(request: httpx.Request):
        req_json = json.loads(request.content)
        vertex_payloads.append(req_json)
        sys_txt = " ".join(
            p.get("text", "") for p in req_json.get("systemInstruction", {}).get("parts", [])
        )
        user_txt = " ".join(
            str(part.get("text", ""))
            for item in req_json.get("contents", [])
            for part in item.get("parts", [])
        )
        if '"check_exam"' in sys_txt:
            txt = (
                json.dumps({"action": "finish_exam", "arguments": {}})
                if '"toolResult"' in user_txt
                else json.dumps(
                    {
                        "action": "check_exam",
                        "arguments": {"questions": [_sample_mcq_question(0)]},
                    },
                    ensure_ascii=False,
                )
            )
        elif "Giải từng câu chỉ từ nguồn" in sys_txt:
            txt = _make_check_response({}, [{"level": 2}])
        else:
            txt = json.dumps({"reviews": [{"ordinal": 0, "consistent": True, "reason": "Khớp."}]})
        return httpx.Response(
            200,
            json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": txt}]}}]},
        )

    async def run_vertex():
        async with httpx.AsyncClient(transport=httpx.MockTransport(vertex_transport)) as client:
            gm = GeminiModel(
                client,
                "AQ.vertex-fake-token-12345",
                RunLog(tmp_path / "vertex-log"),
                model="gemini-2.5-pro",
                auto_fallback=False,
            )

            async def wrapped(purpose, body):
                if purpose == "agent":
                    return await gm(purpose, body)
                if purpose == "blind_content_check":
                    return {"content": _make_check_response({}, [{"level": 2}])}
                return {
                    "content": json.dumps(
                        {"reviews": [{"ordinal": 0, "consistent": True, "reason": "OK."}]}
                    )
                }

            return await _run_provider_matrix_loop(wrapped)

    reset_vertex_disabled_cache()
    vertex_res = asyncio.run(run_vertex())
    assert vertex_res["status"] == "ready_for_teacher_review"
    assert "tools" not in vertex_payloads[0]
    assert vertex_payloads[0]["generationConfig"]["responseMimeType"] == "application/json"

    # (c) DeepSeek Reasoner + DeepSeek Chat 8192 token check
    ds_payloads: list[dict] = []

    def ds_transport(request: httpx.Request):
        req_json = json.loads(request.content)
        ds_payloads.append(req_json)
        if req_json["model"] == "deepseek-reasoner":
            user_dump = " ".join(str(m.get("content", "")) for m in req_json["messages"])
            content = (
                json.dumps({"action": "finish_exam", "arguments": {}})
                if '"toolResult"' in user_dump
                else json.dumps(
                    {"action": "check_exam", "arguments": {"questions": [_sample_mcq_question(0)]}},
                    ensure_ascii=False,
                )
            )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "reasoning_content": "Suy luận toán học ngắn.",
                                "content": content,
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 30},
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    async def run_ds():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ds_transport)) as client:
            ds_reasoner = DeepSeekModel(
                client,
                "sk-deepseek-fake-123",
                RunLog(tmp_path / "ds-r"),
                model="deepseek-reasoner",
                auto_fallback=False,
            )
            ds_chat = DeepSeekModel(
                client,
                "sk-deepseek-fake-123",
                RunLog(tmp_path / "ds-c"),
                model="deepseek-chat",
                auto_fallback=False,
            )
            # Plain chat -> 4096; chat with tools -> 8192
            await ds_chat("chat", {"messages": [{"role": "user", "content": "Chào"}]})
            await ds_chat(
                "agent", {"messages": [{"role": "user", "content": "Soạn"}], "tools": tools}
            )

            async def wrapped(purpose, body):
                if purpose == "agent":
                    return await ds_reasoner(purpose, body)
                if purpose == "blind_content_check":
                    return {"content": _make_check_response({}, [{"level": 2}])}
                return {
                    "content": json.dumps(
                        {"reviews": [{"ordinal": 0, "consistent": True, "reason": "OK."}]}
                    )
                }

            return await _run_provider_matrix_loop(wrapped)

    ds_res = asyncio.run(run_ds())
    assert ds_res["status"] == "ready_for_teacher_review"
    assert ds_payloads[0]["max_tokens"] == 4096
    assert ds_payloads[1]["max_tokens"] == 8192
    assert "tools" not in ds_payloads[2] and ds_payloads[2]["response_format"] == {
        "type": "json_object"
    }

    # (d) Ollama LocalModel num_predict=4096 for agent/batch
    ollama_payloads: list[dict] = []

    def ollama_transport(request: httpx.Request):
        req_json = json.loads(request.content)
        ollama_payloads.append(req_json)
        msg_dump = " ".join(str(m.get("content", "")) for m in req_json["messages"])
        content = (
            json.dumps({"action": "finish_exam", "arguments": {}})
            if '"toolResult"' in msg_dump
            else json.dumps(
                {"action": "check_exam", "arguments": {"questions": [_sample_mcq_question(0)]}},
                ensure_ascii=False,
            )
        )
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": content}}
        )

    async def run_ollama():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ollama_transport)) as client:
            local = LocalModel(
                client, "qwen2.5:7b", RunLog(tmp_path / "ollama-log"), protocol="structured"
            )

            async def wrapped(purpose, body):
                if purpose == "agent":
                    return await local(purpose, body)
                if purpose == "blind_content_check":
                    return {"content": _make_check_response({}, [{"level": 2}])}
                return {
                    "content": json.dumps(
                        {"reviews": [{"ordinal": 0, "consistent": True, "reason": "OK."}]}
                    )
                }

            return await _run_provider_matrix_loop(wrapped)

    ollama_res = asyncio.run(run_ollama())
    assert ollama_res["status"] == "ready_for_teacher_review"
    assert ollama_payloads[0]["options"]["num_predict"] == 4096


# ---------------------------------------------------------------------------
# 2. Shared CircuitBreaker, FALLBACK_ERROR_CODES, M11 routing, Scoped Patch & Check
# ---------------------------------------------------------------------------


def test_shared_circuit_breaker_error_codes_and_m11_presets():
    assert {
        "invalid_response",
        "invalid_result",
        "result_limit",
        "rate_limited",
        "unsupported_model",
    }.issubset(FALLBACK_ERROR_CODES)
    assert "gemini-2.5-flash" in GEMINI_MODELS and "gemini-2.5-pro" in GEMINI_MODELS

    providers = {
        "agy": lambda _p, _b: {"content": "agy"},
        "deepseek_chat": lambda _p, _b: {"content": "ds-chat"},
        "deepseek_reasoner": lambda _p, _b: {"content": "ds-reasoner"},
        "gemini_flash": lambda _p, _b: {"content": "g-flash"},
        "gemini_pro": lambda _p, _b: {"content": "g-pro"},
        "ollama": lambda _p, _b: {"content": "ollama"},
    }
    router_std = FixedTaskRouter(providers, time_preset="standard")
    chain_fast = router_std.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="fast")
    chain_std = router_std.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="standard")
    assert "deepseek_fast" not in chain_fast
    assert chain_fast[:4] == ["deepseek_chat", "gemini_flash", "ollama", "agy"]
    assert chain_std[:4] == ["deepseek_chat", "gemini_flash", "ollama", "agy"]

    chain_deep = router_std.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="deep")
    chain_ext = router_std.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="extended")
    deep_subset = {"agy", "deepseek_reasoner", "gemini_pro", "deepseek_chat", "ollama"}
    assert [p for p in chain_deep if p in deep_subset] == [
        "agy",
        "deepseek_reasoner",
        "gemini_pro",
        "deepseek_chat",
        "ollama",
    ]
    assert [p for p in chain_ext if p in deep_subset] == [
        "agy",
        "deepseek_reasoner",
        "gemini_pro",
        "deepseek_chat",
        "ollama",
    ]
    assert (
        chain_deep.index("gemini_pro")
        < chain_deep.index("gemini_hydrogen")
        < chain_deep.index("deepseek_chat")
    )

    # Shared breaker persists open state across separate router instances & requests
    reset_shared_circuit_breaker()
    breaker = get_shared_circuit_breaker()
    breaker.failure_threshold = 2
    calls_1: list[str] = []
    calls_2: list[str] = []

    async def fail_invalid(_p, _b):
        calls_1.append("deepseek_chat")
        raise AIError("invalid_response", "JSON hỏng")

    async def fail_if_called(_p, _b):
        calls_2.append("deepseek_chat")
        raise AIError("rate_limited", "429")

    r1 = FixedTaskRouter(
        {
            "deepseek_chat": fail_invalid,
            "gemini_flash": lambda _p, _b: {"content": '{"message":"ok"}'},
        },
        circuit_breaker=get_shared_circuit_breaker(),
        time_preset="fast",
    )
    r2 = FixedTaskRouter(
        {
            "deepseek_chat": fail_if_called,
            "gemini_flash": lambda _p, _b: {"content": '{"message":"ok2"}'},
        },
        circuit_breaker=get_shared_circuit_breaker(),
        time_preset="fast",
    )
    asyncio.run(r1("assistant_chat", {"messages": []}))
    asyncio.run(r1("assistant_chat", {"messages": []}))
    assert breaker.is_open("deepseek_chat")
    res2 = asyncio.run(r2("assistant_chat", {"messages": []}))
    assert res2["providerFamily"] == "gemini_flash" and calls_2 == []


def test_scoped_patch_budget_and_workspace_check_router(tmp_path):
    # Verify _build_default_patch_router passes budget to DeepSeekModel
    provider = SimpleNamespace(
        all_gemini_keys=("AIzaFakeKey12345678", "AIzaFakeKey22345678", "AIzaExtraKey32345678"),
        provider_name="gemini",
        active_model="gemini-3.6-flash",
        gemini_key="AIzaFakeKey12345678",
        gemini_backup_key="AIzaFakeKey22345678",
        gemini_extra_keys=("AIzaExtraKey32345678",),
        gemini_free_tier=False,
        gemini_auto_fallback=True,
        agy_available=False,
        agy_custom_path="",
        agy_model="",
        deepseek_key="sk-fake-deepseek-999",
        deepseek_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        deepseek_reasoner_model="deepseek-reasoner",
        deepseek_cross_model="",
        deepseek_backup_models=(),
        model="qwen2.5:7b",
        extended_policy=SimpleNamespace(timePreset="standard"),
    )
    budget = CallBudget(2, 60)
    captured_ds_budgets: list[object] = []

    def ds_transport(_request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"edits": []}'},
                    }
                ]
            },
        )

    async def _run_patch_router():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ds_transport)) as client:
            mp = pytest.MonkeyPatch()
            orig_ds = DeepSeekModel

            def _spy_ds(*args, **kwargs):
                captured_ds_budgets.append(kwargs.get("budget"))
                return orig_ds(*args, **kwargs)

            mp.setattr("mach_backend.poc_scoped_patch.DeepSeekModel", _spy_ds)
            try:
                router = _build_default_patch_router(
                    client, RunLog(tmp_path / "sp"), provider, budget=budget
                )
                await router(
                    "scoped_patch_edit", {"messages": [{"role": "user", "content": "Sửa"}]}
                )
            finally:
                mp.undo()

    asyncio.run(_run_patch_router())
    assert captured_ds_budgets == [budget] and budget.calls == 1

    # Verify workspace_check routes through FixedTaskRouter and honors strictTeacherOnly
    app = create_app(tmp_path / "wc")
    exam_id, q_id, cat_id, t_id = str(uuid4()), str(uuid4()), str(uuid4()), str(uuid4())
    exam = {
        "id": exam_id,
        "revision": 2,
        "strictTeacherOnly": True,
        "questions": [
            {
                "id": q_id,
                "v": 1,
                "type": "mcq",
                "stem": "Ai mở cửa?",
                "options": ["Mai", "Nam", "Hà", "Lan"],
                "answer": 0,
            }
        ],
        "docs": [
            {
                "id": cat_id,
                "version": 1,
                "catalog": True,
                "sourceOrigin": "lesson_catalog",
                "text": "Nguồn hệ thống.",
                "pages": [{"number": 1, "text": "Nguồn hệ thống."}],
            },
            {
                "id": t_id,
                "version": 1,
                "text": "Mai mở cửa lớp.",
                "pages": [{"number": 1, "text": "Mai mở cửa lớp."}],
            },
        ],
    }
    app.state.store.put("state", {"exams": [exam], "current": exam_id})
    app.state.provider.deepseek_key = "sk-deepseek-check-123"

    seen_sources_counts: list[int] = []

    async def fake_ds_check(self, purpose, body):
        data = json.loads(body["messages"][1]["content"])
        seen_sources_counts.append(len(data["sources"]))
        return {
            "content": json.dumps(
                {
                    "jobId": data["jobId"],
                    "examId": data["examId"],
                    "baseRevision": data["baseRevision"],
                    "questionId": data["question"]["questionId"],
                    "questionVersion": data["question"]["questionVersion"],
                    "optionVerdicts": ["correct", "incorrect", "incorrect", "incorrect"],
                    "answer": 0,
                    "explanation": "Mai mở cửa lớp.",
                    "uncertain": False,
                    "evidence": [
                        {
                            "sourceId": s["sourceId"],
                            "sourceVersion": s["sourceVersion"],
                            "locator": s["locator"],
                            "quote": s["text"],
                        }
                        for s in data["sources"]
                    ],
                },
                ensure_ascii=False,
            )
        }

    mp = pytest.MonkeyPatch()
    mp.setattr("mach_backend.workspace_check.DeepSeekModel.__call__", fake_ds_check)
    try:
        with TestClient(app, headers={"Origin": "http://testserver"}) as client:
            cfg = client.get("/api/config").json()
            blocked = client.post(
                f"/api/exams/{exam_id}/questions/{q_id}/check",
                headers={"X-PoC-Config": cfg["fingerprint"]},
                json={
                    "baseRevision": 2,
                    "questionVersion": 1,
                    "consent": True,
                    "sources": [
                        {
                            "sourceId": cat_id,
                            "sourceVersion": 1,
                            "locator": {"kind": "page", "index": 1},
                        },
                        {
                            "sourceId": t_id,
                            "sourceVersion": 1,
                            "locator": {"kind": "page", "index": 1},
                        },
                    ],
                },
            )
            assert blocked.status_code == 404
            r = client.post(
                f"/api/exams/{exam_id}/questions/{q_id}/check",
                headers={"X-PoC-Config": cfg["fingerprint"]},
                json={
                    "baseRevision": 2,
                    "questionVersion": 1,
                    "consent": True,
                    "sources": [
                        {
                            "sourceId": t_id,
                            "sourceVersion": 1,
                            "locator": {"kind": "page", "index": 1},
                        },
                    ],
                },
            )
            assert r.status_code == 200, r.text
            assert seen_sources_counts == [1]
    finally:
        mp.undo()


# ---------------------------------------------------------------------------
# 3. Chunked Generation (28-Q & 40-Q), Surgical Repair, Checkpointing, Early Stop, SSE
# ---------------------------------------------------------------------------


def test_chunked_28q_and_40q_checkpoint_surgical_repair_and_early_stop(tmp_path):
    # (a) Partition limits check on 40 mixed slots
    mixed_40 = [
        *[ExamSlot(type="mcq", topic="Đọc hiểu", level=0, points=0.25) for _ in range(18)],
        *[ExamSlot(type="truefalse", topic="Hình học", level=1, points=0.5) for _ in range(4)],
        *[ExamSlot(type="short", topic="Đại số", level=2, points=0.25) for _ in range(10)],
        *[ExamSlot(type="essay", topic="Tổng hợp", level=3, points=0.25) for _ in range(8)],
    ]
    batches_40 = partition_slots_into_batches(mixed_40)
    assert [len(b) for b in batches_40] == [6, 6, 6, 3, 1, 6, 4, 3, 3, 2]
    assert sum(len(b) for b in batches_40) == 40

    # (b) Full 40-Q GenerateJob (20 common + Track A 10 + Track B 10 = 40 slots; 10.00pt per track)
    slots_40_tracks = (
        *[ExamSlot(type="mcq", topic="Chung", level=0, points=0.25) for _ in range(14)],
        *[ExamSlot(type="truefalse", topic="Chung DS", level=1, points=1.25) for _ in range(2)],
        *[ExamSlot(type="short", topic="Chung TLN", level=2, points=0.25) for _ in range(4)],
        *[
            ExamSlot(type="mcq", topic="Nhánh A", level=1, choiceGroup="A", points=0.30)
            for _ in range(6)
        ],
        *[
            ExamSlot(type="short", topic="Nhánh A", level=2, choiceGroup="A", points=0.30)
            for _ in range(4)
        ],
        *[
            ExamSlot(type="mcq", topic="Nhánh B", level=1, choiceGroup="B", points=0.30)
            for _ in range(6)
        ],
        *[
            ExamSlot(type="short", topic="Nhánh B", level=2, choiceGroup="B", points=0.30)
            for _ in range(4)
        ],
    )
    assert len(slots_40_tracks) == 40
    job_40 = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        sources=(_sample_source(),),
        requireEvidence=True,
        subject="Toán",
        grade="9",
        slots=slots_40_tracks,
    )

    seen_prior_stems: list[int] = []
    last_batch_levels: list[int] = []
    q_counter = 0

    async def batch_model(purpose, body):
        nonlocal q_counter, last_batch_levels
        if purpose == "agent":
            last_msg = body["messages"][-1]
            if last_msg.get("role") == "tool" and json.loads(last_msg["content"]).get("ok"):
                return {"tool_calls": [{"function": {"name": "finish_exam", "arguments": {}}}]}
            assign = json.loads(body["messages"][1]["content"])
            seen_prior_stems.append(len(assign.get("priorStems", [])))
            last_batch_levels = [s["level"] for s in assign["matrix"]["slots"]]
            questions = []
            for s in assign["matrix"]["slots"]:
                idx = q_counter
                q_counter += 1
                pts = s["points"]
                if s["type"] == "mcq":
                    questions.append(_sample_mcq_question(idx))
                elif s["type"] == "truefalse":
                    questions.append(
                        {
                            "stem": f"Xác định tính đúng sai của phát biểu tổng hợp #{idx + 1}:",
                            "options": [f"Mệnh đề {idx}.{k}" for k in range(4)],
                            "answer": "1010",
                            "explanation": "Giải thích từng mệnh đề.",
                            "rubric": [{"text": "Chấm 4 ý.", "points": pts}],
                            "evidenceIds": [0],
                        }
                    )
                else:
                    questions.append(
                        {
                            "stem": f"Điền kết quả tính toán cho bài ngắn #{idx + 1}.",
                            "options": [],
                            "answer": str(idx + 1),
                            "explanation": "Tính từ dữ kiện.",
                            "rubric": [{"text": "Đúng đáp số.", "points": pts}],
                            "evidenceIds": [0],
                        }
                    )
            return {
                "tool_calls": [
                    {"function": {"name": "check_exam", "arguments": {"questions": questions}}}
                ]
            }

        data = json.loads(body["messages"][1]["content"])
        if purpose == "blind_content_check":
            is_mixed = any(q.get("type", "mcq") != "mcq" for q in data["questions"])
            reviews = []
            for i, q in enumerate(data["questions"]):
                q_type = q.get("type", "mcq")
                if q_type == "mcq":
                    ans: object = "0" if is_mixed else 0
                elif q_type == "truefalse":
                    ans = "1010"
                else:
                    ans = q["stem"].split("#")[1].rstrip(".")
                row: dict[str, object] = {
                    "ordinal": i,
                    "answer": ans,
                    "observedLevel": last_batch_levels[i] if i < len(last_batch_levels) else 0,
                    "supported": True,
                    "topicMatches": True,
                    "uncertain": False,
                    "optionVerdicts": (
                        ["correct", "incorrect", "incorrect", "incorrect"]
                        if q_type == "mcq"
                        else (
                            ["correct", "incorrect", "correct", "incorrect"]
                            if q_type == "truefalse"
                            else []
                        )
                    ),
                    "duplicateWith": [],
                    "duplicateUncertain": False,
                    "reason": "Khớp.",
                }
                if is_mixed:
                    row["solution"] = "Giải độc lập."
                reviews.append(row)
            return {"content": json.dumps({"reviews": reviews}, ensure_ascii=False)}

        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {"ordinal": i, "consistent": True, "reason": "Khớp."}
                        for i in range(len(data["questions"]))
                    ]
                }
            )
        }

    checkpoints: list[int] = []
    ev_log: list[str] = []
    res_40 = asyncio.run(
        run_matrix_agent(
            job_40,
            batch_model,
            lambda name, **_kw: ev_log.append(name),
            chunked=True,
            on_batch_verified=lambda passed, **_kw: checkpoints.append(len(passed)),
        )
    )
    assert res_40["status"] == "ready_for_teacher_review"
    assert len(res_40["proposal"]["questions"]) == 40
    assert checkpoints == [6, 12, 14, 16, 20, 26, 30, 36, 40]
    assert seen_prior_stems[-1] == 36

    # (c) Surgical repair via apply_surgical_repair for non-Ollama provider (e.g. DeepSeek/AGY)
    scoped_requests: list[dict] = []

    async def fake_cloud_call(_purpose, body):
        assign = json.loads(body["messages"][1]["content"])
        scoped_requests.append(assign)
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "check_exam",
                        "arguments": {
                            "questions": [_sample_mcq_question(1, stem="Câu 2 đã sửa phẫu thuật?")]
                        },
                    }
                }
            ]
        }

    prior_4 = [_sample_mcq_question(i) for i in range(4)]
    repair_body = {
        "messages": [
            {"role": "system", "content": "Soạn đề."},
            {
                "role": "user",
                "content": json.dumps({"matrix": {"slots": [{"type": "mcq", "level": 0}] * 4}}),
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "check_exam", "arguments": {"questions": prior_4}}}
                ],
            },
            {
                "role": "tool",
                "tool_name": "check_exam",
                "content": json.dumps(
                    {"ok": False, "errors": [{"ordinal": 1, "code": "answer_disagreement"}]}
                ),
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "check_exam",
                    "parameters": {"properties": {"questions": {"minItems": 4, "maxItems": 4}}},
                },
            }
        ],
    }
    repaired = asyncio.run(
        apply_surgical_repair(fake_cloud_call, "agent", repair_body, enable_stem_proposal=False)
    )
    assert scoped_requests[0]["repairOrdinals"] == [1]
    assert len(scoped_requests[0]["matrix"]["slots"]) == 1
    assert len(repaired["tool_calls"][0]["function"]["arguments"]["questions"]) == 4
    assert (
        repaired["tool_calls"][0]["function"]["arguments"]["questions"][1]["stem"]
        == "Câu 2 đã sửa phẫu thuật?"
    )
    assert (
        repaired["tool_calls"][0]["function"]["arguments"]["questions"][0]["stem"]
        == prior_4[0]["stem"]
    )

    # (d) Early stop + Checkpoint + PatchJobRunner > 900s (3600s) + Live SSE
    # 28 slots (20 MCQ + 4 TF + 4 Short) tổng đúng 10.00 điểm.
    slots_28 = (
        *[ExamSlot(type="mcq", topic="Đại số", level=0, points=0.25) for _ in range(20)],
        *[ExamSlot(type="truefalse", topic="Hình học", level=1, points=0.75) for _ in range(4)],
        *[ExamSlot(type="short", topic="Thực tế", level=2, points=0.5) for _ in range(4)],
    )
    job_28 = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        sources=(_sample_source(),),
        requireEvidence=True,
        subject="Toán",
        grade="9",
        slots=slots_28,
    )
    src_28 = job_28.sources[0]
    store = create_app(tmp_path / "es-store").state.store
    store.put(
        "state",
        {
            "exams": [
                {
                    "id": str(job_28.examId),
                    "revision": 1,
                    "docs": [
                        {
                            "id": str(src_28.sourceId),
                            "version": 1,
                            "pages": [{"number": 1, "text": src_28.text}],
                        }
                    ],
                }
            ],
            "current": str(job_28.examId),
        },
    )
    store.put("matrix-source-name:" + str(job_28.examId), "nguon.pdf")
    store.put(
        "matrix:" + str(job_28.examId),
        json.loads(
            GenerationPlan.model_validate(
                job_28.model_dump(include=set(GenerationPlan.model_fields))
            ).model_dump_json()
        ),
    )
    store.put("matrix-source:" + str(job_28.examId), [src_28.model_dump(mode="json")])

    async def _run_early_stop_with_runner():
        agent = AgentGeneration(
            store,
            "qwen2.5:7b",
            tmp_path / "agent-es",
            job_status=lambda _j: SimpleNamespace(status="running", errorCode=None),
            call=batch_model,
            chunked=True,
        )
        # Intercept after batch 1 (6 questions) via wrap or checkpoint check
        orig_save = agent.save_job_checkpoint

        def save_and_stop(job_id, **kwargs):
            out = orig_save(job_id, **kwargs)
            if (
                str(job_id) not in agent.early_stop_jobs
                and kwargs["passed_questions"]
                and len(kwargs["passed_questions"]) >= 6
            ):
                agent.request_early_stop(job_id)
            return out

        agent.save_job_checkpoint = save_and_stop  # type: ignore[method-assign]

        async def snap_ok(_j):
            return True

        async def store_pending(_p):
            return True

        runner = PatchJobRunner(
            agent,
            snap_ok,
            store_pending,
            timeout_seconds=3600,
            max_active=2,
            max_retained=4,
        )
        app = FastAPI()
        app.include_router(build_patch_job_router(runner, lambda: "local", lambda *_a: None))
        status = runner.submit(job_28)
        assert status.status == "running"

        frames: list[str] = []
        async for frame in runner.stream_events("local", job_28.examId, job_28.jobId, after=0):
            frames.append(f"{frame.event}:{frame.event_id}:{frame.data_json}")

        # Verify Last-Event-ID replay contracts over HTTP SSE endpoint as well
        with TestClient(app) as http_client:
            ev_1 = http_client.get(
                f"/api/exams/{job_28.examId}/proposals/{job_28.jobId}/events",
                headers={"Last-Event-ID": "1"},
            )
            assert ev_1.status_code == 200 and ev_1.text.startswith("id: 2\nevent: patch\n")
            ev_2 = http_client.get(
                f"/api/exams/{job_28.examId}/proposals/{job_28.jobId}/events",
                headers={"Last-Event-ID": "2"},
            )
            assert ev_2.status_code == 200 and ev_2.text == ""

        final_state = runner.status("local", job_28.examId, job_28.jobId)
        cp = agent.get_job_checkpoint(str(job_28.jobId))
        return final_state, cp, frames

    final_state, cp, frames = asyncio.run(_run_early_stop_with_runner())
    assert final_state.status == "early_stopped"
    assert final_state.passedCount == 6 and final_state.totalSlots == 28
    assert final_state.partialQuestions is not None and len(final_state.partialQuestions) == 6
    assert cp is not None and cp["status"] == "early_stopped" and cp["passedCount"] == 6
    progress_types = [
        json.loads(f.split(":", 2)[2])["type"] for f in frames if f.startswith("progress:")
    ]
    assert "batch_started" in progress_types
    assert "blind_check" in progress_types
    assert "batch_done" in progress_types
    assert "early_stopped" in progress_types
    assert frames[-1].startswith("patch:2:")


# ---------------------------------------------------------------------------
# 4. Real Token Streaming SSE / NDJSON (DeepSeek, Gemini, Ollama)
# ---------------------------------------------------------------------------


def test_real_sse_and_ndjson_token_streaming(tmp_path):
    async def _run():
        # DeepSeek OpenAI SSE
        def ds_sse(_req: httpx.Request):
            body = (
                'data: {"choices":[{"delta":{"content":"Xin "}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"chào sk-secret-key-999"}}]}\n\n'
                'data: {"usage":{"prompt_tokens":12,"completion_tokens":4}}\n\n'
                "data: [DONE]\n\n"
            ).encode()
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(ds_sse)) as c1:
            ds = DeepSeekModel(c1, "sk-secret-key-999", RunLog(tmp_path / "ds-stream"))
            ds_events = [ev async for ev in ds.stream_chat([{"role": "user", "content": "Hi"}])]
        assert [e["text"] for e in ds_events[:-1]] == ["Xin ", "chào [REDACTED]"]
        assert "sk-secret-key-999" not in ds_events[-1]["text"]
        assert ds_events[-1]["type"] == "done" and ds_events[-1]["usage"]["completion_tokens"] == 4

        # Gemini SSE (:streamGenerateContent?alt=sse) skipping thought=True parts
        def gm_sse(_req: httpx.Request):
            chunk1 = (
                'data: {"candidates":[{"content":{"parts":[{"text":"nháp","thought":true}]}}]}\n\n'
            )
            chunk2 = 'data: {"candidates":[{"content":{"parts":[{"text":"Toán "}]}}]}\n\n'
            chunk3 = (
                'data: {"candidates":[{"content":{"parts":[{"text":"học 9"}]}}],'
                '"usageMetadata":{"totalTokenCount":20}}\n\n'
            )
            body = (chunk1 + chunk2 + chunk3).encode()
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(gm_sse)) as c2:
            gm = GeminiModel(
                c2,
                "AQ.vertex-stream-secret",
                RunLog(tmp_path / "gm-stream"),
                model="gemini-2.5-flash",
            )
            gm_events = [ev async for ev in gm.stream_chat([{"role": "user", "content": "Hi"}])]
        assert [e["text"] for e in gm_events[:-1]] == ["Toán ", "học 9"]
        assert gm_events[-1]["type"] == "done" and gm_events[-1]["provider"] == "vertex-express"

        # Ollama /api/chat NDJSON stream
        def ol_ndjson(_req: httpx.Request):
            lines = (
                json.dumps({"message": {"role": "assistant", "content": "Lời "}, "done": False})
                + "\n"
                + json.dumps({"message": {"role": "assistant", "content": "giải"}, "done": False})
                + "\n"
                + json.dumps({"done": True, "eval_count": 7, "prompt_eval_count": 9})
                + "\n"
            ).encode()
            return httpx.Response(
                200, content=lines, headers={"content-type": "application/x-ndjson"}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(ol_ndjson)) as c3:
            ol = LocalModel(c3, "qwen2.5:7b", RunLog(tmp_path / "ol-stream"))
            ol_events = [ev async for ev in ol.stream_chat([{"role": "user", "content": "Hi"}])]
        assert [e["text"] for e in ol_events[:-1]] == ["Lời ", "giải"]
        assert ol_events[-1] == {
            "type": "done",
            "text": "Lời giải",
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "usage": {"prompt_eval_count": 9, "eval_count": 7},
        }

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Hybrid Retrieval, Vietnamese i/y, Synonyms, Zero-hit Gate & Catalog/Sources
# ---------------------------------------------------------------------------


def test_hybrid_retrieval_fts5_bm25_ollama_embed_and_vi_normalization(tmp_path):
    assert normalize_vi_search("Tỉ số lượng giác & Vật lý") == normalize_vi_search(
        "Tỷ số lượng giác & Vật lí"
    )
    assert normalize_vi_search("Kỹ năng Mĩ thuật Bác sỹ") == normalize_vi_search(
        "Kĩ năng Mỹ thuật Bác sĩ"
    )
    assert "python" in normalize_vi_search("Python và System")

    pages = [
        {
            "page": 1,
            "text": (
                "Chương 4: Tỉ số lượng giác của góc nhọn trong tam giác vuông "
                "gồm sin, cos, tan, cot. " * 8
            ),
        },
        {
            "page": 2,
            "text": (
                "Hệ hai phương trình bậc nhất hai ẩn ax + by = c có thể giải bằng phương pháp thế. "
                "Đạo hàm biểu thị tốc độ biến thiên tức thời; nguyên hàm ngược với vi phân."
            ),
        },
    ]
    chunks = chunk_document_pages(pages, chunk_size=140, overlap=30, doc_id="doc-math", version=2)
    assert len(chunks) >= 3
    assert all(c["doc_id"] == "doc-math" and c["version"] == 2 for c in chunks)
    assert chunks[0]["page_number"] == 1 and chunks[0]["chunk_index"] == 0

    conn = sqlite3.connect(":memory:")
    indexed = index_document_chunks(
        conn,
        "teacher-1",
        "doc-math",
        pages,
        version=2,
        title="Toán 9 Chương 4",
        chunk_size=180,
        overlap=30,
    )
    assert len(indexed) >= 2

    # (a) i/y equivalence via FTS5
    res_iy = search_hybrid_chunks(conn, "teacher-1", "ty so luong giac", ["doc-math"])
    assert res_iy and "Tỉ số lượng giác" in res_iy[0]["text"]

    # (b) Synonym expansion + pure Python BM25 fallback (use_fts5=False)
    res_syn = search_hybrid_chunks(
        conn, "teacher-1", "giải hệ phương trình", ["doc-math"], use_fts5=False
    )
    assert res_syn and "Hệ hai phương trình bậc nhất hai ẩn" in res_syn[0]["text"]

    # (c) Ollama /api/embed cosine reranking
    def fake_embed(texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            lower = normalize_vi_search(t)
            if "dao ham" in lower or "vi phan" in lower:
                out.append([1.0, 0.0, 0.0])
            elif "tich phan" in lower or "nguyen ham" in lower:
                out.append([0.8, 0.2, 0.0])
            elif "ti so" in lower or "he hai" in lower:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out

    res_emb = search_hybrid_chunks(
        conn,
        "teacher-1",
        "đạo hàm",
        [{"id": "doc-math", "version": 2}],
        ollama_embed_fn=fake_embed,
    )
    assert res_emb and "Đạo hàm" in res_emb[0]["text"]

    # (d) Strict zero-hit gate + allowlist enforcement
    assert search_hybrid_chunks(conn, "teacher-1", "zzq999", ["doc-math"]) == []
    assert (
        search_hybrid_chunks(conn, "teacher-1", "zzq999", ["doc-math"], ollama_embed_fn=fake_embed)
        == []
    )
    assert search_hybrid_chunks(conn, "teacher-1", "Tỉ số", []) == []

    # (e) Lesson catalog + curriculum_sources wiring
    cat_hits = search_lesson_catalog("tỷ số", grade="9")
    assert isinstance(cat_hits, list)

    app = FastAPI()
    install_curriculum_sources(app, tmp_path / "cs.sqlite", owner_resolver=lambda _r: "teacher-1")
    with TestClient(app) as client:
        created = client.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 9,
                "subject": "Toán",
                "series": "KNTT",
                "volume": "Tập 1",
                "chapter": "Chương 4",
                "lesson": "Bài 11",
                "title": "Tỉ số lượng giác của góc nhọn",
                "content_excerpt": "Hệ hai phương trình bậc nhất hai ẩn và tỉ số lượng giác.",
                "license_status": "teacher_owned",
            },
        )
        assert created.status_code == 201, created.text
        listed_iy = client.get("/api/lesson-catalog/sources", params={"q": "tỷ số lượng giác"})
        assert listed_iy.json()["total"] == 1
        listed_syn = client.get("/api/lesson-catalog/sources", params={"q": "giải hệ phương trình"})
        assert listed_syn.json()["total"] == 1


# ---------------------------------------------------------------------------
# 6. Ollama Vision OCR, agyModel Config, probe_providers_health & test_single_provider
# ---------------------------------------------------------------------------


def test_vision_ocr_and_provider_health_probes(tmp_path):
    # (a) LocalModel.vision_ocr
    ocr_payloads: list[dict] = []

    def ocr_transport(request: httpx.Request):
        req = json.loads(request.content)
        ocr_payloads.append(req)
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {"role": "assistant", "content": r"Câu 1: Tính $\frac{1}{2}$."},
                "eval_count": 15,
            },
        )

    async def _run_ocr():
        async with httpx.AsyncClient(transport=httpx.MockTransport(ocr_transport)) as client:
            lm = LocalModel(client, "qwen2.5:7b", RunLog(tmp_path / "ocr-log"))
            return await lm.vision_ocr(
                ["ZmFrZS1pbWFnZS1iNjQ="], "Đọc công thức", model="qwen2.5vl:7b"
            )

    ocr_out = asyncio.run(_run_ocr())
    assert ocr_payloads[0]["messages"][0]["images"] == ["ZmFrZS1pbWFnZS1iNjQ="]
    assert ocr_out["model"] == "qwen2.5vl:7b" and r"\frac{1}{2}" in ocr_out["text"]

    # (b) agyModel setting roundtrip in /api/config
    app = create_app(tmp_path / "agy-cfg")
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        res = client.post(
            "/api/config",
            json={"fixedRouter": {"agyModel": "claude-sonnet-4", "timePreset": "deep"}},
        )
        assert res.status_code == 200
        assert res.json()["fixedRouter"]["agyModel"] == "claude-sonnet-4"
        assert (
            client.post("/api/config", json={"fixedRouter": {"agyModel": "bad\nmodel"}}).status_code
            == 400
        )

    # (c) probe_providers_health & test_single_provider
    def health_transport(request: httpx.Request):
        url = str(request.url)
        if url.endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.6.5"})
        if url.endswith("/api/tags"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "qwen2.5:7b", "size": 1000},
                        {"name": "qwen2.5vl:7b", "size": 2000},
                        {"name": "bge-m3:latest", "size": 500},
                    ]
                },
            )
        if url.endswith("/models") and "deepseek" in url:
            auth = request.headers.get("authorization", "")
            if "401" in auth:
                return httpx.Response(401, json={"error": {"message": "bad key"}})
            if "402" in auth:
                return httpx.Response(402, json={"error": {"message": "no balance"}})
            if "429" in auth:
                return httpx.Response(429, json={"error": {"message": "rate limit"}})
            return httpx.Response(200, json={"data": [{"id": "deepseek-chat"}]})
        if "generativelanguage.googleapis.com" in url:
            return httpx.Response(200, json={"models": []})
        return httpx.Response(404)

    pool = GeminiKeyPool.from_keys(
        ("AIzaValidKeyOne123456", "AIzaValidKeyTwo123456", "AQ.ValidVertexThree12")
    )
    pool.mark_rate_limited("gemini-3.6-flash", 1)
    pool.invalid.add(2)

    cfg = {
        "ollama": {"url": "http://127.0.0.1:11434", "model": "qwen2.5:7b"},
        "fixedRouter": {"agyModel": "gemini-3.6-pro"},
        "deepseek": {
            "url": "https://api.deepseek.com/v1",
            "spentSessionUsd": 0.12,
            "spentTotalUsd": 1.45,
        },
        "gemini": {"freeTierConfirmed": True, "keyPool": pool},
    }
    secrets = {
        "deepseekKey": "sk-live-secret-ok-12345",
        "geminiKeys": ["AIzaValidKeyOne123456", "AIzaValidKeyTwo123456", "AQ.ValidVertexThree12"],
    }

    mp = pytest.MonkeyPatch()
    mp.setattr("mach_backend.poc_connections.detect_agy_cli", lambda _p="": r"C:\fake\agy.exe")

    async def _run_health():
        async with httpx.AsyncClient(transport=httpx.MockTransport(health_transport)) as client:
            health = await probe_providers_health(
                cfg,
                secrets,
                client=client,
                agy_runner=lambda _cmd, **_kw: SimpleNamespace(stdout=b"agy 2.4.1\n", returncode=0),
            )
            ds_401 = await check_single_provider(
                "deepseek", cfg, {"deepseekKey": "sk-401-secret"}, client=client
            )
            ds_402 = await check_single_provider(
                "deepseek", cfg, {"deepseekKey": "sk-402-secret"}, client=client
            )
            ds_429 = await check_single_provider(
                "deepseek", cfg, {"deepseekKey": "sk-429-secret"}, client=client
            )
            gm_ok = await check_single_provider("gemini", cfg, secrets, client=client)
            return health, ds_401, ds_402, ds_429, gm_ok

    try:
        health, ds_401, ds_402, ds_429, gm_ok = asyncio.run(_run_health())
    finally:
        mp.undo()

    serialized = json.dumps(health, ensure_ascii=False)
    assert "sk-live-secret-ok-12345" not in serialized
    assert health["ollama"]["reachable"] is True and health["ollama"]["version"] == "0.6.5"
    assert health["ollama"]["chatModels"] == ["qwen2.5:7b", "qwen2.5vl:7b"]
    assert health["ollama"]["visionModels"] == ["qwen2.5vl:7b"]
    assert health["ollama"]["embedModels"] == ["bge-m3:latest"]
    assert health["agy"]["available"] is True and health["agy"]["version"] == "agy 2.4.1"
    assert health["agy"]["agyModel"] == "gemini-3.6-pro"
    assert health["deepseek"]["ok"] is True
    assert (
        health["deepseek"]["spentSessionUsd"] == 0.12
        and health["deepseek"]["spentTotalUsd"] == 1.45
    )
    assert (
        health["gemini"]["validKeys"] == 3
        and health["gemini"]["cooldownSlots"] == [1]
        and health["gemini"]["disabledKeys"] == 1
    )
    assert ds_401["status"] == "auth_error" and "401" in ds_401["message"]
    assert ds_402["status"] == "insufficient_balance" and "402" in ds_402["message"]
    assert ds_429["status"] == "rate_limited" and "429" in ds_429["message"]
    assert gm_ok["ok"] is True
