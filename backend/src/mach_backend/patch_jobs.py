"""Chạy đề xuất sửa lời giải và loại phản hồi đến sau khi đã hủy."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from mach_backend.ai_contract import AIError, JobIdentity, PatchJob, PatchProposal, SnapshotCheck
from mach_backend.ai_service import Provider
from mach_backend.patch_confirmation import PendingPatch, prepare_patch

type TerminalStatus = Literal["complete", "cancelled", "failed"]
logger = logging.getLogger(__name__)


class PatchJobStatus(JobIdentity):
    sequence: Literal[1, 2] = 1
    status: Literal["running", "complete", "cancelled", "failed"] = "running"
    proposal: PatchProposal | None = None
    errorCode: str | None = None


@dataclass
class _Run:
    job: PatchJob
    state: PatchJobStatus
    submission: tuple[UUID, str] | None
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    publishing: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task[None] | None = None
    deadline: asyncio.TimerHandle | None = None


class PatchJobRunner:
    """Giữ tối đa hai sự kiện mỗi job trên cùng event loop với các route."""

    def __init__(
        self,
        provider: Provider[PatchJob] | None,
        snapshot_is_current: SnapshotCheck[PatchJob],
        store_pending: Callable[[PendingPatch], Awaitable[bool]],
        *,
        timeout_seconds: float,
        max_active: int,
        max_retained: int,
    ):
        if not 1 <= max_active <= max_retained or not 0 < timeout_seconds <= 300:
            raise ValueError("Cấu hình số tác vụ hoặc thời hạn không hợp lệ.")
        self._provider = provider
        self._snapshot_is_current = snapshot_is_current
        self._store_pending = store_pending
        self._timeout_seconds = timeout_seconds
        self._max_active = max_active
        self._max_retained = max_retained
        self._runs: dict[UUID, _Run] = {}

    def replay(
        self, owner_id: str, exam_id: UUID, request_id: UUID, digest: str
    ) -> PatchJobStatus | None:
        for run in self._runs.values():
            if (run.job.ownerId, run.job.examId) != (owner_id, exam_id) or run.submission is None:
                continue
            original_id, original_digest = run.submission
            if original_id == request_id:
                if original_digest != digest:
                    raise AIError("job_conflict", "Mã yêu cầu đã dùng cho nội dung khác.")
                return run.state
        return None

    def submit(
        self, job: PatchJob, *, submission: tuple[UUID, str] | None = None
    ) -> PatchJobStatus:
        """Nhận snapshot do backend tạo. Gửi lại cùng job trả trạng thái hiện tại."""
        if job.jobId in self._runs:
            prior = self._owned(job.ownerId, job.examId, job.jobId)
            if prior.job != job:
                raise AIError("job_conflict", "Mã tác vụ đã dùng cho yêu cầu khác.")
            return prior.state
        active = sum(run.task is not None and not run.task.done() for run in self._runs.values())
        if active >= self._max_active:
            raise AIError("job_limit", "Đang có nhiều tác vụ AI. Hãy thử lại sau.")
        if len(self._runs) >= self._max_retained:
            expired = next(key for key, run in self._runs.items() if run.task and run.task.done())
            del self._runs[expired]

        run = _Run(
            job,
            PatchJobStatus(jobId=job.jobId, examId=job.examId, baseRevision=job.baseRevision),
            submission,
        )
        loop = asyncio.get_running_loop()
        self._runs[job.jobId] = run
        run.deadline = loop.call_later(self._timeout_seconds, self._expire, run)
        run.task = loop.create_task(self._execute(run), name=f"patch:{job.jobId}")
        return run.state

    def _owned(self, owner_id: str, exam_id: UUID, job_id: UUID) -> _Run:
        run = self._runs.get(job_id)
        if run is None or (run.job.ownerId, run.job.examId) != (owner_id, exam_id):
            raise AIError("job_not_found", "Không tìm thấy tác vụ trong đề này.")
        return run

    def status(self, owner_id: str, exam_id: UUID, job_id: UUID) -> PatchJobStatus:
        return self._owned(owner_id, exam_id, job_id).state

    async def cancel(self, owner_id: str, exam_id: UUID, job_id: UUID) -> PatchJobStatus:
        run = self._owned(owner_id, exam_id, job_id)
        async with run.publishing:
            if run.state.status == "running":
                self._finish(run, "cancelled")
                if run.task is not None:
                    run.task.cancel()
        return run.state

    def events(
        self, owner_id: str, exam_id: UUID, job_id: UUID, *, after: int = 0
    ) -> AsyncIterator[PatchJobStatus]:
        run = self._owned(owner_id, exam_id, job_id)

        async def follow() -> AsyncIterator[PatchJobStatus]:
            if run.state.sequence == 1 and after < 1:
                yield run.state
            await run.finished.wait()
            if after < run.state.sequence:
                yield run.state

        return follow()

    def _expire(self, run: _Run) -> None:
        if run.state.status == "running":
            self._finish(run, "failed", error_code="timeout")
            if run.task is not None:
                run.task.cancel()

    @staticmethod
    def _finish(
        run: _Run,
        status: TerminalStatus,
        *,
        proposal: PatchProposal | None = None,
        error_code: str | None = None,
    ) -> None:
        if run.state.status != "running":
            return
        run.state = PatchJobStatus(
            jobId=run.job.jobId,
            examId=run.job.examId,
            baseRevision=run.job.baseRevision,
            sequence=2,
            status=status,
            proposal=proposal,
            errorCode=error_code,
        )
        if run.deadline is not None:
            run.deadline.cancel()
        run.finished.set()

    async def _execute(self, run: _Run) -> None:
        async def publish(pending: PendingPatch) -> bool:
            # Hủy và ghi preview dùng cùng khóa để chỉ một bên quyết định trạng thái cuối.
            async with run.publishing:
                if run.state.status != "running":
                    return False
                # Repository giữ giao dịch ngắn và kiểm lại snapshot trước khi commit.
                if run.deadline is not None:
                    run.deadline.cancel()
                if not await self._store_pending(pending):
                    return False
                self._finish(run, "complete", proposal=pending.proposal)
                return True

        try:
            await prepare_patch(
                run.job,
                self._provider,
                self._snapshot_is_current,
                publish,
                timeout_seconds=self._timeout_seconds,
            )
        except asyncio.CancelledError:
            self._finish(run, "cancelled")
            raise
        except AIError as error:
            self._finish(run, "failed", error_code=error.code)
        except Exception:
            logger.error("Lỗi nội bộ khi chạy đề xuất, job_id=%s", run.job.jobId)
            self._finish(run, "failed", error_code="internal_error")
