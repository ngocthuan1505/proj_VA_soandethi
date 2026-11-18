"""Hợp đồng Sinh, Sửa và Kiểm trước bước xác nhận."""

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

Revision = Annotated[int, Field(ge=1)]
LocatorIndex = Annotated[int, Field(ge=1)]
MAX_BLOCK_TEXT = 12000
BlockText = Annotated[str, Field(min_length=1, max_length=MAX_BLOCK_TEXT)]
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


class PatchQuestionContext(ContractModel):
    stem: BlockText
    options: Annotated[tuple[BlockText, ...], Field(max_length=4)]


class BlockTarget(ContractModel):
    questionId: UUID
    questionVersion: Revision
    blockId: UUID
    field: Literal["explanation"]
    text: BlockText
    selection: tuple[int, int] | None = None
    context: PatchQuestionContext | None = None


class JobIdentity(ContractModel):
    jobId: UUID
    examId: UUID
    baseRevision: Revision


class AIJob(JobIdentity):
    ownerId: str
    sources: Annotated[tuple[SourceFragment, ...], Field(max_length=12)] = ()
    requireEvidence: bool = False


class PatchJob(AIJob):
    request: Annotated[str, Field(min_length=1, max_length=4000)]
    targets: Annotated[tuple[BlockTarget, ...], Field(min_length=1, max_length=12)]


class TextEdit(ContractModel):
    op: Literal["replace"]
    blockId: UUID
    content: BlockText


class PatchProposal(JobIdentity):
    edits: Annotated[tuple[TextEdit, ...], Field(min_length=1, max_length=12)]
    evidence: Annotated[tuple[Evidence, ...], Field(max_length=12)]
    message: Annotated[str, Field(min_length=1, max_length=1000)]


class AIError(ValueError):
    def __init__(self, code: str, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


# Đọc snapshot hiện tại bằng quyền của chủ sở hữu đề. Repository trả False nếu đề/khối/nguồn đã đổi.
type SnapshotCheck[JobT: AIJob] = Callable[[JobT], Awaitable[bool]]


def read_patch_context(question: Mapping[str, object]) -> PatchQuestionContext | None:
    stem, options = question.get("stem"), question.get("options", [])
    if not isinstance(stem, str) or not stem.strip() or not isinstance(options, list):
        return None
    try:
        context = PatchQuestionContext(stem=stem, options=tuple(options))
    except ValidationError:
        return None
    # shortcut: dùng bản chữ tối đa một khối; mở rộng khi hỗ trợ ngữ liệu hoặc hình riêng.
    if len(context.stem) + sum(map(len, context.options)) > MAX_BLOCK_TEXT:
        return None
    return context


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


def validate_locator(locator: Locator) -> None:
    if (locator.kind == "region") != (locator.regionId is not None):
        raise AIError("invalid_locator", "Vị trí nguồn chưa đủ thông tin.")


def validate_sources(job: AIJob) -> None:
    if not job.ownerId.strip():
        raise AIError("invalid_request", "Yêu cầu thiếu chủ sở hữu đề.")
    if sum(len(source.text) for source in job.sources) > 50000:
        raise AIError("source_limit", "Mỗi lượt dùng tối đa 50.000 ký tự nguồn.")
    for source in job.sources:
        if source.ownerId != job.ownerId:
            raise AIError("forbidden_source", "Nguồn nằm ngoài phạm vi được phép dùng.")
        validate_locator(source.locator)
        if not source.text.strip():
            raise AIError("missing_source", "Đoạn nguồn chưa có văn bản để đối chiếu.")
    if job.requireEvidence and not job.sources:
        raise AIError("missing_source", "Chọn nguồn trước khi yêu cầu kết quả có căn cứ.")


def validate_patch_job(job: PatchJob) -> None:
    if not job.request.strip():
        raise AIError("invalid_request", "Yêu cầu sửa còn thiếu nội dung.")
    if len({target.blockId for target in job.targets}) != len(job.targets):
        raise AIError("invalid_scope", "Vùng chọn bị lặp.")
    for target in job.targets:
        selection_parts(target)


MATH_DELIMITERS = re.compile(r"(?<!\\)(?:\\\\)*?(\$\$?|\\[()[\]])")
MATH_STRUCTURE = re.compile(
    r"\\verb\*?(?P<literal>[^A-Za-z\s]).*?(?P=literal)"
    r"|\\(?P<environment>begin|end)\s*\{(?P<name>[^{}]+)\}"
    r"|\\[A-Za-z]+|\\[\s\S]|%[^\r\n]*|[{}]"
)


def validate_math_structure(latex: str) -> None:
    stack: list[tuple[str, str]] = []
    for token in MATH_STRUCTURE.finditer(latex):
        value = token.group()
        environment, name = token.group("environment", "name")
        if environment == "begin":
            stack.append(("environment", name))
        elif environment == "end":
            if not stack or stack.pop() != ("environment", name):
                raise AIError("invalid_math", "Môi trường công thức mở và đóng không khớp.")
        elif value == "{":
            stack.append(("group", ""))
        elif value == "}":
            if not stack or stack.pop() != ("group", ""):
                raise AIError("invalid_math", "Ngoặc nhóm trong công thức không khớp.")
        elif value in (r"\begin", r"\end", r"\verb"):
            raise AIError(
                "invalid_math", "Lệnh môi trường hoặc văn bản nguyên dạng chưa đủ cú pháp."
            )
    if stack:
        raise AIError("invalid_math", "Công thức còn thiếu ngoặc nhóm hoặc lệnh đóng môi trường.")


def validate_math_markers(text: str) -> None:
    # shortcut: kiểm cấu trúc, chưa biên dịch đầy đủ lệnh/đối số theo renderer.
    closing = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}
    pending = None
    start = 0
    for match in MATH_DELIMITERS.finditer(text):
        delimiter = match.group(1)
        if pending:
            if delimiter != pending:
                raise AIError("invalid_math", "Dấu mở và đóng công thức không khớp.")
            validate_math_structure(text[start : match.start(1)])
            pending = None
        elif delimiter in closing:
            pending = closing[delimiter]
            start = match.end(1)
        else:
            raise AIError("invalid_math", "Công thức thiếu dấu mở.")
    if pending:
        raise AIError("invalid_math", "Công thức thiếu dấu đóng.")


def read_result[ResultT: JobIdentity](job: AIJob, raw: str, schema: type[ResultT]) -> ResultT:
    try:
        result = schema.model_validate_json(raw)
    except ValidationError:
        raise AIError("invalid_result", "Phản hồi AI sai cấu trúc.") from None
    if (result.jobId, result.examId, result.baseRevision) != (
        job.jobId,
        job.examId,
        job.baseRevision,
    ):
        raise AIError("wrong_job", "Phản hồi không khớp tác vụ hoặc phiên bản đề.")
    return result


def validate_ai_text(text: str) -> None:
    if not text.strip() or "```" in text:
        raise AIError("invalid_result", "Văn bản AI còn thiếu hoặc chứa khối mã.")
    validate_math_markers(text)


def validate_proposal(job: PatchJob, raw: str) -> PatchProposal:
    proposal = read_result(job, raw, PatchProposal)
    targets = {target.blockId: target for target in job.targets}
    seen: set[UUID] = set()
    for edit in proposal.edits:
        target = targets.get(edit.blockId)
        if target is None or edit.blockId in seen:
            raise AIError("invalid_scope", "Đề xuất sửa ngoài vùng chọn hoặc lặp khối.")
        seen.add(edit.blockId)
        if edit.content == target.text:
            raise AIError("invalid_result", "Đề xuất chưa thay đổi văn bản.")
        prefix, suffix = selection_parts(target)
        if (
            len(edit.content) < len(prefix) + len(suffix)
            or not edit.content.startswith(prefix)
            or not edit.content.endswith(suffix)
        ):
            raise AIError("invalid_scope", "Đề xuất thay đổi chữ nằm ngoài vùng chọn.")
        validate_ai_text(edit.content)

    validate_evidence(job, proposal.evidence)
    return proposal


def validate_evidence(
    job: AIJob, evidence_items: tuple[Evidence, ...], *, allow_missing: bool = False
) -> None:
    if job.requireEvidence and not evidence_items and not allow_missing:
        raise AIError("missing_evidence", "Đề xuất chưa có trích dẫn để đối chiếu.")
    for evidence in evidence_items:
        quote = " ".join(evidence.quote.split())
        if len(quote) < 8 or not any(
            source.sourceId == evidence.sourceId
            and source.sourceVersion == evidence.sourceVersion
            and source.locator == evidence.locator
            and quote in " ".join(source.text.split())
            for source in job.sources
        ):
            raise AIError("invalid_evidence", "Trích dẫn không khớp phiên bản hoặc vị trí nguồn.")
