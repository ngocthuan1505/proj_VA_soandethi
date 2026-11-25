"""Kiểm thử tích hợp Step 2 cho UV61: LAN phòng thi, SSE chat stream + failover,
provider health/test-provider, strictTeacherOnly, zero-hit RAG, OCR chọn lọc + Vision,
validate tiêu đề đề thi và đồng bộ Team Workspace."""

from __future__ import annotations

import base64
import io
import json
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from mach_backend.ai_contract import AIError
from mach_backend.ai_router import reset_shared_circuit_breaker
from mach_backend.local_workspace import create_app, plan_from_exam
from mach_backend.team_workspace import create_team_app

ORIGIN = {"Origin": "http://testserver"}
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)


def _sample_exam(exam_id: str | None = None, *, strict_teacher: bool = False) -> dict[str, Any]:
    eid = exam_id or str(uuid4())
    return {
        "id": eid,
        "revision": 1,
        "title": "Đề kiểm tra Vật lí 10 - Động lực học",
        "subject": "Vật lí",
        "grade": "10",
        "minutes": 45,
        "matrixConfirmed": True,
        "strictTeacherOnly": strict_teacher,
        "matrix": [{"topic": "Động lực học", "targets": [1, 0, 0, 0]}],
        "questions": [
            {
                "id": str(uuid4()),
                "type": "mcq",
                "topic": "Động lực học",
                "level": 0,
                "points": 1.0,
                "stem": "Đơn vị của lực trong hệ SI là gì?",
                "options": ["Niutơn (N)", "Jun (J)", "Oát (W)", "Mét (m)"],
                "answer": 0,
                "explanation": "Lực đo bằng đơn vị Niutơn (N).",
            }
        ],
    }


def _parse_sse(raw_text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    cur_event = "message"
    cur_data: list[str] = []
    for line in raw_text.splitlines():
        if not line.strip():
            if cur_data:
                events.append((cur_event, json.loads("\n".join(cur_data))))
                cur_event = "message"
                cur_data = []
            continue
        if line.startswith("event:"):
            cur_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            cur_data.append(line.split(":", 1)[1].strip())
    if cur_data:
        events.append((cur_event, json.loads("\n".join(cur_data))))
    return events


def test_lan_rooms_path_scoped_security_local_workspace(tmp_path):
    app = create_app(tmp_path)
    exam = _sample_exam()
    lan_headers = {"Host": "192.168.1.50:8000", "Origin": "http://192.168.1.50:8000"}

    with TestClient(app, headers=ORIGIN) as teacher:
        teacher.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()
        room = teacher.post(
            "/api/rooms",
            json={
                "examId": exam["id"],
                "title": "Phòng kiểm tra LAN",
                "mode": "exam",
                "durationMinutes": 30,
                "allowLan": False,
                "status": "open",
            },
        )
        assert room.status_code == 201, room.text
        room_data = room.json()
        room_id = room_data["id"]
        room_code = room_data["roomCode"]

        # Khi chưa bật allow_lan, cả /api/kv và /phong-thi đều bị chặn từ LAN
        with TestClient(app, base_url="http://192.168.1.50:8000", headers=lan_headers) as guest:
            assert guest.get("/api/kv?key=state").status_code == 403
            assert guest.get(f"/phong-thi/{room_code}").status_code == 403
            assert guest.get(f"/api/rooms/public/{room_code}").status_code == 403

        # Bật allowLan=True trên phòng thi -> mở đúng cổng học sinh, vẫn khóa API giáo viên
        teacher.patch(f"/api/rooms/{room_id}", json={"allowLan": True}).raise_for_status()
        with TestClient(app, base_url="http://192.168.1.50:8000", headers=lan_headers) as guest:
            assert guest.get("/api/kv?key=state").status_code == 403
            assert guest.get("/api/config").status_code == 403
            assert guest.get("/api/rooms").status_code == 403
            assert guest.get(f"/phong-thi/{room_code}").status_code == 200
            meta = guest.get(f"/api/rooms/public/{room_code}")
            assert meta.status_code == 200, meta.text
            joined = guest.post(
                f"/api/rooms/public/{room_code}/join",
                json={"studentName": "Nguyễn Minh An", "studentClass": "10A1"},
            )
            assert joined.status_code == 201, joined.text
            assert joined.json()["attemptToken"]


def test_chat_stream_sse_and_pre_first_token_failover(tmp_path, monkeypatch):
    from mach_backend import local_workspace

    reset_shared_circuit_breaker()
    calls: list[str] = []
    fail_mode = {"deepseek": False}

    class FakeDeepSeek:
        def __init__(
            self,
            _client,
            _key,
            _log,
            *,
            model,
            base_url,
            backup_models,
            cost_tracker,
            budget=None,
        ):
            self.model = model

        async def stream_chat(self, messages, **_kwargs):
            calls.append(f"deepseek:{self.model}")
            if fail_mode["deepseek"]:
                raise AIError("provider_quota", "DeepSeek gặp 429.", http_status=429)
            yield {"type": "delta", "text": "Xin chào "}
            yield {"type": "delta", "text": "thầy cô!"}
            yield {"type": "done", "text": "Xin chào thầy cô!", "model": self.model}

    class FakeGemini:
        def __init__(self, _client, _key, _log, *, model, key_pool, auto_fallback, budget=None):
            self.model = model

        async def stream_chat(self, messages, **_kwargs):
            calls.append(f"gemini:{self.model}")
            yield {"type": "delta", "text": "Dự phòng "}
            yield {"type": "delta", "text": "Gemini OK"}
            yield {"type": "done", "text": "Dự phòng Gemini OK", "model": self.model}

    monkeypatch.setattr(local_workspace, "DeepSeekModel", FakeDeepSeek)
    monkeypatch.setattr(local_workspace, "GeminiModel", FakeGemini)

    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "gemini": {"key": "AQ.fake_stream_key_0001", "freeTierConfirmed": True},
                "deepseek": {
                    "url": "https://gateway.example.test",
                    "key": "sk-fake-stream-key-0001",
                    "model": "deepseek-v4.1-flash",
                },
                "fixedRouter": {"enabled": True},
            },
        ).raise_for_status()

        # 1. Stream thành công từ deepseek_chat ở preset fast
        with client.stream(
            "POST",
            "/api/assistant/chat/stream",
            json={"text": "Chào trợ lý", "consent": True, "timePreset": "fast"},
        ) as resp:
            assert resp.status_code == 200
            raw = resp.read().decode("utf-8")
        events = _parse_sse(raw)
        assert [ev[0] for ev in events].count("delta") == 2
        done = next(ev[1] for ev in events if ev[0] == "done")
        assert done["message"] == "Xin chào thầy cô!"
        assert done["providerUsed"] == "deepseek_chat"
        assert done["attemptedProviders"] == ["deepseek_chat"]
        assert done["fallbackFrom"] is None

        # 2. timePreset='standard' ưu tiên AGY đầu tiên khi khả dụng
        fake_agy = tmp_path / "agy.cmd"
        fake_agy.write_text("@echo off\n", encoding="utf-8")
        client.post(
            "/api/config",
            json={"fixedRouter": {"enabled": True, "agyCustomPath": str(fake_agy)}},
        ).raise_for_status()

        class FakeAgy:
            def __init__(self, _log, **_kwargs):
                pass

            async def __call__(self, _purpose, _body):
                calls.append("agy:agy-cli")
                return {
                    "content": json.dumps({"message": "AGY standard sẵn sàng"}),
                    "provider": "agy",
                    "model": "agy-cli",
                }

        monkeypatch.setattr(local_workspace, "AgyCliModel", FakeAgy)
        monkeypatch.setattr(local_workspace, "DeepSeekModel", FakeDeepSeek)
        with client.stream(
            "POST",
            "/api/assistant/chat/stream",
            json={"text": "Chào AGY chuẩn", "consent": True, "timePreset": "standard"},
        ) as resp_std:
            assert resp_std.status_code == 200
            raw_std = resp_std.read().decode("utf-8")
        events_std = _parse_sse(raw_std)
        done_std = next(ev[1] for ev in events_std if ev[0] == "done")
        assert done_std["providerUsed"] == "agy"
        assert done_std["modelUsed"] == "agy-cli"
        assert "AGY standard" in done_std["message"]

        # 3. Failover trước token đầu khi DeepSeek trả 429 -> chuyển sang gemini_flash
        calls.clear()
        fail_mode["deepseek"] = True
        with client.stream(
            "POST",
            "/api/assistant/chat/stream",
            json={"text": "Chào khi dự phòng", "consent": True, "timePreset": "fast"},
        ) as resp2:
            assert resp2.status_code == 200
            raw2 = resp2.read().decode("utf-8")
        events2 = _parse_sse(raw2)
        done2 = next(ev[1] for ev in events2 if ev[0] == "done")
        assert done2["message"] == "Dự phòng Gemini OK"
        assert done2["providerUsed"] == "gemini_flash"
        assert done2["fallbackFrom"] == "deepseek_chat"
        assert done2["attemptedProviders"] == ["deepseek_chat", "gemini_flash"]
        reset_shared_circuit_breaker()


def test_provider_test_alias_and_team_non_admin_403(tmp_path):
    local_app = create_app(tmp_path / "local")
    with TestClient(local_app, headers=ORIGIN) as client:
        res = client.post("/api/test-provider", json={"provider": "gemini"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["provider"] == "gemini"
        assert body["ok"] is False
        assert body["status"] == "unconfigured"

    team_app = create_team_app(tmp_path / "team")
    accounts = team_app.state.accounts
    accounts.create(
        "admin@test.local",
        "MatKhauAdmin123!",
        "Admin",
        accounts.invite(bootstrap=True),
    )
    accounts.create(
        "gv@test.local",
        "MatKhauGiaoVien123!",
        "Giáo viên",
        accounts.invite(email="gv@test.local"),
    )
    with TestClient(team_app, headers=ORIGIN) as member:
        member.post(
            "/api/account/login",
            json={"email": "gv@test.local", "password": "MatKhauGiaoVien123!"},
        ).raise_for_status()
        assert member.post("/api/test-provider", json={"provider": "gemini"}).status_code == 403
        assert member.post("/api/providers/gemini/test", json={}).status_code == 403


def test_put_kv_rejects_blank_exam_title_but_allows_titleless_min_dict(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        bad = client.put(
            "/api/kv",
            json={
                "key": "state",
                "value": {"exams": [{"id": str(uuid4()), "title": "   "}], "prefs": []},
            },
            headers={**ORIGIN, "If-Match": "0"},
        )
        assert bad.status_code == 400
        err_msg = str(bad.json().get("detail") or bad.json().get("error") or "")
        assert "không được để trống" in err_msg.casefold()

        # Tương thích dict tối giản không có khóa title
        minimal = client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [{"id": str(uuid4())}], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        )
        assert minimal.status_code == 200, minimal.text


def test_plan_from_exam_filters_uc7_applied_prefs_by_subject_and_grade():
    exam = {
        "id": str(uuid4()),
        "subject": "Ngữ văn",
        "grade": "9",
        "matrixConfirmed": True,
        "matrix": [{"topic": "Đọc hiểu", "targets": [1, 0, 0, 0]}],
        "appliedPrefs": [
            {"confirmedAt": 100, "scopeType": "all", "text": "QUY_TAC_CHUNG"},
            {
                "confirmedAt": 101,
                "scopeType": "subject",
                "subject": "Tiếng Việt",
                "text": "QUY_TAC_NGU_VAN",
            },
            {
                "confirmedAt": 102,
                "scopeType": "subject",
                "subject": "Hóa học",
                "text": "QUY_TAC_HOA_HOC_LOAI",
            },
            {
                "confirmedAt": 103,
                "scopeType": "subject_grade",
                "subject": "Ngữ văn",
                "grade": "10",
                "text": "QUY_TAC_LOP_10_LOAI",
            },
        ],
    }
    plan = plan_from_exam(exam)
    assert "QUY_TAC_CHUNG" in plan.instructions
    assert "QUY_TAC_NGU_VAN" in plan.instructions
    assert "QUY_TAC_HOA_HOC_LOAI" not in plan.instructions
    assert "QUY_TAC_LOP_10_LOAI" not in plan.instructions


def test_strict_teacher_only_and_zero_hit_rag_on_approve_and_chat(tmp_path):
    captured: list[dict[str, Any]] = []

    async def fake_agent(_purpose, body):
        captured.append(body)
        return {"content": json.dumps({"message": "Đã kiểm tra nguồn."}), "provider": "fixture"}

    app = create_app(tmp_path, agent_call=fake_agent)
    doc_teacher_id = str(uuid4())
    doc_catalog_id = str(uuid4())
    exam = _sample_exam(strict_teacher=True)
    exam["docs"] = [
        {
            "id": doc_teacher_id,
            "name": "Tai_lieu_quang_hop.txt",
            "version": 1,
            "pages": [
                {
                    "number": 1,
                    "text": (
                        "Quang hợp xảy ra tại lục lạp của thực vật, "
                        "tổng hợp tinh bột từ CO2 và nước."
                    ),
                }
            ],
        },
        {
            "id": doc_catalog_id,
            "name": "SGK_mau_cam.txt",
            "version": 1,
            "catalog": True,
            "sourceOrigin": "lesson_catalog",
            "pages": [{"number": 1, "text": "Nội dung thư viện chung bị cấm ở chế độ này."}],
        },
    ]

    with TestClient(app, headers=ORIGIN) as client:
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()

        # 1. /matrix/approve chặn general khi strictTeacherOnly=True
        r_gen = client.post(
            f"/api/exams/{exam['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Tự soạn",
                "sourceMode": "general",
            },
        )
        assert r_gen.status_code == 400
        assert r_gen.json()["code"] == "strict_source_policy"

        # 2. /matrix/approve chặn nguồn catalog khi strictTeacherOnly=True
        r_cat = client.post(
            f"/api/exams/{exam['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "SGK mẫu",
                "sourceMode": "provided",
                "sources": [
                    {
                        "sourceId": doc_catalog_id,
                        "sourceVersion": 1,
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert r_cat.status_code == 400
        assert r_cat.json()["code"] == "strict_source_policy"

        # 3. Chat bật strictTeacherOnly + truy vấn lạc đề -> 0-hit cutoff
        r_zero = client.post(
            "/api/assistant/chat",
            json={
                "text": "Chiến thắng Điện Biên Phủ năm 1954 diễn ra như thế nào?",
                "examId": exam["id"],
                "consent": True,
            },
        )
        assert r_zero.status_code == 200, r_zero.text
        data_zero = r_zero.json()
        assert data_zero["strictTeacherOnly"] is True
        assert data_zero["noMatchingSourceFragments"] is True
        sent_user = json.loads(captured[-1]["messages"][1]["content"])
        assert sent_user["noMatchingSourceFragments"] is True
        assert "Quang hợp" not in json.dumps(sent_user["context"], ensure_ascii=False)
        assert "Không tìm thấy đoạn khớp" in captured[-1]["messages"][0]["content"]

        # 4. strictTeacherOnly + chỉ chọn trang 2 + payload cố nhét trang 1 & catalog -> giữ trang 2
        captured.clear()
        exam_pages = dict(exam)
        exam_pages["revision"] = 2
        exam_pages["assistantSources"] = [doc_teacher_id]
        exam_pages["assistantSourcePages"] = {doc_teacher_id: [2]}
        exam_pages["docs"] = [
            {
                "id": doc_teacher_id,
                "name": "Tai_lieu_2_trang.txt",
                "version": 1,
                "pages": [
                    {"number": 1, "text": "BÍ MẬT TRANG 1 KHÔNG ĐƯỢC GỬI QUANG HỢP."},
                    {"number": 2, "text": "NỘI DUNG TRANG 2 ĐƯỢC CHỌN VỀ HÔ HẤP TẾ BÀO."},
                ],
            },
            exam["docs"][1],
        ]
        client.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam_pages], "prefs": []}},
        ).raise_for_status()
        r_p2 = client.post(
            "/api/assistant/chat",
            json={
                "text": "Tóm tắt nội dung hô hấp tế bào ở trang đã chọn",
                "examId": exam["id"],
                "consent": True,
                "teacherFilesOnly": True,
                "context": [
                    {
                        "kind": "attached-source",
                        "id": doc_teacher_id,
                        "sourceId": doc_teacher_id,
                        "pageNumber": 1,
                        "excerpt": "BÍ MẬT TRANG 1 KHÔNG ĐƯỢC GỬI QUANG HỢP.",
                    },
                    {
                        "kind": "attached-source",
                        "id": doc_catalog_id,
                        "sourceId": doc_catalog_id,
                        "pageNumber": 1,
                        "excerpt": "NGUỒN CATALOG BỊ CẤM TRONG CONTEXT",
                    },
                    {
                        "kind": "attached-source",
                        "id": doc_teacher_id,
                        "sourceId": doc_teacher_id,
                        "pageNumber": 2,
                        "excerpt": "NỘI DUNG TRANG 2 ĐƯỢC CHỌN VỀ HÔ HẤP TẾ BÀO.",
                    },
                ],
            },
        )
        assert r_p2.status_code == 200, r_p2.text
        assert r_p2.json()["noMatchingSourceFragments"] is False
        sent_p2 = json.dumps(
            json.loads(captured[-1]["messages"][1]["content"])["context"], ensure_ascii=False
        )
        assert "NỘI DUNG TRANG 2" in sent_p2
        assert "BÍ MẬT TRANG 1" not in sent_p2
        assert "CATALOG BỊ CẤM" not in sent_p2

        # 5. 1 tệp duy nhất gắn trực tiếp trong context + truy vấn lạc đề -> phải bật 0-hit cutoff
        captured.clear()
        r_single_zero = client.post(
            "/api/assistant/chat",
            json={
                "text": "Chiến thắng Điện Biên Phủ năm 1954 diễn ra như thế nào?",
                "examId": exam["id"],
                "consent": True,
                "teacherFilesOnly": True,
                "context": [
                    {
                        "kind": "attached-source",
                        "id": doc_teacher_id,
                        "sourceId": doc_teacher_id,
                        "pageNumber": 2,
                        "excerpt": "Quang hợp tổng hợp tinh bột xảy ra tại lục lạp của cây xanh.",
                    }
                ],
            },
        )
        assert r_single_zero.status_code == 200, r_single_zero.text
        assert r_single_zero.json()["noMatchingSourceFragments"] is True
        sent_single = json.loads(captured[-1]["messages"][1]["content"])
        assert "lục lạp" not in json.dumps(sent_single["context"], ensure_ascii=False)


def test_exam_exports_returns_url_and_is_draft(tmp_path):
    app = create_app(tmp_path)
    draft_exam = _sample_exam()
    draft_exam["saved"] = False
    saved_exam = _sample_exam(draft_exam["id"])
    saved_exam["revision"] = 2

    with TestClient(app, headers=ORIGIN) as client:
        r1 = client.post(
            "/api/save-export",
            json={"type": "exam", "exam": draft_exam, "format": "html", "classLabel": "10A1"},
        )
        assert r1.status_code == 200, r1.text
        r2 = client.post(
            "/api/save-export",
            json={"type": "exam", "exam": saved_exam, "format": "html", "classLabel": "10A2"},
        )
        assert r2.status_code == 200, r2.text

        # Đề lỗi preflight thiếu đáp án: 409 nếu thiếu allowDraft, 200 & banner GV khi đồng ý nháp
        bad_exam = _sample_exam(draft_exam["id"])
        bad_exam["revision"] = 3
        bad_exam["questions"][0]["answerKnown"] = False
        r_block = client.post(
            "/api/save-export",
            json={"type": "exam", "exam": bad_exam, "format": "html", "teacher": True},
        )
        assert r_block.status_code == 409, r_block.text
        assert r_block.json()["code"] == "export_preflight_blocked"
        assert r_block.json()["requiresDraftConfirmation"] is True

        r_allow = client.post(
            "/api/save-export",
            json={
                "type": "exam",
                "exam": bad_exam,
                "format": "html",
                "teacher": True,
                "allowDraft": True,
                "classLabel": "10A3",
            },
        )
        assert r_allow.status_code == 200, r_allow.text
        assert r_allow.json()["isDraft"] is True
        exported_html = client.get(r_allow.json()["url"]).text
        assert "BẢN NHÁP" in exported_html

        hist = client.get(f"/api/exams/{draft_exam['id']}/exports")
        assert hist.status_code == 200, hist.text
        rows = hist.json()["exports"]
        assert len(rows) == 3
        by_class = {row["classLabel"]: row for row in rows}
        assert by_class["10A1"]["isDraft"] is True
        assert by_class["10A1"]["url"] == by_class["10A1"]["downloadUrl"]
        assert by_class["10A2"]["isDraft"] is False
        assert by_class["10A2"]["url"] == by_class["10A2"]["downloadUrl"]
        assert by_class["10A3"]["isDraft"] is True


def test_team_workspace_exam_rooms_and_config_sync(tmp_path):
    team_app = create_team_app(tmp_path)
    accounts = team_app.state.accounts
    accounts.create(
        "admin@school.test",
        "AdminPass999!!",
        "Trưởng bộ môn",
        accounts.invite(bootstrap=True),
    )
    accounts.create(
        "teacher@school.test",
        "TeacherPass999!!",
        "Giáo viên Toán",
        accounts.invite(email="teacher@school.test"),
    )

    exam = _sample_exam()
    with (
        TestClient(team_app, headers=ORIGIN) as admin,
        TestClient(team_app, headers=ORIGIN) as member,
    ):
        admin.post(
            "/api/account/login",
            json={"email": "admin@school.test", "password": "AdminPass999!!"},
        ).raise_for_status()
        member.post(
            "/api/account/login",
            json={"email": "teacher@school.test", "password": "TeacherPass999!!"},
        ).raise_for_status()

        admin.post(
            "/api/config",
            json={
                "saveLocally": False,
                "gemini": {
                    "key": "AIzaSyFakeAdminMainKey0001",
                    "extraKeys": ["AIzaSyFakeAdminExtra0002"],
                    "freeTierConfirmed": True,
                },
                "deepseek": {
                    "url": "https://gateway.team.test/v1",
                    "key": "sk-team-deepseek-key-0001",
                    "model": "deepseek-chat",
                },
                "fixedRouter": {"enabled": True, "timePreset": "deep"},
            },
        ).raise_for_status()

        cfg_res = member.get("/api/config")
        assert cfg_res.status_code == 200, cfg_res.text
        cfg = cfg_res.json()
        assert cfg["gemini"]["extraKeysCount"] == 1
        assert cfg["deepseek"]["hasKey"] is True
        assert cfg["fixedRouter"]["timePreset"] == "deep"

        # Giáo viên thành viên tạo và mở phòng thi trên Team Workspace
        member.put(
            "/api/kv",
            json={"key": "state", "value": {"exams": [exam], "prefs": []}},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()
        room_res = member.post(
            "/api/rooms",
            json={
                "examId": exam["id"],
                "mode": "homework",
                "title": "BTVN Nhóm",
                "status": "open",
            },
        )
        assert room_res.status_code == 201, room_res.text
        code = room_res.json()["roomCode"]

        with TestClient(team_app, headers=ORIGIN) as student:
            join_res = student.post(
                f"/api/rooms/public/{code}/join",
                json={"studentName": "Lê Thu Hà", "studentClass": "10A3"},
            )
            assert join_res.status_code == 201, join_res.text
            assert join_res.json()["attemptToken"]


def test_ocr_selective_single_page_and_ollama_vision_fallback(tmp_path, monkeypatch):
    from mach_backend import local_workspace

    # 1. PDF 2 trang -> /api/ocr page=2 chỉ gửi PDF con đúng 1 trang tới document_model
    seen_page_counts: list[int] = []

    async def fake_agent(purpose, body):
        assert purpose == "source_ocr"
        doc_bytes = base64.b64decode(body["document"]["data"])
        reader = PdfReader(io.BytesIO(doc_bytes))
        seen_page_counts.append(len(reader.pages))
        return {
            "content": json.dumps(
                {
                    "pages": [
                        {
                            "number": 1,
                            "text": "Nội dung trang 2 đọc được",
                            "uncertain": False,
                        }
                    ],
                    "notes": "Đã đọc riêng trang 2.",
                },
                ensure_ascii=False,
            )
        }

    pdf_writer = PdfWriter()
    pdf_writer.add_blank_page(width=200, height=200)
    pdf_writer.add_blank_page(width=200, height=200)
    pdf_buf = io.BytesIO()
    pdf_writer.write(pdf_buf)
    pdf_uri = "data:application/pdf;base64," + base64.b64encode(pdf_buf.getvalue()).decode()

    app_pdf = create_app(tmp_path / "pdf", agent_call=fake_agent)
    with TestClient(app_pdf, headers=ORIGIN) as client:
        client.put(
            "/api/kv",
            json={"key": "file:pdf2", "value": pdf_uri},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()
        res = client.post(
            "/api/ocr",
            json={"fileId": "pdf2", "name": "tailieu.pdf", "page": 2, "consent": True},
        )
        assert res.status_code == 200, res.text
        assert res.json()["number"] == 2
        assert "Nội dung trang 2" in res.json()["text"]
        assert seen_page_counts == [1]

    # 2. Ảnh upload không có Gemini -> fallback sang Ollama Vision
    vision_calls: list[tuple[str, int]] = []

    async def fake_vision_ocr(self, images_b64, _prompt, model=None, base_url=None):
        vision_calls.append((self.model, len(images_b64)))
        return {
            "content": "Đề kiểm tra ảnh $x^2 + 1 = 0$",
            "model": self.model,
            "provider": "ollama",
        }

    monkeypatch.setenv("MACH_VISION_MODEL", "qwen3-vl:4b")
    monkeypatch.setattr(local_workspace.LocalModel, "vision_ocr", fake_vision_ocr)

    app_img = create_app(tmp_path / "img")
    with TestClient(app_img, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "routes": {"generate": "ollama"},
                "ollama": {"model": "qwen3-vl:4b"},
            },
        ).raise_for_status()
        client.put(
            "/api/kv",
            json={"key": "file:img1", "value": f"data:image/png;base64,{TINY_PNG_B64}"},
            headers={**ORIGIN, "If-Match": "0"},
        ).raise_for_status()
        ocr_img = client.post(
            "/api/ocr",
            json={"fileId": "img1", "name": "anh.png", "page": 1, "consent": True},
        )
        assert ocr_img.status_code == 200, ocr_img.text
        assert "$x^2 + 1 = 0$" in ocr_img.json()["text"]
        assert vision_calls == [("qwen3-vl:4b", 1)]
