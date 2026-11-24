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
from collections.abc import Callable
from contextlib import AbstractContextManager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
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
    total_p100 = 0
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
        total_p100 += p100
        questions.append(q)
    snap["questions"] = questions

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
            sig = (_normalize_qtype(q.get("type")), uses_table(q), q.get("sectionId"))
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
    exam: dict[str, Any], play_map: dict[str, tuple[int, int]], attempt_id: str
) -> dict[str, dict[str, int]]:
    audio_summary: dict[str, dict[str, int]] = {}

    def enrich(aud: Any) -> None:
        if not isinstance(aud, dict):
            return
        fid = str(aud.get("fileId") or "").strip()
        if not fid:
            return
        default_max = int(aud.get("maxPlays") or 2)
        used, max_p = play_map.get(fid, (0, default_max))
        rem = max(0, max_p - used)
        aud["playsUsed"] = used
        aud["playsRemaining"] = rem
        aud["maxPlays"] = max_p
        aud["url"] = f"/api/rooms/public/attempts/{attempt_id}/audio/{fid}"
        audio_summary[fid] = {"playsUsed": used, "playsRemaining": rem, "maxPlays": max_p}

    for q in exam.get("questions") or []:
        if isinstance(q, dict):
            enrich(q.get("audio"))
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


def _parse_short_decimal(text: str) -> Decimal | None:
    compact = text.replace(" ", "").replace(",", ".")
    if not compact:
        return None
    try:
        dec = Decimal(compact)
    except (InvalidOperation, ValueError):
        return None
    if not dec.is_finite():
        return None
    return dec


def _normalize_short_raw(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip().replace("\u2212", "-")


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

    s_dec = _parse_short_decimal(s_norm)
    s_text = " ".join(s_norm.split()).casefold()

    for cand in candidates:
        k_norm = _normalize_short_raw(cand)
        k_dec = _parse_short_decimal(k_norm)
        if s_dec is not None and k_dec is not None:
            if s_dec == k_dec:
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


def _grade_attempt_tx(
    db: sqlite3.Connection,
    attempt_id: str,
    exam_snapshot: dict[str, Any],
    delivery_map: dict[str, Any],
    now_ms: int,
) -> tuple[int, int, int, str]:
    """Chấm toàn bộ phần tự động của một lượt thi trong giao dịch SQLite."""
    orig_by_id = {str(q["id"]): q for q in exam_snapshot.get("questions") or []}
    option_order_map = delivery_map.get("optionOrder") or {}

    existing_rows = db.execute(
        "SELECT question_id, question_type, max_points_p100, response_json, "
        "is_auto_graded, earned_points_p100 FROM attempt_answers WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchall()
    existing_by_qid = {row[0]: row for row in existing_rows}

    auto_score = 0
    manual_score = 0
    has_ungraded_essay = False
    has_any_essay = False

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
            has_any_essay = True
            if existing_earned is None:
                has_ungraded_essay = True
            else:
                manual_score += int(existing_earned)
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
            continue

        is_auto, earned = grade_question_response(
            orig_q, response_val, max_p100, option_order_map.get(qid)
        )
        auto_score += int(earned or 0)
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

    total_score = auto_score + manual_score
    if has_ungraded_essay:
        grading_status = "needs_manual"
    elif has_any_essay:
        grading_status = "graded"
    else:
        grading_status = "auto_graded"

    return auto_score, manual_score, total_score, grading_status


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
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(str(val))}</t></is></c>'
                )
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )


def _build_room_export_xlsx(score_rows: list[list[Any]], question_rows: list[list[Any]]) -> bytes:
    """Dựng tệp XLSX 2 sheet ('BangDiem' và 'ThongKeCauHoi') thuần Python stdlib."""
    sheet1_xml = _build_sheet_xml(score_rows)
    sheet2_xml = _build_sheet_xml(question_rows)

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        '<sheet name="BangDiem" sheetId="1" r:id="rId1"/>'
        '<sheet name="ThongKeCauHoi" sheetId="2" r:id="rId2"/>'
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
        "joinPath": join_path,
        "joinUrl": (clean_base + join_path) if clean_base else join_path,
        "lanUrls": _local_lan_urls(join_path, base_url=clean_base) if allow_lan else [],
        "attemptCount": attempt_count,
        "needsManualCount": needs_manual_count,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


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
    ) = row
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
        "totalScoreP100": total_score_p100,
        "totalPointsP100": total_points_p100,
        "gradingStatus": grading_status,
        "tabSwitchCount": tab_switch_count,
        "fullscreenExitCount": fullscreen_exit_count,
        "lastHeartbeatAt": last_heartbeat_at,
    }


_ATTEMPT_PUBLIC_COLS = (
    "id, room_id, token_hash, student_name, student_code, student_class, "
    "attempt_no, variant_offset, variant_code, delivery_map_json, status, "
    "started_at, expires_at, submitted_at, auto_score_p100, manual_score_p100, "
    "total_score_p100, grading_status, tab_switch_count, fullscreen_exit_count, last_heartbeat_at"
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
                   started_at, submitted_at, variant_code, attempt_no
            FROM room_attempts
            WHERE room_id = ?
            ORDER BY started_at ASC
            """,
            (room_id,),
        ).fetchall()

        finalized = [a for a in attempts if a[4] != "in_progress"]
        scores = [int(a[7]) for a in finalized]
        in_progress_count = sum(1 for a in attempts if a[4] == "in_progress")
        locked_count = sum(1 for a in attempts if a[4] == "locked")
        needs_manual_count = sum(1 for a in finalized if a[8] == "needs_manual")
        graded_count = sum(1 for a in finalized if a[8] in ("auto_graded", "graded"))

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
            max_p100 = int(q.get("_maxPointsP100", _question_points_p100(q)))
            q_entries = answers_by_qid.get(qid, [])
            graded_entries = [e for e in q_entries if e[2] is not None]
            correct_cnt = sum(1 for e in graded_entries if e[2] == max_p100 and max_p100 > 0)
            partial_cnt = sum(1 for e in graded_entries if e[2] is not None and 0 < e[2] < max_p100)
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
                    "stem": str(q.get("stem") or "")[:160],
                    "maxPointsP100": max_p100,
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
                )
                attempts_out.append(_attempt_summary_dict(summary_tuple, int(room_row[24])))

        room_dict = _room_to_dict(
            room_row,
            base_url=str(request.base_url),
            attempt_count=len(attempts_out),
            needs_manual_count=needs_manual,
        )
        return {"room": room_dict, "attempts": attempts_out, "serverNow": now_ms}

    @app.patch("/api/rooms/{room_id}")
    def update_room(room_id: str, body: UpdateRoomRequest, request: Request) -> dict[str, Any]:
        owner_id = _require_owner(request)
        now_ms = _now_ms(clock)
        with connect() as db:
            _begin_immediate(db)
            row = _load_owned_room(db, room_id, owner_id)
            updates: dict[str, Any] = {"updated_at": now_ms}
            if body.status is not None:
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
        return {"room": _room_to_dict(refreshed, base_url=str(request.base_url))}

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
        with connect() as db:
            _begin_immediate(db)
            room_row = _load_owned_room(db, room_id, owner_id)
            snap = json.loads(room_row[23])
            now_ms = _now_ms(clock)
            raw_attempts = db.execute(
                f"SELECT {_ATTEMPT_PUBLIC_COLS} FROM room_attempts WHERE room_id = ?",
                (room_id,),
            ).fetchall()
            for raw_a in raw_attempts:
                _expire_attempt_if_needed(db, raw_a, room_row, now_ms)

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

        q_map = {str(q["id"]): (idx, q) for idx, q in enumerate(snap.get("questions") or [], 1)}
        items: list[dict[str, Any]] = []
        pending_count = 0
        graded_count = 0
        for r in rows:
            is_graded = r[11] is not None
            if is_graded:
                graded_count += 1
            else:
                pending_count += 1
            if not includeGraded and is_graded:
                continue
            q_num, q_obj = q_map.get(r[8], (0, {}))
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
        return {
            "roomId": room_id,
            "pendingCount": pending_count,
            "gradedCount": graded_count,
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

            agg = db.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN is_auto_graded = 1 THEN COALESCE(earned_points_p100, 0)
                                      ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN is_auto_graded = 0 THEN COALESCE(earned_points_p100, 0)
                                      ELSE 0 END), 0),
                    SUM(CASE WHEN question_type = 'essay' AND earned_points_p100 IS NULL
                             THEN 1 ELSE 0 END),
                    SUM(CASE WHEN question_type = 'essay' THEN 1 ELSE 0 END)
                FROM attempt_answers
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
            assert agg is not None
            auto_score = int(agg[0] or 0)
            manual_score = int(agg[1] or 0)
            ungraded_essays = int(agg[2] or 0)
            total_essays = int(agg[3] or 0)
            total_score = auto_score + manual_score
            grading_status = (
                "needs_manual"
                if ungraded_essays > 0
                else ("graded" if total_essays > 0 else "auto_graded")
            )

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
            "totalScoreP100": total_score,
            "totalPointsP100": int(room_row[24]),
            "gradingStatus": grading_status,
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
                "tab_switch_count, fullscreen_exit_count, last_heartbeat_at "
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
                "TongDiem",
                "ThangDiem",
                "TrangThaiCham",
                "ChuyenTab",
                "ThoatToanManHinh",
                "BatDau",
                "NopBai",
            ]
        ]
        for idx, att in enumerate(data["attempts"], 1):
            (
                _aid,
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
            ) = att
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
                    round(int(total_p100) / 100.0, 2),
                    max_pts_num,
                    g_status,
                    int(tab_cnt),
                    int(fs_cnt),
                    started_at,
                    submitted_at if submitted_at is not None else "",
                ]
            )

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

        xlsx_bytes = _build_room_export_xlsx(score_rows, question_rows)
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
                "SELECT file_id, play_count, max_plays FROM attempt_audio_plays "
                "WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()

        answers = {r[0]: val for r in ans_rows if (val := json.loads(r[1])) is not None}
        play_map = {r[0]: (int(r[1]), int(r[2])) for r in play_rows}

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
                    },
                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
                )

            ans_rows = db.execute(
                "SELECT question_id, question_type, max_points_p100, response_json, "
                "is_auto_graded, earned_points_p100, grader_note "
                "FROM attempt_answers WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchall()

        ans_by_qid = {r[0]: r for r in ans_rows}
        snap = json.loads(room_row[23])
        dmap = json.loads(attempt_row[9])
        q_order = dmap.get("questionOrder") or [str(q["id"]) for q in snap.get("questions") or []]
        option_order_map = dmap.get("optionOrder") or {}
        orig_by_id = {str(q["id"]): q for q in snap.get("questions") or []}

        question_results: list[dict[str, Any]] = []
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
                "resultPolicy": result_policy,
                "releaseResultsAfterClose": release_after_close,
                "resultsAvailable": True,
                "autoScoreP100": int(attempt_row[14]),
                "manualScoreP100": int(attempt_row[15]),
                "totalScoreP100": int(attempt_row[16]),
                "totalPointsP100": int(room_row[24]),
                "questions": question_results,
            },
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    @app.get("/api/rooms/public/attempts/{attempt_id}/audio/{file_id}")
    def stream_attempt_audio(attempt_id: str, file_id: str, request: Request) -> Response:
        now_ms = _now_ms(clock)
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
                "SELECT play_count FROM attempt_audio_plays WHERE attempt_id = ? AND file_id = ?",
                (attempt_id, file_id),
            ).fetchone()
            current_plays = int(play_row[0]) if play_row is not None else 0
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

            if play_row is None:
                db.execute(
                    """
                    INSERT INTO attempt_audio_plays (
                        attempt_id, file_id, play_count, max_plays, last_played_at
                    ) VALUES (?, ?, 1, ?, ?)
                    """,
                    (attempt_id, file_id, max_plays, now_ms),
                )
                new_count = 1
            else:
                updated = db.execute(
                    """
                    UPDATE attempt_audio_plays
                    SET play_count = play_count + 1, last_played_at = ?
                    WHERE attempt_id = ? AND file_id = ? AND play_count < max_plays
                    """,
                    (now_ms, attempt_id, file_id),
                )
                if updated.rowcount == 0:
                    raise HTTPException(
                        403, f"Bạn đã nghe tối đa {max_plays} lượt cho tệp âm thanh này."
                    )
                new_count = current_plays + 1

        remaining = max(0, max_plays - new_count)
        return Response(
            content=audio_bytes,
            media_type=mime_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Audio-Plays-Used": str(new_count),
                "X-Audio-Plays-Remaining": str(remaining),
                "X-Audio-Max-Plays": str(max_plays),
            },
        )
