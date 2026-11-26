"""Chiến dịch nhiều đề, nhắc lịch giáo viên và Trợ lý Chủ động (Proactive Digest) trên SQLite."""

from __future__ import annotations

import inspect
import json
import sqlite3
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

type ConnectCallable = Callable[[], AbstractContextManager[sqlite3.Connection]]
type OwnerResolver = Callable[[Request], str]
type StateLoader = Callable[..., Any]

CampaignStatus = Literal["active", "completed", "archived"]
ALLOWED_CAMPAIGN_STATUSES: frozenset[str] = frozenset({"active", "completed", "archived"})
ALLOWED_REMINDER_KINDS: frozenset[str] = frozenset(
    {"deadline", "review", "campaign", "grading", "general"}
)
MAX_RESTORE_ITEMS = 2000
VN_TZ = timezone(timedelta(hours=7))

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exam_campaigns (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    target_count INTEGER NOT NULL DEFAULT 1,
    exam_ids_json TEXT NOT NULL DEFAULT '[]',
    due_at INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    note TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exam_campaigns_owner
    ON exam_campaigns (owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS teacher_reminders (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'general',
    target_type TEXT NOT NULL DEFAULT '',
    target_id TEXT NOT NULL DEFAULT '',
    remind_at INTEGER,
    snoozed_until INTEGER,
    done_at INTEGER,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_teacher_reminders_owner
    ON teacher_reminders (owner_id, remind_at ASC);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


def ensure_campaign_tables(db: sqlite3.Connection) -> None:
    """Đảm bảo 2 bảng chiến dịch và nhắc lịch đã tồn tại trong SQLite."""
    db.executescript(_SCHEMA_SQL)


def _clean_exam_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            val = item.strip()
            if val and val not in seen:
                seen.add(val)
                out.append(val)
    return out


def _parse_exam_ids_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return _clean_exam_ids(parsed)


def _load_state_safe(state_loader: StateLoader, request: Request | None = None) -> dict[str, Any]:
    if state_loader is None:
        return {}
    try:
        params = inspect.signature(state_loader).parameters
        raw = state_loader(request) if len(params) >= 1 else state_loader()
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _active_exams_map(
    state: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    trash_ids: set[str] = set()
    for item in state.get("trash") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            trash_ids.add(item["id"])
    exams_by_id: dict[str, dict[str, Any]] = {}
    active_list: list[dict[str, Any]] = []
    for exam in state.get("exams") or []:
        if not isinstance(exam, dict):
            continue
        eid = exam.get("id")
        if not isinstance(eid, str) or not eid or eid in trash_ids:
            continue
        if exam.get("deleted") or exam.get("trashed"):
            continue
        exams_by_id[eid] = exam
        active_list.append(exam)
    return exams_by_id, active_list


def _is_question_approved(q: dict[str, Any]) -> bool:
    if q.get("approvalStatus") == "approved":
        return True
    if q.get("approved") is True or q.get("approvedAt"):
        return True
    return False


def _serialize_campaign(
    row: sqlite3.Row | tuple[Any, ...],
    exams_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    (
        cid,
        owner_id,
        title,
        subject,
        grade,
        target_count,
        exam_ids_json,
        due_at,
        status,
        note,
        created_at,
        updated_at,
    ) = row
    exam_ids = _parse_exam_ids_json(exam_ids_json)
    linked_exams: list[dict[str, Any]] = []
    completed_count = 0
    ready_count = 0
    for eid in exam_ids:
        ex = exams_by_id.get(eid)
        if ex is None:
            continue
        questions = ex.get("questions")
        q_count = len(questions) if isinstance(questions, list) else 0
        has_questions = q_count > 0
        # Ưu tiên tính đủ các đề liên kết còn hoạt động (không nằm trong thùng rác).
        completed_count += 1
        if has_questions:
            ready_count += 1
        linked_exams.append(
            {
                "id": eid,
                "title": str(ex.get("title") or "Đề chưa đặt tên"),
                "questionCount": q_count,
                "workflowStatus": str(ex.get("workflowStatus") or "draft"),
            }
        )
    target = max(1, int(target_count or 1))
    remaining = max(0, target - completed_count)
    next_ordinal = completed_count + 1
    effective_status = status or "active"
    if effective_status == "active" and completed_count >= target:
        effective_status = "completed"
    return {
        "id": cid,
        "ownerId": owner_id,
        "title": title,
        "subject": subject or "",
        "grade": grade or "",
        "targetCount": target,
        "examIds": exam_ids,
        "linkedExams": linked_exams,
        "completedCount": completed_count,
        "readyCount": ready_count,
        "remainingCount": remaining,
        "nextOrdinal": next_ordinal,
        "dueAt": due_at,
        "status": effective_status,
        "note": note or "",
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def _serialize_reminder(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    (
        rid,
        owner_id,
        title,
        kind,
        target_type,
        target_id,
        remind_at,
        snoozed_until,
        done_at,
        created_at,
    ) = row
    return {
        "id": rid,
        "ownerId": owner_id,
        "title": title,
        "kind": kind or "general",
        "targetType": target_type or "",
        "targetId": target_id or "",
        "remindAt": remind_at,
        "snoozedUntil": snoozed_until,
        "doneAt": done_at,
        "done": done_at is not None,
        "createdAt": created_at,
    }


def _greeting_for_ms(now_ms: int) -> str:
    dt = datetime.fromtimestamp(now_ms / 1000.0, tz=VN_TZ)
    hour = dt.hour
    if 5 <= hour < 12:
        return "Chào buổi sáng thầy cô"
    if 12 <= hour < 18:
        return "Chào buổi chiều thầy cô"
    return "Chào buổi tối thầy cô"


def _query_pending_room_grading(db: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    try:
        has_rooms = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='exam_rooms'"
        ).fetchone()
        has_attempts = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='room_attempts'"
        ).fetchone()
        if not has_rooms or not has_attempts:
            return {"count": 0, "rooms": []}
        rows = db.execute(
            """
            SELECT r.id, r.title, r.room_code, COUNT(a.id) AS pending_count
            FROM exam_rooms r
            JOIN room_attempts a ON a.room_id = r.id
            WHERE r.owner_id = ?
              AND a.status IN ('submitted', 'auto_submitted', 'locked')
              AND a.grading_status = 'needs_manual'
            GROUP BY r.id, r.title, r.room_code
            ORDER BY pending_count DESC, r.updated_at DESC
            """,
            (owner_id,),
        ).fetchall()
        rooms = [
            {
                "roomId": row[0],
                "title": row[1],
                "roomCode": row[2],
                "pendingCount": int(row[3] or 0),
            }
            for row in rows
            if int(row[3] or 0) > 0
        ]
        total = sum(r["pendingCount"] for r in rooms)
        return {"count": total, "rooms": rooms}
    except sqlite3.Error:
        return {"count": 0, "rooms": []}


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    subject: str = Field(default="", max_length=80)
    grade: str = Field(default="", max_length=40)
    targetCount: int = Field(default=5, ge=1, le=200)
    examIds: list[str] = Field(default_factory=list, max_length=200)
    dueAt: int | None = None
    note: str = Field(default="", max_length=1000)


class CampaignPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=80)
    grade: str | None = Field(default=None, max_length=40)
    targetCount: int | None = Field(default=None, ge=1, le=200)
    examIds: list[str] | None = Field(default=None, max_length=200)
    dueAt: int | None = None
    status: CampaignStatus | None = None
    note: str | None = Field(default=None, max_length=1000)


class LinkExamPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    examId: str = Field(min_length=1, max_length=128)


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=240)
    kind: str = Field(default="general", max_length=40)
    targetType: str = Field(default="", max_length=40)
    targetId: str = Field(default="", max_length=128)
    remindAt: int | None = None


class ReminderPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(default=None, min_length=1, max_length=240)
    kind: str | None = Field(default=None, max_length=40)
    targetType: str | None = Field(default=None, max_length=40)
    targetId: str | None = Field(default=None, max_length=128)
    remindAt: int | None = None
    done: bool | None = None
    snoozeHours: float | None = Field(default=None, gt=0, le=720)


# ==================== BACKUP & RESTORE HELPERS ====================


def list_owner_campaigns(db: sqlite3.Connection, owner_id: str) -> list[dict[str, Any]]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'exam_campaigns'"
    ).fetchone()
    if not exists:
        return []
    rows = db.execute(
        """
        SELECT id, title, subject, grade, target_count, exam_ids_json, due_at, status,
               note, created_at, updated_at
        FROM exam_campaigns
        WHERE owner_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (owner_id,),
    ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "subject": row[2],
            "grade": row[3],
            "targetCount": row[4],
            "examIds": _parse_exam_ids_json(row[5]),
            "dueAt": row[6],
            "status": row[7],
            "note": row[8],
            "createdAt": row[9],
            "updatedAt": row[10],
        }
        for row in rows
    ]


def list_owner_reminders(db: sqlite3.Connection, owner_id: str) -> list[dict[str, Any]]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'teacher_reminders'"
    ).fetchone()
    if not exists:
        return []
    rows = db.execute(
        """
        SELECT id, title, kind, target_type, target_id, remind_at, snoozed_until,
               done_at, created_at
        FROM teacher_reminders
        WHERE owner_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (owner_id,),
    ).fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "kind": row[2],
            "targetType": row[3],
            "targetId": row[4],
            "remindAt": row[5],
            "snoozedUntil": row[6],
            "doneAt": row[7],
            "createdAt": row[8],
        }
        for row in rows
    ]


def validate_and_restore_campaigns(
    db: sqlite3.Connection,
    owner_id: str,
    raw: Any,
    *,
    dry_run: bool = False,
) -> int:
    if raw is None or raw == []:
        return 0
    if not isinstance(raw, list) or len(raw) > MAX_RESTORE_ITEMS:
        raise ValueError("Danh sách chiến dịch trong bản sao không hợp lệ.")
    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    now = _now_ms()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Mục chiến dịch trong bản sao không hợp lệ.")
        cid = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not cid or cid in seen_ids or not title or len(title) > 200:
            raise ValueError("Chiến dịch trong bản sao thiếu mã hoặc tiêu đề hợp lệ.")
        seen_ids.add(cid)
        target_count = item.get("targetCount", item.get("target_count", 1))
        if (
            isinstance(target_count, bool)
            or not isinstance(target_count, int)
            or not 1 <= target_count <= 200
        ):
            raise ValueError("Số đề mục tiêu trong chiến dịch không hợp lệ.")
        status = str(item.get("status") or "active")
        if status not in ALLOWED_CAMPAIGN_STATUSES:
            status = "active"
        exam_ids = _clean_exam_ids(item.get("examIds", item.get("exam_ids", [])))
        due_at = item.get("dueAt", item.get("due_at"))
        if due_at is not None and (isinstance(due_at, bool) or not isinstance(due_at, int)):
            raise ValueError("Mốc hạn chiến dịch trong bản sao không hợp lệ.")
        created_at = item.get("createdAt", item.get("created_at"))
        updated_at = item.get("updatedAt", item.get("updated_at"))
        created_val = (
            created_at if isinstance(created_at, int) and not isinstance(created_at, bool) else now
        )
        updated_val = (
            updated_at
            if isinstance(updated_at, int) and not isinstance(updated_at, bool)
            else created_val
        )
        cleaned.append(
            {
                "id": cid,
                "owner_id": owner_id,
                "title": title,
                "subject": str(item.get("subject") or "")[:80],
                "grade": str(item.get("grade") or "")[:40],
                "target_count": target_count,
                "exam_ids_json": json.dumps(exam_ids, ensure_ascii=False),
                "due_at": due_at,
                "status": status,
                "note": str(item.get("note") or "")[:1000],
                "created_at": created_val,
                "updated_at": updated_val,
            }
        )
    if dry_run:
        return len(cleaned)
    ensure_campaign_tables(db)
    for rec in cleaned:
        existing = db.execute(
            "SELECT owner_id FROM exam_campaigns WHERE id = ?",
            (rec["id"],),
        ).fetchone()
        if existing and existing[0] != owner_id:
            raise ValueError("Chiến dịch trùng mã với dữ liệu của tài khoản khác trong kho đích.")
        db.execute(
            """
            INSERT INTO exam_campaigns (
                id, owner_id, title, subject, grade, target_count, exam_ids_json,
                due_at, status, note, created_at, updated_at
            ) VALUES (
                :id, :owner_id, :title, :subject, :grade, :target_count, :exam_ids_json,
                :due_at, :status, :note, :created_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                subject = excluded.subject,
                grade = excluded.grade,
                target_count = excluded.target_count,
                exam_ids_json = excluded.exam_ids_json,
                due_at = excluded.due_at,
                status = excluded.status,
                note = excluded.note,
                updated_at = excluded.updated_at
            WHERE exam_campaigns.owner_id = excluded.owner_id
            """,
            rec,
        )
    return len(cleaned)


def validate_and_restore_reminders(
    db: sqlite3.Connection,
    owner_id: str,
    raw: Any,
    *,
    dry_run: bool = False,
) -> int:
    if raw is None or raw == []:
        return 0
    if not isinstance(raw, list) or len(raw) > MAX_RESTORE_ITEMS:
        raise ValueError("Danh sách nhắc lịch trong bản sao không hợp lệ.")
    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    now = _now_ms()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Mục nhắc lịch trong bản sao không hợp lệ.")
        rid = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not rid or rid in seen_ids or not title or len(title) > 240:
            raise ValueError("Nhắc lịch trong bản sao thiếu mã hoặc tiêu đề hợp lệ.")
        seen_ids.add(rid)
        kind = str(item.get("kind") or "general").strip() or "general"
        if kind not in ALLOWED_REMINDER_KINDS:
            kind = "general"

        def _opt_int(src: dict[str, Any], key1: str, key2: str) -> int | None:
            val = src.get(key1, src.get(key2))
            if val is None:
                return None
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError("Mốc thời gian nhắc lịch trong bản sao không hợp lệ.")
            return val

        remind_at = _opt_int(item, "remindAt", "remind_at")
        snoozed_until = _opt_int(item, "snoozedUntil", "snoozed_until")
        done_at = _opt_int(item, "doneAt", "done_at")
        created_at = _opt_int(item, "createdAt", "created_at") or now
        cleaned.append(
            {
                "id": rid,
                "owner_id": owner_id,
                "title": title,
                "kind": kind,
                "target_type": str(item.get("targetType", item.get("target_type", "")) or "")[:40],
                "target_id": str(item.get("targetId", item.get("target_id", "")) or "")[:128],
                "remind_at": remind_at,
                "snoozed_until": snoozed_until,
                "done_at": done_at,
                "created_at": created_at,
            }
        )
    if dry_run:
        return len(cleaned)
    ensure_campaign_tables(db)
    for rec in cleaned:
        existing = db.execute(
            "SELECT owner_id FROM teacher_reminders WHERE id = ?",
            (rec["id"],),
        ).fetchone()
        if existing and existing[0] != owner_id:
            raise ValueError("Nhắc lịch trùng mã với dữ liệu của tài khoản khác trong kho đích.")
        db.execute(
            """
            INSERT INTO teacher_reminders (
                id, owner_id, title, kind, target_type, target_id,
                remind_at, snoozed_until, done_at, created_at
            ) VALUES (
                :id, :owner_id, :title, :kind, :target_type, :target_id,
                :remind_at, :snoozed_until, :done_at, :created_at
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                kind = excluded.kind,
                target_type = excluded.target_type,
                target_id = excluded.target_id,
                remind_at = excluded.remind_at,
                snoozed_until = excluded.snoozed_until,
                done_at = excluded.done_at
            WHERE teacher_reminders.owner_id = excluded.owner_id
            """,
            rec,
        )
    return len(cleaned)


# ==================== FASTAPI ROUTES ====================


def install_campaign_routes(
    app: FastAPI,
    connect_fn: ConnectCallable,
    state_loader: StateLoader,
    owner_resolver: OwnerResolver | None = None,
) -> None:
    """Gắn các tuyến API chiến dịch nhiều đề, nhắc lịch và Trợ lý Chủ động."""
    resolve_owner: OwnerResolver = owner_resolver or (lambda _req: "local")

    with connect_fn() as db:
        ensure_campaign_tables(db)

    @app.get("/api/campaigns")
    def list_campaigns(request: Request):
        owner_id = resolve_owner(request)
        state = _load_state_safe(state_loader, request)
        exams_by_id, _ = _active_exams_map(state)
        with connect_fn() as db:
            ensure_campaign_tables(db)
            rows = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE owner_id = ?
                ORDER BY updated_at DESC, created_at DESC
                """,
                (owner_id,),
            ).fetchall()
        return {"campaigns": [_serialize_campaign(row, exams_by_id) for row in rows]}

    @app.post("/api/campaigns", status_code=201)
    def create_campaign(payload: CampaignCreate, request: Request):
        owner_id = resolve_owner(request)
        state = _load_state_safe(state_loader, request)
        exams_by_id, _ = _active_exams_map(state)
        now = _now_ms()
        cid = str(uuid4())
        exam_ids = _clean_exam_ids(payload.examIds)
        with connect_fn() as db:
            ensure_campaign_tables(db)
            db.execute(
                """
                INSERT INTO exam_campaigns (
                    id, owner_id, title, subject, grade, target_count, exam_ids_json,
                    due_at, status, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    cid,
                    owner_id,
                    payload.title.strip(),
                    payload.subject.strip(),
                    payload.grade.strip(),
                    payload.targetCount,
                    json.dumps(exam_ids, ensure_ascii=False),
                    payload.dueAt,
                    payload.note.strip(),
                    now,
                    now,
                ),
            )
            row = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE id = ? AND owner_id = ?
                """,
                (cid, owner_id),
            ).fetchone()
        return {"campaign": _serialize_campaign(row, exams_by_id)}

    @app.patch("/api/campaigns/{campaign_id}")
    def patch_campaign(campaign_id: str, payload: CampaignPatch, request: Request):
        owner_id = resolve_owner(request)
        state = _load_state_safe(state_loader, request)
        exams_by_id, _ = _active_exams_map(state)
        now = _now_ms()
        with connect_fn() as db:
            ensure_campaign_tables(db)
            existing = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE id = ? AND owner_id = ?
                """,
                (campaign_id, owner_id),
            ).fetchone()
            if existing is None:
                raise HTTPException(404, "Không tìm thấy chiến dịch soạn đề.")
            fields = payload.model_fields_set
            title = (
                payload.title.strip()
                if "title" in fields and payload.title is not None
                else existing[2]
            )
            subject = (
                payload.subject.strip()
                if "subject" in fields and payload.subject is not None
                else existing[3]
            )
            grade = (
                payload.grade.strip()
                if "grade" in fields and payload.grade is not None
                else existing[4]
            )
            target_count = (
                payload.targetCount
                if "targetCount" in fields and payload.targetCount is not None
                else existing[5]
            )
            exam_ids_json = (
                json.dumps(_clean_exam_ids(payload.examIds), ensure_ascii=False)
                if "examIds" in fields and payload.examIds is not None
                else existing[6]
            )
            due_at = payload.dueAt if "dueAt" in fields else existing[7]
            status = (
                payload.status if "status" in fields and payload.status is not None else existing[8]
            )
            note = (
                payload.note.strip()
                if "note" in fields and payload.note is not None
                else existing[9]
            )
            db.execute(
                """
                UPDATE exam_campaigns
                SET title = ?, subject = ?, grade = ?, target_count = ?, exam_ids_json = ?,
                    due_at = ?, status = ?, note = ?, updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (
                    title,
                    subject,
                    grade,
                    target_count,
                    exam_ids_json,
                    due_at,
                    status,
                    note,
                    now,
                    campaign_id,
                    owner_id,
                ),
            )
            row = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE id = ? AND owner_id = ?
                """,
                (campaign_id, owner_id),
            ).fetchone()
        return {"campaign": _serialize_campaign(row, exams_by_id)}

    @app.delete("/api/campaigns/{campaign_id}")
    def delete_campaign(campaign_id: str, request: Request):
        owner_id = resolve_owner(request)
        with connect_fn() as db:
            ensure_campaign_tables(db)
            cur = db.execute(
                "DELETE FROM exam_campaigns WHERE id = ? AND owner_id = ?",
                (campaign_id, owner_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Không tìm thấy chiến dịch soạn đề.")
        return {"deleted": True, "id": campaign_id}

    @app.post("/api/campaigns/{campaign_id}/link-exam")
    def link_exam_to_campaign(campaign_id: str, payload: LinkExamPayload, request: Request):
        owner_id = resolve_owner(request)
        state = _load_state_safe(state_loader, request)
        exams_by_id, _ = _active_exams_map(state)
        now = _now_ms()
        exam_id = payload.examId.strip()
        with connect_fn() as db:
            ensure_campaign_tables(db)
            existing = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE id = ? AND owner_id = ?
                """,
                (campaign_id, owner_id),
            ).fetchone()
            if existing is None:
                raise HTTPException(404, "Không tìm thấy chiến dịch soạn đề.")
            exam_ids = _parse_exam_ids_json(existing[6])
            if exam_id not in exam_ids:
                exam_ids.append(exam_id)
            db.execute(
                """
                UPDATE exam_campaigns
                SET exam_ids_json = ?, updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (json.dumps(exam_ids, ensure_ascii=False), now, campaign_id, owner_id),
            )
            row = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE id = ? AND owner_id = ?
                """,
                (campaign_id, owner_id),
            ).fetchone()
        return {"campaign": _serialize_campaign(row, exams_by_id)}

    @app.get("/api/reminders")
    def list_reminders(
        request: Request,
        includeDone: bool = Query(default=True),
    ):
        owner_id = resolve_owner(request)
        with connect_fn() as db:
            ensure_campaign_tables(db)
            if includeDone:
                rows = db.execute(
                    """
                    SELECT id, owner_id, title, kind, target_type, target_id,
                           remind_at, snoozed_until, done_at, created_at
                    FROM teacher_reminders
                    WHERE owner_id = ?
                    ORDER BY done_at IS NOT NULL ASC, remind_at IS NULL ASC,
                             remind_at ASC, created_at DESC
                    """,
                    (owner_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    """
                    SELECT id, owner_id, title, kind, target_type, target_id,
                           remind_at, snoozed_until, done_at, created_at
                    FROM teacher_reminders
                    WHERE owner_id = ? AND done_at IS NULL
                    ORDER BY remind_at IS NULL ASC, remind_at ASC, created_at DESC
                    """,
                    (owner_id,),
                ).fetchall()
        return {"reminders": [_serialize_reminder(row) for row in rows]}

    @app.post("/api/reminders", status_code=201)
    def create_reminder(payload: ReminderCreate, request: Request):
        owner_id = resolve_owner(request)
        now = _now_ms()
        rid = str(uuid4())
        kind = payload.kind.strip() if payload.kind.strip() in ALLOWED_REMINDER_KINDS else "general"
        with connect_fn() as db:
            ensure_campaign_tables(db)
            db.execute(
                """
                INSERT INTO teacher_reminders (
                    id, owner_id, title, kind, target_type, target_id,
                    remind_at, snoozed_until, done_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                """,
                (
                    rid,
                    owner_id,
                    payload.title.strip(),
                    kind,
                    payload.targetType.strip(),
                    payload.targetId.strip(),
                    payload.remindAt,
                    now,
                ),
            )
            row = db.execute(
                """
                SELECT id, owner_id, title, kind, target_type, target_id,
                       remind_at, snoozed_until, done_at, created_at
                FROM teacher_reminders
                WHERE id = ? AND owner_id = ?
                """,
                (rid, owner_id),
            ).fetchone()
        return {"reminder": _serialize_reminder(row)}

    @app.patch("/api/reminders/{reminder_id}")
    def patch_reminder(reminder_id: str, payload: ReminderPatch, request: Request):
        owner_id = resolve_owner(request)
        now = _now_ms()
        with connect_fn() as db:
            ensure_campaign_tables(db)
            existing = db.execute(
                """
                SELECT id, owner_id, title, kind, target_type, target_id,
                       remind_at, snoozed_until, done_at, created_at
                FROM teacher_reminders
                WHERE id = ? AND owner_id = ?
                """,
                (reminder_id, owner_id),
            ).fetchone()
            if existing is None:
                raise HTTPException(404, "Không tìm thấy nhắc lịch.")
            fields = payload.model_fields_set
            title = (
                payload.title.strip()
                if "title" in fields and payload.title is not None
                else existing[2]
            )
            kind = (
                payload.kind.strip()
                if "kind" in fields
                and payload.kind is not None
                and payload.kind.strip() in ALLOWED_REMINDER_KINDS
                else existing[3]
            )
            target_type = (
                payload.targetType.strip()
                if "targetType" in fields and payload.targetType is not None
                else existing[4]
            )
            target_id = (
                payload.targetId.strip()
                if "targetId" in fields and payload.targetId is not None
                else existing[5]
            )
            remind_at = payload.remindAt if "remindAt" in fields else existing[6]
            snoozed_until = existing[7]
            if "snoozeHours" in fields and payload.snoozeHours is not None:
                snoozed_until = now + int(round(payload.snoozeHours * 3600 * 1000))
            done_at = existing[8]
            if "done" in fields and payload.done is not None:
                done_at = now if payload.done else None
            db.execute(
                """
                UPDATE teacher_reminders
                SET title = ?, kind = ?, target_type = ?, target_id = ?,
                    remind_at = ?, snoozed_until = ?, done_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (
                    title,
                    kind,
                    target_type,
                    target_id,
                    remind_at,
                    snoozed_until,
                    done_at,
                    reminder_id,
                    owner_id,
                ),
            )
            row = db.execute(
                """
                SELECT id, owner_id, title, kind, target_type, target_id,
                       remind_at, snoozed_until, done_at, created_at
                FROM teacher_reminders
                WHERE id = ? AND owner_id = ?
                """,
                (reminder_id, owner_id),
            ).fetchone()
        return {"reminder": _serialize_reminder(row)}

    @app.delete("/api/reminders/{reminder_id}")
    def delete_reminder(reminder_id: str, request: Request):
        owner_id = resolve_owner(request)
        with connect_fn() as db:
            ensure_campaign_tables(db)
            cur = db.execute(
                "DELETE FROM teacher_reminders WHERE id = ? AND owner_id = ?",
                (reminder_id, owner_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "Không tìm thấy nhắc lịch.")
        return {"deleted": True, "id": reminder_id}

    @app.get("/api/proactive/digest")
    def proactive_digest(
        request: Request,
        reviewThresholdHours: float = Query(default=18.0, ge=0.0, le=720.0),
        nowMs: int | None = Query(default=None),
    ):
        owner_id = resolve_owner(request)
        now = int(nowMs) if nowMs is not None else _now_ms()
        state = _load_state_safe(state_loader, request)
        exams_by_id, active_exams = _active_exams_map(state)

        with connect_fn() as db:
            ensure_campaign_tables(db)
            campaign_rows = db.execute(
                """
                SELECT id, owner_id, title, subject, grade, target_count, exam_ids_json,
                       due_at, status, note, created_at, updated_at
                FROM exam_campaigns
                WHERE owner_id = ?
                ORDER BY due_at IS NULL ASC, due_at ASC, updated_at DESC
                """,
                (owner_id,),
            ).fetchall()
            reminder_rows = db.execute(
                """
                SELECT id, owner_id, title, kind, target_type, target_id,
                       remind_at, snoozed_until, done_at, created_at
                FROM teacher_reminders
                WHERE owner_id = ? AND done_at IS NULL
                ORDER BY remind_at IS NULL ASC, remind_at ASC, created_at DESC
                """,
                (owner_id,),
            ).fetchall()
            pending_grading = _query_pending_room_grading(db, owner_id)

        campaigns = [_serialize_campaign(row, exams_by_id) for row in campaign_rows]
        horizon_ms = now + 48 * 3600 * 1000

        # 1) Chiến dịch đang dở (chưa hoàn thành & chưa lưu trữ)
        active_campaigns: list[dict[str, Any]] = []
        urgent_deadlines: list[dict[str, Any]] = []
        for camp in campaigns:
            if camp["status"] == "archived":
                continue
            if camp["completedCount"] < camp["targetCount"]:
                msg = (
                    f"Đã xong {camp['completedCount']}/{camp['targetCount']} đề "
                    f"— Bấm soạn tiếp đề {camp['nextOrdinal']}"
                )
                active_campaigns.append(
                    {
                        "id": camp["id"],
                        "title": camp["title"],
                        "subject": camp["subject"],
                        "grade": camp["grade"],
                        "completedCount": camp["completedCount"],
                        "targetCount": camp["targetCount"],
                        "remainingCount": camp["remainingCount"],
                        "nextOrdinal": camp["nextOrdinal"],
                        "dueAt": camp["dueAt"],
                        "message": msg,
                    }
                )
                due_at = camp["dueAt"]
                if isinstance(due_at, int) and due_at <= horizon_ms:
                    overdue = due_at < now
                    hours_rem = round((due_at - now) / 3600_000, 1)
                    camp_done = camp["completedCount"]
                    camp_target = camp["targetCount"]
                    camp_title = camp["title"]
                    dl_msg = (
                        f'Chiến dịch "{camp_title}" đã quá hạn ({camp_done}/{camp_target} đề)'
                        if overdue
                        else (
                            f'Chiến dịch "{camp_title}" sắp đến hạn '
                            f"(còn {max(0.0, hours_rem):.0f} giờ)"
                        )
                    )
                    urgent_deadlines.append(
                        {
                            "id": camp["id"],
                            "source": "campaign",
                            "title": camp_title,
                            "kind": "campaign",
                            "targetType": "campaign",
                            "targetId": camp["id"],
                            "dueAt": due_at,
                            "overdue": overdue,
                            "hoursRemaining": hours_rem,
                            "message": dl_msg,
                        }
                    )

        # 2) Nhắc rà soát hôm sau cho đề có câu draft/chưa duyệt >= reviewThresholdHours giờ trước
        threshold_ms = int(round(reviewThresholdHours * 3600 * 1000))
        next_day_review_nudges: list[dict[str, Any]] = []
        for ex in active_exams:
            if ex.get("sample"):
                continue
            questions = ex.get("questions")
            if not isinstance(questions, list) or not questions:
                continue
            draft_count = sum(
                1
                for q in questions
                if isinstance(q, dict)
                and (q.get("approvalStatus") == "draft" or not _is_question_approved(q))
            )
            if draft_count == 0:
                continue
            updated_raw = ex.get("updated") or ex.get("updatedAt")
            if not isinstance(updated_raw, (int, float)) or updated_raw <= 0:
                continue
            updated_ms = int(updated_raw)
            if now - updated_ms >= threshold_ms:
                hours_ago = max(1, int((now - updated_ms) // 3600_000))
                title = str(ex.get("title") or "Đề chưa đặt tên")
                next_day_review_nudges.append(
                    {
                        "examId": ex["id"],
                        "title": title,
                        "subject": str(ex.get("subject") or ""),
                        "grade": str(ex.get("grade") or ""),
                        "draftQuestionCount": draft_count,
                        "totalQuestions": len(questions),
                        "updatedAt": updated_ms,
                        "hoursSinceUpdate": hours_ago,
                        "message": (
                            f'Đề "{title}" còn {draft_count}/{len(questions)} câu chưa duyệt '
                            f"(cập nhật {hours_ago} giờ trước) — Nhắc rà soát kiểm đáp án."
                        ),
                    }
                )

        # 3) Nhắc lịch giáo viên sắp đến hạn trong 48h hoặc quá hạn (chưa done & chưa snooze)
        for row in reminder_rows:
            rem = _serialize_reminder(row)
            snoozed_until = rem["snoozedUntil"]
            if isinstance(snoozed_until, int) and snoozed_until > now:
                continue
            remind_at = rem["remindAt"]
            if remind_at is not None and remind_at > horizon_ms:
                continue
            overdue = isinstance(remind_at, int) and remind_at < now
            hours_rem = (
                round((remind_at - now) / 3600_000, 1) if isinstance(remind_at, int) else 0.0
            )
            urgent_deadlines.append(
                {
                    "id": rem["id"],
                    "source": "reminder",
                    "title": rem["title"],
                    "kind": rem["kind"],
                    "targetType": rem["targetType"],
                    "targetId": rem["targetId"],
                    "dueAt": remind_at,
                    "overdue": overdue,
                    "hoursRemaining": hours_rem,
                    "message": (
                        f"Quá hạn: {rem['title']}" if overdue else f"Sắp đến hạn: {rem['title']}"
                    ),
                }
            )

        urgent_deadlines.sort(key=lambda d: (0 if d["overdue"] else 1, d["dueAt"] or 0))
        badge_count = (
            len(active_campaigns)
            + len(next_day_review_nudges)
            + len(urgent_deadlines)
            + (1 if pending_grading["count"] > 0 else 0)
        )
        return {
            "badgeCount": badge_count,
            "greeting": _greeting_for_ms(now),
            "activeCampaigns": active_campaigns,
            "nextDayReviewNudges": next_day_review_nudges,
            "urgentDeadlines": urgent_deadlines,
            "pendingRoomGrading": pending_grading,
        }
