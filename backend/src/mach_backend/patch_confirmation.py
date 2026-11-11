"""Xác nhận đề xuất đã lưu từ bản xem trước bằng một giao dịch."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

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
    validate_patch_job,
    validate_proposal,
    validate_sources,
)
from mach_backend.ai_service import Provider, propose_patch
from mach_backend.rich_patch import update_rich

type ExamSnapshot = dict[str, JsonValue]


class PendingPatch(ContractModel):
    job: PatchJob
    proposal: PatchProposal


class PatchReceipt(JobIdentity):
    revision: Revision
    changedQuestionIds: tuple[UUID, ...]


@dataclass(frozen=True)
class ConfirmationState:
    owner_id: str
    pending: PendingPatch
    exam: ExamSnapshot
    sources: tuple[SourceFragment, ...]
    receipt: PatchReceipt | None = None


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
        exam, receipt = apply_patch(state)
        tx.write(exam, receipt)
        return receipt


def apply_patch(state: ConfirmationState) -> tuple[ExamSnapshot, PatchReceipt]:
    job = state.pending.job
    validate_sources(job)
    validate_patch_job(job)
    proposal = validate_proposal(job, state.pending.proposal.model_dump_json())
    exam = deepcopy(state.exam)
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
    questions = exam.get("questions")
    if not isinstance(questions, list):
        raise changed_snapshot()

    targets = {target.blockId: target for target in job.targets}
    changed: list[UUID] = []
    for edit in proposal.edits:
        target = targets[edit.blockId]
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
        ):
            raise changed_snapshot()

        rich = question.get("explanationDoc")
        if rich is not None:
            question["explanationDoc"] = update_rich(rich, target, edit.content)
        question[target.field] = edit.content
        question["v"] = version + 1
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
