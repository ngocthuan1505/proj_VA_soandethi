"""Tham chiếu nguồn dùng chung cho các thao tác AI."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, ValidationError

from mach_backend.ai_contract import (
    AIError,
    ContractModel,
    Locator,
    Revision,
    SourceFragment,
    validate_locator,
)

type WireUUID = Annotated[UUID, Field(strict=False)]
type SourceKey = tuple[UUID, Locator]


class SelectedSource(ContractModel):
    sourceId: WireUUID
    sourceVersion: Revision
    locator: Locator

    @property
    def key(self) -> SourceKey:
        return self.sourceId, self.locator


class SourceSelection(ContractModel):
    consent: bool = False
    sources: Annotated[list[SelectedSource], Field(max_length=12)] = Field(default_factory=list)
    requireEvidence: bool = False


def selected_source_keys(request: SourceSelection) -> tuple[SourceKey, ...]:
    if not request.consent:
        raise AIError("consent_required", "Xác nhận dùng AI trước khi gửi.")
    keys = tuple(source.key for source in request.sources)
    if len(set(keys)) != len(keys):
        raise AIError("invalid_locator", "Vị trí nguồn bị chọn trùng.")
    for _, locator in keys:
        validate_locator(locator)
    if request.requireEvidence and not keys:
        raise AIError("missing_source", "Chọn nguồn trước khi yêu cầu kết quả có căn cứ.")
    return keys


def read_selected_sources(
    owner_id: str, request: SourceSelection, sources: tuple[SourceFragment, ...]
) -> tuple[SourceFragment, ...]:
    selected = []
    for choice in request.sources:
        matches = [
            source
            for source in sources
            if source.ownerId == owner_id and (source.sourceId, source.locator) == choice.key
        ]
        if len(matches) != 1:
            raise AIError("source_not_found", "Không tìm thấy đoạn nguồn đã chọn.")
        if matches[0].sourceVersion != choice.sourceVersion:
            raise AIError("stale_snapshot", "Nguồn đã đổi. Hãy tải lại.")
        selected.append(matches[0])
    return tuple(selected)


def workspace_page_sources(exam, owner_id: str, keys: tuple[SourceKey, ...]):
    """Resolve selected pages from the current exam snapshot."""
    chosen = {
        (str(source_id), locator.index) for source_id, locator in keys if locator.kind == "page"
    }
    sources = []
    for doc in exam.get("docs", []):
        doc_id = doc.get("id")
        if not any(source_id == doc_id for source_id, _ in chosen):
            continue
        pages = doc.get("pages") or [{"number": 1, "text": doc.get("text", "")}]
        for page in pages:
            if (doc_id, page.get("number")) not in chosen:
                continue
            text = page.get("text")
            if not isinstance(text, str) or not text.strip():
                raise AIError("invalid_source", "Trang nguồn không có văn bản hợp lệ.")
            if len(text) > 12000:
                raise AIError("source_limit", "Trang nguồn vượt 12.000 ký tự.")
            try:
                sources.append(
                    SourceFragment(
                        ownerId=owner_id,
                        sourceId=UUID(doc_id),
                        sourceVersion=doc.get("version", 1),
                        locator=Locator(kind="page", index=page["number"]),
                        text=text,
                    )
                )
            except (ValidationError, ValueError):
                raise AIError("invalid_source", "Trang nguồn đang lưu không hợp lệ.") from None
    if sum(len(source.text) for source in sources) > 12000:
        raise AIError("source_limit", "Chọn các trang có tổng cộng tối đa 12.000 ký tự.")
    return tuple(sources)
