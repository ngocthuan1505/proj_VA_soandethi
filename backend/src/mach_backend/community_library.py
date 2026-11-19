"""Kho đề cộng đồng: công bố có đồng ý chủ động, lọc, sao chép độc lập và thu hồi an toàn."""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Awaitable, Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from mach_backend.ai_contract import AIError
from mach_backend.share_snapshot import snapshot as build_share_snapshot

type Connector = Callable[[], AbstractContextManager[sqlite3.Connection]]
type ConnectOrPath = Path | str | Connector
type OwnerResolver = Callable[[Request], str | Awaitable[str]]

SENSITIVE_KEYS = frozenset(
    {
        "chat",
        "history",
        "aiconfig",
        "apikey",
        "api_key",
        "secret",
        "token",
        "notes",
        "password",
        "salt",
        "undo",
        "redo",
        "docs",
        "appliedprefs",
        "assistantsources",
        "aiplan",
        "aiclarification",
        "activeaijob",
    }
)
ANSWER_FIELDS = (
    "answer",
    "answerKnown",
    "answerText",
    "truthValues",
    "explanation",
    "explanationDoc",
    "rubric",
    "solution",
    "blindSolution",
    "approval",
)
EXAM_BLOCK_KEYS = ("heading", "general", "marking")
QUESTION_BLOCK_KEYS = (
    "stem",
    "explanation",
    "rubric",
    "figure",
    "options",
    "answer",
    "answerText",
    "truthValues",
)
PUBLIC_QUESTION_BLOCK_KEYS = ("stem", "options", "figure")
MAX_SNAPSHOT_BYTES = 25_000_000
MAX_TAGS = 30
MAX_TAG_LENGTH = 64

_ITEM_SELECT_COLUMNS = (
    "id, source_exam_id, author_id, author_label, title, grade, subject, "
    "series, chapter, tags_json, include_answers, status, version, "
    "snapshot_json, created_at, revoked_at"
)


class CommunityLibraryError(Exception):
    """Lỗi nghiệp vụ kho đề cộng đồng kèm mã HTTP và mã lỗi ổn định."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class PublishRequest(BaseModel):
    """Dữ liệu đầu vào khi giáo viên chủ động công bố đề lên kho cộng đồng."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    consent_public: Annotated[bool, Field(strict=True)] | None = Field(
        default=None,
        validation_alias=AliasChoices("consent_public", "consentPublic"),
    )
    include_answers: Annotated[bool, Field(strict=True)] = Field(
        default=False,
        validation_alias=AliasChoices("include_answers", "includeAnswers"),
    )
    exam: dict[str, Any]
    source_exam_id: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("source_exam_id", "sourceExamId"),
    )
    author_label: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("author_label", "authorLabel"),
    )
    title: str | None = Field(default=None, max_length=300)
    grade: Annotated[int, Field(strict=True)] | Annotated[str, Field(strict=True)] | None = None
    subject: str | None = Field(default=None, max_length=120)
    series: str | None = Field(default=None, max_length=150)
    chapter: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = None
    version: Annotated[int, Field(strict=True, ge=1)] | None = None


def _make_connector(connect_or_db_path: ConnectOrPath) -> Connector:
    """Chuẩn hóa đường dẫn SQLite hoặc callable trả về context manager kết nối."""
    if not isinstance(connect_or_db_path, Path | str):
        return connect_or_db_path

    raw_target = str(connect_or_db_path)
    if raw_target == ":memory:":
        memory_conn = sqlite3.connect(":memory:", timeout=5.0, check_same_thread=False)
        memory_conn.execute("PRAGMA foreign_keys = ON")
        memory_lock = threading.RLock()

        @contextmanager
        def _connect_memory() -> Generator[sqlite3.Connection]:
            with memory_lock, memory_conn:
                yield memory_conn

        return _connect_memory

    is_uri = raw_target.startswith("file:")
    if not is_uri:
        db_path = Path(connect_or_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        target = str(db_path)
    else:
        target = raw_target

    @contextmanager
    def _connect() -> Generator[sqlite3.Connection]:
        conn = sqlite3.connect(target, timeout=5.0, uri=is_uri)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn
        finally:
            conn.close()

    return _connect


def _init_schema(connect: Connector) -> None:
    """Khởi tạo các bảng và chỉ mục SQLite cho kho cộng đồng và lịch sử sao chép."""
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS community_items (
                id TEXT PRIMARY KEY,
                source_exam_id TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_label TEXT NOT NULL,
                title TEXT NOT NULL,
                grade INTEGER NOT NULL CHECK (grade >= 1 AND grade <= 12),
                subject TEXT NOT NULL,
                series TEXT NOT NULL DEFAULT '',
                chapter TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                include_answers INTEGER NOT NULL DEFAULT 0 CHECK (include_answers IN (0, 1)),
                status TEXT NOT NULL DEFAULT 'published'
                    CHECK (status IN ('published', 'revoked')),
                version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
                snapshot_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS community_clones (
                clone_id TEXT PRIMARY KEY,
                community_item_id TEXT NOT NULL REFERENCES community_items(id),
                cloned_exam_id TEXT NOT NULL,
                cloner_id TEXT NOT NULL,
                cloned_at INTEGER NOT NULL,
                cloned_snapshot_json TEXT NOT NULL
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_community_items_status_created "
            "ON community_items(status, created_at DESC)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_community_items_filters "
            "ON community_items(status, grade, subject, series, chapter)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_community_items_author "
            "ON community_items(author_id, status)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_community_clones_item "
            "ON community_clones(community_item_id, cloned_at DESC)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_community_clones_cloner "
            "ON community_clones(cloner_id, cloned_at DESC)"
        )


def _parse_grade(raw_grade: Any) -> int:
    """Kiểm tra khối lớp là số nguyên hợp lệ trong khoảng 1..12."""
    if type(raw_grade) is int:
        if 1 <= raw_grade <= 12:
            return raw_grade
        raise CommunityLibraryError(422, "invalid_grade", "Khối lớp phải từ 1 đến 12.")
    if isinstance(raw_grade, str):
        cleaned = raw_grade.strip()
        if re.fullmatch(r"[1-9]|1[0-2]", cleaned):
            return int(cleaned)
    raise CommunityLibraryError(422, "invalid_grade", "Khối lớp phải là số nguyên từ 1 đến 12.")


def _require_non_empty_text(value: Any, *, code: str, message: str, max_length: int) -> str:
    """Kiểm tra chuỗi bắt buộc không rỗng và không vượt giới hạn độ dài."""
    if not isinstance(value, str):
        raise CommunityLibraryError(422, code, message)
    cleaned = value.strip()
    if not cleaned or len(cleaned) > max_length:
        raise CommunityLibraryError(422, code, message)
    return cleaned


def _normalize_optional_text(value: Any, *, code: str, message: str, max_length: int) -> str:
    """Chuẩn hóa chuỗi tùy chọn về rỗng nếu None hoặc kiểm tra kiểu/độ dài."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CommunityLibraryError(422, code, message)
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise CommunityLibraryError(422, code, message)
    return cleaned


def _normalize_tags(raw_tags: Any) -> list[str]:
    """Chuẩn hóa danh sách thẻ từ khóa: loại trùng, cắt khoảng trắng, giới hạn số lượng."""
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        raise CommunityLibraryError(
            422, "invalid_tags", "Danh sách thẻ từ khóa phải là mảng chuỗi."
        )
    result: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        if not isinstance(tag, str):
            raise CommunityLibraryError(422, "invalid_tags", "Mỗi thẻ từ khóa phải là chuỗi ký tự.")
        cleaned = tag.strip()
        if not cleaned:
            continue
        if len(cleaned) > MAX_TAG_LENGTH:
            raise CommunityLibraryError(
                422, "invalid_tags", f"Mỗi thẻ từ khóa không vượt quá {MAX_TAG_LENGTH} ký tự."
            )
        folded = cleaned.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(cleaned)
    if len(result) > MAX_TAGS:
        raise CommunityLibraryError(
            422, "invalid_tags", f"Số lượng thẻ từ khóa không vượt quá {MAX_TAGS}."
        )
    return result


def _scrub_sensitive(value: Any) -> Any:
    """Loại bỏ đệ quy các khóa nội bộ hoặc nhạy cảm khỏi cấu trúc JSON trước khi lưu."""
    if isinstance(value, dict):
        return {
            key: _scrub_sensitive(item)
            for key, item in value.items()
            if isinstance(key, str) and key.casefold() not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_scrub_sensitive(item) for item in value]
    return value


def _refresh_block_ids(raw_blocks: Any, default_keys: tuple[str, ...]) -> dict[str, str]:
    """Cấp mới UUID cho toàn bộ khóa blockIds an toàn và bảo đảm đủ khóa chuẩn."""
    keys: list[str] = []
    seen: set[str] = set()
    if isinstance(raw_blocks, dict):
        for key in raw_blocks:
            if (
                isinstance(key, str)
                and key.strip()
                and len(key) <= 64
                and key.casefold() not in SENSITIVE_KEYS
                and key not in seen
            ):
                seen.add(key)
                keys.append(key)
    for key in default_keys:
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return {key: str(uuid4()) for key in keys}


def _strip_question_answers(question: dict[str, Any]) -> None:
    """Cắt bỏ hoàn toàn đáp án, giải thích, barem và lời giải khỏi câu hỏi công bố không đáp án."""
    for field in ANSWER_FIELDS:
        question.pop(field, None)
    question["answerKnown"] = False


def _normalize_exam_for_snapshot(raw_exam: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa các trường tùy chọn đang để None trước khi chuyển qua share_snapshot."""
    prepared = deepcopy(raw_exam)
    if prepared.get("quote") is None:
        prepared["quote"] = {}
    if prepared.get("data") is None:
        prepared["data"] = []
    questions: list[dict[str, Any]] = []
    for item in prepared["questions"]:
        if not isinstance(item, dict):
            raise CommunityLibraryError(
                422, "invalid_exam", "Mỗi câu hỏi trong đề thi phải là một đối tượng hợp lệ."
            )
        q_copy = dict(item)
        for list_field in ("options", "formulas", "tables", "images", "rubric"):
            if list_field in q_copy and q_copy[list_field] is None:
                q_copy[list_field] = []
        questions.append(q_copy)
    prepared["questions"] = questions
    return prepared


def _sanitize_published_exam(
    raw_exam: dict[str, Any],
    *,
    include_answers: bool,
    title: str,
    subject: str,
    grade: int,
    series: str,
    chapter: str,
    tags: list[str],
) -> dict[str, Any]:
    """Lọc sạch dữ liệu nhạy cảm của đề thi theo chuẩn share_snapshot trước khi công bố."""
    if not isinstance(raw_exam, dict) or not isinstance(raw_exam.get("questions"), list):
        raise CommunityLibraryError(
            422, "invalid_exam", "Đề thi công bố cần có danh sách câu hỏi hợp lệ."
        )
    prepared = _normalize_exam_for_snapshot(raw_exam)
    try:
        sanitized = build_share_snapshot(prepared, include_answers)
    except AIError as error:
        raise CommunityLibraryError(422, error.code, str(error)) from None

    sanitized["title"] = title
    sanitized["subject"] = subject
    sanitized["grade"] = str(grade)
    sanitized["series"] = series
    sanitized["chapter"] = chapter
    sanitized["tags"] = tags
    sanitized["blockIds"] = _refresh_block_ids(raw_exam.get("blockIds"), EXAM_BLOCK_KEYS)

    original_questions = raw_exam["questions"]
    for index, q in enumerate(sanitized["questions"]):
        original_q = original_questions[index] if index < len(original_questions) else {}
        if include_answers:
            if "solution" in original_q and original_q["solution"] is not None:
                if not isinstance(original_q["solution"], str):
                    raise CommunityLibraryError(
                        422,
                        "invalid_document",
                        "Trường lời giải tham khảo (solution) phải là chuỗi.",
                    )
                q["solution"] = original_q["solution"]
            block_defaults = QUESTION_BLOCK_KEYS
        else:
            _strip_question_answers(q)
            block_defaults = PUBLIC_QUESTION_BLOCK_KEYS
        q["blockIds"] = _refresh_block_ids(
            original_q.get("blockIds") if isinstance(original_q, dict) else None,
            block_defaults,
        )

    cleaned = _scrub_sensitive(sanitized)
    encoded = json.dumps(cleaned, ensure_ascii=False, allow_nan=False)
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise CommunityLibraryError(422, "export_limit", "Bản công bố vượt quá giới hạn 25 MB.")
    return cleaned


def _refresh_subitem_ids(items: Any) -> None:
    """Cấp mới UUID cho trường id trong danh sách phần tử con nếu có."""
    if not isinstance(items, list):
        return
    for item in items:
        if isinstance(item, dict) and "id" in item:
            item["id"] = str(uuid4())


def _build_independent_clone(
    snapshot_data: dict[str, Any],
    *,
    item_id: str,
    author_id: str,
    source_exam_id: str,
    version: int,
) -> dict[str, Any]:
    """Tạo bản sao đề hoàn toàn độc lập với UUID mới và metadata truy vết nguồn gốc."""
    cloned = deepcopy(snapshot_data)
    cloned["id"] = str(uuid4())
    cloned["revision"] = 1
    cloned["blockIds"] = _refresh_block_ids(cloned.get("blockIds"), EXAM_BLOCK_KEYS)

    questions = cloned.get("questions")
    if isinstance(questions, list):
        for question in questions:
            if not isinstance(question, dict):
                continue
            question["id"] = str(uuid4())
            question["v"] = 1
            question["check"] = None
            question["blockIds"] = _refresh_block_ids(question.get("blockIds"), QUESTION_BLOCK_KEYS)
            _refresh_subitem_ids(question.get("formulas"))
            _refresh_subitem_ids(question.get("images"))
            _refresh_subitem_ids(question.get("rubric"))

    cloned["clonedFrom"] = {
        "communityItemId": item_id,
        "authorId": author_id,
        "sourceExamId": source_exam_id,
        "version": version,
    }
    return cloned


def _row_to_item(row: Any, *, include_snapshot: bool = False) -> dict[str, Any]:
    """Chuyển dòng SQLite của bảng community_items sang dictionary chuẩn API."""
    snapshot_data = json.loads(row[13])
    questions = snapshot_data.get("questions")
    question_count = len(questions) if isinstance(questions, list) else 0
    payload: dict[str, Any] = {
        "id": row[0],
        "source_exam_id": row[1],
        "author_id": row[2],
        "author_label": row[3],
        "title": row[4],
        "grade": row[5],
        "subject": row[6],
        "series": row[7],
        "chapter": row[8],
        "tags": json.loads(row[9]),
        "include_answers": bool(row[10]),
        "status": row[11],
        "version": row[12],
        "question_count": question_count,
        "created_at": row[14],
        "revoked_at": row[15],
    }
    if include_snapshot:
        payload["snapshot"] = snapshot_data
    return payload


def _row_to_clone_record(
    row: Any, *, item_version: int = 1, source_exam_id: str = "", author_id: str = ""
) -> dict[str, Any]:
    """Chuyển dòng SQLite của bảng community_clones sang metadata cloneRecord."""
    record: dict[str, Any] = {
        "clone_id": row[0],
        "community_item_id": row[1],
        "cloned_exam_id": row[2],
        "cloner_id": row[3],
        "cloned_at": row[4],
    }
    if source_exam_id:
        record["source_exam_id"] = source_exam_id
    if author_id:
        record["author_id"] = author_id
    if item_version >= 1:
        record["version"] = item_version
    return record


def _fold_text(value: str) -> str:
    """Chuẩn hóa Unicode NFC và chữ thường để lọc tiếng Việt có dấu ổn định."""
    return unicodedata.normalize("NFC", value).strip().casefold()


def _matches_text_filters(
    item: dict[str, Any],
    snapshot_json: str,
    *,
    subject: str | None,
    series: str | None,
    chapter: str | None,
    tag: str | None,
    q: str | None,
) -> bool:
    """Lọc theo môn, bộ sách, chương, thẻ và từ khóa hỗ trợ chữ tiếng Việt có dấu."""
    if subject and subject.strip():
        if _fold_text(item["subject"]) != _fold_text(subject):
            return False
    if series and series.strip():
        if _fold_text(item["series"]) != _fold_text(series):
            return False
    if chapter and chapter.strip():
        if _fold_text(chapter) not in _fold_text(item["chapter"]):
            return False
    if tag and tag.strip():
        target_tag = _fold_text(tag)
        if not any(_fold_text(t) == target_tag for t in item["tags"]):
            return False
    if q and q.strip():
        keyword = _fold_text(q)
        snapshot_data = json.loads(snapshot_json)
        stems = " ".join(
            str(question.get("stem", ""))
            for question in snapshot_data.get("questions", [])
            if isinstance(question, dict)
        )
        haystack = _fold_text(
            " ".join(
                [
                    item["title"],
                    item["subject"],
                    item["series"],
                    item["chapter"],
                    item["author_label"],
                    " ".join(item["tags"]),
                    stems,
                ]
            )
        )
        if keyword not in haystack:
            return False
    return True


def install_community_library(
    app: FastAPI,
    connect_or_db_path: ConnectOrPath,
    *,
    owner_resolver: OwnerResolver | None = None,
    clock: Callable[[], float] = time.time,
    require_auth_for_read: bool = False,
) -> None:
    """Cài đặt các route kho cộng đồng vào ứng dụng FastAPI với SQLite độc lập."""
    connect = _make_connector(connect_or_db_path)
    _init_schema(connect)
    resolve = owner_resolver or (lambda _request: "local")

    if CommunityLibraryError not in app.exception_handlers:

        @app.exception_handler(CommunityLibraryError)
        async def _community_error_handler(
            _request: Request, exc: CommunityLibraryError
        ) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "code": exc.code,
                    "error": exc.message,
                    "detail": {"code": exc.code, "message": exc.message},
                },
            )

    async def _resolve_owner(request: Request) -> str:
        resolved = resolve(request)
        if inspect.isawaitable(resolved):
            resolved = await resolved
        if not isinstance(resolved, str) or not resolved.strip():
            raise HTTPException(401, "Cần đăng nhập để thao tác với kho cộng đồng.")
        return resolved.strip()

    router = APIRouter(prefix="/api/community", tags=["community-library"])

    @router.post("/publish", status_code=201)
    async def publish_item(body: PublishRequest, request: Request) -> dict[str, Any]:
        author_id = await _resolve_owner(request)
        if body.consent_public is not True:
            raise CommunityLibraryError(
                400,
                "consent_required",
                "Cần xác nhận đồng ý công bố công khai (consent_public=true) trước khi đăng.",
            )

        raw_exam = body.exam
        title = _require_non_empty_text(
            body.title if body.title is not None else raw_exam.get("title"),
            code="invalid_exam",
            message="Đề thi công bố cần có tiêu đề hợp lệ.",
            max_length=300,
        )
        subject = _require_non_empty_text(
            body.subject if body.subject is not None else raw_exam.get("subject"),
            code="invalid_exam",
            message="Đề thi công bố cần có môn học hợp lệ.",
            max_length=120,
        )
        grade = _parse_grade(body.grade if body.grade is not None else raw_exam.get("grade"))
        series = _normalize_optional_text(
            body.series if body.series is not None else raw_exam.get("series"),
            code="invalid_exam",
            message="Tên bộ sách không hợp lệ hoặc quá dài.",
            max_length=150,
        )
        chapter = _normalize_optional_text(
            body.chapter if body.chapter is not None else raw_exam.get("chapter"),
            code="invalid_exam",
            message="Tên chương không hợp lệ hoặc quá dài.",
            max_length=200,
        )
        tags = _normalize_tags(body.tags if body.tags is not None else raw_exam.get("tags"))
        author_label = (
            _normalize_optional_text(
                body.author_label if body.author_label is not None else raw_exam.get("authorLabel"),
                code="invalid_exam",
                message="Tên hiển thị tác giả không hợp lệ hoặc quá dài.",
                max_length=120,
            )
            or author_id
        )

        raw_source_id = (
            body.source_exam_id if body.source_exam_id is not None else raw_exam.get("id")
        )
        if raw_source_id is None or (isinstance(raw_source_id, str) and not raw_source_id.strip()):
            source_exam_id = str(uuid4())
        else:
            source_exam_id = _require_non_empty_text(
                str(raw_source_id),
                code="invalid_exam",
                message="Mã đề gốc (source_exam_id) không hợp lệ.",
                max_length=128,
            )

        sanitized = _sanitize_published_exam(
            raw_exam,
            include_answers=body.include_answers,
            title=title,
            subject=subject,
            grade=grade,
            series=series,
            chapter=chapter,
            tags=tags,
        )
        snapshot_json = json.dumps(sanitized, ensure_ascii=False, allow_nan=False)
        tags_json = json.dumps(tags, ensure_ascii=False, allow_nan=False)
        item_id = str(uuid4())
        created_at = int(clock() * 1000)

        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if body.version is not None:
                version = body.version
            else:
                latest_row = db.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM community_items "
                    "WHERE author_id = ? AND source_exam_id = ?",
                    (author_id, source_exam_id),
                ).fetchone()
                version = int(latest_row[0]) + 1 if latest_row else 1

            db.execute(
                """
                INSERT INTO community_items (
                    id, source_exam_id, author_id, author_label, title, grade,
                    subject, series, chapter, tags_json, include_answers,
                    status, version, snapshot_json, created_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?, ?, ?, NULL)
                """,
                (
                    item_id,
                    source_exam_id,
                    author_id,
                    author_label,
                    title,
                    grade,
                    subject,
                    series,
                    chapter,
                    tags_json,
                    int(body.include_answers),
                    version,
                    snapshot_json,
                    created_at,
                ),
            )
            saved = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _row_to_item(saved, include_snapshot=True)

    @router.get("/items")
    async def list_items(
        request: Request,
        grade: int | None = Query(default=None, ge=1, le=12),
        subject: str | None = Query(default=None),
        series: str | None = Query(default=None),
        chapter: str | None = Query(default=None),
        tag: str | None = Query(default=None),
        q: str | None = Query(default=None),
        include_answers: bool | None = Query(default=None),
    ) -> dict[str, Any]:
        if require_auth_for_read:
            await _resolve_owner(request)
        clauses = ["status = 'published'"]
        params: list[Any] = []
        if grade is not None:
            clauses.append("grade = ?")
            params.append(grade)
        if include_answers is not None:
            clauses.append("include_answers = ?")
            params.append(int(include_answers))

        where_sql = " AND ".join(clauses)
        with connect() as db:
            rows = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items "
                f"WHERE {where_sql} ORDER BY created_at DESC, rowid DESC",
                tuple(params),
            ).fetchall()

        matched: list[dict[str, Any]] = []
        for row in rows:
            item = _row_to_item(row, include_snapshot=False)
            if _matches_text_filters(
                item,
                row[13],
                subject=subject,
                series=series,
                chapter=chapter,
                tag=tag,
                q=q,
            ):
                matched.append(item)
        return {"items": matched, "total": len(matched)}

    @router.get("/items/{item_id}")
    async def get_item(item_id: str, request: Request) -> dict[str, Any]:
        if require_auth_for_read:
            await _resolve_owner(request)
        with connect() as db:
            row = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            raise CommunityLibraryError(
                404, "item_not_found", "Không tìm thấy đề cộng đồng được yêu cầu."
            )
        if row[11] == "revoked":
            raise CommunityLibraryError(
                410, "item_revoked", "Đề cộng đồng này đã được tác giả thu hồi."
            )
        return _row_to_item(row, include_snapshot=True)

    @router.post("/items/{item_id}/clone", status_code=201)
    async def clone_item(item_id: str, request: Request) -> dict[str, Any]:
        cloner_id = await _resolve_owner(request)
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if row is None:
                raise CommunityLibraryError(
                    404, "item_not_found", "Không tìm thấy đề cộng đồng để sao chép."
                )
            if row[11] == "revoked":
                raise CommunityLibraryError(
                    410,
                    "item_revoked",
                    "Đề cộng đồng đã được tác giả thu hồi nên không thể sao chép mới.",
                )

            snapshot_data = json.loads(row[13])
            source_exam_id = row[1]
            author_id = row[2]
            version = int(row[12])
            cloned_exam = _build_independent_clone(
                snapshot_data,
                item_id=item_id,
                author_id=author_id,
                source_exam_id=source_exam_id,
                version=version,
            )
            clone_id = str(uuid4())
            cloned_exam_id = str(cloned_exam["id"])
            cloned_at = int(clock() * 1000)
            cloned_snapshot_json = json.dumps(cloned_exam, ensure_ascii=False, allow_nan=False)

            db.execute(
                """
                INSERT INTO community_clones (
                    clone_id, community_item_id, cloned_exam_id,
                    cloner_id, cloned_at, cloned_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clone_id,
                    item_id,
                    cloned_exam_id,
                    cloner_id,
                    cloned_at,
                    cloned_snapshot_json,
                ),
            )
            clone_row = db.execute(
                "SELECT clone_id, community_item_id, cloned_exam_id, cloner_id, cloned_at "
                "FROM community_clones WHERE clone_id = ?",
                (clone_id,),
            ).fetchone()

        return {
            "clonedExam": cloned_exam,
            "cloneRecord": _row_to_clone_record(
                clone_row,
                item_version=version,
                source_exam_id=source_exam_id,
                author_id=author_id,
            ),
        }

    @router.post("/items/{item_id}/revoke")
    async def revoke_item(item_id: str, request: Request) -> dict[str, Any]:
        caller_id = await _resolve_owner(request)
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if row is None:
                raise CommunityLibraryError(
                    404, "item_not_found", "Không tìm thấy đề cộng đồng để thu hồi."
                )
            if row[2] != caller_id:
                raise CommunityLibraryError(
                    403, "forbidden", "Chỉ tác giả đã công bố mới có quyền thu hồi đề này."
                )
            if row[11] != "revoked":
                revoked_at = int(clock() * 1000)
                db.execute(
                    "UPDATE community_items SET status = 'revoked', revoked_at = ? "
                    "WHERE id = ? AND author_id = ?",
                    (revoked_at, item_id, caller_id),
                )
            updated = db.execute(
                f"SELECT {_ITEM_SELECT_COLUMNS} FROM community_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        return _row_to_item(updated, include_snapshot=False)

    @router.get("/clones")
    async def list_clones(request: Request) -> dict[str, Any]:
        caller_id = await _resolve_owner(request)
        with connect() as db:
            rows = db.execute(
                """
                SELECT c.clone_id, c.community_item_id, c.cloned_exam_id, c.cloner_id, c.cloned_at,
                       i.version, i.source_exam_id, i.author_id
                FROM community_clones AS c
                JOIN community_items AS i ON i.id = c.community_item_id
                WHERE c.cloner_id = ?
                ORDER BY c.cloned_at DESC, c.rowid DESC
                """,
                (caller_id,),
            ).fetchall()
        clones = [
            _row_to_clone_record(r, item_version=int(r[5]), source_exam_id=r[6], author_id=r[7])
            for r in rows
        ]
        return {"clones": clones, "total": len(clones)}

    @router.get("/clones/{clone_id}")
    async def get_clone(clone_id: str, request: Request) -> dict[str, Any]:
        caller_id = await _resolve_owner(request)
        with connect() as db:
            row = db.execute(
                """
                SELECT c.clone_id, c.community_item_id, c.cloned_exam_id, c.cloner_id, c.cloned_at,
                       c.cloned_snapshot_json, i.version, i.source_exam_id, i.author_id
                FROM community_clones AS c
                JOIN community_items AS i ON i.id = c.community_item_id
                WHERE c.clone_id = ? AND c.cloner_id = ?
                """,
                (clone_id, caller_id),
            ).fetchone()
        if row is None:
            raise CommunityLibraryError(
                404, "clone_not_found", "Không tìm thấy bản sao thuộc quyền sở hữu của bạn."
            )
        return {
            "clonedExam": json.loads(row[5]),
            "cloneRecord": _row_to_clone_record(
                row, item_version=int(row[6]), source_exam_id=row[7], author_id=row[8]
            ),
        }

    app.include_router(router)
