"""Chạy đề xuất Sinh/Sửa và loại phản hồi đến sau khi đã hủy."""

import asyncio
import contextvars
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import model_serializer

from mach_backend.ai_contract import (
    AIError,
    JobIdentity,
    PatchJob,
    PatchProposal,
    SnapshotCheck,
    validate_patch_job,
    validate_proposal,
    validate_sources,
)
from mach_backend.ai_questions import (
    GenerateJob,
    GenerateProposal,
    validate_generation,
    validate_generation_plan,
)
from mach_backend.ai_service import MAX_AI_SECONDS, MAX_RESPONSE_BYTES, Provider
from mach_backend.patch_confirmation import (
    PendingGeneration,
    PendingPatch,
    prepare_generation,
    prepare_patch,
)

MAX_EXTENDED_AI_SECONDS = 7200
type TerminalStatus = Literal["complete", "cancelled", "failed", "early_stopped"]
logger = logging.getLogger(__name__)

_PROGRESS_CB: contextvars.ContextVar[Callable[[dict[str, Any]], None] | None] = (
    contextvars.ContextVar("_patch_job_progress_cb", default=None)
)


class _EarlyStopCaptured(Exception):
    """Tín hiệu nội bộ giữ nguyên bộ câu hỏi đã kiểm định khi dừng sớm giữa chừng."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__("early_stopped")
        self.payload = payload


def emit_patch_progress(event_type: str, **fields: Any) -> None:
    """Phát sự kiện tiến độ chi tiết vào luồng SSE của job hiện tại nếu đang chạy trong runner."""
    cb = _PROGRESS_CB.get()
    if cb is None:
        return
    event: dict[str, Any] = {
        "type": str(event_type),
        "timestamp": round(time.time(), 3),
        "utc": datetime.now(UTC).isoformat(),
    }
    for key, val in fields.items():
        if val is not None:
            event[key] = val
    try:
        cb(event)
    except Exception:
        pass


class PatchJobStatus(JobIdentity):
    sequence: Literal[1, 2] = 1
    status: Literal["running", "complete", "cancelled", "failed", "early_stopped"] = "running"
    proposal: PatchProposal | GenerateProposal | None = None
    errorCode: str | None = None
    partialQuestions: list[dict[str, Any]] | None = None
    passedCount: int | None = None
    totalSlots: int | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_early_fields(self, handler):
        data = handler(self)
        for key in ("partialQuestions", "passedCount", "totalSlots"):
            if key in data and data[key] is None:
                data.pop(key)
        return data


@dataclass(frozen=True)
class PatchStreamFrame:
    """Khung sự kiện chuẩn hóa để PatchJobRouter xuất ra SSE."""

    event: Literal["patch", "progress"]
    data_json: str
    event_id: int | None = None


@dataclass
class _Run:
    job: PatchJob | GenerateJob
    state: PatchJobStatus
    submission: tuple[UUID, str] | None
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    publishing: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task[None] | None = None
    deadline: asyncio.TimerHandle | None = None
    progress_history: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[dict[str, Any] | None]] = field(default_factory=set)


class PatchJobRunner:
    """Giữ sự kiện vòng đời và luồng tiến độ SSE trực tiếp cho mỗi job AI."""

    def __init__(
        self,
        provider: Provider[PatchJob | GenerateJob] | None,
        snapshot_is_current: SnapshotCheck[PatchJob | GenerateJob],
        store_pending: Callable[[PendingPatch | PendingGeneration], Awaitable[bool]],
        *,
        timeout_seconds: float,
        max_active: int,
        max_retained: int,
    ):
        if (
            not 1 <= max_active <= max_retained
            or not 0 < timeout_seconds <= MAX_EXTENDED_AI_SECONDS
        ):
            raise ValueError("Cấu hình số tác vụ hoặc thời hạn không hợp lệ.")
        self._provider = provider
        self._snapshot_is_current = snapshot_is_current
        self._store_pending = store_pending
        self._timeout_seconds = timeout_seconds
        self._max_active = max_active
        self._max_retained = max_retained
        self._runs: dict[UUID, _Run] = {}

    @property
    def active(self):
        return any(run.state.status == "running" for run in self._runs.values())

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
        self, job: PatchJob | GenerateJob, *, submission: tuple[UUID, str] | None = None
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

    def _record_progress(self, run: _Run, event: dict[str, Any]) -> None:
        if run.state.status != "running":
            return
        run.progress_history.append(event)
        for queue in tuple(run.subscribers):
            queue.put_nowait(event)

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

    def stream_events(
        self, owner_id: str, exam_id: UUID, job_id: UUID, *, after: int = 0
    ) -> AsyncIterator[PatchStreamFrame]:
        """Phát luồng SSE gồm trạng thái job (`patch`) và tiến độ (`progress`) tức thời."""
        run = self._owned(owner_id, exam_id, job_id)

        async def follow() -> AsyncIterator[PatchStreamFrame]:
            if run.state.sequence == 2:
                if after < 1:
                    for prior_ev in list(run.progress_history):
                        yield PatchStreamFrame(
                            event="progress",
                            data_json=json.dumps(prior_ev, ensure_ascii=False),
                        )
                if after < run.state.sequence:
                    yield PatchStreamFrame(
                        event="patch",
                        event_id=run.state.sequence,
                        data_json=run.state.model_dump_json(),
                    )
                return

            queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
            run.subscribers.add(queue)
            try:
                if run.state.sequence == 1 and after < 1:
                    yield PatchStreamFrame(
                        event="patch",
                        event_id=1,
                        data_json=run.state.model_dump_json(),
                    )
                if after < 1:
                    for prior_ev in list(run.progress_history):
                        yield PatchStreamFrame(
                            event="progress",
                            data_json=json.dumps(prior_ev, ensure_ascii=False),
                        )
                while not run.finished.is_set() or not queue.empty():
                    if run.finished.is_set() and queue.empty():
                        break
                    get_task = asyncio.create_task(queue.get())
                    wait_task = asyncio.create_task(run.finished.wait())
                    done, pending = await asyncio.wait(
                        {get_task, wait_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    if get_task in done:
                        ev = get_task.result()
                        if ev is None:
                            break
                        yield PatchStreamFrame(
                            event="progress",
                            data_json=json.dumps(ev, ensure_ascii=False),
                        )
                    else:
                        while not queue.empty():
                            ev = queue.get_nowait()
                            if ev is None:
                                break
                            yield PatchStreamFrame(
                                event="progress",
                                data_json=json.dumps(ev, ensure_ascii=False),
                            )
                        break
                if after < run.state.sequence:
                    yield PatchStreamFrame(
                        event="patch",
                        event_id=run.state.sequence,
                        data_json=run.state.model_dump_json(),
                    )
            finally:
                run.subscribers.discard(queue)

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
        proposal: PatchProposal | GenerateProposal | None = None,
        error_code: str | None = None,
        partial_questions: list[dict[str, Any]] | None = None,
        passed_count: int | None = None,
        total_slots: int | None = None,
    ) -> None:
        if run.state.status != "running":
            return
        if status in {"complete", "early_stopped"}:
            terminal_progress = {
                "type": status,
                "timestamp": round(time.time(), 3),
                "utc": datetime.now(UTC).isoformat(),
                "passedCount": passed_count
                if passed_count is not None
                else (
                    len(partial_questions)
                    if partial_questions is not None
                    else (
                        len(proposal.questions) if isinstance(proposal, GenerateProposal) else None
                    )
                ),
                "totalSlots": total_slots
                if total_slots is not None
                else (len(run.job.slots) if isinstance(run.job, GenerateJob) else None),
            }
            compact = {k: v for k, v in terminal_progress.items() if v is not None}
            run.progress_history.append(compact)
            for queue in tuple(run.subscribers):
                queue.put_nowait(compact)
        run.state = PatchJobStatus(
            jobId=run.job.jobId,
            examId=run.job.examId,
            baseRevision=run.job.baseRevision,
            sequence=2,
            status=status,
            proposal=proposal,
            errorCode=error_code,
            partialQuestions=partial_questions,
            passedCount=passed_count,
            totalSlots=total_slots,
        )
        if run.deadline is not None:
            run.deadline.cancel()
        for queue in tuple(run.subscribers):
            queue.put_nowait(None)
        run.finished.set()

    async def _run_extended_job(
        self,
        run: _Run,
        provider_fn: Provider[PatchJob | GenerateJob] | None,
        publish: Callable[[PendingPatch | PendingGeneration], Awaitable[bool]],
    ) -> None:
        """Chạy job mở rộng >900s (deep 1200s / extended 3600s) bảo toàn snapshot concurrency."""
        job = run.job
        validate_sources(job)
        if isinstance(job, GenerateJob):
            validate_generation_plan(job)
        else:
            validate_patch_job(job)
        if provider_fn is None:
            raise AIError("provider_unconfigured", "Chọn kết nối AI để gửi yêu cầu.")
        try:
            async with asyncio.timeout(self._timeout_seconds):
                if not await self._snapshot_is_current(job):
                    raise AIError("stale_snapshot", "Đề hoặc nguồn đã đổi. Hãy tải lại.")
                raw = await provider_fn(job)
                if len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
                    raise AIError("result_limit", "Phản hồi AI vượt giới hạn kích thước.")
                if isinstance(job, GenerateJob):
                    proposal_gen = validate_generation(job, raw)
                    if not await self._snapshot_is_current(job):
                        raise AIError("stale_snapshot", "Đề hoặc nguồn đã đổi trong lúc AI xử lý.")
                    if not await publish(PendingGeneration(job=job, proposal=proposal_gen)):
                        raise AIError(
                            "stale_snapshot",
                            "Đề, nguồn hoặc tác vụ đã đổi trước khi lưu bản xem trước.",
                        )
                else:
                    proposal_patch = validate_proposal(job, raw)
                    if not await self._snapshot_is_current(job):
                        raise AIError("stale_snapshot", "Đề hoặc nguồn đã đổi trong lúc AI xử lý.")
                    if not await publish(PendingPatch(job=job, proposal=proposal_patch)):
                        raise AIError(
                            "stale_snapshot",
                            "Đề, nguồn hoặc tác vụ đã đổi trước khi lưu bản xem trước.",
                        )
        except TimeoutError:
            raise AIError("timeout", "AI chưa trả kết quả trong thời hạn. Hãy thử lại.") from None

    async def _execute(self, run: _Run) -> None:
        async def publish(pending: PendingPatch | PendingGeneration) -> bool:
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

        captured_early: dict[str, Any] | None = None

        async def tracked_provider(current_job: Any) -> str:
            nonlocal captured_early
            if self._provider is None:
                raise AIError("provider_unconfigured", "Chọn kết nối AI để gửi yêu cầu.")
            raw = await self._provider(current_job)
            if isinstance(raw, str) and '"early_stopped"' in raw:
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("status") == "early_stopped":
                    captured_early = parsed
                    raise _EarlyStopCaptured(parsed)
            return raw

        token = _PROGRESS_CB.set(lambda ev: self._record_progress(run, ev))
        try:
            provider_to_use = None if self._provider is None else tracked_provider
            if self._timeout_seconds > MAX_AI_SECONDS:
                await self._run_extended_job(run, provider_to_use, publish)
            elif isinstance(run.job, GenerateJob):
                await prepare_generation(
                    run.job,
                    provider_to_use,
                    self._snapshot_is_current,
                    publish,
                    timeout_seconds=self._timeout_seconds,
                )
            else:
                await prepare_patch(
                    run.job,
                    provider_to_use,
                    self._snapshot_is_current,
                    publish,
                    timeout_seconds=self._timeout_seconds,
                )
        except _EarlyStopCaptured as stopped:
            payload = captured_early or stopped.payload
            questions = payload.get("questions") if isinstance(payload, dict) else []
            partial = list(questions) if isinstance(questions, list) else []
            raw_total = payload.get("totalSlots") if isinstance(payload, dict) else None
            total = (
                int(raw_total)
                if raw_total is not None
                else (len(run.job.slots) if isinstance(run.job, GenerateJob) else len(partial))
            )
            raw_passed = payload.get("passedCount") if isinstance(payload, dict) else None
            passed = int(raw_passed) if raw_passed is not None else len(partial)
            self._finish(
                run,
                "early_stopped",
                partial_questions=partial,
                passed_count=passed,
                total_slots=total,
            )
        except asyncio.CancelledError:
            self._finish(run, "cancelled")
            raise
        except AIError as error:
            self._finish(run, "failed", error_code=error.code)
        except Exception:
            logger.error("Lỗi nội bộ khi chạy đề xuất, job_id=%s", run.job.jobId)
            self._finish(run, "failed", error_code="internal_error")
        finally:
            _PROGRESS_CB.reset(token)
