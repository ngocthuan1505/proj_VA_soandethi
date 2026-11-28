"""Kiểm thử toàn diện bản vá AGY CLI 1.5.17, tầng Neon/Nhanh, cắt finish_exam và Tự động 1 chạm."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mach_backend.agy_cli_model import (
    AGY_RECOMMENDED_MODELS,
    DEFAULT_AGY_FAST_MODEL,
    DEFAULT_AGY_ORCHESTRATOR_MODEL,
    AgyCliModel,
    is_blocked_agy_model,
    normalize_agy_json_schema,
    resolve_agy_effort,
    validate_agy_model,
)
from mach_backend.ai_contract import AIError, Locator, SourceFragment
from mach_backend.ai_questions import ExamSlot, GenerateJob
from mach_backend.ai_router import (
    M01_OCR,
    M02_SOURCE_INDEX,
    M03_EXAM_BLUEPRINT,
    M04_GEN_STANDARD,
    M05_GEN_HARD,
    M06_BLIND_SOLVE,
    M07_DISTRACTOR_CHECK,
    M09_SURGICAL_REPAIR,
    M11_FLEXIBLE_CHAT,
    FixedTaskRouter,
    classify_micro_task,
    structured_tool_request,
)
from mach_backend.auto_create import (
    AutoCreateDeps,
    infer_exam_request_params,
    partition_auto_batches,
    register_auto_create_routes,
    verify_auto_questions,
)
from mach_backend.local_workspace import create_app
from mach_backend.matrix_agent import (
    LEVEL_RULES,
    run_chunked_matrix_agent,
    run_matrix_agent,
)
from mach_backend.poc_matrix import RunLog
from mach_backend.poc_policy import CallBudget
from mach_backend.poc_scoped_patch import _build_default_patch_router
from mach_backend.workspace_agent import AgentGeneration
from mach_backend.workspace_check import build_check_router_for_provider
from mach_backend.workspace_store import WorkspaceStore


def _parse_sse(raw_text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw_text.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        ev_type = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                ev_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((ev_type, json.loads("\n".join(data_lines))))
    return events


# ---------------------------------------------------------------------------
# 1. AGY CLI 1.5.17: normalize_agy_json_schema, envelope unwrap, stream-json
# ---------------------------------------------------------------------------


def test_structured_tool_request_and_normalize_agy_json_schema():
    two_tools = [
        {
            "type": "function",
            "function": {
                "name": "check_exam",
                "parameters": {
                    "type": "object",
                    "properties": {"questions": {"type": "array"}},
                    "required": ["questions"],
                    "$defs": {"Item": {"type": "object"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish_exam",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    req_two = structured_tool_request(
        {
            "messages": [{"role": "system", "content": "Soạn đề."}],
            "tools": two_tools,
        }
    )
    fmt_two = req_two["format"]
    assert fmt_two["type"] == "object"
    assert "oneOf" in fmt_two and len(fmt_two["oneOf"]) == 2
    assert "$defs" in fmt_two

    norm_two = normalize_agy_json_schema(fmt_two)
    assert norm_two == {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["check_exam", "finish_exam"]},
            "arguments": {"type": "object"},
        },
        "required": ["action", "arguments"],
    }

    req_one = structured_tool_request(
        {
            "messages": [{"role": "system", "content": "Soạn đề."}],
            "tools": two_tools[:1],
        }
    )
    norm_one = normalize_agy_json_schema(req_one["format"])
    assert norm_one is not None
    assert norm_one["type"] == "object"
    assert "oneOf" not in norm_one
    assert norm_one["properties"]["action"] == {"type": "string", "enum": ["check_exam"]}
    assert "questions" in norm_one["properties"]["arguments"]["properties"]
    assert "$defs" in norm_one

    # Non-object root schema wraps cleanly
    wrapped = normalize_agy_json_schema({"type": "array", "items": {"type": "string"}})
    assert wrapped is not None and wrapped["type"] == "object" and "result" in wrapped["properties"]


def test_agy_cli_unwraps_tool_action_from_structured_output_envelope_and_streams(tmp_path):
    fake_exe = tmp_path / "agy.exe"
    fake_exe.write_bytes(b"MZ")

    written_schemas: list[dict] = []

    def envelope_tool_runner(cmd, *, cwd, **_kwargs):
        schema_file = Path(cwd) / "schema.json"
        if schema_file.is_file():
            written_schemas.append(json.loads(schema_file.read_text(encoding="utf-8")))
        # AGY CLI 1.5.17 có thể bọc outer dict chứa cả "message" + "structured_output"
        cli_envelope = {
            "message": "Đã hoàn tất lượt gọi công cụ.",
            "stats": {"tokens": 42},
            "structured_output": {
                "action": "check_exam",
                "arguments": {"questions": [{"stem": "1 + 1 = ?"}]},
            },
        }
        return SimpleNamespace(stdout=json.dumps(cli_envelope, ensure_ascii=False).encode("utf-8"))

    model = AgyCliModel(
        RunLog(tmp_path / "agy-env"),
        custom_path=str(fake_exe),
        runner=envelope_tool_runner,
        effort="medium",
        model=DEFAULT_AGY_ORCHESTRATOR_MODEL,
    )
    res = asyncio.run(
        model(
            "agent",
            {
                "messages": [{"role": "user", "content": "Soạn 1 câu"}],
                "tools": [
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
                        "function": {
                            "name": "finish_exam",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
        )
    )
    assert res["tool_calls"][0]["function"]["name"] == "check_exam"
    assert res["tool_calls"][0]["function"]["arguments"] == {"questions": [{"stem": "1 + 1 = ?"}]}
    assert res["model"] == DEFAULT_AGY_ORCHESTRATOR_MODEL
    assert written_schemas and written_schemas[0]["type"] == "object"
    assert "oneOf" not in written_schemas[0]

    # Kiểm tra stream=True dùng --output-format stream-json + gọi on_delta
    stream_cmds: list[list[str]] = []
    received_deltas: list[str] = []

    def stream_runner(cmd, **_kwargs):
        stream_cmds.append(list(cmd))
        ndjson = "\n".join(
            [
                json.dumps({"type": "delta", "text": "Xin chào "}, ensure_ascii=False),
                json.dumps(
                    {"type": "content_block_delta", "delta": {"text": "thầy cô!"}},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"type": "result", "structuredOutput": {"message": "Xin chào thầy cô!"}},
                    ensure_ascii=False,
                ),
            ]
        )
        return SimpleNamespace(stdout=ndjson.encode("utf-8"), returncode=0)

    stream_model = AgyCliModel(
        RunLog(tmp_path / "agy-stream"),
        custom_path=str(fake_exe),
        runner=stream_runner,
        effort="low",
        model="gemini-3.8-flash",
    )

    async def on_delta_cb(chunk: str) -> None:
        received_deltas.append(chunk)

    stream_res = asyncio.run(
        stream_model(
            "chat",
            {
                "messages": [{"role": "user", "content": "Chào"}],
                "format": {"type": "object", "properties": {"message": {"type": "string"}}},
            },
            stream=True,
            on_delta=on_delta_cb,
        )
    )
    assert "--output-format" in stream_cmds[0]
    assert stream_cmds[0][stream_cmds[0].index("--output-format") + 1] == "stream-json"
    assert stream_cmds[0][stream_cmds[0].index("--effort") + 1] == "low"
    assert stream_cmds[0][stream_cmds[0].index("--model") + 1] == "gemini-3.8-flash"
    assert received_deltas == ["Xin chào ", "thầy cô!"]
    assert json.loads(stream_res["content"]) == {"message": "Xin chào thầy cô!"}

    # Kiểm tra bảo vệ AGY CLI 1.5.17:
    # không gửi --effort với orchestrator hoặc model đã gắn suffix.
    no_effort_cmds: list[list[str]] = []

    def capture_no_effort(cmd, **_kwargs):
        no_effort_cmds.append(list(cmd))
        return SimpleNamespace(stdout=b'{"response": "OK"}', returncode=0)

    for suffix_model in (DEFAULT_AGY_ORCHESTRATOR_MODEL, DEFAULT_AGY_FAST_MODEL):
        m = AgyCliModel(
            RunLog(tmp_path / f"no-effort-{suffix_model}"),
            custom_path=str(fake_exe),
            runner=capture_no_effort,
            effort="low",
            model=suffix_model,
        )
        asyncio.run(m("plan", {"messages": [{"role": "user", "content": "Test"}]}))
    assert len(no_effort_cmds) == 2
    assert all("--effort" not in cmd for cmd in no_effort_cmds)


# ---------------------------------------------------------------------------
# 2. Neon/Fast defaults, Argon blocking, classify_micro_task fix & tiered routing
# ---------------------------------------------------------------------------


def test_agy_defaults_and_blocked_model_validation(tmp_path):
    assert DEFAULT_AGY_ORCHESTRATOR_MODEL == "gemini-pro-orchestrator-neon"
    assert DEFAULT_AGY_FAST_MODEL == "gemini-3.8-flash-medium"
    assert AGY_RECOMMENDED_MODELS == (
        "gemini-pro-orchestrator-neon",
        "gemini-3.8-flash-medium",
        "gemini-4-neon-medium",
        "gemini-4-hydrogen-medium",
    )
    assert all(not is_blocked_agy_model(m) for m in AGY_RECOMMENDED_MODELS)
    assert is_blocked_agy_model("gemini-4-argon-high") is True
    assert is_blocked_agy_model("ARGON-pro") is True

    with pytest.raises(AIError) as exc_init:
        validate_agy_model("gemini-4-argon-medium")
    assert exc_init.value.code == "unsupported_model"

    with pytest.raises(AIError) as exc_cls:
        AgyCliModel(RunLog(tmp_path / "blocked"), model="gemini-4-argon")
    assert exc_cls.value.code == "unsupported_model"

    # Kiểm /api/config chặn 400 và lưu đọc đủ trường mới
    app = create_app(tmp_path / "cfg-app")
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        init_cfg = client.get("/api/config").json()["fixedRouter"]
        assert init_cfg["agyModel"] == DEFAULT_AGY_ORCHESTRATOR_MODEL
        assert init_cfg["agyFastModel"] == DEFAULT_AGY_FAST_MODEL
        assert init_cfg["agyEffort"] == "medium"
        assert init_cfg["autoPilot"] is True
        assert init_cfg["workspaceAiConsent"] is False

        assert (
            client.post(
                "/api/config", json={"fixedRouter": {"agyModel": "gemini-4-argon-high"}}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/config", json={"fixedRouter": {"agyFastModel": "custom-argon-fast"}}
            ).status_code
            == 400
        )

        updated = client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "fixedRouter": {
                    "agyModel": "gemini-4-neon-medium",
                    "agyFastModel": "gemini-3.8-flash-medium",
                    "agyEffort": "high",
                    "autoPilot": False,
                    "workspaceAiConsent": True,
                },
            },
        )
        assert updated.status_code == 200, updated.text
        fr = updated.json()["fixedRouter"]
        assert fr["agyModel"] == "gemini-4-neon-medium"
        assert fr["agyFastModel"] == "gemini-3.8-flash-medium"
        assert fr["agyEffort"] == "high"
        assert fr["autoPilot"] is False
        assert fr["workspaceAiConsent"] is True


def test_classify_micro_task_ignores_system_level_rules_and_tiered_router():
    # Bug cũ: system prompt chứa LEVEL_RULES ("Vận dụng cao") đẩy 100% lô NB/TH sang M05_GEN_HARD
    standard_body = {
        "messages": [
            {"role": "system", "content": "Bạn soạn đề. " + LEVEL_RULES},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "matrix": {
                            "slots": [
                                {"topic": "Hàm số", "level": 0, "levelName": "Nhận biết"},
                                {"topic": "Hàm số", "level": 1, "levelName": "Thông hiểu"},
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    assert classify_micro_task("agent", standard_body) == M04_GEN_STANDARD

    hard_body = {
        "messages": [
            {"role": "system", "content": "Bạn soạn đề. " + LEVEL_RULES},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "matrix": {
                            "slots": [
                                {"topic": "Hình học", "level": 2, "levelName": "Vận dụng"},
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }
    assert classify_micro_task("agent", hard_body) == M05_GEN_HARD

    # Legacy router (chỉ có "agy") giữ 100% hành vi cũ
    legacy_router = FixedTaskRouter(
        {
            "agy": lambda *_: {},
            "deepseek_chat": lambda *_: {},
            "gemini_flash": lambda *_: {},
            "ollama": lambda *_: {},
        }
    )
    assert legacy_router.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="standard")[0] == "agy"
    assert legacy_router.candidate_chain(M04_GEN_STANDARD)[0] == "deepseek_chat"

    # Tiered router (có agy_orchestrator + agy_fast)
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
    for hard_task in (
        M01_OCR,
        M02_SOURCE_INDEX,
        M03_EXAM_BLUEPRINT,
        M05_GEN_HARD,
        M07_DISTRACTOR_CHECK,
        M09_SURGICAL_REPAIR,
    ):
        assert tiered.candidate_chain(hard_task)[0] == "agy_orchestrator"
    assert tiered.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="deep")[0] == "agy_orchestrator"
    assert tiered.candidate_chain(M04_GEN_STANDARD)[:2] == ["agy_fast", "deepseek_chat"]
    assert tiered.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="standard")[:2] == [
        "agy_fast",
        "deepseek_chat",
    ]
    assert (
        tiered.candidate_chain(M06_BLIND_SOLVE, generator_family="agy_orchestrator")[0]
        == "deepseek_reasoner"
    )


def test_effort_resolution_and_tiered_registration_in_patch_and_check(tmp_path):
    assert resolve_agy_effort("blind_content_check") == "low"
    assert resolve_agy_effort("agent", tier="fast") == "low"
    assert resolve_agy_effort("exam_planning") == "medium"
    assert resolve_agy_effort("repair") == "high"
    assert resolve_agy_effort("agent", time_preset="deep") == "high"

    provider = SimpleNamespace(
        agy_available=True,
        agy_custom_path="",
        agy_model=DEFAULT_AGY_ORCHESTRATOR_MODEL,
        agy_fast_model=DEFAULT_AGY_FAST_MODEL,
        agy_effort="medium",
        gemini_key="",
        gemini_free_tier=False,
        all_gemini_keys=(),
        deepseek_key="",
        model="qwen3:4b",
        provider_name="ollama",
        active_model="qwen3:4b",
        reviewer_config={"provider": "ollama", "model": "qwen3:4b"},
        extended_policy=SimpleNamespace(timePreset="standard"),
    )

    async def _check_routers():
        async with httpx.AsyncClient() as client:
            patch_r = _build_default_patch_router(
                client, RunLog(tmp_path / "pr"), provider, budget=CallBudget(6, 60)
            )
            check_r = build_check_router_for_provider(
                client, RunLog(tmp_path / "cr"), provider, budget=CallBudget(6, 60)
            )
            assert "agy_orchestrator" in patch_r.providers and "agy_fast" in patch_r.providers
            assert "agy_orchestrator" in check_r.providers and "agy_fast" in check_r.providers

    asyncio.run(_check_routers())


# ---------------------------------------------------------------------------
# 3. matrix_agent: cắt lượt finish_exam thừa trên đề 22 câu chạy theo lô
# ---------------------------------------------------------------------------


def test_chunked_22q_cuts_redundant_finish_exam_calls():
    src = SourceFragment(
        ownerId="local",
        sourceId=uuid4(),
        sourceVersion=1,
        locator=Locator(kind="page", index=1),
        text="Hàm số bậc nhất y = ax + b (a != 0). Phương trình bậc hai ax^2 + bx + c = 0.",
    )
    # 22 câu: 16 MCQ (0.25đ = 4đ) + 6 Short (1.0đ = 6đ) -> tổng đúng 10.00đ, chia 4 lô (6, 6, 4, 6)
    slots_22 = (
        *[ExamSlot(type="mcq", topic="Đại số", level=0, points=0.25) for _ in range(16)],
        *[ExamSlot(type="short", topic="Phương trình", level=1, points=1.0) for _ in range(6)],
    )
    job_22 = GenerateJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=1,
        ownerId="local",
        sources=(src,),
        requireEvidence=True,
        subject="Toán",
        grade="9",
        slots=slots_22,
    )

    agent_turns = 0
    q_idx = 0

    async def batch_call(purpose: str, body: dict):
        nonlocal agent_turns, q_idx
        if purpose == "agent":
            agent_turns += 1
            last_msg = body["messages"][-1]
            # Với auto_finish_on_ok=True, KHÔNG gọi thêm lượt LLM sau khi check_exam ok=True
            assert not (
                last_msg.get("role") == "tool" and json.loads(last_msg["content"]).get("ok") is True
            ), "Không được gọi thêm lượt finish_exam thừa sau khi check_exam đã ok=True!"
            assign = json.loads(body["messages"][1]["content"])
            batch_slots = assign["matrix"]["slots"]
            is_mixed = any(s.get("type", "mcq") != "mcq" for s in batch_slots)
            questions = []
            for slot in batch_slots:
                q_idx += 1
                if slot["type"] == "mcq":
                    q_item: dict[str, object] = {
                        "stem": f"Câu trắc nghiệm #{q_idx}?",
                        "options": [f"Đúng {q_idx}", f"B{q_idx}", f"C{q_idx}", f"D{q_idx}"],
                        "answer": "0" if is_mixed else 0,
                        "explanation": f"Giải câu {q_idx}.",
                        "evidenceIds": [0],
                    }
                    if is_mixed:
                        q_item["rubric"] = [{"text": "Đúng.", "points": slot["points"]}]
                    questions.append(q_item)
                else:
                    questions.append(
                        {
                            "stem": f"Điền đáp số câu #{q_idx}?",
                            "options": [],
                            "answer": str(q_idx),
                            "explanation": f"Giải ngắn câu {q_idx}.",
                            "rubric": [{"text": "Đúng.", "points": slot["points"]}],
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
            q_list = data["questions"]
            is_mixed = any(q.get("type", "mcq") != "mcq" for q in q_list)
            reviews = []
            for i, q in enumerate(q_list):
                is_mcq = q.get("type", "mcq") == "mcq"
                num = q["stem"].split("#")[1].rstrip("?")
                review: dict[str, object] = {
                    "ordinal": i,
                    "answer": ("0" if is_mixed else 0) if is_mcq else num,
                    "observedLevel": 0 if is_mcq else 1,
                    "supported": True,
                    "topicMatches": True,
                    "uncertain": False,
                    "optionVerdicts": (
                        ["correct", "incorrect", "incorrect", "incorrect"] if is_mcq else []
                    ),
                    "duplicateWith": [],
                    "duplicateUncertain": False,
                    "reason": "Khớp.",
                }
                if is_mixed:
                    review["solution"] = "Giải độc lập."
                reviews.append(review)
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

    res = asyncio.run(run_chunked_matrix_agent(job_22, batch_call, lambda *_a, **_kw: None))
    assert res["status"] == "ready_for_teacher_review"
    assert len(res["proposal"]["questions"]) == 22
    # 4 lô -> chỉ đúng 4 lượt agent (0 lượt finish_exam thừa!)
    assert agent_turns == 4

    # Single batch mặc định vẫn giữ yêu cầu finish_exam như cũ (trừ khi auto_finish_on_ok=True)
    single_job = job_22.model_copy(
        update={"slots": (ExamSlot(type="mcq", topic="Đại số", level=0, points=10.0),)}
    )
    single_turns = 0

    async def single_call(purpose: str, body: dict):
        nonlocal single_turns
        if purpose == "agent":
            single_turns += 1
            return {
                "tool_calls": [
                    {
                        "function": {
                            "name": "check_exam",
                            "arguments": {
                                "questions": [
                                    {
                                        "stem": "Câu đơn 1?",
                                        "options": ["A", "B", "C", "D"],
                                        "answer": 0,
                                        "explanation": "Giải.",
                                        "evidenceIds": [0],
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        if purpose == "blind_content_check":
            return {
                "content": json.dumps(
                    {
                        "reviews": [
                            {
                                "ordinal": 0,
                                "answer": 0,
                                "observedLevel": 0,
                                "supported": True,
                                "topicMatches": True,
                                "uncertain": False,
                                "optionVerdicts": [
                                    "correct",
                                    "incorrect",
                                    "incorrect",
                                    "incorrect",
                                ],
                                "duplicateWith": [],
                                "duplicateUncertain": False,
                                "reason": "OK.",
                            }
                        ]
                    }
                )
            }
        return {
            "content": json.dumps(
                {"reviews": [{"ordinal": 0, "consistent": True, "reason": "OK."}]}
            )
        }

    res_auto = asyncio.run(
        run_matrix_agent(single_job, single_call, lambda *_a, **_kw: None, auto_finish_on_ok=True)
    )
    assert res_auto["status"] == "ready_for_teacher_review"
    assert single_turns == 1


# ---------------------------------------------------------------------------
# 4. Luồng Tự động 1 chạm (auto_create.py): Consent, Parallel Swarm, Goal Repair, Revision 409
# ---------------------------------------------------------------------------


def test_auto_create_consent_gate_stale_revision_parallel_swarm_and_goal_repair(tmp_path):
    store = WorkspaceStore(tmp_path / "ws")
    exam_id = str(uuid4())
    doc_id = str(uuid4())
    store.put(
        "state",
        {
            "current": exam_id,
            "exams": [
                {
                    "id": exam_id,
                    "title": "Đề trống",
                    "subject": "Toán",
                    "grade": "11",
                    "minutes": 45,
                    "revision": 3,
                    "questions": [],
                    "docs": [
                        {
                            "id": doc_id,
                            "name": "SGK Toán 11 · Chương Lượng giác",
                            "version": 1,
                            "pages": [
                                {
                                    "number": 1,
                                    "text": (
                                        "Hàm số lượng giác sin(x), cos(x) tuần hoàn chu kì 2pi."
                                    ),
                                }
                            ],
                        }
                    ],
                    "assistantSources": [doc_id],
                    "matrix": [],
                    "chat": [],
                    "history": [],
                    "undo": [],
                    "redo": [],
                }
            ],
        },
    )
    provider = AgentGeneration(
        store,
        "qwen3:4b",
        tmp_path / "agent",
        job_status=lambda _j: SimpleNamespace(status="running", errorCode=None),
    )

    in_flight = 0
    max_concurrency_seen = 0
    seen_tasks: list[str] = []
    injected_defect = {"done": False}

    async def fake_auto_ai(purpose: str, body: dict):
        nonlocal in_flight, max_concurrency_seen
        seen_tasks.append(purpose)
        if purpose == M03_EXAM_BLUEPRINT:
            # 10 câu (8 MCQ 0.5đ + 2 Essay 3.0đ) -> tổng đúng 10.00đ -> chia 2 lô 5+5
            slots = [
                *[{"topic": "Lượng giác", "type": "mcq", "level": 0} for _ in range(5)],
                *[{"topic": "Dãy số", "type": "mcq", "level": 2} for _ in range(3)],
                *[{"topic": "Tự luận tổng hợp", "type": "essay", "level": 3} for _ in range(2)],
            ]
            return {
                "model": DEFAULT_AGY_ORCHESTRATOR_MODEL,
                "content": json.dumps(
                    {
                        "slots": slots,
                        "notes": "Ma trận Toán 11 CK1 chuẩn GDPT 2018.",
                        "minutes": 60,
                    },
                    ensure_ascii=False,
                ),
            }

        if purpose in {M04_GEN_STANDARD, M05_GEN_HARD}:
            in_flight += 1
            max_concurrency_seen = max(max_concurrency_seen, in_flight)
            await asyncio.sleep(0.05)
            in_flight -= 1
            payload = json.loads(body["messages"][1]["content"])
            questions = []
            for s in payload["slots"]:
                ord_num = s["ordinal"]
                if s["type"] == "mcq":
                    # Cố ý tạo 1 lỗi thiếu phương án ở câu 1 để kích hoạt pha Goal tự sửa
                    opts = (
                        ["Trùng", "Trùng", "C", "D"]
                        if ord_num == 1 and not injected_defect["done"]
                        else [
                            f"Đáp án đúng #{ord_num}",
                            f"Nhiễu B #{ord_num}",
                            f"Nhiễu C #{ord_num}",
                            f"Nhiễu D #{ord_num}",
                        ]
                    )
                    if ord_num == 1:
                        injected_defect["done"] = True
                    questions.append(
                        {
                            "stem": f"Câu hỏi Toán 11 số {ord_num}: giá trị hàm lượng giác?",
                            "options": opts,
                            "answer": 0,
                            "explanation": f"Giải thích chi tiết câu {ord_num}.",
                            "evidenceIds": [0],
                        }
                    )
                else:
                    questions.append(
                        {
                            "stem": f"Bài tự luận số {ord_num}: chứng minh đẳng thức lượng giác.",
                            "options": [],
                            "answer": None,
                            "explanation": f"Lời giải đầy đủ bài {ord_num}.",
                            "rubric": [
                                {"text": "Biến đổi công thức.", "points": s["points"]},
                            ],
                            "evidenceIds": [0],
                        }
                    )
            return {
                "model": (
                    DEFAULT_AGY_FAST_MODEL
                    if purpose == M04_GEN_STANDARD
                    else DEFAULT_AGY_ORCHESTRATOR_MODEL
                ),
                "content": json.dumps({"questions": questions}, ensure_ascii=False),
            }

        if purpose == M09_SURGICAL_REPAIR:
            payload = json.loads(body["messages"][1]["content"])
            repaired = []
            for target in payload["targets"]:
                q = dict(target["currentQuestion"])
                q["options"] = ["Đáp án đã sửa A", "Nhiễu đã sửa B", "Nhiễu C", "Nhiễu D"]
                q["answer"] = 0
                repaired.append(q)
            return {
                "model": DEFAULT_AGY_ORCHESTRATOR_MODEL,
                "content": json.dumps({"questions": repaired}, ensure_ascii=False),
            }

        raise AssertionError(f"Unexpected purpose: {purpose}")

    app = FastAPI()
    register_auto_create_routes(
        app,
        deps=AutoCreateDeps(
            store=store,
            provider=provider,
            agent_call=fake_auto_ai,
            directory=tmp_path / "logs",
        ),
    )

    with TestClient(app) as client:
        # 1. Thiếu consent -> 400 consent_required
        no_consent = client.post(
            f"/api/exams/{exam_id}/agent/auto-create",
            json={"prompt": "Soạn đề Toán 11 CK1 chuẩn GDPT 2018"},
        )
        assert no_consent.status_code == 400
        assert no_consent.json()["code"] == "consent_required"

        # 2. Lệch expectedRevision -> 409 stale_snapshot
        stale = client.post(
            f"/api/exams/{exam_id}/agent/auto-create",
            json={
                "prompt": "Soạn đề Toán 11 CK1",
                "consentGiven": True,
                "expectedRevision": 2,
            },
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "stale_snapshot"

        # 3. Chạy đầy đủ 4 pha + lưu workspace consent
        resp = client.post(
            f"/api/exams/{exam_id}/agent/auto-create",
            json={
                "prompt": "Soạn đề Toán 11 CK1 chuẩn GDPT 2018",
                "expectedRevision": 3,
                "sourceIds": [doc_id],
                "consentGiven": True,
                "saveWorkspaceConsent": True,
                "campaignId": "camp-01",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse(resp.text)
        ev_names = [name for name, _ in events]
        assert "step" in ev_names
        assert "batch" in ev_names
        assert "verify" in ev_names
        assert ev_names[-1] == "complete"

        plan_done = next(
            d
            for n, d in events
            if n == "step" and d.get("phase") == "plan" and d.get("status") == "done"
        )
        assert plan_done["subject"] == "Toán"
        assert plan_done["grade"] == "11"
        assert plan_done["minutes"] == 60

        batch_events = [d for n, d in events if n == "batch"]
        assert len(batch_events) == 2
        assert {b["microTask"] for b in batch_events} == {M04_GEN_STANDARD, M05_GEN_HARD}
        assert max_concurrency_seen >= 2 and max_concurrency_seen <= 3

        verify_events = [d for n, d in events if n == "verify"]
        assert any(v.get("repairing") is True for v in verify_events)
        assert verify_events[-1]["ok"] is True
        assert verify_events[-1]["totalPoints"] == 10.0
        assert verify_events[-1]["repairRounds"] == 1
        assert M09_SURGICAL_REPAIR in seen_tasks

        complete = events[-1][1]
        assert complete["totalQuestions"] == 10
        assert complete["totalPoints"] == 10.0
        assert complete["savedRevision"] == 4
        assert complete["campaignId"] == "camp-01"
        assert all(q["approvalStatus"] == "draft" for q in complete["questions"])
        assert all(q["source"] and q["source"]["docId"] == doc_id for q in complete["questions"])
        assert DEFAULT_AGY_ORCHESTRATOR_MODEL in complete["stats"]["modelsUsed"]
        assert DEFAULT_AGY_FAST_MODEL in complete["stats"]["modelsUsed"]

        # Xác nhận đã ghi revision mới + undo snapshot vào store
        _, saved_exam = store.exam(exam_id)
        assert saved_exam["revision"] == 4
        assert len(saved_exam["questions"]) == 10
        assert saved_exam["undo"][-1]["label"] == "AI tự động soạn đề"
        assert saved_exam["chat"][-1]["undoRevision"] == 4

        # 4. Nhờ saveWorkspaceConsent=True ở lượt trước, lượt sau không cần gửi consentGiven
        assert provider.workspace_ai_consent is True
        resp2 = client.post(
            f"/api/exams/{exam_id}/agent/auto-create",
            json={
                "prompt": "Soạn đề Ngữ văn 10 đọc hiểu 45 phút",
                "expectedRevision": 4,
                "persistToStore": False,
            },
        )
        assert resp2.status_code == 200
        events2 = _parse_sse(resp2.text)
        assert events2[-1][0] == "complete"
        assert events2[-1][1]["persistedToStore"] is False


def test_auto_create_helpers_and_deterministic_fallback_when_offline(tmp_path):
    params = infer_exam_request_params("Soạn đề Tiếng Anh 12 THPT 60 phút chỉ trắc nghiệm 12 câu")
    assert params["subject"] == "Tiếng Anh"
    assert params["grade"] == 12
    assert params["minutes"] == 60
    assert params["count"] == 12
    assert params["types"] == ["mcq"]

    slots_11 = [ExamSlot(type="mcq", topic="Chủ đề", level=i % 4, points=0.5) for i in range(11)]
    batches = partition_auto_batches(slots_11)
    assert [len(b) for b in batches] == [4, 4, 3]
    assert all(3 <= len(b) <= 5 for b in batches)

    # Kiểm tra fallback an toàn khi không có kênh AI live (không treo)
    app = FastAPI()
    register_auto_create_routes(app, directory=tmp_path / "offline")
    with TestClient(app) as client:
        r = client.post(
            f"/api/exams/{uuid4()}/agent/auto-create",
            json={"prompt": "Soạn đề Toán 9 45 phút", "consentGiven": True},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        complete = events[-1][1]
        assert events[-1][0] == "complete"
        assert complete["totalPoints"] == 10.0
        assert complete["stats"]["fallbackUsed"] is True
        assert all(q["approvalStatus"] == "draft" for q in complete["questions"])

    # verify_auto_questions bắt lỗi lệch điểm & trùng thân
    bad_slots = (
        ExamSlot(type="mcq", topic="T1", level=0, points=5.0),
        ExamSlot(type="mcq", topic="T2", level=1, points=5.0),
    )
    bad_qs = [
        {
            "type": "mcq",
            "points": 5.0,
            "stem": "Trùng?",
            "options": ["A", "B", "C", "D"],
            "answer": 0,
            "explanation": "OK",
        },
        {
            "type": "mcq",
            "points": 4.0,
            "stem": "Trùng?",
            "options": ["A", "A", "C", "D"],
            "answer": 9,
            "explanation": "",
        },
    ]
    found_codes = {i["code"] for i in verify_auto_questions(bad_qs, bad_slots)}
    assert {
        "points_mismatch",
        "duplicate_stem",
        "duplicate_options",
        "invalid_answer",
        "empty_explanation",
        "total_points_mismatch",
    }.issubset(found_codes)
