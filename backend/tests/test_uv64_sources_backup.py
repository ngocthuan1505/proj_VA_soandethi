"""Kiểm chứng UV64 miền A: thu hồi nguồn, cô lập assistantSources, sao lưu và chẩn đoán AGY."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sqlite3
import zipfile
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.agy_cli_model import AgyCliModel, normalize_agy_json_schema
from mach_backend.ai_contract import AIError
from mach_backend.ai_router import (
    FixedTaskRouter,
    attach_error_diagnostic,
    diagnose_invalid_response,
    get_error_diagnostic,
)
from mach_backend.auto_create import AutoCreateRequest, _collect_sources_for_request
from mach_backend.curriculum_sources import SCHEMA_DDL
from mach_backend.hybrid_retrieval import (
    ensure_hybrid_schema,
    index_document_chunks,
    search_hybrid_chunks,
)
from mach_backend.local_workspace import create_app
from mach_backend.poc_matrix import RunLog
from mach_backend.source_policy import (
    CITABLE_LICENSE_STATUSES,
    filter_allowed_docs_for_hybrid,
    is_source_revoked,
    require_citable_source,
)
from mach_backend.workspace_backup import EXAM_EXPORTS_NOTICE, check_file

ORIGIN = {"Origin": "http://testserver"}


def _data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _make_exam(
    exam_id: str | None = None, *, docs: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    eid = exam_id or str(uuid4())
    return {
        "id": eid,
        "revision": 1,
        "title": "Đề kiểm tra Vật lí 10",
        "subject": "Vật lí",
        "grade": "10",
        "minutes": 45,
        "matrixConfirmed": True,
        "strictTeacherOnly": False,
        "matrix": [{"topic": "Động lực học", "targets": [1, 0, 0, 0]}],
        "docs": docs or [],
        "history": [],
        "undo": [],
        "redo": [],
        "chat": [],
        "data": [],
        "quote": {"text": "", "versions": []},
        "questions": [
            {
                "id": str(uuid4()),
                "type": "mcq",
                "topic": "Động lực học",
                "level": 0,
                "points": 1.0,
                "stem": "Đơn vị của lực trong hệ SI là gì?",
                "options": ["N", "J", "W", "m"],
                "answer": 0,
                "explanation": "Lực đo bằng N.",
            }
        ],
    }


def _make_minimal_pptx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        zf.writestr("ppt/presentation.xml", '<?xml version="1.0"?><p:presentation/>')
        zf.writestr("ppt/slides/slide1.xml", '<?xml version="1.0"?><p:sld>Slide 1</p:sld>')
    return buf.getvalue()


def test_source_policy_blocks_revoked_records_even_with_stale_allowed_snapshot(tmp_path):
    """Nguồn thu hồi bị chặn ở mọi đầu vào, nhưng tài liệu cục bộ không bị thu hồi vẫn dùng được."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_DDL)
    ensure_hybrid_schema(conn)

    revoked_pending = str(uuid4())
    revoked_restricted = str(uuid4())
    allowed_src = str(uuid4())
    local_pdf_id = str(uuid4())

    for idx, (sid, status, text) in enumerate(
        (
            (revoked_pending, "pending_review", "Tài liệu chờ duyệt thu hồi về quang hợp."),
            (revoked_restricted, "restricted", "Tài liệu hạn chế về hô hấp tế bào."),
            (allowed_src, "allowed", "Tài liệu SGK hợp lệ về lực ma sát."),
        ),
        start=1,
    ):
        conn.execute(
            """
            INSERT INTO curriculum_sources (
                id, owner_id, grade, subject, series, volume, chapter, lesson,
                title, license_status, license_note, source_origin, locator,
                content_excerpt, sha256, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                "teacher-a",
                8,
                "Khoa học tự nhiên",
                "Kết nối tri thức",
                "1",
                f"Chương {idx}",
                f"Bài {idx}",
                f"Nguồn {idx}",
                status,
                "",
                "lesson_catalog",
                "Trang 1",
                text,
                f"sha-{idx}",
                1000,
                1000,
            ),
        )
    conn.commit()

    assert "allowed" in CITABLE_LICENSE_STATUSES
    assert "teacher_owned" in CITABLE_LICENSE_STATUSES
    assert is_source_revoked({"id": revoked_pending, "licenseStatus": "allowed"}, db=conn) is True
    assert (
        is_source_revoked({"sourceId": revoked_restricted, "license_status": "allowed"}, db=conn)
        is True
    )
    assert is_source_revoked({"id": allowed_src, "licenseStatus": "allowed"}, db=conn) is False
    # Tài liệu cục bộ do GV tự upload không nằm trong curriculum_sources vẫn được phép dùng.
    assert is_source_revoked({"id": local_pdf_id, "name": "De_cu_GV.pdf"}, db=conn) is False

    with pytest.raises(AIError) as exc_info:
        require_citable_source(
            {"originSourceId": revoked_pending, "licenseStatus": "allowed"}, db=conn
        )
    assert exc_info.value.code == "source_license_restricted"
    assert exc_info.value.http_status == 403

    exam_docs = [
        {
            "id": str(uuid4()),
            "originSourceId": revoked_pending,
            "name": "Ban_sao_thu_hoi.pdf",
            "licenseStatus": "allowed",
            "version": 1,
            "pages": [{"number": 1, "text": "Quang hợp xảy ra tại lục lạp."}],
        },
        {
            "id": local_pdf_id,
            "name": "Tai_lieu_cuc_bo.pdf",
            "version": 1,
            "pages": [{"number": 1, "text": "Quang hợp ở lá xanh giúp tạo tinh bột."}],
        },
    ]
    index_document_chunks(
        conn,
        owner_id="teacher-a",
        doc_id=exam_docs[0]["id"],
        pages=exam_docs[0]["pages"],
        version=1,
        title=exam_docs[0]["name"],
    )
    index_document_chunks(
        conn,
        owner_id="teacher-a",
        doc_id=exam_docs[1]["id"],
        pages=exam_docs[1]["pages"],
        version=1,
        title=exam_docs[1]["name"],
    )

    filtered = filter_allowed_docs_for_hybrid(
        conn,
        [
            (revoked_pending, None),
            (revoked_restricted, None),
            (local_pdf_id, None),
        ],
    )
    assert [entry[0] for entry in filtered] == [local_pdf_id]

    hits = search_hybrid_chunks(
        conn,
        owner_id="teacher-a",
        query="quang hợp tinh bột",
        allowed_docs=filtered,
    )
    assert hits
    assert all((hit.get("docId") or hit.get("doc_id")) == local_pdf_id for hit in hits)


def test_revoked_curriculum_source_blocked_across_chat_stream_and_matrix_approve(tmp_path):
    """Chặn nguồn pending_review/restricted trên /chat, /chat/stream và /matrix/approve."""
    calls = 0

    async def fake_agent(_purpose, _body):
        nonlocal calls
        calls += 1
        return {"content": json.dumps({"message": "OK"}), "provider": "fixture"}

    app = create_app(tmp_path, agent_call=fake_agent)
    local_pdf_id = str(uuid4())

    with TestClient(app, headers=ORIGIN) as client:
        created = client.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 8,
                "subject": "Ngữ văn",
                "title": "Bài học sẽ bị thu hồi",
                "license_status": "allowed",
                "content_excerpt": "Nội dung bài học mẫu được cấp phép ban đầu.",
            },
        )
        assert created.status_code == 201, created.text
        src_id = created.json()["id"]

        client.patch(
            f"/api/lesson-catalog/sources/{src_id}",
            json={"license_status": "pending_review"},
        ).raise_for_status()

        exam = _make_exam(
            docs=[
                {
                    "id": src_id,
                    "name": "SGK_da_thu_hoi.pdf",
                    "licenseStatus": "allowed",
                    "version": 1,
                    "pages": [{"number": 1, "text": "Bản chụp cũ trong đề vẫn ghi allowed."}],
                },
                {
                    "id": local_pdf_id,
                    "name": "Giao_an_GV.pdf",
                    "version": 1,
                    "pages": [
                        {"number": 1, "text": "Định luật vạn vật hấp dẫn và gia tốc rơi tự do."}
                    ],
                },
            ]
        )
        exam["assistantSources"] = [src_id]
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()

        # 1. request.context mang nguồn đã thu hồi -> 403
        r_ctx = client.post(
            "/api/assistant/chat",
            json={
                "text": "Tóm tắt bài học này",
                "examId": exam["id"],
                "consent": True,
                "context": [
                    {
                        "kind": "attached-source",
                        "id": src_id,
                        "sourceId": src_id,
                        "pageNumber": 1,
                        "excerpt": "Bản chụp trong request context.",
                    }
                ],
            },
        )
        assert r_ctx.status_code == 403
        assert r_ctx.json()["code"] == "source_license_restricted"

        # 2. exam.assistantSources trỏ vào nguồn thu hồi -> 403 trên cả /chat và /chat/stream
        r_chat = client.post(
            "/api/assistant/chat",
            json={"text": "Tóm tắt bài học đã chọn", "examId": exam["id"], "consent": True},
        )
        assert r_chat.status_code == 403
        assert r_chat.json()["code"] == "source_license_restricted"

        r_stream = client.post(
            "/api/assistant/chat/stream",
            json={"text": "Tóm tắt bài học đã chọn", "examId": exam["id"], "consent": True},
        )
        assert r_stream.status_code == 403
        assert r_stream.json()["code"] == "source_license_restricted"

        # 3. /matrix/approve mang nguồn thu hồi -> 403
        r_approve = client.post(
            f"/api/exams/{exam['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceName": "Nguồn thu hồi",
                "sourceText": "",
                "sources": [
                    {
                        "sourceId": src_id,
                        "sourceVersion": 1,
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert r_approve.status_code == 403
        assert r_approve.json()["code"] == "source_license_restricted"
        assert calls == 0

        # 4. Đổi assistantSources sang tài liệu cục bộ của GV -> cho phép 200 OK
        exam["assistantSources"] = [local_pdf_id]
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
        ).raise_for_status()
        r_local = client.post(
            "/api/assistant/chat",
            json={
                "text": "Tóm tắt định luật vạn vật hấp dẫn",
                "examId": exam["id"],
                "consent": True,
            },
        )
        assert r_local.status_code == 200, r_local.text
        assert calls == 1


def test_empty_assistant_sources_vs_none_isolation_in_chat_and_stream(tmp_path):
    """Phân biệt assistantSources == [] (không fallback exam.docs) với None."""
    captured: list[dict[str, Any]] = []

    async def fake_agent(_purpose, body):
        captured.append(body)
        return {"content": json.dumps({"message": "Đã trả lời."}), "provider": "fixture"}

    app = create_app(tmp_path, agent_call=fake_agent)
    doc_id = str(uuid4())
    secret_text = "NOI_DUNG_BI_MAT_TRONG_EXAM_DOCS_KHONG_DUOC_LO"
    exam = _make_exam(
        docs=[
            {
                "id": doc_id,
                "name": "Nguon_cu.pdf",
                "version": 1,
                "pages": [{"number": 1, "text": f"Chuyên đề động lực học: {secret_text}."}],
            }
        ]
    )
    exam["assistantSources"] = []

    with TestClient(app, headers=ORIGIN) as client:
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()

        with client.app.state.store.connect() as db:
            ensure_hybrid_schema(db)
            index_document_chunks(
                db,
                owner_id=client.app.state.store.owner,
                doc_id=doc_id,
                pages=exam["docs"][0]["pages"],
                version=1,
                title=exam["docs"][0]["name"],
            )
            db.commit()

        r_empty_chat = client.post(
            "/api/assistant/chat",
            json={
                "text": "Hãy nêu NOI_DUNG_BI_MAT trong chuyên đề động lực học",
                "examId": exam["id"],
                "consent": True,
            },
        )
        assert r_empty_chat.status_code == 200, r_empty_chat.text
        assert secret_text not in json.dumps(captured[-1]["messages"], ensure_ascii=False)

        captured.clear()
        r_empty_stream = client.post(
            "/api/assistant/chat/stream",
            json={
                "text": "Hãy nêu NOI_DUNG_BI_MAT trong chuyên đề động lực học",
                "examId": exam["id"],
                "consent": True,
            },
        )
        assert r_empty_stream.status_code == 200, r_empty_stream.text
        assert secret_text not in json.dumps(captured[-1]["messages"], ensure_ascii=False)

        # Khi assistantSources == None thì fallback lấy exam.docs bình thường.
        captured.clear()
        exam["assistantSources"] = None
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
        ).raise_for_status()
        r_none_chat = client.post(
            "/api/assistant/chat",
            json={
                "text": "Hãy nêu NOI_DUNG_BI_MAT trong chuyên đề động lực học",
                "examId": exam["id"],
                "consent": True,
            },
        )
        assert r_none_chat.status_code == 200, r_none_chat.text
        assert secret_text in json.dumps(captured[-1]["messages"], ensure_ascii=False)


def test_auto_create_collect_sources_and_local_single_turn_consent(tmp_path):
    """_collect_sources_for_request không chèn thừa nguồn/trang và consent cục bộ giữ nguyên kho."""
    doc_a = str(uuid4())
    doc_b = str(uuid4())
    revoked_id = str(uuid4())

    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_DDL)
    conn.execute(
        """
        INSERT INTO curriculum_sources (
            id, owner_id, grade, subject, series, volume, chapter, lesson,
            title, license_status, license_note, source_origin, locator,
            content_excerpt, sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revoked_id,
            "teacher-1",
            10,
            "Vật lí",
            "CTST",
            "1",
            "C1",
            "B1",
            "Nguồn thu hồi",
            "restricted",
            "",
            "lesson_catalog",
            "Trang 1",
            "Nội dung thu hồi",
            "sha-r",
            1000,
            1000,
        ),
    )
    conn.commit()

    exam = _make_exam(
        docs=[
            {
                "id": doc_a,
                "name": "Tai_lieu_A.pdf",
                "version": 3,
                "pages": [
                    {"number": 1, "text": "TRANG_1_KHONG_CHON"},
                    {"number": 2, "text": "TRANG_2_DUOC_CHON"},
                ],
            },
            {
                "id": doc_b,
                "name": "Tai_lieu_B.pdf",
                "version": 1,
                "pages": [{"number": 1, "text": "TAI_LIEU_B_KHONG_CHON"}],
            },
        ]
    )

    # 1. assistantSources == [] và body.sources trống -> 0 nguồn
    exam_empty = {**exam, "assistantSources": []}
    assert (
        _collect_sources_for_request(AutoCreateRequest(prompt="Soạn đề"), exam_empty, db=conn) == []
    )

    # 2. assistantSources == [doc_a] và assistantSourcePages == {doc_a: [2]} -> chỉ lấy trang 2
    exam_p2 = {**exam, "assistantSources": [doc_a], "assistantSourcePages": {doc_a: [2]}}
    frags_p2 = _collect_sources_for_request(AutoCreateRequest(prompt="Soạn đề"), exam_p2, db=conn)
    assert len(frags_p2) == 1
    assert frags_p2[0]["page"] == 2
    assert frags_p2[0]["version"] == 3
    assert "TRANG_2_DUOC_CHON" in frags_p2[0]["text"]
    assert all("TAI_LIEU_B" not in f["text"] and "TRANG_1" not in f["text"] for f in frags_p2)

    # 3. body.sources đã có dữ liệu -> không tự chèn thêm trang/tài liệu khác từ exam.docs
    body_custom = AutoCreateRequest(
        prompt="Soạn đề",
        sources=[{"docId": doc_a, "docName": "Tai_lieu_A.pdf", "page": 1, "text": "CHI_TRANG_1"}],
    )
    frags_custom = _collect_sources_for_request(body_custom, exam, db=conn)
    assert len(frags_custom) == 1
    assert frags_custom[0]["page"] == 1
    assert frags_custom[0]["text"] == "CHI_TRANG_1"

    # 4. body.sources chứa nguồn bị thu hồi -> bị chặn 403
    with pytest.raises(AIError) as exc_rev:
        _collect_sources_for_request(
            AutoCreateRequest(
                prompt="Soạn đề",
                sources=[{"docId": revoked_id, "page": 1, "text": "Nội dung thu hồi"}],
            ),
            exam,
            db=conn,
        )
    assert exc_rev.value.code == "source_license_restricted"

    # 5. Gọi /agent/auto-create với saveWorkspaceConsent=False không bật consent toàn kho
    async def fake_auto_agent(_purpose, _body):
        return {
            "content": json.dumps(
                {
                    "title": "Đề Vật lí 10",
                    "subject": "Vật lí",
                    "grade": "10",
                    "durationMinutes": 45,
                    "slots": [{"topic": "Động lực học", "type": "mcq", "level": 0, "points": 1.0}],
                },
                ensure_ascii=False,
            ),
            "provider": "fixture",
        }

    app = create_app(tmp_path, agent_call=fake_auto_agent)
    with TestClient(app, headers=ORIGIN) as client:
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam_p2], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()

        r_status_before = client.get("/api/status").json()
        assert r_status_before["config"]["fixedRouter"]["workspaceAiConsent"] is False

        r_auto = client.post(
            f"/api/exams/{exam_p2['id']}/agent/auto-create",
            json={
                "prompt": "Soạn đề nhanh từ bài này",
                "consentGiven": True,
                "saveWorkspaceConsent": False,
                "expectedRevision": 1,
                "sources": [{"docId": doc_a, "page": 2, "text": "TRANG_2_DUOC_CHON"}],
            },
        )
        assert r_auto.status_code == 200, r_auto.text
        r_status_after = client.get("/api/status").json()
        assert r_status_after["config"]["fixedRouter"]["workspaceAiConsent"] is False


def test_source_file_endpoint_serves_pptx_and_rejects_invalid_bytes(tmp_path):
    """GET /api/source-file/{file_id} phục vụ đúng PPTX và trả 404 với dữ liệu sai định dạng."""
    app = create_app(tmp_path)
    pptx_bytes = _make_minimal_pptx_bytes()
    with TestClient(app, headers=ORIGIN) as client:
        client.put(
            "/api/kv",
            json={
                "key": "file:pptx_ok",
                "value": _data_url(
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    pptx_bytes,
                ),
            },
        ).raise_for_status()
        client.put(
            "/api/kv",
            json={
                "key": "file:bad_bin",
                "value": _data_url("application/octet-stream", b"corrupt-binary"),
            },
        ).raise_for_status()

        res_ok = client.get("/api/source-file/pptx_ok")
        assert res_ok.status_code == 200
        assert (
            res_ok.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        assert res_ok.content == pptx_bytes

        res_bad = client.get("/api/source-file/bad_bin")
        assert res_bad.status_code == 404


def test_backup_audio_validation_and_restore_200_and_409(tmp_path):
    """Bản sao lưu chứa âm thanh .wav/.mp3/... hợp lệ khôi phục 200 OK; giả mạo header bị 409."""
    valid_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00"
    valid_id3 = b"ID3\x04\x00\x00\x00\x00\x00\x00FRAME_DATA"
    valid_mp3_sync = b"\xff\xfb\x90\x00FRAME_DATA"
    valid_ogg = b"OggS\x00\x02\x00\x00\x00\x00"
    valid_m4a = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00"
    valid_webm = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81"

    for key, mime, raw in (
        ("wav1", "audio/wav", valid_wav),
        ("mp3a", "audio/mpeg", valid_id3),
        ("mp3b", "audio/mp3", valid_mp3_sync),
        ("ogg1", "audio/ogg", valid_ogg),
        ("m4a1", "audio/mp4", valid_m4a),
        ("webm1", "audio/webm", valid_webm),
    ):
        assert check_file(key, _data_url(mime, raw), {mime}) == _data_url(mime, raw)

    with pytest.raises(AIError) as exc_bad_audio:
        check_file("badwav", _data_url("audio/wav", b"PLAIN_TEXT_SPOOF"), {"audio/wav"})
    assert exc_bad_audio.value.code == "invalid_backup"

    app = create_app(tmp_path)
    exam_audio = _make_exam()
    exam_audio["questions"].append(
        {
            "id": str(uuid4()),
            "type": "short",
            "topic": "Nghe hiểu",
            "level": 0,
            "points": 1.0,
            "stem": "Nghe đoạn audio mẫu.",
            "options": [],
            "answer": None,
            "answerKnown": False,
            "audio": [
                {"fileId": "wav_ref", "filename": "nghe.wav", "mimeType": "audio/wav"},
                {"fileId": "mp3_ref", "filename": "nghe.mp3", "mimeType": "audio/mpeg"},
            ],
        }
    )

    with TestClient(app, headers=ORIGIN) as client:
        rev = client.get("/api/kv", params={"key": "state"}).json()["revision"]
        good_backup = {
            "format": "tro-ly-soan-de",
            "version": 1,
            "state": {"exams": [exam_audio], "prefs": [], "current": exam_audio["id"]},
            "files": {
                "wav_ref": _data_url("audio/wav", valid_wav),
                "mp3_ref": _data_url("audio/mpeg", valid_id3),
            },
        }
        r_ok = client.post(
            "/api/workspace/restore", json=good_backup, headers={"If-Match": str(rev)}
        )
        assert r_ok.status_code == 200, r_ok.text
        rev2 = r_ok.json()["revision"]

        bad_backup = {
            "format": "tro-ly-soan-de",
            "version": 1,
            "state": {"exams": [exam_audio], "prefs": [], "current": exam_audio["id"]},
            "files": {
                "wav_ref": _data_url("audio/wav", b"NOT_A_REAL_RIFF_WAVE"),
                "mp3_ref": _data_url("audio/mpeg", valid_id3),
            },
        }
        r_bad = client.post(
            "/api/workspace/restore", json=bad_backup, headers={"If-Match": str(rev2)}
        )
        assert r_bad.status_code == 409


def test_backup_mcq_2_to_6_options_unknown_answer_and_export_history_notice(tmp_path):
    """Hỗ trợ MCQ 2..6 phương án, đáp án E=4, answer=None và cảnh báo exam_exports."""
    app = create_app(tmp_path)
    exam = {
        "id": str(uuid4()),
        "revision": 1,
        "title": "Đề cộng đồng ẩn đáp án",
        "subject": "Tiếng Anh",
        "grade": "11",
        "docs": [],
        "matrix": [],
        "history": [],
        "undo": [],
        "redo": [],
        "chat": [],
        "data": [],
        "quote": {"text": "", "versions": []},
        "questions": [
            {
                "id": str(uuid4()),
                "type": "mcq",
                "level": 0,
                "stem": "Câu 2 phương án",
                "options": ["True", "False"],
                "answer": 1,
                "points": 1.0,
            },
            {
                "id": str(uuid4()),
                "type": "mcq",
                "level": 1,
                "stem": "Câu 5 phương án đáp án E",
                "options": ["A", "B", "C", "D", "E"],
                "answer": 4,
                "points": 1.0,
            },
            {
                "id": str(uuid4()),
                "type": "mcq",
                "level": 2,
                "stem": "Câu 6 phương án ẩn khóa đáp án",
                "options": ["1", "2", "3", "4", "5", "6"],
                "answer": None,
                "answerKnown": False,
                "points": 1.0,
            },
            {
                "id": str(uuid4()),
                "type": "truefalse",
                "level": 1,
                "stem": "Câu đúng sai ẩn đáp án từng ý",
                "options": ["Ý 1", "Ý 2", "Ý 3", "Ý 4"],
                "answer": None,
                "answerKnown": False,
                "truthValues": [True, None, False, None],
                "points": 1.0,
            },
        ],
    }

    with TestClient(app, headers=ORIGIN) as client:
        rev = client.get("/api/kv", params={"key": "state"}).json()["revision"]
        backup_ok = {
            "format": "tro-ly-soan-de",
            "version": 1,
            "state": {"exams": [exam], "prefs": [], "current": exam["id"]},
            "files": {},
        }

        # Minimal clean workspace: preview giữ nguyên các khóa tối giản tương thích test cũ
        prev_clean = client.post("/api/workspace/restore/preview", json=backup_ok)
        assert prev_clean.status_code == 200, prev_clean.text
        assert prev_clean.json() == {"revision": rev, "exams": 1, "files": 0, "prefs": 0}

        restored = client.post(
            "/api/workspace/restore", json=backup_ok, headers={"If-Match": str(rev)}
        )
        assert restored.status_code == 200, restored.text
        body = restored.json()
        assert body["examExportsMigrated"] is False
        assert body["examExportsWarning"] == EXAM_EXPORTS_NOTICE

        # Khi kho đã có lịch sử bản in trong exam_exports -> preview cảnh báo không di chuyển
        exp = client.post(
            "/api/save-export",
            json={
                "type": "exam",
                "exam": {
                    "id": exam["id"],
                    "title": exam["title"],
                    "subject": exam["subject"],
                    "grade": exam["grade"],
                    "revision": 1,
                    "questions": [
                        {
                            "id": str(uuid4()),
                            "type": "mcq",
                            "level": 0,
                            "stem": "Câu mẫu in đề",
                            "options": ["A", "B", "C", "D"],
                            "answer": 0,
                            "points": 1.0,
                        }
                    ],
                },
                "format": "html",
                "teacher": False,
                "classLabel": "11A1",
            },
        )
        assert exp.status_code == 200, exp.text
        prev_with_exports = client.post("/api/workspace/restore/preview", json=backup_ok)
        assert prev_with_exports.status_code == 200
        prev_json = prev_with_exports.json()
        assert prev_json["examExportsMigrated"] is False
        assert prev_json["examExportsWarning"] == EXAM_EXPORTS_NOTICE
        assert EXAM_EXPORTS_NOTICE in prev_json["warnings"]

        # Đáp án vượt len(options) vẫn phải bị 409
        invalid_exam = {
            **exam,
            "questions": [
                {
                    "id": str(uuid4()),
                    "type": "mcq",
                    "level": 0,
                    "stem": "Câu sai đáp án",
                    "options": ["A", "B"],
                    "answer": 2,
                    "points": 1.0,
                }
            ],
        }
        r_invalid = client.post(
            "/api/workspace/restore",
            json={
                "format": "tro-ly-soan-de",
                "version": 1,
                "state": {"exams": [invalid_exam], "prefs": [], "current": invalid_exam["id"]},
                "files": {},
            },
            headers={"If-Match": str(body["revision"])},
        )
        assert r_invalid.status_code == 409


def test_agy_cli_and_ai_router_redacted_invalid_response_diagnostics(tmp_path):
    """Giữ normalize_agy_json_schema và ghi mã phụ chẩn đoán đã khử bí mật khi invalid_response."""
    raw_schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "additionalProperties": False,
    }
    normalized = normalize_agy_json_schema(raw_schema)
    assert normalized["required"] == ["message"]
    assert raw_schema["additionalProperties"] is False

    secret = "sk-proj-SECRETTOKEN987654321"
    assert diagnose_invalid_response("")["subcode"] == "empty_response"
    d_malformed = diagnose_invalid_response(f"{{broken {secret}", reason_hint="malformed_json")
    assert d_malformed["subcode"] == "malformed_json"
    assert d_malformed["response_len"] > 0
    assert d_malformed["top_keys"] == []

    d_tool = diagnose_invalid_response(
        {"unexpected": 1},
        has_tools=True,
        allowed_tools=("read_file",),
        reason_hint="invalid_tool_action",
    )
    assert d_tool["subcode"] == "invalid_tool_action"
    assert d_tool["top_keys"] == ["unexpected"]

    d_schema = diagnose_invalid_response(
        {"wrongKey": 123},
        expected_schema=raw_schema,
        parsed_payload={"wrongKey": 123},
        reason_hint="schema_mismatch",
    )
    assert d_schema["subcode"] == "schema_mismatch"
    assert d_schema["top_keys"] == ["wrongKey"]
    assert d_schema["missing_required"] == ["message"]

    fake_exe = tmp_path / "agy.cmd"
    fake_exe.write_text("@echo off\n", encoding="utf-8")

    def broken_runner(*_args, **_kwargs):
        ndjson = json.dumps(
            {"type": "result", "structuredOutput": f"{{not-valid-json {secret}"},
            ensure_ascii=False,
        )
        return SimpleNamespace(stdout=ndjson.encode("utf-8"), returncode=0)

    events: list[dict[str, Any]] = []
    log = RunLog(tmp_path / "agy-diag-log", on_event=events.append)
    model = AgyCliModel(
        log, custom_path=str(fake_exe), runner=broken_runner, model="gemini-3.8-flash"
    )
    with pytest.raises(AIError) as exc_agy:
        asyncio.run(
            model(
                "chat",
                {
                    "messages": [{"role": "user", "content": "Chào"}],
                    "format": raw_schema,
                },
            )
        )
    assert exc_agy.value.code == "invalid_response"
    diag = get_error_diagnostic(exc_agy.value)
    assert diag is not None
    assert diag["subcode"] == "malformed_json"
    assert diag["response_len"] > 0
    assert secret not in json.dumps(diag)

    invalid_events = [ev for ev in events if ev.get("event") == "model_invalid_response"]
    assert invalid_events
    assert invalid_events[0]["subcode"] == "malformed_json"
    assert secret not in json.dumps(events)

    # Router giữ nguyên diagnostic trong router_fallback
    router_events: list[dict[str, Any]] = []
    router_log = RunLog(tmp_path / "router-diag-log", on_event=router_events.append)

    def fail_agy(_purpose, _body):
        raise exc_agy.value

    def ok_ollama(_purpose, _body):
        return {"content": json.dumps({"message": "Dự phòng OK"}), "model": "qwen2.5"}

    router = FixedTaskRouter({"agy": fail_agy, "ollama": ok_ollama}, log=router_log)
    res = asyncio.run(router("chat", {"messages": [{"role": "user", "content": "Hỏi"}]}))
    assert res["content"]
    fb = [ev for ev in router_events if ev.get("event") == "router_fallback"]
    assert fb and fb[0]["subcode"] == "malformed_json"
    assert fb[0]["diagnostic"]["response_len"] == diag["response_len"]

    # Endpoint /api/assistant/chat trả detail diagnostic đã khử bí mật khi lỗi invalid_response
    async def broken_chat_agent(_purpose, _body):
        err = AIError(
            "invalid_response",
            "Phản hồi chưa đúng định dạng.",
            http_status=409,
        )
        attach_error_diagnostic(
            err,
            diagnose_invalid_response(
                '{"wrong": 1}', expected_schema=raw_schema, parsed_payload={"wrong": 1}
            ),
        )
        raise err

    app = create_app(tmp_path / "ws", agent_call=broken_chat_agent)
    with TestClient(app, headers=ORIGIN) as client:
        r_err = client.post("/api/assistant/chat", json={"text": "Hỏi thử", "consent": True})
        assert r_err.status_code == 409
        err_json = r_err.json()
        assert err_json["code"] == "invalid_response"
        assert err_json["detail"]["subcode"] == "schema_mismatch"
        assert err_json["detail"]["top_keys"] == ["wrong"]
