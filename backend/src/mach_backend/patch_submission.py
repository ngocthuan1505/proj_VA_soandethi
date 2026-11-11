"""Tạo snapshot sửa lời giải từ đề và các đoạn nguồn thuộc phiên đang dùng."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field

from mach_backend.ai_contract import (
    MAX_BLOCK_TEXT,
    AIError,
    BlockTarget,
    ContractModel,
    Locator,
    PatchJob,
    Revision,
    SourceFragment,
    validate_locator,
    validate_patch_job,
    validate_sources,
)
from mach_backend.patch_confirmation import ExamSnapshot, changed_snapshot

type WireUUID = Annotated[UUID, Field(strict=False)]
type SourceKey = tuple[UUID, Locator]
type Selection = Annotated[list[Annotated[int, Field(ge=0)]], Field(min_length=2, max_length=2)]


class SelectedBlock(ContractModel):
    questionId: WireUUID
    questionVersion: Revision
    blockId: WireUUID
    selection: Selection | None = None


class SelectedSource(ContractModel):
    sourceId: WireUUID
    sourceVersion: Revision
    locator: Locator

    @property
    def key(self) -> SourceKey:
        return self.sourceId, self.locator


class PatchSubmission(ContractModel):
    requestId: WireUUID
    baseRevision: Revision
    request: Annotated[str, Field(min_length=1, max_length=4000)]
    consent: bool = False
    targets: Annotated[list[SelectedBlock], Field(min_length=1, max_length=12)]
    sources: Annotated[list[SelectedSource], Field(max_length=12)] = Field(default_factory=list)
    requireEvidence: bool = False


@dataclass(frozen=True)
class PatchInputs:
    owner_id: str
    exam: ExamSnapshot
    sources: tuple[SourceFragment, ...]


# Đọc đề và đúng các vị trí nguồn hiện hành bằng một snapshot của repository.
# Không tra phiên bản cũ theo dữ liệu trình duyệt.
type ReadPatchInputs = Callable[[str, UUID, tuple[SourceKey, ...]], Awaitable[PatchInputs | None]]


def selected_source_keys(request: PatchSubmission) -> tuple[SourceKey, ...]:
    if not request.consent:
        raise AIError("consent_required", "Xác nhận dùng AI cho lượt sửa này trước khi gửi.")
    keys = tuple(source.key for source in request.sources)
    if len(set(keys)) != len(keys):
        raise AIError("invalid_locator", "Vị trí nguồn bị chọn trùng.")
    for _, locator in keys:
        validate_locator(locator)
    if request.requireEvidence and not keys:
        raise AIError("missing_source", "Chọn nguồn trước khi yêu cầu kết quả có căn cứ.")
    return keys


def build_patch_job(
    owner_id: str, exam_id: UUID, request: PatchSubmission, inputs: PatchInputs | None
) -> PatchJob:
    if inputs is None or inputs.owner_id != owner_id or inputs.exam.get("id") != str(exam_id):
        raise AIError("exam_not_found", "Không tìm thấy đề có thể sửa.")
    exam = inputs.exam
    revision = exam.get("revision")
    if type(revision) is not int or revision != request.baseRevision:
        raise changed_snapshot()
    if exam.get("draftStatus", "draft") not in ("draft", "ready"):
        raise AIError("exam_read_only", "Trạng thái hiện tại của đề không cho phép sửa.")
    questions = exam.get("questions")
    if not isinstance(questions, list):
        raise changed_snapshot()

    targets: list[BlockTarget] = []
    for selected in request.targets:
        matches = [
            q for q in questions if isinstance(q, dict) and q.get("id") == str(selected.questionId)
        ]
        if len(matches) != 1:
            raise changed_snapshot()
        q = matches[0]
        version = q.get("v")
        block_ids = q.get("blockIds")
        if (
            type(version) is not int
            or version != selected.questionVersion
            or not isinstance(block_ids, dict)
            or block_ids.get("explanation") != str(selected.blockId)
        ):
            raise changed_snapshot()
        text = q.get("explanation")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_BLOCK_TEXT:
            raise AIError("invalid_scope", "Hãy chọn lời giải đã có nội dung trong phạm vi hỗ trợ.")
        offsets = selected.selection
        targets.append(
            BlockTarget(
                questionId=selected.questionId,
                questionVersion=version,
                blockId=selected.blockId,
                field="explanation",
                text=text,
                selection=(offsets[0], offsets[1]) if offsets is not None else None,
            )
        )

    sources: list[SourceFragment] = []
    for selected_source in request.sources:
        matches = [
            source
            for source in inputs.sources
            if source.ownerId == owner_id
            and (source.sourceId, source.locator) == selected_source.key
        ]
        if len(matches) != 1:
            raise AIError("source_not_found", "Không tìm thấy đoạn nguồn đã chọn.")
        if matches[0].sourceVersion != selected_source.sourceVersion:
            raise changed_snapshot()
        sources.append(matches[0])

    job = PatchJob(
        jobId=uuid4(),
        examId=exam_id,
        baseRevision=revision,
        ownerId=owner_id,
        request=request.request,
        targets=tuple(targets),
        sources=tuple(sources),
        requireEvidence=bool(sources) or request.requireEvidence,
    )
    validate_patch_job(job)
    validate_sources(job)
    return job
