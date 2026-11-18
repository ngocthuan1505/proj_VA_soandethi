"""Kiểm thử thực nghiệm T01–T05 cho thiết kế schema, migration và hợp đồng BE-3."""

import base64
import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mach_backend.be3_schema_migration import (
    JobConflictError,
    RevisionConflictError,
    canonical_json,
    confirm_patch_or_generation_tx,
    get_question_version_history,
    migrate_legacy_store,
    reconstruct_workspace_state,
    replay_or_register_submission,
    sha256_hex,
    table_counts,
    update_exam_with_occ,
)
from mach_backend.local_workspace import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "be3-legacy-kv.json"
USER_A_ID = "a1000000000000000000000000000001"
USER_B_ID = "b2000000000000000000000000000002"
EXPECTED_STATE_A_SHA256 = "75fe5228d005d4216023c5a24844a06f07abe5d51b1df08429a9db0c071f06c6"
EXPECTED_STATE_B_SHA256 = "51e480ea2462b5445ff24b02666af7b2b4a0a47eda20ef4f898184f8ad78f6da"


def create_legacy_kv_sqlite(db_path: Path, *, include_corrupt: bool = False) -> None:
    """Tạo kho SQLite KV legacy từ bộ fixture JSON chuẩn."""
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = list(fixture["clean_kv_rows"])
    if include_corrupt:
        rows.extend(fixture["corrupt_extra_rows"])

    conn = sqlite3.connect(db_path.as_posix())
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    rev INTEGER NOT NULL DEFAULT 1,
                    updated INTEGER NOT NULL
                )
                """
            )
            for row in rows:
                conn.execute(
                    "INSERT INTO kv(key, value, rev, updated) VALUES (?, ?, ?, ?)",
                    (row["key"], row["value"], int(row["rev"]), int(row["updated"])),
                )
    finally:
        conn.close()


class TestBE3MigrationAndContracts(unittest.TestCase):
    """Kiểm chứng T01, T02, T03 và hai kịch bản mở rộng T04 (QuestionVersion), T05 (Replay)."""

    def test_t01_clean_migration_and_canonical_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_db = root / "clean_workspace.sqlite"
            dst_db = root / "migrated.sqlite"
            blobs_dir = root / "blobs"
            create_legacy_kv_sqlite(src_db, include_corrupt=False)

            migrate_legacy_store(src_db, dst_db, blobs_dir)

            conn = sqlite3.connect(dst_db.as_posix())
            conn.row_factory = sqlite3.Row
            src_conn = sqlite3.connect(src_db.as_posix())
            src_conn.row_factory = sqlite3.Row
            try:
                counts = table_counts(conn)
                self.assertEqual(
                    counts,
                    {
                        "app_configs": 1,
                        "users": 4,
                        "sessions": 2,
                        "credit_accounts": 2,
                        "credit_ledgers": 1,
                        "teacher_preferences": 1,
                        "source_documents": 3,
                        "exams": 2,
                        "questions": 3,
                        "exam_versions": 2,
                        "question_versions": 3,
                        "ai_jobs": 2,
                        "share_snapshots": 2,
                        "exports": 1,
                        "quarantine_legacy_items": 0,
                    },
                )

                blob_files = list(blobs_dir.rglob("*.bin"))
                self.assertEqual(len(blob_files), 2)

                orig_a = json.loads(
                    src_conn.execute(
                        "SELECT value FROM kv WHERE key = ?",
                        (f"u:{USER_A_ID}:state",),
                    ).fetchone()["value"]
                )
                orig_b = json.loads(
                    src_conn.execute(
                        "SELECT value FROM kv WHERE key = ?",
                        (f"u:{USER_B_ID}:state",),
                    ).fetchone()["value"]
                )

                rebuilt_a = reconstruct_workspace_state(conn, USER_A_ID)
                rebuilt_b = reconstruct_workspace_state(conn, USER_B_ID)

                hash_a = sha256_hex(canonical_json(rebuilt_a))
                hash_b = sha256_hex(canonical_json(rebuilt_b))
                self.assertEqual(hash_a, sha256_hex(canonical_json(orig_a)))
                self.assertEqual(hash_b, sha256_hex(canonical_json(orig_b)))
                self.assertEqual(hash_a, EXPECTED_STATE_A_SHA256)
                self.assertEqual(hash_b, EXPECTED_STATE_B_SHA256)
            finally:
                conn.close()
                src_conn.close()

    def test_t02_quarantine_corrupt_items_rollback_and_online_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            corrupt_src = root / "corrupt_workspace.sqlite"
            corrupt_dst = root / "migrated_corrupt.sqlite"
            corrupt_blobs = root / "blobs_corrupt"
            create_legacy_kv_sqlite(corrupt_src, include_corrupt=True)

            migrate_legacy_store(corrupt_src, corrupt_dst, corrupt_blobs)
            conn = sqlite3.connect(corrupt_dst.as_posix())
            conn.row_factory = sqlite3.Row
            try:
                counts = table_counts(conn)
                self.assertEqual(counts["quarantine_legacy_items"], 2)
                self.assertEqual(counts["exams"], 2)
                q_keys = {
                    str(r["legacy_key"])
                    for r in conn.execute("SELECT legacy_key FROM quarantine_legacy_items")
                }
                self.assertEqual(
                    q_keys,
                    {
                        "u:corrupt-user:state",
                        f"u:{USER_A_ID}:file:file-corrupt-b64",
                    },
                )
            finally:
                conn.close()

            # Kiểm tra rollback nguyên tử khi gặp lỗi giữa chừng
            src_sha_before = sha256_hex(corrupt_src.read_bytes())
            rollback_dst = root / "rollback.sqlite"
            rollback_blobs = root / "rollback_blobs"
            with self.assertRaises(RuntimeError):
                migrate_legacy_store(
                    corrupt_src,
                    rollback_dst,
                    rollback_blobs,
                    simulate_mid_failure=True,
                )
            self.assertFalse(rollback_dst.exists())
            self.assertFalse(rollback_blobs.exists())
            self.assertEqual(sha256_hex(corrupt_src.read_bytes()), src_sha_before)

            # Kiểm tra sao lưu nóng qua sqlite3.Connection.backup()
            backup_db = root / "online_backup.sqlite"
            src_c = sqlite3.connect(corrupt_dst.as_posix())
            bck_c = sqlite3.connect(backup_db.as_posix())
            try:
                with bck_c:
                    src_c.backup(bck_c)
                integrity = bck_c.execute("PRAGMA integrity_check").fetchone()[0]
                self.assertEqual(integrity, "ok")
                self.assertEqual(table_counts(bck_c), table_counts(src_c))
            finally:
                bck_c.close()
                src_c.close()

    def test_t03_idempotent_remigration_and_occ_409_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_db = root / "clean_workspace.sqlite"
            dst_db = root / "migrated.sqlite"
            blobs_dir = root / "blobs"
            create_legacy_kv_sqlite(src_db, include_corrupt=False)

            migrate_legacy_store(src_db, dst_db, blobs_dir)
            conn1 = sqlite3.connect(dst_db.as_posix())
            try:
                counts_run1 = table_counts(conn1)
            finally:
                conn1.close()

            # Chạy lại lần 2 trên cùng đích
            migrate_legacy_store(src_db, dst_db, blobs_dir)
            conn2 = sqlite3.connect(dst_db.as_posix())
            try:
                counts_run2 = table_counts(conn2)
                self.assertEqual(counts_run1, counts_run2)

                new_rev = update_exam_with_occ(
                    conn2,
                    "exam-math-001",
                    USER_A_ID,
                    "Đề kiểm tra giữa kì I — Toán 9 (Bản 3)",
                    2,
                )
                self.assertEqual(new_rev, 3)

                with self.assertRaises(RevisionConflictError) as ctx:
                    update_exam_with_occ(
                        conn2,
                        "exam-math-001",
                        USER_A_ID,
                        "Ghi đè từ cửa sổ cũ",
                        2,
                    )
                self.assertEqual(ctx.exception.status, 409)
                self.assertEqual(ctx.exception.current_revision, 3)
            finally:
                conn2.close()

    def test_t04_preserve_question_versions_across_patch_and_regeneration(self) -> None:
        """Chứng minh Q1 v1 -> Q1 v2 -> Sinh bộ mới Q2 vẫn giữ nguyên lịch sử Q1 v1 & v2."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_db = root / "clean_workspace.sqlite"
            dst_db = root / "migrated.sqlite"
            blobs_dir = root / "blobs"
            create_legacy_kv_sqlite(src_db, include_corrupt=False)
            migrate_legacy_store(src_db, dst_db, blobs_dir)

            # Ban đầu q-math-002 đang ở v1, bây giờ bổ sung thêm lịch sử q-math-001 v1
            # hoặc dùng q-math-002 (đang ở v1) -> sửa lời giải lên v2 (có richDoc/explanationDoc)
            conn = sqlite3.connect(dst_db.as_posix())
            conn.row_factory = sqlite3.Row
            try:
                state_before = reconstruct_workspace_state(conn, USER_A_ID)
            finally:
                conn.close()

            exam_math = next(ex for ex in state_before["exams"] if ex["id"] == "exam-math-001")
            q1, q2 = (
                copy.deepcopy(exam_math["questions"][0]),
                copy.deepcopy(exam_math["questions"][1]),
            )
            self.assertEqual(q2["id"], "q-math-002")
            self.assertEqual(q2["v"], 1)

            # Bước 1: Tạo job Sửa lời giải câu q-math-002 từ v1 -> v2 (kèm explanationDoc)
            patch_req = {
                "requestId": "req-patch-q2-v2",
                "baseRevision": 2,
                "request": "Bổ sung giải thích chi tiết đường cao AH",
            }
            replay_or_register_submission(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-patch-q2-v2",
                job_kind="patch",
                request_id="req-patch-q2-v2",
                request_payload=patch_req,
                base_revision=2,
            )

            q2_v2 = copy.deepcopy(q2)
            q2_v2["v"] = 2
            q2_v2["explanation"] = "Đường cao AH = (6 * 8) / 10 = 4,8 cm (đã sửa v2)."
            q2_v2["explanationDoc"] = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Đường cao "},
                            {
                                "type": "mathInline",
                                "attrs": {"latex": "AH = 4,8", "display": False},
                            },
                        ],
                    }
                ],
            }
            receipt_patch = confirm_patch_or_generation_tx(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-patch-q2-v2",
                base_revision=2,
                new_questions=[q1, q2_v2],
                is_generation=False,
            )
            self.assertEqual(receipt_patch["revision"], 3)

            # Bước 2: Đăng ký job Sinh bộ câu mới hoàn toàn (UUID mới q-gen-new-001) ở revision 3
            gen_req = {
                "requestId": "req-gen-rev3",
                "baseRevision": 3,
                "plan": {"subject": "Toán", "grade": "9", "slots": [{"type": "mcq"}]},
            }
            replay_or_register_submission(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-gen-rev3",
                job_kind="generate",
                request_id="req-gen-rev3",
                request_payload=gen_req,
                base_revision=3,
            )

            new_generated_q = copy.deepcopy(q1)
            new_generated_q["id"] = "q-gen-new-001"
            new_generated_q["v"] = 1
            new_generated_q["stem"] = "Câu hỏi mới sinh từ ma trận $\\sqrt{x} = 3$."

            # Giả lập lỗi giữa lúc ghi Sinh đề -> rollback toàn bộ về revision 3 và giữ q2_v2
            with self.assertRaises(sqlite3.IntegrityError):
                confirm_patch_or_generation_tx(
                    dst_db,
                    owner_id=USER_A_ID,
                    exam_id="exam-math-001",
                    job_id="job-gen-rev3",
                    base_revision=3,
                    new_questions=[new_generated_q],
                    is_generation=True,
                    fail_after_update=True,
                )

            conn_check = sqlite3.connect(dst_db.as_posix())
            conn_check.row_factory = sqlite3.Row
            try:
                state_after_rollback = reconstruct_workspace_state(conn_check, USER_A_ID)
                ex_rb = next(
                    ex for ex in state_after_rollback["exams"] if ex["id"] == "exam-math-001"
                )
                self.assertEqual(ex_rb["revision"], 3)
                self.assertEqual(
                    [q["id"] for q in ex_rb["questions"]],
                    ["q-math-001", "q-math-002"],
                )
            finally:
                conn_check.close()

            # Xác nhận Sinh đề thành công (revision 3 -> 4), thay bộ câu bằng q-gen-new-001
            receipt_gen = confirm_patch_or_generation_tx(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-gen-rev3",
                base_revision=3,
                new_questions=[new_generated_q],
                is_generation=True,
            )
            self.assertEqual(receipt_gen["revision"], 4)
            self.assertEqual(receipt_gen["changedQuestionIds"], ["q-gen-new-001"])

            # Gửi lại confirm lần 2 cho cùng job-gen-rev3 sau khi mở lại DB -> trả đúng receipt cũ
            receipt_gen_retry = confirm_patch_or_generation_tx(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-gen-rev3",
                base_revision=3,
                new_questions=[new_generated_q],
                is_generation=True,
            )
            self.assertEqual(receipt_gen_retry, receipt_gen)

            # Bước 3: Mở lại repository, kiểm tra đề hiện hành chỉ có q-gen-new-001,
            # NHƯNG lịch sử question_versions của q-math-002 vẫn còn nguyên cả v1 và v2 + richDoc!
            conn_final = sqlite3.connect(dst_db.as_posix())
            conn_final.row_factory = sqlite3.Row
            try:
                state_final = reconstruct_workspace_state(conn_final, USER_A_ID)
                ex_final = next(ex for ex in state_final["exams"] if ex["id"] == "exam-math-001")
                self.assertEqual(ex_final["revision"], 4)
                self.assertEqual(
                    [q["id"] for q in ex_final["questions"]],
                    ["q-gen-new-001"],
                )
                self.assertEqual(len(ex_final["history"]), 4)

                q2_versions = get_question_version_history(conn_final, "q-math-002")
                self.assertEqual([v["version"] for v in q2_versions], [1, 2])
                self.assertEqual(
                    q2_versions[0]["content"]["richDoc"],
                    q2["richDoc"],
                )
                self.assertIsNone(q2_versions[0]["content"]["explanationDoc"])
                self.assertEqual(
                    q2_versions[1]["content"]["explanationDoc"],
                    q2_v2["explanationDoc"],
                )
                self.assertEqual(
                    q2_versions[1]["content"]["explanation"],
                    q2_v2["explanation"],
                )
            finally:
                conn_final.close()

    def test_t05_persistent_replay_and_cross_operation_conflict_after_restart(self) -> None:
        """Chứng minh sau khi đóng/mở lại SQLite, gửi lặp trả job cũ, đổi nội dung/loại báo 409."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_db = root / "clean_workspace.sqlite"
            dst_db = root / "migrated.sqlite"
            blobs_dir = root / "blobs"
            create_legacy_kv_sqlite(src_db, include_corrupt=False)
            migrate_legacy_store(src_db, dst_db, blobs_dir)

            req_id = "6cdd6c81-8024-4f26-a487-f818f6be71ae"
            patch_payload = {
                "requestId": req_id,
                "baseRevision": 2,
                "consent": True,
                "request": "Viết rõ bước biến đổi tương đương.",
                "targets": [
                    {
                        "questionId": "q-math-001",
                        "questionVersion": 2,
                        "blockId": "blk-q1-exp",
                    }
                ],
            }

            # Lần 1: Tạo job Sửa mới trên kết nối 1 (rồi đóng kết nối bên trong hàm)
            first_sub, is_replay_1 = replay_or_register_submission(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-created-001",
                job_kind="patch",
                request_id=req_id,
                request_payload=patch_payload,
                base_revision=2,
            )
            self.assertFalse(is_replay_1)
            self.assertEqual(first_sub.job_id, "job-created-001")

            # Lần 2 (Sau khi mở lại repository): Cùng owner/đề/requestId/nội dung -> trả đúng job cũ
            replay_sub, is_replay_2 = replay_or_register_submission(
                dst_db,
                owner_id=USER_A_ID,
                exam_id="exam-math-001",
                job_id="job-should-not-be-used",
                job_kind="patch",
                request_id=req_id,
                request_payload=patch_payload,
                base_revision=2,
            )
            self.assertTrue(is_replay_2)
            self.assertEqual(replay_sub.job_id, "job-created-001")
            self.assertEqual(replay_sub.request_digest, first_sub.request_digest)

            # Lần 3: Cùng owner/đề/requestId nhưng đổi nội dung request -> 409 job_conflict
            modified_payload = {**patch_payload, "request": "Nội dung khác hoàn toàn."}
            with self.assertRaises(JobConflictError) as ctx_diff_body:
                replay_or_register_submission(
                    dst_db,
                    owner_id=USER_A_ID,
                    exam_id="exam-math-001",
                    job_id="job-conflict-body",
                    job_kind="patch",
                    request_id=req_id,
                    request_payload=modified_payload,
                    base_revision=2,
                )
            self.assertEqual(ctx_diff_body.exception.status, 409)
            self.assertEqual(ctx_diff_body.exception.code, "job_conflict")

            # Lần 4: Dùng lại cùng requestId đó cho thao tác Sinh thay vì Sửa -> 409 job_conflict
            with self.assertRaises(JobConflictError) as ctx_cross_op:
                replay_or_register_submission(
                    dst_db,
                    owner_id=USER_A_ID,
                    exam_id="exam-math-001",
                    job_id="job-conflict-op",
                    job_kind="generate",
                    request_id=req_id,
                    request_payload=patch_payload,
                    base_revision=2,
                )
            self.assertEqual(ctx_cross_op.exception.status, 409)
            self.assertEqual(ctx_cross_op.exception.code, "job_conflict")


@pytest.fixture
def migrated_store(tmp_path):
    source, target, blobs = (
        tmp_path / "source.sqlite",
        tmp_path / "target.sqlite",
        tmp_path / "blobs",
    )
    create_legacy_kv_sqlite(source)
    migrate_legacy_store(source, target, blobs)
    return source, target, blobs


def test_concurrent_revision_updates_report_one_conflict(migrated_store):
    _, target, _ = migrated_store
    ready = Barrier(2)

    class Connection(sqlite3.Connection):
        def execute(self, sql, params=()):
            if sql.lstrip().startswith("UPDATE exams SET title"):
                ready.wait(timeout=5)
            return super().execute(sql, params)

    def update(title):
        with closing(sqlite3.connect(target, factory=Connection)) as conn:
            try:
                return (
                    "saved",
                    update_exam_with_occ(conn, "exam-math-001", USER_A_ID, title, 2),
                    title,
                )
            except RevisionConflictError as error:
                return "conflict", error.current_revision, title

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["Thay đổi thứ nhất", "Thay đổi thứ hai"]))
    assert sorted((status, revision) for status, revision, _ in results) == [
        ("conflict", 3),
        ("saved", 3),
    ]
    winner = next(title for status, _, title in results if status == "saved")
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute(
            "SELECT title,revision FROM exams WHERE id='exam-math-001'"
        ).fetchone() == (winner, 3)


def test_locked_exam_and_question_statuses_survive_roundtrip(migrated_store, tmp_path):
    source, target, blobs = migrated_store
    with closing(sqlite3.connect(source)) as conn, conn:
        key = f"u:{USER_A_ID}:state"
        state = json.loads(conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()[0])
        exam = state["exams"][0]
        exam["draftStatus"] = "finalized"
        exam["aiInstructions"] = "Giữ đơn vị mét và giải thích từng bước."
        exam["generationRequest"] = "Soạn đề gồm bốn dạng câu hỏi."
        question = exam["questions"][0]
        question.update(
            verificationStatus="review",
            approvalStatus="rejected",
            evidence=[{"quote": "Trích đoạn tổng hợp chỉ dùng để thử."}],
        )
        conn.execute("UPDATE kv SET value=? WHERE key=?", (json.dumps(state), key))
    migrate_legacy_store(source, target, blobs)
    with closing(sqlite3.connect(target)) as conn:
        conn.row_factory = sqlite3.Row
        rebuilt_state = reconstruct_workspace_state(conn, USER_A_ID)
    assert rebuilt_state["exams"][0] == exam
    with TestClient(
        create_app(tmp_path / "fastapi"), headers={"Origin": "http://testserver"}
    ) as client:
        key = "/api/kv"
        saved = client.put(
            key, headers={"If-Match": "0"}, json={"key": "state", "value": rebuilt_state}
        )
        assert saved.json() == {"revision": 1}
        assert client.get(key, params={"key": "state"}).json()["value"] == state


def test_migration_opens_a_path_with_uri_characters_and_keeps_source(tmp_path):
    source = tmp_path / "Kho #mẫu %.sqlite"
    create_legacy_kv_sqlite(source)
    before = source.read_bytes()
    assert migrate_legacy_store(source, tmp_path / "target.sqlite", tmp_path / "blobs")["ok"]
    with pytest.raises(ValueError, match="Chọn kho đích khác"):
        migrate_legacy_store(source, source, tmp_path / "blobs")
    assert source.read_bytes() == before


@pytest.mark.parametrize("collision_kind", ["exam", "question"])
def test_migration_rejects_duplicate_ids_across_workspaces(migrated_store, collision_kind):
    source, target, blobs = migrated_store
    before = target.read_bytes()
    with closing(sqlite3.connect(source)) as conn, conn:
        key_a = f"u:{USER_A_ID}:state"
        key_b = f"u:{USER_B_ID}:state"
        state_a = json.loads(
            conn.execute("SELECT value FROM kv WHERE key=?", (key_a,)).fetchone()[0]
        )
        state_b = json.loads(
            conn.execute("SELECT value FROM kv WHERE key=?", (key_b,)).fetchone()[0]
        )
        exam_a, exam_b = state_a["exams"][0], state_b["exams"][0]
        if collision_kind == "exam":
            exam_b["id"] = state_b["current"] = exam_a["id"]
        else:
            exam_b["questions"][0]["id"] = exam_a["questions"][0]["id"]
        conn.execute("UPDATE kv SET value=? WHERE key=?", (json.dumps(state_b), key_b))

    with pytest.raises(sqlite3.IntegrityError, match="Trùng mã"):
        migrate_legacy_store(source, target, blobs)

    assert target.read_bytes() == before


@pytest.mark.parametrize("failure", ["blob", "database"])
def test_failed_publication_preserves_existing_store(migrated_store, monkeypatch, failure):
    source, target, blobs = migrated_store
    before_db = target.read_bytes()
    before_blobs = {p.relative_to(blobs): p.read_bytes() for p in blobs.rglob("*.bin")}
    added_data = b"PDF synthetic contents for migration publication test"
    with closing(sqlite3.connect(source)) as conn, conn:
        value = "data:application/pdf;base64," + base64.b64encode(added_data).decode()
        conn.execute(
            "INSERT INTO kv VALUES(?,?,1,0)",
            (f"u:{USER_A_ID}:file:publication-test", json.dumps(value)),
        )
    replace = Path.replace
    reached_failure = False

    def failing_replace(path, destination):
        nonlocal reached_failure
        is_database = path == target.with_suffix(".tmp.sqlite")
        is_blob = path.suffix == ".bin" or path == blobs.with_name("blobs_tmp")
        if (failure == "database" and is_database) or (failure == "blob" and is_blob):
            reached_failure = True
            raise OSError("Lỗi công bố bản di trú giả lập.")
        return replace(path, destination)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "replace", failing_replace)
        with pytest.raises(OSError, match="giả lập"):
            migrate_legacy_store(source, target, blobs)
    assert reached_failure
    assert target.read_bytes() == before_db
    for relative, contents in before_blobs.items():
        assert (blobs / relative).read_bytes() == contents
    with closing(sqlite3.connect(target)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM source_documents WHERE id='publication-test'"
            ).fetchone()[0]
            == 0
        )

    migrate_legacy_store(source, target, blobs)
    with closing(sqlite3.connect(target)) as conn:
        relative = conn.execute(
            "SELECT blob_rel_path FROM source_documents WHERE id='publication-test'"
        ).fetchone()[0]
    assert (blobs.parent / relative).read_bytes() == added_data


if __name__ == "__main__":
    unittest.main()
