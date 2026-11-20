"""Quản lý mẫu ma trận cá nhân tái sử dụng trong SQLite và đồng bộ sao lưu/khôi phục."""

from __future__ import annotations

import json
import sqlite3
import time
import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mach_backend.ai_contract import AIError

type ConnectCallable = Callable[[], AbstractContextManager[sqlite3.Connection]]
type OwnerResolver = Callable[[Request], str]

MAX_TEMPLATE_QUESTIONS = 30
MAX_TEMPLATE_ROWS = 50
MAX_RESTORE_TEMPLATES = 1000

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS matrix_templates (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    grade TEXT NOT NULL,
    rows_json TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    total_points_q4 INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""
_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_matrix_templates_owner_updated
    ON matrix_templates (owner_id, updated_at DESC)
"""


def _norm_text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _fold(value: str) -> str:
    return _norm_text(value).casefold()


def _strict_int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(message)
    return value


class MatrixTemplateRow(BaseModel):
    """Một dòng cấu trúc theo chủ đề/dạng câu trong mẫu ma trận cá nhân."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=200)
    type: Literal["mcq", "truefalse", "short", "essay"] = "mcq"
    targets: list[int] = Field(min_length=3, max_length=4)
    pointsQ4: int | None = None
    pointsByLevelQ4: list[int | None] | None = None

    @field_validator("topic", mode="after")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        cleaned = _norm_text(value)
        if not cleaned:
            raise ValueError("Chủ đề trong mẫu ma trận không được để trống.")
        return cleaned

    @field_validator("targets", mode="before")
    @classmethod
    def validate_targets(cls, value: Any) -> Any:
        if not isinstance(value, list) or len(value) not in {3, 4}:
            raise ValueError("Mỗi dòng ma trận phải có 3 hoặc 4 mức nhận thức.")
        for item in value:
            num = _strict_int(item, "Số câu mỗi mức phải là số nguyên từ 0 đến 30.")
            if not 0 <= num <= 30:
                raise ValueError("Số câu mỗi mức phải nằm trong khoảng 0 đến 30.")
        return value

    @field_validator("pointsQ4", mode="before")
    @classmethod
    def validate_points_q4(cls, value: Any) -> Any:
        if value is None:
            return None
        num = _strict_int(value, "Điểm/câu (pointsQ4) phải là số nguyên dương (1 = 0,25 điểm).")
        if not 1 <= num <= 40:
            raise ValueError("Điểm/câu (pointsQ4) phải nằm trong khoảng 1..40.")
        return num

    @field_validator("pointsByLevelQ4", mode="before")
    @classmethod
    def validate_points_by_level(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("pointsByLevelQ4 phải là danh sách điểm theo mức.")
        cleaned: list[int | None] = []
        for item in value:
            if item is None:
                cleaned.append(None)
                continue
            num = _strict_int(item, "Điểm theo mức phải là số nguyên dương 1..40.")
            if not 1 <= num <= 40:
                raise ValueError("Điểm theo mức phải nằm trong khoảng 1..40.")
            cleaned.append(num)
        return cleaned

    @model_validator(mode="after")
    def match_level_points_length(self) -> MatrixTemplateRow:
        if self.pointsByLevelQ4 is not None and len(self.pointsByLevelQ4) != len(self.targets):
            raise ValueError("pointsByLevelQ4 phải có cùng độ dài với targets.")
        return self


def _compute_totals(rows: list[MatrixTemplateRow]) -> tuple[int, int]:
    total_questions = sum(sum(row.targets) for row in rows)
    if not 1 <= total_questions <= MAX_TEMPLATE_QUESTIONS:
        raise ValueError(f"Tổng số câu trong mẫu ma trận phải từ 1 đến {MAX_TEMPLATE_QUESTIONS}.")
    explicit_q4 = 0
    for row in rows:
        if row.pointsByLevelQ4 is not None:
            explicit_q4 += sum(
                (row.pointsByLevelQ4[idx] or 0) * count for idx, count in enumerate(row.targets)
            )
        elif row.pointsQ4 is not None:
            explicit_q4 += row.pointsQ4 * sum(row.targets)
    return total_questions, explicit_q4 if explicit_q4 > 0 else 40


class MatrixTemplateCreate(BaseModel):
    """Payload tạo mới mẫu ma trận cá nhân."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=80)
    grade: str = Field(min_length=1, max_length=20)
    rows: list[MatrixTemplateRow] = Field(min_length=1, max_length=MAX_TEMPLATE_ROWS)
    notes: str = Field(default="", max_length=1000)

    @field_validator("name", "subject", "grade", mode="after")
    @classmethod
    def clean_required(cls, value: str) -> str:
        cleaned = _norm_text(value)
        if not cleaned:
            raise ValueError("Tên mẫu, môn học và lớp không được để trống.")
        return cleaned

    @field_validator("notes", mode="after")
    @classmethod
    def clean_notes(cls, value: str) -> str:
        return _norm_text(value)

    @model_validator(mode="after")
    def validate_totals(self) -> MatrixTemplateCreate:
        _compute_totals(self.rows)
        return self


class MatrixTemplateUpdate(BaseModel):
    """Payload cập nhật từng phần mẫu ma trận cá nhân."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    subject: str | None = Field(default=None, min_length=1, max_length=80)
    grade: str | None = Field(default=None, min_length=1, max_length=20)
    rows: list[MatrixTemplateRow] | None = Field(
        default=None, min_length=1, max_length=MAX_TEMPLATE_ROWS
    )
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "subject", "grade", mode="after")
    @classmethod
    def clean_optional_required(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _norm_text(value)
        if not cleaned:
            raise ValueError("Tên mẫu, môn học và lớp không được để trống.")
        return cleaned

    @field_validator("notes", mode="after")
    @classmethod
    def clean_optional_notes(cls, value: str | None) -> str | None:
        return _norm_text(value) if value is not None else None

    @model_validator(mode="after")
    def reject_nulls_and_check_rows(self) -> MatrixTemplateUpdate:
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"Trường '{field_name}' không được nhận giá trị null.")
        if self.rows is not None:
            _compute_totals(self.rows)
        return self


def ensure_matrix_templates_schema(db: sqlite3.Connection) -> None:
    """Bảo đảm bảng `matrix_templates` và index tồn tại trong SQLite."""
    db.execute(_CREATE_TABLE_SQL)
    db.execute(_CREATE_INDEX_SQL)


def _dump_rows(rows: list[MatrixTemplateRow]) -> str:
    return json.dumps(
        [row.model_dump(exclude_none=True) for row in rows],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _row_to_dict(row: Any) -> dict[str, Any]:
    (
        tpl_id,
        owner_id,
        name,
        subject,
        grade,
        rows_json,
        total_questions,
        total_points_q4,
        notes,
        created_at,
        updated_at,
    ) = row
    return {
        "id": tpl_id,
        "owner_id": owner_id,
        "name": name,
        "subject": subject,
        "grade": grade,
        "rows": json.loads(rows_json),
        "total_questions": total_questions,
        "total_points_q4": total_points_q4,
        "notes": notes,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _not_found() -> AIError:
    return AIError(
        "template_not_found",
        "Không tìm thấy mẫu ma trận trong phạm vi tài khoản hiện tại.",
        http_status=404,
    )


def _load_owned_row(db: sqlite3.Connection, template_id: str, owner_id: str) -> dict[str, Any]:
    row = db.execute(
        """
        SELECT id, owner_id, name, subject, grade, rows_json,
               total_questions, total_points_q4, notes, created_at, updated_at
        FROM matrix_templates
        WHERE id = ? AND owner_id = ?
        """,
        (template_id, owner_id),
    ).fetchone()
    if row is None:
        raise _not_found()
    return _row_to_dict(row)


def list_owner_matrix_templates(db: sqlite3.Connection, owner_id: str) -> list[dict[str, Any]]:
    """Đọc toàn bộ mẫu ma trận của một chủ sở hữu để phục vụ sao lưu."""
    ensure_matrix_templates_schema(db)
    rows = db.execute(
        """
        SELECT id, owner_id, name, subject, grade, rows_json,
               total_questions, total_points_q4, notes, created_at, updated_at
        FROM matrix_templates
        WHERE owner_id = ?
        ORDER BY updated_at DESC, id ASC
        """,
        (owner_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def validate_and_restore_matrix_templates(
    db: sqlite3.Connection,
    owner_id: str,
    raw_items: Any,
    *,
    dry_run: bool = False,
) -> int:
    """Kiểm tra và chèn mẫu ma trận vào transaction khôi phục kho."""
    if raw_items is None:
        return 0
    if not isinstance(raw_items, list) or len(raw_items) > MAX_RESTORE_TEMPLATES:
        raise ValueError("Danh sách mẫu ma trận trong bản sao không hợp lệ.")
    ensure_matrix_templates_schema(db)
    seen_ids: set[str] = set()
    parsed_items: list[tuple[str, MatrixTemplateCreate, int, int, str, float, float]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Có mẫu ma trận sai cấu trúc trong bản sao.")
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or str(UUID(raw_id)) != raw_id or raw_id in seen_ids:
            raise ValueError("Mã mẫu ma trận trong bản sao bị thiếu hoặc trùng.")
        seen_ids.add(raw_id)
        created_at = item.get("created_at")
        updated_at = item.get("updated_at")
        if (
            isinstance(created_at, bool)
            or isinstance(updated_at, bool)
            or not isinstance(created_at, (int, float))
            or not isinstance(updated_at, (int, float))
            or not 0 < float(created_at) <= float(updated_at)
        ):
            raise ValueError("Mốc thời gian của mẫu ma trận trong bản sao không hợp lệ.")
        validated = MatrixTemplateCreate.model_validate(
            {
                "name": item.get("name"),
                "subject": item.get("subject"),
                "grade": item.get("grade"),
                "rows": item.get("rows"),
                "notes": item.get("notes", ""),
            }
        )
        total_q, total_q4 = _compute_totals(validated.rows)
        rows_json = _dump_rows(validated.rows)
        parsed_items.append(
            (
                raw_id,
                validated,
                total_q,
                total_q4,
                rows_json,
                float(created_at),
                float(updated_at),
            )
        )

    for tpl_id, validated, total_q, total_q4, rows_json, created_at, updated_at in parsed_items:
        existing = db.execute(
            """
            SELECT owner_id, name, subject, grade, rows_json, notes, updated_at
            FROM matrix_templates
            WHERE id = ?
            """,
            (tpl_id,),
        ).fetchone()
        if existing:
            same = (
                existing[0] == owner_id
                and existing[1] == validated.name
                and existing[2] == validated.subject
                and existing[3] == validated.grade
                and existing[4] == rows_json
                and existing[5] == validated.notes
                and abs(float(existing[6]) - updated_at) < 1e-6
            )
            if not same:
                raise ValueError(
                    "Mẫu ma trận trùng mã với bản khác trong kho đích. Chưa thay dữ liệu."
                )
        elif not dry_run:
            db.execute(
                """
                INSERT INTO matrix_templates (
                    id, owner_id, name, subject, grade, rows_json,
                    total_questions, total_points_q4, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tpl_id,
                    owner_id,
                    validated.name,
                    validated.subject,
                    validated.grade,
                    rows_json,
                    total_q,
                    total_q4,
                    validated.notes,
                    created_at,
                    updated_at,
                ),
            )
    return len(parsed_items)


def _matches_if_match(expected: str, current_updated_at: float) -> bool:
    clean = expected.strip().strip('"')
    if clean == str(current_updated_at):
        return True
    try:
        return abs(float(clean) - float(current_updated_at)) < 1e-6
    except ValueError:
        return False


def install_matrix_templates(
    app: FastAPI,
    connect: ConnectCallable,
    *,
    owner_resolver: OwnerResolver | None = None,
    clock: Callable[[], float] = time.time,
) -> None:
    """Cài đặt CRUD `/api/matrix-templates` trên FastAPI và khởi tạo bảng SQLite."""
    resolve_owner: OwnerResolver = owner_resolver or (lambda _request: "local")
    with connect() as db:
        ensure_matrix_templates_schema(db)

    def current_owner(request: Request) -> str:
        owner_id = resolve_owner(request)
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise AIError(
                "owner_required", "Thiếu định danh chủ sở hữu mẫu ma trận.", http_status=401
            )
        return owner_id.strip()

    @app.get("/api/matrix-templates")
    def list_templates(
        request: Request,
        subject: str | None = None,
        grade: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            items = list_owner_matrix_templates(db, owner_id)
        if subject is not None and _fold(subject):
            expected = _fold(subject)
            items = [item for item in items if _fold(item["subject"]) == expected]
        if grade is not None and _fold(grade):
            expected = _fold(grade)
            items = [item for item in items if _fold(item["grade"]) == expected]
        if q is not None and _fold(q):
            needle = _fold(q)
            items = [
                item
                for item in items
                if any(
                    needle in _fold(text)
                    for text in (
                        item["name"],
                        item["subject"],
                        item["grade"],
                        item["notes"],
                        *[row.get("topic", "") for row in item["rows"]],
                    )
                )
            ]
        return {"templates": items, "total": len(items)}

    @app.post("/api/matrix-templates", status_code=201)
    def create_template(body: MatrixTemplateCreate, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        tpl_id = str(uuid4())
        now = float(clock())
        total_q, total_q4 = _compute_totals(body.rows)
        rows_json = _dump_rows(body.rows)
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ensure_matrix_templates_schema(db)
            db.execute(
                """
                INSERT INTO matrix_templates (
                    id, owner_id, name, subject, grade, rows_json,
                    total_questions, total_points_q4, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tpl_id,
                    owner_id,
                    body.name,
                    body.subject,
                    body.grade,
                    rows_json,
                    total_q,
                    total_q4,
                    body.notes,
                    now,
                    now,
                ),
            )
            return _load_owned_row(db, tpl_id, owner_id)

    @app.get("/api/matrix-templates/{template_id}")
    def get_template(template_id: str, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            ensure_matrix_templates_schema(db)
            return _load_owned_row(db, template_id, owner_id)

    @app.patch("/api/matrix-templates/{template_id}")
    def update_template(
        template_id: str, body: MatrixTemplateUpdate, request: Request
    ) -> dict[str, Any]:
        owner_id = current_owner(request)
        updates = body.model_dump(exclude_unset=True)
        expected = request.headers.get("If-Match")
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ensure_matrix_templates_schema(db)
            existing = _load_owned_row(db, template_id, owner_id)
            if expected is not None and not _matches_if_match(expected, existing["updated_at"]):
                raise AIError(
                    "template_conflict",
                    "Mẫu ma trận đã thay đổi ở phiên bản khác. Tải lại trước khi lưu.",
                    http_status=409,
                )
            merged_rows = (
                body.rows
                if body.rows is not None
                else [MatrixTemplateRow.model_validate(row) for row in existing["rows"]]
            )
            total_q, total_q4 = _compute_totals(merged_rows)
            now = float(clock())
            if clock is time.time and now <= float(existing["updated_at"]):
                now = float(existing["updated_at"]) + 0.001
            db.execute(
                """
                UPDATE matrix_templates
                SET name = ?,
                    subject = ?,
                    grade = ?,
                    rows_json = ?,
                    total_questions = ?,
                    total_points_q4 = ?,
                    notes = ?,
                    updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (
                    updates.get("name", existing["name"]),
                    updates.get("subject", existing["subject"]),
                    updates.get("grade", existing["grade"]),
                    _dump_rows(merged_rows),
                    total_q,
                    total_q4,
                    updates.get("notes", existing["notes"]),
                    now,
                    template_id,
                    owner_id,
                ),
            )
            return _load_owned_row(db, template_id, owner_id)

    @app.delete("/api/matrix-templates/{template_id}")
    def delete_template(template_id: str, request: Request) -> dict[str, Any]:
        owner_id = current_owner(request)
        with connect() as db:
            ensure_matrix_templates_schema(db)
            deleted = db.execute(
                "DELETE FROM matrix_templates WHERE id = ? AND owner_id = ?",
                (template_id, owner_id),
            ).rowcount
        if not deleted:
            raise _not_found()
        return {"deleted": True, "id": template_id}
