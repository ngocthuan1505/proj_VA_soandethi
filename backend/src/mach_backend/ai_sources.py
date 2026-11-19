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
from mach_backend.lesson_catalog import lesson_catalog

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
    if not chosen:
        return ()
    catalog = {collection["id"]: collection for collection in lesson_catalog()}
    sources = []
    for doc in exam.get("docs", []):
        doc_id = doc.get("id")
        if not any(source_id == doc_id for source_id, _ in chosen):
            continue
        license_status = str(
            doc.get("licenseStatus") or doc.get("license_status") or "allowed"
        ).strip()
        if license_status in {"restricted", "pending_review"}:
            raise AIError(
                "source_license_restricted",
                "Nguồn chưa có quyền dùng cho AI hoặc đang bị hạn chế.",
                http_status=403,
            )
        collection = catalog.get(doc_id)
        if collection is None:
            if doc.get("catalog") is True:
                raise AIError("source_not_found", "Học liệu đã chọn không còn trong thư viện.")
            pages = doc.get("pages") or [{"number": 1, "text": doc.get("text", "")}]
            version = doc.get("version", 1)
        else:
            if doc.get("version", 1) != collection["version"]:
                raise AIError("stale_snapshot", "Học liệu đã đổi. Hãy chọn lại bài trong thư viện.")
            pages = [
                {
                    "number": lesson["number"],
                    "text": (
                        f"Bài {lesson['number']}. {lesson['title']}\n{lesson['text']}\n"
                        f"Mục tiêu: {lesson['outcome']}"
                    ),
                }
                for lesson in collection["lessons"]
            ]
            version = collection["version"]
        for page in pages:
            number = page.get("number")
            if type(number) is not int or (doc_id, number) not in chosen:
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
                        sourceVersion=version,
                        locator=Locator(kind="page", index=number),
                        text=text,
                    )
                )
            except (ValidationError, ValueError):
                raise AIError("invalid_source", "Trang nguồn đang lưu không hợp lệ.") from None
    if sum(len(source.text) for source in sources) > 12000:
        raise AIError("source_limit", "Chọn các trang có tổng cộng tối đa 12.000 ký tự.")
    return tuple(sources)
