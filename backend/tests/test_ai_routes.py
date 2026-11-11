"""Chạy các route AI đã ghép với cùng phiên, repository và provider."""

import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from test_check_routes import path_for, reply_for
from test_check_routes import sample as sample
from test_generation_confirmation import generated as generated
from test_generation_submission import submission
from test_patch_confirmation import HEADERS, OTHER, OWNER, submission_body
from test_patch_confirmation import sample as patch_fixture

from mach_backend.ai_routes import build_ai_router
from mach_backend.ai_service import OllamaProvider


def authenticated_owner(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if authorization == HEADERS["Authorization"]:
        return OWNER
    if authorization == OTHER["Authorization"]:
        return "teacher-2"
    raise HTTPException(401)


patch_sample = patch_fixture


@pytest.mark.parametrize("operation", ["patch", "generate"])
@pytest.mark.parametrize("first", ["proposal", "check"])
def test_combined_routes_share_one_model_slot_and_confirm(
    sample, generated, patch_sample, operation, first
):
    repo, check_job, check_body, check_exam = sample
    if operation == "generate":
        _, job, old, proposal, _ = generated
        proposal_reply = proposal.model_dump(mode="json")
        body = submission(job)
    else:
        job, old, result = patch_sample
        proposal_reply = {
            **result,
            "edits": [
                {
                    "op": "replace",
                    "blockId": result["edits"][0]["blockId"],
                    "replacement": "Viết lại lời giải.",
                }
            ],
        }
        body = submission_body(job)
    repo.seed(job, old)

    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def reply(request):
            payload = json.loads(json.loads(request.content)["messages"][1]["content"])
            kind = "check" if "question" in payload else "proposal"
            calls.append(kind)
            if len(calls) == 1:
                started.set()
                await release.wait()
            result = reply_for(check_job) if kind == "check" else proposal_reply
            return httpx.Response(
                200,
                json={
                    "done": True,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({**result, "jobId": payload["jobId"]}),
                    },
                },
            )

        provider = OllamaProvider("fixture", transport=httpx.MockTransport(reply))
        app = FastAPI()
        app.include_router(
            build_ai_router(
                authenticated_owner=authenticated_owner,
                repository=repo,
                read_patch=repo.read_inputs,
                read_generation=repo.read_generation_inputs,
                read_check=repo.read_check,
                snapshot_is_current=repo.current,
                store_pending=repo.stage,
                provider=provider,
                timeout_seconds=2,
                max_active=2,
                max_retained=4,
            )
        )
        collection = f"/api/exams/{job.examId}/proposals"
        submit_path = collection + ("/generate" if operation == "generate" else "")
        check_path = path_for(check_job)
        assert len(app.openapi()["paths"]) == 7
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            assert (await client.post(submit_path, json=body)).status_code == 401
            assert (
                await client.post(check_path, headers=OTHER, json=check_body)
            ).status_code == 404

            async def submit(request_body):
                response = await client.post(submit_path, headers=HEADERS, json=request_body)
                assert response.status_code == 202, response.text
                return collection + "/" + response.json()["jobId"]

            async def solve():
                return await client.post(check_path, headers=HEADERS, json=check_body)

            async def end_event(path):
                response = await client.get(path + "/events", headers=HEADERS)
                assert response.status_code == 200, response.text
                return json.loads(response.text.rsplit("data: ", 1)[1])

            if first == "proposal":
                path = await submit(body)
                await started.wait()
                busy = await solve()
                assert busy.status_code == 429
                assert busy.json()["detail"]["code"] == "job_limit"
                assert calls == ["proposal"]
                release.set()
                complete = await end_event(path)
                assert (await solve()).json()["comparison"] == "disagrees"
            else:
                pending_check = asyncio.create_task(solve())
                await started.wait()
                blocked_path = await submit(body)
                blocked = await end_event(blocked_path)
                assert (blocked["status"], blocked["errorCode"]) == ("failed", "job_limit")
                assert calls == ["check"]
                refused = await client.post(
                    blocked_path + "/confirm", headers=HEADERS, json={"baseRevision": 4}
                )
                assert refused.status_code == 404
                release.set()
                assert (await pending_check).json()["comparison"] == "disagrees"
                path = await submit({**body, "requestId": str(uuid4())})
                complete = await end_event(path)

            assert complete["status"] == "complete", complete
            assert (await client.get(path + "/status", headers=OTHER)).status_code == 404
            assert repo.snapshot(job)[0] == old
            assert repo.history_count() == 0
            confirmed = await client.post(
                path + "/confirm", headers=HEADERS, json={"baseRevision": 4}
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["revision"] == 5
            assert repo.snapshot(job)[0]["revision"] == 5
            assert repo.snapshot(check_job)[0] == check_exam
            assert repo.history_count() == 1
            assert len(calls) == 2

    asyncio.run(asyncio.wait_for(run(), timeout=5))
