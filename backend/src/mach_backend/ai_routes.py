"""Ghép các route AI với phiên và repository do ứng dụng cung cấp."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter

from mach_backend.ai_contract import PatchJob, SnapshotCheck
from mach_backend.ai_questions import GenerateJob
from mach_backend.ai_service import OllamaProvider
from mach_backend.check_routes import ReadCheckInputs, build_check_router
from mach_backend.generation_submission import ReadGenerationInputs
from mach_backend.patch_confirmation import ConfirmationRepository, PendingGeneration, PendingPatch
from mach_backend.patch_jobs import PatchJobRunner
from mach_backend.patch_routes import (
    build_generation_router,
    build_patch_confirmation_router,
    build_patch_job_router,
)
from mach_backend.patch_submission import ReadPatchInputs


def build_ai_router(
    *,
    authenticated_owner: Callable[..., str | Awaitable[str]],
    repository: ConfirmationRepository,
    read_patch: ReadPatchInputs,
    read_generation: ReadGenerationInputs,
    read_check: ReadCheckInputs,
    snapshot_is_current: SnapshotCheck[PatchJob | GenerateJob],
    store_pending: Callable[[PendingPatch | PendingGeneration], Awaitable[bool]],
    provider: OllamaProvider | None,
    timeout_seconds: float,
    max_active: int,
    max_retained: int,
) -> APIRouter:
    runner = PatchJobRunner(
        provider,
        snapshot_is_current,
        store_pending,
        timeout_seconds=timeout_seconds,
        max_active=max_active,
        max_retained=max_retained,
    )
    router = APIRouter()
    router.include_router(build_patch_job_router(runner, authenticated_owner, read_patch))
    router.include_router(build_generation_router(runner, authenticated_owner, read_generation))
    router.include_router(build_patch_confirmation_router(repository, authenticated_owner))
    router.include_router(
        build_check_router(
            authenticated_owner,
            read_check,
            provider,
            timeout_seconds=timeout_seconds,
            max_active=max_active,
        )
    )
    return router
