"""Router xác nhận đề xuất dành cho app đã cấu hình phiên và repository."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mach_backend.ai_contract import AIError, ContractModel, Revision
from mach_backend.patch_confirmation import ConfirmationRepository, PatchReceipt, confirm_patch


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
