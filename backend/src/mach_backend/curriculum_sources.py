"""Quản lý nguồn học liệu theo lớp/môn/bộ sách/tập/chương/bài có quyền dùng và truy vết."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from mach_backend.ai_contract import AIError

type LicenseStatus = Literal["allowed", "teacher_owned", "pending_review", "restricted"]
type ConnectCallable = Callable[[], AbstractContextManager[sqlite3.Connection]]
type ConnectOrDbPath = Path | str | ConnectCallable
type OwnerResolver = Callable[[Request], str]

LICENSE_STATUSES: tuple[LicenseStatus, ...] = (
    "allowed",
    "teacher_owned",
    "pending_review",
    "restricted",
)
CITABLE_LICENSE_STATUSES: frozenset[str] = frozenset({"allowed", "teacher_owned"})
MAX_EXCERPT_LENGTH = 50_000

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS curriculum_sources (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    grade INTEGER NOT NULL CHECK (grade >= 1 AND grade <= 12),
    subject TEXT NOT NULL,
    series TEXT NOT NULL DEFAULT '',
    volume TEXT NOT NULL DEFAULT '',
    chapter TEXT NOT NULL DEFAULT '',
    lesson TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    license_status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (license_status IN ('allowed', 'teacher_owned', 'pending_review', 'restricted')),
    license_note TEXT NOT NULL DEFAULT '',
    source_origin TEXT NOT NULL DEFAULT '',
    locator TEXT NOT NULL DEFAULT '',
    content_excerpt TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_curriculum_sources_owner_hierarchy
    ON curriculum_sources (owner_id, grade, subject, series, volume, chapter, lesson);
CREATE INDEX IF NOT EXISTS idx_curriculum_sources_owner_license
    ON curriculum_sources (owner_id, license_status);
"""

_COLUMNS = (
    "id",
    "owner_id",
    "grade",
    "subject",
    "series",
    "volume",
    "chapter",
    "lesson",
    "title",
    "license_status",
    "license_note",
    "source_origin",
    "locator",
    "content_excerpt",
    "sha256",
    "created_at",
    "updated_at",
)
_SELECT_SQL = "SELECT " + ", ".join(_COLUMNS) + " FROM curriculum_sources"


class CurriculumSourceError(AIError):
    """Lỗi nghiệp vụ khi quản lý hoặc trích dẫn nguồn học liệu."""


def _validate_grade_int(value: Any) -> Any:
    """Đảm bảo khối lớp là số nguyên thực thụ (từ chối bool và float)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Khối lớp phải là số nguyên từ 1 đến 12.")
    return value


def _normalize_metadata(value: str) -> str:
    """Chuẩn hóa NFC và cắt khoảng trắng hai đầu cho trường metadata."""
    return unicodedata.normalize("NFC", value).strip()


def _clean_metadata_field(value: str, field_name: str | None) -> str:
    """Làm sạch chuỗi metadata và chặn giá trị rỗng cho trường bắt buộc."""
    cleaned = _normalize_metadata(value)
    if field_name in {"subject", "title"} and not cleaned:
        raise ValueError(f"Trường '{field_name}' không được để trống.")
    return cleaned


def _source_not_found() -> CurriculumSourceError:
    return CurriculumSourceError(
        "source_not_found",
        "Không tìm thấy nguồn học liệu trong phạm vi quyền sở hữu hiện tại.",
        http_status=404,
    )


def _normalize_search(value: str) -> str:
    """Chuẩn hóa NFC và gấp chữ để so khớp tiếng Việt không phân biệt hoa thường."""
    return unicodedata.normalize("NFC", value).strip().casefold()


def compute_source_sha256(payload: Mapping[str, Any]) -> str:
    """Tính mã băm SHA-256 ổn định từ nội dung và metadata nguồn học liệu."""
    canonical = {
        "grade": payload["grade"],
        "subject": payload["subject"],
        "series": payload["series"],
        "volume": payload["volume"],
        "chapter": payload["chapter"],
        "lesson": payload["lesson"],
        "title": payload["title"],
        "license_status": payload["license_status"],
        "license_note": payload["license_note"],
        "source_origin": payload["source_origin"],
        "locator": payload["locator"],
        "content_excerpt": payload["content_excerpt"],
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CurriculumSourceCreate(BaseModel):
    """Payload tạo mới nguồn học liệu theo lớp/môn/bộ sách/tập/chương/bài."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    grade: Annotated[int, Field(ge=1, le=12)]
    subject: Annotated[str, Field(min_length=1, max_length=200)]
    series: str = Field(
        default="",
        max_length=200,
        validation_alias=AliasChoices("series", "book"),
    )
    volume: Annotated[str, Field(max_length=100)] = ""
    chapter: Annotated[str, Field(max_length=300)] = ""
    lesson: Annotated[str, Field(max_length=300)] = ""
    title: Annotated[str, Field(min_length=1, max_length=400)]
    license_status: LicenseStatus = Field(
        default="pending_review",
        validation_alias=AliasChoices("license_status", "licenseStatus"),
    )
    license_note: str = Field(
        default="",
        max_length=1000,
        validation_alias=AliasChoices("license_note", "licenseNote"),
    )
    source_origin: str = Field(
        default="",
        max_length=500,
        validation_alias=AliasChoices("source_origin", "sourceOrigin"),
    )
    locator: Annotated[str, Field(max_length=300)] = ""
    content_excerpt: str = Field(
        default="",
        max_length=MAX_EXCERPT_LENGTH,
        validation_alias=AliasChoices("content_excerpt", "contentExcerpt"),
    )

    @field_validator("grade", mode="before")
    @classmethod
    def check_grade_type(cls, value: Any) -> Any:
        return _validate_grade_int(value)

    @field_validator(
        "subject",
        "series",
        "volume",
        "chapter",
        "lesson",
        "title",
        "license_note",
        "source_origin",
        "locator",
        mode="after",
    )
    @classmethod
    def clean_metadata_text(cls, value: str, info: ValidationInfo) -> str:
        return _clean_metadata_field(value, info.field_name)


class CurriculumSourceUpdate(BaseModel):
    """Payload cập nhật metadata, vị trí chương/bài hoặc trạng thái quyền dùng."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    grade: Annotated[int, Field(ge=1, le=12)] | None = None
    subject: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    series: str | None = Field(
        default=None,
        max_length=200,
        validation_alias=AliasChoices("series", "book"),
    )
    volume: Annotated[str, Field(max_length=100)] | None = None
    chapter: Annotated[str, Field(max_length=300)] | None = None
    lesson: Annotated[str, Field(max_length=300)] | None = None
    title: Annotated[str, Field(min_length=1, max_length=400)] | None = None
    license_status: LicenseStatus | None = Field(
        default=None,
        validation_alias=AliasChoices("license_status", "licenseStatus"),
    )
    license_note: str | None = Field(
        default=None,
        max_length=1000,
        validation_alias=AliasChoices("license_note", "licenseNote"),
    )
    source_origin: str | None = Field(
        default=None,
        max_length=500,
        validation_alias=AliasChoices("source_origin", "sourceOrigin"),
    )
    locator: Annotated[str, Field(max_length=300)] | None = None
    content_excerpt: str | None = Field(
        default=None,
        max_length=MAX_EXCERPT_LENGTH,
        validation_alias=AliasChoices("content_excerpt", "contentExcerpt"),
    )

    @field_validator("grade", mode="before")
    @classmethod
    def check_grade_type(cls, value: Any) -> Any:
        if value is None:
            return None
        return _validate_grade_int(value)

    @field_validator(
        "subject",
        "series",
        "volume",
        "chapter",
        "lesson",
        "title",
        "license_note",
        "source_origin",
        "locator",
        mode="after",
    )
    @classmethod
    def clean_metadata_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return _clean_metadata_field(value, info.field_name)

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> CurriculumSourceUpdate:
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"Trường '{field_name}' không được nhận giá trị null.")
        return self


class CurriculumSourceRecord(BaseModel):
    """Bản ghi nguồn học liệu đầy đủ lưu trong kho SQLite."""

    id: str
    owner_id: str
    grade: int
    subject: str
    series: str
    volume: str
    chapter: str
    lesson: str
    title: str
    license_status: LicenseStatus
    license_note: str
    source_origin: str
    locator: str
    content_excerpt: str
    sha256: str
    created_at: int
    updated_at: int


class CurriculumSourceListResponse(BaseModel):
    """Kết quả liệt kê và lọc nguồn học liệu theo chủ sở hữu."""

    sources: list[CurriculumSourceRecord]
    total: int


class CurriculumCitation(BaseModel):
    """Gói truy vết trích dẫn chuẩn hóa để gắn provenance cho AI và câu hỏi."""

    sourceId: str
    grade: int
    subject: str
    series: str
    volume: str
    chapter: str
    lesson: str
    title: str
    locator: str
    licenseStatus: LicenseStatus
    licenseNote: str
    sha256: str
    excerpt: str


def _build_connector(connect_or_db_path: ConnectOrDbPath) -> tuple[ConnectCallable, bool]:
    """Chuẩn hóa tham số kết nối từ đường dẫn SQLite hoặc hàm tạo context manager."""
    if isinstance(connect_or_db_path, (Path, str)):
        raw_path = str(connect_or_db_path)
        if raw_path == ":memory:" or raw_path.startswith("file::memory:"):
            lock = threading.RLock()
            memory_conn = sqlite3.connect(raw_path, check_same_thread=False)

            @contextmanager
            def connect_memory() -> Generator[sqlite3.Connection]:
                with lock, memory_conn:
                    yield memory_conn

            return connect_memory, True

        db_path = Path(connect_or_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        @contextmanager
        def connect_file() -> Generator[sqlite3.Connection]:
            connection = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

        return connect_file, False

    if callable(connect_or_db_path):
        return connect_or_db_path, False
    raise TypeError("connect_or_db_path phải là Path/str tới tệp SQLite hoặc hàm kết nối.")


def _default_owner(_request: Request) -> str:
    return "local"


def _row_to_record(row: Any) -> CurriculumSourceRecord:
    return CurriculumSourceRecord.model_validate(dict(zip(_COLUMNS, row, strict=True)))


def _register_error_handlers(app: FastAPI) -> None:
    if CurriculumSourceError not in app.exception_handlers:

        async def handle_curriculum_error(_request: Request, exc: Exception) -> JSONResponse:
            if not isinstance(exc, CurriculumSourceError):
                return JSONResponse(
                    {"error": "Lỗi xử lý nguồn học liệu.", "code": "internal_error"},
                    status_code=500,
                )
            status_code = exc.http_status or 400
            message = str(exc)
            return JSONResponse(
                {
                    "error": message,
                    "code": exc.code,
                    "detail": {"code": exc.code, "message": message},
                },
                status_code=status_code,
            )

        app.add_exception_handler(CurriculumSourceError, handle_curriculum_error)

    if AIError not in app.exception_handlers:

        async def handle_ai_error(_request: Request, exc: Exception) -> JSONResponse:
            if not isinstance(exc, AIError):
                return JSONResponse(
                    {"error": "Lỗi nghiệp vụ AI.", "code": "internal_error"},
                    status_code=500,
                )
            status_code = exc.http_status or (
                404
                if exc.code.endswith("_not_found")
                else 403
                if exc.code in {"source_license_restricted", "consent_required"}
                else 409
            )
            return JSONResponse({"error": str(exc), "code": exc.code}, status_code=status_code)

        app.add_exception_handler(AIError, handle_ai_error)


def install_curriculum_sources(
    app: FastAPI,
    connect_or_db_path: ConnectOrDbPath,
    *,
    owner_resolver: OwnerResolver | None = None,
    clock: Callable[[], float] = time.time,
) -> None:
    """Cài đặt router `/api/curriculum/sources` và khởi tạo bảng SQLite `curriculum_sources`."""
    connect, is_memory = _build_connector(connect_or_db_path)
    if owner_resolver is None:
        resolve_owner: OwnerResolver = _default_owner
    elif callable(owner_resolver):
        resolve_owner = owner_resolver
    else:
        raise TypeError("owner_resolver phải là hàm nhận Request và trả về chuỗi owner_id.")

    _register_error_handlers(app)

    with connect() as db:
        if not is_memory:
            db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA_DDL)

    def current_owner(request: Request) -> str:
        owner_id = resolve_owner(request)
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise CurriculumSourceError(
                "owner_required",
                "Thiếu định danh chủ sở hữu hợp lệ cho nguồn học liệu.",
                http_status=401,
            )
        return owner_id.strip()

    def load_owned_source(db: sqlite3.Connection, source_id: str, owner_id: str) -> Any:
        row = db.execute(
            _SELECT_SQL + " WHERE id = ? AND owner_id = ?",
            (source_id, owner_id),
        ).fetchone()
        if row is None:
            raise _source_not_found()
        return row

    router = APIRouter(prefix="/api/lesson-catalog/sources", tags=["lesson-catalog"])

    @router.post("", status_code=201, response_model=CurriculumSourceRecord)
    def create_source(body: CurriculumSourceCreate, request: Request) -> CurriculumSourceRecord:
        owner_id = current_owner(request)
        source_id = str(uuid4())
        now_ms = int(clock() * 1000)
        payload = body.model_dump()
        digest = compute_source_sha256(payload)
        with connect() as db:
            db.execute(
                "INSERT INTO curriculum_sources ("
                + ", ".join(_COLUMNS)
                + ") VALUES ("
                + ", ".join("?" for _ in _COLUMNS)
                + ")",
                (
                    source_id,
                    owner_id,
                    payload["grade"],
                    payload["subject"],
                    payload["series"],
                    payload["volume"],
                    payload["chapter"],
                    payload["lesson"],
                    payload["title"],
                    payload["license_status"],
                    payload["license_note"],
                    payload["source_origin"],
                    payload["locator"],
                    payload["content_excerpt"],
                    digest,
                    now_ms,
                    now_ms,
                ),
            )
            row = load_owned_source(db, source_id, owner_id)
        return _row_to_record(row)

    @router.get("", response_model=CurriculumSourceListResponse)
    def list_sources(
        request: Request,
        grade: Annotated[int | None, Query(ge=1, le=12)] = None,
        subject: str | None = None,
        series: str | None = None,
        book: str | None = None,
        volume: str | None = None,
        chapter: str | None = None,
        lesson: str | None = None,
        license_status: LicenseStatus | None = None,
        q: str | None = None,
    ) -> CurriculumSourceListResponse:
        owner_id = current_owner(request)
        clauses = ["owner_id = ?"]
        params: list[Any] = [owner_id]
        if grade is not None:
            clauses.append("grade = ?")
            params.append(grade)
        if license_status is not None:
            clauses.append("license_status = ?")
            params.append(license_status)

        sql = (
            _SELECT_SQL
            + " WHERE "
            + " AND ".join(clauses)
            + " ORDER BY grade ASC, subject ASC, series ASC, volume ASC, "
            "chapter ASC, lesson ASC, created_at ASC, id ASC"
        )
        with connect() as db:
            rows = db.execute(sql, params).fetchall()

        records = [_row_to_record(row) for row in rows]
        exact_filters = (
            ("subject", subject),
            ("series", series if series is not None else book),
            ("volume", volume),
            ("chapter", chapter),
            ("lesson", lesson),
        )
        for field_name, raw_expected in exact_filters:
            if raw_expected is None:
                continue
            expected = _normalize_search(raw_expected)
            if not expected:
                continue
            records = [
                record
                for record in records
                if _normalize_search(getattr(record, field_name)) == expected
            ]

        if q is not None:
            needle = _normalize_search(q)
            if needle:
                records = [
                    record
                    for record in records
                    if any(
                        needle in _normalize_search(value)
                        for value in (
                            record.title,
                            record.chapter,
                            record.lesson,
                            record.content_excerpt,
                        )
                    )
                ]

        return CurriculumSourceListResponse(sources=records, total=len(records))

    @router.get("/{source_id}", response_model=CurriculumSourceRecord)
    def get_source(source_id: str, request: Request) -> CurriculumSourceRecord:
        owner_id = current_owner(request)
        with connect() as db:
            row = load_owned_source(db, source_id, owner_id)
        return _row_to_record(row)

    @router.patch("/{source_id}", response_model=CurriculumSourceRecord)
    def update_source(
        source_id: str,
        body: CurriculumSourceUpdate,
        request: Request,
    ) -> CurriculumSourceRecord:
        owner_id = current_owner(request)
        updates = body.model_dump(exclude_unset=True)
        with connect() as db:
            existing = _row_to_record(load_owned_source(db, source_id, owner_id))
            merged = existing.model_dump()
            merged.update(updates)
            digest = compute_source_sha256(merged)
            now_ms = int(clock() * 1000)
            if now_ms <= existing.updated_at and clock is time.time:
                now_ms = existing.updated_at + 1
            db.execute(
                """
                UPDATE curriculum_sources
                SET grade = ?,
                    subject = ?,
                    series = ?,
                    volume = ?,
                    chapter = ?,
                    lesson = ?,
                    title = ?,
                    license_status = ?,
                    license_note = ?,
                    source_origin = ?,
                    locator = ?,
                    content_excerpt = ?,
                    sha256 = ?,
                    updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (
                    merged["grade"],
                    merged["subject"],
                    merged["series"],
                    merged["volume"],
                    merged["chapter"],
                    merged["lesson"],
                    merged["title"],
                    merged["license_status"],
                    merged["license_note"],
                    merged["source_origin"],
                    merged["locator"],
                    merged["content_excerpt"],
                    digest,
                    now_ms,
                    source_id,
                    owner_id,
                ),
            )
            row = load_owned_source(db, source_id, owner_id)
        return _row_to_record(row)

    @router.delete("/{source_id}")
    def delete_source(source_id: str, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            deleted = db.execute(
                "DELETE FROM curriculum_sources WHERE id = ? AND owner_id = ?",
                (source_id, owner_id),
            ).rowcount
        if not deleted:
            raise _source_not_found()
        return {"ok": True, "id": source_id}

    @router.get("/{source_id}/citation", response_model=CurriculumCitation)
    def get_citation(
        source_id: str,
        request: Request,
        allow_unverified: bool = False,
    ) -> CurriculumCitation:
        owner_id = current_owner(request)
        with connect() as db:
            record = _row_to_record(load_owned_source(db, source_id, owner_id))

        if record.license_status == "restricted":
            raise CurriculumSourceError(
                "source_license_restricted",
                "Nguồn bị hạn chế quyền dùng (restricted), không được phép dùng cho AI trích dẫn.",
                http_status=403,
            )
        if record.license_status == "pending_review" and not allow_unverified:
            raise CurriculumSourceError(
                "source_license_restricted",
                "Nguồn đang chờ rà soát quyền dùng (pending_review), "
                "cần xác minh trước khi AI trích dẫn.",
                http_status=403,
            )

        return CurriculumCitation(
            sourceId=record.id,
            grade=record.grade,
            subject=record.subject,
            series=record.series,
            volume=record.volume,
            chapter=record.chapter,
            lesson=record.lesson,
            title=record.title,
            locator=record.locator,
            licenseStatus=record.license_status,
            licenseNote=record.license_note,
            sha256=record.sha256,
            excerpt=record.content_excerpt,
        )

    app.include_router(router)
