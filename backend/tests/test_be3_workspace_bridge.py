"""Kiểm thử cầu nối WorkspaceStore KV -> BE-3 relational migration, idempotency và rollback."""

import base64
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import pytest

from mach_backend.be3_schema_migration import (
    canonical_json,
    migrate_legacy_store,
    reconstruct_workspace_state,
    sha256_hex,
    table_counts,
)
from mach_backend.workspace_store import WorkspaceStore


def test_workspace_store_migrates_preserving_uuids_richdoc_files_idempotent_and_rollback(tmp_path):
    live_dir = tmp_path / "live_workspace"
    store = WorkspaceStore(live_dir, owner="local")

    exam_id = str(uuid4())
    question_id = str(uuid4())
    block_stem_id = str(uuid4())
    file_id = "nguon-hinh-hoc-01"
    job_id = str(uuid4())

    rich_doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Tính số ô trồng rau tối đa cho diện tích "},
                    {
                        "type": "mathInline",
                        "attrs": {"latex": r"1200\text{ m}^2", "display": False},
                    },
                ],
            }
        ],
    }
    pdf_bytes = b"%PDF-1.4\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n"
    state_value = {
        "exams": [
            {
                "id": exam_id,
                "title": "Đề kiểm thử cầu nối BE-3",
                "subject": "Toán",
                "grade": "5",
                "minutes": 40,
                "revision": 4,
                "docs": [
                    {
                        "fileId": file_id,
                        "name": "nguon-hinh-hoc.pdf",
                        "kind": "pdf",
                        "uploaded": 1700000100,
                    }
                ],
                "questions": [
                    {
                        "id": question_id,
                        "v": 3,
                        "type": "short",
                        "topic": "Hình học",
                        "level": 2,
                        "points": 2.0,
                        "stem": r"Tính số ô trồng rau tối đa cho diện tích $1200\text{ m}^2$.",
                        "richDoc": rich_doc,
                        "options": [],
                        "optionDocs": [],
                        "answer": 0,
                        "answerKnown": True,
                        "answerText": "75",
                        "truthValues": [],
                        "explanation": r"Lấy $1200 : 16 = 75$.",
                        "rubric": [{"text": "Tính đúng cận trên", "points": 2.0}],
                        "formulas": [r"1200:16=75"],
                        "blockIds": {"stem": block_stem_id},
                        "updated": 1700000200,
                    }
                ],
                "updated": 1700000200,
            }
        ],
        "prefs": [
            {
                "id": "pref-1",
                "text": "Giữ rõ đơn vị mét vuông.",
                "kind": "style",
                "maxWords": 120,
                "confirmedAt": 1700000050,
            }
        ],
    }
    store.put("state", state_value)
    store.put(
        f"file:{file_id}",
        "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode(),
    )
    store.put(f"last-job:{exam_id}", job_id)
    store.put(
        f"job:{job_id}",
        {
            "examId": exam_id,
            "baseRevision": 4,
            "status": "complete",
            "plan": {"slots": [{"type": "short", "topic": "Hình học", "level": 3, "pointsQ4": 8}]},
            "questions": [],
            "created": 1700000150,
            "completed": 1700000180,
        },
    )

    live_bytes_before = store.file.read_bytes()
    copy_src = tmp_path / "copy_workspace.sqlite"
    shutil.copy2(store.file, copy_src)
    dst_db = tmp_path / "relational.sqlite"
    blobs_dir = tmp_path / "blobs"

    # Di trú lần 1 trên bản sao.
    assert migrate_legacy_store(copy_src, dst_db, blobs_dir)["ok"] is True
    assert store.file.read_bytes() == live_bytes_before

    with closing(sqlite3.connect(dst_db)) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        counts_first = table_counts(conn)
        assert counts_first["exams"] == 1
        assert counts_first["questions"] == 1
        assert counts_first["question_versions"] == 1
        assert counts_first["source_documents"] == 1
        assert counts_first["ai_jobs"] == 1
        assert counts_first["teacher_preferences"] == 1
        doc_row = conn.execute(
            "SELECT sha256_hash, blob_rel_path, byte_size FROM source_documents WHERE id = ?",
            (file_id,),
        ).fetchone()
        assert doc_row["sha256_hash"] == sha256_hex(pdf_bytes)
        assert doc_row["byte_size"] == len(pdf_bytes)
        assert (Path(blobs_dir.parent) / doc_row["blob_rel_path"]).read_bytes() == pdf_bytes
        rebuilt_first = reconstruct_workspace_state(conn, "local")

    rebuilt_exam = rebuilt_first["exams"][0]
    assert rebuilt_exam["id"] == exam_id
    assert rebuilt_exam["revision"] == 4
    assert rebuilt_exam["questions"][0]["id"] == question_id
    assert rebuilt_exam["questions"][0]["v"] == 3
    assert rebuilt_exam["questions"][0]["richDoc"] == rich_doc
    assert rebuilt_exam["questions"][0]["formulas"] == [r"1200:16=75"]
    assert rebuilt_exam["questions"][0]["blockIds"] == {"stem": block_stem_id}

    # Di trú lần 2 (idempotent): số bảng và canonical JSON không thay đổi.
    assert migrate_legacy_store(copy_src, dst_db, blobs_dir)["ok"] is True
    with closing(sqlite3.connect(dst_db)) as conn:
        conn.row_factory = sqlite3.Row
        assert table_counts(conn) == counts_first
        assert canonical_json(reconstruct_workspace_state(conn, "local")) == canonical_json(
            rebuilt_first
        )

    # Giả lập lỗi giữa chừng sau khi cập nhật bản sao nguồn: DB đích giữ nguyên checksum và dữ liệu.
    dst_bytes_before = dst_db.read_bytes()
    dst_sha_before = sha256_hex(dst_bytes_before)
    updated_exam = dict(state_value["exams"][0], revision=5, title="Bản sửa sẽ rollback")
    with closing(sqlite3.connect(copy_src)) as src_conn, src_conn:
        src_conn.execute(
            "UPDATE kv SET value = ?, rev = rev + 1 WHERE key = 'state'",
            (json.dumps({"exams": [updated_exam], "prefs": state_value["prefs"]}),),
        )

    with pytest.raises(RuntimeError, match="Simulated disk failure"):
        migrate_legacy_store(copy_src, dst_db, blobs_dir, simulate_mid_failure=True)

    assert dst_db.read_bytes() == dst_bytes_before
    assert sha256_hex(dst_db.read_bytes()) == dst_sha_before
    with closing(sqlite3.connect(dst_db)) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert table_counts(conn) == counts_first
        after_fail = reconstruct_workspace_state(conn, "local")
        assert after_fail["exams"][0]["revision"] == 4
        assert after_fail["exams"][0]["title"] == "Đề kiểm thử cầu nối BE-3"
