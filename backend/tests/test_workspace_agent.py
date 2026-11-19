import asyncio
import copy
import json

import pytest

from mach_backend.ai_contract import AIError
from mach_backend.matrix_agent import ContentReviews, MixedContentReviews
from mach_backend.mixed_questions import MixedDraftBatch, MixedDraftQuestion
from mach_backend.poc_matrix import structured_tool_request
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


def test_local_mixed_schema_fixes_type_by_approved_slot():
    kinds = ["mcq", "mcq", "truefalse", "short", "essay"]
    schema = MixedDraftBatch.model_json_schema()
    schema["properties"]["questions"]["items"] = {
        k: v for k, v in MixedDraftQuestion.model_json_schema().items() if k != "$defs"
    }
    body = {
        "messages": [
            {"role": "system", "content": "Soạn bộ câu."},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "matrix": {
                            "slots": [
                                {
                                    "type": kind,
                                    "pointsQ4": points,
                                    "topic": f"Chủ đề {i}",
                                    "levelName": "Thông hiểu",
                                    "requiredTask": "Nối dữ kiện.",
                                }
                                for i, (kind, points) in enumerate(
                                    zip(kinds, [8, 8, 8, 1, 12], strict=True), 1
                                )
                            ]
                        }
                    }
                ),
            },
        ],
        "tools": [{"function": {"name": "check_exam", "parameters": schema}}],
    }
    before = copy.deepcopy(body)

    async def model(purpose, request):
        transport = structured_tool_request(request)
        assert transport["messages"][1]["content"] == before["messages"][1]["content"]
        assert "Chủ đề 3" not in transport["messages"][0]["content"]
        wire = transport["format"]
        assert "RubricStep" in wire["$defs"]
        args = wire["oneOf"][0]["properties"]["arguments"]
        items = [item["properties"] for item in args["properties"]["questions"]["items"]]
        fields = ["options", "options", "statements", "options", "options"]
        assert [i[f]["minItems"] for i, f in zip(items, fields, strict=True)] == [4, 4, 4, 0, 0]
        assert [i[f]["maxItems"] for i, f in zip(items, fields, strict=True)] == [4, 4, 4, 0, 0]
        assert "options" not in items[2]
        assert "statements" in args["properties"]["questions"]["items"][2]["required"]
        assert items[0]["answer"]["enum"] == items[1]["answer"]["enum"] == list("0123")
        assert "matrix.slots[2].topic" in items[2]["stem"]["description"]
        assert "Thông hiểu: Nối dữ kiện." in items[2]["stem"]["description"]
        assert "Chủ đề 3" not in items[2]["stem"]["description"]
        assert "Bốn mệnh đề" in items[2]["statements"]["description"]
        assert "đúng thứ tự" in items[2]["answer"]["description"]
        assert "matrix.slots[4].topic" in items[4]["stem"]["description"]
        assert len(items[2]["answer"]["enum"]) == 16 and "1010" in items[2]["answer"]["enum"]
        assert items[3]["answer"]["minLength"] == 1
        assert items[4]["answer"]["const"] == ""
        assert items[0]["rubric"]["$ref"] == items[2]["rubric"]["$ref"] == "#/$defs/RubricQ4_8"
        single, multiple = wire["$defs"]["RubricQ4_8"]["oneOf"]
        assert single["items"][0]["properties"]["pointsQ4"] == {"const": 8}
        assert multiple["minItems"] == 2 and multiple["maxItems"] == 8
        assert multiple["items"]["properties"]["pointsQ4"]["maximum"] == 7
        assert wire["$defs"]["RubricQ4_1"]["items"][0]["properties"]["pointsQ4"] == {"const": 1}
        return {}

    asyncio.run(local_model_call(model, "agent", body))
    assert body == before


@pytest.mark.parametrize("answer", ["40", "3"])
def test_mixed_reviewer_maps_answer_content_and_keeps_verdicts(answer):
    values = ["24", "16", "40", "30"]
    verdicts = ["incorrect", "incorrect", "incorrect", "correct"]
    body = {
        "format": MixedContentReviews.model_json_schema(),
        "messages": [
            {"role": "system", "content": "mcq dùng '0'/'1'/'2'/'3'"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "questions": [
                            {
                                "type": "mcq",
                                "ordinal": 0,
                                "options": [{"index": i, "text": v} for i, v in enumerate(values)],
                            }
                        ]
                    }
                ),
            },
        ],
    }

    async def model(_purpose, request):
        schema = request["format"]["properties"]["reviews"]["items"][0]
        assert schema["properties"]["answer"]["enum"] == [*values, ""]
        assert "'0'/'1'" not in request["messages"][0]["content"]
        return {
            "content": json.dumps(
                {"reviews": [{"ordinal": 0, "answer": answer, "optionVerdicts": verdicts}]}
            )
        }

    if answer == "3":
        with pytest.raises(AIError, match="nguyên văn phương án"):
            asyncio.run(local_model_call(model, "blind_content_check", body))
    else:
        response = asyncio.run(local_model_call(model, "blind_content_check", body))
        assert json.loads(response["content"])["reviews"] == [
            {"ordinal": 0, "answer": "2", "optionVerdicts": verdicts}
        ]


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
