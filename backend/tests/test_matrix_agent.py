"""Fixture kiểm cơ chế công cụ; không là số đo chất lượng model thật."""

import asyncio
import copy
import json
from uuid import uuid4

import httpx
import pytest

from mach_backend.ai_questions import GenerateJob, validate_generation
from mach_backend.ai_service import propose_exam
from mach_backend.matrix_agent import (
    ContentReview,
    candidate_hash,
    candidate_proposal,
    inspect_candidate,
    run_matrix_agent,
)
from mach_backend.matrix_provider import MatrixProvider
from mach_backend.mixed_questions import MixedDraftBatch
from mach_backend.poc_matrix import (
    LocalModel,
    RunLog,
    structured_tool_request,
    structured_tool_response,
)
from mach_backend.poc_policy import CallBudget


@pytest.fixture
def job():
    return GenerateJob.model_validate_json(
        json.dumps(
            {
                "jobId": str(uuid4()),
                "examId": str(uuid4()),
                "baseRevision": 1,
                "ownerId": "fixture",
                "subject": "Ngữ văn",
                "grade": "6",
                "requireEvidence": True,
                "slots": [{"type": "mcq", "topic": "Chi tiết", "level": 0, "pointsQ4": 40}],
                "sources": [
                    {
                        "ownerId": "fixture",
                        "sourceId": str(uuid4()),
                        "sourceVersion": 1,
                        "locator": {"kind": "passage", "index": 1},
                        "text": "Mai báo với cô Loan về cửa sổ hỏng.",
                    }
                ],
            },
            ensure_ascii=False,
        )
    )


def draft(answer=2):
    return {
        "questions": [
            {
                "stem": "Mai báo với ai?",
                "options": ["Lan", "Nam", "Cô Loan", "Bảo vệ"],
                "answer": answer,
                "explanation": "Mai báo với cô Loan.",
                "evidenceIds": [0],
            }
        ]
    }


def tool(name, arguments):
    return {"function": {"name": name, "arguments": arguments}}


class ModelFixture:
    def __init__(self, agent_calls, *, uncertain=False, omit_review=False):
        self.agent_calls = iter(agent_calls)
        self.calls = []
        self.uncertain, self.omit_review = uncertain, omit_review

    async def __call__(self, purpose, body):
        self.calls.append((purpose, copy.deepcopy(body)))
        if purpose == "agent":
            return {"role": "assistant", "content": "", "tool_calls": next(self.agent_calls)}
        if purpose == "blind_content_check":
            data = json.loads(body["messages"][1]["content"])
            for question in data["questions"]:
                assert set(question) == {"ordinal", "stem", "options", "topic"}
                assert [o["index"] for o in question["options"]] == [0, 1, 2, 3]
                assert [o["text"] for o in question["options"]] == draft()["questions"][0][
                    "options"
                ]
            assert body["format"]["properties"]["reviews"]["maxItems"] == len(data["questions"])
            reviews = (
                []
                if self.omit_review
                else [
                    {
                        "ordinal": 0,
                        "answer": None if self.uncertain else 2,
                        "observedLevel": 0,
                        "supported": True,
                        "topicMatches": True,
                        "uncertain": self.uncertain,
                        "optionVerdicts": ["incorrect", "incorrect", "correct", "incorrect"],
                        "duplicateWith": [],
                        "duplicateUncertain": False,
                        "reason": "Nguồn nêu trực tiếp cô Loan.",
                    }
                ]
            )
            return {"content": json.dumps({"reviews": reviews}, ensure_ascii=False)}
        assert purpose == "explanation_check"
        return {
            "content": json.dumps(
                {"reviews": [{"ordinal": 0, "consistent": True, "reason": "Khớp nguồn."}]}
            )
        }


def events():
    log = []
    return log, lambda event, **data: log.append({"event": event, **data})


def test_wrong_level_defers_explanation_until_replacement_is_checked(job):
    model = ModelFixture([])
    _, emit = events()

    async def wrong_level(purpose, body):
        assert purpose == "blind_content_check"
        response = await model(purpose, body)
        value = json.loads(response["content"])
        value["reviews"][0]["observedLevel"] = 1
        return {"content": json.dumps(value)}

    _, rejected = asyncio.run(inspect_candidate(job, draft(), wrong_level, emit))
    assert not rejected["ok"]
    assert [error["code"] for error in rejected["errors"]] == ["level_disagreement"]
    assert {c["toolName"]: c["status"] for c in rejected["checks"]}[
        "check_explanation"
    ] == "UNKNOWN"
    assert rejected["explanations"] == []

    _, checked = asyncio.run(inspect_candidate(job, draft(), model, emit))
    assert checked["ok"]
    assert [purpose for purpose, _ in model.calls] == [
        "blind_content_check",
        "blind_content_check",
        "explanation_check",
    ]


def test_model_uses_tool_and_repairs_wrong_answer_before_finish(job):
    before = job.model_dump_json()
    model = ModelFixture(
        [[tool("check_exam", draft(3))], [tool("check_exam", draft(2))], [tool("finish_exam", {})]]
    )
    log, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "ready_for_teacher_review"
    assert result["generationAttempts"] == 2
    assert result["toolCalls"] == 3
    assert result["saved"] is False
    assert job.model_dump_json() == before
    feedback = model.calls[3][1]["messages"][-1]
    assert feedback["role"] == "tool"
    assert "answer_disagreement" in feedback["content"]
    answer_error = json.loads(feedback["content"])["errors"][0]
    assert answer_error["actualAnswer"] == 3
    assert answer_error["checkedAnswer"] == 2
    assert [row["ok"] for row in log if row["event"] == "generation_result"] == [False, True]
    assert [
        [tool["function"]["name"] for tool in request["tools"]]
        for purpose, request in model.calls
        if purpose == "agent"
    ] == [["check_exam"], ["check_exam"], ["check_exam", "finish_exam"]]
    schema = model.calls[0][1]["tools"][0]["function"]["parameters"]
    matrix = json.loads(model.calls[0][1]["messages"][1]["content"])["matrix"]
    assert matrix["slots"][0]["level"] == 0
    assert "nêu trực tiếp" in matrix["slots"][0]["requiredTask"]
    assert "$ref" not in json.dumps(schema)
    assert schema["properties"]["questions"]["maxItems"] == 1
    explanation_input = json.loads(model.calls[2][1]["messages"][1]["content"])
    assert explanation_input["questions"][0]["evidence"][0]["quote"] == job.sources[0].text
    assert explanation_input["questions"][0]["chosenOption"] == {"index": 3, "text": "Bảo vệ"}


def test_two_attempt_limit_cannot_be_bypassed_by_parallel_tool_calls(job):
    model = ModelFixture([[tool("check_exam", draft(3))] * 3])
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit, max_attempts=2))
    assert result["status"] == "attempt_limit"
    assert result["generationAttempts"] == 2
    assert len([c for c in model.calls if c[0] == "blind_content_check"]) == 1
    assert result["report"]["reusedFromAttempt"] == 1
    assert "proposal" not in result


def test_budget_mode_can_repair_more_than_two_submissions(job):
    model = ModelFixture(
        [[tool("check_exam", draft(3))]] * 3
        + [[tool("check_exam", draft(2))], [tool("finish_exam", {})]]
    )
    log, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit, max_attempts=None, max_turns=12))
    assert result["status"] == "ready_for_teacher_review"
    assert result["generationAttempts"] == 4
    reports = [r for r in log if r["event"] == "generation_result"]
    assert [r["ok"] for r in reports] == [False, False, False, True]
    assert [r.get("reusedFromAttempt") for r in reports] == [None, 1, 1, None]
    assert reports[1]["errors"] == reports[0]["errors"]
    assert len([c for c in model.calls if c[0] == "blind_content_check"]) == 2
    next_request = [r for purpose, r in model.calls if purpose == "agent"][2]
    assert "Viết lại" in json.loads(next_request["messages"][-1]["content"])["repairInstruction"]
    final = result["report"]
    assert all(
        r["status"] == "PASS" and r["candidateHash"] == final["candidateHash"]
        for r in final["checks"]
    )
    assert reports[0]["candidateHash"] != final["candidateHash"]


def test_report_hash_changes_when_source_or_matrix_changes(job):
    before = candidate_hash(job, draft())
    source = job.sources[0].model_copy(update={"sourceVersion": 2})
    assert candidate_hash(job.model_copy(update={"sources": (source,)}), draft()) != before
    assert candidate_hash(job.model_copy(update={"instructions": "Rubric mới"}), draft()) != before


def test_finish_cannot_skip_tools(job):
    model = ModelFixture([[tool("finish_exam", {})]] * 4)
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "turn_limit"
    assert result["generationAttempts"] == 0
    assert "proposal" not in result


@pytest.mark.parametrize("uncertain,omit", [(True, False), (False, True)])
def test_uncertain_or_incomplete_review_fails_closed(job, uncertain, omit):
    model = ModelFixture([[tool("check_exam", draft())]] * 2, uncertain=uncertain, omit_review=omit)
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "attempt_limit"
    assert not result["report"]["ok"]
    assert "proposal" not in result


def test_plain_chat_is_not_accepted_as_finished_exam(job):
    model = ModelFixture([[]])
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "no_tool_call"
    assert "proposal" not in result


def test_bad_source_index_is_rejected_by_code(job):
    candidate = draft()
    candidate["questions"][0]["evidenceIds"] = [-1]
    with pytest.raises(ValueError, match="không tồn tại"):
        candidate_proposal(job, candidate)


def test_comparison_can_use_four_existing_evidence_spans_but_not_duplicates(job):
    source = job.sources[0].model_copy(
        update={"text": "Mai báo với cô Loan. Nam chuyển sách. Cửa được sửa lại. Sách vẫn khô ráo."}
    )
    job = job.model_copy(update={"sources": (source,)})
    candidate = draft()
    candidate["questions"][0]["evidenceIds"] = [0, 1, 2, 3]
    proposal = candidate_proposal(job, candidate)
    assert len(proposal.questions[0].evidence) == 4
    assert all(e.sourceId == source.sourceId for e in proposal.questions[0].evidence)
    candidate["questions"][0]["evidenceIds"] = [0, 0]
    with pytest.raises(ValueError, match="lặp mã"):
        candidate_proposal(job, candidate)
    candidate["questions"][0]["evidenceIds"] = list(range(13))
    with pytest.raises(ValueError, match="at most 12"):
        candidate_proposal(job, candidate)


def test_certain_review_without_answer_is_rejected(job):
    model = ModelFixture([[tool("check_exam", draft())]] * 2)

    async def contradictory_review(purpose, body):
        response = await model(purpose, body)
        if purpose == "blind_content_check":
            reviews = json.loads(response["content"])
            reviews["reviews"][0]["answer"] = None
            response["content"] = json.dumps(reviews)
        return response

    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, contradictory_review, emit))
    assert result["status"] == "attempt_limit"
    assert result["report"]["errors"][0]["code"] == "invalid_review"
    assert "thiếu chỉ số đáp án" in result["report"]["errors"][0]["details"][0]["message"]
    assert "proposal" not in result


@pytest.mark.parametrize(
    "label,number", [("Nhận biết", 0), ("Thông hiểu", 1), ("Vận dụng", 2), ("Vận dụng cao", 3)]
)
def test_review_level_names_keep_internal_numeric_mapping(label, number):
    value = {
        "ordinal": 0,
        "answer": 0,
        "observedLevel": label,
        "supported": True,
        "topicMatches": True,
        "uncertain": False,
        "optionVerdicts": ["correct", "incorrect", "incorrect", "incorrect"],
        "duplicateWith": [],
        "duplicateUncertain": False,
        "reason": "Kiểm tên mức và biểu diễn nội bộ.",
    }
    result = ContentReview.model_validate_json(json.dumps(value))
    assert result.observedLevel == number
    schema = ContentReview.model_json_schema()["properties"]["observedLevel"]
    assert schema["anyOf"][0]["enum"] == ["Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"]
    value["observedLevel"] = "VDC"
    with pytest.raises(ValueError, match="không hợp lệ"):
        ContentReview.model_validate_json(json.dumps(value))


def test_option_labels_do_not_hide_duplicate_content(job):
    candidate = draft()
    candidate["questions"][0]["options"] = ["A. Mai", "B. Mai", "C. Mai", "D. Mai"]
    with pytest.raises(ValueError, match="Câu 1: phương án trùng nội dung"):
        candidate_proposal(job, candidate)


@pytest.mark.parametrize(
    "patch,code",
    [
        (
            {"optionVerdicts": ["incorrect"] * 4, "answer": None, "uncertain": True},
            "option_verdicts_failed",
        ),
        (
            {"optionVerdicts": ["incorrect", "correct", "correct", "incorrect"]},
            "option_verdicts_failed",
        ),
        (
            {"optionVerdicts": ["unknown", "incorrect", "correct", "incorrect"]},
            "option_verdicts_failed",
        ),
        (
            {"optionVerdicts": ["incorrect", "correct", "incorrect", "incorrect"]},
            "answer_verdict_disagreement",
        ),
        ({"duplicateUncertain": True}, "uncertain_duplicate"),
    ],
)
def test_per_option_and_duplicate_uncertainty_block_finish(job, patch, code):
    model = ModelFixture([[tool("check_exam", draft())]] * 2)

    async def review(purpose, body):
        response = await model(purpose, body)
        if purpose == "blind_content_check":
            data = json.loads(response["content"])
            data["reviews"][0].update(patch)
            response["content"] = json.dumps(data)
        return response

    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, review, emit))
    assert result["status"] == "attempt_limit"
    assert code in [e["code"] for e in result["report"]["errors"]]
    assert "proposal" not in result


def test_semantic_duplicate_with_different_words_is_blocked(job):
    job = job.model_copy(update={"slots": (job.slots[0].model_copy(update={"pointsQ4": 20}),) * 2})
    candidate = draft()
    candidate["questions"].append(
        {**candidate["questions"][0], "stem": "Người Mai thông báo là ai?"}
    )

    async def model(purpose, body):
        if purpose == "agent":
            return {"tool_calls": [tool("check_exam", candidate)]}
        if purpose == "blind_content_check":
            return {
                "content": json.dumps(
                    {
                        "reviews": [
                            {
                                "ordinal": i,
                                "answer": 2,
                                "observedLevel": 0,
                                "supported": True,
                                "topicMatches": True,
                                "uncertain": False,
                                "optionVerdicts": [
                                    "incorrect",
                                    "incorrect",
                                    "correct",
                                    "incorrect",
                                ],
                                "duplicateWith": [] if i == 0 else [0],
                                "duplicateUncertain": False,
                                "reason": "Hai câu đều hỏi người nhận thông báo.",
                            }
                            for i in range(2)
                        ]
                    }
                )
            }
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {"ordinal": i, "consistent": True, "reason": "Khớp."} for i in range(2)
                    ]
                }
            )
        }

    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "attempt_limit"
    assert result["report"]["errors"][0]["code"] == "semantic_duplicate"
    assert result["report"]["errors"][0]["duplicateWith"] == (0,)


@pytest.mark.parametrize("bad", [[0], [-1], [2], [0, 0]])
def test_duplicate_references_must_be_unique_prior_questions(bad):
    value = {
        "ordinal": 0 if bad == [0] else 1,
        "answer": 0,
        "observedLevel": 0,
        "supported": True,
        "topicMatches": True,
        "uncertain": False,
        "optionVerdicts": ["correct", "incorrect", "incorrect", "incorrect"],
        "duplicateWith": bad,
        "duplicateUncertain": False,
        "reason": "Fixture.",
    }
    with pytest.raises(ValueError, match="mã câu trước"):
        ContentReview.model_validate_json(json.dumps(value))


def test_unknown_tool_is_never_executed(job):
    model = ModelFixture([[tool("execute_shell", {"command": "anything"})]] * 4)
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "turn_limit"
    assert all(purpose == "agent" for purpose, _ in model.calls)
    assert "tool_not_allowed" in model.calls[-1][1]["messages"][-1]["content"]


@pytest.mark.parametrize("calls", [[None], [{"function": []}], [tool("finish_exam", {})] * 9])
def test_malformed_or_excessive_tool_calls_fail_closed(job, calls):
    model = ModelFixture([calls])
    _, emit = events()
    result = asyncio.run(run_matrix_agent(job, model, emit))
    assert result["status"] == "invalid_tool_call"
    assert result["generationAttempts"] == 0
    assert "proposal" not in result


def test_local_adapter_returns_typed_proposal(job):
    def respond(request):
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(draft()["questions"][0], ensure_ascii=False),
                },
            },
        )

    provider = MatrixProvider("qwen2.5:3b", transport=httpx.MockTransport(respond))
    raw = asyncio.run(provider(job))
    proposal = validate_generation(job, raw)
    assert proposal.questions[0].evidence[0].quote == job.sources[0].text
    assert proposal.questions[0].pointsQ4 == 40


def test_structured_protocol_preserves_real_tool_feedback(job):
    original = {
        "messages": [
            {"role": "system", "content": "Soạn đề."},
            {"role": "assistant", "tool_calls": [tool("check_exam", draft(3))]},
            {"role": "tool", "tool_name": "check_exam", "content": '{"ok":false}'},
        ],
        "tools": [{"function": {"name": "check_exam", "parameters": {"type": "object"}}}],
    }
    request = structured_tool_request(original)
    assert "format" in request and "tools" not in request
    assert json.loads(request["messages"][-1]["content"])["result"] == {"ok": False}
    assert json.loads(request["messages"][1]["content"])["arguments"] == draft(3)
    assert original["messages"][0]["content"] == "Soạn đề."
    response = structured_tool_response(
        {"content": json.dumps({"action": "check_exam", "arguments": draft()})}
    )
    assert response["tool_calls"] == [tool("check_exam", draft())]


def test_ollama_structured_tool_keeps_references_at_schema_root():
    parameters = MixedDraftBatch.model_json_schema()
    request = structured_tool_request(
        {
            "messages": [{"role": "system", "content": "Soạn đề."}],
            "tools": [{"function": {"name": "check_exam", "parameters": parameters}}],
        }
    )
    schema = request["format"]
    nested = schema["oneOf"][0]["properties"]["arguments"]
    assert "$defs" not in nested
    assert schema["$defs"] == parameters["$defs"]
    assert schema["$defs"]["MixedDraftQuestion"]["properties"]["rubric"]["items"] == {
        "$ref": "#/$defs/RubricStep"
    }
    assert nested["properties"]["questions"] == parameters["properties"]["questions"]


def test_ollama_restarts_context_after_exact_repeat_without_losing_feedback():
    feedback = {
        "ok": False,
        "reusedFromAttempt": 1,
        "errors": [{"ordinal": 0, "code": "level_disagreement"}],
    }
    assignment = {"role": "user", "content": '{"matrix":{"slots":[]},"source":[]}'}
    messages = [
        {"role": "system", "content": "Soạn đề."},
        assignment,
        {"role": "assistant", "tool_calls": [tool("check_exam", draft(3))]},
        {"role": "tool", "tool_name": "check_exam", "content": '{"ok":false}'},
        {"role": "assistant", "tool_calls": [tool("check_exam", draft(3))]},
        {"role": "tool", "tool_name": "check_exam", "content": json.dumps(feedback)},
    ]
    request = structured_tool_request(
        {
            "messages": messages,
            "tools": [{"function": {"name": "check_exam", "parameters": {"type": "object"}}}],
        }
    )
    assert len(request["messages"]) == 3 and len(messages) == 6
    assert request["messages"][1] == assignment
    assert json.loads(request["messages"][-1]["content"]) == {
        "toolResult": "check_exam",
        "result": feedback,
    }
    assert "đặt câu hỏi mới" in request["messages"][0]["content"]


@pytest.mark.parametrize("budget_seconds", [None, 900])
def test_model_call_budget_and_raw_response_are_kept(tmp_path, budget_seconds):
    def respond(request):
        assert json.loads(request.content)["options"] == {
            "temperature": 0.45,
            "num_ctx": 8192,
            "num_predict": 2400,
        }
        timeout = request.extensions["timeout"]
        if budget_seconds is None:
            assert timeout["read"] == 300
        else:
            assert 890 < timeout["read"] <= budget_seconds
            assert timeout["connect"] == 5
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": "{}"}}
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), timeout=1) as client:
            budget = CallBudget(4, budget_seconds) if budget_seconds else None
            model = LocalModel(client, "qwen2.5:3b", RunLog(tmp_path / "log"), budget=budget)
            return await model("agent", {"messages": [], "options": {"temperature": 0.45}})

    assert asyncio.run(run())["content"] == "{}"
    response = json.loads((tmp_path / "log/call-01-response.json").read_text())
    assert response["done"] is True


@pytest.mark.parametrize("action", ["execute_shell", "auto_save"])
def test_structured_protocol_rejects_unknown_tools(action):
    with pytest.raises(ValueError, match="không hợp lệ"):
        structured_tool_response({"content": json.dumps({"action": action, "arguments": {}})})


def test_multi_call_workflow_timeout_is_bounded(job):
    async def provider(current_job):
        return candidate_proposal(current_job, draft()).model_dump_json()

    async def current(_job):
        return True

    proposal = asyncio.run(propose_exam(job, provider, current, timeout_seconds=900))
    assert len(proposal.questions) == 1
    with pytest.raises(ValueError, match="900"):
        asyncio.run(propose_exam(job, provider, current, timeout_seconds=901))
