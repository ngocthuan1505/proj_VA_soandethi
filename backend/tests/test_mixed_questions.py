"""Bốn dạng câu qua cùng vòng công cụ; fixture không là kết quả AI thật."""

import asyncio
import copy
import json
from uuid import uuid4

import pytest

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import GenerateJob
from mach_backend.matrix_agent import candidate_proposal, inspect_candidate, run_matrix_agent
from mach_backend.mixed_questions import decode_answer
from mach_backend.workspace_agent import local_model_call


@pytest.fixture
def mixed():
    job = GenerateJob.model_validate_json(
        json.dumps(
            {
                "jobId": str(uuid4()),
                "examId": str(uuid4()),
                "baseRevision": 1,
                "ownerId": "fixture",
                "subject": "Ngữ văn",
                "grade": "6",
                "requireEvidence": True,
                "slots": [
                    {"type": kind, "topic": "Đọc hiểu", "level": i % 3, "pointsQ4": 10}
                    for i, kind in enumerate(["mcq", "truefalse", "short", "essay"])
                ],
                "sources": [
                    {
                        "ownerId": "fixture",
                        "sourceId": str(uuid4()),
                        "sourceVersion": 1,
                        "locator": {"kind": "passage", "index": 1},
                        "text": "Mai báo cô Loan về cửa sổ hỏng. Nam mang sách đến thư viện.",
                    }
                ],
            }
        )
    )
    questions = [
        {
            "stem": f"Câu giả lập {i + 1}: {slot.type}?",
            "options": ["Lan", "Nam", "Cô Loan", "Hà"] if slot.type in {"mcq", "truefalse"} else [],
            "answer": ["2", "1010", "Mai", ""][i],
            "explanation": "Lời giải giả lập có căn cứ.",
            "rubric": [{"text": "Bước giải giả lập.", "pointsQ4": 10}],
            "evidenceIds": [0],
        }
        for i, slot in enumerate(job.slots)
    ]
    return job, {"questions": questions}


class MixedModel:
    def __init__(self, job, arguments, *, fail_verdict=False, fail_essay=False):
        self.job, self.arguments = job, arguments
        self.calls, self.attempts = [], 0
        self.fail_verdict, self.fail_essay = fail_verdict, fail_essay

    async def __call__(self, purpose, body):
        self.calls.append((purpose, copy.deepcopy(body)))
        if purpose == "agent":
            if (
                body["messages"][-1]["role"] == "tool"
                and json.loads(body["messages"][-1]["content"])["ok"]
            ):
                return {"tool_calls": [{"function": {"name": "finish_exam", "arguments": {}}}]}
            self.attempts += 1
            args = copy.deepcopy(self.arguments)
            if self.attempts == 1:
                args["questions"][0]["answer"] = "1"
            return {"tool_calls": [{"function": {"name": "check_exam", "arguments": args}}]}
        data = json.loads(body["messages"][1]["content"])
        if purpose == "blind_content_check":
            assert all(
                set(q) == {"ordinal", "stem", "options", "topic", "type"} for q in data["questions"]
            )
            return {
                "content": json.dumps(
                    {
                        "reviews": [
                            {
                                "ordinal": i,
                                "answer": q["answer"],
                                "solution": "Tự giải giả lập trước khi xem đáp án.",
                                "observedLevel": self.job.slots[i].level,
                                "supported": True,
                                "topicMatches": True,
                                "uncertain": False,
                                "duplicateWith": [],
                                "duplicateUncertain": False,
                                "reason": "Fixture.",
                                "optionVerdicts": (
                                    [
                                        "correct" if j == int(q["answer"]) else "incorrect"
                                        for j in range(4)
                                    ]
                                    if self.job.slots[i].type == "mcq"
                                    else (
                                        ["incorrect"] * 4
                                        if self.fail_verdict
                                        else ["correct", "incorrect", "correct", "incorrect"]
                                    )
                                    if self.job.slots[i].type == "truefalse"
                                    else []
                                ),
                            }
                            for i, q in enumerate(self.arguments["questions"])
                        ]
                    }
                )
            }
        assert purpose == "explanation_check"
        assert data["questions"][3]["rubric"][0]["pointsQ4"] == self.job.slots[3].pointsQ4
        assert data["questions"][3]["blindSolution"].startswith("Tự giải")
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {
                            "ordinal": i,
                            "consistent": not (self.fail_essay and i == 3),
                            "reason": "Fixture.",
                        }
                        for i in range(len(self.job.slots))
                    ]
                }
            )
        }


def test_mixed_agent_repairs_then_finishes_with_typed_answers_and_real_rubric(mixed):
    job, arguments = mixed
    model, events = MixedModel(job, arguments), []
    result = asyncio.run(
        run_matrix_agent(job, model, lambda name, **data: events.append((name, data)))
    )
    assert result["status"] == "ready_for_teacher_review" and not result["saved"]
    assert model.attempts == 2 and len(model.calls) == 7
    questions = result["proposal"]["questions"]
    assert [q["type"] for q in questions] == ["mcq", "truefalse", "short", "essay"]
    assert [q["answer"] for q in questions] == [2, [True, False, True, False], "Mai", None]
    assert sum(q["pointsQ4"] for q in questions) == 40
    assert questions[3]["rubric"] == arguments["questions"][3]["rubric"]
    reports = [data for name, data in events if name == "candidate_check"]
    assert not reports[0]["ok"] and reports[-1]["ok"]
    schema = model.calls[0][1]["tools"][0]["function"]["parameters"]
    assert "RubricStep" in schema["$defs"]


@pytest.mark.parametrize(
    "bad_verdict,bad_essay,code",
    [(True, False, "answer_verdict_disagreement"), (False, True, "explanation_disagreement")],
)
def test_mixed_rejects_wrong_truth_table_or_essay_solution(mixed, bad_verdict, bad_essay, code):
    job, arguments = mixed
    model = MixedModel(job, arguments, fail_verdict=bad_verdict, fail_essay=bad_essay)
    _, report = asyncio.run(inspect_candidate(job, arguments, model, lambda *_args, **_kw: None))
    assert not report["ok"] and code in {e["code"] for e in report["errors"]}


def test_mixed_rubric_cannot_borrow_points_from_another_question(mixed):
    job, arguments = mixed
    arguments["questions"][3]["rubric"][0]["pointsQ4"] = 9
    with pytest.raises(AIError, match="Câu 4: tổng barem là 9, cần 10 đơn vị"):
        candidate_proposal(job, arguments)


@pytest.mark.parametrize(
    "kind,value",
    [
        ("mcq", "A"),
        ("truefalse", "101"),
        ("truefalse", "abcd"),
        ("short", ""),
        ("essay", "Một đáp án"),
    ],
)
def test_mixed_rejects_bad_answer_transport(kind, value):
    with pytest.raises(AIError):
        decode_answer(kind, value)


@pytest.mark.parametrize("variant", ["paired", "old", "numeric"])
def test_local_adapter_uses_option_text_without_changing_canonical_answers(mixed, variant):
    job, args = mixed
    model = MixedModel(job, args)

    async def local_response(purpose, body):
        response = await model(purpose, body)
        if purpose == "agent":
            for message in body["messages"]:
                for tool in message.get("tool_calls", []):
                    old = tool["function"]["arguments"]["questions"][1]
                    if variant == "paired":
                        assert "options" not in old and "answer" not in old
                        assert [s["isTrue"] for s in old["statements"]] == [
                            True,
                            False,
                            True,
                            False,
                        ]
            arguments = response["tool_calls"][0]["function"]["arguments"]
            if variant != "old" and "questions" in arguments:
                question = arguments["questions"][1]
                question["statements"] = [
                    {"text": text, "isTrue": bit == "1"}
                    for text, bit in zip(
                        question.pop("options"), question.pop("answer"), strict=True
                    )
                ]
                if variant == "numeric":
                    question["statements"][0]["isTrue"] = 1
        elif purpose == "blind_content_check":
            content = json.loads(response["content"])
            review = content["reviews"][0]
            review["answer"] = args["questions"][0]["options"][int(review["answer"])]
            response["content"] = json.dumps(content)
        return response

    result = asyncio.run(
        run_matrix_agent(
            job,
            lambda purpose, body: local_model_call(local_response, purpose, body),
            lambda *_a, **_kw: None,
        )
    )
    if variant != "paired":
        assert result["status"] == "attempt_limit"
        assert result["report"]["errors"][0]["code"] == "invalid_result"
        return
    assert result["status"] == "ready_for_teacher_review"
    assert result["proposal"]["questions"][0]["answer"] == 2
    assert result["proposal"]["questions"][1]["options"] == list(args["questions"][1]["options"])
    assert result["proposal"]["questions"][1]["answer"] == [True, False, True, False]
    items = model.calls[0][1]["tools"][0]["function"]["parameters"]["properties"]["questions"][
        "items"
    ]
    assert len(items) == len(job.slots)
    assert all(items[i]["properties"]["answer"]["type"] == "string" for i in (0, 2, 3))
    assert "answer" not in items[1]["properties"]
    blind = next(request for purpose, request in model.calls if purpose == "blind_content_check")
    review_items = blind["format"]["properties"]["reviews"]["items"]
    assert [item["properties"]["ordinal"]["const"] for item in review_items] == list(range(4))
    assert [item["properties"]["optionVerdicts"]["maxItems"] for item in review_items] == [
        4,
        4,
        0,
        0,
    ]
    assert review_items[0]["properties"]["answer"]["enum"] == [*args["questions"][0]["options"], ""]
    assert len(review_items[1]["properties"]["answer"]["enum"]) == 17
    assert review_items[3]["properties"]["answer"] == {"const": ""}
    assert review_items[0]["properties"]["duplicateWith"]["maxItems"] == 0
    assert review_items[2]["properties"]["duplicateWith"]["items"]["enum"] == [0, 1]
