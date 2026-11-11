"""Router xác nhận đề xuất dành cho app đã cấu hình phiên và repository."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from mach_backend.ai_contract import AIError, ContractModel, Revision
from mach_backend.patch_confirmation import ConfirmationRepository, PatchReceipt, confirm_patch
from mach_backend.patch_jobs import PatchJobRunner, PatchJobStatus


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
) -> APIRouter:
    router = APIRouter(prefix="/api/exams/{exam_id}/proposals/{job_id}")

    @router.get("/status")
    async def status(
        exam_id: UUID, job_id: UUID, owner_id: Annotated[str, Depends(authenticated_owner)]
    ) -> PatchJobStatus:
        try:
            return runner.status(owner_id, exam_id, job_id)
        except AIError as error:
            raise HTTPException(404, detail={"code": error.code, "message": str(error)}) from None

    @router.post("/cancel")
    async def cancel(
        exam_id: UUID, job_id: UUID, owner_id: Annotated[str, Depends(authenticated_owner)]
    ) -> PatchJobStatus:
        try:
            return await runner.cancel(owner_id, exam_id, job_id)
        except AIError as error:
            raise HTTPException(404, detail={"code": error.code, "message": str(error)}) from None

    @router.get("/events")
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
