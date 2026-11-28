"""Phòng thi trực tuyến và bài tập trên SQLite: tạo phòng, trộn đề, chấm điểm, xuất Excel/QR."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import inspect
import io
import ipaddress
import json
import math
import re
import secrets
import socket
import sqlite3
import time
import unicodedata
import zipfile
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mach_backend.ai_contract import AIError
from mach_backend.ai_questions import saved_answer
from mach_backend.exam_spec_export import redact_exam_for_student
from mach_backend.export_preflight import audit_export_preflight
from mach_backend.local_documents import _plan_variant_units, exam_variant, shuffle_variant_question
from mach_backend.tnmaker_export import _build_qr_matrix, _col_ref
from mach_backend.word_export import uses_table

type ConnectCallable = Callable[[], AbstractContextManager[sqlite3.Connection]]
type OwnerResolver = Callable[[Request], str]
type ReadExamCallable = Callable[[Request, str], Any]
type ReadFileBytesCallable = Callable[..., Any]

ROOT = Path(__file__).resolve().parents[3]
# Bảng chữ cái 31 ký tự rõ ràng, loại hoàn toàn 0/O/1/I/L để học sinh nhập không nhầm.
ROOM_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
ROOM_CODE_LEN = 6
ROOM_CODE_RE = re.compile(r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$")
PUBLIC_ROOM_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
SAFE_KATEX_SUBPATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
MAX_SNAPSHOT_BYTES = 25 * 1024 * 1024
MAX_ESSAY_CHARS = 50_000
MAX_SHORT_CHARS = 1_000

TF_RATIO_PCT: dict[int, int] = {0: 0, 1: 10, 2: 25, 3: 50, 4: 100}
VALID_ROOM_STATUSES = ("draft", "open", "closed", "archived")
VALID_MODES = ("exam", "homework")
VALID_RESULT_POLICIES = ("hidden", "score_only", "score_and_answers", "full_explanation")
VALID_EVENT_TYPES = (
    "tab_hidden",
    "window_blur",
    "fullscreen_exit",
    "copy_attempt",
    "auto_lock",
    "submit",
    "reconnect",
)

_STATIC_PUBLIC_ASSETS = frozenset(
    {
        "/assets/exam-room.css",
        "/assets/exam-room.js",
        "/assets/exam-room.html",
        "/assets/exam-icon.svg",
    }
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exam_rooms (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    exam_id TEXT NOT NULL,
    exam_revision INTEGER NOT NULL DEFAULT 1,
    room_code TEXT UNIQUE NOT NULL,
    pin_hash TEXT NOT NULL DEFAULT '',
    pin_salt TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'exam' CHECK (mode IN ('exam', 'homework')),
    title TEXT NOT NULL,
    class_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('draft', 'open', 'closed', 'archived')),
    allow_lan INTEGER NOT NULL DEFAULT 0,
    duration_minutes INTEGER NOT NULL DEFAULT 45,
    opens_at INTEGER,
    deadline_at INTEGER,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    shuffle_questions INTEGER NOT NULL DEFAULT 0,
    shuffle_options INTEGER NOT NULL DEFAULT 0,
    variant_config_json TEXT NOT NULL DEFAULT '{}',
    result_policy TEXT NOT NULL DEFAULT 'score_only'
        CHECK (result_policy IN ('hidden', 'score_only', 'score_and_answers', 'full_explanation')),
    release_results_after_close INTEGER NOT NULL DEFAULT 0,
    require_fullscreen INTEGER NOT NULL DEFAULT 0,
    max_tab_switches INTEGER NOT NULL DEFAULT 0,
    teacher_snapshot_json TEXT NOT NULL,
    total_points_p100 INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exam_rooms_owner_created
    ON exam_rooms (owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS room_attempts (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    student_name TEXT NOT NULL,
    student_code TEXT NOT NULL DEFAULT '',
    student_class TEXT NOT NULL DEFAULT '',
    attempt_no INTEGER NOT NULL DEFAULT 1,
    variant_offset INTEGER NOT NULL DEFAULT 0,
    variant_code TEXT NOT NULL DEFAULT '101',
    delivery_map_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'submitted', 'auto_submitted', 'locked')),
    started_at INTEGER NOT NULL,
    expires_at INTEGER,
    submitted_at INTEGER,
    auto_score_p100 INTEGER NOT NULL DEFAULT 0,
    manual_score_p100 INTEGER NOT NULL DEFAULT 0,
    score_adjustment_p100 INTEGER NOT NULL DEFAULT 0,
    adjustment_note TEXT NOT NULL DEFAULT '',
    total_score_p100 INTEGER NOT NULL DEFAULT 0,
    grading_status TEXT NOT NULL DEFAULT 'auto_graded'
        CHECK (grading_status IN ('auto_graded', 'needs_manual', 'graded')),
    tab_switch_count INTEGER NOT NULL DEFAULT 0,
    fullscreen_exit_count INTEGER NOT NULL DEFAULT 0,
    last_heartbeat_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_room_attempts_room
    ON room_attempts (room_id, started_at DESC);

CREATE TABLE IF NOT EXISTS attempt_answers (
    attempt_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'truefalse', 'short', 'essay')),
    max_points_p100 INTEGER NOT NULL DEFAULT 0,
    response_json TEXT NOT NULL DEFAULT 'null',
    is_auto_graded INTEGER NOT NULL DEFAULT 0,
    earned_points_p100 INTEGER,
    grader_note TEXT NOT NULL DEFAULT '',
    graded_by TEXT NOT NULL DEFAULT '',
    graded_at INTEGER,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (attempt_id, question_id)
);

CREATE TABLE IF NOT EXISTS attempt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'tab_hidden',
            'window_blur',
            'fullscreen_exit',
            'copy_attempt',
            'auto_lock',
            'submit',
            'reconnect'
        )
    ),
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempt_events_attempt
    ON attempt_events (attempt_id, created_at DESC);

CREATE TABLE IF NOT EXISTS attempt_audio_plays (
    attempt_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    play_count INTEGER NOT NULL DEFAULT 0,
    max_plays INTEGER NOT NULL DEFAULT 2,
    last_played_at INTEGER NOT NULL,
    active_lease_id TEXT NOT NULL DEFAULT '',
    active_lease_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (attempt_id, file_id)
);
"""


def is_public_room_path(path: str) -> bool:
    """Kiểm tra đường dẫn có thuộc cổng học sinh công khai (không cần đăng nhập GV) hay không."""
    if not isinstance(path, str) or not path:
        return False
    if "%" in path or "\\" in path or "\x00" in path or "//" in path or ".." in path.split("/"):
        return False
    if path == "/phong-thi":
        return True
    if path.startswith("/phong-thi/"):
        code = path.removeprefix("/phong-thi/")
        return "/" not in code and PUBLIC_ROOM_CODE_RE.fullmatch(code) is not None
    if path.startswith("/api/rooms/public/"):
        tail = path.removeprefix("/api/rooms/public/")
        return bool(tail) and SAFE_KATEX_SUBPATH_RE.fullmatch(tail) is not None
    if path in _STATIC_PUBLIC_ASSETS:
        return True
    if path.startswith("/assets/katex/"):
        sub = path.removeprefix("/assets/katex/")
        return bool(sub) and SAFE_KATEX_SUBPATH_RE.fullmatch(sub) is not None
    return False


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(_SCHEMA_SQL)
    attempt_cols = {
        str(row[1]) for row in db.execute("PRAGMA table_info(room_attempts)").fetchall()
    }
    if "score_adjustment_p100" not in attempt_cols:
        db.execute(
            "ALTER TABLE room_attempts ADD COLUMN score_adjustment_p100 INTEGER NOT NULL DEFAULT 0"
        )
    if "adjustment_note" not in attempt_cols:
        db.execute("ALTER TABLE room_attempts ADD COLUMN adjustment_note TEXT NOT NULL DEFAULT ''")
    audio_cols = {
        str(row[1]) for row in db.execute("PRAGMA table_info(attempt_audio_plays)").fetchall()
    }
    if "active_lease_id" not in audio_cols:
        db.execute(
            "ALTER TABLE attempt_audio_plays ADD COLUMN active_lease_id TEXT NOT NULL DEFAULT ''"
        )
    if "active_lease_at" not in audio_cols:
        db.execute(
            "ALTER TABLE attempt_audio_plays ADD COLUMN active_lease_at INTEGER NOT NULL DEFAULT 0"
        )


def _begin_immediate(db: sqlite3.Connection) -> None:
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")


def _now_ms(clock: Callable[[], float]) -> int:
    return int(clock() * 1000)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_pin(pin: str) -> tuple[str, str]:
    clean = pin.strip()
    if not clean:
        return "", ""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(clean.encode("utf-8"), salt=salt, n=4096, r=8, p=1, dklen=32)
    return digest.hex(), salt.hex()


def _verify_pin(pin: str, stored_hash: str, stored_salt: str) -> bool:
    if not stored_hash or not stored_salt:
        return True
    try:
        salt = bytes.fromhex(stored_salt)
        expected = bytes.fromhex(stored_hash)
    except ValueError:
        return False
    given = hashlib.scrypt(pin.strip().encode("utf-8"), salt=salt, n=4096, r=8, p=1, dklen=32)
    return hmac.compare_digest(given, expected)


def _generate_room_code() -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LEN))


def _parse_epoch_ms(value: int | float | str | None, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise HTTPException(422, f"Trường {field_name} không hợp lệ.")
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value < 0:
            raise HTTPException(422, f"Trường {field_name} phải là thời điểm hợp lệ.")
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)
        try:
            iso = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            dt = datetime.fromisoformat(iso)
            return int(dt.timestamp() * 1000)
        except ValueError:
            raise HTTPException(
                422, f"Trường {field_name} không đúng định dạng thời gian."
            ) from None
    raise HTTPException(422, f"Trường {field_name} không hợp lệ.")


def _to_p100(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        dec = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not dec.is_finite() or dec < Decimal("0"):
        return None
    return int((dec * Decimal("100")).to_integral_value())


def _to_signed_p100(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        clean = (
            unicodedata.normalize("NFC", str(value))
            .strip()
            .replace("\u2212", "-")
            .replace(",", ".")
        )
        dec = Decimal(clean)
    except (InvalidOperation, ValueError):
        return None
    if not dec.is_finite():
        return None
    return int((dec * Decimal("100")).to_integral_value())


def _apply_score_adjustment(
    base_total_p100: int, adjustment_p100: int, total_points_p100: int
) -> int:
    raw = int(base_total_p100) + int(adjustment_p100)
    if total_points_p100 > 0:
        return max(0, min(int(total_points_p100), raw))
    return max(0, raw)


def _question_points_p100(question: dict[str, Any]) -> int:
    if question.get("points") is not None:
        parsed = _to_p100(question["points"])
        if parsed is not None:
            return parsed
    if question.get("pointsQ4") is not None:
        raw_q4 = question["pointsQ4"]
        if not isinstance(raw_q4, bool) and isinstance(raw_q4, (int, float)) and raw_q4 >= 0:
            return round(float(raw_q4) * 25)
    rubric = question.get("rubric")
    if isinstance(rubric, list) and rubric:
        total = 0
        has_any = False
        for step in rubric:
            if not isinstance(step, dict):
                continue
            if step.get("points") is not None:
                p = _to_p100(step["points"])
                if p is not None:
                    total += p
                    has_any = True
            elif step.get("pointsQ4") is not None:
                raw_sq4 = step["pointsQ4"]
                if (
                    not isinstance(raw_sq4, bool)
                    and isinstance(raw_sq4, (int, float))
                    and raw_sq4 >= 0
                ):
                    total += round(float(raw_sq4) * 25)
                    has_any = True
        if has_any:
            return total
    return 100


def _normalize_qtype(raw_type: Any) -> Literal["mcq", "truefalse", "short", "essay"]:
    val = str(raw_type or "mcq").strip().lower()
    mapping: dict[str, Literal["mcq", "truefalse", "short", "essay"]] = {
        "mcq": "mcq",
        "multiple_choice": "mcq",
        "truefalse": "truefalse",
        "true_false": "truefalse",
        "short": "short",
        "short_answer": "short",
        "essay": "essay",
    }
    return mapping.get(val, "mcq")


def _normalize_audio_entry(audio: Any) -> dict[str, Any] | None:
    if not isinstance(audio, dict):
        return None
    copy_audio = deepcopy(audio)
    file_id = str(copy_audio.get("fileId") or copy_audio.get("id") or "").strip()
    if not file_id:
        file_id = f"aud-{uuid4().hex[:12]}"
    copy_audio["fileId"] = file_id
    raw_max = copy_audio.get("maxPlays")
    max_plays = int(raw_max) if isinstance(raw_max, int) and not isinstance(raw_max, bool) else 2
    copy_audio["maxPlays"] = max(1, min(20, max_plays))
    return copy_audio


def _question_choice_group(question: dict[str, Any]) -> str:
    return str(question.get("choiceGroup") or question.get("track") or "").strip()


def _extract_choice_groups(exam_snapshot: dict[str, Any]) -> list[str]:
    groups: list[str] = []
    seen: set[str] = set()
    for q in exam_snapshot.get("questions") or []:
        if not isinstance(q, dict):
            continue
        grp = _question_choice_group(q)
        if grp and grp not in seen:
            seen.add(grp)
            groups.append(grp)
    return groups


def _snapshot_exam_for_room(exam: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if not isinstance(exam, dict):
        raise HTTPException(422, "Dữ liệu đề thi không hợp lệ.")
    raw_questions = exam.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise HTTPException(422, "Đề thi chưa có câu hỏi để mở phòng thi.")

    snap = deepcopy(exam)
    for transient in ("undo", "redo", "history", "chat", "aiConfig", "apiKey", "secret", "token"):
        snap.pop(transient, None)

    questions: list[dict[str, Any]] = []
    common_p100 = 0
    track_totals_p100: dict[str, int] = {}
    for idx, raw_q in enumerate(raw_questions, 1):
        if not isinstance(raw_q, dict):
            raise HTTPException(422, f"Câu {idx} không hợp lệ.")
        q = deepcopy(raw_q)
        q["id"] = str(q.get("id") or f"q-{idx}").strip() or f"q-{idx}"
        q["type"] = _normalize_qtype(q.get("type"))
        if isinstance(q.get("audio"), dict):
            q["audio"] = _normalize_audio_entry(q["audio"])
        p100 = _question_points_p100(q)
        q["_maxPointsP100"] = p100
        grp = _question_choice_group(q)
        if grp:
            q["choiceGroup"] = grp
            track_totals_p100[grp] = track_totals_p100.get(grp, 0) + p100
        else:
            common_p100 += p100
        questions.append(q)
    snap["questions"] = questions
    total_p100 = common_p100 + (max(track_totals_p100.values()) if track_totals_p100 else 0)

    if isinstance(snap.get("audio"), dict):
        snap["audio"] = _normalize_audio_entry(snap["audio"])

    raw_passages = snap.get("passages")
    if isinstance(raw_passages, list):
        for p in raw_passages:
            if isinstance(p, dict) and isinstance(p.get("audio"), dict):
                p["audio"] = _normalize_audio_entry(p["audio"])
    elif isinstance(raw_passages, dict):
        for p in raw_passages.values():
            if isinstance(p, dict) and isinstance(p.get("audio"), dict):
                p["audio"] = _normalize_audio_entry(p["audio"])

    encoded = json.dumps(snap, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(413, "Kích thước đề thi vượt giới hạn tạo phòng.")
    return snap, total_p100


def _collect_audio_entries(exam_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if isinstance(exam_snapshot.get("audio"), dict):
        aud = exam_snapshot["audio"]
        fid = str(aud.get("fileId") or "").strip()
        if fid:
            found[fid] = aud
    for q in exam_snapshot.get("questions") or []:
        if isinstance(q, dict) and isinstance(q.get("audio"), dict):
            aud = q["audio"]
            fid = str(aud.get("fileId") or "").strip()
            if fid:
                found[fid] = aud
    raw_passages = exam_snapshot.get("passages")
    passage_items = (
        raw_passages
        if isinstance(raw_passages, list)
        else list(raw_passages.values())
        if isinstance(raw_passages, dict)
        else []
    )
    for p in passage_items:
        if isinstance(p, dict) and isinstance(p.get("audio"), dict):
            aud = p["audio"]
            fid = str(aud.get("fileId") or "").strip()
            if fid:
                found[fid] = aud
    return found


def _build_student_delivery(
    exam_snapshot: dict[str, Any],
    *,
    shuffle_questions: bool,
    shuffle_options: bool,
    variant_offset: int,
    variant_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Tạo đề biến thể an toàn cho 1 lượt làm bài, giữ delivery_map và xóa sạch đáp án."""
    questions = exam_snapshot["questions"]
    orig_by_id = {q["id"]: q for q in questions}
    variant_exam = deepcopy(exam_snapshot)
    variant_code = str(101 + variant_offset)

    explicit_sections = variant_config.get("sections") if isinstance(variant_config, dict) else None
    explicit_ids = variant_config.get("questionIds") if isinstance(variant_config, dict) else None

    if shuffle_questions and isinstance(explicit_sections, list) and explicit_sections:
        try:
            variant_exam = exam_variant(
                variant_exam,
                {"sections": explicit_sections, "offset": variant_offset},
            )
        except AIError:
            pass
    elif shuffle_questions and isinstance(explicit_ids, list) and len(explicit_ids) >= 2:
        try:
            plan = _plan_variant_units(questions, explicit_ids)
            max_v = max(1, min(6, len(plan["units"])))
            variant_exam = exam_variant(
                variant_exam,
                {
                    "questionIds": explicit_ids,
                    "shuffleOptions": shuffle_options,
                    "offset": variant_offset % max_v,
                },
            )
        except AIError:
            pass
    elif shuffle_questions:
        # Gom các nhóm câu liên tiếp đồng nhất (loại câu, bảng dữ kiện, sectionId) để trộn hợp lệ.
        sections: list[dict[str, Any]] = []
        current_sig: tuple[Any, ...] | None = None
        current_ids: list[str] = []
        for q in questions:
            sig = (
                _normalize_qtype(q.get("type")),
                uses_table(q),
                q.get("sectionId"),
                _question_choice_group(q),
            )
            if sig != current_sig:
                if len(current_ids) >= 2:
                    sections.append({"questionIds": current_ids, "shuffleOptions": shuffle_options})
                current_sig = sig
                current_ids = [q["id"]]
            else:
                current_ids.append(q["id"])
        if len(current_ids) >= 2:
            sections.append({"questionIds": current_ids, "shuffleOptions": shuffle_options})

        if sections:
            for sec in sections:
                sec_ids = sec["questionIds"]
                try:
                    plan = _plan_variant_units(variant_exam["questions"], sec_ids)
                    max_v = max(1, min(6, len(plan["units"])))
                    variant_exam = exam_variant(
                        variant_exam,
                        {
                            "questionIds": sec_ids,
                            "shuffleOptions": shuffle_options,
                            "offset": variant_offset % max_v,
                        },
                    )
                except AIError:
                    if shuffle_options:
                        variant_exam["questions"] = [
                            shuffle_variant_question(q, variant_offset)
                            if q["id"] in set(sec_ids)
                            else q
                            for q in variant_exam["questions"]
                        ]
            variant_exam["title"] = (
                f"{exam_snapshot.get('title') or 'Đề kiểm tra'} · Mã đề {variant_code}"
            )
        elif shuffle_options:
            variant_exam["questions"] = [
                shuffle_variant_question(q, variant_offset) for q in variant_exam["questions"]
            ]
    elif shuffle_options:
        variant_exam["questions"] = [
            shuffle_variant_question(q, variant_offset) for q in variant_exam["questions"]
        ]

    # Xử lý thêm trường hợp chỉ shuffle_questions=True nhưng 1 nhóm có câu không nằm trong sections.
    if shuffle_options and shuffle_questions:
        # Đảm bảo câu MCQ đơn lẻ (nhóm 1 câu) cũng được trộn phương án nếu chưa trộn.
        updated_qs: list[dict[str, Any]] = []
        for q in variant_exam["questions"]:
            orig_q = orig_by_id.get(q["id"], q)
            if (
                _normalize_qtype(q.get("type")) == "mcq"
                and q.get("options") == orig_q.get("options")
                and isinstance(q.get("options"), list)
                and len(q["options"]) == 4
            ):
                updated_qs.append(shuffle_variant_question(q, variant_offset))
            else:
                updated_qs.append(q)
        variant_exam["questions"] = updated_qs

    question_order: list[str] = []
    option_order: dict[str, list[int]] = {}
    for q in variant_exam["questions"]:
        qid = str(q["id"])
        question_order.append(qid)
        orig_q = orig_by_id.get(qid, q)
        if _normalize_qtype(q.get("type")) == "mcq":
            orig_opts = orig_q.get("options") or []
            var_opts = q.get("options") or []
            if (
                isinstance(orig_opts, list)
                and isinstance(var_opts, list)
                and len(orig_opts) == len(var_opts)
                and len(set(orig_opts)) == len(orig_opts)
                and set(orig_opts) == set(var_opts)
            ):
                option_order[qid] = [orig_opts.index(opt) for opt in var_opts]
            else:
                option_order[qid] = list(range(len(var_opts)))

    delivery_map = {"questionOrder": question_order, "optionOrder": option_order}
    redacted = redact_exam_for_student(variant_exam)
    _scrub_student_exam(redacted)
    return redacted, delivery_map, variant_code


def _scrub_audio_dict(audio: Any) -> dict[str, Any] | None:
    if not isinstance(audio, dict):
        return None
    cleaned = deepcopy(audio)
    cleaned.pop("dataUri", None)
    cleaned.pop("dataUrl", None)
    cleaned.pop("src", None)
    return cleaned


def _scrub_student_exam(exam: dict[str, Any]) -> None:
    """Xóa mọi trường nội bộ của giáo viên hoặc dữ liệu âm thanh thô khỏi bản gửi học sinh."""
    for extra_key in (
        "docs",
        "appliedPrefs",
        "matrix",
        "matrixConfirmed",
        "undo",
        "redo",
        "aiPlan",
        "activeAIJob",
        "aiClarification",
        "aiPendingPatch",
        "markingGuidance",
    ):
        exam.pop(extra_key, None)

    for q in exam.get("questions") or []:
        if not isinstance(q, dict):
            continue
        if uses_table(q):
            q["dataLinked"] = True
        for secret_q_key in ("source", "rule", "algebra", "verification", "generated"):
            q.pop(secret_q_key, None)
        p100 = q.pop("_maxPointsP100", None)
        if p100 is not None and "points" not in q and "pointsQ4" not in q:
            q["points"] = round(p100 / 100.0, 2)
        if isinstance(q.get("audio"), dict):
            q["audio"] = _scrub_audio_dict(q["audio"])

    if isinstance(exam.get("audio"), dict):
        exam["audio"] = _scrub_audio_dict(exam["audio"])

    raw_passages = exam.get("passages")
    if isinstance(raw_passages, list):
        for p in raw_passages:
            if isinstance(p, dict) and isinstance(p.get("audio"), dict):
                p["audio"] = _scrub_audio_dict(p["audio"])
    elif isinstance(raw_passages, dict):
        for p in raw_passages.values():
            if isinstance(p, dict) and isinstance(p.get("audio"), dict):
                p["audio"] = _scrub_audio_dict(p["audio"])


def _attach_audio_play_counts(
    exam: dict[str, Any],
    play_map: Mapping[str, tuple[int, int] | tuple[int, int, str]],
    attempt_id: str,
) -> dict[str, dict[str, Any]]:
    audio_summary: dict[str, dict[str, Any]] = {}

    def enrich(aud: Any) -> None:
        if not isinstance(aud, dict):
            return
        fid = str(aud.get("fileId") or "").strip()
        if not fid:
            return
        default_max = int(aud.get("maxPlays") or 2)
        entry = play_map.get(fid)
        if entry is None:
            used, max_p, lease_id = 0, default_max, ""
        elif len(entry) >= 3:
            used, max_p, lease_id = int(entry[0]), int(entry[1]), str(entry[2] or "")
        else:
            used, max_p, lease_id = int(entry[0]), int(entry[1]), ""
        rem = max(0, max_p - used)
        aud["playsUsed"] = used
        aud["playsRemaining"] = rem
        aud["maxPlays"] = max_p
        aud["pendingLeaseId"] = lease_id
        aud["url"] = f"/api/rooms/public/attempts/{attempt_id}/audio/{fid}"
        audio_summary[fid] = {
            "playsUsed": used,
            "playsRemaining": rem,
            "maxPlays": max_p,
            "pendingLeaseId": lease_id,
        }

    for q in exam.get("questions") or []:
        if isinstance(q, dict):
            enrich(q.get("audio"))
    enrich(exam.get("audio"))

    raw_passages = exam.get("passages")
    passage_items = (
        raw_passages
        if isinstance(raw_passages, list)
        else list(raw_passages.values())
        if isinstance(raw_passages, dict)
        else []
    )
    for p in passage_items:
        if isinstance(p, dict):
            enrich(p.get("audio"))
    return audio_summary


def _parse_mcq_answer(question: dict[str, Any]) -> int | None:
    if question.get("answerKnown") is False:
        return None
    ans = question.get("answer")
    if isinstance(ans, int) and not isinstance(ans, bool) and 0 <= ans < 26:
        return ans
    if isinstance(ans, str):
        clean = ans.strip().upper()
        if len(clean) == 1 and "A" <= clean <= "Z":
            return ord(clean) - 65
    return None


def _parse_truefalse_key(question: dict[str, Any]) -> tuple[bool, bool, bool, bool] | None:
    if question.get("answerKnown") is False:
        return None
    raw = question.get("truthValues")
    if raw is None:
        raw = question.get("answer")
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        out: list[bool] = []
        for item in raw:
            if type(item) is bool:
                out.append(item)
            elif isinstance(item, str) and item.strip().casefold() in {"đ", "đúng", "true", "t"}:
                out.append(True)
            elif isinstance(item, str) and item.strip().casefold() in {"s", "sai", "false", "f"}:
                out.append(False)
            else:
                return None
        return (out[0], out[1], out[2], out[3])
    return None


_SHORT_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_MAX_SHORT_NUMERIC_LEN = 32


def _normalize_short_raw(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().replace("\u2212", "-")


def _parse_short_decimal(text: str) -> Fraction | None:
    normalized = _normalize_short_raw(text)
    if not normalized or len(normalized) > _MAX_SHORT_NUMERIC_LEN:
        return None
    compact = re.sub(r"\s*/\s*", "/", normalized)
    compact = re.sub(r"^([+-])\s+", r"\1", compact)
    compact = re.sub(r"/\s*([+-])\s*", r"/\1", compact)
    compact = compact.replace(",", ".")
    if not compact or any(ch.isspace() for ch in compact) or len(compact) > _MAX_SHORT_NUMERIC_LEN:
        return None

    if "/" in compact:
        parts = compact.split("/")
        if len(parts) != 2:
            return None
        num_str, den_str = parts
        if not _SHORT_DECIMAL_RE.fullmatch(num_str) or not _SHORT_DECIMAL_RE.fullmatch(den_str):
            return None
        try:
            den = Fraction(den_str)
            if den == 0:
                return None
            return Fraction(num_str) / den
        except (ValueError, ZeroDivisionError):
            return None

    if not _SHORT_DECIMAL_RE.fullmatch(compact):
        return None
    try:
        return Fraction(compact)
    except ValueError:
        return None


def _short_matches(student_raw: Any, key_raw: Any) -> bool:
    if not isinstance(student_raw, str):
        if isinstance(student_raw, (int, float)) and not isinstance(student_raw, bool):
            student_str = str(student_raw)
        else:
            return False
    else:
        student_str = student_raw
    s_norm = _normalize_short_raw(student_str)
    if not s_norm:
        return False

    if isinstance(key_raw, (int, float)) and not isinstance(key_raw, bool):
        key_str = str(key_raw)
    elif isinstance(key_raw, str):
        key_str = key_raw
    else:
        return False

    candidates = [part.strip() for part in re.split(r"[;|]", key_str) if part.strip()]
    if not candidates:
        return False

    s_num = _parse_short_decimal(s_norm)
    s_text = " ".join(s_norm.split()).casefold()

    for cand in candidates:
        k_norm = _normalize_short_raw(cand)
        k_num = _parse_short_decimal(k_norm)
        if s_num is not None and k_num is not None:
            if s_num == k_num:
                return True
        elif s_text == " ".join(k_norm.split()).casefold():
            return True
    return False


def grade_question_response(
    orig_question: dict[str, Any],
    student_response: Any,
    max_points_p100: int,
    option_order: list[int] | None = None,
) -> tuple[int, int | None]:
    """Chấm điểm nguyên p100 cho từng câu; trả về (is_auto_graded, earned_points_p100)."""
    qtype = _normalize_qtype(orig_question.get("type"))
    if qtype == "essay":
        return 0, None

    if qtype == "mcq":
        if isinstance(student_response, dict):
            student_response = student_response.get("answer", student_response.get("choice"))
        choice_idx: int | None = None
        if isinstance(student_response, int) and not isinstance(student_response, bool):
            choice_idx = student_response
        elif isinstance(student_response, str):
            clean = student_response.strip().upper()
            if len(clean) == 1 and "A" <= clean <= "Z":
                choice_idx = ord(clean) - 65
        if choice_idx is None or choice_idx < 0:
            return 1, 0
        if option_order:
            if choice_idx >= len(option_order):
                return 1, 0
            orig_choice = option_order[choice_idx]
        else:
            orig_choice = choice_idx
        key_idx = _parse_mcq_answer(orig_question)
        earned = max_points_p100 if (key_idx is not None and orig_choice == key_idx) else 0
        return 1, earned

    if qtype == "truefalse":
        key_tf = _parse_truefalse_key(orig_question)
        if key_tf is None:
            return 1, 0
        if isinstance(student_response, dict):
            student_response = student_response.get("truthValues", student_response.get("answer"))
        if not isinstance(student_response, list) or len(student_response) != 4:
            return 1, 0
        matches = 0
        for idx, truth in enumerate(key_tf):
            val = student_response[idx]
            if type(val) is bool and val == truth:
                matches += 1
        pct = TF_RATIO_PCT.get(matches, 0)
        return 1, (max_points_p100 * pct + 50) // 100

    # short
    if isinstance(student_response, dict):
        student_response = student_response.get("answerText", student_response.get("answer"))
    key_raw = orig_question.get("answerText")
    if key_raw is None or (isinstance(key_raw, str) and not key_raw.strip()):
        key_raw = orig_question.get("answer")
    if key_raw is None:
        key_raw = saved_answer(orig_question)
    return 1, (max_points_p100 if _short_matches(student_response, key_raw) else 0)


def _is_student_response_answered(qtype: str, response_val: Any) -> bool:
    if response_val is None:
        return False
    if qtype == "mcq":
        if isinstance(response_val, dict):
            response_val = response_val.get("answer", response_val.get("choice"))
        if isinstance(response_val, bool):
            return False
        if isinstance(response_val, int):
            return response_val >= 0
        return isinstance(response_val, str) and bool(response_val.strip())
    if qtype == "truefalse":
        if isinstance(response_val, dict):
            response_val = response_val.get("truthValues", response_val.get("answer"))
        return isinstance(response_val, list) and any(type(item) is bool for item in response_val)
    if isinstance(response_val, dict):
        response_val = response_val.get(
            "answerText", response_val.get("text", response_val.get("answer"))
        )
    if isinstance(response_val, (int, float)) and not isinstance(response_val, bool):
        return True
    return isinstance(response_val, str) and bool(response_val.strip())


def _summarize_attempt_scores(
    orig_questions: list[dict[str, Any]],
    answer_data_by_qid: dict[str, tuple[str, int, Any, int, int | None]],
) -> dict[str, Any]:
    """Tính điểm hiệu lực và trạng thái chấm bài, hỗ trợ đề có nhánh tự chọn (choiceGroup)."""
    groups: list[str] = []
    seen_groups: set[str] = set()
    for q in orig_questions:
        if not isinstance(q, dict):
            continue
        grp = _question_choice_group(q)
        if grp and grp not in seen_groups:
            seen_groups.add(grp)
            groups.append(grp)

    common_auto = 0
    common_manual = 0
    common_essays = 0
    common_ungraded_essays = 0
    track_stats: dict[str, dict[str, int]] = {
        g: {
            "auto": 0,
            "manual": 0,
            "maxP100": 0,
            "questionCount": 0,
            "answeredCount": 0,
            "essays": 0,
            "ungradedEssays": 0,
            "answeredUngradedEssays": 0,
        }
        for g in groups
    }

    for q in orig_questions:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or "")
        qtype = _normalize_qtype(q.get("type"))
        max_p100 = int(q.get("_maxPointsP100", _question_points_p100(q)))
        grp = _question_choice_group(q)
        row_data = answer_data_by_qid.get(qid)
        if row_data is not None:
            qtype = row_data[0] or qtype
            max_p100 = int(row_data[1])
            response_val = row_data[2]
            is_auto = int(row_data[3])
            earned = row_data[4]
        else:
            response_val = None
            is_auto = 0 if qtype == "essay" else 1
            earned = None

        answered = _is_student_response_answered(qtype, response_val)
        is_essay = qtype == "essay"
        earned_val = int(earned or 0)

        if not grp:
            if is_essay:
                common_essays += 1
                if earned is None:
                    common_ungraded_essays += 1
                else:
                    common_manual += earned_val
            elif is_auto:
                common_auto += earned_val
            else:
                common_manual += earned_val
        else:
            st = track_stats[grp]
            st["questionCount"] += 1
            st["maxP100"] += max_p100
            if answered:
                st["answeredCount"] += 1
            if is_essay:
                st["essays"] += 1
                if earned is None:
                    st["ungradedEssays"] += 1
                    if answered:
                        st["answeredUngradedEssays"] += 1
                else:
                    st["manual"] += earned_val
            elif is_auto:
                st["auto"] += earned_val
            else:
                st["manual"] += earned_val

    if not groups:
        auto_score = common_auto
        manual_score = common_manual
        total_score = auto_score + manual_score
        ungraded_essay_count = common_ungraded_essays
        has_any_essay = common_essays > 0
        chosen_track: str | None = None
        track_scores: dict[str, dict[str, int]] = {}
    else:
        track_scores = {
            g: {
                "scoreP100": st["auto"] + st["manual"],
                "autoScoreP100": st["auto"],
                "manualScoreP100": st["manual"],
                "maxPointsP100": st["maxP100"],
                "answeredCount": st["answeredCount"],
                "questionCount": st["questionCount"],
            }
            for g, st in track_stats.items()
        }
        attempted = [g for g in groups if track_stats[g]["answeredCount"] > 0]
        if len(attempted) == 1:
            chosen_track = attempted[0]
        elif len(attempted) > 1:
            chosen_track = max(
                attempted,
                key=lambda g: (
                    track_stats[g]["auto"] + track_stats[g]["manual"],
                    track_stats[g]["answeredCount"],
                    -groups.index(g),
                ),
            )
        else:
            chosen_track = None

        chosen_st = track_stats.get(chosen_track) if chosen_track else None
        auto_score = common_auto + (chosen_st["auto"] if chosen_st else 0)
        manual_score = common_manual + (chosen_st["manual"] if chosen_st else 0)
        total_score = auto_score + manual_score
        other_answered_ungraded = sum(
            track_stats[g]["answeredUngradedEssays"] for g in attempted if g != chosen_track
        )
        other_answered_essays = sum(
            1
            for q in orig_questions
            if isinstance(q, dict)
            and _normalize_qtype(q.get("type")) == "essay"
            and (g := _question_choice_group(q))
            and g != chosen_track
            and g in attempted
            and (
                (r_data := answer_data_by_qid.get(str(q.get("id") or ""))) is not None
                and (_is_student_response_answered("essay", r_data[2]) or r_data[4] is not None)
            )
        )
        ungraded_essay_count = (
            common_ungraded_essays
            + (chosen_st["ungradedEssays"] if chosen_st else 0)
            + other_answered_ungraded
        )
        has_any_essay = (
            common_essays > 0
            or (chosen_st["essays"] > 0 if chosen_st else False)
            or other_answered_essays > 0
        )

    if ungraded_essay_count > 0:
        grading_status = "needs_manual"
    elif has_any_essay:
        grading_status = "graded"
    else:
        grading_status = "auto_graded"

    return {
        "autoScoreP100": auto_score,
        "manualScoreP100": manual_score,
        "totalScoreP100": total_score,
        "gradingStatus": grading_status,
        "ungradedEssayCount": ungraded_essay_count,
        "isProvisionalScore": ungraded_essay_count > 0,
        "chosenTrack": chosen_track,
        "trackScores": track_scores,
        "trackStats": track_stats,
        "groups": groups,
    }


def _grade_attempt_tx(
    db: sqlite3.Connection,
    attempt_id: str,
    exam_snapshot: dict[str, Any],
    delivery_map: dict[str, Any],
    now_ms: int,
) -> tuple[int, int, int, str]:
    """Chấm toàn bộ phần tự động của một lượt thi trong giao dịch SQLite."""
    orig_questions = [q for q in (exam_snapshot.get("questions") or []) if isinstance(q, dict)]
    orig_by_id = {str(q["id"]): q for q in orig_questions}
    option_order_map = delivery_map.get("optionOrder") or {}

    existing_rows = db.execute(
        "SELECT question_id, question_type, max_points_p100, response_json, "
        "is_auto_graded, earned_points_p100 FROM attempt_answers WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchall()
    existing_by_qid = {row[0]: row for row in existing_rows}

    answer_data_by_qid: dict[str, tuple[str, int, Any, int, int | None]] = {}

    for qid, orig_q in orig_by_id.items():
        qtype = _normalize_qtype(orig_q.get("type"))
        max_p100 = int(orig_q.get("_maxPointsP100", _question_points_p100(orig_q)))
        row = existing_by_qid.get(qid)
        if row is not None:
            response_val = json.loads(row[3])
            existing_earned = row[5]
        else:
            response_val = None
            existing_earned = None

        if qtype == "essay":
            if row is None:
                db.execute(
                    """
                    INSERT INTO attempt_answers (
                        attempt_id, question_id, question_type, max_points_p100,
                        response_json, is_auto_graded, earned_points_p100,
                        grader_note, graded_by, graded_at, updated_at
                    ) VALUES (?, ?, 'essay', ?, 'null', 0, NULL, '', '', NULL, ?)
                    """,
                    (attempt_id, qid, max_p100, now_ms),
                )
            answer_data_by_qid[qid] = (qtype, max_p100, response_val, 0, existing_earned)
            continue

        is_auto, earned = grade_question_response(
            orig_q, response_val, max_p100, option_order_map.get(qid)
        )
        answer_data_by_qid[qid] = (qtype, max_p100, response_val, is_auto, earned)
        if row is None:
            db.execute(
                """
                INSERT INTO attempt_answers (
                    attempt_id, question_id, question_type, max_points_p100,
                    response_json, is_auto_graded, earned_points_p100,
                    grader_note, graded_by, graded_at, updated_at
                ) VALUES (?, ?, ?, ?, 'null', ?, ?, '', '', ?, ?)
                """,
                (attempt_id, qid, qtype, max_p100, is_auto, earned, now_ms, now_ms),
            )
        else:
            db.execute(
                """
                UPDATE attempt_answers
                SET is_auto_graded = ?, earned_points_p100 = ?, graded_at = ?, updated_at = ?
                WHERE attempt_id = ? AND question_id = ?
                """,
                (is_auto, earned, now_ms, now_ms, attempt_id, qid),
            )

    summary = _summarize_attempt_scores(orig_questions, answer_data_by_qid)
    return (
        summary["autoScoreP100"],
        summary["manualScoreP100"],
        summary["totalScoreP100"],
        summary["gradingStatus"],
    )


def _validate_student_answer_value(qtype: str, value: Any, option_count: int) -> Any:
    if value is None:
        return None
    if qtype == "mcq":
        if isinstance(value, str):
            clean = value.strip().upper()
            if len(clean) == 1 and "A" <= clean <= "Z":
                value = ord(clean) - 65
            else:
                raise HTTPException(422, "Đáp án trắc nghiệm phải là chỉ số phương án hợp lệ.")
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < max(4, option_count)
        ):
            raise HTTPException(422, "Lựa chọn trắc nghiệm không hợp lệ.")
        return value
    if qtype == "truefalse":
        if not isinstance(value, list) or len(value) != 4:
            raise HTTPException(422, "Câu Đúng/Sai phải là danh sách 4 nhận định.")
        cleaned: list[bool | None] = []
        for item in value:
            if item is None or type(item) is bool:
                cleaned.append(item)
            else:
                raise HTTPException(
                    422,
                    "Giá trị nhận định Đúng/Sai phải là true, false hoặc null.",
                )
        return cleaned
    if qtype == "short":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise HTTPException(422, "Câu trả lời ngắn phải là văn bản.")
        if len(value) > MAX_SHORT_CHARS:
            raise HTTPException(422, f"Đáp án trả lời ngắn tối đa {MAX_SHORT_CHARS} ký tự.")
        return value
    if qtype == "essay":
        if not isinstance(value, str):
            raise HTTPException(422, "Bài làm tự luận phải là văn bản.")
        if len(value) > MAX_ESSAY_CHARS:
            raise HTTPException(422, f"Bài làm tự luận tối đa {MAX_ESSAY_CHARS} ký tự.")
        return value
    return value


def _guess_audio_mime(data: bytes, filename: str = "") -> str:
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"fLaC"):
        return "audio/flac"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "audio/mp4"
    ext = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".webm": "audio/webm",
        ".flac": "audio/flac",
    }.get(ext, "audio/mpeg")


def _decode_data_uri(data_uri: str, filename: str = "") -> tuple[bytes, str] | None:
    if not isinstance(data_uri, str) or not data_uri.startswith("data:"):
        return None
    try:
        header, encoded = data_uri.split(",", 1)
    except ValueError:
        return None
    if not header.endswith(";base64"):
        return None
    mime = header[5:-7].strip() or "audio/mpeg"
    if not re.fullmatch(r"[A-Za-z0-9.+_-]+/[A-Za-z0-9.+_-]+", mime):
        mime = "audio/mpeg"
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None
    return raw, mime or _guess_audio_mime(raw, filename)


def _call_read_file_bytes(callback: ReadFileBytesCallable, file_id: str, owner_id: str) -> Any:
    try:
        sig = inspect.signature(callback)
        params = [
            p
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
    except (TypeError, ValueError):
        params = []
    if len(params) >= 2:
        first_name = params[0].name.lower()
        if "owner" in first_name or "user" in first_name:
            return callback(owner_id, file_id)
        return callback(file_id, owner_id)
    return callback(file_id)


def _resolve_audio_payload(
    *,
    db: sqlite3.Connection,
    owner_id: str,
    file_id: str,
    audio_meta: dict[str, Any],
    read_file_bytes: ReadFileBytesCallable | None,
) -> tuple[bytes, str] | None:
    filename = str(audio_meta.get("filename") or "")
    for key in ("dataUri", "dataUrl", "src"):
        raw_uri = audio_meta.get(key)
        if isinstance(raw_uri, str) and raw_uri.startswith("data:"):
            decoded = _decode_data_uri(raw_uri, filename)
            if decoded is not None:
                return decoded

    if read_file_bytes is not None:
        result = _call_read_file_bytes(read_file_bytes, file_id, owner_id)
        if result is not None:
            if isinstance(result, tuple) and len(result) == 2:
                raw_bytes, mime = result
                if isinstance(raw_bytes, (bytes, bytearray)):
                    data = bytes(raw_bytes)
                    return data, str(mime or _guess_audio_mime(data, filename))
            elif isinstance(result, (bytes, bytearray)):
                data = bytes(result)
                return data, _guess_audio_mime(data, filename)
            elif isinstance(result, str):
                decoded = _decode_data_uri(result, filename)
                if decoded is not None:
                    return decoded

    try:
        kv_row = db.execute("SELECT value FROM kv WHERE key = ?", ("file:" + file_id,)).fetchone()
    except sqlite3.OperationalError:
        kv_row = None
    if kv_row is not None and kv_row[0]:
        try:
            kv_val = json.loads(kv_row[0])
        except ValueError:
            kv_val = kv_row[0]
        if isinstance(kv_val, str):
            decoded = _decode_data_uri(kv_val, filename)
            if decoded is not None:
                return decoded
    return None


_XML_INVALID_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _sanitize_xlsx_text(value: str) -> str:
    cleaned = _XML_INVALID_RE.sub("", value)
    if len(cleaned) > 32767:
        return cleaned[:32764] + "..."
    return cleaned


def _format_answer_for_xlsx(
    orig_q: dict[str, Any],
    response_val: Any,
    option_order: list[int] | None = None,
) -> str:
    qtype = _normalize_qtype(orig_q.get("type"))
    if response_val is None:
        return ""
    if qtype == "mcq":
        raw = (
            response_val.get("answer", response_val.get("choice"))
            if isinstance(response_val, dict)
            else response_val
        )
        idx: int | None = None
        if isinstance(raw, int) and not isinstance(raw, bool):
            idx = raw
        elif isinstance(raw, str):
            clean = raw.strip().upper()
            if len(clean) == 1 and "A" <= clean <= "Z":
                idx = ord(clean) - 65
        if idx is None or idx < 0:
            return ""
        orig_idx = option_order[idx] if (option_order and idx < len(option_order)) else idx
        orig_opts = orig_q.get("options") or []
        letter = chr(65 + orig_idx) if 0 <= orig_idx < 26 else str(orig_idx + 1)
        if 0 <= orig_idx < len(orig_opts) and isinstance(orig_opts[orig_idx], str):
            opt_text = orig_opts[orig_idx].strip()
            return f"{letter}. {opt_text}" if opt_text else letter
        return letter
    if qtype == "truefalse":
        raw = (
            response_val.get("truthValues", response_val.get("answer"))
            if isinstance(response_val, dict)
            else response_val
        )
        if not isinstance(raw, list) or not any(type(v) is bool for v in raw):
            return ""
        parts: list[str] = []
        for idx in range(min(4, len(raw))):
            val = raw[idx]
            label = "Đúng" if val is True else ("Sai" if val is False else "—")
            parts.append(f"{chr(97 + idx)}) {label}")
        return "; ".join(parts)
    if qtype == "short":
        raw = (
            response_val.get("answerText", response_val.get("answer"))
            if isinstance(response_val, dict)
            else response_val
        )
        return "" if raw is None else str(raw).strip()
    if isinstance(response_val, dict):
        raw = response_val.get("text", response_val.get("answerText", response_val.get("answer")))
        return "" if raw is None else str(raw)
    return str(response_val)


def _build_sheet_xml(rows: list[list[Any]]) -> str:
    sheet_rows: list[str] = []
    for r_idx, row in enumerate(rows, 1):
        cells: list[str] = []
        for c_idx, val in enumerate(row):
            ref = _col_ref(c_idx, r_idx)
            if val is None:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t></t></is></c>')
            elif not isinstance(val, bool) and isinstance(val, (int, float)) and math.isfinite(val):
                cells.append(f'<c r="{ref}" t="n"><v>{val}</v></c>')
            else:
                safe_text = xml_escape(_sanitize_xlsx_text(str(val)))
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{safe_text}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )


def _build_room_export_xlsx(
    score_rows: list[list[Any]],
    question_rows: list[list[Any]],
    detail_rows: list[list[Any]] | None = None,
) -> bytes:
    """Dựng tệp XLSX 3 sheet ('BangDiem', 'ThongKeCauHoi', 'BaiLamChiTiet') thuần Python stdlib."""
    sheet1_xml = _build_sheet_xml(score_rows)
    sheet2_xml = _build_sheet_xml(question_rows)
    default_detail_rows: list[list[Any]] = [["STT", "HoTen", "MaHS", "Lop", "LanThi", "MaDe"]]
    sheet3_xml = _build_sheet_xml(detail_rows if detail_rows is not None else default_detail_rows)

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="BangDiem" sheetId="1" r:id="rId1"/>'
        '<sheet name="ThongKeCauHoi" sheetId="2" r:id="rId2"/>'
        '<sheet name="BaiLamChiTiet" sheetId="3" r:id="rId3"/>'
        "</sheets>"
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet3.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet3.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        zf.writestr("xl/worksheets/sheet2.xml", sheet2_xml)
        zf.writestr("xl/worksheets/sheet3.xml", sheet3_xml)
    return buf.getvalue()


def _build_qr_svg(payload: str, *, border: int = 4) -> str:
    """Sinh mã QR SVG chuẩn ISO 18004 từ ma trận QR của tnmaker_export."""
    mat, size = _build_qr_matrix(payload)
    dim = size + 2 * border
    paths: list[str] = []
    for r, row in enumerate(mat):
        for c, dark in enumerate(row):
            if dark:
                paths.append(f"M{c + border} {r + border}h1v1h-1z")
    d = "".join(paths)
    escaped_label = xml_escape(f"Mã QR vào phòng thi: {payload}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
        f'width="240" height="240" shape-rendering="crispEdges" role="img" '
        f'aria-label="{escaped_label}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<path d="{d}" fill="#111827"/>'
        "</svg>"
    )


class CreateRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examId: str = Field(min_length=1, max_length=120)
    mode: Literal["exam", "homework"] = "exam"
    title: str | None = Field(default=None, max_length=240)
    classLabel: str = Field(default="", max_length=120)
    status: Literal["draft", "open"] = "open"
    allowLan: bool = False
    durationMinutes: int | None = Field(default=None, ge=0, le=600)
    opensAt: int | float | str | None = None
    deadlineAt: int | float | str | None = None
    maxAttempts: int = Field(default=1, ge=1, le=50)
    shuffleQuestions: bool = False
    shuffleOptions: bool = False
    variantConfig: dict[str, Any] = Field(default_factory=dict)
    resultPolicy: Literal["hidden", "score_only", "score_and_answers", "full_explanation"] = (
        "score_only"
    )
    releaseResultsAfterClose: bool = False
    requireFullscreen: bool = False
    maxTabSwitches: int = Field(default=0, ge=0, le=100)
    pin: str = Field(default="", max_length=32)

    @field_validator("classLabel", "pin", mode="after")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return unicodedata.normalize("NFC", value).strip()


class UpdateRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["draft", "open", "closed", "archived"] | None = None
    mode: Literal["exam", "homework"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    classLabel: str | None = Field(default=None, max_length=120)
    allowLan: bool | None = None
    durationMinutes: int | None = Field(default=None, ge=0, le=600)
    opensAt: int | float | str | None = None
    deadlineAt: int | float | str | None = None
    maxAttempts: int | None = Field(default=None, ge=1, le=50)
    shuffleQuestions: bool | None = None
    shuffleOptions: bool | None = None
    resultPolicy: (
        Literal["hidden", "score_only", "score_and_answers", "full_explanation"] | None
    ) = None
    releaseResultsAfterClose: bool | None = None
    requireFullscreen: bool | None = None
    maxTabSwitches: int | None = Field(default=None, ge=0, le=100)
    pin: str | None = Field(default=None, max_length=32)


class GradeEssayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    earnedPointsP100: int | None = Field(default=None, ge=0, le=10000)
    earnedPoints: float | None = Field(default=None, ge=0, le=100)
    graderNote: str = Field(default="", max_length=2000)


class LockAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="teacher_lock", max_length=200)


class JoinRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    studentName: str = Field(min_length=1, max_length=120)
    studentCode: str = Field(default="", max_length=60)
    studentClass: str = Field(default="", max_length=60)
    pin: str = Field(default="", max_length=32)

    @field_validator("studentName", "studentCode", "studentClass", "pin", mode="after")
    @classmethod
    def clean_fields(cls, value: str) -> str:
        return unicodedata.normalize("NFC", value).strip()


class SaveAnswersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any] = Field(default_factory=dict)


class RecordEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventType: Literal[
        "tab_hidden",
        "window_blur",
        "fullscreen_exit",
        "copy_attempt",
        "reconnect",
    ]
    detail: dict[str, Any] = Field(default_factory=dict)


class SubmitAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any] | None = None
    autoSubmit: bool = False


class AdjustAttemptScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustmentPointsP100: int | None = Field(default=None, ge=-10000, le=10000)
    adjustmentPoints: float | None = Field(default=None, ge=-100, le=100)
    adjustmentNote: str = Field(default="", max_length=500)


class AckAudioPlayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leaseId: str = Field(min_length=1, max_length=120)


class RegradeQuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questionId: str = Field(min_length=1, max_length=120)
    answer: int | str | None = None
    truthValues: list[bool] | None = None
    answerText: str | None = None
    points: float | None = Field(default=None, ge=0, le=100)


class RegradeRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[RegradeQuestionUpdate] = Field(min_length=1, max_length=300)


_ROOM_SELECT_COLS = (
    "id, owner_id, exam_id, exam_revision, room_code, pin_hash, pin_salt, "
    "mode, title, class_label, status, allow_lan, duration_minutes, "
    "opens_at, deadline_at, max_attempts, shuffle_questions, shuffle_options, "
    "variant_config_json, result_policy, release_results_after_close, "
    "require_fullscreen, max_tab_switches, teacher_snapshot_json, "
    "total_points_p100, created_at, updated_at"
)


def _local_lan_urls(join_path: str, *, base_url: str) -> list[str]:
    if not base_url:
        return []
    port_part = ""
    m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?", base_url.strip(), re.I)
    if not m:
        return []
    scheme = m.group(1).lower()
    if m.group(3):
        port_part = f":{m.group(3)}"
    urls: list[str] = []
    seen: set[str] = set()
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for info in infos:
            ip_str = str(info[4][0])
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private and not ip_obj.is_loopback and ip_str not in seen:
                seen.add(ip_str)
                urls.append(f"{scheme}://{ip_str}{port_part}{join_path}")
    except OSError:
        return []
    return urls[:4]


def _room_to_dict(
    row: tuple[Any, ...],
    *,
    base_url: str = "",
    attempt_count: int = 0,
    needs_manual_count: int = 0,
) -> dict[str, Any]:
    (
        room_id,
        owner_id,
        exam_id,
        exam_revision,
        room_code,
        pin_hash,
        _pin_salt,
        mode,
        title,
        class_label,
        status,
        allow_lan,
        duration_minutes,
        opens_at,
        deadline_at,
        max_attempts,
        shuffle_questions,
        shuffle_options,
        variant_config_json,
        result_policy,
        release_results_after_close,
        require_fullscreen,
        max_tab_switches,
        teacher_snapshot_json,
        total_points_p100,
        created_at,
        updated_at,
    ) = row
    snap = json.loads(teacher_snapshot_json)
    join_path = f"/phong-thi/{room_code}"
    clean_base = base_url.rstrip("/")
    return {
        "id": room_id,
        "ownerId": owner_id,
        "examId": exam_id,
        "examRevision": exam_revision,
        "roomCode": room_code,
        "requiresPin": bool(pin_hash),
        "mode": mode,
        "title": title,
        "classLabel": class_label,
        "subject": str(snap.get("subject") or ""),
        "grade": str(snap.get("grade") or ""),
        "questionCount": len(snap.get("questions") or []),
        "status": status,
        "allowLan": bool(allow_lan),
        "durationMinutes": duration_minutes,
        "opensAt": opens_at,
        "deadlineAt": deadline_at,
        "maxAttempts": max_attempts,
        "shuffleQuestions": bool(shuffle_questions),
        "shuffleOptions": bool(shuffle_options),
        "variantConfig": json.loads(variant_config_json or "{}"),
        "resultPolicy": result_policy,
        "releaseResultsAfterClose": bool(release_results_after_close),
        "requireFullscreen": bool(require_fullscreen),
        "maxTabSwitches": max_tab_switches,
        "totalPointsP100": total_points_p100,
        "choiceGroups": _extract_choice_groups(snap),
        "markingGuidance": str(snap.get("markingGuidance") or "").strip(),
        "joinPath": join_path,
        "joinUrl": (clean_base + join_path) if clean_base else join_path,
        "lanUrls": _local_lan_urls(join_path, base_url=clean_base) if allow_lan else [],
        "attemptCount": attempt_count,
        "needsManualCount": needs_manual_count,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def _room_attempt_counts(db: sqlite3.Connection, room_id: str) -> tuple[int, int]:
    row = db.execute(
        """
        SELECT COUNT(id),
               COALESCE(
                   SUM(
                       CASE WHEN grading_status = 'needs_manual' AND status != 'in_progress'
                            THEN 1 ELSE 0 END
                   ),
                   0
               )
        FROM room_attempts
        WHERE room_id = ?
        """,
        (room_id,),
    ).fetchone()
    if row is None:
        return 0, 0
    return int(row[0] or 0), int(row[1] or 0)


def _is_unescaped_dollar(text: str, idx: int) -> bool:
    backslashes = 0
    pos = idx - 1
    while pos >= 0 and text[pos] == "\\":
        backslashes += 1
        pos -= 1
    return backslashes % 2 == 0


def _safe_math_truncate(text: str, limit: int = 160) -> str:
    """Cắt ngắn văn bản mà không cắt ngang giữa cặp công thức `$...$` hoặc `$$...$$`."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    spans: list[tuple[int, int]] = []
    open_delim: str | None = None
    open_start = -1
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "$" and _is_unescaped_dollar(text, i):
            if open_delim is None:
                if i + 1 < n and text[i + 1] == "$":
                    open_delim = "$$"
                    open_start = i
                    i += 2
                else:
                    open_delim = "$"
                    open_start = i
                    i += 1
            elif open_delim == "$":
                spans.append((open_start, i + 1))
                open_delim = None
                open_start = -1
                i += 1
            else:
                if i + 1 < n and text[i + 1] == "$":
                    spans.append((open_start, i + 2))
                    open_delim = None
                    open_start = -1
                    i += 2
                else:
                    i += 1
        else:
            i += 1

    unclosed_start = open_start if open_delim is not None else None
    max_extend = max(60, limit // 2)

    for span_start, span_end in spans:
        if span_start < limit < span_end:
            if span_end - limit <= max_extend:
                return text[:span_end]
            return text[:span_start].rstrip()

    if unclosed_start is not None and unclosed_start < limit:
        return text[:unclosed_start].rstrip()

    return text[:limit]


def _validate_room_exam_ready(snap: dict[str, Any]) -> dict[str, Any]:
    """Kiểm đề trước khi mở phòng bằng preflight và chặn câu bất đồng đáp án hiện tại."""
    try:
        report = audit_export_preflight(snap)
    except AIError as err:
        issue = {
            "code": err.code,
            "severity": "blocking",
            "questionId": None,
            "ordinal": None,
            "field": "exam",
            "message": str(err),
        }
        raise HTTPException(
            422,
            detail={
                "code": "room_preflight_failed",
                "message": f"Đề thi chưa sẵn sàng để mở phòng: {err}",
                "blockingIssues": [issue],
            },
        ) from None

    blocking_issues: list[dict[str, Any]] = list(report.get("blockingIssues") or [])
    for ordinal, q in enumerate(snap.get("questions") or [], 1):
        if not isinstance(q, dict):
            continue
        chk = q.get("check")
        if not isinstance(chk, dict):
            continue
        q_version = q.get("v")
        chk_version = chk.get("version")
        if q_version is not None and chk_version is not None and chk_version != q_version:
            continue

        raw_problems = chk.get("problems")
        problems = raw_problems if isinstance(raw_problems, list) else []
        disagree_msgs = [
            p.strip() for p in problems if isinstance(p, str) and p.strip().startswith("Bất đồng:")
        ]
        solver = chk.get("solver")
        has_disagreement = (
            chk.get("comparison") == "disagrees"
            or chk.get("status") == "disagrees"
            or (isinstance(solver, dict) and solver.get("comparison") == "disagrees")
            or bool(disagree_msgs)
        )
        if not has_disagreement:
            continue

        q_id = str(q.get("id") or f"q-{ordinal}").strip() or f"q-{ordinal}"
        msg = (
            f"Câu {ordinal}: {disagree_msgs[0]}"
            if disagree_msgs
            else f"Câu {ordinal}: đáp án lưu đang bất đồng với kết quả kiểm tra độc lập."
        )
        blocking_issues.append(
            {
                "code": "answer_disagreement",
                "severity": "blocking",
                "questionId": q_id,
                "ordinal": ordinal,
                "field": "answer",
                "message": msg,
            }
        )

    report["blockingIssues"] = blocking_issues
    if blocking_issues:
        first_msg = str(blocking_issues[0].get("message") or "").strip()
        summary_msg = (
            f"Đề thi chưa sẵn sàng để mở phòng ({len(blocking_issues)} lỗi chặn): {first_msg}"
            if first_msg
            else "Đề thi chưa sẵn sàng để mở phòng; hãy kiểm tra lại câu hỏi và đáp án."
        )
        raise HTTPException(
            422,
            detail={
                "code": "room_preflight_failed",
                "message": summary_msg,
                "blockingIssues": blocking_issues[:10],
            },
        )
    return report


def _public_room_metadata(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        _room_id,
        _owner_id,
        _exam_id,
        _exam_revision,
        room_code,
        pin_hash,
        _pin_salt,
        mode,
        title,
        class_label,
        status,
        _allow_lan,
        duration_minutes,
        opens_at,
        deadline_at,
        max_attempts,
        _shuffle_questions,
        _shuffle_options,
        _variant_config_json,
        result_policy,
        release_results_after_close,
        require_fullscreen,
        max_tab_switches,
        teacher_snapshot_json,
        total_points_p100,
        _created_at,
        _updated_at,
    ) = row
    snap = json.loads(teacher_snapshot_json)
    return {
        "roomCode": room_code,
        "requiresPin": bool(pin_hash),
        "mode": mode,
        "title": title,
        "classLabel": class_label,
        "subject": str(snap.get("subject") or ""),
        "grade": str(snap.get("grade") or ""),
        "questionCount": len(snap.get("questions") or []),
        "status": status,
        "durationMinutes": duration_minutes,
        "opensAt": opens_at,
        "deadlineAt": deadline_at,
        "maxAttempts": max_attempts,
        "resultPolicy": result_policy,
        "releaseResultsAfterClose": bool(release_results_after_close),
        "requireFullscreen": bool(require_fullscreen),
        "maxTabSwitches": max_tab_switches,
        "totalPointsP100": total_points_p100,
        "choiceGroups": _extract_choice_groups(snap),
    }


def _attempt_summary_dict(row: tuple[Any, ...], total_points_p100: int) -> dict[str, Any]:
    (
        attempt_id,
        room_id,
        student_name,
        student_code,
        student_class,
        attempt_no,
        variant_offset,
        variant_code,
        status,
        started_at,
        expires_at,
        submitted_at,
        auto_score_p100,
        manual_score_p100,
        total_score_p100,
        grading_status,
        tab_switch_count,
        fullscreen_exit_count,
        last_heartbeat_at,
    ) = row[:19]
    score_adjustment_p100 = int(row[19]) if len(row) > 19 and row[19] is not None else 0
    adjustment_note = str(row[20] or "") if len(row) > 20 else ""
    return {
        "id": attempt_id,
        "roomId": room_id,
        "studentName": student_name,
        "studentCode": student_code,
        "studentClass": student_class,
        "attemptNo": attempt_no,
        "variantOffset": variant_offset,
        "variantCode": variant_code,
        "status": status,
        "startedAt": started_at,
        "expiresAt": expires_at,
        "submittedAt": submitted_at,
        "autoScoreP100": auto_score_p100,
        "manualScoreP100": manual_score_p100,
        "scoreAdjustmentP100": score_adjustment_p100,
        "adjustmentNote": adjustment_note,
        "totalScoreP100": total_score_p100,
        "totalPointsP100": total_points_p100,
        "gradingStatus": grading_status,
        "isProvisionalScore": grading_status == "needs_manual",
        "tabSwitchCount": tab_switch_count,
        "fullscreenExitCount": fullscreen_exit_count,
        "lastHeartbeatAt": last_heartbeat_at,
    }


_ATTEMPT_PUBLIC_COLS = (
    "id, room_id, token_hash, student_name, student_code, student_class, "
    "attempt_no, variant_offset, variant_code, delivery_map_json, status, "
    "started_at, expires_at, submitted_at, auto_score_p100, manual_score_p100, "
    "total_score_p100, grading_status, tab_switch_count, fullscreen_exit_count, "
    "last_heartbeat_at, score_adjustment_p100, adjustment_note"
)


def install_exam_rooms(
    app: FastAPI,
    connect: ConnectCallable,
    owner_resolver: OwnerResolver,
    read_exam: ReadExamCallable,
    *,
    read_file_bytes: ReadFileBytesCallable | None = None,
    clock: Callable[[], float] = time.time,
) -> None:
    """Đăng ký toàn bộ API phòng thi trực tuyến/BTVN và cổng học sinh công khai."""
    if AIError not in app.exception_handlers:

        async def _ai_error(_request: Request, error: Exception) -> JSONResponse:
            assert isinstance(error, AIError)
            return JSONResponse(
                {"error": str(error), "code": error.code},
                error.http_status or (404 if error.code == "exam_not_found" else 409),
            )

        app.add_exception_handler(AIError, _ai_error)

    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        _ensure_schema(db)

    def _require_owner(request: Request) -> str:
        uid = owner_resolver(request)
        if not uid or not isinstance(uid, str):
            raise HTTPException(401, "Đăng nhập trước khi quản lý phòng thi.")
        return uid

    def _load_owned_room(db: sqlite3.Connection, room_id: str, owner_id: str) -> tuple[Any, ...]:
        row = db.execute(
            f"SELECT {_ROOM_SELECT_COLS} FROM exam_rooms WHERE id = ? AND owner_id = ?",
            (room_id, owner_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy phòng thi thuộc quyền quản lý của bạn.")
        return row

    def _load_room_by_code(db: sqlite3.Connection, room_code: str) -> tuple[Any, ...]:
        clean = room_code.strip().upper()
        if not clean:
            raise HTTPException(404, "Mã phòng thi không hợp lệ.")
        row = db.execute(
            f"SELECT {_ROOM_SELECT_COLS} FROM exam_rooms WHERE room_code = ?",
            (clean,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy phòng thi với mã này.")
        return row

    def _expire_attempt_if_needed(
        db: sqlite3.Connection,
        attempt_row: tuple[Any, ...],
        room_row: tuple[Any, ...],
        now_ms: int,
    ) -> tuple[Any, ...]:
        status = attempt_row[10]
        expires_at = attempt_row[12]
        if status == "in_progress" and expires_at is not None and now_ms > expires_at:
            snap = json.loads(room_row[23])
            dmap = json.loads(attempt_row[9])
            auto_s, manual_s, total_s, g_status = _grade_attempt_tx(
                db, attempt_row[0], snap, dmap, expires_at
            )
            adj_p100 = (
                int(attempt_row[21]) if len(attempt_row) > 21 and attempt_row[21] is not None else 0
            )
            total_s = _apply_score_adjustment(total_s, adj_p100, int(room_row[24]))
            db.execute(
                """
                UPDATE room_attempts
                SET status = 'auto_submitted',
                    submitted_at = ?,
                    auto_score_p100 = ?,
                    manual_score_p100 = ?,
                    total_score_p100 = ?,
                    grading_status = ?
                WHERE id = ?
                """,
                (expires_at, auto_s, manual_s, total_s, g_status, attempt_row[0]),
            )
            db.execute(
                "INSERT INTO attempt_events (attempt_id, event_type, detail_json, created_at) "
                "VALUES (?, 'submit', ?, ?)",
                (attempt_id := attempt_row[0], '{"autoSubmit":true,"reason":"expired"}', now_ms),
            )
            refreshed = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            assert refreshed is not None
            return refreshed
        return attempt_row

    def _require_attempt(
        db: sqlite3.Connection,
        attempt_id: str,
        request: Request,
        *,
        auto_expire: bool = True,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        token = request.headers.get("X-Attempt-Token")
        if not token or not isinstance(token, str):
            raise HTTPException(401, "Thiếu mã phiên làm bài (X-Attempt-Token).")
        attempt_row = db.execute(
            f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not attempt_row:
            raise HTTPException(404, "Không tìm thấy lượt làm bài.")
        expected_hash = attempt_row[2]
        given_hash = _sha256_hex(token)
        if not hmac.compare_digest(given_hash, expected_hash):
            raise HTTPException(403, "Mã phiên làm bài không hợp lệ.")
        room_row = db.execute(
            f"SELECT {_ROOM_SELECT_COLS} FROM exam_rooms WHERE id = ?",
            (attempt_row[1],),
        ).fetchone()
        if not room_row:
            raise HTTPException(404, "Phòng thi không còn tồn tại.")
        if auto_expire:
            attempt_row = _expire_attempt_if_needed(db, attempt_row, room_row, _now_ms(clock))
        return attempt_row, room_row

    def _room_analytics_data(db: sqlite3.Connection, room_row: tuple[Any, ...]) -> dict[str, Any]:
        room_id = room_row[0]
        snap = json.loads(room_row[23])
        total_points_p100 = int(room_row[24])
        attempts = db.execute(
            """
            SELECT id, student_name, student_code, student_class, status,
                   auto_score_p100, manual_score_p100, total_score_p100,
                   grading_status, tab_switch_count, fullscreen_exit_count,
                   started_at, submitted_at, variant_code, attempt_no,
                   score_adjustment_p100, adjustment_note
            FROM room_attempts
            WHERE room_id = ?
            ORDER BY started_at ASC
            """,
            (room_id,),
        ).fetchall()

        finalized = [a for a in attempts if a[4] != "in_progress"]
        # Chỉ đưa bài đã chấm đủ vào thống kê chính thức
        # (bài chờ chấm tự luận không làm lệch phổ điểm).
        official = [a for a in finalized if a[8] in ("auto_graded", "graded")]
        scores = [int(a[7]) for a in official]
        in_progress_count = sum(1 for a in attempts if a[4] == "in_progress")
        locked_count = sum(1 for a in attempts if a[4] == "locked")
        needs_manual_count = sum(1 for a in finalized if a[8] == "needs_manual")
        graded_count = len(official)

        avg_p100 = round(sum(scores) / len(scores)) if scores else 0
        min_p100 = min(scores) if scores else 0
        max_p100 = max(scores) if scores else 0
        sorted_scores = sorted(scores)
        if not sorted_scores:
            median_p100 = 0
        elif len(sorted_scores) % 2 == 1:
            median_p100 = sorted_scores[len(sorted_scores) // 2]
        else:
            mid = len(sorted_scores) // 2
            median_p100 = (sorted_scores[mid - 1] + sorted_scores[mid]) // 2

        pass_threshold = (total_points_p100 + 1) // 2 if total_points_p100 > 0 else 0
        pass_count = sum(1 for s in scores if s >= pass_threshold) if scores else 0
        pass_rate = round(pass_count * 100.0 / len(scores), 1) if scores else 0.0

        bucket_specs: list[tuple[str, float, float]] = [
            ("0 – <2", 0.0, 2.0),
            ("2 – <4", 2.0, 4.0),
            ("4 – <5", 4.0, 5.0),
            ("5 – <6,5", 5.0, 6.5),
            ("6,5 – <8", 6.5, 8.0),
            ("8 – <9", 8.0, 9.0),
            ("9 – 10", 9.0, 10.1),
        ]
        bucket_counts = [0] * len(bucket_specs)
        denom = total_points_p100 if total_points_p100 > 0 else 1000
        for s in scores:
            norm10 = (s / denom) * 10.0
            for idx, (_, min10, max10) in enumerate(bucket_specs):
                if min10 <= norm10 < max10:
                    bucket_counts[idx] += 1
                    break

        finalized_ids = {a[0] for a in finalized}
        answer_rows = db.execute(
            """
            SELECT attempt_id, question_id, response_json, earned_points_p100
            FROM attempt_answers
            WHERE attempt_id IN (SELECT id FROM room_attempts WHERE room_id = ?)
            """,
            (room_id,),
        ).fetchall()
        answers_by_qid: dict[str, list[tuple[str, Any, int | None]]] = {}
        for aid, qid, resp_json, earned in answer_rows:
            if aid in finalized_ids:
                answers_by_qid.setdefault(qid, []).append((aid, json.loads(resp_json), earned))

        question_stats: list[dict[str, Any]] = []
        for idx, q in enumerate(snap.get("questions") or [], 1):
            qid = str(q["id"])
            qtype = _normalize_qtype(q.get("type"))
            q_max_p100 = int(q.get("_maxPointsP100", _question_points_p100(q)))
            q_entries = answers_by_qid.get(qid, [])
            graded_entries = [e for e in q_entries if e[2] is not None]
            correct_cnt = sum(1 for e in graded_entries if e[2] == q_max_p100 and q_max_p100 > 0)
            partial_cnt = sum(
                1 for e in graded_entries if e[2] is not None and 0 < e[2] < q_max_p100
            )
            wrong_cnt = sum(1 for e in graded_entries if e[2] == 0)
            avg_q_p100 = (
                round(sum(int(e[2] or 0) for e in graded_entries) / len(graded_entries))
                if graded_entries
                else 0
            )
            correct_rate = (
                round(correct_cnt * 100.0 / len(graded_entries), 1) if graded_entries else 0.0
            )
            question_stats.append(
                {
                    "order": idx,
                    "questionId": qid,
                    "type": qtype,
                    "stem": _safe_math_truncate(str(q.get("stem") or ""), 160),
                    "maxPointsP100": q_max_p100,
                    "attemptCount": len(q_entries),
                    "gradedCount": len(graded_entries),
                    "correctCount": correct_cnt,
                    "partialCount": partial_cnt,
                    "wrongCount": wrong_cnt,
                    "avgEarnedP100": avg_q_p100,
                    "correctRate": correct_rate,
                }
            )

        return {
            "roomId": room_id,
            "totalAttempts": len(attempts),
            "submittedCount": len(finalized),
            "inProgressCount": in_progress_count,
            "lockedCount": locked_count,
            "gradedCount": graded_count,
            "provisionalCount": needs_manual_count,
            "needsManualCount": needs_manual_count,
            "totalPointsP100": total_points_p100,
            "avgScoreP100": avg_p100,
            "minScoreP100": min_p100,
            "maxScoreP100": max_p100,
            "medianScoreP100": median_p100,
            "passCount": pass_count,
            "passRate": pass_rate,
            "histogram": [
                {"label": label, "count": bucket_counts[b_idx]}
                for b_idx, (label, _, _) in enumerate(bucket_specs)
            ],
            "questionStats": question_stats,
            "attempts": attempts,
        }

    # =========================================================================
    # 1. TEACHER ROOM MANAGEMENT ENDPOINTS
    # =========================================================================

    @app.post("/api/rooms", status_code=201)
    def create_room(body: CreateRoomRequest, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        raw_exam = read_exam(request, body.examId)
        exam = raw_exam[1] if isinstance(raw_exam, tuple) and len(raw_exam) == 2 else raw_exam
        if not isinstance(exam, dict):
            raise HTTPException(404, "Không tìm thấy đề thi để mở phòng.")

        opens_at = _parse_epoch_ms(body.opensAt, field_name="opensAt")
        deadline_at = _parse_epoch_ms(body.deadlineAt, field_name="deadlineAt")
        if opens_at is not None and deadline_at is not None and opens_at >= deadline_at:
            raise HTTPException(422, "Thời điểm mở phòng phải trước hạn nộp bài.")

        snap, total_points_p100 = _snapshot_exam_for_room(exam)
        if body.status == "open":
            _validate_room_exam_ready(snap)
        title = (body.title or "").strip() or str(snap.get("title") or "Phòng thi").strip()
        duration = body.durationMinutes
        if duration is None:
            raw_min = snap.get("minutes")
            duration = (
                int(raw_min)
                if isinstance(raw_min, int) and not isinstance(raw_min, bool) and raw_min >= 0
                else (45 if body.mode == "exam" else 0)
            )
        if body.mode == "exam" and duration <= 0:
            raise HTTPException(422, "Chế độ kiểm tra cần thời lượng làm bài lớn hơn 0 phút.")

        pin_hash, pin_salt = _hash_pin(body.pin)
        now_ms = _now_ms(clock)
        room_id = str(uuid4())
        exam_rev = int(snap.get("revision") or 1)
        snap_json = json.dumps(snap, ensure_ascii=False, allow_nan=False)
        vconf_json = json.dumps(body.variantConfig or {}, ensure_ascii=False, allow_nan=False)

        with connect() as db:
            _begin_immediate(db)
            room_code = ""
            for _ in range(12):
                candidate = _generate_room_code()
                exists = db.execute(
                    "SELECT 1 FROM exam_rooms WHERE room_code = ?", (candidate,)
                ).fetchone()
                if not exists:
                    room_code = candidate
                    break
            if not room_code:
                raise HTTPException(500, "Không thể cấp mã phòng mới; vui lòng thử lại.")
            db.execute(
                """
                INSERT INTO exam_rooms (
                    id, owner_id, exam_id, exam_revision, room_code, pin_hash, pin_salt,
                    mode, title, class_label, status, allow_lan, duration_minutes,
                    opens_at, deadline_at, max_attempts, shuffle_questions, shuffle_options,
                    variant_config_json, result_policy, release_results_after_close,
                    require_fullscreen, max_tab_switches, teacher_snapshot_json,
                    total_points_p100, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    room_id,
                    owner_id,
                    str(body.examId),
                    exam_rev,
                    room_code,
                    pin_hash,
                    pin_salt,
                    body.mode,
                    title[:240],
                    body.classLabel[:120],
                    body.status,
                    int(body.allowLan),
                    duration,
                    opens_at,
                    deadline_at,
                    body.maxAttempts,
                    int(body.shuffleQuestions),
                    int(body.shuffleOptions),
                    vconf_json,
                    body.resultPolicy,
                    int(body.releaseResultsAfterClose),
                    int(body.requireFullscreen),
                    body.maxTabSwitches,
                    snap_json,
                    total_points_p100,
                    now_ms,
                    now_ms,
                ),
            )
            created_row = _load_owned_room(db, room_id, owner_id)
        return _room_to_dict(created_row, base_url=str(request.base_url))

    @app.get("/api/rooms")
    def list_rooms(
        request: Request,
        examId: str | None = Query(default=None),
        status: str | None = Query(default=None),
    ) -> dict[str, Any]:
        owner_id = _require_owner(request)
        clauses = ["r.owner_id = ?"]
        params: list[Any] = [owner_id]
        if examId:
            clauses.append("r.exam_id = ?")
            params.append(examId)
        if status and status in VALID_ROOM_STATUSES:
            clauses.append("r.status = ?")
            params.append(status)
        where_sql = " AND ".join(clauses)
        with connect() as db:
            rows = db.execute(
                f"""
                SELECT r.id, r.owner_id, r.exam_id, r.exam_revision, r.room_code,
                       r.pin_hash, r.pin_salt, r.mode, r.title, r.class_label,
                       r.status, r.allow_lan, r.duration_minutes, r.opens_at,
                       r.deadline_at, r.max_attempts, r.shuffle_questions,
                       r.shuffle_options, r.variant_config_json, r.result_policy,
                       r.release_results_after_close, r.require_fullscreen,
                       r.max_tab_switches, r.teacher_snapshot_json,
                       r.total_points_p100, r.created_at, r.updated_at,
                       COUNT(a.id) AS attempt_count,
                       SUM(CASE WHEN a.grading_status = 'needs_manual' AND a.status != 'in_progress'
                                THEN 1 ELSE 0 END) AS needs_manual_count
                FROM exam_rooms r
                LEFT JOIN room_attempts a ON a.room_id = r.id
                WHERE {where_sql}
                GROUP BY r.id
                ORDER BY r.created_at DESC, r.rowid DESC
                """,
                params,
            ).fetchall()
        base_url = str(request.base_url)
        rooms = [
            _room_to_dict(
                row[:27],
                base_url=base_url,
                attempt_count=int(row[27] or 0),
                needs_manual_count=int(row[28] or 0),
            )
            for row in rows
        ]
        return {"rooms": rooms}

    @app.get("/api/rooms/{room_id}")
    def get_room_detail(room_id: str, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            now_ms = _now_ms(clock)
            raw_attempts = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE room_id = ? "
                "ORDER BY started_at DESC",
                (room_id,),
            ).fetchall()
            attempts_out: list[dict[str, Any]] = []
            needs_manual = 0
            for raw_a in raw_attempts:
                a_row = _expire_attempt_if_needed(db, raw_a, room_row, now_ms)
                if a_row[17] == "needs_manual" and a_row[10] != "in_progress":
                    needs_manual += 1
                summary_tuple = (
                    a_row[0],
                    a_row[1],
                    a_row[3],
                    a_row[4],
                    a_row[5],
                    a_row[6],
                    a_row[7],
                    a_row[8],
                    a_row[10],
                    a_row[11],
                    a_row[12],
                    a_row[13],
                    a_row[14],
                    a_row[15],
                    a_row[16],
                    a_row[17],
                    a_row[18],
                    a_row[19],
                    a_row[20],
                    a_row[21] if len(a_row) > 21 else 0,
                    a_row[22] if len(a_row) > 22 else "",
                )
                attempts_out.append(_attempt_summary_dict(summary_tuple, int(room_row[24])))

        snap = json.loads(room_row[23])
        answer_keys: list[dict[str, Any]] = []
        for q_idx, q in enumerate(snap.get("questions") or [], 1):
            if not isinstance(q, dict):
                continue
            qtype = _normalize_qtype(q.get("type"))
            key_item: dict[str, Any] = {
                "order": q_idx,
                "questionId": str(q.get("id") or f"q-{q_idx}"),
                "type": qtype,
                "stem": _safe_math_truncate(str(q.get("stem") or ""), 200),
                "points": round(int(q.get("_maxPointsP100", _question_points_p100(q))) / 100.0, 2),
            }
            if qtype == "mcq":
                key_item["options"] = list(q.get("options") or [])
                key_item["answer"] = _parse_mcq_answer(q)
            elif qtype == "truefalse":
                key_item["options"] = list(q.get("options") or [])
                tf = _parse_truefalse_key(q)
                key_item["truthValues"] = (
                    list(tf) if tf is not None else [False, False, False, False]
                )
            elif qtype == "short":
                key_val = q.get("answerText")
                if key_val is None or (isinstance(key_val, str) and not key_val.strip()):
                    key_val = q.get("answer")
                if key_val is None:
                    key_val = saved_answer(q)
                key_item["answerText"] = "" if key_val is None else str(key_val)
            answer_keys.append(key_item)

        room_dict = _room_to_dict(
            room_row,
            base_url=str(request.base_url),
            attempt_count=len(attempts_out),
            needs_manual_count=needs_manual,
        )
        return {
            "room": room_dict,
            "attempts": attempts_out,
            "answerKeys": answer_keys,
            "serverNow": now_ms,
        }

    @app.patch("/api/rooms/{room_id}")
    def update_room(room_id: str, body: UpdateRoomRequest, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            row = _load_owned_room(db, room_id, owner_id)
            updates: dict[str, Any] = {"updated_at": now_ms}
            if body.status is not None:
                if body.status == "open" and str(row[10]) != "open":
                    _validate_room_exam_ready(json.loads(row[23]))
                updates["status"] = body.status
            if body.mode is not None:
                updates["mode"] = body.mode
            if body.title is not None:
                updates["title"] = unicodedata.normalize("NFC", body.title).strip()[:240]
            if body.classLabel is not None:
                updates["class_label"] = unicodedata.normalize("NFC", body.classLabel).strip()[:120]
            if body.allowLan is not None:
                updates["allow_lan"] = int(body.allowLan)
            if body.durationMinutes is not None:
                updates["duration_minutes"] = body.durationMinutes
            if "opensAt" in body.model_fields_set:
                updates["opens_at"] = _parse_epoch_ms(body.opensAt, field_name="opensAt")
            if "deadlineAt" in body.model_fields_set:
                updates["deadline_at"] = _parse_epoch_ms(body.deadlineAt, field_name="deadlineAt")
            eff_opens = updates.get("opens_at", row[13])
            eff_deadline = updates.get("deadline_at", row[14])
            if eff_opens is not None and eff_deadline is not None and eff_opens >= eff_deadline:
                raise HTTPException(422, "Thời điểm mở phòng phải trước hạn nộp bài.")
            if body.maxAttempts is not None:
                updates["max_attempts"] = body.maxAttempts
            if body.shuffleQuestions is not None:
                updates["shuffle_questions"] = int(body.shuffleQuestions)
            if body.shuffleOptions is not None:
                updates["shuffle_options"] = int(body.shuffleOptions)
            if body.resultPolicy is not None:
                updates["result_policy"] = body.resultPolicy
            if body.releaseResultsAfterClose is not None:
                updates["release_results_after_close"] = int(body.releaseResultsAfterClose)
            if body.requireFullscreen is not None:
                updates["require_fullscreen"] = int(body.requireFullscreen)
            if body.maxTabSwitches is not None:
                updates["max_tab_switches"] = body.maxTabSwitches
            if body.pin is not None:
                pin_hash, pin_salt = _hash_pin(body.pin)
                updates["pin_hash"] = pin_hash
                updates["pin_salt"] = pin_salt

            set_clause = ", ".join(f"{col} = ?" for col in updates)
            db.execute(
                f"UPDATE exam_rooms SET {set_clause} WHERE id = ? AND owner_id = ?",
                [*updates.values(), room_id, owner_id],
            )
            refreshed = _load_owned_room(db, room_id, owner_id)
            attempt_count, needs_manual_count = _room_attempt_counts(db, room_id)
        return {
            "room": _room_to_dict(
                refreshed,
                base_url=str(request.base_url),
                attempt_count=attempt_count,
                needs_manual_count=needs_manual_count,
            )
        }

    @app.delete("/api/rooms/{room_id}")
    def delete_room(room_id: str, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        with connect() as db:
            _begin_immediate(db)
            _load_owned_room(db, room_id, owner_id)
            attempt_ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM room_attempts WHERE room_id = ?", (room_id,)
                ).fetchall()
            ]
            for aid in attempt_ids:
                db.execute("DELETE FROM attempt_answers WHERE attempt_id = ?", (aid,))
                db.execute("DELETE FROM attempt_events WHERE attempt_id = ?", (aid,))
                db.execute("DELETE FROM attempt_audio_plays WHERE attempt_id = ?", (aid,))
            db.execute("DELETE FROM room_attempts WHERE room_id = ?", (room_id,))
            db.execute("DELETE FROM exam_rooms WHERE id = ? AND owner_id = ?", (room_id, owner_id))
        return {"ok": True, "deleted": room_id}

    @app.get("/api/rooms/{room_id}/grading-queue")
    def get_grading_queue(
        room_id: str,
        request: Request,
        includeGraded: bool = Query(default=True),
    ) -> dict[str, Any]:
        owner_id = _require_owner(request)
        summary_by_aid: dict[str, dict[str, Any]] = {}
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            snap = json.loads(room_row[23])
            orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
            has_choice_groups = bool(_extract_choice_groups(snap))
            now_ms = _now_ms(clock)
            raw_attempts = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE room_id = ? "
                "ORDER BY submitted_at ASC, started_at ASC",
                (room_id,),
            ).fetchall()
            finalized_attempts: list[tuple[Any, ...]] = []
            for raw_a in raw_attempts:
                checked_a = _expire_attempt_if_needed(db, raw_a, room_row, now_ms)
                if checked_a[10] != "in_progress":
                    finalized_attempts.append(checked_a)

            rows = db.execute(
                """
                SELECT a.id, a.student_name, a.student_code, a.student_class,
                       a.attempt_no, a.status, a.submitted_at, a.total_score_p100,
                       ans.question_id, ans.max_points_p100, ans.response_json,
                       ans.earned_points_p100, ans.grader_note, ans.graded_at
                FROM room_attempts a
                JOIN attempt_answers ans ON ans.attempt_id = a.id
                WHERE a.room_id = ? AND a.status != 'in_progress' AND ans.question_type = 'essay'
                ORDER BY (ans.earned_points_p100 IS NOT NULL) ASC, a.submitted_at ASC
                """,
                (room_id,),
            ).fetchall()

            if has_choice_groups and rows:
                all_ans_rows = db.execute(
                    """
                    SELECT ans.attempt_id, ans.question_id, ans.question_type,
                           ans.max_points_p100, ans.response_json, ans.is_auto_graded,
                           ans.earned_points_p100
                    FROM attempt_answers ans
                    JOIN room_attempts a ON a.id = ans.attempt_id
                    WHERE a.room_id = ? AND a.status != 'in_progress'
                    """,
                    (room_id,),
                ).fetchall()
                by_aid: dict[str, dict[str, tuple[str, int, Any, int, int | None]]] = {}
                for ar in all_ans_rows:
                    by_aid.setdefault(ar[0], {})[ar[1]] = (
                        str(ar[2]),
                        int(ar[3]),
                        json.loads(ar[4]),
                        int(ar[5]),
                        ar[6],
                    )
                for aid, ans_map in by_aid.items():
                    summary_by_aid[aid] = _summarize_attempt_scores(orig_questions, ans_map)

        q_map = {str(q["id"]): (idx, q) for idx, q in enumerate(orig_questions, 1)}
        items: list[dict[str, Any]] = []
        pending_count = 0
        graded_count = 0
        for r in rows:
            q_num, q_obj = q_map.get(r[8], (0, {}))
            if has_choice_groups and q_obj:
                q_grp = _question_choice_group(q_obj)
                if q_grp:
                    att_summary = summary_by_aid.get(r[0])
                    if att_summary is not None:
                        answered_in_grp = (
                            att_summary["trackStats"].get(q_grp, {}).get("answeredCount", 0) > 0
                        )
                        if (
                            q_grp != att_summary["chosenTrack"]
                            and not answered_in_grp
                            and r[11] is None
                        ):
                            continue
            is_graded = r[11] is not None
            if is_graded:
                graded_count += 1
            else:
                pending_count += 1
            if not includeGraded and is_graded:
                continue
            items.append(
                {
                    "attemptId": r[0],
                    "studentName": r[1],
                    "studentCode": r[2],
                    "studentClass": r[3],
                    "attemptNo": r[4],
                    "attemptStatus": r[5],
                    "submittedAt": r[6],
                    "attemptTotalScoreP100": r[7],
                    "questionId": r[8],
                    "questionNumber": q_num,
                    "choiceGroup": _question_choice_group(q_obj) or None,
                    "stem": str(q_obj.get("stem") or ""),
                    "richDoc": q_obj.get("richDoc"),
                    "rubric": q_obj.get("rubric") or [],
                    "explanation": str(q_obj.get("explanation") or ""),
                    "maxPointsP100": int(r[9]),
                    "response": json.loads(r[10]),
                    "earnedPointsP100": r[11],
                    "graderNote": r[12],
                    "gradedAt": r[13],
                }
            )
        total_pts_p100 = int(room_row[24])
        attempt_summaries = [
            {
                "attemptId": a[0],
                "studentName": a[3],
                "studentCode": a[4],
                "studentClass": a[5],
                "attemptNo": int(a[6]),
                "status": a[10],
                "gradingStatus": a[17],
                "isProvisionalScore": a[17] == "needs_manual",
                "autoScoreP100": int(a[14]),
                "manualScoreP100": int(a[15]),
                "scoreAdjustmentP100": int(a[21]) if len(a) > 21 and a[21] is not None else 0,
                "adjustmentNote": str(a[22] or "") if len(a) > 22 else "",
                "totalScoreP100": int(a[16]),
                "totalPointsP100": total_pts_p100,
            }
            for a in finalized_attempts
        ]
        return {
            "roomId": room_id,
            "markingGuidance": str(snap.get("markingGuidance") or "").strip(),
            "pendingCount": pending_count,
            "gradedCount": graded_count,
            "totalAttempts": len(raw_attempts),
            "attempts": attempt_summaries,
            "items": items,
        }

    @app.put("/api/rooms/{room_id}/attempts/{attempt_id}/grades/{question_id}")
    def grade_essay_answer(
        room_id: str,
        attempt_id: str,
        question_id: str,
        body: GradeEssayRequest,
        request: Request,
    ) -> dict[str, Any]:
        owner_id = _require_owner(request)
        if body.earnedPointsP100 is not None:
            p100 = body.earnedPointsP100
        elif body.earnedPoints is not None:
            parsed = _to_p100(body.earnedPoints)
            if parsed is None:
                raise HTTPException(422, "Điểm chấm tay không hợp lệ.")
            p100 = parsed
        else:
            raise HTTPException(422, "Cần nhập điểm chấm tay cho câu hỏi.")

        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            attempt_row = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE id = ? AND room_id = ?",
                (attempt_id, room_id),
            ).fetchone()
            if not attempt_row:
                raise HTTPException(404, "Không tìm thấy lượt làm bài trong phòng này.")
            attempt_row = _expire_attempt_if_needed(db, attempt_row, room_row, now_ms)
            if attempt_row[10] == "in_progress":
                raise HTTPException(
                    409, "Thí sinh đang làm bài; thu bài hoặc khóa trước khi chấm tự luận."
                )

            snap = json.loads(room_row[23])
            orig_q = next(
                (q for q in snap.get("questions") or [] if str(q.get("id")) == question_id),
                None,
            )
            if orig_q is None:
                raise HTTPException(404, "Không tìm thấy câu hỏi trong đề của phòng thi.")

            ans_row = db.execute(
                "SELECT question_type, max_points_p100 FROM attempt_answers "
                "WHERE attempt_id = ? AND question_id = ?",
                (attempt_id, question_id),
            ).fetchone()
            max_p100 = (
                int(ans_row[1])
                if ans_row is not None
                else int(orig_q.get("_maxPointsP100", _question_points_p100(orig_q)))
            )
            if not 0 <= p100 <= max_p100:
                raise HTTPException(
                    422,
                    f"Điểm chấm phải nằm trong khoảng 0 đến {max_p100 / 100:.2f} điểm.",
                )

            clean_note = unicodedata.normalize("NFC", body.graderNote).strip()[:2000]
            if ans_row is None:
                db.execute(
                    """
                    INSERT INTO attempt_answers (
                        attempt_id, question_id, question_type, max_points_p100,
                        response_json, is_auto_graded, earned_points_p100,
                        grader_note, graded_by, graded_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'null', 0, ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        question_id,
                        _normalize_qtype(orig_q.get("type")),
                        max_p100,
                        p100,
                        clean_note,
                        owner_id,
                        now_ms,
                        now_ms,
                    ),
                )
            else:
                db.execute(
                    """
                    UPDATE attempt_answers
                    SET earned_points_p100 = ?, grader_note = ?, graded_by = ?,
                        graded_at = ?, updated_at = ?
                    WHERE attempt_id = ? AND question_id = ?
                    """,
                    (p100, clean_note, owner_id, now_ms, now_ms, attempt_id, question_id),
                )

            all_ans = db.execute(
                "SELECT question_id, question_type, max_points_p100, response_json, "
                "is_auto_graded, earned_points_p100 FROM attempt_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()
            ans_data_map = {
                ar[0]: (str(ar[1]), int(ar[2]), json.loads(ar[3]), int(ar[4]), ar[5])
                for ar in all_ans
            }
            orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
            summary = _summarize_attempt_scores(orig_questions, ans_data_map)
            auto_score = summary["autoScoreP100"]
            manual_score = summary["manualScoreP100"]
            adj_p100 = (
                int(attempt_row[21]) if len(attempt_row) > 21 and attempt_row[21] is not None else 0
            )
            adj_note = str(attempt_row[22] or "") if len(attempt_row) > 22 else ""
            total_points_p100 = int(room_row[24])
            total_score = _apply_score_adjustment(
                summary["totalScoreP100"], adj_p100, total_points_p100
            )
            grading_status = summary["gradingStatus"]

            db.execute(
                """
                UPDATE room_attempts
                SET auto_score_p100 = ?, manual_score_p100 = ?,
                    total_score_p100 = ?, grading_status = ?
                WHERE id = ?
                """,
                (auto_score, manual_score, total_score, grading_status, attempt_id),
            )

        return {
            "attemptId": attempt_id,
            "questionId": question_id,
            "earnedPointsP100": p100,
            "maxPointsP100": max_p100,
            "graderNote": clean_note,
            "autoScoreP100": auto_score,
            "manualScoreP100": manual_score,
            "scoreAdjustmentP100": adj_p100,
            "adjustmentNote": adj_note,
            "totalScoreP100": total_score,
            "totalPointsP100": total_points_p100,
            "gradingStatus": grading_status,
            "ungradedEssayCount": summary["ungradedEssayCount"],
            "isProvisionalScore": summary["isProvisionalScore"],
            "chosenTrack": summary["chosenTrack"],
            "trackScores": summary["trackScores"],
        }

    @app.put("/api/rooms/{room_id}/attempts/{attempt_id}/adjustment")
    def adjust_attempt_score(
        room_id: str,
        attempt_id: str,
        body: AdjustAttemptScoreRequest,
        request: Request,
    ) -> dict[str, Any]:
        """Điều chỉnh tổng điểm cấp bài (vd -0,25 lỗi đơn vị), giữ nguyên điểm từng câu."""
        owner_id = _require_owner(request)
        if body.adjustmentPointsP100 is not None:
            adj_p100 = int(body.adjustmentPointsP100)
        elif body.adjustmentPoints is not None:
            parsed = _to_signed_p100(body.adjustmentPoints)
            if parsed is None:
                raise HTTPException(422, "Giá trị điều chỉnh tổng bài không hợp lệ.")
            adj_p100 = parsed
        else:
            raise HTTPException(422, "Cần nhập giá trị điều chỉnh tổng điểm bài làm.")

        clean_note = unicodedata.normalize("NFC", body.adjustmentNote).strip()[:500]
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            attempt_row = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE id = ? AND room_id = ?",
                (attempt_id, room_id),
            ).fetchone()
            if not attempt_row:
                raise HTTPException(404, "Không tìm thấy lượt làm bài trong phòng này.")
            attempt_row = _expire_attempt_if_needed(db, attempt_row, room_row, now_ms)
            if attempt_row[10] == "in_progress":
                raise HTTPException(
                    409, "Thí sinh đang làm bài; thu bài hoặc khóa trước khi điều chỉnh tổng điểm."
                )

            snap = json.loads(room_row[23])
            all_ans = db.execute(
                "SELECT question_id, question_type, max_points_p100, response_json, "
                "is_auto_graded, earned_points_p100 FROM attempt_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()
            ans_data_map = {
                ar[0]: (str(ar[1]), int(ar[2]), json.loads(ar[3]), int(ar[4]), ar[5])
                for ar in all_ans
            }
            orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
            summary = _summarize_attempt_scores(orig_questions, ans_data_map)
            total_points_p100 = int(room_row[24])
            total_score = _apply_score_adjustment(
                summary["totalScoreP100"], adj_p100, total_points_p100
            )
            db.execute(
                """
                UPDATE room_attempts
                SET score_adjustment_p100 = ?, adjustment_note = ?,
                    auto_score_p100 = ?, manual_score_p100 = ?,
                    total_score_p100 = ?, grading_status = ?
                WHERE id = ?
                """,
                (
                    adj_p100,
                    clean_note,
                    summary["autoScoreP100"],
                    summary["manualScoreP100"],
                    total_score,
                    summary["gradingStatus"],
                    attempt_id,
                ),
            )

        return {
            "attemptId": attempt_id,
            "autoScoreP100": summary["autoScoreP100"],
            "manualScoreP100": summary["manualScoreP100"],
            "scoreAdjustmentP100": adj_p100,
            "adjustmentNote": clean_note,
            "totalScoreP100": total_score,
            "totalPointsP100": total_points_p100,
            "gradingStatus": summary["gradingStatus"],
            "ungradedEssayCount": summary["ungradedEssayCount"],
            "isProvisionalScore": summary["isProvisionalScore"],
            "chosenTrack": summary["chosenTrack"],
            "trackScores": summary["trackScores"],
        }

    @app.post("/api/rooms/{room_id}/regrade")
    def regrade_room(
        room_id: str,
        body: RegradeRoomRequest,
        request: Request,
    ) -> dict[str, Any]:
        """Cập nhật khóa đáp án/điểm câu trong phòng và chấm lại mọi bài đã nộp."""
        owner_id = _require_owner(request)
        now_ms = _now_ms(clock)
        updates_by_qid = {item.questionId: item for item in body.questions}
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            snap = json.loads(room_row[23])
            orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
            q_by_id = {str(q.get("id")): q for q in orig_questions}
            for qid, upd in updates_by_qid.items():
                target_q = q_by_id.get(qid)
                if target_q is None:
                    raise HTTPException(404, f"Không tìm thấy câu hỏi '{qid}' trong phòng thi.")
                qtype = _normalize_qtype(target_q.get("type"))
                if upd.points is not None:
                    p100 = _to_p100(upd.points)
                    if p100 is None:
                        raise HTTPException(422, f"Điểm câu '{qid}' không hợp lệ.")
                    target_q["points"] = upd.points
                    target_q["_maxPointsP100"] = p100
                if qtype == "mcq" and upd.answer is not None:
                    opts_len = len(target_q.get("options") or [])
                    idx_val: int | None = None
                    if isinstance(upd.answer, int) and not isinstance(upd.answer, bool):
                        idx_val = upd.answer
                    elif isinstance(upd.answer, str):
                        clean = upd.answer.strip().upper()
                        if len(clean) == 1 and "A" <= clean <= "Z":
                            idx_val = ord(clean) - 65
                    if idx_val is None or not 0 <= idx_val < max(4, opts_len):
                        raise HTTPException(422, f"Đáp án câu '{qid}' không hợp lệ.")
                    target_q["answer"] = idx_val
                    target_q["answerKnown"] = True
                elif qtype == "truefalse" and upd.truthValues is not None:
                    if len(upd.truthValues) != 4:
                        raise HTTPException(422, f"Đáp án Đúng/Sai câu '{qid}' phải đủ 4 ý.")
                    target_q["truthValues"] = [bool(v) for v in upd.truthValues]
                    target_q["answerKnown"] = True
                elif qtype == "short" and upd.answerText is not None:
                    clean_txt = unicodedata.normalize("NFC", upd.answerText).strip()
                    if not clean_txt:
                        raise HTTPException(
                            422, f"Đáp án câu trả lời ngắn '{qid}' không được trống."
                        )
                    target_q["answerText"] = clean_txt
                    target_q["answerKnown"] = True

            new_snap, new_total_points_p100 = _snapshot_exam_for_room(snap)
            new_snap_json = json.dumps(new_snap, ensure_ascii=False, allow_nan=False)
            db.execute(
                """
                UPDATE exam_rooms
                SET teacher_snapshot_json = ?, total_points_p100 = ?, updated_at = ?
                WHERE id = ? AND owner_id = ?
                """,
                (new_snap_json, new_total_points_p100, now_ms, room_id, owner_id),
            )

            all_attempts = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE room_id = ?",
                (room_id,),
            ).fetchall()
            regraded_count = 0
            for att_row in all_attempts:
                aid = str(att_row[0])
                for q in new_snap.get("questions") or []:
                    qid = str(q["id"])
                    new_max_p100 = int(q.get("_maxPointsP100", _question_points_p100(q)))
                    db.execute(
                        "UPDATE attempt_answers SET max_points_p100 = ? "
                        "WHERE attempt_id = ? AND question_id = ?",
                        (new_max_p100, aid, qid),
                    )
                if att_row[10] != "in_progress":
                    dmap = json.loads(att_row[9])
                    auto_s, manual_s, total_s, g_status = _grade_attempt_tx(
                        db, aid, new_snap, dmap, now_ms
                    )
                    adj_p100 = (
                        int(att_row[21]) if len(att_row) > 21 and att_row[21] is not None else 0
                    )
                    final_total = _apply_score_adjustment(total_s, adj_p100, new_total_points_p100)
                    db.execute(
                        """
                        UPDATE room_attempts
                        SET auto_score_p100 = ?, manual_score_p100 = ?,
                            total_score_p100 = ?, grading_status = ?
                        WHERE id = ?
                        """,
                        (auto_s, manual_s, final_total, g_status, aid),
                    )
                    regraded_count += 1

            refreshed_room = _load_owned_room(db, room_id, owner_id)
            attempt_count, needs_manual_count = _room_attempt_counts(db, room_id)

        return {
            "room": _room_to_dict(
                refreshed_room,
                base_url=str(request.base_url),
                attempt_count=attempt_count,
                needs_manual_count=needs_manual_count,
            ),
            "regradedCount": regraded_count,
        }

    @app.post("/api/rooms/{room_id}/attempts/{attempt_id}/lock")
    def lock_attempt(
        room_id: str,
        attempt_id: str,
        request: Request,
        body: LockAttemptRequest | None = None,
    ) -> dict[str, Any]:
        owner_id = _require_owner(request)
        now_ms = _now_ms(clock)
        reason = (body.reason if body else "teacher_lock") or "teacher_lock"
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            attempt_row = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE id = ? AND room_id = ?",
                (attempt_id, room_id),
            ).fetchone()
            if not attempt_row:
                raise HTTPException(404, "Không tìm thấy lượt làm bài.")
            if attempt_row[10] == "in_progress":
                snap = json.loads(room_row[23])
                dmap = json.loads(attempt_row[9])
                auto_s, manual_s, total_s, g_status = _grade_attempt_tx(
                    db, attempt_id, snap, dmap, now_ms
                )
                adj_p100 = (
                    int(attempt_row[21])
                    if len(attempt_row) > 21 and attempt_row[21] is not None
                    else 0
                )
                total_s = _apply_score_adjustment(total_s, adj_p100, int(room_row[24]))
                db.execute(
                    """
                    UPDATE room_attempts
                    SET status = 'locked', submitted_at = ?, auto_score_p100 = ?,
                        manual_score_p100 = ?, total_score_p100 = ?, grading_status = ?
                    WHERE id = ?
                    """,
                    (now_ms, auto_s, manual_s, total_s, g_status, attempt_id),
                )
                db.execute(
                    "INSERT INTO attempt_events (attempt_id, event_type, detail_json, created_at) "
                    "VALUES (?, 'auto_lock', ?, ?)",
                    (attempt_id, json.dumps({"reason": reason}, ensure_ascii=False), now_ms),
                )
            else:
                db.execute(
                    "UPDATE room_attempts SET status = 'locked' WHERE id = ?",
                    (attempt_id,),
                )
                db.execute(
                    "INSERT INTO attempt_events (attempt_id, event_type, detail_json, created_at) "
                    "VALUES (?, 'auto_lock', ?, ?)",
                    (attempt_id, json.dumps({"reason": reason}, ensure_ascii=False), now_ms),
                )
            refreshed = db.execute(
                "SELECT id, room_id, student_name, student_code, student_class, attempt_no, "
                "variant_offset, variant_code, status, started_at, expires_at, submitted_at, "
                "auto_score_p100, manual_score_p100, total_score_p100, grading_status, "
                "tab_switch_count, fullscreen_exit_count, last_heartbeat_at, "
                "score_adjustment_p100, adjustment_note "
                "FROM room_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            assert refreshed is not None
        return {"attempt": _attempt_summary_dict(refreshed, int(room_row[24]))}

    @app.get("/api/rooms/{room_id}/analytics")
    def get_room_analytics(room_id: str, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        with connect() as db:
            room_row = _load_owned_room(db, room_id, owner_id)
            data = _room_analytics_data(db, room_row)
        data.pop("attempts", None)
        return data

    @app.get("/api/rooms/{room_id}/export.xlsx")
    def export_room_xlsx(room_id: str, request: Request) -> Response:
        owner_id = _require_owner(request)
        with connect() as db:
            room_row = _load_owned_room(db, room_id, owner_id)
            data = _room_analytics_data(db, room_row)
            dmap_rows = db.execute(
                "SELECT id, delivery_map_json FROM room_attempts WHERE room_id = ?",
                (room_id,),
            ).fetchall()
            detail_ans_rows = db.execute(
                """
                SELECT ans.attempt_id, ans.question_id, ans.question_type,
                       ans.max_points_p100, ans.response_json, ans.is_auto_graded,
                       ans.earned_points_p100
                FROM attempt_answers ans
                WHERE ans.attempt_id IN (SELECT id FROM room_attempts WHERE room_id = ?)
                """,
                (room_id,),
            ).fetchall()

        snap = json.loads(room_row[23])
        orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
        has_choice_groups = bool(_extract_choice_groups(snap))
        dmap_by_aid = {r[0]: json.loads(r[1] or "{}") for r in dmap_rows}
        ans_by_aid: dict[str, dict[str, tuple[str, int, Any, int, int | None]]] = {}
        for ar in detail_ans_rows:
            ans_by_aid.setdefault(ar[0], {})[ar[1]] = (
                str(ar[2]),
                int(ar[3]),
                json.loads(ar[4]),
                int(ar[5]),
                ar[6],
            )

        room_code = str(room_row[4])
        total_pts_p100 = int(room_row[24])
        max_pts_num = round(total_pts_p100 / 100.0, 2)

        score_rows: list[list[Any]] = [
            [
                "STT",
                "HoTen",
                "MaHS",
                "Lop",
                "LanThi",
                "MaDe",
                "TrangThai",
                "DiemTuDong",
                "DiemTuLuan",
                "DieuChinhTong",
                "GhiChuDieuChinh",
                "DiemTam",
                "TongDiem",
                "ThangDiem",
                "TrangThaiCham",
                "ChuyenTab",
                "ThoatToanManHinh",
                "BatDau",
                "NopBai",
            ]
        ]
        detail_header: list[Any] = ["STT", "HoTen", "MaHS", "Lop", "LanThi", "MaDe"]
        if has_choice_groups:
            detail_header.append("HuongTuChon")
        for q_idx in range(1, len(orig_questions) + 1):
            detail_header.append(f"Cau {q_idx}")
        detail_rows: list[list[Any]] = [detail_header]

        for idx, att in enumerate(data["attempts"], 1):
            (
                aid,
                s_name,
                s_code,
                s_class,
                a_status,
                auto_p100,
                manual_p100,
                total_p100,
                g_status,
                tab_cnt,
                fs_cnt,
                started_at,
                submitted_at,
                v_code,
                att_no,
                adj_p100,
                adj_note,
            ) = att
            is_provisional_row = a_status == "in_progress" or g_status == "needs_manual"
            provisional_cell: Any = (
                round(int(total_p100) / 100.0, 2)
                if a_status != "in_progress" and is_provisional_row
                else ""
            )
            official_cell: Any = "" if is_provisional_row else round(int(total_p100) / 100.0, 2)
            score_rows.append(
                [
                    idx,
                    s_name,
                    s_code,
                    s_class,
                    int(att_no),
                    str(v_code),
                    a_status,
                    round(int(auto_p100) / 100.0, 2),
                    round(int(manual_p100) / 100.0, 2),
                    round(int(adj_p100 or 0) / 100.0, 2),
                    str(adj_note or ""),
                    provisional_cell,
                    official_cell,
                    max_pts_num,
                    g_status,
                    int(tab_cnt),
                    int(fs_cnt),
                    started_at,
                    submitted_at if submitted_at is not None else "",
                ]
            )
            att_ans_map = ans_by_aid.get(aid, {})
            dmap = dmap_by_aid.get(aid, {})
            opt_order_map = dmap.get("optionOrder") or {}
            detail_row: list[Any] = [
                idx,
                s_name,
                s_code,
                s_class,
                int(att_no),
                str(v_code),
            ]
            if has_choice_groups:
                att_sum = _summarize_attempt_scores(orig_questions, att_ans_map)
                detail_row.append(att_sum["chosenTrack"] or "")
            for q in orig_questions:
                qid = str(q["id"])
                resp_val = att_ans_map[qid][2] if qid in att_ans_map else None
                detail_row.append(_format_answer_for_xlsx(q, resp_val, opt_order_map.get(qid)))
            detail_rows.append(detail_row)

        question_rows: list[list[Any]] = [
            [
                "Cau",
                "MaCau",
                "LoaiCau",
                "DiemToiDa",
                "SoLuotLam",
                "SoDung",
                "TyLeDungPct",
                "DiemTrungBinh",
            ]
        ]
        for qs in data["questionStats"]:
            question_rows.append(
                [
                    qs["order"],
                    qs["questionId"],
                    qs["type"],
                    round(qs["maxPointsP100"] / 100.0, 2),
                    qs["attemptCount"],
                    qs["correctCount"],
                    qs["correctRate"],
                    round(qs["avgEarnedP100"] / 100.0, 2),
                ]
            )

        xlsx_bytes = _build_room_export_xlsx(score_rows, question_rows, detail_rows)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="Ket_qua_{room_code}.xlsx"',
                "Cache-Control": "no-store",
            },
        )

    @app.get("/api/rooms/{room_id}/qr.svg")
    def get_room_qr_svg(
        room_id: str,
        request: Request,
        baseUrl: str | None = Query(default=None, max_length=300),
    ) -> Response:
        owner_id = _require_owner(request)
        with connect() as db:
            row = _load_owned_room(db, room_id, owner_id)
        room_code = str(row[4])
        if baseUrl and re.match(r"^https?://[^\s<>]+$", baseUrl.strip(), re.I):
            base = baseUrl.strip().rstrip("/")
        else:
            base = str(request.base_url).rstrip("/")
        join_url = f"{base}/phong-thi/{room_code}"
        svg = _build_qr_svg(join_url)
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    # =========================================================================
    # 2. STUDENT PUBLIC PORTAL & ATTEMPT ENDPOINTS (NO TEACHER COOKIE REQUIRED)
    # =========================================================================

    def _serve_student_html() -> Response:
        html_path = ROOT / "assets" / "exam-room.html"
        if not html_path.is_file():
            raise HTTPException(404, "Trang phòng thi chưa sẵn sàng.")
        return FileResponse(
            html_path,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Robots-Tag": "noindex, nofollow",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/phong-thi")
    def student_portal_root() -> Response:
        return _serve_student_html()

    @app.get("/phong-thi/{room_code}")
    def student_portal_room(room_code: str) -> Response:
        if not PUBLIC_ROOM_CODE_RE.fullmatch(room_code):
            raise HTTPException(404, "Mã phòng thi không hợp lệ.")
        return _serve_student_html()

    @app.get("/api/rooms/public/{room_code}")
    def get_public_room_metadata(room_code: str) -> JSONResponse:
        with connect() as db:
            row = _load_room_by_code(db, room_code)
        return JSONResponse(
            {**_public_room_metadata(row), "serverNow": _now_ms(clock)},
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.post("/api/rooms/public/{room_code}/join", status_code=201)
    def join_room(room_code: str, body: JoinRoomRequest) -> JSONResponse:
        if not body.studentName:
            raise HTTPException(422, "Vui lòng nhập họ và tên thí sinh.")
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_room_by_code(db, room_code)
            room_id = str(room_row[0])
            pin_hash = str(room_row[5] or "")
            pin_salt = str(room_row[6] or "")
            mode = str(room_row[7])
            status = str(room_row[10])
            duration_minutes = int(room_row[12] or 0)
            opens_at = room_row[13]
            deadline_at = room_row[14]
            max_attempts = int(room_row[15] or 1)
            shuffle_q = bool(room_row[16])
            shuffle_o = bool(room_row[17])
            variant_config = json.loads(room_row[18] or "{}")

            if status != "open":
                msg = (
                    "Phòng thi chưa mở." if status == "draft" else "Phòng thi đã đóng hoặc lưu trữ."
                )
                raise HTTPException(403, msg)
            if opens_at is not None and now_ms < opens_at:
                raise HTTPException(403, "Chưa đến giờ mở phòng thi.")
            if deadline_at is not None and now_ms > deadline_at:
                raise HTTPException(403, "Đã hết hạn tham gia phòng thi.")
            if not _verify_pin(body.pin, pin_hash, pin_salt):
                raise HTTPException(403, "Mã PIN phòng thi chưa đúng.")

            if body.studentCode:
                existing_count = int(
                    db.execute(
                        "SELECT COUNT(*) FROM room_attempts "
                        "WHERE room_id = ? AND LOWER(student_code) = LOWER(?)",
                        (room_id, body.studentCode),
                    ).fetchone()[0]
                )
            else:
                existing_count = int(
                    db.execute(
                        "SELECT COUNT(*) FROM room_attempts "
                        "WHERE room_id = ? AND student_code = '' "
                        "AND LOWER(student_name) = LOWER(?) AND LOWER(student_class) = LOWER(?)",
                        (room_id, body.studentName, body.studentClass),
                    ).fetchone()[0]
                )
            if existing_count >= max_attempts:
                raise HTTPException(
                    403,
                    f"Bạn đã sử dụng tối đa {max_attempts} lượt làm bài cho phòng này.",
                )

            total_room_attempts = int(
                db.execute(
                    "SELECT COUNT(*) FROM room_attempts WHERE room_id = ?", (room_id,)
                ).fetchone()[0]
            )
            variant_offset = (total_room_attempts % 6) if (shuffle_q or shuffle_o) else 0
            snap = json.loads(room_row[23])
            redacted_exam, delivery_map, variant_code = _build_student_delivery(
                snap,
                shuffle_questions=shuffle_q,
                shuffle_options=shuffle_o,
                variant_offset=variant_offset,
                variant_config=variant_config,
            )

            attempt_id = str(uuid4())
            attempt_token = secrets.token_urlsafe(32)
            token_hash = _sha256_hex(attempt_token)
            attempt_no = existing_count + 1

            expires_at: int | None = None
            if mode == "exam" or duration_minutes > 0:
                calc_exp = now_ms + max(1, duration_minutes) * 60_000
                expires_at = min(calc_exp, deadline_at) if deadline_at is not None else calc_exp
            elif deadline_at is not None:
                expires_at = deadline_at

            db.execute(
                """
                INSERT INTO room_attempts (
                    id, room_id, token_hash, student_name, student_code, student_class,
                    attempt_no, variant_offset, variant_code, delivery_map_json, status,
                    started_at, expires_at, submitted_at, auto_score_p100, manual_score_p100,
                    total_score_p100, grading_status, tab_switch_count, fullscreen_exit_count,
                    last_heartbeat_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, NULL, 0, 0, 0,
                          'auto_graded', 0, 0, ?)
                """,
                (
                    attempt_id,
                    room_id,
                    token_hash,
                    body.studentName,
                    body.studentCode,
                    body.studentClass,
                    attempt_no,
                    variant_offset,
                    variant_code,
                    json.dumps(delivery_map, ensure_ascii=False),
                    now_ms,
                    expires_at,
                    now_ms,
                ),
            )
            for q in snap.get("questions") or []:
                qid = str(q["id"])
                qtype = _normalize_qtype(q.get("type"))
                max_p100 = int(q.get("_maxPointsP100", _question_points_p100(q)))
                db.execute(
                    """
                    INSERT INTO attempt_answers (
                        attempt_id, question_id, question_type, max_points_p100,
                        response_json, is_auto_graded, earned_points_p100,
                        grader_note, graded_by, graded_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'null', 0, NULL, '', '', NULL, ?)
                    """,
                    (attempt_id, qid, qtype, max_p100, now_ms),
                )

            audio_plays = _attach_audio_play_counts(redacted_exam, {}, attempt_id)

        return JSONResponse(
            {
                "attemptId": attempt_id,
                "attemptToken": attempt_token,
                "attemptNo": attempt_no,
                "variantOffset": variant_offset,
                "variantCode": variant_code,
                "status": "in_progress",
                "startedAt": now_ms,
                "expiresAt": expires_at,
                "serverNow": now_ms,
                "studentName": body.studentName,
                "studentCode": body.studentCode,
                "studentClass": body.studentClass,
                "room": _public_room_metadata(room_row),
                "exam": redacted_exam,
                "answers": {},
                "audioPlays": audio_plays,
            },
            status_code=201,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/api/rooms/public/attempts/{attempt_id}")
    def get_attempt_state(attempt_id: str, request: Request) -> JSONResponse:
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request)
            db.execute(
                "UPDATE room_attempts SET last_heartbeat_at = ? WHERE id = ?",
                (now_ms, attempt_id),
            )
            ans_rows = db.execute(
                "SELECT question_id, response_json FROM attempt_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()
            play_rows = db.execute(
                "SELECT file_id, play_count, max_plays, active_lease_id "
                "FROM attempt_audio_plays WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()

        answers = {r[0]: val for r in ans_rows if (val := json.loads(r[1])) is not None}
        play_map = {r[0]: (int(r[1]), int(r[2]), str(r[3] or "")) for r in play_rows}

        snap = json.loads(room_row[23])
        redacted_exam, _, variant_code = _build_student_delivery(
            snap,
            shuffle_questions=bool(room_row[16]),
            shuffle_options=bool(room_row[17]),
            variant_offset=int(attempt_row[7]),
            variant_config=json.loads(room_row[18] or "{}"),
        )
        audio_plays = _attach_audio_play_counts(redacted_exam, play_map, attempt_id)

        return JSONResponse(
            {
                "attemptId": attempt_row[0],
                "attemptNo": int(attempt_row[6]),
                "variantCode": variant_code,
                "status": attempt_row[10],
                "startedAt": attempt_row[11],
                "expiresAt": attempt_row[12],
                "submittedAt": attempt_row[13],
                "serverNow": now_ms,
                "studentName": attempt_row[3],
                "studentCode": attempt_row[4],
                "studentClass": attempt_row[5],
                "tabSwitchCount": int(attempt_row[18]),
                "fullscreenExitCount": int(attempt_row[19]),
                "room": _public_room_metadata(room_row),
                "exam": redacted_exam,
                "answers": answers,
                "audioPlays": audio_plays,
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.put("/api/rooms/public/attempts/{attempt_id}/answers")
    def save_attempt_answers(
        attempt_id: str, body: SaveAnswersRequest, request: Request
    ) -> JSONResponse:
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request)
            if attempt_row[10] != "in_progress":
                raise HTTPException(
                    409,
                    "Bài làm đã nộp, hết giờ hoặc đã bị khóa; không thể lưu thêm đáp án.",
                )
            if room_row[10] != "open":
                raise HTTPException(409, "Phòng thi đã đóng; không thể lưu thêm đáp án.")

            snap = json.loads(room_row[23])
            q_by_id = {str(q["id"]): q for q in snap.get("questions") or []}
            saved_count = 0
            for qid, raw_val in body.answers.items():
                orig_q = q_by_id.get(qid)
                if orig_q is None:
                    raise HTTPException(422, f"Câu hỏi '{qid}' không thuộc đề thi này.")
                qtype = _normalize_qtype(orig_q.get("type"))
                opt_count = len(orig_q.get("options") or [])
                clean_val = _validate_student_answer_value(qtype, raw_val, opt_count)
                encoded_val = json.dumps(clean_val, ensure_ascii=False, allow_nan=False)
                db.execute(
                    """
                    INSERT INTO attempt_answers (
                        attempt_id, question_id, question_type, max_points_p100,
                        response_json, is_auto_graded, earned_points_p100,
                        grader_note, graded_by, graded_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0, NULL, '', '', NULL, ?)
                    ON CONFLICT(attempt_id, question_id) DO UPDATE SET
                        response_json = excluded.response_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        attempt_id,
                        qid,
                        qtype,
                        int(orig_q.get("_maxPointsP100", _question_points_p100(orig_q))),
                        encoded_val,
                        now_ms,
                    ),
                )
                saved_count += 1
            db.execute(
                "UPDATE room_attempts SET last_heartbeat_at = ? WHERE id = ?",
                (now_ms, attempt_id),
            )
        return JSONResponse(
            {"ok": True, "savedCount": saved_count, "serverNow": now_ms},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/rooms/public/attempts/{attempt_id}/events")
    def record_attempt_event(
        attempt_id: str, body: RecordEventRequest, request: Request
    ) -> JSONResponse:
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request)
            status = str(attempt_row[10])
            tab_count = int(attempt_row[18])
            fs_count = int(attempt_row[19])
            max_tab_switches = int(room_row[22] or 0)

            detail_str = json.dumps(body.detail or {}, ensure_ascii=False, allow_nan=False)[:2000]
            db.execute(
                "INSERT INTO attempt_events (attempt_id, event_type, detail_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (attempt_id, body.eventType, detail_str, now_ms),
            )

            auto_locked = False
            if status == "in_progress":
                if body.eventType in ("tab_hidden", "window_blur"):
                    tab_count += 1
                elif body.eventType == "fullscreen_exit":
                    fs_count += 1

                if max_tab_switches > 0 and tab_count > max_tab_switches:
                    auto_locked = True
                    status = "locked"
                    snap = json.loads(room_row[23])
                    dmap = json.loads(attempt_row[9])
                    auto_s, manual_s, total_s, g_status = _grade_attempt_tx(
                        db, attempt_id, snap, dmap, now_ms
                    )
                    adj_p100 = (
                        int(attempt_row[21])
                        if len(attempt_row) > 21 and attempt_row[21] is not None
                        else 0
                    )
                    total_s = _apply_score_adjustment(total_s, adj_p100, int(room_row[24]))
                    db.execute(
                        """
                        UPDATE room_attempts
                        SET status = 'locked', submitted_at = ?,
                            auto_score_p100 = ?, manual_score_p100 = ?,
                            total_score_p100 = ?, grading_status = ?,
                            tab_switch_count = ?, fullscreen_exit_count = ?,
                            last_heartbeat_at = ?
                        WHERE id = ?
                        """,
                        (
                            now_ms,
                            auto_s,
                            manual_s,
                            total_s,
                            g_status,
                            tab_count,
                            fs_count,
                            now_ms,
                            attempt_id,
                        ),
                    )
                    db.execute(
                        "INSERT INTO attempt_events "
                        "(attempt_id, event_type, detail_json, created_at) "
                        "VALUES (?, 'auto_lock', ?, ?)",
                        (
                            attempt_id,
                            json.dumps(
                                {
                                    "reason": "max_tab_switches_exceeded",
                                    "tabSwitchCount": tab_count,
                                    "maxTabSwitches": max_tab_switches,
                                }
                            ),
                            now_ms,
                        ),
                    )
                else:
                    db.execute(
                        """
                        UPDATE room_attempts
                        SET tab_switch_count = ?, fullscreen_exit_count = ?,
                            last_heartbeat_at = ?
                        WHERE id = ?
                        """,
                        (tab_count, fs_count, now_ms, attempt_id),
                    )
            else:
                db.execute(
                    "UPDATE room_attempts SET last_heartbeat_at = ? WHERE id = ?",
                    (now_ms, attempt_id),
                )

        return JSONResponse(
            {
                "ok": True,
                "status": status,
                "autoLocked": auto_locked,
                "tabSwitchCount": tab_count,
                "maxTabSwitches": max_tab_switches,
                "fullscreenExitCount": fs_count,
                "serverNow": now_ms,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/rooms/public/attempts/{attempt_id}/submit")
    def submit_attempt(
        attempt_id: str,
        request: Request,
        body: SubmitAttemptRequest | None = None,
    ) -> JSONResponse:
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request, auto_expire=False)
            status = str(attempt_row[10])
            expires_at = attempt_row[12]
            snap = json.loads(room_row[23])
            dmap = json.loads(attempt_row[9])

            if status == "in_progress":
                is_expired = expires_at is not None and now_ms > expires_at
                if body and body.answers and not is_expired:
                    q_by_id = {str(q["id"]): q for q in snap.get("questions") or []}
                    for qid, raw_val in body.answers.items():
                        orig_q = q_by_id.get(qid)
                        if orig_q is None:
                            raise HTTPException(422, f"Câu hỏi '{qid}' không thuộc đề thi.")
                        qtype = _normalize_qtype(orig_q.get("type"))
                        clean_val = _validate_student_answer_value(
                            qtype, raw_val, len(orig_q.get("options") or [])
                        )
                        db.execute(
                            """
                            INSERT INTO attempt_answers (
                                attempt_id, question_id, question_type, max_points_p100,
                                response_json, is_auto_graded, earned_points_p100,
                                grader_note, graded_by, graded_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, 0, NULL, '', '', NULL, ?)
                            ON CONFLICT(attempt_id, question_id) DO UPDATE SET
                                response_json = excluded.response_json,
                                updated_at = excluded.updated_at
                            """,
                            (
                                attempt_id,
                                qid,
                                qtype,
                                int(orig_q.get("_maxPointsP100", _question_points_p100(orig_q))),
                                json.dumps(clean_val, ensure_ascii=False, allow_nan=False),
                                now_ms,
                            ),
                        )

                final_status = (
                    "auto_submitted"
                    if (is_expired or (body is not None and body.autoSubmit))
                    else "submitted"
                )
                sub_time = expires_at if (is_expired and expires_at is not None) else now_ms
                auto_s, manual_s, total_s, g_status = _grade_attempt_tx(
                    db, attempt_id, snap, dmap, now_ms
                )
                adj_p100 = (
                    int(attempt_row[21])
                    if len(attempt_row) > 21 and attempt_row[21] is not None
                    else 0
                )
                total_s = _apply_score_adjustment(total_s, adj_p100, int(room_row[24]))
                db.execute(
                    """
                    UPDATE room_attempts
                    SET status = ?, submitted_at = ?, auto_score_p100 = ?,
                        manual_score_p100 = ?, total_score_p100 = ?,
                        grading_status = ?, last_heartbeat_at = ?
                    WHERE id = ?
                    """,
                    (
                        final_status,
                        sub_time,
                        auto_s,
                        manual_s,
                        total_s,
                        g_status,
                        now_ms,
                        attempt_id,
                    ),
                )
                db.execute(
                    "INSERT INTO attempt_events (attempt_id, event_type, detail_json, created_at) "
                    "VALUES (?, 'submit', ?, ?)",
                    (
                        attempt_id,
                        json.dumps({"autoSubmit": final_status == "auto_submitted"}),
                        now_ms,
                    ),
                )
                submitted_at = sub_time
                grading_status = g_status
                status = final_status
            else:
                submitted_at = attempt_row[13]
                grading_status = str(attempt_row[17])

            synced_answer_count = int(
                db.execute(
                    "SELECT COUNT(DISTINCT question_id) FROM attempt_answers "
                    "WHERE attempt_id = ? AND response_json IS NOT NULL "
                    "AND response_json != 'null'",
                    (attempt_id,),
                ).fetchone()[0]
            )
            total_questions = len(snap.get("questions") or [])

        result_policy = str(room_row[19])
        release_after_close = bool(room_row[20])
        room_status = str(room_row[10])
        results_available = result_policy != "hidden" and (
            (not release_after_close) or room_status in ("closed", "archived")
        )
        return JSONResponse(
            {
                "attemptId": attempt_id,
                "status": status,
                "submittedAt": submitted_at,
                "gradingStatus": grading_status,
                "resultPolicy": result_policy,
                "releaseResultsAfterClose": release_after_close,
                "resultsAvailable": results_available,
                "syncedAnswerCount": synced_answer_count,
                "totalQuestions": total_questions,
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/api/rooms/public/attempts/{attempt_id}/result")
    def get_attempt_result(attempt_id: str, request: Request) -> JSONResponse:
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request)
            status = str(attempt_row[10])
            if status == "in_progress":
                raise HTTPException(409, "Bài làm chưa được nộp; hãy nộp bài để xem kết quả.")

            snap = json.loads(room_row[23])
            total_questions = len(snap.get("questions") or [])
            synced_answer_count = int(
                db.execute(
                    "SELECT COUNT(DISTINCT question_id) FROM attempt_answers "
                    "WHERE attempt_id = ? AND response_json IS NOT NULL "
                    "AND response_json != 'null'",
                    (attempt_id,),
                ).fetchone()[0]
            )

            result_policy = str(room_row[19])
            release_after_close = bool(room_row[20])
            room_status = str(room_row[10])
            results_released = (not release_after_close) or (room_status in ("closed", "archived"))

            if not results_released or result_policy == "hidden":
                msg = (
                    "Kết quả sẽ được công bố sau khi giáo viên đóng phòng thi."
                    if (release_after_close and room_status == "open")
                    else "Giáo viên đang ẩn kết quả cho phòng thi này."
                )
                return JSONResponse(
                    {
                        "attemptId": attempt_id,
                        "status": status,
                        "submittedAt": attempt_row[13],
                        "gradingStatus": attempt_row[17],
                        "resultPolicy": result_policy,
                        "releaseResultsAfterClose": release_after_close,
                        "resultsAvailable": False,
                        "message": msg,
                        "syncedAnswerCount": synced_answer_count,
                        "totalQuestions": total_questions,
                    },
                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
                )

            ans_rows = db.execute(
                "SELECT question_id, question_type, max_points_p100, response_json, "
                "is_auto_graded, earned_points_p100, grader_note "
                "FROM attempt_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()

        orig_questions = [q for q in (snap.get("questions") or []) if isinstance(q, dict)]
        ans_data_map = {
            r[0]: (str(r[1]), int(r[2]), json.loads(r[3]), int(r[4]), r[5]) for r in ans_rows
        }
        summary = _summarize_attempt_scores(orig_questions, ans_data_map)
        ungraded_essay_count = int(summary["ungradedEssayCount"])
        is_provisional = bool(attempt_row[17] == "needs_manual" or ungraded_essay_count > 0)

        question_results: list[dict[str, Any]] = []
        if result_policy != "score_only":
            ans_by_qid = {r[0]: r for r in ans_rows}
            dmap = json.loads(attempt_row[9])
            q_order = dmap.get("questionOrder") or [str(q["id"]) for q in orig_questions]
            option_order_map = dmap.get("optionOrder") or {}
            orig_by_id = {str(q["id"]): q for q in orig_questions}

            for idx, qid in enumerate(q_order, 1):
                orig_q = orig_by_id.get(qid)
                if orig_q is None:
                    continue
                qtype = _normalize_qtype(orig_q.get("type"))
                a_row = ans_by_qid.get(qid)
                max_p100 = (
                    int(a_row[2])
                    if a_row is not None
                    else int(orig_q.get("_maxPointsP100", _question_points_p100(orig_q)))
                )
                student_resp = json.loads(a_row[3]) if a_row is not None else None
                earned_p100 = a_row[5] if a_row is not None else None
                grader_note = a_row[6] if a_row is not None else ""

                item: dict[str, Any] = {
                    "order": idx,
                    "questionId": qid,
                    "type": qtype,
                    "maxPointsP100": max_p100,
                    "earnedPointsP100": earned_p100,
                    "studentResponse": student_resp,
                }
                q_grp = _question_choice_group(orig_q)
                if q_grp:
                    item["choiceGroup"] = q_grp

                if result_policy in ("score_and_answers", "full_explanation"):
                    item["stem"] = str(orig_q.get("stem") or "")
                    opt_order = option_order_map.get(qid)
                    orig_opts = orig_q.get("options") or []
                    if qtype == "mcq" and opt_order and len(opt_order) == len(orig_opts):
                        item["options"] = [orig_opts[o_idx] for o_idx in opt_order]
                        orig_ans = _parse_mcq_answer(orig_q)
                        item["correctAnswer"] = (
                            opt_order.index(orig_ans)
                            if orig_ans is not None and orig_ans in opt_order
                            else orig_ans
                        )
                    elif qtype == "mcq":
                        item["options"] = orig_opts
                        item["correctAnswer"] = _parse_mcq_answer(orig_q)
                    elif qtype == "truefalse":
                        item["options"] = orig_opts
                        tf = _parse_truefalse_key(orig_q)
                        item["correctAnswer"] = list(tf) if tf is not None else None
                    elif qtype == "short":
                        item["correctAnswer"] = (
                            orig_q.get("answerText") or orig_q.get("answer") or saved_answer(orig_q)
                        )
                    else:
                        item["correctAnswer"] = None

                if result_policy == "full_explanation":
                    item["explanation"] = str(orig_q.get("explanation") or "")
                    item["rubric"] = orig_q.get("rubric") or []
                    item["graderNote"] = grader_note

                question_results.append(item)

        adj_p100 = (
            int(attempt_row[21]) if len(attempt_row) > 21 and attempt_row[21] is not None else 0
        )
        adj_note = str(attempt_row[22] or "") if len(attempt_row) > 22 else ""
        return JSONResponse(
            {
                "attemptId": attempt_id,
                "studentName": attempt_row[3],
                "studentCode": attempt_row[4],
                "studentClass": attempt_row[5],
                "attemptNo": int(attempt_row[6]),
                "variantCode": attempt_row[8],
                "status": status,
                "startedAt": attempt_row[11],
                "submittedAt": attempt_row[13],
                "serverNow": now_ms,
                "gradingStatus": attempt_row[17],
                "ungradedEssayCount": ungraded_essay_count,
                "isProvisionalScore": is_provisional,
                "chosenTrack": summary["chosenTrack"],
                "trackScores": summary["trackScores"],
                "resultPolicy": result_policy,
                "releaseResultsAfterClose": release_after_close,
                "resultsAvailable": True,
                "autoScoreP100": int(attempt_row[14]),
                "manualScoreP100": int(attempt_row[15]),
                "scoreAdjustmentP100": adj_p100,
                "adjustmentNote": adj_note,
                "totalScoreP100": int(attempt_row[16]),
                "totalPointsP100": int(room_row[24]),
                "syncedAnswerCount": synced_answer_count,
                "totalQuestions": total_questions,
                "questions": question_results,
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/api/rooms/public/attempts/{attempt_id}/audio/{file_id}")
    def stream_attempt_audio(
        attempt_id: str,
        file_id: str,
        request: Request,
        lease: bool = Query(default=False),
        leaseId: str | None = Query(default=None),
    ) -> Response:
        now_ms = _now_ms(clock)
        use_lease = bool(lease or (leaseId is not None and leaseId.strip()))
        with connect() as db:
            _begin_immediate(db)
            attempt_row, room_row = _require_attempt(db, attempt_id, request)
            if attempt_row[10] != "in_progress":
                raise HTTPException(409, "Bài làm đã kết thúc; không thể phát thêm âm thanh.")
            snap = json.loads(room_row[23])
            audio_map = _collect_audio_entries(snap)
            audio_meta = audio_map.get(file_id)
            if audio_meta is None:
                raise HTTPException(404, "Tệp âm thanh không thuộc phòng thi này.")

            max_plays = max(1, int(audio_meta.get("maxPlays") or 2))
            play_row = db.execute(
                "SELECT play_count, active_lease_id FROM attempt_audio_plays "
                "WHERE attempt_id = ? AND file_id = ?",
                (attempt_id, file_id),
            ).fetchone()
            current_plays = int(play_row[0]) if play_row is not None else 0
            existing_lease = str(play_row[1] or "") if play_row is not None else ""
            if current_plays >= max_plays:
                raise HTTPException(
                    403, f"Bạn đã nghe tối đa {max_plays} lượt cho tệp âm thanh này."
                )

            resolved = _resolve_audio_payload(
                db=db,
                owner_id=str(room_row[1]),
                file_id=file_id,
                audio_meta=audio_meta,
                read_file_bytes=read_file_bytes,
            )
            if resolved is None:
                raise HTTPException(404, "Không tìm thấy dữ liệu âm thanh trên máy chủ.")
            audio_bytes, mime_type = resolved

            active_lease_id = ""
            if use_lease:
                active_lease_id = existing_lease or secrets.token_hex(12)
                if play_row is None:
                    db.execute(
                        """
                        INSERT INTO attempt_audio_plays (
                            attempt_id, file_id, play_count, max_plays,
                            last_played_at, active_lease_id, active_lease_at
                        ) VALUES (?, ?, 0, ?, ?, ?, ?)
                        """,
                        (attempt_id, file_id, max_plays, now_ms, active_lease_id, now_ms),
                    )
                else:
                    db.execute(
                        """
                        UPDATE attempt_audio_plays
                        SET active_lease_id = ?, active_lease_at = ?
                        WHERE attempt_id = ? AND file_id = ?
                        """,
                        (active_lease_id, now_ms, attempt_id, file_id),
                    )
                reported_used = current_plays + 1
                reported_remaining = max(0, max_plays - reported_used)
            else:
                if play_row is None:
                    db.execute(
                        """
                        INSERT INTO attempt_audio_plays (
                            attempt_id, file_id, play_count, max_plays,
                            last_played_at, active_lease_id, active_lease_at
                        ) VALUES (?, ?, 1, ?, ?, '', 0)
                        """,
                        (attempt_id, file_id, max_plays, now_ms),
                    )
                    reported_used = 1
                else:
                    updated = db.execute(
                        """
                        UPDATE attempt_audio_plays
                        SET play_count = play_count + 1, last_played_at = ?,
                            active_lease_id = '', active_lease_at = 0
                        WHERE attempt_id = ? AND file_id = ? AND play_count < max_plays
                        """,
                        (now_ms, attempt_id, file_id),
                    )
                    if updated.rowcount == 0:
                        raise HTTPException(
                            403, f"Bạn đã nghe tối đa {max_plays} lượt cho tệp âm thanh này."
                        )
                    reported_used = current_plays + 1
                reported_remaining = max(0, max_plays - reported_used)

        headers = {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Audio-Plays-Used": str(reported_used),
            "X-Audio-Plays-Remaining": str(reported_remaining),
            "X-Audio-Max-Plays": str(max_plays),
        }
        if active_lease_id:
            headers["X-Audio-Lease-Id"] = active_lease_id
        return Response(content=audio_bytes, media_type=mime_type, headers=headers)

    @app.post("/api/rooms/public/attempts/{attempt_id}/audio/{file_id}/ack")
    def ack_attempt_audio(
        attempt_id: str,
        file_id: str,
        body: AckAudioPlayRequest,
        request: Request,
    ) -> JSONResponse:
        """Xác nhận học sinh đã nhận đủ tệp và bắt đầu phát thật để trừ 1 lượt nghe."""
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            _attempt_row, room_row = _require_attempt(db, attempt_id, request, auto_expire=False)
            snap = json.loads(room_row[23])
            audio_map = _collect_audio_entries(snap)
            audio_meta = audio_map.get(file_id)
            if audio_meta is None:
                raise HTTPException(404, "Tệp âm thanh không thuộc phòng thi này.")
            max_plays = max(1, int(audio_meta.get("maxPlays") or 2))
            play_row = db.execute(
                "SELECT play_count, max_plays, active_lease_id FROM attempt_audio_plays "
                "WHERE attempt_id = ? AND file_id = ?",
                (attempt_id, file_id),
            ).fetchone()
            if play_row is None:
                raise HTTPException(404, "Chưa cấp lượt phát nào cho tệp âm thanh này.")
            current_plays = int(play_row[0])
            row_max = max(1, int(play_row[1] or max_plays))
            active_lease = str(play_row[2] or "")
            if active_lease and hmac.compare_digest(active_lease, body.leaseId.strip()):
                new_count = min(row_max, current_plays + 1)
                db.execute(
                    """
                    UPDATE attempt_audio_plays
                    SET play_count = ?, last_played_at = ?,
                        active_lease_id = '', active_lease_at = 0
                    WHERE attempt_id = ? AND file_id = ?
                    """,
                    (new_count, now_ms, attempt_id, file_id),
                )
            elif not active_lease:
                new_count = current_plays
            else:
                raise HTTPException(409, "Mã lượt phát không khớp với phiên đang chờ xác nhận.")

        remaining = max(0, row_max - new_count)
        return JSONResponse(
            {
                "fileId": file_id,
                "playsUsed": new_count,
                "playsRemaining": remaining,
                "maxPlays": row_max,
                "acknowledged": True,
            },
            headers={"Cache-Control": "no-store"},
        )
