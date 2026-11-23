"""Ngân hàng câu hỏi SQLite: tìm không dấu, gắn thẻ, clone cấp UUID mới và sao lưu nguyên tử."""

from __future__ import annotations

import copy
import json
import math
import sqlite3
import time
import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mach_backend.ai_contract import AIError

type ConnectCallable = Callable[[], AbstractContextManager[sqlite3.Connection]]
type OwnerResolver = Callable[[Request], str]

QuestionKind = Literal["mcq", "truefalse", "short", "essay"]
ALLOWED_QTYPES: frozenset[str] = frozenset({"mcq", "truefalse", "short", "essay"})
MAX_RESTORE_ITEMS = 5000
MAX_QUESTION_JSON_BYTES = 2 * 1024 * 1024

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS question_bank (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    qtype TEXT NOT NULL DEFAULT 'mcq',
    level INTEGER NOT NULL DEFAULT 0,
    points_q4 INTEGER NOT NULL DEFAULT 1,
    tags_json TEXT NOT NULL DEFAULT '[]',
    question_json TEXT NOT NULL,
    search_text TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_question_bank_owner_updated
    ON question_bank (owner_id, updated_at DESC)
"""


def strip_vietnamese_accents(value: str) -> str:
    """Chuẩn hóa chữ tiếng Việt bỏ dấu, chuyển đ/Đ -> d và hạ chữ thường để tìm nhanh."""
    normalized = unicodedata.normalize("NFD", str(value or ""))
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d").replace("Đ", "D").casefold()


def _norm_text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _strict_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(message)
    return value


def _walk_rich_text(node: Any, depth: int = 0) -> list[str]:
    if not isinstance(node, dict) or depth > 64:
        return []
    kind = node.get("type")
    if kind == "text":
        text = node.get("text")
        return [text] if isinstance(text, str) and text else []
    if kind == "mathInline":
        attrs = node.get("attrs")
        if isinstance(attrs, dict) and isinstance(attrs.get("latex"), str):
            return [attrs["latex"]]
        return []
    out: list[str] = []
    children = node.get("content")
    if isinstance(children, list):
        for child in children:
            out.extend(_walk_rich_text(child, depth + 1))
    return out


def _normalize_tags(raw_tags: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in raw_tags:
        tag = _norm_text(raw)
        if not tag:
            continue
        if len(tag) > 60:
            raise ValueError("Mỗi thẻ (tag) tối đa 60 ký tự.")
        key = strip_vietnamese_accents(tag)
        if key not in seen:
            seen.add(key)
            cleaned.append(tag)
    return cleaned


def _validate_question_dict(question: Any) -> dict[str, Any]:
    if not isinstance(question, dict):
        raise ValueError("Trường question phải là đối tượng JSON hợp lệ.")
    stem = question.get("stem")
    rich_doc = question.get("richDoc")
    has_stem = isinstance(stem, str) and bool(stem.strip())
    has_rich = isinstance(rich_doc, dict) and bool(rich_doc)
    if not has_stem and not has_rich:
        raise ValueError("Câu hỏi cần có nội dung stem hoặc richDoc.")
    try:
        serialized = json.dumps(question, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Nội dung câu hỏi chứa dữ liệu không thể tuần tự hóa JSON.") from exc
    if len(serialized.encode("utf-8")) > MAX_QUESTION_JSON_BYTES:
        raise ValueError("Dữ liệu câu hỏi vượt giới hạn 2 MB.")
    return copy.deepcopy(question)


def _derive_metadata(
    *,
    subject: str,
    grade: str,
    topic: str,
    qtype: QuestionKind | None,
    level: int | None,
    points_q4: int | None,
    tags: list[str],
    question: dict[str, Any],
) -> tuple[str, str, str, str, int, int, list[str], str]:
    clean_subject = _norm_text(subject)
    clean_grade = _norm_text(grade)
    raw_topic = topic if topic.strip() else str(question.get("topic") or "")
    clean_topic = _norm_text(raw_topic)[:240]

    raw_qtype = qtype if qtype is not None else str(question.get("type") or "mcq").strip().lower()
    if raw_qtype not in ALLOWED_QTYPES:
        raise ValueError("Dạng câu hỏi phải thuộc mcq, truefalse, short hoặc essay.")

    if level is not None:
        clean_level = _strict_int(level, "Mức nhận thức (level) phải là số nguyên 0..3.")
    else:
        raw_level = question.get("level", 0)
        if isinstance(raw_level, bool) or not isinstance(raw_level, int):
            clean_level = 0
        else:
            clean_level = raw_level
    if not 0 <= clean_level <= 3:
        raise ValueError("Mức nhận thức (level) phải nằm trong khoảng 0..3.")

    if points_q4 is not None:
        clean_points_q4 = _strict_int(points_q4, "points_q4 phải là số nguyên từ 0 đến 400.")
    else:
        raw_pts = question.get("points")
        if isinstance(raw_pts, bool):
            raise ValueError("Điểm câu hỏi không hợp lệ.")
        if isinstance(raw_pts, (int, float)):
            if not math.isfinite(raw_pts) or raw_pts < 0:
                raise ValueError("Điểm câu hỏi phải là số không âm hữu hạn.")
            clean_points_q4 = round(float(raw_pts) * 4)
        else:
            clean_points_q4 = 1
    if not 0 <= clean_points_q4 <= 400:
        raise ValueError("points_q4 phải nằm trong khoảng 0..400.")

    clean_tags = _normalize_tags(tags)
    search_parts: list[str] = [clean_subject, clean_grade, clean_topic, *clean_tags]
    if isinstance(question.get("stem"), str):
        search_parts.append(question["stem"])
    if isinstance(question.get("explanation"), str):
        search_parts.append(question["explanation"])
    if isinstance(question.get("answerText"), str):
        search_parts.append(question["answerText"])
    options = question.get("options")
    if isinstance(options, list):
        search_parts.extend(str(opt) for opt in options if isinstance(opt, str))
    for doc_key in ("richDoc", "explanationDoc"):
        if isinstance(question.get(doc_key), dict):
            search_parts.extend(_walk_rich_text(question[doc_key]))
    rubric = question.get("rubric")
    if isinstance(rubric, list):
        for step in rubric:
            if isinstance(step, dict):
                for key in ("text", "criterion", "content", "step"):
                    val = step.get(key)
                    if isinstance(val, str) and val:
                        search_parts.append(val)
    search_text = " ".join(
        strip_vietnamese_accents(part) for part in search_parts if part and part.strip()
    )
    return (
        clean_subject,
        clean_grade,
        clean_topic,
        raw_qtype,
        clean_level,
        clean_points_q4,
        clean_tags,
        search_text,
    )


class QuestionBankCreate(BaseModel):
    """Payload thêm một câu hỏi vào ngân hàng cá nhân."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(default="", max_length=120)
    grade: str = Field(default="", max_length=40)
    topic: str = Field(default="", max_length=240)
    qtype: QuestionKind | None = None
    level: int | None = Field(default=None, ge=0, le=3)
    points_q4: int | None = Field(default=None, ge=0, le=400)
    tags: list[str] = Field(default_factory=list, max_length=30)
    question: dict[str, Any]

    @field_validator("level", mode="before")
    @classmethod
    def check_level_not_bool(cls, value: Any) -> Any:
        if value is not None and isinstance(value, bool):
            raise ValueError("Mức nhận thức (level) phải là số nguyên 0..3.")
        return value

    @field_validator("points_q4", mode="before")
    @classmethod
    def check_points_q4_not_bool(cls, value: Any) -> Any:
        if value is not None and isinstance(value, bool):
            raise ValueError("points_q4 phải là số nguyên 0..400.")
        return value

    @field_validator("question")
    @classmethod
    def check_question(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_question_dict(value)

    @field_validator("tags")
    @classmethod
    def check_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class QuestionBankUpdate(BaseModel):
    """Payload cập nhật một phần bản ghi trong ngân hàng câu hỏi."""

    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=120)
    grade: str | None = Field(default=None, max_length=40)
    topic: str | None = Field(default=None, max_length=240)
    qtype: QuestionKind | None = None
    level: int | None = Field(default=None, ge=0, le=3)
    points_q4: int | None = Field(default=None, ge=0, le=400)
    tags: list[str] | None = Field(default=None, max_length=30)
    question: dict[str, Any] | None = None

    @field_validator("level", mode="before")
    @classmethod
    def check_level_not_bool(cls, value: Any) -> Any:
        if value is not None and isinstance(value, bool):
            raise ValueError("Mức nhận thức (level) phải là số nguyên 0..3.")
        return value

    @field_validator("points_q4", mode="before")
    @classmethod
    def check_points_q4_not_bool(cls, value: Any) -> Any:
        if value is not None and isinstance(value, bool):
            raise ValueError("points_q4 phải là số nguyên 0..400.")
        return value

    @field_validator("question")
    @classmethod
    def check_optional_question(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return _validate_question_dict(value)

    @field_validator("tags")
    @classmethod
    def check_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_tags(value)

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> QuestionBankUpdate:
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"Trường '{field_name}' không được nhận giá trị null.")
        return self


def ensure_question_bank_schema(db: sqlite3.Connection) -> None:
    """Bảo đảm bảng `question_bank` và chỉ mục tồn tại trong SQLite."""
    db.execute(_CREATE_TABLE_SQL)
    db.execute(_CREATE_INDEX_SQL)


def _row_to_dict(row: Any) -> dict[str, Any]:
    (
        item_id,
        owner_id,
        subject,
        grade,
        topic,
        qtype,
        level,
        points_q4,
        tags_json,
        question_json,
        _search_text,
        created_at,
        updated_at,
    ) = row
    return {
        "id": item_id,
        "owner_id": owner_id,
        "subject": subject,
        "grade": grade,
        "topic": topic,
        "qtype": qtype,
        "level": level,
        "points_q4": points_q4,
        "points": points_q4 / 4,
        "tags": json.loads(tags_json),
        "question": json.loads(question_json),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _not_found() -> AIError:
    return AIError(
        "question_bank_not_found",
        "Không tìm thấy câu hỏi trong ngân hàng của tài khoản hiện tại.",
        http_status=404,
    )


def _load_owned_row(db: sqlite3.Connection, item_id: str, owner_id: str) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT id, owner_id, subject, grade, topic, qtype, level, points_q4,
               tags_json, question_json, search_text, created_at, updated_at
        FROM question_bank
        WHERE id = ? AND owner_id = ?
        """,
        (item_id, owner_id),
    ).fetchone()
    if row is None:
        raise _not_found()
    return _row_to_dict(row)


def list_owner_question_bank(db: sqlite3.Connection, owner_id: str) -> list[dict[str, Any]]:
    """Đọc toàn bộ bản ghi ngân hàng câu hỏi của một chủ sở hữu (dùng cho truy vấn và sao lưu)."""
    ensure_question_bank_schema(db)
    rows = db.execute(
        """
        SELECT id, owner_id, subject, grade, topic, qtype, level, points_q4,
               tags_json, question_json, search_text, created_at, updated_at
        FROM question_bank
        WHERE owner_id = ?
        ORDER BY updated_at DESC, id ASC
        """,
        (owner_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _remap_rich_doc_ids(node: Any, id_map: dict[str, str], depth: int = 0) -> None:
    if not isinstance(node, dict) or depth > 64:
        return
    attrs = node.get("attrs")
    if isinstance(attrs, dict) and isinstance(attrs.get("id"), str) and attrs["id"]:
        old_id = attrs["id"]
        if old_id not in id_map:
            id_map[old_id] = str(uuid4())
        attrs["id"] = id_map[old_id]
    children = node.get("content")
    if isinstance(children, list):
        for child in children:
            _remap_rich_doc_ids(child, id_map, depth + 1)


def clone_bank_question(question: dict[str, Any]) -> dict[str, Any]:
    """Sao chép sâu câu hỏi từ ngân hàng và cấp UUID mới toàn bộ cho mọi định danh con."""
    cloned = copy.deepcopy(question)
    cloned["id"] = str(uuid4())

    block_id_map: dict[str, str] = {}
    raw_block_ids = cloned.get("blockIds")
    if isinstance(raw_block_ids, dict):
        new_block_ids: dict[str, Any] = {}
        for key, val in raw_block_ids.items():
            if isinstance(val, str) and val:
                new_uid = str(uuid4())
                block_id_map[val] = new_uid
                new_block_ids[key] = new_uid
            elif isinstance(val, list):
                remapped_list: list[Any] = []
                for entry in val:
                    if isinstance(entry, str) and entry:
                        new_uid = str(uuid4())
                        block_id_map[entry] = new_uid
                        remapped_list.append(new_uid)
                    else:
                        remapped_list.append(entry)
                new_block_ids[key] = remapped_list
            else:
                new_block_ids[key] = val
        cloned["blockIds"] = new_block_ids
    elif isinstance(raw_block_ids, list):
        remapped_block_list: list[Any] = []
        for entry in raw_block_ids:
            if isinstance(entry, str) and entry:
                new_uid = str(uuid4())
                block_id_map[entry] = new_uid
                remapped_block_list.append(new_uid)
            else:
                remapped_block_list.append(entry)
        cloned["blockIds"] = remapped_block_list

    for doc_key in ("richDoc", "explanationDoc"):
        if isinstance(cloned.get(doc_key), dict):
            _remap_rich_doc_ids(cloned[doc_key], block_id_map)
    option_docs = cloned.get("optionDocs")
    if isinstance(option_docs, list):
        for opt_doc in option_docs:
            if isinstance(opt_doc, dict):
                _remap_rich_doc_ids(opt_doc, block_id_map)

    for list_field in ("formulas", "tables", "images", "rubric"):
        items = cloned.get(list_field)
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    entry["id"] = str(uuid4())
                    if isinstance(entry.get("richDoc"), dict):
                        _remap_rich_doc_ids(entry["richDoc"], block_id_map)

    return cloned


def validate_and_restore_question_bank(
    db: sqlite3.Connection,
    owner_id: str,
    raw_items: Any,
    *,
    dry_run: bool = False,
) -> int:
    """Kiểm tra và khôi phục ngân hàng câu hỏi trong cùng transaction với workspace."""
    if raw_items is None:
        return 0
    if not isinstance(raw_items, list) or len(raw_items) > MAX_RESTORE_ITEMS:
        raise ValueError("Danh sách ngân hàng câu hỏi trong bản sao không hợp lệ.")
    ensure_question_bank_schema(db)

    seen_ids: set[str] = set()
    parsed: list[tuple[str, str, str, str, str, int, int, str, str, str, int, int]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Có mục ngân hàng câu hỏi sai cấu trúc trong bản sao.")
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or str(UUID(raw_id)) != raw_id or raw_id in seen_ids:
            raise ValueError("Mã câu hỏi trong ngân hàng của bản sao bị thiếu hoặc trùng.")
        seen_ids.add(raw_id)

        created_at = item.get("created_at")
        updated_at = item.get("updated_at")
        if (
            isinstance(created_at, bool)
            or isinstance(updated_at, bool)
            or not isinstance(created_at, int)
            or not isinstance(updated_at, int)
            or not 0 < created_at <= updated_at <= 2**53 - 1
        ):
            raise ValueError("Mốc thời gian của câu hỏi trong ngân hàng bản sao không hợp lệ.")

        validated = QuestionBankCreate.model_validate(
            {
                "subject": item.get("subject", ""),
                "grade": item.get("grade", ""),
                "topic": item.get("topic", ""),
                "qtype": item.get("qtype"),
                "level": item.get("level"),
                "points_q4": item.get("points_q4"),
                "tags": item.get("tags", []),
                "question": item.get("question"),
            }
        )
        (
            clean_subject,
            clean_grade,
            clean_topic,
            clean_qtype,
            clean_level,
            clean_points_q4,
            clean_tags,
            search_text,
        ) = _derive_metadata(
            subject=validated.subject,
            grade=validated.grade,
            topic=validated.topic,
            qtype=validated.qtype,
            level=validated.level,
            points_q4=validated.points_q4,
            tags=validated.tags,
            question=validated.question,
        )
        tags_json = json.dumps(clean_tags, ensure_ascii=False, separators=(",", ":"))
        question_json = json.dumps(
            validated.question, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        parsed.append(
            (
                raw_id,
                clean_subject,
                clean_grade,
                clean_topic,
                clean_qtype,
                clean_level,
                clean_points_q4,
                tags_json,
                question_json,
                search_text,
                created_at,
                updated_at,
            )
        )

    for record in parsed:
        (
            item_id,
            subject,
            grade,
            topic,
            qtype,
            level,
            points_q4,
            tags_json,
            question_json,
            search_text,
            created_at,
            updated_at,
        ) = record
        existing = db.execute(
            """
            SELECT owner_id, subject, grade, topic, qtype, level, points_q4,
                   tags_json, question_json, updated_at
            FROM question_bank
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
        if existing:
            same = (
                existing[0] == owner_id
                and existing[1] == subject
                and existing[2] == grade
                and existing[3] == topic
                and existing[4] == qtype
                and existing[5] == level
                and existing[6] == points_q4
                and existing[7] == tags_json
                and existing[8] == question_json
                and existing[9] == updated_at
            )
            if not same:
                raise ValueError(
                    "Câu hỏi trong ngân hàng trùng mã với bản khác ở kho đích. Chưa thay dữ liệu."
                )
        elif not dry_run:
            db.execute(
                """
                INSERT INTO question_bank (
                    id, owner_id, subject, grade, topic, qtype, level, points_q4,
                    tags_json, question_json, search_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    owner_id,
                    subject,
                    grade,
                    topic,
                    qtype,
                    level,
                    points_q4,
                    tags_json,
                    question_json,
                    search_text,
                    created_at,
                    updated_at,
                ),
            )
    return len(parsed)


def _matches_if_match(expected: str, current_updated_at: int) -> bool:
    clean = expected.strip().strip('"')
    if clean == str(current_updated_at):
        return True
    try:
        return int(clean) == current_updated_at
    except ValueError:
        return False


def _default_clock_ms() -> int:
    return int(time.time() * 1000)


def register_question_bank_routes(
    app: FastAPI,
    connect: ConnectCallable,
    *,
    owner_resolver: OwnerResolver | None = None,
    clock: Callable[[], int] = _default_clock_ms,
) -> None:
    """Đăng ký CRUD và clone `/api/question-bank` trên FastAPI + SQLite."""
    resolve_owner: OwnerResolver = owner_resolver or (lambda _request: "local")
    with connect() as db:
        ensure_question_bank_schema(db)

    def current_owner(request: Request) -> str:
        owner_id = resolve_owner(request)
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise AIError(
                "owner_required",
                "Thiếu định danh chủ sở hữu ngân hàng câu hỏi.",
                http_status=401,
            )
        return owner_id.strip()

    @app.get("/api/question-bank")
    def list_question_bank(
        request: Request,
        q: str | None = None,
        subject: str | None = None,
        grade: str | None = None,
        topic: str | None = None,
        qtype: str | None = None,
        level: str | None = None,
        tag: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        owner_id = current_owner(request)
        level_filter: int | None = None
        if level is not None and level.strip() != "":
            raw_lv = level.strip()
            if not raw_lv.isdigit() or not 0 <= int(raw_lv) <= 3:
                raise AIError(
                    "invalid_question_bank_filter",
                    "Tham số level phải là số nguyên từ 0 đến 3.",
                    http_status=422,
                )
            level_filter = int(raw_lv)
        with connect() as db:
            ensure_question_bank_schema(db)
            rows = db.execute(
                """
                SELECT id, owner_id, subject, grade, topic, qtype, level, points_q4,
                       tags_json, question_json, search_text, created_at, updated_at
                FROM question_bank
                WHERE owner_id = ?
                ORDER BY updated_at DESC, id ASC
                """,
                (owner_id,),
            ).fetchall()

        q_tokens = (
            [tok for tok in strip_vietnamese_accents(q).split() if tok]
            if q is not None and q.strip()
            else []
        )
        subj_needle = (
            strip_vietnamese_accents(subject).strip()
            if subject is not None and subject.strip()
            else ""
        )
        grade_needle = _norm_text(grade).casefold() if grade is not None and grade.strip() else ""
        topic_needle = (
            strip_vietnamese_accents(topic).strip() if topic is not None and topic.strip() else ""
        )
        qtype_needle = qtype.strip().lower() if qtype is not None and qtype.strip() else ""
        tag_needle = (
            strip_vietnamese_accents(tag).strip() if tag is not None and tag.strip() else ""
        )

        matched: list[dict[str, Any]] = []
        for row in rows:
            item = _row_to_dict(row)
            search_text = str(row[10] or "")
            if subj_needle and strip_vietnamese_accents(item["subject"]).strip() != subj_needle:
                continue
            if grade_needle and _norm_text(item["grade"]).casefold() != grade_needle:
                continue
            if topic_needle and topic_needle not in strip_vietnamese_accents(item["topic"]):
                continue
            if qtype_needle and item["qtype"] != qtype_needle:
                continue
            if level_filter is not None and item["level"] != level_filter:
                continue
            if tag_needle and not any(
                tag_needle == strip_vietnamese_accents(t).strip() for t in item["tags"]
            ):
                continue
            if q_tokens and not all(tok in search_text for tok in q_tokens):
                continue
            matched.append(item)

        return {"items": matched[:limit], "total": len(matched)}

    @app.post("/api/question-bank", status_code=201)
    def create_question_bank_item(body: QuestionBankCreate, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        try:
            (
                subject,
                grade,
                topic,
                qtype,
                level,
                points_q4,
                tags,
                search_text,
            ) = _derive_metadata(
                subject=body.subject,
                grade=body.grade,
                topic=body.topic,
                qtype=body.qtype,
                level=body.level,
                points_q4=body.points_q4,
                tags=body.tags,
                question=body.question,
            )
        except ValueError as exc:
            raise AIError("invalid_question_bank_item", str(exc), http_status=422) from None

        item_id = str(uuid4())
        now = int(clock())
        tags_json = json.dumps(tags, ensure_ascii=False, separators=(",", ":"))
        question_json = json.dumps(
            body.question, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ensure_question_bank_schema(db)
            db.execute(
                """
                INSERT INTO question_bank (
                    id, owner_id, subject, grade, topic, qtype, level, points_q4,
                    tags_json, question_json, search_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    owner_id,
                    subject,
                    grade,
                    topic,
                    qtype,
                    level,
                    points_q4,
                    tags_json,
                    question_json,
                    search_text,
                    now,
                    now,
                ),
            )
            return {"item": _load_owned_row(db, item_id, owner_id)}

    @app.patch("/api/question-bank/{item_id}")
    def update_question_bank_item(
        item_id: str, body: QuestionBankUpdate, request: Request
    ) -> dict[str, Any]:
        owner_id = current_owner(request)
        updates = body.model_dump(exclude_unset=True)
        expected = request.headers.get("If-Match")
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ensure_question_bank_schema(db)
            existing = _load_owned_row(db, item_id, owner_id)
            if expected is not None and not _matches_if_match(expected, existing["updated_at"]):
                raise AIError(
                    "question_bank_conflict",
                    "Câu hỏi trong ngân hàng đã thay đổi ở phiên bản khác. Tải lại trước khi lưu.",
                    http_status=409,
                )

            merged_question = updates.get("question", existing["question"])
            try:
                (
                    subject,
                    grade,
                    topic,
                    qtype,
                    level,
                    points_q4,
                    tags,
                    search_text,
                ) = _derive_metadata(
                    subject=updates.get("subject", existing["subject"]),
                    grade=updates.get("grade", existing["grade"]),
                    topic=updates.get("topic", existing["topic"]),
                    qtype=updates.get("qtype", existing["qtype"]),
                    level=updates.get("level", existing["level"]),
                    points_q4=updates.get("points_q4", existing["points_q4"]),
                    tags=updates.get("tags", existing["tags"]),
                    question=merged_question,
                )
            except ValueError as exc:
                raise AIError("invalid_question_bank_item", str(exc), http_status=422) from None

            now = int(clock())
            if clock is _default_clock_ms and now <= int(existing["updated_at"]):
                now = int(existing["updated_at"]) + 1
            tags_json = json.dumps(tags, ensure_ascii=False, separators=(",", ":"))
            question_json = json.dumps(
                merged_question, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            db.execute(
                """
                UPDATE question_bank
                SET subject = ?,
                    grade = ?,
                    topic = ?,
                    qtype = ?,
                    level = ?,
                    points_q4 = ?,
                    tags_json = ?,
                    question_json = ?,
                    search_text = ?,
                    updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (
                    subject,
                    grade,
                    topic,
                    qtype,
                    level,
                    points_q4,
                    tags_json,
                    question_json,
                    search_text,
                    now,
                    item_id,
                    owner_id,
                ),
            )
            return {"item": _load_owned_row(db, item_id, owner_id)}

    @app.delete("/api/question-bank/{item_id}")
    def delete_question_bank_item(item_id: str, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            ensure_question_bank_schema(db)
            deleted = db.execute(
                "DELETE FROM question_bank WHERE id = ? AND owner_id = ?",
                (item_id, owner_id),
            ).rowcount
        if not deleted:
            raise _not_found()
        return {"deleted": True, "id": item_id}

    @app.post("/api/question-bank/{item_id}/clone")
    def clone_question_bank_item(item_id: str, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            ensure_question_bank_schema(db)
            existing = _load_owned_row(db, item_id, owner_id)
        cloned = clone_bank_question(existing["question"])
        return {"question": cloned}
