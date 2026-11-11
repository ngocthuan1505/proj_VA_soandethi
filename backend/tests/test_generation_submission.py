"""Sinh qua HTTP phải dùng ma trận và nguồn đã đọc từ kho theo phiên."""

import asyncio
import json
from dataclasses import replace
from uuid import UUID, uuid4

import httpx
import pytest
from test_generation_confirmation import generated as generated
from test_patch_confirmation import HEADERS, OTHER, fixture_app

from mach_backend.ai_questions import GenerationPlan
from mach_backend.ai_service import OllamaProvider
from mach_backend.patch_jobs import PatchJobRunner


def submission(job):
    return {
        "requestId": str(uuid4()),
        "baseRevision": job.baseRevision,
        "consent": True,
        "plan": job.model_dump(mode="json", include=set(GenerationPlan.model_fields)),
        "sources": [
            fragment.model_dump(mode="json", include={"sourceId", "sourceVersion", "locator"})
            for fragment in job.sources
        ],
    }


def terminal(response):
    assert response.status_code == 200, response.text
    return json.loads(response.text.rsplit("data: ", 1)[1])


def test_generate_http_replays_then_confirms_four_types_from_trusted_inputs(generated):
    repo, job, old, proposal, _ = generated
    body = submission(job)
    source = job.sources[0]
    excluded = source.model_copy(update={"locator": source.locator.model_copy(update={"index": 9})})
    repo.update_sources(job, (source, excluded))

    async def run():
        calls = 0
        started, released = asyncio.Event(), asyncio.Event()

        async def reply(request):
            nonlocal calls
            calls += 1
            payload = json.loads(json.loads(request.content)["messages"][1]["content"])
            assert payload["jobId"] != body["requestId"]
            assert payload["sources"] == [source.model_dump(mode="json", exclude={"ownerId"})]
            assert "ownerId" not in payload
            assert payload["slots"] == body["plan"]["slots"]
            started.set()
            await released.wait()
            return httpx.Response(
                200,
                json={
                    "done": True,
                    "message": {
                        "role": "assistant",
                        "content": proposal.model_copy(
                            update={"jobId": UUID(payload["jobId"])}
                        ).model_dump_json(),
                    },
                },
            )

        runner = PatchJobRunner(
            OllamaProvider("fixture", transport=httpx.MockTransport(reply)),
            repo.current,
            repo.stage,
            timeout_seconds=2,
            max_active=1,
            max_retained=2,
        )
        app = fixture_app(repo, runner)
        collection = f"/api/exams/{job.examId}/proposals"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first, second = await asyncio.gather(
                *[
                    client.post(collection + "/generate", headers=HEADERS, json=body)
                    for _ in range(2)
                ]
            )
            assert first.status_code == second.status_code == 202, first.text
            assert first.json()["jobId"] == second.json()["jobId"]
            base = collection + "/" + first.json()["jobId"]
            await started.wait()
            conflict = await client.post(
                collection + "/generate", headers=HEADERS, json={**body, "baseRevision": 8}
            )
            assert conflict.status_code == 409
            assert conflict.json()["detail"]["code"] == "job_conflict"
            cross_operation = await client.post(
                collection,
                headers=HEADERS,
                json={
                    "requestId": body["requestId"],
                    "baseRevision": 4,
                    "consent": True,
                    "request": "Sửa lời giải.",
                    "targets": [
                        {
                            "questionId": old["questions"][0]["id"],
                            "questionVersion": 8,
                            "blockId": str(uuid4()),
                        }
                    ],
                },
            )
            assert cross_operation.status_code == 409
            assert cross_operation.json()["detail"]["code"] == "job_conflict"
            assert (await client.get(base + "/status", headers=OTHER)).status_code == 404
            assert (await client.get(base + "/status")).status_code == 401
            released.set()
            completed = terminal(
                await client.get(base + "/events", headers={**HEADERS, "Last-Event-ID": "1"})
            )
            assert completed["status"] == "complete", completed["errorCode"]
            assert (
                completed["proposal"]["questions"] == proposal.model_dump(mode="json")["questions"]
            )
            assert repo.snapshot(job)[0] == old
            assert repo.history_count() == 0
            assert (
                await client.get(base + "/events", headers={**HEADERS, "Last-Event-ID": "2"})
            ).text == ""
            saved = await client.post(base + "/confirm", headers=HEADERS, json={"baseRevision": 4})
            assert saved.status_code == 200, saved.text
            assert saved.json()["revision"] == 5
            retry = await client.post(collection + "/generate", headers=HEADERS, json=body)
            assert retry.json() == completed
            assert calls == 1
            assert len(saved.json()["changedQuestionIds"]) == 4
            assert repo.history_count() == 1

    asyncio.run(asyncio.wait_for(run(), timeout=5))


@pytest.mark.parametrize(
    "mutation,status,code",
    [
        ("no_session", 401, None),
        ("other_owner", 404, "exam_not_found"),
        ("no_consent", 403, "consent_required"),
        ("old_revision", 409, "stale_snapshot"),
        ("no_approved_plan", 409, "plan_not_approved"),
        ("fake_plan", 409, "plan_not_approved"),
        ("invalid_total", 422, "invalid_plan"),
        ("locked", 409, "exam_read_only"),
        ("source_changed", 409, "stale_snapshot"),
        ("other_source", 404, "source_not_found"),
        ("duplicate_source", 422, "invalid_locator"),
        ("missing_source", 422, "missing_source"),
        ("fake_text", 422, None),
        ("fake_owner", 422, None),
        ("fake_job", 422, None),
        ("boolean_points", 422, None),
    ],
)
def test_generation_rejects_bad_inputs_before_provider(generated, mutation, status, code):
    repo, job, original, _, _ = generated
    body, headers = submission(job), HEADERS
    old = json.loads(json.dumps(original))
    match mutation:
        case "no_session":
            headers = {}
        case "other_owner":
            headers = OTHER
        case "no_consent":
            body["consent"] = False
        case "old_revision":
            body["baseRevision"] = 3
        case "no_approved_plan":
            del old["approvedGenerationPlan"]
        case "fake_plan":
            body["plan"]["instructions"] = "Ma trận tự gửi chưa được duyệt."
        case "invalid_total":
            old["approvedGenerationPlan"]["slots"][0]["pointsQ4"] = 1
            body["plan"]["slots"][0]["pointsQ4"] = 1
        case "locked":
            old["draftStatus"] = "finalized"
        case "source_changed":
            body["sources"][0]["sourceVersion"] -= 1
        case "other_source":
            body["sources"][0]["sourceId"] = str(uuid4())
        case "duplicate_source":
            body["sources"] *= 2
        case "missing_source":
            body.update(sources=[], requireEvidence=True)
        case "fake_text":
            body["sources"][0]["text"] = "Nội dung giả từ trình duyệt."
        case "fake_owner":
            body["ownerId"] = "teacher-1"
        case "fake_job":
            body["jobId"] = str(uuid4())
        case "boolean_points":
            body["plan"]["slots"][0]["pointsQ4"] = True
    repo.update_exam(job, old)

    async def run():
        calls = 0

        async def provider(_job):
            nonlocal calls
            calls += 1
            return "{}"

        runner = PatchJobRunner(
            provider, repo.current, repo.stage, timeout_seconds=1, max_active=1, max_retained=1
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fixture_app(repo, runner)), base_url="http://test"
        ) as client:
            result = await client.post(
                f"/api/exams/{job.examId}/proposals/generate", headers=headers, json=body
            )
            assert result.status_code == status, result.text
            if code is not None:
                assert result.json()["detail"]["code"] == code
        assert calls == 0
        assert repo.snapshot(job)[0] == old
        assert repo.history_count() == 0

    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["plan", "source", "revision", "cancel", "timeout"])
def test_generation_drops_late_or_stale_result_before_storing_preview(generated, mutation):
    repo, job, old, proposal, _ = generated
    body = submission(job)

    async def run():
        started, caught, released, exited = (asyncio.Event() for _ in range(4))

        async def provider(current):
            started.set()
            try:
                await released.wait()
            except asyncio.CancelledError:
                caught.set()
                await released.wait()
            finally:
                exited.set()
            return proposal.model_copy(update={"jobId": current.jobId}).model_dump_json()

        runner = PatchJobRunner(
            provider,
            repo.current,
            repo.stage,
            timeout_seconds=0.08 if mutation == "timeout" else 2,
            max_active=1,
            max_retained=2,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fixture_app(repo, runner)), base_url="http://test"
        ) as client:
            url = f"/api/exams/{job.examId}/proposals"
            created = await client.post(url + "/generate", headers=HEADERS, json=body)
            assert created.status_code == 202, created.text
            base = url + "/" + created.json()["jobId"]
            await started.wait()
            expected = json.loads(json.dumps(old))
            if mutation == "plan":
                expected["approvedGenerationPlan"]["instructions"] = "Ma trận mới."
                repo.update_exam(job, expected)
            elif mutation == "revision":
                expected["revision"] += 1
                repo.update_exam(job, expected)
            elif mutation == "source":
                repo.update_sources(job, (job.sources[0].model_copy(update={"sourceVersion": 4}),))
            elif mutation == "cancel":
                assert (await client.post(base + "/cancel", headers=OTHER)).status_code == 404
                assert (await client.post(base + "/cancel", headers=HEADERS)).json()[
                    "status"
                ] == "cancelled"
                await caught.wait()
            else:
                await caught.wait()
            if mutation in ("cancel", "timeout"):
                again = await client.post(
                    url + "/generate", headers=HEADERS, json={**body, "requestId": str(uuid4())}
                )
                assert again.status_code == 429
            released.set()
            completed = terminal(
                await client.get(base + "/events", headers={**HEADERS, "Last-Event-ID": "1"})
            )
            await exited.wait()
            await asyncio.sleep(0)
            expected_error = "timeout" if mutation == "timeout" else "stale_snapshot"
            if mutation == "cancel":
                assert completed["status"] == "cancelled"
            else:
                assert (completed["status"], completed["errorCode"]) == ("failed", expected_error)
            assert completed["proposal"] is None
            assert (
                await client.post(base + "/confirm", headers=HEADERS, json={"baseRevision": 4})
            ).status_code == 404
            assert repo.snapshot(job)[0] == expected
            assert repo.history_count() == 0

    asyncio.run(asyncio.wait_for(run(), timeout=5))


def test_generation_rejects_repository_identity_mismatch(generated):
    repo, job, old, _, _ = generated
    read = repo.read_generation_inputs

    async def wrong(owner, exam, keys):
        return replace(await read(owner, exam, keys), owner_id="other-teacher")

    repo.read_generation_inputs = wrong

    async def run():
        runner = PatchJobRunner(
            None, repo.current, repo.stage, timeout_seconds=1, max_active=1, max_retained=1
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fixture_app(repo, runner)), base_url="http://test"
        ) as client:
            result = await client.post(
                f"/api/exams/{job.examId}/proposals/generate", headers=HEADERS, json=submission(job)
            )
            assert result.status_code == 404
        assert repo.snapshot(job)[0] == old

    asyncio.run(run())


def test_generation_plan_changed_before_provider_is_not_sent(generated):
    repo, job, old, _, _ = generated

    async def run():
        calls = 0

        async def provider(_job):
            nonlocal calls
            calls += 1
            return "{}"

        async def current(candidate):
            changed = json.loads(json.dumps(old))
            changed["approvedGenerationPlan"]["instructions"] = "Ma trận đã đổi khi đang xếp hàng."
            repo.update_exam(job, changed)
            return await repo.current(candidate)

        runner = PatchJobRunner(
            provider, current, repo.stage, timeout_seconds=1, max_active=1, max_retained=1
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fixture_app(repo, runner)), base_url="http://test"
        ) as client:
            collection = f"/api/exams/{job.examId}/proposals"
            created = await client.post(
                collection + "/generate", headers=HEADERS, json=submission(job)
            )
            assert created.status_code == 202, created.text
            base = collection + "/" + created.json()["jobId"]
            completed = terminal(await client.get(base + "/events", headers=HEADERS))
            assert (completed["status"], completed["errorCode"]) == ("failed", "stale_snapshot")
            assert calls == 0
            assert (
                await client.post(base + "/confirm", headers=HEADERS, json={"baseRevision": 4})
            ).status_code == 404
            assert repo.history_count() == 0

    asyncio.run(run())


def test_smoke_sinh_tu_request_den_luu_qua_http(generated, smoke_evidence):
    mode, model, _, _, timeout = smoke_evidence
    if mode == "fixture":
        pytest.skip("Chạy khi chọn --smoke-ollama-model.")
    repo, job, old, _, _ = generated
    body = submission(job)
    body["plan"]["slots"] = [{**body["plan"]["slots"][0], "pointsQ4": 40}]
    body["plan"]["instructions"] = (
        "Sinh một câu trắc nghiệm tính x + 1 khi x = 2 theo nguồn đã chọn."
    )
    old = {**old, "approvedGenerationPlan": body["plan"]}
    repo.update_exam(job, old)

    async def run():
        runner = PatchJobRunner(
            OllamaProvider(model),
            repo.current,
            repo.stage,
            timeout_seconds=timeout,
            max_active=1,
            max_retained=1,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fixture_app(repo, runner)), base_url="http://test"
        ) as client:
            collection = f"/api/exams/{job.examId}/proposals"
            created = await client.post(collection + "/generate", headers=HEADERS, json=body)
            assert created.status_code == 202, created.text
            base = collection + "/" + created.json()["jobId"]
            completed = terminal(await client.get(base + "/events", headers=HEADERS))
            assert completed["status"] == "complete", completed["errorCode"]
            assert repo.snapshot(job)[0] == old
            assert repo.history_count() == 0
            saved = await client.post(base + "/confirm", headers=HEADERS, json={"baseRevision": 4})
            assert saved.status_code == 200, saved.text
            repeated = await client.post(
                base + "/confirm", headers=HEADERS, json={"baseRevision": 4}
            )
            assert repeated.json() == saved.json()
            current = repo.snapshot(job)[0]
            assert current["revision"] == 5
            assert current["questions"][0]["id"] == saved.json()["changedQuestionIds"][0]
            assert current["questions"][0]["stem"] == completed["proposal"]["questions"][0]["stem"]
            assert (
                current["questions"][0]["evidence"]
                == completed["proposal"]["questions"][0]["evidence"]
            )
            assert current["questions"][0]["points"] == 10
            assert repo.history_count() == 1

    asyncio.run(asyncio.wait_for(run(), timeout=timeout + 10))
