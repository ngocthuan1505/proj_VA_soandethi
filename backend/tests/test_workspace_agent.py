import asyncio
import copy
import json

import pytest

from mach_backend.ai_contract import AIError
from mach_backend.matrix_agent import ContentReviews
from mach_backend.workspace_agent import local_model_call


def test_local_reviewer_receives_one_question_without_saved_answers():
    body = {
        "format": ContentReviews.model_json_schema(),
        "messages": [
            {"role": "system", "content": "Giải độc lập"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "sources": [],
                        "questions": [
                            {
                                "ordinal": 0,
                                "stem": "Một?",
                                "options": [{"index": 0, "text": "a"}, {"index": 1, "text": "b"}],
                            },
                            {
                                "ordinal": 1,
                                "stem": "Hai?",
                                "options": [{"index": 0, "text": "c"}, {"index": 1, "text": "d"}],
                            },
                        ],
                    }
                ),
            },
        ],
    }
    before = copy.deepcopy(body)
    calls = []

    async def model(purpose, request):
        calls.append(request)
        questions = json.loads(request["messages"][1]["content"])["questions"]
        assert len(questions) == 1 and "answer" not in questions[0]
        ordinal = questions[0]["ordinal"]
        prior = json.loads(request["messages"][1]["content"])["priorQuestions"]
        assert [q["ordinal"] for q in prior] == list(range(ordinal))
        assert all("answer" not in q for q in prior)
        assert request["format"]["$defs"]["ContentReview"]["properties"]["ordinal"] == {
            "const": ordinal
        }
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {
                            "ordinal": ordinal,
                            "answer": "B",
                            "observedLevel": "nhan_biet",
                            "optionVerdicts": ["incorrect", "correct", "incorrect", "incorrect"],
                        }
                    ]
                }
            )
        }

    result = asyncio.run(local_model_call(model, "blind_content_check", body))
    assert json.loads(result["content"])["reviews"] == [
        {
            "ordinal": i,
            "answer": 1,
            "observedLevel": 0,
            "optionVerdicts": ["incorrect", "correct", "incorrect", "incorrect"],
        }
        for i in range(2)
    ]
    assert len(calls) == 2 and body == before


def test_split_reviewer_does_not_accept_wrong_ordinal():
    async def model(*_):
        return {"content": '{"reviews":[{"ordinal":99}]}'}

    body = {
        "format": ContentReviews.model_json_schema(),
        "messages": [
            {"role": "system", "content": "Test"},
            {"role": "user", "content": '{"questions":[{"ordinal":0,"options":[]}]}'},
        ],
    }
    with pytest.raises(AIError, match="sai mã câu"):
        asyncio.run(local_model_call(model, "blind_content_check", body))


def test_review_with_multiple_correct_options_is_uncertain():
    async def model(*_):
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {
                            "ordinal": 0,
                            "answer": "A",
                            "observedLevel": "nhan_biet",
                            "uncertain": False,
                            "reason": "Phương án A đúng.",
                            "optionVerdicts": ["correct", "correct", "incorrect", "incorrect"],
                        }
                    ]
                }
            )
        }

    body = {
        "format": ContentReviews.model_json_schema(),
        "messages": [
            {"role": "system", "content": "Test"},
            {"role": "user", "content": '{"questions":[{"ordinal":0,"options":[]}]}'},
        ],
    }
    result = asyncio.run(local_model_call(model, "blind_content_check", body))
    review = json.loads(result["content"])["reviews"][0]
    assert review["uncertain"] is True and review["answer"] is None
    assert "2 phương án" in review["reason"]


def test_generation_translates_letter_without_changing_original_request():
    async def model(purpose, body):
        assert body["tools"][0]["function"]["parameters"]["properties"]["questions"]["items"][
            "properties"
        ]["answer"]["enum"] == list("ABCD")
        return {
            "tool_calls": [
                {"function": {"name": "check_exam", "arguments": {"questions": [{"answer": "C"}]}}}
            ]
        }

    body = {
        "tools": [
            {
                "function": {
                    "name": "check_exam",
                    "parameters": {
                        "properties": {
                            "questions": {"items": {"properties": {"answer": {"type": "integer"}}}}
                        }
                    },
                }
            }
        ],
        "messages": [{"role": "system", "content": "answer là vị trí 0..3"}],
    }
    before = copy.deepcopy(body)
    response = asyncio.run(local_model_call(model, "agent", body))
    assert response["tool_calls"][0]["function"]["arguments"]["questions"][0]["answer"] == 2
    assert body == before
