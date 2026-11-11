"""Route kiểm đáp án đọc câu, nguồn và đáp án đã lưu từ phiên hiện tại."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from mach_backend.ai_contract import AIError, Revision, SourceFragment
from mach_backend.ai_questions import Answer, BlindQuestion, CheckJob, CheckReport
from mach_backend.ai_service import Provider, check_question
from mach_backend.ai_sources import (
    SourceKey,
    SourceSelection,
    read_selected_sources,
    selected_source_keys,
)


class CheckSubmission(SourceSelection):
    baseRevision: Revision
    questionVersion: Revision


@dataclass(frozen=True)
class CheckInputs:
    owner_id: str
    exam_id: UUID
    base_revision: int
    question: BlindQuestion
    saved_answer: Answer
    sources: tuple[SourceFragment, ...] = ()


# Repository đọc cùng snapshot theo owner/đề/câu và các khóa nguồn được chọn.
type ReadCheckInputs = Callable[
    [str, UUID, UUID, tuple[SourceKey, ...]], Awaitable[CheckInputs | None]
]


def build_check_router(
    authenticated_owner: Callable[..., str | Awaitable[str]],
    read_inputs: ReadCheckInputs,
    provider: Provider[CheckJob] | None,
    *,
    timeout_seconds: float,
    max_active: int,
) -> APIRouter:
    if not 0 < timeout_seconds <= 300 or max_active < 1:
        raise ValueError("Cấu hình thời hạn hoặc số tác vụ kiểm đáp án không hợp lệ.")
    router = APIRouter()
    active = 0

    @router.post("/api/exams/{exam_id}/questions/{question_id}/check")
    async def check(
        exam_id: UUID,
        question_id: UUID,
        request: CheckSubmission,
        response: Response,
        owner_id: Annotated[str, Depends(authenticated_owner)],
    ) -> CheckReport:
        nonlocal active

        try:
            keys = selected_source_keys(request)

            async def load() -> CheckInputs:
                inputs = await read_inputs(owner_id, exam_id, question_id, keys)
                if inputs is None or (
                    inputs.owner_id,
                    inputs.exam_id,
                    inputs.question.questionId,
                ) != (owner_id, exam_id, question_id):
                    raise AIError("question_not_found", "Không tìm thấy câu trong đề này.")
                if (inputs.base_revision, inputs.question.questionVersion) != (
                    request.baseRevision,
                    request.questionVersion,
                ):
                    raise AIError("stale_snapshot", "Đề hoặc câu đã đổi. Hãy tải lại.")
                return replace(
                    inputs, sources=read_selected_sources(owner_id, request, inputs.sources)
                )

            deadline = asyncio.get_running_loop().time() + timeout_seconds
            async with asyncio.timeout_at(deadline):
                original = await load()
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AIError("timeout", "Chưa đọc được câu và nguồn trong thời hạn.")
            if active >= max_active:
                raise AIError("job_limit", "Đang có nhiều tác vụ kiểm đáp án. Hãy thử lại sau.")
            job = CheckJob(
                jobId=uuid4(),
                examId=exam_id,
                baseRevision=request.baseRevision,
                ownerId=owner_id,
                question=original.question,
                sources=original.sources,
                requireEvidence=bool(original.sources) or request.requireEvidence,
            )

            async def snapshot_is_current(_job: CheckJob) -> bool:
                try:
                    return await load() == original
                except AIError:
                    return False

            active += 1
            try:
                report = await check_question(
                    job,
                    provider,
                    snapshot_is_current,
                    saved_answer=original.saved_answer,
                    timeout_seconds=remaining,
                )
            finally:
                active -= 1
            response.headers["Cache-Control"] = "no-store"
            return report
        except TimeoutError:
            raise HTTPException(
                504, detail={"code": "timeout", "message": "Chưa đọc được câu trong thời hạn."}
            ) from None
        except AIError as error:
            match error.code:
                case "consent_required":
                    code = 403
                case "question_not_found" | "source_not_found":
                    code = 404
                case "stale_snapshot":
                    code = 409
                case "job_limit" | "rate_limited":
                    code = 429
                case "provider_unconfigured" | "provider_unavailable":
                    code = 503
                case "timeout":
                    code = 504
                case (
                    "invalid_result"
                    | "wrong_job"
                    | "invalid_evidence"
                    | "result_limit"
                    | "missing_evidence"
                    | "invalid_answer"
                    | "invalid_math"
                    | "invalid_options"
                ):
                    code = 502
                case _:
                    code = 422
            raise HTTPException(code, detail={"code": error.code, "message": str(error)}) from None

    return router
