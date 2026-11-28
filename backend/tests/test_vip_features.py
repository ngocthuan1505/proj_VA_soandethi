"""Kiểm thử toàn diện gói VIP Backend: Chat M11 tốc độ, Ngân hàng câu hỏi, Phân tích đề & OMR A4."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.exam_analytics import analyze_exam
from mach_backend.local_workspace import create_app
from mach_backend.question_bank import register_question_bank_routes
from mach_backend.team_workspace import create_team_app
from mach_backend.workspace_backup import export_workspace_backup
from mach_backend.workspace_store import WorkspaceStore

ORIGIN = {"Origin": "http://testserver"}
PASSWORD = "mat-khau-vip-chi-dung-test"


def _rich_question_fixture() -> dict:
    block_stem = str(uuid4())
    block_exp = str(uuid4())
    return {
        "id": str(uuid4()),
        "v": 2,
        "type": "mcq",
        "topic": "Đạo hàm và ứng dụng",
        "level": 2,
        "points": 0.5,
        "stem": r"Tính đạo hàm của hàm số $f(x) = x^3 - 3x + 1$.",
        "options": [
            r"$3x^2 - 3$",
            r"$3x^2 + 3$",
            r"$x^2 - 3$",
            r"$3x - 3$",
        ],
        "answer": 0,
        "explanation": r"Áp dụng quy tắc đạo hàm đa thức: $f'(x) = 3x^2 - 3$.",
        "blockIds": {"stem": block_stem, "explanation": block_exp},
        "richDoc": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "attrs": {"id": block_stem},
                    "content": [{"type": "text", "text": "Tính đạo hàm của hàm số bậc ba."}],
                }
            ],
        },
        "formulas": [{"id": str(uuid4()), "latex": r"f'(x)=3x^2-3", "display": True}],
        "tables": [{"id": str(uuid4()), "rows": [["x", "0", "1"], ["f'(x)", "-3", "0"]]}],
        "images": [
            {"id": str(uuid4()), "data": "data:image/png;base64,ZmFrZQ==", "caption": "Đồ thị"}
        ],
        "figure": {"kind": "geometry", "width": 400, "points": [{"id": "A", "x": 0, "y": 0}]},
        "rubric": [{"id": str(uuid4()), "text": "Tính đúng từng hạng tử", "points": 0.5}],
    }


def _clean_10_point_exam() -> dict:
    questions = []
    answers = [0, 1, 2, 3, 1, 2, 3, 0, 2, 3]
    stems = [
        "Giải phương trình bậc nhất $2x - 6 = 0$ tìm nghiệm thực duy nhất.",
        "Tìm cặp nghiệm của hệ tuyến tính hai ẩn $x + y = 5$ và $x - y = 1$.",
        "Xác định tọa độ đỉnh parabol đồ thị hàm số $y = x^2 - 4x + 3$.",
        "Tam giác vuông có hai cạnh góc vuông dài 3 cm và 4 cm; tính cạnh huyền.",
        "Cho đường tròn bán kính $R = 5$, độ dài dây cung cách tâm 3 cm bằng mấy?",
        "Gieo một đồng xu cân đối hai lần liên tiếp, xác suất xuất hiện hai mặt ngửa?",
        "Tính trung vị của mẫu số liệu ghép nhóm ghi nhận chiều cao học sinh khối 9.",
        r"Rút gọn biểu thức chứa căn bậc hai $\sqrt{18} + \sqrt{8} - \sqrt{2}$.",
        "Với ba đoạn thẳng 5 cm, 7 cm và $c$, điều kiện để lập thành tam giác là gì?",
        "Một hình trụ đứng có bán kính đáy 2 cm, chiều cao 10 cm; tính thể tích.",
    ]
    for i in range(10):
        questions.append(
            {
                "id": str(uuid4()),
                "type": "mcq",
                "level": i % 4,
                "points": 1.0,
                "approved": True,
                "topic": f"Chủ đề {i + 1}",
                "stem": stems[i],
                "options": [
                    f"Kết quả {i + 1}",
                    f"Kết quả {i + 2}",
                    f"Kết quả {i + 3}",
                    f"Kết quả {i + 4}",
                ],
                "answer": answers[i],
                "explanation": f"Lời giải chi tiết từng bước cho bài số {i + 1}.",
            }
        )
    return {
        "id": str(uuid4()),
        "title": "Đề kiểm tra giữa kỳ Toán 9",
        "subject": "Toán",
        "grade": "9",
        "minutes": 20,
        "questions": questions,
        "customUiState": {"zoom": 1.1, "activeTab": "preview"},
    }


def test_fast_chat_routes_deepseek_and_gemini_ahead_of_agy_and_returns_latency_ms(
    tmp_path, monkeypatch
):
    from mach_backend import local_workspace

    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_bytes(b"MZ")
    order: list[str] = []
    captured_prompts: list[str] = []
    captured_efforts: list[str | None] = []

    class FakeAgy:
        def __init__(self, _log, *, custom_path="", budget=None, effort=None):
            assert custom_path == str(fake_agy)
            captured_efforts.append(effort)

        async def __call__(self, _purpose, body):
            order.append("agy")
            captured_prompts.append(body["messages"][0]["content"])
            return {"content": '{"message": "Trả lời từ AGY"}', "model": "agy-cli"}

    class FakeGemini:
        def __init__(self, _client, _key, _log, *, model, key_pool, auto_fallback):
            self.model = model

        async def __call__(self, _purpose, body):
            order.append(f"gemini:{self.model}")
            captured_prompts.append(body["messages"][0]["content"])
            return {"content": '{"message": "Trả lời nhanh từ Gemini"}', "model": self.model}

    class FakeDeepSeek:
        def __init__(self, _client, _key, _log, *, model, base_url, backup_models, cost_tracker):
            self.model = model

        async def __call__(self, _purpose, body):
            order.append(f"deepseek:{self.model}")
            captured_prompts.append(body["messages"][0]["content"])
            if state["fail_fast_ds"] and self.model == "deepseek-v4.1-flash":
                raise AIError("provider_unavailable", "Fast gateway busy")
            return {"content": '{"message": "Xin chào từ DeepSeek Fast!"}', "model": self.model}

    monkeypatch.setattr(local_workspace, "AgyCliModel", FakeAgy)
    monkeypatch.setattr(local_workspace, "GeminiModel", FakeGemini)
    monkeypatch.setattr(local_workspace, "DeepSeekModel", FakeDeepSeek)

    state = {"fail_fast_ds": False}
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "gemini": {"key": "AQ.fake_fast_chat_key_0001", "freeTierConfirmed": True},
                "deepseek": {
                    "url": "https://gateway.example.test",
                    "key": "sk-fake-fast-chat-key-0001",
                    "model": "deepseek-v4.1-flash",
                    "reasonerModel": "deepseek-v4-pro",
                },
                "fixedRouter": {"enabled": True, "agyCustomPath": str(fake_agy)},
            },
        ).raise_for_status()

        # 1. timePreset='standard': ở cấp router M11 chuẩn ưu tiên AGY và fast đẩy AGY trước Ollama
        from mach_backend.ai_router import M11_FLEXIBLE_CHAT, FixedTaskRouter

        router_check = FixedTaskRouter(
            {
                "agy": lambda *_: {},
                "deepseek_chat": lambda *_: {},
                "gemini_flash": lambda *_: {},
                "ollama": lambda *_: {},
            }
        )
        assert router_check.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="standard")[0] == "agy"
        fast_chain = router_check.candidate_chain(M11_FLEXIBLE_CHAT, time_preset="fast")
        assert fast_chain.index("agy") < fast_chain.index("ollama")

        # 1. timePreset='standard' -> ưu tiên AGY đầu tiên với effort='low'
        r_std = client.post(
            "/api/assistant/chat",
            json={"text": "hello", "consent": True, "timePreset": "standard"},
        )
        assert r_std.status_code == 200, r_std.text
        data_std = r_std.json()
        assert data_std["providerUsed"] == "agy"
        assert data_std["modelUsed"] == "agy-cli"
        assert data_std["attemptedProviders"] == ["agy"]
        assert data_std["fallbackFrom"] is None
        assert captured_efforts[-1] == "low"
        assert isinstance(data_std["latencyMs"], int) and data_std["latencyMs"] >= 0
        assert order == ["agy"]
        assert "propose_questions" in captured_prompts[-1]
        assert "propose_patch" in captured_prompts[-1]
        assert "propose_matrix" in captured_prompts[-1]

        # 2. timePreset='fast' (hoặc fastChat=True) -> ưu tiên deepseek_chat/gemini trước AGY
        order.clear()
        r_fast_ok = client.post(
            "/api/assistant/chat",
            json={"text": "hello fast", "consent": True, "timePreset": "fast"},
        )
        assert r_fast_ok.status_code == 200, r_fast_ok.text
        assert r_fast_ok.json()["providerUsed"] == "deepseek_chat"
        assert r_fast_ok.json()["modelUsed"] == "deepseek-v4.1-flash"
        assert order == ["deepseek:deepseek-v4.1-flash"]

        # 3. Nếu deepseek_chat lỗi ở chế độ fast -> nhảy sang gemini_flash kèm fallbackFrom/Reason
        order.clear()
        state["fail_fast_ds"] = True
        r_fast = client.post(
            "/api/assistant/chat",
            json={"text": "hello", "consent": True, "fastChat": True},
        )
        assert r_fast.status_code == 200, r_fast.text
        data_fast = r_fast.json()
        assert data_fast["providerUsed"] == "gemini_flash"
        assert data_fast["attemptedProviders"] == ["deepseek_chat", "gemini_flash"]
        assert data_fast["fallbackFrom"] == "deepseek_chat"
        assert "Fast gateway busy" in (data_fast["fallbackReason"] or "")
        assert order == ["deepseek:deepseek-v4.1-flash", "gemini:gemini-3.8-flash"]

        # 4. timePreset='deep' -> ưu tiên AGY đầu tiên với effort='medium'
        order.clear()
        r_deep = client.post(
            "/api/assistant/chat",
            json={"text": "Phân tích sâu", "consent": True, "timePreset": "deep"},
        )
        assert r_deep.status_code == 200, r_deep.text
        assert r_deep.json()["providerUsed"] == "agy"
        assert captured_efforts[-1] == "medium"
        assert order == ["agy"]

        # 5. timePreset='extended' -> ưu tiên AGY đầu tiên với effort='high'
        order.clear()
        r_ext = client.post(
            "/api/assistant/chat",
            json={"text": "Phân tích chuyên sâu", "consent": True, "timePreset": "extended"},
        )
        assert r_ext.status_code == 200, r_ext.text
        assert r_ext.json()["providerUsed"] == "agy"
        assert captured_efforts[-1] == "high"
        assert order == ["agy"]


def test_question_bank_crud_diacritic_search_if_match_409_clone_uuids(tmp_path):
    app = create_app(tmp_path)
    q = _rich_question_fixture()
    with TestClient(app, headers=ORIGIN) as client:
        # Reject extra fields (ConfigDict(extra="forbid"))
        bad = client.post(
            "/api/question-bank",
            json={"subject": "Toán", "question": q, "unexpectedField": True},
        )
        assert bad.status_code == 422

        # Create 201 preserving richDoc, formulas, tables, images, figure, rubric, explanation
        created = client.post(
            "/api/question-bank",
            json={
                "subject": "Toán học",
                "grade": "12",
                "topic": "Đạo hàm và ứng dụng",
                "tags": ["Giải tích", "Đề minh họa 2025"],
                "question": q,
            },
        )
        assert created.status_code == 201, created.text
        item = created.json()["item"]
        item_id = item["id"]
        assert item["qtype"] == "mcq"
        assert item["level"] == 2
        assert item["points_q4"] == 2
        assert item["question"]["richDoc"] == q["richDoc"]
        assert item["question"]["formulas"] == q["formulas"]
        assert item["question"]["tables"] == q["tables"]
        assert item["question"]["images"] == q["images"]
        assert item["question"]["figure"] == q["figure"]
        assert item["question"]["rubric"] == q["rubric"]
        assert item["question"]["explanation"] == q["explanation"]

        # Search không dấu tiếng Việt (kể cả đ -> d) & lọc metadata
        res_search = client.get(
            "/api/question-bank",
            params={
                "q": "dao ham da thuc",
                "subject": "toan hoc",
                "grade": "12",
                "topic": "ung dung",
                "qtype": "mcq",
                "level": 2,
                "tag": "de minh hoa 2025",
                "limit": 10,
            },
        )
        assert res_search.status_code == 200, res_search.text
        assert res_search.json()["total"] == 1
        assert res_search.json()["items"][0]["id"] == item_id

        # Query rỗng từ dropdown UI (?q=&subject=&grade=&qtype=&level=) vẫn trả 200
        res_empty_filters = client.get(
            "/api/question-bank",
            params={"q": "", "subject": "", "grade": "", "qtype": "", "level": ""},
        )
        assert res_empty_filters.status_code == 200
        assert res_empty_filters.json()["total"] == 1

        # PATCH với If-Match sai -> 409 Conflict
        stale = client.patch(
            f"/api/question-bank/{item_id}",
            json={"topic": "Chủ đề mới"},
            headers={"If-Match": str(item["updated_at"] - 10)},
        )
        assert stale.status_code == 409

        # PATCH với If-Match đúng -> 200 & tăng updated_at
        patched = client.patch(
            f"/api/question-bank/{item_id}",
            json={"topic": "Cực trị hàm số", "tags": ["Cực trị"]},
            headers={"If-Match": str(item["updated_at"])},
        )
        assert patched.status_code == 200, patched.text
        updated_item = patched.json()["item"]
        assert updated_item["topic"] == "Cực trị hàm số"
        assert updated_item["updated_at"] > item["updated_at"]

        # Clone cấp mới toàn bộ UUID
        cloned_res = client.post(f"/api/question-bank/{item_id}/clone")
        assert cloned_res.status_code == 200, cloned_res.text
        cloned = cloned_res.json()["question"]
        assert UUID(cloned["id"])
        assert cloned["id"] != q["id"]
        assert cloned["blockIds"]["stem"] != q["blockIds"]["stem"]
        assert cloned["blockIds"]["explanation"] != q["blockIds"]["explanation"]
        # Paragraph attrs.id trong richDoc được remap đồng bộ với blockIds["stem"]
        assert cloned["richDoc"]["content"][0]["attrs"]["id"] == cloned["blockIds"]["stem"]
        assert cloned["formulas"][0]["id"] != q["formulas"][0]["id"]
        assert cloned["tables"][0]["id"] != q["tables"][0]["id"]
        assert cloned["images"][0]["id"] != q["images"][0]["id"]
        assert cloned["rubric"][0]["id"] != q["rubric"][0]["id"]
        # Nội dung rich giữ nguyên vẹn
        assert cloned["stem"] == q["stem"]
        assert cloned["explanation"] == q["explanation"]
        assert cloned["figure"] == q["figure"]

        # DELETE & kiểm 404
        deleted = client.delete(f"/api/question-bank/{item_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True, "id": item_id}
        assert client.delete(f"/api/question-bank/{item_id}").status_code == 404


def test_question_bank_owner_isolation_shared_db_and_team_workspace(tmp_path):
    # 1. Shared SQLite DB với 2 owner khác nhau -> khác owner trả 404
    store = WorkspaceStore(tmp_path / "shared-db", owner="user-a")
    shared_app = FastAPI()

    @shared_app.exception_handler(AIError)
    async def _err(_req, exc: AIError):
        return JSONResponse({"error": str(exc), "code": exc.code}, exc.http_status or 409)

    register_question_bank_routes(
        shared_app,
        store.connect,
        owner_resolver=lambda req: req.headers.get("x-test-owner", ""),
    )
    q = _rich_question_fixture()
    with TestClient(shared_app) as client:
        r_a = client.post(
            "/api/question-bank",
            json={"subject": "Vật lý", "grade": "11", "question": q},
            headers={"x-test-owner": "user-a"},
        )
        assert r_a.status_code == 201
        item_id = r_a.json()["item"]["id"]

        assert (
            client.get("/api/question-bank", headers={"x-test-owner": "user-b"}).json()["total"]
            == 0
        )
        assert (
            client.patch(
                f"/api/question-bank/{item_id}",
                json={"subject": "Chiếm quyền"},
                headers={"x-test-owner": "user-b"},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/question-bank/{item_id}", headers={"x-test-owner": "user-b"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/question-bank/{item_id}/clone", headers={"x-test-owner": "user-b"}
            ).status_code
            == 404
        )

    # 2. Chế độ nhóm (team_workspace): guest 401, hai tài khoản cô lập hoàn toàn
    team_app = create_team_app(tmp_path / "team")
    accounts = team_app.state.accounts
    admin = accounts.create(
        "admin@example.test", PASSWORD, "Quản trị", accounts.invite(bootstrap=True)
    )
    member = accounts.create(
        "member@example.test",
        PASSWORD,
        "Thành viên",
        accounts.invite(email="member@example.test"),
    )
    with TestClient(team_app, headers=ORIGIN) as guest:
        assert guest.get("/api/question-bank").status_code == 401

    with (
        TestClient(team_app, headers=ORIGIN) as c_admin,
        TestClient(team_app, headers=ORIGIN) as c_member,
    ):
        c_admin.post(
            "/api/account/login", json={"email": admin["email"], "password": PASSWORD}
        ).raise_for_status()
        c_member.post(
            "/api/account/login", json={"email": member["email"], "password": PASSWORD}
        ).raise_for_status()

        created = c_admin.post(
            "/api/question-bank",
            json={"subject": "Hóa học", "grade": "10", "question": q},
        )
        assert created.status_code == 201
        admin_item_id = created.json()["item"]["id"]

        assert c_member.get("/api/question-bank").json()["total"] == 0
        assert c_member.delete(f"/api/question-bank/{admin_item_id}").status_code == 404


def test_question_bank_backup_preview_and_atomic_restore(tmp_path):
    from test_workspace_backup import backup_fixture

    with (
        TestClient(create_app(tmp_path / "src"), headers=ORIGIN) as src_client,
        TestClient(
            create_app(tmp_path / "dst", account_info={"user": {"id": "dst-user"}}),
            headers=ORIGIN,
        ) as dst_client,
    ):
        q = _rich_question_fixture()
        created = src_client.post(
            "/api/question-bank",
            json={"subject": "Toán", "grade": "12", "tags": ["VIP"], "question": q},
        )
        assert created.status_code == 201
        saved_item = created.json()["item"]

        # Kiểm export_workspace_backup gồm questionBank
        exported = export_workspace_backup(src_client.app.state.store)
        assert len(exported["questionBank"]) == 1
        assert exported["questionBank"][0]["id"] == saved_item["id"]

        # Preview & restore trên kho đích
        snapshot = backup_fixture()
        snapshot["questionBank"] = exported["questionBank"]

        preview = dst_client.post("/api/workspace/restore/preview", json=snapshot)
        assert preview.status_code == 200, preview.text
        assert preview.json()["questionBank"] == 1
        assert dst_client.get("/api/question-bank").json()["total"] == 0

        applied = dst_client.post(
            "/api/workspace/restore", json=snapshot, headers={"If-Match": "0"}
        )
        assert applied.status_code == 200, applied.text
        restored_bank = dst_client.get("/api/question-bank").json()
        assert restored_bank["total"] == 1
        assert restored_bank["items"][0]["owner_id"] == "dst-user"
        assert restored_bank["items"][0]["question"]["richDoc"] == q["richDoc"]

        # Bản sao chứa mục questionBank hỏng -> 409 và rollback nguyên tử không đổi state/bank
        before_state = dst_client.get("/api/kv?key=state").json()
        bad_snapshot = backup_fixture()
        bad_snapshot["questionBank"] = [
            {**saved_item, "id": str(uuid4()), "question": {"stem": ""}}
        ]
        rejected = dst_client.post(
            "/api/workspace/restore",
            json=bad_snapshot,
            headers={"If-Match": str(before_state["revision"])},
        )
        assert rejected.status_code == 409
        assert dst_client.get("/api/kv?key=state").json() == before_state
        assert dst_client.get("/api/question-bank").json()["total"] == 1


def test_exam_analytics_clean_exam_performance_and_issue_detection(tmp_path):
    clean = _clean_10_point_exam()
    # Kiểm tốc độ trực tiếp < 20ms
    t0 = time.perf_counter()
    direct = analyze_exam(clean)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 20.0
    assert direct["readinessScore"] == 100
    assert direct["totalQuestions"] == 10
    assert direct["totalPoints"] == 10.0
    assert direct["targetPoints"] == 10.0
    assert direct["pointsDelta"] == 0.0
    assert direct["approvedCount"] == 10
    assert len(direct["levelDistribution"]) == 4
    assert sum(row["count"] for row in direct["levelDistribution"]) == 10
    assert isinstance(direct["typeDistribution"], list)
    mcq_dist = next(row for row in direct["typeDistribution"] if row["type"] == "mcq")
    assert mcq_dist["count"] == 10
    assert direct["answerDistribution"]["imbalanced"] is False
    assert direct["duplicates"] == []
    assert direct["issues"] == []

    # Kiểm qua API với đề có nhiều lỗi đồng thời
    problematic = {
        "title": "Đề thử lỗi",
        "minutes": 90,
        "extraUiMetadata": {"draft": True},
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "level": 0,
                "points": 1.0,
                "stem": "Phương trình chuyển động thẳng đều của vật trên đường thẳng là gì?",
                "options": ["x = x0 + vt", "x = vt^2", "v = at", "a = 0"],
                "answer": 0,
                "explanation": "Công thức chuẩn.",
            },
            {
                "id": "q2",
                "type": "mcq",
                "level": 0,
                "points": 1.0,
                "stem": "Phương trình chuyển động thẳng đều của vật trên đường thẳng là gì",
                "options": ["x = x0 + vt", "x = vt^2", "v = at", "a = 0"],
                "answer": 0,
                "explanation": "",
            },
            {
                "id": "q3",
                "type": "mcq",
                "level": 1,
                "points": 1.0,
                "stem": r"Tính giá trị công thức bị lỗi $x = \frac{1{2}",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
                "explanation": "Thiếu dấu đô la.",
            },
            {
                "id": "q4",
                "type": "mcq",
                "level": 1,
                "points": 1.0,
                "stem": "Câu hỏi bị thiếu đáp án đúng chưa xác nhận?",
                "options": ["A", "B", "C", "D"],
                "answerKnown": False,
                "answer": 1,
                "explanation": "Chưa chốt.",
            },
            {
                "id": "q5",
                "type": "short",
                "level": 2,
                "points": 1.0,
                "stem": "Điền kết quả số nguyên của tích 2 nhân 5",
                "options": [],
                "answerText": "",
                "explanation": "10",
            },
        ],
    }
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        res = client.post("/api/exams/analyze", json={"exam": problematic})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["totalQuestions"] == 5
        assert body["totalPoints"] == 5.0
        assert body["pointsDelta"] == -5.0
        assert body["answerDistribution"]["A"] == 3
        assert body["answerDistribution"]["maxStreak"] == 3
        assert body["answerDistribution"]["streakQuestions"] == [0, 1, 2]
        assert body["answerDistribution"]["imbalanced"] is True
        assert len(body["duplicates"]) == 1
        assert body["duplicates"][0]["q1Index"] == 0
        assert body["duplicates"][0]["q2Index"] == 1
        assert body["duplicates"][0]["similarity"] >= 0.65

        codes = {issue["code"] for issue in body["issues"]}
        assert "points_mismatch" in codes
        assert "missing_answer" in codes
        assert "missing_explanation" in codes
        assert "math_syntax_error" in codes
        assert "answer_imbalance" in codes
        assert "duration_mismatch" in codes
        assert "duplicate_question" in codes
        assert 0 <= body["readinessScore"] < 50


def test_omr_sheet_html_zero_leakage_teacher_shading_and_pdf_export(tmp_path, monkeypatch):
    exam = {
        "title": "Đề Toán 2025 <script>alert(1)</script>",
        "subject": "Toán học",
        "grade": "12",
        "questions": [
            {
                "id": "m1",
                "type": "mcq",
                "stem": "Câu 1",
                "options": ["A", "B", "C", "D"],
                "answer": 2,
                "explanation": "BI_MAT_GIAI_THICH_MCQ",
            },
            {
                "id": "m2",
                "type": "mcq",
                "stem": "Câu 2",
                "options": ["A", "B", "C", "D"],
                "answer": 0,
                "explanation": "Giải thích 2",
            },
            {
                "id": "tf1",
                "type": "truefalse",
                "stem": "Câu đúng sai 1",
                "options": ["Ý a", "Ý b", "Ý c", "Ý d"],
                "truthValues": [True, False, True, False],
                "explanation": "BI_MAT_TF",
            },
            {
                "id": "sh1",
                "type": "short",
                "stem": "Câu trả lời ngắn 1",
                "options": [],
                "answerText": "-1,5",
                "explanation": "BI_MAT_SHORT",
            },
            {
                "id": "es1",
                "type": "essay",
                "stem": "Câu tự luận",
                "options": [],
                "answer": None,
            },
        ],
    }
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        # 1. Bản học sinh (teacher=False): 0 rò đáp án, thoát XSS, đủ cấu trúc Bộ GD&ĐT 2025
        stu = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": False, "variantCode": "204", "format": "html"},
        )
        assert stu.status_code == 200, stu.text
        stu_data = stu.json()
        assert stu_data["name"].startswith("Phieu_OMR_") and stu_data["name"].endswith(".html")
        assert stu_data["downloadUrl"] == f"/api/exports/{stu_data['name']}"
        assert stu_data["questionCounts"] == {
            "mcq": 2,
            "truefalse": 1,
            "short": 1,
            "essay": 1,
            "total": 5,
        }
        stu_html = stu_data["html"]
        assert "@page { size: A4; margin: 10mm; }" in stu_html
        assert "<script>alert(1)</script>" not in stu_html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in stu_html
        assert "Số báo danh" in stu_html
        assert "Mã đề thi" in stu_html
        assert "Phần I." in stu_html
        assert "Phần II." in stu_html
        assert "Phần III." in stu_html
        # Tuyệt đối 0 ô tô đen và 0 rò đáp án / giải thích ở bản học sinh
        assert 'data-filled="true"' not in stu_html
        assert "bubble filled" not in stu_html
        assert "-1,5" not in stu_html
        assert "BI_MAT_GIAI_THICH_MCQ" not in stu_html
        assert "BI_MAT_TF" not in stu_html
        assert "BI_MAT_SHORT" not in stu_html

        dl_html = client.get(stu_data["downloadUrl"])
        assert dl_html.status_code == 200
        assert "Phiếu trả lời trắc nghiệm" in dl_html.text

        # 2. Bản giáo viên (teacher=True): tô đen sẵn mã đề + đáp án Phần I, II, III
        tea = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": True, "variantCode": "204", "format": "html"},
        )
        assert tea.status_code == 200, tea.text
        tea_html = tea.json()["html"]
        assert "Bản đáp án giáo viên" in tea_html
        # 3 chữ số mã đề (2,0,4) + 2 MCQ + 4 ý TF + 4 ký tự "-1,5" = 13 ô được tô đen
        assert tea_html.count('data-filled="true"') == 13
        assert '<td class="write-cell">-</td>' in tea_html
        assert '<td class="write-cell">1</td>' in tea_html
        assert '<td class="write-cell">,</td>' in tea_html
        assert '<td class="write-cell">5</td>' in tea_html

        # 3. Xuất PDF qua Chrome headless (mock subprocess để test chạy nhanh độc lập máy)
        monkeypatch.setattr("mach_backend.omr_sheet.chrome_path", lambda: "/usr/bin/chromium")
        calls: list[list[str]] = []

        def fake_pdf_run(args, **_kwargs):
            calls.append(list(args))
            pdf_arg = next(a for a in args if a.startswith("--print-to-pdf="))
            Path(pdf_arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4\n%OMR-OK\n")
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr("mach_backend.omr_sheet.subprocess.run", fake_pdf_run)
        pdf_res = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": False, "variantCode": "101", "format": "pdf"},
        )
        assert pdf_res.status_code == 200, pdf_res.text
        pdf_data = pdf_res.json()
        assert pdf_data["name"].endswith(".pdf")
        assert len(calls) == 1
        assert "--host-resolver-rules=MAP * ~NOTFOUND" in calls[0]
        assert "--no-proxy-server" in calls[0]
        dl_pdf = client.get(pdf_data["downloadUrl"])
        assert dl_pdf.status_code == 200
        assert dl_pdf.content.startswith(b"%PDF-1.4")

        # 4. Khi không có Chrome -> trả lỗi pdf_unavailable rõ ràng
        monkeypatch.setattr("mach_backend.omr_sheet.chrome_path", lambda: None)
        no_chrome = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": False, "variantCode": "101", "format": "pdf"},
        )
        assert no_chrome.status_code == 409
        assert no_chrome.json()["code"] == "pdf_unavailable"

        # 5. Nếu Chrome thất bại lần đầu trên Linux -> tự thử lại với --no-sandbox
        monkeypatch.setattr("mach_backend.omr_sheet.os", SimpleNamespace(name="posix"))
        monkeypatch.setattr("mach_backend.omr_sheet.chrome_path", lambda: "/usr/bin/chromium")
        retry_calls: list[list[str]] = []

        def retry_pdf_run(args, **_kwargs):
            retry_calls.append(list(args))
            if len(retry_calls) == 1:
                raise subprocess.CalledProcessError(1, args)
            pdf_arg = next(a for a in args if a.startswith("--print-to-pdf="))
            Path(pdf_arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4\n%OMR-LINUX-RETRY\n")
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr("mach_backend.omr_sheet.subprocess.run", retry_pdf_run)
        linux_pdf = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": True, "variantCode": "101", "format": "pdf"},
        )
        assert linux_pdf.status_code == 200, linux_pdf.text
        assert len(retry_calls) == 2
        assert "--no-sandbox" in retry_calls[1]


def test_exam_analytics_two_track_choice_group_effective_points():
    two_track = {
        "title": "Đề Tin học 12 hai hướng",
        "minutes": 45,
        "questions": [
            {
                "id": "c1",
                "type": "mcq",
                "level": 0,
                "points": 5.0,
                "stem": "Câu chung phần mạng máy tính?",
                "options": ["A1", "B1", "C1", "D1"],
                "answer": 0,
                "explanation": "Giải thích chung",
            },
            {
                "id": "a1",
                "type": "mcq",
                "choiceGroup": "Tự chọn A",
                "level": 1,
                "points": 5.0,
                "stem": "Câu nhánh A khoa học máy tính?",
                "options": ["A2", "B2", "C2", "D2"],
                "answer": 1,
                "explanation": "Giải thích A",
            },
            {
                "id": "b1",
                "type": "mcq",
                "choiceGroup": "Tự chọn B",
                "level": 1,
                "points": 5.0,
                "stem": "Câu nhánh B tin học ứng dụng?",
                "options": ["A3", "B3", "C3", "D3"],
                "answer": 2,
                "explanation": "Giải thích B",
            },
        ],
    }
    report = analyze_exam(two_track)
    assert report["totalPoints"] == 10.0
    assert report["pointsDelta"] == 0.0
    assert not any(issue["code"] == "points_mismatch" for issue in report["issues"])
