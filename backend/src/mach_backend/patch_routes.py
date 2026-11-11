"""Router xác nhận đề xuất dành cho app đã cấu hình phiên và repository."""

from collections.abc import AsyncIterator, Awaitable, Callable
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from mach_backend.ai_contract import AIError, ContractModel, Revision
from mach_backend.ai_sources import selected_source_keys
from mach_backend.patch_confirmation import ConfirmationRepository, PatchReceipt, confirm_patch
from mach_backend.patch_jobs import PatchJobRunner, PatchJobStatus
from mach_backend.patch_submission import (
    PatchSubmission,
    ReadPatchInputs,
    build_patch_job,
)


class ConfirmPatchRequest(ContractModel):
    baseRevision: Revision


def build_patch_confirmation_router(
    repository: ConfirmationRepository,
    authenticated_owner: Callable[..., str | Awaitable[str]],
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/exams/{exam_id}/proposals/{job_id}/confirm",
        responses={
            404: {"description": "Không tìm thấy đề xuất"},
            409: {"description": "Xung đột"},
        },
    )
    def confirm(
        exam_id: UUID,
        job_id: UUID,
        request: ConfirmPatchRequest,
        owner_id: Annotated[str, Depends(authenticated_owner)],
    ) -> PatchReceipt:
        try:
            return confirm_patch(repository, owner_id, exam_id, job_id, request.baseRevision)
        except AIError as error:
            status = 404 if error.code == "proposal_not_found" else 409
            raise HTTPException(
                status_code=status, detail={"code": error.code, "message": str(error)}
            ) from None

    return router


def build_patch_job_router(
    runner: PatchJobRunner,
    authenticated_owner: Callable[..., str | Awaitable[str]],
    read_inputs: ReadPatchInputs,
) -> APIRouter:
    router = APIRouter(prefix="/api/exams/{exam_id}/proposals")

    @router.post("", status_code=202)
    async def submit(
        exam_id: UUID,
        request: PatchSubmission,
        owner_id: Annotated[str, Depends(authenticated_owner)],
    ) -> PatchJobStatus:
        try:
            sources = selected_source_keys(request)
            digest = sha256(request.model_dump_json().encode()).hexdigest()
            if prior := runner.replay(owner_id, exam_id, request.requestId, digest):
                return prior
            inputs = await read_inputs(owner_id, exam_id, sources)
            if prior := runner.replay(owner_id, exam_id, request.requestId, digest):
                return prior
            job = build_patch_job(owner_id, exam_id, request, inputs)
            return runner.submit(job, submission=(request.requestId, digest))
        except AIError as error:
            match error.code:
                case "exam_not_found" | "source_not_found":
                    status_code = 404
                case "consent_required":
                    status_code = 403
                case "stale_snapshot" | "exam_read_only" | "job_conflict":
                    status_code = 409
                case "job_limit":
                    status_code = 429
                case _:
                    status_code = 422
            raise HTTPException(
                status_code, detail={"code": error.code, "message": str(error)}
            ) from None

    @router.get("/{job_id}/status")
    async def status(
        exam_id: UUID, job_id: UUID, owner_id: Annotated[str, Depends(authenticated_owner)]
    ) -> PatchJobStatus:
        try:
            return runner.status(owner_id, exam_id, job_id)
        except AIError as error:
            raise HTTPException(404, detail={"code": error.code, "message": str(error)}) from None

    @router.post("/{job_id}/cancel")
    async def cancel(
        exam_id: UUID, job_id: UUID, owner_id: Annotated[str, Depends(authenticated_owner)]
    ) -> PatchJobStatus:
        try:
            return await runner.cancel(owner_id, exam_id, job_id)
        except AIError as error:
            raise HTTPException(404, detail={"code": error.code, "message": str(error)}) from None

    @router.get("/{job_id}/events")
    async def events(
        exam_id: UUID,
        job_id: UUID,
        owner_id: Annotated[str, Depends(authenticated_owner)],
        after: Annotated[int, Header(alias="Last-Event-ID", ge=0, le=2)] = 0,
    ) -> StreamingResponse:
        try:
            updates = runner.events(owner_id, exam_id, job_id, after=after)
        except AIError as error:
            raise HTTPException(404, detail={"code": error.code, "message": str(error)}) from None

        async def encode() -> AsyncIterator[str]:
            async for update in updates:
                yield (f"id: {update.sequence}\nevent: patch\ndata: {update.model_dump_json()}\n\n")

        return StreamingResponse(
            encode(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
