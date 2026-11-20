"""Kho workspace cục bộ tương thích dữ liệu bàn soạn hiện có."""

import json
import sqlite3
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

from mach_backend.ai_contract import AIError, SourceFragment
from mach_backend.ai_questions import GenerationPlan
from mach_backend.ai_sources import workspace_page_sources
from mach_backend.matrix_agent import sha256_json
from mach_backend.patch_confirmation import (
    ConfirmationState,
    PatchReceipt,
    PendingGeneration,
    changed_snapshot,
)
from mach_backend.poc_policy import CHECK_NAMES


class WorkspaceStore:
    def __init__(self, directory: Path, *, owner="local"):
        directory.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        self.file = directory / "workspace.sqlite"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS kv
                    (key TEXT PRIMARY KEY, value TEXT NOT NULL, rev INTEGER NOT NULL DEFAULT 1,
                     updated INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS matrix_pending
                    (job_id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL,
                     receipt TEXT, reviews TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS matrix_trace
                    (job_id TEXT NOT NULL, ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
                     payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.file, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, key: str, db=None) -> dict[str, Any]:
        if db is None:
            with self.connect() as connection:
                return self.get(key, connection)
        row = db.execute("SELECT value,rev FROM kv WHERE key=?", (key,)).fetchone()
        return (
            {"value": json.loads(row[0]), "revision": row[1]}
            if row
            else {"value": None, "revision": 0}
        )

    def put(
        self, key: str, value: Any, base: int | None = None, db=None, *, skip_unchanged=False
    ) -> int:
        if db is None:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                return self.put(key, value, base, connection, skip_unchanged=skip_unchanged)
        current = db.execute("SELECT value,rev FROM kv WHERE key=?", (key,)).fetchone()
        revision = current[1] if current else 0
        if base is not None and revision != base:
            raise changed_snapshot()
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if skip_unchanged and current and current[0] == encoded:
            return revision
        revision += 1
        db.execute(
            "INSERT INTO kv VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "value=excluded.value,rev=excluded.rev,updated=excluded.updated",
            (
                key,
                encoded,
                revision,
                int(time.time() * 1000),
            ),
        )
        return revision

    def exam(self, exam_id: UUID | str, db=None):
        state = self.get("state", db)["value"]
        if not isinstance(state, dict):
            raise AIError("exam_not_found", "Chưa có workspace để sinh đề.")
        exam = next((e for e in state.get("exams", []) if e.get("id") == str(exam_id)), None)
        if exam is None:
            raise AIError("exam_not_found", "Không tìm thấy đề đang mở.")
        return state, exam

    def plan(self, exam_id, db=None):
        value = self.get("matrix:" + str(exam_id), db)["value"]
        return GenerationPlan.model_validate_json(json.dumps(value)) if value else None

    def sources(self, exam_id, db=None):
        value = self.get("matrix-source:" + str(exam_id), db)["value"] or []
        return tuple(SourceFragment.model_validate_json(json.dumps(s)) for s in value)

    def current_sources(self, exam, db):
        approved = self.sources(exam["id"], db)
        keys = tuple(
            (source.sourceId, source.locator)
            for source in approved
            if source.locator.kind == "page"
        )
        if not keys:
            return approved
        actual = workspace_page_sources(exam, self.owner, keys, db)
        pages = {(source.sourceId, source.locator): source for source in actual}
        if any(
            source.locator.kind == "page" and pages.get((source.sourceId, source.locator)) != source
            for source in approved
        ):
            raise AIError("stale_snapshot", "Nguồn đã đổi. Hãy duyệt lại ma trận.")
        return approved

    async def is_current(self, job) -> bool:
        with self.connect() as db:
            db.execute("BEGIN")
            _, exam = self.exam(job.examId, db)
            plan = self.plan(job.examId, db)
            try:
                return (
                    exam["revision"] == job.baseRevision
                    and plan is not None
                    and plan.model_dump()
                    == job.model_dump(include=set(GenerationPlan.model_fields))
                    and self.current_sources(exam, db) == job.sources
                )
            except AIError:
                return False

    async def store_pending(self, pending) -> bool:
        if not isinstance(pending, PendingGeneration):
            return False
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            _, exam = self.exam(pending.job.examId, db)
            try:
                if (
                    exam["revision"] != pending.job.baseRevision
                    or self.current_sources(exam, db) != pending.job.sources
                ):
                    return False
            except AIError:
                return False
            db.execute(
                "INSERT INTO matrix_pending(job_id,owner,payload) VALUES(?,?,?)",
                (str(pending.job.jobId), pending.job.ownerId, pending.model_dump_json()),
            )
        return True

    def trace(self, job_id, entry=None):
        with self.connect() as db:
            if entry is not None:
                db.execute(
                    "INSERT INTO matrix_trace(job_id,payload) VALUES(?,?)",
                    (str(job_id), json.dumps(entry, ensure_ascii=False)),
                )
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM matrix_trace WHERE job_id=? ORDER BY ordinal",
                    (str(job_id),),
                )
            ]

    def review(
        self,
        owner,
        job_id,
        ordinal: int,
        observed: int,
        reason: str,
        content_ok: bool,
        reviewer: str,
    ):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,reviews,receipt FROM matrix_pending WHERE job_id=? AND owner=?",
                (str(job_id), owner),
            ).fetchone()
            if row is None or row[2] is not None:
                raise AIError("proposal_not_found", "Đề xuất không còn ở bước rà.")
            pending = PendingGeneration.model_validate_json(row[0])
            if not 0 <= ordinal < len(pending.proposal.questions):
                raise AIError("invalid_request", "Không có câu cần rà.")
            reviews = json.loads(row[1])
            reviews[str(ordinal)] = {
                "observed": observed,
                "reason": reason,
                "contentOk": content_ok,
                "reviewer": reviewer,
            }
            db.execute(
                "UPDATE matrix_pending SET reviews=? WHERE job_id=?",
                (json.dumps(reviews, ensure_ascii=False), str(job_id)),
            )
            return reviews

    def prior_feedback(self, exam_id, source_text, db):
        for payload, raw_reviews in db.execute(
            "SELECT payload,reviews FROM matrix_pending WHERE owner=? ORDER BY rowid DESC LIMIT 20",
            (self.owner,),
        ):
            pending = PendingGeneration.model_validate_json(payload)
            if (
                str(pending.job.examId) != str(exam_id)
                or "\n\n".join(s.text for s in pending.job.sources) != source_text
            ):
                continue
            reviews = json.loads(raw_reviews)
            feedback = [
                {
                    "question": pending.proposal.questions[int(i)].stem,
                    "requested": pending.proposal.questions[int(i)].level,
                    **review,
                }
                for i, review in reviews.items()
                if review["observed"] != pending.proposal.questions[int(i)].level
                or not review.get("contentOk", False)
            ]
            return feedback
        return []

    @contextmanager
    def transaction(self, owner_id, exam_id, job_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            yield WorkspaceTransaction(self, db, owner_id, exam_id, job_id)

    def discard(self, owner_id, exam_id, job_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,receipt FROM matrix_pending WHERE job_id=? AND owner=?",
                (str(job_id), owner_id),
            ).fetchone()
            if row is None or PendingGeneration.model_validate_json(row[0]).job.examId != exam_id:
                raise AIError("proposal_not_found", "Không tìm thấy đề xuất của đề này.")
            if row[1] is not None:
                raise AIError("already_saved", "Đề xuất đã được lưu. Dùng Hoàn tác nếu cần.")
            self.put("matrix-discarded:" + str(job_id), True, db=db)
        return {"discarded": True, "saved": False}


class WorkspaceTransaction:
    def __init__(self, store, db, owner, exam_id, job_id):
        self.store, self.db = store, db
        self.owner, self.exam_id, self.job_id = owner, exam_id, job_id

    def read(self):
        if self.store.get("matrix-discarded:" + str(self.job_id), self.db)["value"]:
            raise AIError("proposal_discarded", "Đề xuất đã bị bỏ. Hãy tạo lượt mới.")
        row = self.db.execute(
            "SELECT payload,receipt,reviews FROM matrix_pending WHERE job_id=? AND owner=?",
            (str(self.job_id), self.owner),
        ).fetchone()
        if row is None:
            return None
        pending = PendingGeneration.model_validate_json(row[0])
        receipt = PatchReceipt.model_validate_json(row[1]) if row[1] else None
        if receipt is None:
            agent_result = self.store.get("matrix-agent-result:" + str(self.job_id), self.db)[
                "value"
            ]
            report = agent_result.get("report", {}) if isinstance(agent_result, dict) else {}
            checks = report.get("checks")
            if checks is not None and (
                not isinstance(checks, list)
                or len(checks) != len(CHECK_NAMES)
                or any(not isinstance(r, dict) for r in checks)
                or not isinstance(report.get("candidateHash"), str)
                or len(report["candidateHash"]) != 64
                or {r.get("toolName") for r in checks} != set(CHECK_NAMES)
                or not all(
                    r.get("status") == "PASS"
                    and r.get("candidateHash") == report.get("candidateHash")
                    for r in checks
                )
            ):
                raise AIError(
                    "needs_review", "Báo cáo kiểm còn thiếu, chưa đạt hoặc thuộc bản đề khác."
                )
            agent_checked = (
                isinstance(agent_result, dict)
                and agent_result.get("status") == "ready_for_teacher_review"
                and agent_result.get("report", {}).get("ok") is True
                and agent_result.get("proposalSha256")
                == sha256_json(pending.proposal.model_dump(mode="json"))
            )
            reviews = json.loads(row[2])
            manual_checked = len(reviews) == len(pending.proposal.questions) and all(
                reviews.get(str(i), {}).get("observed") == q.level
                and reviews.get(str(i), {}).get("contentOk", False)
                for i, q in enumerate(pending.proposal.questions)
            )
            manual_rejected = any(
                reviews.get(str(i), {}).get("observed") != q.level
                or not reviews.get(str(i), {}).get("contentOk", False)
                for i, q in enumerate(pending.proposal.questions)
                if str(i) in reviews
            )
            if manual_rejected or not (agent_checked or manual_checked):
                raise AIError(
                    "needs_review", "Rà đủ từng câu và xử lý mức chưa phù hợp trước khi lưu."
                )
        _, exam = self.store.exam(self.exam_id, self.db)
        return ConfirmationState(
            self.owner,
            pending,
            exam,
            self.store.sources(self.exam_id, self.db)
            if receipt
            else self.store.current_sources(exam, self.db),
            receipt,
            self.store.plan(self.exam_id, self.db),
        )

    def write(self, exam, receipt):
        state, before = self.store.exam(self.exam_id, self.db)
        old = deepcopy({k: v for k, v in before.items() if k not in {"history", "undo", "redo"}})
        exam["undo"] = [*before.get("undo", []), {"label": "Sinh theo ma trận", "state": old}][-60:]
        exam["redo"] = []
        exam["updated"] = int(time.time() * 1000)
        # Yêu cầu sinh của PoC chứa tiêu chí cho AI, không phải lời dặn thí sinh.
        neutral = "Đọc kỹ và làm theo yêu cầu của từng câu."
        exam["instructions"] = before.get("instructions", neutral)
        legacy_defaults = {
            "Thí sinh chọn một phương án đúng cho mỗi câu hỏi.",
            "Chọn một phương án đúng cho mỗi câu hỏi.",
            (
                "Chọn một phương án đúng cho mỗi câu hỏi. Các phương trình được "
                "xét trên tập số thực ℝ."
            ),
        }
        kinds = {q["type"] for q in exam["questions"]}
        if exam["instructions"] == neutral or (
            kinds != {"mcq"} and exam["instructions"] in legacy_defaults
        ):
            guidance = {
                "mcq": "Chọn một phương án đúng ở mỗi câu nhiều lựa chọn.",
                "truefalse": "Đánh giá đúng/sai từng nhận định.",
                "short": "Điền đáp án ở phần trả lời ngắn.",
                "essay": "Trình bày lời giải ở phần tự luận.",
            }
            exam["instructions"] = " ".join(
                text for kind, text in guidance.items() if kind in kinds
            )
        documents = exam.setdefault("docs", [])
        sources = self.store.sources(self.exam_id, self.db)
        for source in sources:
            if not any(doc.get("id") == str(source.sourceId) for doc in documents):
                documents.append(
                    {
                        "id": str(source.sourceId),
                        "kind": "text",
                        "version": source.sourceVersion,
                        "name": self.store.get("matrix-source-name:" + str(self.exam_id), self.db)[
                            "value"
                        ],
                        "text": source.text,
                        "pages": [{"number": source.locator.index, "text": source.text}],
                    }
                )
        if sources:
            exam["quote"] = {
                "text": "\n\n".join(source.text for source in sources),
                "chosen": None,
                "versions": [
                    {
                        "id": str(source.sourceId),
                        "label": "Nguồn dùng sinh bộ câu",
                        "text": source.text,
                        "docId": str(source.sourceId),
                        "location": "Đoạn " + str(source.locator.index),
                    }
                    for source in sources
                ],
            }
        for q in exam["questions"]:
            evidence = q.get("evidence", [])
            q["source"] = (
                {
                    "docId": evidence[0]["sourceId"],
                    "page": evidence[0]["locator"]["index"],
                    "location": "Đoạn nguồn " + str(evidence[0]["locator"]["index"]),
                    "quote": evidence[0]["quote"],
                }
                if evidence
                else None
            )
            q.setdefault("figure", None)
            q.setdefault("dataRefs", [])
        exam["history"] = [
            *before.get("history", []),
            {
                "id": str(receipt.jobId),
                "label": "Sinh theo ma trận · giáo viên xác nhận",
                "at": exam["updated"],
                "revision": exam["revision"],
                "state": deepcopy(
                    {k: v for k, v in exam.items() if k not in {"history", "undo", "redo"}}
                ),
            },
        ][-100:]
        state["exams"] = [exam if e["id"] == str(self.exam_id) else e for e in state["exams"]]
        self.store.put("state", state, db=self.db)
        self.db.execute(
            "UPDATE matrix_pending SET receipt=? WHERE job_id=?",
            (receipt.model_dump_json(), str(self.job_id)),
        )
