"""Tạo tác vụ Sinh từ ma trận đã duyệt và nguồn được đọc theo phiên."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from mach_backend.ai_contract import AIError, Revision, SourceFragment, validate_sources
from mach_backend.ai_questions import GenerateJob, GenerationPlan, validate_generation_plan
from mach_backend.ai_sources import SourceKey, SourceSelection, WireUUID, read_selected_sources
from mach_backend.patch_confirmation import ExamSnapshot, changed_snapshot


class GenerationSubmission(SourceSelection):
    requestId: WireUUID
    baseRevision: Revision
    plan: GenerationPlan


@dataclass(frozen=True)
class GenerationInputs:
    owner_id: str
    exam: ExamSnapshot
    approved_plan: GenerationPlan | None
    sources: tuple[SourceFragment, ...]


# Repository đọc đề, ma trận đã duyệt và đoạn nguồn trong cùng snapshot theo owner.
type ReadGenerationInputs = Callable[
    [str, UUID, tuple[SourceKey, ...]], Awaitable[GenerationInputs | None]
]


def build_generation_job(
    owner_id: str,
    exam_id: UUID,
    request: GenerationSubmission,
    inputs: GenerationInputs | None,
) -> GenerateJob:
    if inputs is None or inputs.owner_id != owner_id or inputs.exam.get("id") != str(exam_id):
        raise AIError("exam_not_found", "Không tìm thấy đề có thể sinh câu.")
    exam = inputs.exam
    revision = exam.get("revision")
    if type(revision) is not int or revision != request.baseRevision:
        raise changed_snapshot()
    if exam.get("draftStatus", "draft") not in ("draft", "ready"):
        raise AIError("exam_read_only", "Trạng thái hiện tại của đề không cho phép sửa.")
    if inputs.approved_plan is None or inputs.approved_plan != request.plan:
        raise AIError("plan_not_approved", "Ma trận chưa được duyệt hoặc đã thay đổi. Hãy tải lại.")
    sources = read_selected_sources(owner_id, request, inputs.sources)
    job = GenerateJob(
        **inputs.approved_plan.model_dump(),
        jobId=uuid4(),
        examId=exam_id,
        baseRevision=revision,
        ownerId=owner_id,
        sources=sources,
        requireEvidence=bool(sources) or request.requireEvidence,
    )
    validate_generation_plan(job)
    validate_sources(job)
    return job
