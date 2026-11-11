"""Kiểm quyền, đọc snapshot và giải độc lập từ HTTP với SQLite tạm."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from pydantic import TypeAdapter
from test_patch_confirmation import HEADERS, OTHER, OWNER, SQLiteFixture

from mach_backend.ai_contract import Locator, SourceFragment
from mach_backend.ai_questions import Answer, BlindQuestion, CheckJob
from mach_backend.ai_service import OLLAMA_CHAT, OllamaProvider
from mach_backend.check_routes import CheckInputs, build_check_router

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[2] / "tests/fixtures/ai-sinh-kiem.json").read_text(
        encoding="utf-8"
    )
)


class CheckSQLiteFixture(SQLiteFixture):
    async def read_check(self, owner, exam_id, question_id, keys):
        inputs = await self.read_inputs(owner, exam_id, keys)
        if inputs is None:
            return None
        questions = [q for q in inputs.exam["questions"] if q["id"] == str(question_id)]
        if len(questions) != 1:
            return None
        row = questions[0]
        question = BlindQuestion.model_validate_json(
            json.dumps(
                {
                    "questionId": row["id"],
                    "questionVersion": row["v"],
                    **{key: row[key] for key in ("type", "stem", "options")},
                }
            )
        )
        return CheckInputs(
            owner_id=owner,
            exam_id=UUID(inputs.exam["id"]),
            base_revision=inputs.exam["revision"],
            question=question,
            saved_answer=TypeAdapter(Answer).validate_json(json.dumps(row["answer"])),
            sources=inputs.sources,
        )


@pytest.fixture
def sample(tmp_path):
    q = FIXTURE["questions"][0]
    job = CheckJob(
        jobId=uuid4(),
        examId=uuid4(),
        baseRevision=4,
        ownerId=OWNER,
        question=BlindQuestion(
            questionId=uuid4(),
            questionVersion=2,
            type=q["type"],
            stem=q["stem"],
            options=tuple(q["options"]),
        ),
        sources=(
            SourceFragment(
                ownerId=OWNER,
                sourceId=UUID(FIXTURE["sourceId"]),
                sourceVersion=3,
                locator=Locator(kind="page", index=1),
                text=FIXTURE["sourceText"],
            ),
        ),
        requireEvidence=True,
    )
    stored = {
        "id": str(job.examId),
        "revision": 4,
        "questions": [
            {
                **q,
                "id": str(job.question.questionId),
                "v": 2,
                "answer": 1,
                "explanation": "LỜI_GIẢI_ĐÃ_LƯU_KHÔNG_GỬI_MODEL",
            }
        ],
    }
    body = {
        "baseRevision": 4,
        "questionVersion": 2,
        "consent": True,
        "sources": [
            source.model_dump(mode="json", exclude={"ownerId", "text"}) for source in job.sources
        ],
    }
    repo = CheckSQLiteFixture(tmp_path / "check.sqlite")
    repo.seed(job, stored)
    extra = job.sources[0].model_copy(update={"sourceId": uuid4(), "text": "Nguồn chưa được chọn."})
    repo.update_sources(job, (*job.sources, extra))
    return repo, job, body, stored


def check_app(repo, provider, *, read_inputs=None, timeout=1):
    def authenticated_owner(request: Request):
        match request.headers.get("Authorization"):
            case "Bearer owner-fixture":
                return OWNER
            case "Bearer second-fixture":
                return "teacher-2"
            case _:
                raise HTTPException(401)

    app = FastAPI()
    app.include_router(
        build_check_router(
            authenticated_owner,
            read_inputs or repo.read_check,
            provider,
            timeout_seconds=timeout,
            max_active=1,
        )
    )
    return app


def reply_for(job):
    return {
        **job.model_dump(mode="json", include={"jobId", "examId", "baseRevision"}),
        "questionId": str(job.question.questionId),
        "questionVersion": job.question.questionVersion,
        "answer": 2,
        "explanation": FIXTURE["questions"][0]["explanation"],
        "uncertain": False,
        "evidence": [
            {
                "sourceId": FIXTURE["sourceId"],
                "sourceVersion": 3,
                "locator": {"kind": "page", "index": 1},
                "quote": FIXTURE["quote"],
            }
        ],
    }


def path_for(job):
    return f"/api/exams/{job.examId}/questions/{job.question.questionId}/check"


def test_check_reads_saved_answer_separately_and_does_not_write(sample):
    repo, job, body, stored = sample
    requests = []

    def reply(request):
        assert str(request.url) == OLLAMA_CHAT
        messages = json.loads(request.content)["messages"]
        assert "LỜI_GIẢI_ĐÃ_LƯU_KHÔNG_GỬI_MODEL" not in messages[1]["content"]
        payload = json.loads(messages[1]["content"])
        assert payload["question"] == job.question.model_dump(mode="json")
        assert payload["sources"] == [job.sources[0].model_dump(mode="json", exclude={"ownerId"})]
        assert "answer" not in payload["question"] and "ownerId" not in payload
        requests.append(payload)
        data = reply_for(job)
        data["jobId"] = payload["jobId"]
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": json.dumps(data)}}
        )

    async def run():
        provider = OllamaProvider("fixture", transport=httpx.MockTransport(reply))
        transport = httpx.ASGITransport(app=check_app(repo, provider))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["comparison"] == "disagrees"
            assert response.json()["answer"] == 2
        assert len(requests) == 1
        assert repo.snapshot(job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    ("case", "status"),
    [
        ("anonymous", 401),
        ("other_owner", 404),
        ("other_exam", 404),
        ("other_question", 404),
        ("no_consent", 403),
        ("old_exam", 409),
        ("old_question", 409),
        ("old_source", 409),
        ("foreign_source", 404),
        ("duplicate_source", 422),
        ("bad_locator", 422),
        ("forged_answer", 422),
        ("forged_text", 422),
    ],
)
def test_check_refuses_invalid_input_before_calling_provider(sample, case, status):
    repo, job, body, stored = sample
    path = path_for(job)
    headers = HEADERS
    match case:
        case "anonymous":
            headers = {}
        case "other_owner":
            headers = OTHER
        case "other_exam":
            path = path.replace(str(job.examId), str(uuid4()))
        case "other_question":
            path = path.replace(str(job.question.questionId), str(uuid4()))
        case "no_consent":
            del body["consent"]
        case "old_exam":
            body["baseRevision"] -= 1
        case "old_question":
            body["questionVersion"] -= 1
        case "old_source":
            body["sources"][0]["sourceVersion"] -= 1
        case "foreign_source":
            repo.update_sources(job, (job.sources[0].model_copy(update={"ownerId": "teacher-2"}),))
        case "duplicate_source":
            body["sources"] *= 2
        case "bad_locator":
            body["sources"][0]["locator"]["kind"] = "region"
        case "forged_answer":
            body["answer"] = 2
        case "forged_text":
            body["sources"][0]["text"] = "Nguồn do trình duyệt ghi đè."

    async def provider(_job):
        pytest.fail("Đầu vào không hợp lệ không được gọi provider.")

    async def run():
        transport = httpx.ASGITransport(app=check_app(repo, provider))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path, headers=headers, json=body)
            assert response.status_code == status, response.text
        assert repo.snapshot(job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "change", ["revision", "question_version", "stem", "answer", "source", "source_text"]
)
def test_check_rejects_change_while_provider_is_solving(sample, change):
    repo, job, body, stored = sample

    async def provider(current):
        if change.startswith("source"):
            values = {"sourceVersion": 4} if change == "source" else {"text": "Đoạn nguồn mới."}
            repo.update_sources(job, (job.sources[0].model_copy(update=values),))
        else:
            exam, _ = repo.snapshot(job)
            match change:
                case "revision":
                    exam["revision"] += 1
                case "question_version":
                    exam["questions"][0]["v"] += 1
                case "stem":
                    exam["questions"][0]["stem"] = "Dữ kiện mới."
                case "answer":
                    exam["questions"][0]["answer"] = 2
            repo.update_exam(job, exam)
        return json.dumps(reply_for(current))

    async def run():
        transport = httpx.ASGITransport(app=check_app(repo, provider))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "stale_snapshot"
        assert repo.history_count() == 0
        if change.startswith("source"):
            assert repo.snapshot(job)[0] == stored

    asyncio.run(run())


@pytest.mark.parametrize("cancelled", [False, True])
def test_check_returns_capacity_after_timeout_or_cancel(sample, cancelled):
    repo, job, body, stored = sample

    async def run():
        started = asyncio.Event()
        calls = 0

        async def provider(current):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                await asyncio.Future()
            return json.dumps(reply_for(current))

        transport = httpx.ASGITransport(
            app=check_app(repo, provider, timeout=1 if cancelled else 0.05)
        )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(client.post(path_for(job), headers=HEADERS, json=body))
            await started.wait()
            limited = await client.post(path_for(job), headers=HEADERS, json=body)
            assert limited.status_code == 429
            if cancelled:
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
            else:
                expired = await first
                assert expired.status_code == 504
                assert expired.json()["detail"]["code"] == "timeout"
            next_try = await client.post(path_for(job), headers=HEADERS, json=body)
            assert next_try.status_code == 200, next_try.text
        assert repo.snapshot(job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(asyncio.wait_for(run(), 5))


def test_check_deadline_covers_initial_repository_read(sample):
    repo, job, body, _ = sample

    async def stalled_read(*_args):
        await asyncio.Future()

    async def run():
        transport = httpx.ASGITransport(
            app=check_app(repo, None, read_inputs=stalled_read, timeout=0.02)
        )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == 504

    asyncio.run(asyncio.wait_for(run(), 2))


def test_check_rejects_repository_identity_mismatch(sample):
    repo, job, body, _ = sample

    async def incorrect_read(*args):
        inputs = await repo.read_check(*args)
        return replace(inputs, owner_id="teacher-2")

    async def run():
        transport = httpx.ASGITransport(app=check_app(repo, None, read_inputs=incorrect_read))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == 404

    asyncio.run(run())


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        ("wrong_job", 502, "wrong_job"),
        ("bad_answer", 502, "invalid_answer"),
        ("missing_evidence", 502, "missing_evidence"),
        ("malformed", 502, "invalid_result"),
        ("unconfigured", 503, "provider_unconfigured"),
        ("rate_limit", 429, "rate_limited"),
    ],
)
def test_check_reports_upstream_errors_without_echoing_private_output(
    sample, failure, status, code
):
    repo, job, body, stored = sample

    def reply(request):
        data = reply_for(job)
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        data["jobId"] = payload["jobId"]
        match failure:
            case "wrong_job":
                data["jobId"] = str(uuid4())
            case "bad_answer":
                data["answer"] = "KEY_GIA_LAP_KHONG_TRA_RA_HTTP"
            case "missing_evidence":
                data["evidence"] = []
            case "malformed":
                return httpx.Response(
                    200,
                    json={
                        "done": True,
                        "message": {
                            "role": "assistant",
                            "content": "KEY_GIA_LAP_KHONG_TRA_RA_HTTP",
                        },
                    },
                )
            case "rate_limit":
                return httpx.Response(429, text="KEY_GIA_LAP_KHONG_TRA_RA_HTTP")
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": json.dumps(data)}}
        )

    async def run():
        provider = (
            None
            if failure == "unconfigured"
            else OllamaProvider("fixture", transport=httpx.MockTransport(reply))
        )
        transport = httpx.ASGITransport(app=check_app(repo, provider))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == status, response.text
            assert response.json()["detail"]["code"] == code
            assert "KEY_GIA_LAP_KHONG_TRA_RA_HTTP" not in response.text
        assert repo.snapshot(job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(run())


def test_smoke_kiem_qua_http(sample, smoke_evidence):
    mode, model, _, _, timeout = smoke_evidence
    if mode == "fixture":
        pytest.skip("Chạy khi chọn --smoke-ollama-model.")
    repo, job, body, stored = sample

    async def run():
        transport = httpx.ASGITransport(app=check_app(repo, OllamaProvider(model), timeout=timeout))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(path_for(job), headers=HEADERS, json=body)
            assert response.status_code == 200, response.text
            report = response.json()
            assert report["questionId"] == str(job.question.questionId)
            assert report["questionVersion"] == job.question.questionVersion
            assert report["comparison"] == "disagrees"
            assert report["answer"] == FIXTURE["questions"][0]["answer"]
            assert report["evidence"]
        assert repo.snapshot(job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(asyncio.wait_for(run(), timeout + 5))
