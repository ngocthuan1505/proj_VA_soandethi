"""Hợp đồng cho đề xuất sửa văn bản từ AI trước bước xác nhận."""

import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

Revision = Annotated[int, Field(ge=1)]
LocatorIndex = Annotated[int, Field(ge=1)]
BlockText = Annotated[str, Field(min_length=1, max_length=12000)]
Quote = Annotated[str, Field(min_length=8, max_length=1000)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)


class Locator(ContractModel):
    kind: Literal["page", "passage", "region"]
    index: LocatorIndex
    regionId: Annotated[str, Field(min_length=1, max_length=128)] | None = None


class Evidence(ContractModel):
    sourceId: UUID
    sourceVersion: Revision
    locator: Locator
    quote: Quote


class SourceFragment(ContractModel):
    ownerId: str
    sourceId: UUID
    sourceVersion: Revision
    locator: Locator
    text: BlockText


class BlockTarget(ContractModel):
    questionId: UUID
    questionVersion: Revision
    blockId: UUID
    field: Literal["explanation"]
    text: BlockText
    selection: tuple[int, int] | None = None


class PatchJob(ContractModel):
    ownerId: str
    jobId: UUID
    examId: UUID
    baseRevision: Revision
    request: Annotated[str, Field(min_length=1, max_length=4000)]
    targets: Annotated[tuple[BlockTarget, ...], Field(min_length=1, max_length=12)]
    sources: Annotated[tuple[SourceFragment, ...], Field(max_length=12)] = ()
    requireEvidence: bool = False


class TextEdit(ContractModel):
    op: Literal["replace"]
    blockId: UUID
    content: BlockText


class PatchProposal(ContractModel):
    jobId: UUID
    examId: UUID
    baseRevision: Revision
    edits: Annotated[tuple[TextEdit, ...], Field(min_length=1, max_length=12)]
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=12)]
    message: Annotated[str, Field(min_length=1, max_length=1000)]


class AIError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# Đọc snapshot hiện tại bằng quyền của chủ sở hữu đề. Repository trả False nếu đề/khối/nguồn đã đổi.
SnapshotCheck = Callable[[PatchJob], Awaitable[bool]]


def selection_parts(target: BlockTarget) -> tuple[str, str]:
    if target.selection is None:
        return "", ""
    # Offset từ editor JavaScript tính theo đơn vị UTF-16.
    start, end = target.selection
    text = target.text.encode("utf-16-le")
    if not 0 <= start < end <= len(text) // 2:
        raise AIError("invalid_scope", "Vùng chọn không còn hợp lệ. Hãy chọn lại.")
    try:
        text[start * 2 : end * 2].decode("utf-16-le")
        return text[: start * 2].decode("utf-16-le"), text[end * 2 :].decode("utf-16-le")
    except UnicodeDecodeError:
        raise AIError("invalid_scope", "Vùng chọn cắt ngang một ký tự. Hãy chọn lại.") from None


def validate_job(job: PatchJob) -> None:
    if not job.ownerId or not job.request.strip():
        raise AIError("invalid_request", "Yêu cầu sửa còn thiếu nội dung.")
    if len({target.blockId for target in job.targets}) != len(job.targets):
        raise AIError("invalid_scope", "Vùng chọn bị lặp.")
    if sum(len(source.text) for source in job.sources) > 50000:
        raise AIError("source_limit", "Mỗi lượt dùng tối đa 50.000 ký tự nguồn.")
    for source in job.sources:
        if source.ownerId != job.ownerId:
            raise AIError("forbidden_source", "Nguồn nằm ngoài phạm vi được phép dùng.")
        locator = source.locator
        if (locator.kind == "region") != (locator.regionId is not None):
            raise AIError("invalid_locator", "Vị trí nguồn chưa đủ thông tin.")
    if job.requireEvidence and not job.sources:
        raise AIError("missing_source", "Chọn nguồn trước khi yêu cầu sửa có căn cứ.")
    for target in job.targets:
        selection_parts(target)


def validate_math_markers(text: str) -> None:
    # shortcut: chỉ kiểm cặp dấu công thức, bổ sung parser khi nhóm chốt renderer Python.
    delimiters = re.findall(r"(?<!\\)(?:\\\\)*?(\$\$?|\\[()[\]])", text)
    closing = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}
    pending = None
    for delimiter in delimiters:
        if pending:
            if delimiter != pending:
                raise AIError("invalid_math", "Dấu mở và đóng công thức không khớp.")
            pending = None
        elif delimiter in closing:
            pending = closing[delimiter]
        else:
            raise AIError("invalid_math", "Công thức thiếu dấu mở.")
    if pending:
        raise AIError("invalid_math", "Công thức thiếu dấu đóng.")


def validate_proposal(job: PatchJob, raw: str) -> PatchProposal:
    try:
        proposal = PatchProposal.model_validate_json(raw)
    except ValidationError:
        raise AIError("invalid_result", "Phản hồi AI sai cấu trúc đề xuất sửa.") from None
    if (proposal.jobId, proposal.examId, proposal.baseRevision) != (
        job.jobId,
        job.examId,
        job.baseRevision,
    ):
        raise AIError("wrong_job", "Phản hồi không khớp lượt sửa hoặc phiên bản đề.")

    targets = {target.blockId: target for target in job.targets}
    seen: set[UUID] = set()
    for edit in proposal.edits:
        target = targets.get(edit.blockId)
        if target is None or edit.blockId in seen:
            raise AIError("invalid_scope", "Đề xuất sửa ngoài vùng chọn hoặc lặp khối.")
        seen.add(edit.blockId)
        if not edit.content.strip() or "```" in edit.content or edit.content == target.text:
            raise AIError("invalid_result", "Đề xuất cần thay đổi văn bản và không chứa khối mã.")
        prefix, suffix = selection_parts(target)
        if (
            len(edit.content) < len(prefix) + len(suffix)
            or not edit.content.startswith(prefix)
            or not edit.content.endswith(suffix)
        ):
            raise AIError("invalid_scope", "Đề xuất thay đổi chữ nằm ngoài vùng chọn.")
        validate_math_markers(edit.content)

    if job.requireEvidence and not proposal.evidence:
        raise AIError("missing_evidence", "Đề xuất chưa có trích dẫn để đối chiếu.")
    for evidence in proposal.evidence:
        quote = " ".join(evidence.quote.split())
        if len(quote) < 8 or not any(
            source.sourceId == evidence.sourceId
            and source.sourceVersion == evidence.sourceVersion
            and source.locator == evidence.locator
            and quote in " ".join(source.text.split())
            for source in job.sources
        ):
            raise AIError("invalid_evidence", "Trích dẫn không khớp phiên bản hoặc vị trí nguồn.")
    return proposal
