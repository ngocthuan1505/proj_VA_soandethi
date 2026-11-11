import asyncio
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import CheckJob, GenerateJob
from mach_backend.ai_service import OLLAMA_CHAT, OllamaProvider, check_question, propose_exam

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/ai-sinh-kiem.json").read_text(
        encoding="utf-8"
    )
)
IDENTITY = {
    "jobId": "658ec201-abf5-4b78-8c20-4c2ba53e6d6a",
    "examId": "4058563a-d831-4a63-b787-d464a05c5682",
    "baseRevision": 4,
}
QUESTION_IDENTITY = {"questionId": "5907b3d3-6402-40ba-9b6e-5e0faf6d46a3", "questionVersion": 2}
EVIDENCE = {
    "sourceId": FIXTURE["sourceId"],
    "sourceVersion": FIXTURE["sourceVersion"],
    "locator": {"kind": "page", "index": 1, "regionId": None},
    "quote": FIXTURE["quote"],
}
OWNER = "chu-de-mau"


def job_fields():
    source = {key: value for key, value in EVIDENCE.items() if key != "quote"}
    return {
        **IDENTITY,
        "ownerId": OWNER,
        "requireEvidence": True,
        "sources": [{**source, "ownerId": OWNER, "text": FIXTURE["sourceText"]}],
    }


@pytest.fixture
def generation():
    questions = FIXTURE["questions"]
    job = GenerateJob.model_validate_json(
        json.dumps(
            {
                **job_fields(),
                "subject": "Toán",
                "grade": "6",
                "slots": [
                    {field: item[field] for field in ("type", "topic", "level", "pointsQ4")}
                    for item in questions
                ],
            }
        )
    )
    return job, {
        **IDENTITY,
        "questions": [{**item, "evidence": [EVIDENCE]} for item in questions],
    }


@pytest.fixture
def check():
    first = FIXTURE["questions"][0]
    job = CheckJob.model_validate_json(
        json.dumps(
            {
                **job_fields(),
                "question": {
                    **QUESTION_IDENTITY,
                    **{key: first[key] for key in ("stem", "type", "options")},
                },
            }
        )
    )
    return job, {
        **IDENTITY,
        **QUESTION_IDENTITY,
        "answer": first["answer"],
        "explanation": first["explanation"],
        "uncertain": False,
        "evidence": [EVIDENCE],
    }


async def current(_job):
    return True


def ollama_fixture(result, request_checks):
    def respond(request):
        assert str(request.url) == OLLAMA_CHAT
        assert request.method == "POST"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert "tools" not in payload
        assert payload["messages"][0]["role"] == "system"
        data = json.loads(payload["messages"][1]["content"])
        assert "ownerId" not in data and "ownerId" not in data["sources"][0]
        request_checks(data, payload["format"]["properties"])
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(result)},
            },
        )

    return OllamaProvider("mo-hinh-fixture", transport=httpx.MockTransport(respond))


def test_generate_four_types_in_approved_order_without_mutating_plan(generation):
    job, result = generation

    def check_payload(data, schema):
        assert data["slots"] == job.model_dump(mode="json")["slots"]
        assert "questions" in schema and "edits" not in schema

    before = job.model_dump()
    provider = ollama_fixture(result, check_payload)
    proposal = asyncio.run(propose_exam(job, provider, current, timeout_seconds=1))
    assert proposal.model_dump(mode="json") == result
    assert job.model_dump() == before
    assert sum(question.pointsQ4 for question in proposal.questions) == 40


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda p: p["questions"].pop(), "invalid_plan"),
        (lambda p: p["questions"].reverse(), "invalid_plan"),
        (lambda p: p["questions"][0].update(level=2), "invalid_plan"),
        (lambda p: p["questions"][0].update(pointsQ4=8), "invalid_plan"),
        (lambda p: p["questions"][0]["rubric"][0].update(pointsQ4=1), "invalid_rubric"),
        (lambda p: p["questions"][0].update(answer=True), "invalid_result"),
        (lambda p: p["questions"][1].update(answer=2), "invalid_answer"),
        (lambda p: p["questions"][2].update(answer=" "), "invalid_answer"),
        (lambda p: p["questions"][3].update(answer=0), "invalid_answer"),
        (lambda p: p["questions"][0].update(options=["a", " a ", "c", "d"]), "invalid_options"),
        (lambda p: p["questions"][0].update(stem="Thiếu dấu $x+1."), "invalid_math"),
        (lambda p: p["questions"][0].update(evidence=[]), "missing_evidence"),
        (
            lambda p: p["questions"][0]["evidence"][0].update(quote="Nguồn tự chế"),
            "invalid_evidence",
        ),
    ],
)
def test_generate_rejects_drift_and_invalid_provider_result(generation, mutation, code):
    job, result = generation
    result = deepcopy(result)
    mutation(result)

    async def provider(_job):
        return json.dumps(result)

    with pytest.raises(AIError) as error:
        asyncio.run(propose_exam(job, provider, current, timeout_seconds=1))
    assert error.value.code == code


def test_invalid_plan_is_rejected_before_calling_provider(generation):
    job, _ = generation

    async def provider(_job):
        pytest.fail("Không gửi ma trận sai tổng điểm tới provider.")

    with pytest.raises(AIError) as error:
        asyncio.run(
            propose_exam(
                job.model_copy(update={"slots": job.slots[:1]}),
                provider,
                current,
                timeout_seconds=1,
            )
        )
    assert error.value.code == "invalid_plan"


@pytest.mark.parametrize(("saved_answer", "comparison"), [(2, "agrees"), (1, "disagrees")])
def test_check_is_blind_and_compares_after_result(check, saved_answer, comparison):
    job, result = check

    def check_payload(data, schema):
        assert data["question"] == job.question.model_dump(mode="json")
        assert set(data["question"]) == {"questionId", "questionVersion", "type", "stem", "options"}
        assert "saved_answer" not in data
        assert "comparison" not in schema

    report = asyncio.run(
        check_question(
            job,
            ollama_fixture(result, check_payload),
            current,
            saved_answer=saved_answer,
            timeout_seconds=1,
        )
    )
    assert report.answer == 2
    assert report.comparison == comparison


def test_insufficient_evidence_requires_review(check):
    job, result = check

    async def provider(_job):
        return json.dumps({**result, "uncertain": True, "answer": None, "evidence": []})

    report = asyncio.run(check_question(job, provider, current, saved_answer=2, timeout_seconds=1))
    assert report.comparison == "needs_review"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"questionVersion": 1}, "wrong_job"),
        ({"questionId": IDENTITY["examId"]}, "wrong_job"),
        ({"comparison": "agrees"}, "invalid_result"),
        ({"evidence": []}, "missing_evidence"),
    ],
)
def test_check_rejects_wrong_question_or_claims_without_evidence(check, change, code):
    job, result = check

    async def provider(_job):
        return json.dumps({**result, **change})

    with pytest.raises(AIError) as error:
        asyncio.run(check_question(job, provider, current, saved_answer=2, timeout_seconds=1))
    assert error.value.code == code


def test_check_discards_answer_after_question_changes(check):
    job, result = check
    snapshots = iter([True, False])

    async def read(_job):
        return next(snapshots)

    async def provider(_job):
        return json.dumps(result)

    with pytest.raises(AIError) as error:
        asyncio.run(check_question(job, provider, read, saved_answer=2, timeout_seconds=1))
    assert error.value.code == "stale_snapshot"


def test_smoke_sinh_de(generation, run_smoke):
    job, fixture = generation
    slot = job.slots[0].model_copy(update={"pointsQ4": 40})
    job = job.model_copy(
        update={
            "slots": (slot,),
            "instructions": "Sinh một câu trắc nghiệm tính x + 1 khi x = 2 theo nguồn đã chọn.",
        }
    )
    expected = {
        **fixture["questions"][0],
        "pointsQ4": 40,
        "rubric": [{"text": "Tính đúng giá trị biểu thức.", "pointsQ4": 40}],
    }

    async def call(provider, timeout):
        return await propose_exam(job, provider, current, timeout_seconds=timeout)

    result = run_smoke(call, {**fixture, "questions": [expected]})
    assert len(result.questions) == 1
    assert result.questions[0].pointsQ4 == 40
    assert result.questions[0].evidence


def test_smoke_kiem_dap_an(check, run_smoke):
    job, fixture = check

    async def call(provider, timeout):
        return await check_question(
            job, provider, current, saved_answer=fixture["answer"], timeout_seconds=timeout
        )

    result = run_smoke(call, fixture)
    assert result.comparison == "agrees"
    assert result.evidence
