import asyncio
import copy
import json

import pytest

from mach_backend.ai_contract import AIError
from mach_backend.matrix_agent import ContentReviews, MixedContentReviews, sha256_json
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


def mixed_tool_body():
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
    return body


def test_local_mixed_schema_fixes_type_by_approved_slot():
    body = mixed_tool_body()
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
        assert "answer" not in items[2]
        assert items[2]["statements"]["items"]["required"] == ["text", "isTrue"]
        assert items[2]["statements"]["items"]["properties"]["isTrue"]["type"] == "boolean"
        assert "matrix.slots[4].topic" in items[4]["stem"]["description"]
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


@pytest.mark.parametrize("mode", ["scoped", "malformed", "unscoped", "history", "repeat"])
def test_local_mixed_repair_retains_other_questions_and_limits_wire_schema(mode):
    body = mixed_tool_body()
    previous = [{"stem": f"Câu {i}?"} for i in range(5)]
    previous[2].update(options=["a", "b", "c", "d"], answer="1011")
    feedback = {"ok": False, "errors": [{"ordinal": 2, "code": "level_disagreement"}]}
    if mode == "unscoped":
        feedback["errors"].append({"code": "invalid_result"})
    if mode in {"history", "repeat"}:
        feedback["errors"][0]["code"] = "duplicate_question"
    body["messages"] += [
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "check_exam", "arguments": {"questions": previous}}}
            ],
        },
        {"role": "tool", "tool_name": "check_exam", "content": json.dumps(feedback)},
    ]
    if mode in {"history", "repeat"}:
        initial = copy.deepcopy(previous)
        initial[2]["stem"] = "Cách hỏi đã bị báo sai mức."
        old_report = {
            "ok": False,
            "errors": [
                {"ordinal": 2, "code": "level_disagreement", "requiredTask": "Nối hai dữ kiện."},
                {"ordinal": 3, "code": "level_disagreement", "requiredTask": "Mức của câu khác."},
            ],
        }
        if mode == "repeat":
            old_report["errors"][0]["code"] = "duplicate_question"
        body["messages"][2:2] = [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "check_exam", "arguments": {"questions": initial}}}
                ],
            },
            {"role": "tool", "tool_name": "check_exam", "content": json.dumps(old_report)},
        ]
    repaired = {
        "stem": "Hãy xét lại từng mệnh đề.",
        "statements": [
            {"text": text, "isTrue": label}
            for text, label in zip("abcd", [False, True, False, True], strict=True)
        ],
    }

    async def model(purpose, request):
        transport = structured_tool_request(request)
        assignment = json.loads(transport["messages"][1]["content"])
        questions = transport["format"]["oneOf"][0]["properties"]["arguments"]["properties"][
            "questions"
        ]
        if mode == "unscoped":
            assert "repairOrdinals" not in assignment
            assert len(questions["items"]) == len(previous)
            return {}
        assert assignment["repairOrdinals"] == [2]
        original_slots = json.loads(body["messages"][1]["content"])["matrix"]["slots"]
        assert assignment["matrix"]["slots"] == [{**original_slots[2], "ordinal": 2}]
        if mode in {"history", "repeat"}:
            assert "previousStems" not in assignment
            assert assignment["repairStemsHash"] == sha256_json([row["stem"] for row in previous])
            assert assignment["earlierRejected"] == [
                {
                    "ordinal": 2,
                    "code": "duplicate_question" if mode == "repeat" else "level_disagreement",
                }
            ]
            assert not any(row["stem"] in transport["messages"][1]["content"] for row in previous)
            assert "Cách hỏi đã bị báo sai mức." not in transport["messages"][1]["content"]
            assert transport["options"] == {"temperature": 0.45}
        else:
            assert assignment["previousStems"] == [row["stem"] for row in previous]
            assert "earlierRejected" not in assignment and "repairStemsHash" not in assignment
            assert "options" not in transport
        assert len(transport["messages"]) == 3
        assert json.loads(transport["messages"][-1]["content"])["result"] == feedback
        assert questions["minItems"] == questions["maxItems"] == len(questions["items"]) == 1
        assert "matrix.slots[0].topic" in questions["items"][0]["properties"]["stem"]["description"]
        replacements = [repaired, repaired] if mode == "malformed" else [copy.deepcopy(repaired)]
        return {
            "tool_calls": [
                {"function": {"name": "check_exam", "arguments": {"questions": replacements}}}
            ]
        }

    before = copy.deepcopy(body)
    response = asyncio.run(local_model_call(model, "agent", body))
    assert body == before
    if mode == "unscoped":
        assert response == {}
    else:
        arguments = response["tool_calls"][0]["function"]["arguments"]
        if mode == "malformed":
            assert arguments == {}
        else:
            assert arguments["questions"] == [
                *previous[:2],
                {"stem": repaired["stem"], "options": list("abcd"), "answer": "0101"},
                *previous[3:],
            ]


@pytest.mark.parametrize("mode", ["valid", "old_stem", "malformed", "corrected", "copies_source"])
def test_repeated_level_error_plans_one_stem_before_scoped_generation(mode):
    body = mixed_tool_body()
    assignment = json.loads(body["messages"][1]["content"])
    assignment["matrix"].update(subject="Toán", grade="5", instructions="")
    assignment["source"] = [
        {"id": 0, "text": "Kệ có 24 sách truyện và 16 sách khoa học."},
        {"id": 1, "text": "Buổi sáng mở cửa lúc 8 giờ."},
        {"id": 2, "text": "Ngày đọc sách là thứ sáu."},
    ]
    body["messages"][1]["content"] = json.dumps(assignment)
    chosen = "Hai nhóm sách cộng lại có bao nhiêu cuốn?"
    wrong_comparison = "Số sách khoa học nhiều hơn số sách truyện bao nhiêu cuốn?"
    corrected = "Số sách truyện nhiều hơn số sách khoa học bao nhiêu cuốn?"
    previous = [{"stem": f"Câu {i}?"} for i in range(5)]
    previous[1]["evidenceIds"] = [0]
    feedback = {"ok": False, "errors": [{"ordinal": 1, "code": "level_disagreement"}]}
    submission = {
        "role": "assistant",
        "tool_calls": [{"function": {"name": "check_exam", "arguments": {"questions": previous}}}],
    }
    report = {"role": "tool", "tool_name": "check_exam", "content": json.dumps(feedback)}
    body["messages"].extend([submission, report, submission, report])
    seen = []

    async def model(purpose, request):
        seen.append(purpose)
        data = json.loads(request["messages"][1]["content"])
        if purpose == "repair_stem":
            assert data["source"] == assignment["source"][:1]
            assert data["target"]["topic"] == assignment["matrix"]["slots"][1]["topic"]
            assert "matrix" not in data and "options" not in data and "answer" not in data
            assert data["avoid"] == [row["stem"] for row in previous]
            stem = {
                "old_stem": " CÂU 1? ",
                "corrected": wrong_comparison,
                "copies_source": " ".join(row["text"] for row in assignment["source"])
                + " "
                + chosen,
            }.get(mode, chosen)
            content = json.dumps({"stem": stem})
            return {"content": "{" if mode == "malformed" else content}
        assert data["repairOrdinals"] == [1]
        assert data["matrix"]["slots"] == [{**assignment["matrix"]["slots"][1], "ordinal": 1}]
        stem_schema = request["tools"][0]["function"]["parameters"]["properties"]["questions"][
            "items"
        ][0]["properties"]["stem"]
        assert "const" not in stem_schema
        if mode in {"valid", "corrected"}:
            assert data["suggestedStem"] == (wrong_comparison if mode == "corrected" else chosen)
        else:
            assert "suggestedStem" not in data
        change = {"stem": corrected if mode == "corrected" else chosen}
        return {
            "tool_calls": [
                {"function": {"name": "check_exam", "arguments": {"questions": [change]}}}
            ]
        }

    result = asyncio.run(local_model_call(model, "agent", body))
    args = result["tool_calls"][0]["function"]["arguments"]
    assert seen == ["repair_stem", "agent"]
    expected = corrected if mode == "corrected" else chosen
    assert args["questions"] == [previous[0], {"stem": expected}, *previous[2:]]


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


@pytest.mark.parametrize(
    "bad_stem",
    [
        "Thư viện có bao nhiêu quyển sách \u0628?",
        " CÂU 1!! ",
        "Tổng số sách 汉字 là bao nhiêu?",
    ],
)
def test_propose_repair_stem_rejects_disallowed_scripts_and_punct_duplicates(bad_stem):
    body = mixed_tool_body()
    assignment = json.loads(body["messages"][1]["content"])
    assignment["matrix"].update(subject="Toán", grade="5", instructions="")
    assignment["source"] = [{"id": 0, "text": "Kệ có 24 và 16 cuốn sách."}]
    body["messages"][1]["content"] = json.dumps(assignment)
    previous = [{"stem": f"Câu {i}?"} for i in range(5)]
    feedback = {"ok": False, "errors": [{"ordinal": 1, "code": "level_disagreement"}]}
    submission = {
        "role": "assistant",
        "tool_calls": [{"function": {"name": "check_exam", "arguments": {"questions": previous}}}],
    }
    report = {"role": "tool", "tool_name": "check_exam", "content": json.dumps(feedback)}
    body["messages"].extend([submission, report, submission, report])

    async def model(purpose, request):
        if purpose == "repair_stem":
            return {"content": json.dumps({"stem": bad_stem}, ensure_ascii=False)}
        data = json.loads(request["messages"][1]["content"])
        assert "suggestedStem" not in data
        stem_schema = request["tools"][0]["function"]["parameters"]["properties"]["questions"][
            "items"
        ][0]["properties"]["stem"]
        assert "const" not in stem_schema
        return {
            "tool_calls": [
                {
                    "function": {
                        "name": "check_exam",
                        "arguments": {"questions": [{"stem": "Câu sửa hợp lệ?"}]},
                    }
                }
            ]
        }

    result = asyncio.run(local_model_call(model, "agent", body))
    assert result["tool_calls"][0]["function"]["arguments"]["questions"][1] == {
        "stem": "Câu sửa hợp lệ?"
    }


def test_local_reviewer_merges_prior_questions_from_cached_subset():
    body = {
        "format": ContentReviews.model_json_schema(),
        "messages": [
            {"role": "system", "content": "Giải độc lập"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "sources": [],
                        "priorQuestions": [
                            {
                                "ordinal": 0,
                                "stem": "Một?",
                                "options": [{"index": 0, "text": "a"}, {"index": 1, "text": "b"}],
                            }
                        ],
                        "questions": [
                            {
                                "ordinal": 1,
                                "stem": "Hai?",
                                "options": [{"index": 0, "text": "c"}, {"index": 1, "text": "d"}],
                            }
                        ],
                    }
                ),
            },
        ],
    }

    async def model(_purpose, request):
        payload = json.loads(request["messages"][1]["content"])
        assert [q["ordinal"] for q in payload["questions"]] == [1]
        assert [q["ordinal"] for q in payload["priorQuestions"]] == [0]
        return {
            "content": json.dumps(
                {
                    "reviews": [
                        {
                            "ordinal": 1,
                            "answer": "B",
                            "observedLevel": "nhan_biet",
                            "optionVerdicts": ["incorrect", "correct", "incorrect", "incorrect"],
                        }
                    ]
                }
            )
        }

    result = asyncio.run(local_model_call(model, "blind_content_check", body))
    assert [r["ordinal"] for r in json.loads(result["content"])["reviews"]] == [1]


def test_propose_repair_stem_normalizes_question_marks_and_blocks_tail_extension():
    from mach_backend.workspace_agent import propose_repair_stem

    excluded_stem = (
        "Thư viện trường có 24 sách truyện và 16 sách khoa học. "
        "Số sách khoa học nhiều hơn số sách truyện bao nhiêu quyển?"
    )
    assignment = {
        "matrix": {
            "subject": "Toán",
            "grade": "5",
            "instructions": "Mức Thông hiểu",
            "slots": [
                {
                    "type": "mcq",
                    "topic": "Thư viện",
                    "level": 0,
                    "pointsQ4": 4,
                    "levelName": "Nhận biết",
                    "requiredTask": "Tìm chi tiết.",
                },
                {
                    "type": "mcq",
                    "topic": "Thư viện",
                    "level": 1,
                    "pointsQ4": 8,
                    "levelName": "Thông hiểu",
                    "requiredTask": "Nối dữ kiện.",
                },
            ],
        },
        "source": [{"id": 0, "text": "Thư viện trường có 24 sách truyện và 16 sách khoa học."}],
        "previousStems": [excluded_stem],
        "earlierRejected": [{"ordinal": 1, "code": "level_disagreement", "stem": excluded_stem}],
    }
    body = {
        "messages": [
            {"role": "user", "content": json.dumps({"errors": [{"code": "level_disagreement"}]})}
        ]
    }
    previous = [{}, {"evidenceIds": [0]}]

    async def run(proposed):
        async def model(_purpose, _request):
            return {"content": json.dumps({"stem": proposed}, ensure_ascii=False)}

        return await propose_repair_stem(model, body, assignment, [1], previous)

    assert (
        asyncio.run(run("Số sách truyện nhiều hơn số sách khoa học bao nhiêu quyển\u061f"))
        == "Số sách truyện nhiều hơn số sách khoa học bao nhiêu quyển?"
    )
    assert asyncio.run(run(excluded_stem + " (trả lời bằng số tự nhiên).")) is None
