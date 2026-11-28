"""Chính sách kiểm soát quyền học liệu và trạng thái thu hồi trong SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from mach_backend.ai_contract import AIError

CITABLE_LICENSE_STATUSES: frozenset[str] = frozenset({"allowed", "teacher_owned"})

_SOURCE_ID_FIELDS: tuple[str, ...] = (
    "docId",
    "sourceId",
    "id",
    "curriculumSourceId",
    "originSourceId",
    "curriculumId",
)


def _get_field(item: Any, key: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(key)
    return getattr(item, key, None)


def extract_source_candidate_ids(item: Any) -> tuple[str, ...]:
    """Trích các định danh nguồn có thể có (docId, sourceId, id, curriculumSourceId...)."""
    if isinstance(item, str):
        cleaned = item.strip()
        return (cleaned,) if cleaned else ()
    seen: list[str] = []
    seen_set: set[str] = set()
    for field in _SOURCE_ID_FIELDS:
        raw = _get_field(item, field)
        if raw is None:
            continue
        cleaned = str(raw).strip()
        if cleaned and cleaned not in seen_set:
            seen.append(cleaned)
            seen_set.add(cleaned)
    return tuple(seen)


def embedded_license_status(item: Any) -> str | None:
    """Đọc trạng thái quyền gắn sẵn trên dict/snapshot nguồn (nếu có)."""
    if isinstance(item, str):
        return None
    for key in ("licenseStatus", "license_status"):
        raw = _get_field(item, key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().casefold()
    return None


def lookup_curriculum_license_statuses(
    db: sqlite3.Connection | None,
    candidate_ids: Iterable[str],
) -> dict[str, str]:
    """Tra license_status thực tế từ bảng curriculum_sources cho danh sách ID."""
    if db is None:
        return {}
    unique_ids: list[str] = []
    seen: set[str] = set()
    for cid in candidate_ids:
        cleaned = str(cid or "").strip()
        if cleaned and cleaned not in seen:
            unique_ids.append(cleaned)
            seen.add(cleaned)
    if not unique_ids:
        return {}

    statuses: dict[str, str] = {}
    chunk_size = 400
    for start in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[start : start + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        try:
            rows = db.execute(
                f"SELECT id, license_status FROM curriculum_sources WHERE id IN ({placeholders})",
                tuple(chunk),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        for row in rows:
            row_id = str(row[0] or "").strip()
            row_status = str(row[1] or "").strip().casefold()
            if row_id:
                statuses[row_id] = row_status
    return statuses


def collect_status_map(
    db: sqlite3.Connection | None,
    items: Iterable[Any],
) -> dict[str, str]:
    """Thu thập toàn bộ candidate ID từ tập nguồn và tra 1 lần từ curriculum_sources."""
    if db is None:
        return {}
    ids: list[str] = []
    for item in items:
        if item is None:
            continue
        ids.extend(extract_source_candidate_ids(item))
    return lookup_curriculum_license_statuses(db, ids)


def is_source_revoked(
    item: Any,
    *,
    db: sqlite3.Connection | None = None,
    status_map: Mapping[str, str] | None = None,
) -> bool:
    """Trả True nếu nguồn bị thu hồi hoặc hạn chế quyền trích dẫn.

    Chỉ chặn khi ID thực sự có trong curriculum_sources với trạng thái không thuộc
    CITABLE_LICENSE_STATUSES (ghi đè cả bản chụp cũ licenseStatus='allowed'),
    hoặc bản thân snapshot mang licenseStatus/license_status không hợp lệ.
    Tài liệu cục bộ GV tự tải lên không có bản ghi thu hồi vẫn được phép dùng.
    """
    if item is None:
        return False
    candidate_ids = extract_source_candidate_ids(item)
    resolved_map = (
        status_map
        if status_map is not None
        else lookup_curriculum_license_statuses(db, candidate_ids)
    )
    for cid in candidate_ids:
        if cid in resolved_map:
            if resolved_map[cid] not in CITABLE_LICENSE_STATUSES:
                return True

    embedded = embedded_license_status(item)
    if embedded is not None and embedded not in CITABLE_LICENSE_STATUSES:
        return True
    return False


def require_citable_source(
    item: Any,
    *,
    db: sqlite3.Connection | None = None,
    status_map: Mapping[str, str] | None = None,
) -> None:
    """Ném AIError(source_license_restricted, 403) nếu nguồn đã bị thu hồi hoặc hạn chế."""
    if is_source_revoked(item, db=db, status_map=status_map):
        raise AIError(
            "source_license_restricted",
            "Nguồn học liệu đã bị thu hồi hoặc chưa được phép trích dẫn cho AI.",
            http_status=403,
        )


def filter_allowed_docs_for_hybrid[DocEntryT: tuple[Any, ...]](
    db: sqlite3.Connection | None,
    allowed_docs: Sequence[DocEntryT],
) -> list[DocEntryT]:
    """Loại bỏ khỏi allowed_docs các doc_id có bản ghi thu hồi trong curriculum_sources."""
    if not allowed_docs:
        return []
    status_map = lookup_curriculum_license_statuses(db, [entry[0] for entry in allowed_docs])
    if not status_map:
        return list(allowed_docs)
    return [
        entry
        for entry in allowed_docs
        if str(entry[0]).strip() not in status_map
        or status_map[str(entry[0]).strip()] in CITABLE_LICENSE_STATUSES
    ]
