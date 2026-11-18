"""Đặc tả thực thi DDL 15 bảng, migration 5 pha và hợp đồng giao dịch BE-3."""

import argparse
import base64
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

SCHEMA_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_configs (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    rev INTEGER NOT NULL DEFAULT 1,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    name TEXT NOT NULL,
    salt TEXT,
    password_hash TEXT,
    is_local_owner INTEGER NOT NULL DEFAULT 0 CHECK (is_local_owner IN (0, 1)),
    workspace_version INTEGER NOT NULL DEFAULT 1,
    current_exam_id TEXT,
    seen_ai_jobs TEXT NOT NULL DEFAULT '[]',
    workspace_revision INTEGER NOT NULL DEFAULT 0 CHECK (workspace_revision >= 0),
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1)),
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_accounts (
    owner_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 1000 CHECK (balance >= 0),
    label TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledgers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL REFERENCES credit_accounts(owner_id) ON DELETE CASCADE,
    seq_index INTEGER NOT NULL,
    delta INTEGER NOT NULL,
    reason TEXT NOT NULL,
    reference TEXT,
    created_at INTEGER NOT NULL,
    UNIQUE (owner_id, seq_index)
);

CREATE TABLE IF NOT EXISTS teacher_preferences (
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    kind TEXT NOT NULL,
    content_text TEXT NOT NULL,
    max_words INTEGER,
    confirmed_at INTEGER NOT NULL,
    PRIMARY KEY (owner_id, id)
);

CREATE TABLE IF NOT EXISTS source_documents (
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pdf', 'slides', 'text', 'image')),
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size > 0 AND byte_size <= 20971520),
    sha256_hash TEXT NOT NULL,
    blob_rel_path TEXT NOT NULL,
    is_orphan INTEGER NOT NULL DEFAULT 0 CHECK (is_orphan IN (0, 1)),
    rev INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (owner_id, id)
);

CREATE TABLE IF NOT EXISTS exams (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    grade TEXT NOT NULL,
    minutes INTEGER NOT NULL CHECK (minutes > 0),
    department TEXT NOT NULL DEFAULT '',
    school TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    marking_guidance TEXT NOT NULL DEFAULT '',
    draft_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (draft_status IN ('draft', 'ready', 'finalized', 'archived')),
    is_sample INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0, 1)),
    is_full_exam INTEGER NOT NULL DEFAULT 0 CHECK (is_full_exam IN (0, 1)),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    block_ids TEXT NOT NULL,
    layout_config TEXT NOT NULL,
    data_table TEXT NOT NULL DEFAULT '[]',
    matrix_spec TEXT NOT NULL DEFAULT '[]',
    matrix_confirmed INTEGER NOT NULL DEFAULT 0 CHECK (matrix_confirmed IN (0, 1)),
    quote_data TEXT NOT NULL,
    embedded_docs TEXT NOT NULL DEFAULT '[]',
    assistant_sources TEXT NOT NULL DEFAULT '[]',
    applied_prefs TEXT NOT NULL DEFAULT '[]',
    chat_messages TEXT NOT NULL DEFAULT '[]',
    ai_state TEXT NOT NULL,
    undo_redo_stack TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    order_index INTEGER NOT NULL CHECK (order_index >= 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    archived_at_revision INTEGER,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'essay', 'short', 'truefalse')),
    topic TEXT NOT NULL DEFAULT '',
    cognitive_level INTEGER NOT NULL DEFAULT 0 CHECK (cognitive_level IN (0, 1, 2)),
    points_q4 INTEGER NOT NULL DEFAULT 0 CHECK (points_q4 >= 0),
    verification_status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (verification_status IN ('unverified', 'consistent', 'review', 'error')),
    approval_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (approval_status IN ('draft', 'approved', 'rejected')),
    block_ids TEXT NOT NULL,
    stem_text TEXT NOT NULL,
    rich_doc TEXT,
    runs_data TEXT,
    options_text TEXT NOT NULL DEFAULT '[]',
    option_docs TEXT NOT NULL DEFAULT '[]',
    answer_index INTEGER NOT NULL DEFAULT 0,
    answer_known INTEGER NOT NULL DEFAULT 1 CHECK (answer_known IN (0, 1)),
    answer_text TEXT NOT NULL DEFAULT '',
    truth_values TEXT NOT NULL DEFAULT '[]',
    explanation_text TEXT NOT NULL DEFAULT '',
    explanation_doc TEXT,
    rubric_items TEXT NOT NULL DEFAULT '[]',
    rule_type TEXT,
    data_linked INTEGER NOT NULL DEFAULT 0 CHECK (data_linked IN (0, 1)),
    figure_spec TEXT,
    figure_doc TEXT,
    extra_assets TEXT NOT NULL,
    source_ref TEXT,
    check_state TEXT,
    verification_data TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS exam_versions (
    id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    seq_index INTEGER NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    label TEXT NOT NULL,
    snapshot_state TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS question_versions (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    question_type TEXT NOT NULL,
    content_payload TEXT NOT NULL,
    evidence_list TEXT NOT NULL DEFAULT '[]',
    verification_status TEXT NOT NULL,
    approval_status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE (question_id, version_number)
);

CREATE TABLE IF NOT EXISTS ai_jobs (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT REFERENCES exams(id) ON DELETE SET NULL,
    origin_exam_id TEXT NOT NULL,
    job_kind TEXT NOT NULL DEFAULT 'generate'
        CHECK (job_kind IN ('patch', 'generate', 'check')),
    request_id TEXT,
    request_digest TEXT,
    base_revision INTEGER NOT NULL DEFAULT 1,
    sequence INTEGER NOT NULL DEFAULT 1 CHECK (sequence IN (1, 2)),
    status TEXT NOT NULL
        CHECK (status IN ('running', 'cancelling', 'cancelled', 'complete', 'failed')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    plan_data TEXT NOT NULL,
    questions_data TEXT NOT NULL DEFAULT '[]',
    pending_payload TEXT,
    receipt_payload TEXT,
    cost_points INTEGER,
    error_code TEXT,
    error_message TEXT,
    is_last_for_exam INTEGER NOT NULL DEFAULT 0 CHECK (is_last_for_exam IN (0, 1)),
    created_at INTEGER NOT NULL,
    completed_at INTEGER,
    UNIQUE (owner_id, origin_exam_id, request_id)
);

CREATE TABLE IF NOT EXISTS share_snapshots (
    token_hash TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id TEXT REFERENCES exams(id) ON DELETE SET NULL,
    origin_exam_id TEXT NOT NULL,
    exam_snapshot TEXT NOT NULL,
    include_answers INTEGER NOT NULL DEFAULT 0 CHECK (include_answers IN (0, 1)),
    allow_copy INTEGER NOT NULL DEFAULT 0 CHECK (allow_copy IN (0, 1)),
    revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1)),
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS exports (
    filename TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    export_type TEXT NOT NULL DEFAULT 'exam',
    format TEXT NOT NULL,
    is_teacher_copy INTEGER NOT NULL DEFAULT 0 CHECK (is_teacher_copy IN (0, 1)),
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine_legacy_items (
    legacy_key TEXT PRIMARY KEY,
    raw_value TEXT NOT NULL,
    rev INTEGER NOT NULL,
    updated INTEGER NOT NULL,
    error_reason TEXT NOT NULL,
    quarantined_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_docs_sha256 ON source_documents(sha256_hash);
CREATE INDEX IF NOT EXISTS idx_exams_owner ON exams(owner_id, order_index);
CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_active_order
    ON questions(exam_id, order_index) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS idx_exam_versions_exam ON exam_versions(exam_id, seq_index);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_owner_exam ON ai_jobs(owner_id, origin_exam_id);
"""


class RevisionConflictError(Exception):
    """Ngoại lệ khi xung đột phiên bản đề hoặc câu (HTTP 409 Conflict)."""

    def __init__(self, message: str, current_revision: int, code: str = "stale_snapshot") -> None:
        super().__init__(message)
        self.status = 409
        self.code = code
        self.current_revision = current_revision


class JobConflictError(Exception):
    """Ngoại lệ khi dùng lại requestId cho thao tác hoặc nội dung khác (HTTP 409)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status = 409
        self.code = "job_conflict"


@dataclass(frozen=True)
class StoredJobSubmission:
    """Trạng thái tác vụ AI lưu bền vững phục vụ replay qua khởi động lại."""

    job_id: str
    exam_id: str
    base_revision: int
    job_kind: str
    request_id: str
    request_digest: str
    sequence: int
    status: str
    proposal: dict[str, Any] | None = None
    error_code: str | None = None


def canonical_json(obj: Any) -> str:
    """Chuẩn hóa JSON để tính SHA-256 ổn định."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(data: bytes | str) -> str:
    """Tính mã băm SHA-256 hex 64 ký tự."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def compute_submission_digest(job_kind: str, request_payload: dict[str, Any]) -> str:
    """Tính fingerprint request khớp quy ước tại patch_routes.py (PR #39)."""
    raw_json = canonical_json(request_payload).encode("utf-8")
    prefix = b"generate:" if job_kind == "generate" else b""
    return hashlib.sha256(prefix + raw_json).hexdigest()


def map_question_statuses(q: dict[str, Any]) -> tuple[str, str]:
    """Tách check.status thành verification_status và approval_status."""
    check = q.get("check")
    if not isinstance(check, dict) or check.get("version") != q.get("v"):
        return ("unverified", "draft")
    st = check.get("status")
    problems = check.get("problems") or []
    if st == "approved":
        v_status = "review" if problems else "consistent"
        return (v_status, "approved")
    if st in ("consistent", "review", "unverified"):
        return (str(st), "draft")
    return ("unverified", "draft")


def build_question_version_payload(q: dict[str, Any]) -> str:
    """Đóng gói đầy đủ nội dung câu hỏi và richDoc cho bảng question_versions."""
    points_q4 = int(round(float(q.get("points") or 0) * 4))
    return canonical_json(
        {
            "stem": q["stem"],
            "richDoc": q.get("richDoc"),
            "options": q.get("options") or [],
            "optionDocs": q.get("optionDocs") or [],
            "answer": int(q.get("answer", 0)),
            "answerKnown": bool(q.get("answerKnown", True)),
            "answerText": q.get("answerText") or "",
            "truthValues": q.get("truthValues") or [],
            "explanation": q.get("explanation") or "",
            "explanationDoc": q.get("explanationDoc"),
            "rubric": q.get("rubric") or [],
            "points_q4": points_q4,
            "figure": q.get("figure"),
            "blockIds": q.get("blockIds") or {},
        }
    )


def parse_scoped_key(key: str, prefix: str) -> tuple[str, str] | None:
    """Tách (owner_id, resource_id) từ khóa KV legacy."""
    if key.startswith("u:"):
        parts = key.split(":", 2)
        if len(parts) == 3 and parts[2].startswith(prefix):
            return parts[1], parts[2][len(prefix) :]
    if key.startswith("guest:" + prefix):
        return "guest", key[len("guest:" + prefix) :]
    if key.startswith(prefix):
        return "local", key[len(prefix) :]
    return None


def _upsert_question_and_version(
    conn: sqlite3.Connection,
    exam_id: str,
    q_idx: int,
    q: dict[str, Any],
    updated_at: int,
) -> None:
    q_id = str(q["id"])
    v_num = int(q.get("v", 1))
    q_type = str(q.get("type") or "mcq")
    v_status, a_status = map_question_statuses(q)
    if "verificationStatus" in q:
        v_status = str(q["verificationStatus"])
    if "approvalStatus" in q:
        a_status = str(q["approvalStatus"])
    points_q4 = int(round(float(q.get("points") or 0) * 4))
    extra_assets = {
        "formulas": q.get("formulas") or [],
        "tables": q.get("tables") or [],
        "images": q.get("images") or [],
        "pageBreak": bool(q.get("pageBreak", False)),
    }
    ver_data = {
        "verification": q.get("verification"),
        "algebra": q.get("algebra"),
        "generated": q.get("generated"),
    }
    ver_data.update(
        {key: q[key] for key in ("verificationStatus", "approvalStatus", "evidence") if key in q}
    )
    result = conn.execute(
        """
        INSERT INTO questions(
            id, exam_id, order_index, is_active, archived_at_revision, version,
            question_type, topic, cognitive_level, points_q4,
            verification_status, approval_status, block_ids, stem_text,
            rich_doc, runs_data, options_text, option_docs,
            answer_index, answer_known, answer_text, truth_values,
            explanation_text, explanation_doc, rubric_items, rule_type,
            data_linked, figure_spec, figure_doc, extra_assets,
            source_ref, check_state, verification_data, updated_at
        )
        VALUES (
            ?, ?, ?, 1, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            order_index = excluded.order_index,
            is_active = 1,
            archived_at_revision = NULL,
            version = excluded.version,
            question_type = excluded.question_type,
            topic = excluded.topic,
            cognitive_level = excluded.cognitive_level,
            points_q4 = excluded.points_q4,
            verification_status = excluded.verification_status,
            approval_status = excluded.approval_status,
            block_ids = excluded.block_ids,
            stem_text = excluded.stem_text,
            rich_doc = excluded.rich_doc,
            runs_data = excluded.runs_data,
            options_text = excluded.options_text,
            option_docs = excluded.option_docs,
            answer_index = excluded.answer_index,
            answer_known = excluded.answer_known,
            answer_text = excluded.answer_text,
            truth_values = excluded.truth_values,
            explanation_text = excluded.explanation_text,
            explanation_doc = excluded.explanation_doc,
            rubric_items = excluded.rubric_items,
            rule_type = excluded.rule_type,
            data_linked = excluded.data_linked,
            figure_spec = excluded.figure_spec,
            figure_doc = excluded.figure_doc,
            extra_assets = excluded.extra_assets,
            source_ref = excluded.source_ref,
            check_state = excluded.check_state,
            verification_data = excluded.verification_data,
            updated_at = excluded.updated_at
        WHERE questions.exam_id = excluded.exam_id
        """,
        (
            q_id,
            exam_id,
            q_idx,
            v_num,
            q_type,
            q.get("topic") or "",
            int(q.get("level", 0)),
            points_q4,
            v_status,
            a_status,
            canonical_json(q.get("blockIds") or {}),
            q["stem"],
            canonical_json(q["richDoc"]) if q.get("richDoc") is not None else None,
            canonical_json(q["runs"]) if q.get("runs") is not None else None,
            canonical_json(q.get("options") or []),
            canonical_json(q.get("optionDocs") or []),
            int(q.get("answer", 0)),
            1 if q.get("answerKnown", True) else 0,
            q.get("answerText") or "",
            canonical_json(q.get("truthValues") or []),
            q.get("explanation") or "",
            canonical_json(q["explanationDoc"]) if q.get("explanationDoc") is not None else None,
            canonical_json(q.get("rubric") or []),
            q.get("rule"),
            1 if q.get("dataLinked") else 0,
            canonical_json(q["figure"]) if q.get("figure") is not None else None,
            canonical_json(q["figureDoc"]) if q.get("figureDoc") is not None else None,
            canonical_json(extra_assets),
            canonical_json(q["source"]) if q.get("source") is not None else None,
            canonical_json(q["check"]) if q.get("check") is not None else None,
            canonical_json(ver_data),
            updated_at,
        ),
    )

    if result.rowcount != 1:
        raise sqlite3.IntegrityError("Trùng mã câu hỏi giữa hai đề.")

    qv_id = f"{q_id}:v{v_num}"
    evidence = q.get("evidence") or ([q["source"]] if q.get("source") else [])
    conn.execute(
        """
        INSERT INTO question_versions(
            id, question_id, version_number, question_type,
            content_payload, evidence_list, verification_status,
            approval_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id, version_number) DO UPDATE SET
            content_payload = excluded.content_payload,
            evidence_list = excluded.evidence_list,
            verification_status = excluded.verification_status,
            approval_status = excluded.approval_status
        """,
        (
            qv_id,
            q_id,
            v_num,
            q_type,
            build_question_version_payload(q),
            canonical_json(evidence),
            v_status,
            a_status,
            updated_at,
        ),
    )


def migrate_legacy_store(
    src_sqlite: Path,
    dst_sqlite: Path,
    blobs_dir: Path,
    *,
    simulate_mid_failure: bool = False,
) -> dict[str, Any]:
    """Thực thi di trú 5 pha từ SQLite KV sang 15 bảng chuẩn hóa trên bản sao."""
    src_sqlite = src_sqlite.resolve()
    dst_sqlite = dst_sqlite.resolve()
    blobs_dir = blobs_dir.resolve()
    if src_sqlite == dst_sqlite:
        raise ValueError("Chọn kho đích khác với kho nguồn.")

    dst_sqlite.parent.mkdir(parents=True, exist_ok=True)
    blobs_dir.parent.mkdir(parents=True, exist_ok=True)
    lock_path = dst_sqlite.with_name(dst_sqlite.name + ".migration-lock")
    with closing(sqlite3.connect(lock_path, timeout=0)) as lock:
        try:
            lock.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                raise
            raise RuntimeError("Kho đích đang có một lượt di trú.") from exc
        with (
            TemporaryDirectory(prefix=".migration-db-", dir=dst_sqlite.parent) as db_temp,
            TemporaryDirectory(prefix=".migration-blobs-", dir=blobs_dir.parent) as blob_temp,
        ):
            return _migrate_snapshot(
                src_sqlite,
                dst_sqlite,
                blobs_dir,
                Path(db_temp) / dst_sqlite.name,
                Path(blob_temp),
                simulate_mid_failure,
            )


def _migrate_snapshot(
    src_sqlite: Path,
    dst_sqlite: Path,
    blobs_dir: Path,
    tmp_sqlite: Path,
    tmp_blobs: Path,
    simulate_mid_failure: bool,
) -> dict[str, Any]:
    if dst_sqlite.exists():
        shutil.copy2(dst_sqlite, tmp_sqlite)

    with (
        closing(sqlite3.connect(f"{src_sqlite.as_uri()}?mode=ro", uri=True)) as src_conn,
        closing(sqlite3.connect(tmp_sqlite)) as dst_conn,
    ):
        src_conn.row_factory = dst_conn.row_factory = sqlite3.Row
        src_conn.execute("BEGIN")
        dst_conn.executescript(SCHEMA_DDL)
        with dst_conn:
            for sys_id, sys_name in [("local", "Tài khoản cục bộ"), ("guest", "Khách")]:
                dst_conn.execute(
                    """
                    INSERT INTO users(id, email, name, salt, password_hash, created_at)
                    VALUES (?, NULL, ?, NULL, NULL, 0)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (sys_id, sys_name),
                )

            local_owner_row = src_conn.execute(
                "SELECT value FROM kv WHERE key = 'local-owner'"
            ).fetchone()
            local_owner_id = json.loads(local_owner_row["value"]) if local_owner_row else None

            # PHA 1: config, users, sessions, credits (nạp users trước để thỏa FK)
            pha1_query = (
                "SELECT key, value, rev, updated FROM kv "
                "WHERE key = 'config' OR key LIKE 'user:%' "
                "OR key LIKE 'session:%' OR key LIKE 'credits:%' "
                "ORDER BY CASE "
                "WHEN key = 'config' THEN 0 "
                "WHEN key LIKE 'user:%' THEN 1 "
                "ELSE 2 END, key"
            )
            for row in src_conn.execute(pha1_query):
                key = str(row["key"])
                raw_val = str(row["value"])
                rev = int(row["rev"])
                updated = int(row["updated"])
                try:
                    val = json.loads(raw_val)
                except Exception as exc:
                    dst_conn.execute(
                        "INSERT OR REPLACE INTO quarantine_legacy_items VALUES (?, ?, ?, ?, ?, ?)",
                        (key, raw_val, rev, updated, f"Invalid JSON: {exc}", updated),
                    )
                    continue

                if key == "config":
                    dst_conn.execute(
                        """
                        INSERT INTO app_configs(key, value_json, rev, updated_at)
                        VALUES ('config', ?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            value_json = excluded.value_json,
                            rev = excluded.rev,
                            updated_at = excluded.updated_at
                        """,
                        (canonical_json(val), rev, updated),
                    )
                elif key.startswith("user:"):
                    uid = str(val["id"])
                    dst_conn.execute(
                        """
                        INSERT INTO users(
                            id, email, name, salt, password_hash,
                            is_local_owner, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            email = excluded.email,
                            name = excluded.name,
                            salt = excluded.salt,
                            password_hash = excluded.password_hash,
                            is_local_owner = excluded.is_local_owner
                        """,
                        (
                            uid,
                            str(val["email"]).lower(),
                            val["name"],
                            val.get("salt"),
                            val.get("passwordHash"),
                            1 if uid == local_owner_id else 0,
                            updated,
                        ),
                    )
                elif key.startswith("session:"):
                    token_hash = key.split(":", 1)[1]
                    user_id = val.get("userId")
                    expires = int(val.get("expires", 0))
                    revoked = 1 if (expires <= 0 or not user_id) else 0
                    dst_conn.execute(
                        """
                        INSERT INTO sessions(
                            token_hash, user_id, expires_at, revoked, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(token_hash) DO UPDATE SET
                            user_id = excluded.user_id,
                            expires_at = excluded.expires_at,
                            revoked = excluded.revoked,
                            updated_at = excluded.updated_at
                        """,
                        (token_hash, user_id, expires, revoked, updated),
                    )
                elif key.startswith("credits:"):
                    owner_id = key.split(":", 1)[1]
                    dst_conn.execute(
                        """
                        INSERT INTO credit_accounts(owner_id, balance, label, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(owner_id) DO UPDATE SET
                            balance = excluded.balance,
                            label = excluded.label,
                            updated_at = excluded.updated_at
                        """,
                        (
                            owner_id,
                            int(val.get("balance", 1000)),
                            val.get("label", ""),
                            updated,
                        ),
                    )
                    for idx, entry in enumerate(val.get("ledger") or []):
                        dst_conn.execute(
                            """
                            INSERT INTO credit_ledgers(
                                owner_id, seq_index, delta, reason, reference, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(owner_id, seq_index) DO UPDATE SET
                                delta = excluded.delta,
                                reason = excluded.reason,
                                reference = excluded.reference,
                                created_at = excluded.created_at
                            """,
                            (
                                owner_id,
                                idx,
                                int(entry["delta"]),
                                entry["reason"],
                                entry.get("reference"),
                                int(entry.get("at", updated)),
                            ),
                        )

            # PHA 2: Quét state lập bảng tra cứu fileId -> {filename, kind, uploaded}
            file_meta_map: dict[tuple[str, str], dict[str, Any]] = {}
            valid_states: list[tuple[str, dict[str, Any], int, int]] = []
            pha2_query = (
                "SELECT key, value, rev, updated FROM kv "
                "WHERE key = 'state' OR key = 'guest:state' OR key LIKE 'u:%:state'"
            )
            for row in src_conn.execute(pha2_query):
                key = str(row["key"])
                raw_val = str(row["value"])
                rev = int(row["rev"])
                updated = int(row["updated"])
                owner_id = (
                    "local"
                    if key == "state"
                    else ("guest" if key == "guest:state" else key.split(":")[1])
                )
                try:
                    state_obj = json.loads(raw_val)
                    if not isinstance(state_obj, dict) or not isinstance(
                        state_obj.get("exams"), list
                    ):
                        raise ValueError("Missing exams list in state payload")
                except Exception as exc:
                    dst_conn.execute(
                        "INSERT OR REPLACE INTO quarantine_legacy_items VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            key,
                            raw_val,
                            rev,
                            updated,
                            f"Corrupt state payload: {exc}",
                            updated,
                        ),
                    )
                    continue

                valid_states.append((owner_id, state_obj, rev, updated))
                for ex in state_obj.get("exams") or []:
                    for doc in ex.get("docs") or []:
                        fid = doc.get("fileId")
                        if fid:
                            file_meta_map[(owner_id, str(fid))] = {
                                "filename": doc.get("name") or f"document-{fid}",
                                "kind": doc.get("kind") or "pdf",
                                "uploaded": int(doc.get("uploaded") or updated),
                            }

            # PHA 3: Streaming từng dòng file:* qua cursor
            data_url_re = re.compile(r"^data:([^;,]+);base64,(.+)$", re.DOTALL)
            pha3_query = (
                "SELECT key, value, rev, updated FROM kv "
                "WHERE key LIKE 'file:%' OR key LIKE 'guest:file:%' "
                "OR key LIKE 'u:%:file:%'"
            )
            for row in src_conn.execute(pha3_query):
                key = str(row["key"])
                raw_val = str(row["value"])
                rev = int(row["rev"])
                updated = int(row["updated"])
                parsed_scope = parse_scoped_key(key, "file:")
                if not parsed_scope:
                    continue
                owner_id, file_id = parsed_scope
                try:
                    data_url = json.loads(raw_val)
                    if not isinstance(data_url, str):
                        raise ValueError("File payload is not a string")
                    m = data_url_re.match(data_url)
                    if not m:
                        raise ValueError("File payload is not a valid base64 Data URL")
                    mime_type, b64_part = m.group(1), m.group(2)
                    binary_data = base64.b64decode(b64_part, validate=True)
                    if len(binary_data) == 0 or len(binary_data) > 20 * 1024 * 1024:
                        raise ValueError(f"Invalid decoded file size: {len(binary_data)}")
                except Exception as exc:
                    dst_conn.execute(
                        "INSERT OR REPLACE INTO quarantine_legacy_items VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            key,
                            raw_val,
                            rev,
                            updated,
                            f"Corrupt file payload: {exc}",
                            updated,
                        ),
                    )
                    continue

                digest = sha256_hex(binary_data)
                rel_path = f"blobs/{digest[:2]}/{digest}.bin"
                abs_blob_path = tmp_blobs / digest[:2] / f"{digest}.bin"
                abs_blob_path.parent.mkdir(parents=True, exist_ok=True)
                if not abs_blob_path.exists():
                    abs_blob_path.write_bytes(binary_data)

                meta = file_meta_map.get((owner_id, file_id))
                is_orphan = 0 if meta else 1
                ext = mime_type.split("/")[-1] if "/" in mime_type else "bin"
                filename = meta["filename"] if meta else f"orphan-{file_id}.{ext}"
                if meta:
                    kind = meta["kind"]
                elif "pdf" in mime_type:
                    kind = "pdf"
                elif "image" in mime_type:
                    kind = "image"
                else:
                    kind = "text"
                created_at = meta["uploaded"] if meta else updated

                dst_conn.execute(
                    """
                    INSERT INTO source_documents(
                        owner_id, id, filename, kind, mime_type, byte_size,
                        sha256_hash, blob_rel_path, is_orphan, rev, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(owner_id, id) DO UPDATE SET
                        filename = excluded.filename,
                        kind = excluded.kind,
                        mime_type = excluded.mime_type,
                        byte_size = excluded.byte_size,
                        sha256_hash = excluded.sha256_hash,
                        blob_rel_path = excluded.blob_rel_path,
                        is_orphan = excluded.is_orphan,
                        rev = excluded.rev
                    """,
                    (
                        owner_id,
                        file_id,
                        filename,
                        kind,
                        mime_type,
                        len(binary_data),
                        digest,
                        rel_path,
                        is_orphan,
                        rev,
                        created_at,
                    ),
                )

            if simulate_mid_failure:
                raise RuntimeError("Simulated disk failure in the middle of migration")

            # PHA 4: Nạp States, Exams, Questions, Versions, Jobs, Shares, Exports
            known_exam_ids: set[str] = set()
            for owner_id, state_obj, rev, updated in valid_states:
                dst_conn.execute(
                    """
                    UPDATE users
                    SET workspace_version = ?,
                        current_exam_id = ?,
                        seen_ai_jobs = ?,
                        workspace_revision = ?
                    WHERE id = ?
                    """,
                    (
                        int(state_obj.get("version", 1)),
                        state_obj.get("current"),
                        canonical_json(state_obj.get("seenAIJobs") or []),
                        rev,
                        owner_id,
                    ),
                )

                for p_idx, pref in enumerate(state_obj.get("prefs") or []):
                    dst_conn.execute(
                        """
                        INSERT INTO teacher_preferences(
                            owner_id, id, order_index, kind,
                            content_text, max_words, confirmed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(owner_id, id) DO UPDATE SET
                            order_index = excluded.order_index,
                            kind = excluded.kind,
                            content_text = excluded.content_text,
                            max_words = excluded.max_words,
                            confirmed_at = excluded.confirmed_at
                        """,
                        (
                            owner_id,
                            pref["id"],
                            p_idx,
                            pref.get("kind") or "short",
                            pref["text"],
                            pref.get("maxWords"),
                            int(pref.get("confirmedAt") or updated),
                        ),
                    )

                for e_idx, ex in enumerate(state_obj.get("exams") or []):
                    ex_id = str(ex["id"])
                    if ex_id in known_exam_ids:
                        raise sqlite3.IntegrityError("Trùng mã đề trong kho nguồn.")
                    known_exam_ids.add(ex_id)
                    ai_state: dict[str, Any] = {
                        "aiPlan": ex.get("aiPlan"),
                        "aiClarification": ex.get("aiClarification"),
                        "activeAIJob": ex.get("activeAIJob"),
                        "aiConsent": ex.get("aiConsent", False),
                        "aiEffort": ex.get("aiEffort", 1),
                        "aiChatMode": ex.get("aiChatMode", "auto"),
                        "autoUpdate": ex.get("autoUpdate", False),
                    }
                    for key in ("approvedGenerationPlan", "aiInstructions", "generationRequest"):
                        if key in ex:
                            ai_state[key] = ex[key]
                    if "draftStatus" in ex:
                        ai_state["draftStatus"] = ex["draftStatus"]
                    undo_redo = {
                        "undo": (ex.get("undo") or [])[-60:],
                        "redo": (ex.get("redo") or [])[-60:],
                    }
                    draft_status = str(ex.get("draftStatus") or "draft")
                    result = dst_conn.execute(
                        """
                        INSERT INTO exams(
                            id, owner_id, order_index, title, subject, grade, minutes,
                            department, school, instructions, marking_guidance,
                            draft_status, is_sample, is_full_exam, revision, block_ids,
                            layout_config, data_table, matrix_spec, matrix_confirmed,
                            quote_data, embedded_docs, assistant_sources, applied_prefs,
                            chat_messages, ai_state, undo_redo_stack, updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        ON CONFLICT(id) DO UPDATE SET
                            order_index = excluded.order_index,
                            title = excluded.title,
                            subject = excluded.subject,
                            grade = excluded.grade,
                            minutes = excluded.minutes,
                            department = excluded.department,
                            school = excluded.school,
                            instructions = excluded.instructions,
                            marking_guidance = excluded.marking_guidance,
                            draft_status = excluded.draft_status,
                            is_sample = excluded.is_sample,
                            is_full_exam = excluded.is_full_exam,
                            revision = excluded.revision,
                            block_ids = excluded.block_ids,
                            layout_config = excluded.layout_config,
                            data_table = excluded.data_table,
                            matrix_spec = excluded.matrix_spec,
                            matrix_confirmed = excluded.matrix_confirmed,
                            quote_data = excluded.quote_data,
                            embedded_docs = excluded.embedded_docs,
                            assistant_sources = excluded.assistant_sources,
                            applied_prefs = excluded.applied_prefs,
                            chat_messages = excluded.chat_messages,
                            ai_state = excluded.ai_state,
                            undo_redo_stack = excluded.undo_redo_stack,
                            updated_at = excluded.updated_at
                        WHERE exams.owner_id = excluded.owner_id
                        """,
                        (
                            ex_id,
                            owner_id,
                            e_idx,
                            ex["title"],
                            ex["subject"],
                            str(ex["grade"]),
                            int(ex["minutes"]),
                            ex.get("department") or "",
                            ex.get("school") or "",
                            ex.get("instructions") or "",
                            ex.get("markingGuidance") or "",
                            draft_status,
                            1 if ex.get("sample") else 0,
                            1 if ex.get("fullExam") else 0,
                            int(ex.get("revision", 1)),
                            canonical_json(ex.get("blockIds") or {}),
                            canonical_json(ex.get("layout") or {}),
                            canonical_json(ex.get("data") or []),
                            canonical_json(ex.get("matrix") or []),
                            1 if ex.get("matrixConfirmed") else 0,
                            canonical_json(ex.get("quote") or {}),
                            canonical_json(ex.get("docs") or []),
                            canonical_json(ex.get("assistantSources") or []),
                            canonical_json(ex.get("appliedPrefs") or []),
                            canonical_json(ex.get("chat") or []),
                            canonical_json(ai_state),
                            canonical_json(undo_redo),
                            int(ex.get("updated") or updated),
                        ),
                    )

                    if result.rowcount != 1:
                        raise sqlite3.IntegrityError("Trùng mã đề giữa hai kho.")

                    for h_idx, h_item in enumerate(ex.get("history") or []):
                        dst_conn.execute(
                            """
                            INSERT INTO exam_versions(
                                id, exam_id, seq_index, revision,
                                label, snapshot_state, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                seq_index = excluded.seq_index,
                                revision = excluded.revision,
                                label = excluded.label,
                                snapshot_state = excluded.snapshot_state,
                                created_at = excluded.created_at
                            """,
                            (
                                h_item["id"],
                                ex_id,
                                h_idx,
                                int(h_item["revision"]),
                                h_item["label"],
                                canonical_json(h_item["state"]),
                                int(h_item["at"]),
                            ),
                        )

                    # Đưa các câu cũ của đề về is_active = 0 trước khi nạp danh sách câu hiện hành
                    dst_conn.execute(
                        "UPDATE questions SET is_active = 0 WHERE exam_id = ?",
                        (ex_id,),
                    )
                    for q_idx, q in enumerate(ex.get("questions") or []):
                        _upsert_question_and_version(
                            dst_conn,
                            ex_id,
                            q_idx,
                            q,
                            int(ex.get("updated") or updated),
                        )

            last_job_map: dict[tuple[str, str], str] = {}
            last_job_query = (
                "SELECT key, value FROM kv "
                "WHERE key LIKE 'last-job:%' OR key LIKE 'guest:last-job:%' "
                "OR key LIKE 'u:%:last-job:%'"
            )
            for row in src_conn.execute(last_job_query):
                parsed = parse_scoped_key(str(row["key"]), "last-job:")
                if parsed:
                    last_job_map[parsed] = str(json.loads(str(row["value"])))

            job_query = (
                "SELECT key, value, rev, updated FROM kv "
                "WHERE key LIKE 'job:%' OR key LIKE 'guest:job:%' "
                "OR key LIKE 'u:%:job:%'"
            )
            for row in src_conn.execute(job_query):
                parsed = parse_scoped_key(str(row["key"]), "job:")
                if not parsed:
                    continue
                owner_id, job_id = parsed
                job = json.loads(str(row["value"]))
                origin_exam_id = str(job["examId"])
                fk_exam_id = origin_exam_id if origin_exam_id in known_exam_ids else None
                is_last = 1 if last_job_map.get((owner_id, origin_exam_id)) == job_id else 0
                status = str(job["status"])
                active = 0 if status in ("cancelled", "cancelling", "failed") else 1
                seq = 1 if status == "running" else 2
                dst_conn.execute(
                    """
                    INSERT INTO ai_jobs(
                        id, owner_id, exam_id, origin_exam_id, job_kind,
                        request_id, request_digest, base_revision, sequence,
                        status, active, plan_data, questions_data, cost_points,
                        error_message, is_last_for_exam, created_at, completed_at
                    )
                    VALUES (?, ?, ?, ?, 'generate', NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        exam_id = excluded.exam_id,
                        sequence = excluded.sequence,
                        status = excluded.status,
                        active = excluded.active,
                        plan_data = excluded.plan_data,
                        questions_data = excluded.questions_data,
                        cost_points = excluded.cost_points,
                        error_message = excluded.error_message,
                        is_last_for_exam = excluded.is_last_for_exam,
                        completed_at = excluded.completed_at
                    """,
                    (
                        job_id,
                        owner_id,
                        fk_exam_id,
                        origin_exam_id,
                        int(job.get("baseRevision", 1)),
                        seq,
                        status,
                        active,
                        canonical_json(job.get("plan") or {}),
                        canonical_json(job.get("questions") or []),
                        job.get("cost"),
                        job.get("error"),
                        is_last,
                        int(job.get("created") or row["updated"]),
                        job.get("completed"),
                    ),
                )

            for row in src_conn.execute(
                "SELECT key, value, updated FROM kv WHERE key LIKE 'share:%'"
            ):
                token_hash = str(row["key"]).split(":", 1)[1]
                share = json.loads(str(row["value"]))
                origin_exam_id = str(share["examId"])
                fk_exam_id = origin_exam_id if origin_exam_id in known_exam_ids else None
                dst_conn.execute(
                    """
                    INSERT INTO share_snapshots(
                        token_hash, owner_id, exam_id, origin_exam_id, exam_snapshot,
                        include_answers, allow_copy, revoked, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(token_hash) DO UPDATE SET
                        exam_id = excluded.exam_id,
                        exam_snapshot = excluded.exam_snapshot,
                        include_answers = excluded.include_answers,
                        allow_copy = excluded.allow_copy,
                        revoked = excluded.revoked
                    """,
                    (
                        token_hash,
                        share["owner"],
                        fk_exam_id,
                        origin_exam_id,
                        canonical_json(share["exam"]),
                        1 if share.get("answers") else 0,
                        1 if share.get("allowCopy") else 0,
                        1 if share.get("revoked") else 0,
                        int(share.get("created") or row["updated"]),
                    ),
                )

            for row in src_conn.execute(
                "SELECT key, value, updated FROM kv WHERE key LIKE 'export-owner:%'"
            ):
                filename = str(row["key"]).split(":", 1)[1]
                owner_id = str(json.loads(str(row["value"])))
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "html"
                export_type = "backup" if filename.startswith("Ban-sao-") else "exam"
                is_teacher = 1 if filename.startswith("Giao-vien-") else 0
                dst_conn.execute(
                    """
                    INSERT INTO exports(
                        filename, owner_id, export_type, format,
                        is_teacher_copy, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(filename) DO UPDATE SET
                        owner_id = excluded.owner_id
                    """,
                    (filename, owner_id, export_type, ext, is_teacher, int(row["updated"])),
                )

            # PHA 5: Kiểm tra PRAGMA foreign_key_check và integrity_check
            fk_errors = dst_conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise RuntimeError(f"Foreign key check failed: {fk_errors}")
            integrity = dst_conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"Integrity check failed: {integrity}")

    # Thêm blob theo hash trước khi thay DB để DB cũ luôn đọc được dữ liệu đã có.
    for blob in tmp_blobs.rglob("*.bin"):
        destination = blobs_dir / blob.relative_to(tmp_blobs)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            blob.replace(destination)
    tmp_sqlite.replace(dst_sqlite)
    return {"ok": True}


def reconstruct_workspace_state(conn: sqlite3.Connection, owner_id: str) -> dict[str, Any]:
    """Tái tạo JSON state chuẩn từ 15 bảng quan hệ (chỉ lấy câu hỏi is_active = 1)."""
    u_row = conn.execute("SELECT * FROM users WHERE id = ?", (owner_id,)).fetchone()
    prefs = [
        {
            "id": r["id"],
            "text": r["content_text"],
            "kind": r["kind"],
            "maxWords": r["max_words"],
            "confirmedAt": r["confirmed_at"],
        }
        for r in conn.execute(
            "SELECT * FROM teacher_preferences WHERE owner_id = ? ORDER BY order_index ASC",
            (owner_id,),
        )
    ]

    exams = []
    for ex_row in conn.execute(
        "SELECT * FROM exams WHERE owner_id = ? ORDER BY order_index ASC", (owner_id,)
    ):
        ex_id = ex_row["id"]
        questions = []
        for q_row in conn.execute(
            "SELECT * FROM questions WHERE exam_id = ? AND is_active = 1 ORDER BY order_index ASC",
            (ex_id,),
        ):
            extra = json.loads(q_row["extra_assets"])
            ver = json.loads(q_row["verification_data"])
            pts_q4 = int(q_row["points_q4"])
            pts: int | float = pts_q4 // 4 if pts_q4 % 4 == 0 else pts_q4 / 4.0
            questions.append(
                {
                    "id": q_row["id"],
                    "v": q_row["version"],
                    "type": q_row["question_type"],
                    "topic": q_row["topic"],
                    "level": q_row["cognitive_level"],
                    "points": pts,
                    "stem": q_row["stem_text"],
                    "richDoc": json.loads(q_row["rich_doc"])
                    if q_row["rich_doc"] is not None
                    else None,
                    "runs": json.loads(q_row["runs_data"])
                    if q_row["runs_data"] is not None
                    else None,
                    "options": json.loads(q_row["options_text"]),
                    "optionDocs": json.loads(q_row["option_docs"]),
                    "answer": q_row["answer_index"],
                    "answerKnown": bool(q_row["answer_known"]),
                    "answerText": q_row["answer_text"],
                    "truthValues": json.loads(q_row["truth_values"]),
                    "explanation": q_row["explanation_text"],
                    "explanationDoc": json.loads(q_row["explanation_doc"])
                    if q_row["explanation_doc"] is not None
                    else None,
                    "rubric": json.loads(q_row["rubric_items"]),
                    "rule": q_row["rule_type"],
                    "dataLinked": bool(q_row["data_linked"]),
                    "figure": json.loads(q_row["figure_spec"])
                    if q_row["figure_spec"] is not None
                    else None,
                    "figureDoc": json.loads(q_row["figure_doc"])
                    if q_row["figure_doc"] is not None
                    else None,
                    "formulas": extra["formulas"],
                    "tables": extra["tables"],
                    "images": extra["images"],
                    "pageBreak": extra["pageBreak"],
                    "source": json.loads(q_row["source_ref"])
                    if q_row["source_ref"] is not None
                    else None,
                    "check": json.loads(q_row["check_state"])
                    if q_row["check_state"] is not None
                    else None,
                    "verification": ver["verification"],
                    "algebra": ver["algebra"],
                    "generated": ver["generated"],
                    "blockIds": json.loads(q_row["block_ids"]),
                    **{
                        key: value
                        for key, value in (
                            ("verificationStatus", q_row["verification_status"]),
                            ("approvalStatus", q_row["approval_status"]),
                            ("evidence", ver.get("evidence")),
                        )
                        if key in ver
                    },
                }
            )

        history = [
            {
                "id": h["id"],
                "label": h["label"],
                "at": h["created_at"],
                "revision": h["revision"],
                "state": json.loads(h["snapshot_state"]),
            }
            for h in conn.execute(
                "SELECT * FROM exam_versions WHERE exam_id = ? ORDER BY seq_index ASC",
                (ex_id,),
            )
        ]

        ai_state = json.loads(ex_row["ai_state"])
        undo_redo = json.loads(ex_row["undo_redo_stack"])
        exam_dict: dict[str, Any] = {
            "id": ex_id,
            "title": ex_row["title"],
            "subject": ex_row["subject"],
            "grade": ex_row["grade"],
            "minutes": ex_row["minutes"],
            "department": ex_row["department"],
            "school": ex_row["school"],
            "instructions": ex_row["instructions"],
            "markingGuidance": ex_row["marking_guidance"],
            "sample": bool(ex_row["is_sample"]),
            "fullExam": bool(ex_row["is_full_exam"]),
            "layout": json.loads(ex_row["layout_config"]),
            "blockIds": json.loads(ex_row["block_ids"]),
            "questions": questions,
            "docs": json.loads(ex_row["embedded_docs"]),
            "assistantSources": json.loads(ex_row["assistant_sources"]),
            "data": json.loads(ex_row["data_table"]),
            "matrix": json.loads(ex_row["matrix_spec"]),
            "matrixConfirmed": bool(ex_row["matrix_confirmed"]),
            "quote": json.loads(ex_row["quote_data"]),
            "appliedPrefs": json.loads(ex_row["applied_prefs"]),
            "chat": json.loads(ex_row["chat_messages"]),
            "aiPlan": ai_state["aiPlan"],
            "aiClarification": ai_state["aiClarification"],
            "activeAIJob": ai_state["activeAIJob"],
            "aiConsent": ai_state["aiConsent"],
            "aiEffort": ai_state["aiEffort"],
            "aiChatMode": ai_state["aiChatMode"],
            "autoUpdate": ai_state["autoUpdate"],
            "history": history,
            "undo": undo_redo["undo"],
            "redo": undo_redo["redo"],
            "revision": ex_row["revision"],
            "updated": ex_row["updated_at"],
        }
        for key in ("approvedGenerationPlan", "aiInstructions", "generationRequest"):
            if key in ai_state:
                exam_dict[key] = ai_state[key]
        if "draftStatus" in ai_state or ex_row["draft_status"] != "draft":
            exam_dict["draftStatus"] = ex_row["draft_status"]
        exams.append(exam_dict)

    out: dict[str, Any] = {
        "version": u_row["workspace_version"],
        "current": u_row["current_exam_id"],
        "exams": exams,
        "prefs": prefs,
    }
    seen_jobs = json.loads(u_row["seen_ai_jobs"])
    if seen_jobs:
        out["seenAIJobs"] = seen_jobs
    return out


def update_exam_with_occ(
    conn: sqlite3.Connection,
    exam_id: str,
    owner_id: str,
    new_title: str,
    base_revision: int,
) -> int:
    """Cập nhật đề thi với kiểm tra khóa lạc quan (Optimistic Concurrency Control)."""
    with conn:
        updated = conn.execute(
            "UPDATE exams SET title = ?, revision = revision + 1 "
            "WHERE id = ? AND owner_id = ? AND revision = ? RETURNING revision",
            (new_title, exam_id, owner_id, base_revision),
        ).fetchone()
        if updated is not None:
            return int(updated[0])
        row = conn.execute(
            "SELECT revision FROM exams WHERE id = ? AND owner_id = ?",
            (exam_id, owner_id),
        ).fetchone()
        if not row:
            raise KeyError(exam_id)
        current_rev = int(row[0])
        raise RevisionConflictError(
            "Dữ liệu đã được thay đổi ở cửa sổ khác. Hãy tải lại trước khi tiếp tục.",
            current_revision=current_rev,
        )


def replay_or_register_submission(
    db_path: Path,
    *,
    owner_id: str,
    exam_id: str,
    job_id: str,
    job_kind: str,
    request_id: str,
    request_payload: dict[str, Any],
    base_revision: int,
    created_at: int = 1762700500000,
) -> tuple[StoredJobSubmission, bool]:
    """Kiểm tra idempotency / job_conflict (409) bền vững qua khởi động lại."""
    digest = compute_submission_digest(job_kind, request_payload)
    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                """
                SELECT id, origin_exam_id, job_kind, request_id, request_digest,
                       base_revision, sequence, status, pending_payload, error_code
                FROM ai_jobs
                WHERE owner_id = ? AND origin_exam_id = ? AND request_id = ?
                """,
                (owner_id, exam_id, request_id),
            ).fetchone()
            if prior is not None:
                if prior["job_kind"] != job_kind or prior["request_digest"] != digest:
                    raise JobConflictError("Mã yêu cầu đã dùng cho nội dung khác.")
                proposal = (
                    json.loads(prior["pending_payload"]).get("proposal")
                    if prior["pending_payload"]
                    else None
                )
                return (
                    StoredJobSubmission(
                        job_id=str(prior["id"]),
                        exam_id=str(prior["origin_exam_id"]),
                        base_revision=int(prior["base_revision"]),
                        job_kind=str(prior["job_kind"]),
                        request_id=str(prior["request_id"]),
                        request_digest=str(prior["request_digest"]),
                        sequence=int(prior["sequence"]),
                        status=str(prior["status"]),
                        proposal=proposal,
                        error_code=prior["error_code"],
                    ),
                    True,
                )

            ex_exists = conn.execute(
                "SELECT 1 FROM exams WHERE id = ? AND owner_id = ?",
                (exam_id, owner_id),
            ).fetchone()
            fk_exam_id = exam_id if ex_exists else None
            conn.execute(
                """
                INSERT INTO ai_jobs(
                    id, owner_id, exam_id, origin_exam_id, job_kind,
                    request_id, request_digest, base_revision, sequence,
                    status, active, plan_data, questions_data, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'running', 1, ?, '[]', ?)
                """,
                (
                    job_id,
                    owner_id,
                    fk_exam_id,
                    exam_id,
                    job_kind,
                    request_id,
                    digest,
                    base_revision,
                    canonical_json(request_payload),
                    created_at,
                ),
            )
            return (
                StoredJobSubmission(
                    job_id=job_id,
                    exam_id=exam_id,
                    base_revision=base_revision,
                    job_kind=job_kind,
                    request_id=request_id,
                    request_digest=digest,
                    sequence=1,
                    status="running",
                ),
                False,
            )
    finally:
        conn.close()


def confirm_patch_or_generation_tx(
    db_path: Path,
    *,
    owner_id: str,
    exam_id: str,
    job_id: str,
    base_revision: int,
    new_questions: list[dict[str, Any]],
    is_generation: bool,
    updated_at: int = 1762700600000,
    fail_after_update: bool = False,
) -> dict[str, Any]:
    """Giao dịch xác nhận Sửa/Sinh nguyên tử, bảo toàn QuestionVersion cũ khi thay bộ câu."""
    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            job_row = conn.execute(
                """
                SELECT id, base_revision, active, receipt_payload
                FROM ai_jobs
                WHERE id = ? AND owner_id = ? AND origin_exam_id = ?
                """,
                (job_id, owner_id, exam_id),
            ).fetchone()
            if job_row is None or int(job_row["active"]) == 0:
                raise KeyError("proposal_not_found")
            if int(job_row["base_revision"]) != base_revision:
                raise RevisionConflictError(
                    "Đề hoặc nguồn đã thay đổi. Hãy tạo lại đề xuất.",
                    current_revision=int(job_row["base_revision"]),
                )
            if job_row["receipt_payload"] is not None:
                return dict(json.loads(str(job_row["receipt_payload"])))

            ex_row = conn.execute(
                "SELECT revision FROM exams WHERE id = ? AND owner_id = ?",
                (exam_id, owner_id),
            ).fetchone()
            if ex_row is None:
                raise KeyError("exam_not_found")
            current_rev = int(ex_row["revision"])
            if current_rev != base_revision:
                raise RevisionConflictError(
                    "Đề hoặc nguồn đã thay đổi. Hãy tạo lại đề xuất.",
                    current_revision=current_rev,
                )

            # 1. Lưu snapshot đề hiện tại vào exam_versions (history) trước khi ghi đè
            current_state = reconstruct_workspace_state(conn, owner_id)
            old_exam = next(ex for ex in current_state["exams"] if ex["id"] == exam_id)
            seq_row = conn.execute(
                "SELECT COALESCE(MAX(seq_index), -1) + 1 AS next_seq "
                "FROM exam_versions WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()
            next_seq = int(seq_row["next_seq"])
            hist_id = f"hist-{exam_id}-r{base_revision}-{job_id}"
            label = "AI sinh bộ câu mới" if is_generation else "AI cập nhật lời giải câu hỏi"
            conn.execute(
                """
                INSERT INTO exam_versions(
                    id, exam_id, seq_index, revision, label, snapshot_state, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hist_id,
                    exam_id,
                    next_seq,
                    base_revision,
                    label,
                    canonical_json(old_exam),
                    updated_at,
                ),
            )

            # 2. Chuyển các câu đang active của đề sang is_active = 0 trước khi ghi câu mới
            conn.execute(
                """
                UPDATE questions
                SET is_active = 0,
                    archived_at_revision = CASE
                        WHEN ? THEN ?
                        ELSE COALESCE(archived_at_revision, ?)
                    END
                WHERE exam_id = ? AND is_active = 1
                """,
                (1 if is_generation else 0, base_revision, base_revision, exam_id),
            )

            # 3. Ghi câu hỏi mới hoặc câu hỏi vừa sửa và thêm dòng mới vào question_versions
            changed_ids: list[str] = []
            for q_idx, q in enumerate(new_questions):
                _upsert_question_and_version(conn, exam_id, q_idx, q, updated_at)
                changed_ids.append(str(q["id"]))

            next_rev = base_revision + 1
            conn.execute(
                "UPDATE exams SET revision = ?, updated_at = ? WHERE id = ?",
                (next_rev, updated_at, exam_id),
            )

            if fail_after_update:
                raise sqlite3.IntegrityError("Simulated write failure before receipt")

            receipt = {
                "jobId": job_id,
                "examId": exam_id,
                "baseRevision": base_revision,
                "revision": next_rev,
                "changedQuestionIds": changed_ids,
            }
            conn.execute(
                """
                UPDATE ai_jobs
                SET status = 'complete',
                    sequence = 2,
                    receipt_payload = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (canonical_json(receipt), updated_at, job_id),
            )
            return receipt
    finally:
        conn.close()


def get_question_version_history(
    conn: sqlite3.Connection, question_id: str
) -> list[dict[str, Any]]:
    """Đọc toàn bộ lịch sử phiên bản của một câu hỏi (kể cả câu đã archived)."""
    rows = conn.execute(
        """
        SELECT id, question_id, version_number, question_type,
               content_payload, evidence_list, verification_status,
               approval_status, created_at
        FROM question_versions
        WHERE question_id = ?
        ORDER BY version_number ASC
        """,
        (question_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "questionId": r["question_id"],
            "version": int(r["version_number"]),
            "type": r["question_type"],
            "content": json.loads(r["content_payload"]),
            "evidence": json.loads(r["evidence_list"]),
            "verificationStatus": r["verification_status"],
            "approvalStatus": r["approval_status"],
            "createdAt": int(r["created_at"]),
        }
        for r in rows
    ]


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Đếm số bản ghi của cả 15 bảng trong schema BE-3."""
    tables = [
        "app_configs",
        "users",
        "sessions",
        "credit_accounts",
        "credit_ledgers",
        "teacher_preferences",
        "source_documents",
        "exams",
        "questions",
        "exam_versions",
        "question_versions",
        "ai_jobs",
        "share_snapshots",
        "exports",
        "quarantine_legacy_items",
    ]
    return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tables}


def main() -> None:
    parser = argparse.ArgumentParser(description="Di trú bản sao SQLite KV sang kho BE-3.")
    parser.add_argument("--source", required=True, type=Path, help="Đường dẫn DB nguồn chỉ đọc.")
    parser.add_argument("--target", required=True, type=Path, help="Đường dẫn DB đích đã dừng.")
    args = parser.parse_args()
    try:
        result = migrate_legacy_store(args.source, args.target, args.target.parent / "blobs")
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Di trú dừng: {exc}\n")
    print(canonical_json(result))


if __name__ == "__main__":
    main()
