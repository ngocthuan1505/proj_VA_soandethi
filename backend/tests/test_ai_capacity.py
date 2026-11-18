"""Một provider được chia sẻ phải giữ chung suất cho Sinh/Sửa/Kiểm."""

import asyncio
import json

import httpx
import pytest
from test_ai_patch import job as job
from test_ai_patch import proposal as proposal
from test_ai_questions import check as check
from test_ai_questions import generation as generation
from test_check_routes import check_app, path_for, reply_for
from test_check_routes import sample as sample
from test_patch_confirmation import HEADERS

from mach_backend.ai_contract import AIError
from mach_backend.ai_service import OllamaProvider, check_question, propose_exam, propose_patch


async def current(_job):
    return True


def test_shared_provider_keeps_slot_until_cancelled_transport_exits(check):
    job, reply = check

    async def run():
        started, caught, released, exited = (asyncio.Event() for _ in range(4))
        calls = 0

        async def transport(_request):
            nonlocal calls
            calls += 1
            if calls == 1:
                started.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    caught.set()
                    await released.wait()
                finally:
                    exited.set()
            return httpx.Response(
                200,
                json={"done": True, "message": {"role": "assistant", "content": json.dumps(reply)}},
            )

        provider = OllamaProvider("fixture", transport=httpx.MockTransport(transport))

        async def call():
            return await check_question(job, provider, current, saved_answer=2, timeout_seconds=2)

        first = asyncio.create_task(call())
        await started.wait()
        with pytest.raises(AIError) as busy:
            await call()
        assert busy.value.code == "job_limit"
        assert calls == 1
        first.cancel()
        await caught.wait()
        with pytest.raises(AIError) as still_busy:
            await call()
        assert still_busy.value.code == "job_limit"
        assert calls == 1
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert exited.is_set()
        assert (await call()).comparison == "agrees"
        assert calls == 2

    asyncio.run(asyncio.wait_for(run(), timeout=5))


def test_provider_honors_explicit_capacity_without_queueing_extra_calls(check):
    job, reply = check

    async def run():
        started, released = asyncio.Event(), asyncio.Event()
        calls = 0

        async def transport(_request):
            nonlocal calls
            calls += 1
            if calls == 2:
                started.set()
            await released.wait()
            return httpx.Response(
                200,
                json={"done": True, "message": {"role": "assistant", "content": json.dumps(reply)}},
            )

        provider = OllamaProvider("fixture", transport=httpx.MockTransport(transport), max_active=2)
        first, second = (asyncio.create_task(provider(job)) for _ in range(2))
        await started.wait()
        with pytest.raises(AIError) as busy:
            await provider(job)
        assert busy.value.code == "job_limit"
        assert calls == 2
        released.set()
        await asyncio.gather(first, second)
        await provider(job)
        assert calls == 3

    asyncio.run(asyncio.wait_for(run(), timeout=5))


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_invalid_provider_capacity_is_rejected(capacity):
    with pytest.raises(ValueError):
        OllamaProvider("fixture", max_active=capacity)


@pytest.mark.parametrize("kind", ["generate", "patch"])
def test_check_http_shares_provider_capacity_with_generation_and_patch(
    sample, generation, job, proposal, kind
):
    repo, check_job, body, stored = sample
    generation_job, generation_reply = generation

    async def run():
        started, released = asyncio.Event(), asyncio.Event()
        calls = 0

        async def transport(request):
            nonlocal calls
            calls += 1
            payload = json.loads(json.loads(request.content)["messages"][1]["content"])
            if "slots" in payload:
                result = generation_reply
            elif "targets" in payload:
                result = {
                    **proposal.model_dump(mode="json"),
                    "edits": [
                        {
                            "op": "replace",
                            "blockId": payload["targets"][0]["blockId"],
                            "replacement": "Viết lại lời giải.",
                        }
                    ],
                }
            else:
                result = {**reply_for(check_job), "jobId": payload["jobId"]}
            if "slots" in payload or "targets" in payload:
                started.set()
                await released.wait()
            return httpx.Response(
                200,
                json={
                    "done": True,
                    "message": {"role": "assistant", "content": json.dumps(result)},
                },
            )

        provider = OllamaProvider("fixture", transport=httpx.MockTransport(transport))
        work = (
            propose_exam(generation_job, provider, current, timeout_seconds=2)
            if kind == "generate"
            else propose_patch(job, provider, current, timeout_seconds=2)
        )
        first = asyncio.create_task(work)
        await started.wait()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=check_app(repo, provider)), base_url="http://test"
        ) as client:
            busy = await client.post(path_for(check_job), headers=HEADERS, json=body)
            assert busy.status_code == 429, busy.text
            assert busy.json()["detail"]["code"] == "job_limit"
            assert calls == 1
            assert repo.snapshot(check_job)[0] == stored
            released.set()
            await first
            accepted = await client.post(path_for(check_job), headers=HEADERS, json=body)
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["comparison"] == "disagrees"
            assert calls == 2
        assert repo.snapshot(check_job)[0] == stored
        assert repo.history_count() == 0

    asyncio.run(asyncio.wait_for(run(), timeout=5))


@pytest.mark.parametrize("status,code", [(429, "rate_limited"), (503, "provider_unavailable")])
def test_provider_releases_capacity_after_http_failure(check, status, code):
    job, reply = check
    calls = 0

    def transport(_request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status)
        return httpx.Response(
            200, json={"done": True, "message": {"role": "assistant", "content": json.dumps(reply)}}
        )

    async def run():
        provider = OllamaProvider("fixture", transport=httpx.MockTransport(transport))
        with pytest.raises(AIError) as failed:
            await provider(job)
        assert failed.value.code == code
        assert json.loads(await provider(job)) == reply
        assert calls == 2

    asyncio.run(run())
