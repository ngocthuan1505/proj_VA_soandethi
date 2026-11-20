"""Xác nhận đề xuất đã lưu từ bản xem trước bằng một giao dịch."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import JsonValue

from mach_backend.ai_contract import (
    AIError,
    ContractModel,
    JobIdentity,
    PatchJob,
    PatchProposal,
    Revision,
    SnapshotCheck,
    SourceFragment,
    read_patch_context,
    validate_patch_job,
    validate_proposal,
    validate_sources,
)
from mach_backend.ai_questions import (
    GeneratedQuestion,
    GenerateJob,
    GenerateProposal,
    GenerationPlan,
    validate_generation,
    validate_generation_plan,
)
from mach_backend.ai_service import Provider, propose_exam, propose_patch
from mach_backend.rich_patch import update_rich

type ExamSnapshot = dict[str, JsonValue]


class PendingPatch(ContractModel):
    job: PatchJob
    proposal: PatchProposal


class PendingGeneration(ContractModel):
    job: GenerateJob
    proposal: GenerateProposal


class PatchReceipt(JobIdentity):
    revision: Revision
    changedQuestionIds: tuple[UUID, ...]


@dataclass(frozen=True)
class ConfirmationState:
    owner_id: str
    pending: PendingPatch | PendingGeneration
    exam: ExamSnapshot
    sources: tuple[SourceFragment, ...]
    receipt: PatchReceipt | None = None
    approved_plan: GenerationPlan | None = None


class PatchTransaction(Protocol):
    def read(self) -> ConfirmationState | None:
        """Đọc đề xuất còn hiệu lực hoặc biên nhận đã xác nhận trong đúng phạm vi."""
        ...

    def write(self, exam: ExamSnapshot, receipt: PatchReceipt) -> None:
        """Ghi đề, phiên bản câu và biên nhận chung trong giao dịch hiện tại."""
        ...


class ConfirmationRepository(Protocol):
    def transaction(
        self, owner_id: str, exam_id: UUID, job_id: UUID
    ) -> AbstractContextManager[PatchTransaction]:
        """Giữ cùng giao dịch từ lúc đọc đến khi ghi, rollback nếu lỗi."""
        ...


async def prepare_patch(
    job: PatchJob,
    provider: Provider[PatchJob] | None,
    snapshot_is_current: SnapshotCheck[PatchJob],
    store_pending: Callable[[PendingPatch], Awaitable[bool]],
    *,
    timeout_seconds: float,
) -> PatchProposal:
    proposal = await propose_patch(
        job, provider, snapshot_is_current, timeout_seconds=timeout_seconds
    )
    # Repository kiểm lại snapshot và trạng thái job khi ghi bản xem trước.
    if not await store_pending(PendingPatch(job=job, proposal=proposal)):
        raise AIError("stale_snapshot", "Đề, nguồn hoặc tác vụ đã đổi trước khi lưu bản xem trước.")
    return proposal


async def prepare_generation(
    job: GenerateJob,
    provider: Provider[GenerateJob] | None,
    snapshot_is_current: SnapshotCheck[GenerateJob],
    store_pending: Callable[[PendingGeneration], Awaitable[bool]],
    *,
    timeout_seconds: float,
) -> GenerateProposal:
    proposal = await propose_exam(
        job, provider, snapshot_is_current, timeout_seconds=timeout_seconds
    )
    if not await store_pending(PendingGeneration(job=job, proposal=proposal)):
        raise changed_snapshot()
    return proposal


def missing_patch() -> AIError:
    return AIError("proposal_not_found", "Không tìm thấy đề xuất có thể xác nhận.")


def changed_snapshot() -> AIError:
    return AIError("stale_snapshot", "Đề hoặc nguồn đã thay đổi. Hãy tạo lại đề xuất.")


def confirm_patch(
    repo: ConfirmationRepository,
    owner_id: str,
    exam_id: UUID,
    job_id: UUID,
    base_revision: int,
) -> PatchReceipt:
    with repo.transaction(owner_id, exam_id, job_id) as tx:
        state = tx.read()
        if state is None or state.owner_id != owner_id:
            raise missing_patch()
        job = state.pending.job
        if (job.ownerId, job.examId, job.jobId) != (owner_id, exam_id, job_id):
            raise missing_patch()
        if job.baseRevision != base_revision:
            raise changed_snapshot()
        if state.receipt is not None:
            return state.receipt
        if isinstance(state.pending, PendingGeneration):
            exam, receipt = apply_generation(state)
        else:
            exam, receipt = apply_patch(state)
        tx.write(exam, receipt)
        return receipt


def current_patch_questions(job: PatchJob, exam: ExamSnapshot) -> dict[UUID, ExamSnapshot]:
    questions = exam.get("questions")
    if not isinstance(questions, list):
        raise changed_snapshot()

    by_block = {}
    for target in job.targets:
        matches = [
            question
            for question in questions
            if isinstance(question, dict) and question.get("id") == str(target.questionId)
        ]
        if len(matches) != 1:
            raise changed_snapshot()
        question = matches[0]
        version, blocks = question.get("v"), question.get("blockIds")
        if (
            type(version) is not int
            or version != target.questionVersion
            or not isinstance(blocks, dict)
            or blocks.get(target.field) != str(target.blockId)
            or question.get(target.field) != target.text
            or (target.context is not None and read_patch_context(question) != target.context)
        ):
            raise changed_snapshot()
        by_block[target.blockId] = question
    return by_block


def apply_patch(state: ConfirmationState) -> tuple[ExamSnapshot, PatchReceipt]:
    if not isinstance(state.pending, PendingPatch):
        raise AIError("invalid_result", "Đề xuất không thuộc thao tác sửa lời giải.")
    job = state.pending.job
    validate_sources(job)
    validate_patch_job(job)
    proposal = validate_proposal(job, state.pending.proposal.model_dump_json())
    exam = editable_snapshot(state)
    revision = job.baseRevision
    questions = current_patch_questions(job, exam)
    targets = {target.blockId: target for target in job.targets}
    changed: list[UUID] = []
    for edit in proposal.edits:
        target = targets[edit.blockId]
        question = questions[edit.blockId]
        rich = question.get("explanationDoc")
        if rich is not None:
            question["explanationDoc"] = update_rich(rich, target, edit.content)
        question[target.field] = edit.content
        question["v"] = target.questionVersion + 1
        question["check"] = None
        if "verification" in question:
            question["verification"] = None
        question["verificationStatus"] = "unverified"
        question["approvalStatus"] = "draft"
        changed.append(target.questionId)

    exam["revision"] = revision + 1
    return exam, PatchReceipt(
        jobId=job.jobId,
        examId=job.examId,
        baseRevision=job.baseRevision,
        revision=revision + 1,
        changedQuestionIds=tuple(changed),
    )


def editable_snapshot(state: ConfirmationState) -> ExamSnapshot:
    job = state.pending.job
    exam = state.exam
    revision = exam.get("revision")
    if (
        exam.get("id") != str(job.examId)
        or type(revision) is not int
        or revision != job.baseRevision
        or not set(job.sources).issubset(state.sources)
    ):
        raise changed_snapshot()
    if exam.get("draftStatus", "draft") not in ("draft", "ready"):
        raise AIError("exam_read_only", "Trạng thái hiện tại của đề không cho phép sửa.")
    return deepcopy(exam)


def generated_question_snapshot(question: GeneratedQuestion) -> ExamSnapshot:
    fields = {
        "stem",
        "explanation",
        "rubric",
        "figure",
        "options",
        "answer",
        "answerText",
        "truthValues",
    }
    data: ExamSnapshot = question.model_dump(mode="json", exclude={"rubric"})
    answer = data.pop("answer")
    data.update(
        id=str(uuid4()),
        v=1,
        blockIds={field: str(uuid4()) for field in sorted(fields)},
        points=question.pointsQ4 / 4,
        answer=answer if question.type == "mcq" else 0,
        answerText=answer if question.type == "short" else "",
        truthValues=answer if question.type == "truefalse" else [],
        answerKnown=question.type != "essay",
        rubric=[
            {**step.model_dump(mode="json"), "points": step.pointsQ4 / 4}
            for step in question.rubric
        ],
        check=None,
        verificationStatus="unverified",
        approvalStatus="draft",
    )
    return data


def apply_generation(state: ConfirmationState) -> tuple[ExamSnapshot, PatchReceipt]:
    if not isinstance(state.pending, PendingGeneration):
        raise AIError("invalid_result", "Đề xuất không thuộc thao tác sinh đề.")
    job = state.pending.job
    validate_sources(job)
    validate_generation_plan(job)
    proposal = validate_generation(job, state.pending.proposal.model_dump_json())
    exam = editable_snapshot(state)
    if state.approved_plan is None or state.approved_plan.model_dump() != job.model_dump(
        include=set(GenerationPlan.model_fields)
    ):
        raise AIError("plan_not_approved", "Cấu trúc sinh đề chưa được duyệt hoặc đã thay đổi.")
    questions = [generated_question_snapshot(question) for question in proposal.questions]
    revision = job.baseRevision + 1
    exam["questions"] = [question for question in questions]
    exam.update(
        revision=revision,
        subject=job.subject,
        grade=job.grade,
        instructions=job.instructions,
        draftStatus="draft",
        fullExam=True,
        sample=False,
        aiPlan=None,
    )
    return exam, PatchReceipt(
        jobId=job.jobId,
        examId=job.examId,
        baseRevision=job.baseRevision,
        revision=revision,
        changedQuestionIds=tuple(UUID(str(question["id"])) for question in questions),
    )
