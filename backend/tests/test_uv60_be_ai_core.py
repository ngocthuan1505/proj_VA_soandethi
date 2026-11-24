"""Kiểm thử 7 hạng mục backend UV60 (AGY, Router, Bank, Backup, Analytics, Export, Hybrid)."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sqlite3
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from mach_backend.agy_cli_model import AgyCliModel
from mach_backend.ai_contract import AIError, Locator, SourceFragment
from mach_backend.ai_router import FixedTaskRouter
from mach_backend.ai_sources import rank_source_fragments, workspace_page_sources
from mach_backend.exam_analytics import analyze_exam
from mach_backend.exam_planning import PlanRequest, deterministic_exam_blueprint
from mach_backend.local_documents import (
    exam_html,
    exam_variant,
    extract_text,
    preview_exam_variant,
)
from mach_backend.local_workspace import create_app
from mach_backend.poc_connections import DEEPSEEK_BASE
from mach_backend.question_bank import ensure_question_bank_schema
from mach_backend.word_export import export_docx

ORIGIN = {"Origin": "http://testserver"}


def _png_data_url(color: str = "blue") -> str:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), color).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_agy_cli_model_appends_effort_and_model_flags_when_valid(tmp_path):
    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_bytes(b"MZ")
    seen_cmds: list[list[str]] = []

    def fake_runner(cmd, **_kwargs):
        seen_cmds.append(list(cmd))
        return SimpleNamespace(stdout=b'{"message": "OK"}')

    model_low = AgyCliModel(
        None,
        custom_path=str(fake_agy),
        runner=fake_runner,
        effort="low",
        model="gemini-2.5-pro",
    )
    res = asyncio.run(model_low("chat", {"messages": [{"role": "user", "content": "Chào"}]}))
    assert res["provider"] == "agy"
    assert res["model"] == "gemini-2.5-pro"
    assert "--effort" in seen_cmds[0]
    assert seen_cmds[0][seen_cmds[0].index("--effort") + 1] == "low"
    assert "--model" in seen_cmds[0]
    assert seen_cmds[0][seen_cmds[0].index("--model") + 1] == "gemini-2.5-pro"

    model_invalid = AgyCliModel(
        None,
        custom_path=str(fake_agy),
        runner=fake_runner,
        effort="invalid_tier",
    )
    res2 = asyncio.run(model_invalid("chat", {"messages": [{"role": "user", "content": "Hi"}]}))
    assert res2["model"] == "agy-cli"
    assert "--effort" not in seen_cmds[1]


def test_fixed_router_tracks_attempted_providers_and_redacted_fallback():
    async def fail_agy(_purpose, _body):
        raise AIError("provider_timeout", "AGY quá hạn với khóa sk-secret1234567890abcdef")

    async def ok_gemini(_purpose, _body):
        return {"content": '{"message": "Dự phòng OK"}', "model": "gemini-4-hydrogen"}

    router = FixedTaskRouter({"agy": fail_agy, "gemini_hydrogen": ok_gemini})
    res = asyncio.run(router("chat", {"messages": []}))
    assert res["providerFamily"] == "gemini_hydrogen"
    assert res["attemptedProviders"] == ["agy", "gemini_hydrogen"]
    assert res["fallbackFrom"] == "agy"
    assert "sk-secret1234567890abcdef" not in (res.get("fallbackReason") or "")
    assert res.get("fallbackReason")


def test_scoped_patch_uses_fixed_router_cross_model_and_allows_005_rubric_step(
    tmp_path, monkeypatch
):
    from mach_backend import local_workspace

    q = {
        "id": str(uuid4()),
        "v": 1,
        "type": "essay",
        "stem": "Tính chu vi hình chữ nhật dài 4 cm, rộng 2 cm.",
        "options": [],
        "answer": 0,
        "explanation": "Chu vi là (4 + 2) * 2 = 12 cm.",
        "points": 0.4,
        "rubric": [{"text": "Nêu đúng công thức và kết quả 12 cm", "points": 0.4}],
        "blockIds": {
            f: str(uuid4()) for f in ("stem", "options", "answer", "explanation", "rubric")
        },
    }
    exam = {"id": str(uuid4()), "revision": 1, "questions": [q], "docs": [], "assistantSources": []}
    route_trace: list[tuple[str, str]] = []

    class FakeGemini:
        def __init__(self, _client, _key, _log, *, model, key_pool, auto_fallback):
            self.model = model

        async def __call__(self, purpose, _body):
            route_trace.append(("gemini:" + self.model, purpose))
            if purpose == "M10_SCOPED_PATCH":
                return {
                    "content": json.dumps(
                        {
                            "edits": [
                                {
                                    "blockId": q["blockIds"]["stem"],
                                    "op": "replace",
                                    "content": "Tính chu vi hình chữ nhật dài 5 cm, rộng 3 cm.",
                                },
                                {
                                    "blockId": q["blockIds"]["explanation"],
                                    "op": "replace",
                                    "content": "Chu vi là (5 + 3) * 2 = 16 cm.",
                                },
                                {
                                    "blockId": q["blockIds"]["rubric"],
                                    "op": "replace",
                                    "content": [
                                        {"text": "Viết đúng công thức chu vi", "points": 0.15},
                                        {"text": "Tính đúng kết quả 16 cm", "points": 0.25},
                                    ],
                                },
                            ],
                            "message": "Đã đổi số liệu và chia barem bước 0,05.",
                        }
                    ),
                    "model": self.model,
                }
            return {
                "content": json.dumps({"reviews": [{"ordinal": 0, "agrees": True}]}),
                "model": self.model,
            }

    class FakeDeepSeek:
        def __init__(self, _client, _key, _log, *, model, base_url, backup_models, cost_tracker):
            self.model = model

        async def __call__(self, purpose, _body):
            route_trace.append(("deepseek:" + self.model, purpose))
            return {
                "content": json.dumps(
                    {
                        "reviews": [
                            {
                                "ordinal": 0,
                                "solution": "Chu vi = (5 + 3) * 2 = 16 cm.",
                                "uncertain": False,
                            }
                        ]
                    }
                ),
                "model": self.model,
            }

    monkeypatch.setattr(local_workspace, "GeminiModel", FakeGemini)
    monkeypatch.setattr(local_workspace, "DeepSeekModel", FakeDeepSeek)

    app = create_app(tmp_path)
    app.state.store.put("state", {"exams": [exam], "current": exam["id"]})
    with TestClient(app, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "gemini": {"key": "AQ.fake_patch_key_0001", "freeTierConfirmed": True},
                "deepseek": {
                    "url": "https://gateway.example.test",
                    "key": "sk-fake-patch-key-0001",
                    "model": "deepseek-chat",
                    "reasonerModel": "deepseek-reasoner",
                },
                "fixedRouter": {"enabled": True},
            },
        ).raise_for_status()
        fp = client.get("/api/config").json()["fingerprint"]
        res = client.post(
            "/api/assistant/patch",
            headers={"X-PoC-Config": fp},
            json={
                "exam": {"id": exam["id"], "revision": 1},
                "scopes": [
                    {
                        "id": q["id"],
                        "version": 1,
                        "field": "stem",
                        "blockId": q["blockIds"]["stem"],
                        "wholeField": True,
                    }
                ],
                "request": "Đổi kích thước thành 5 cm và 3 cm",
                "consent": True,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["confirmationId"]
        # M10 chạy Gemini, M06 giải mù chéo họ chạy DeepSeek, M07 chạy Gemini
        assert route_trace[0][0].startswith("gemini:") and route_trace[0][1] == "M10_SCOPED_PATCH"
        assert route_trace[1][0].startswith("deepseek:") and route_trace[1][1] == "M06_BLIND_SOLVE"
        assert route_trace[2][1] == "M07_DISTRACTOR_CHECK"


def test_exam_plan_fallback_local_when_ai_unavailable_and_enforces_consent(tmp_path, monkeypatch):
    async def broken_ollama(*_args, **_kwargs):
        raise httpx.ConnectError("Connection refused to Ollama")

    monkeypatch.setattr("mach_backend.local_workspace.LocalModel.__call__", broken_ollama)
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        # consent=False vẫn trả 409 consent_required
        no_consent = client.post(
            "/api/ai/exam-plan",
            json={
                "request": "Đề Toán 4 cuối kỳ",
                "subject": "Toán",
                "grade": 4,
                "term": "cuối học kì I",
                "consent": False,
            },
        )
        assert no_consent.status_code == 409
        assert no_consent.json()["code"] == "consent_required"

        # Ollama sập -> fallback xác định tại máy, không 500
        primary = client.post(
            "/api/ai/exam-plan",
            json={
                "request": "Đề Toán lớp 4 giữa kỳ",
                "subject": "Toán",
                "grade": 4,
                "term": "giữa học kì I",
                "consent": True,
            },
        )
        assert primary.status_code == 200, primary.text
        data = primary.json()
        assert data["sentToAI"] is False
        assert data["fallbackLocal"] is True
        assert 4 <= data["count"] <= 10
        assert {row["type"] for row in data["matrix"]} == {"mcq", "essay"}
        assert "tại máy" in data["notes"].casefold()

    # Kiểm trực tiếp deterministic_exam_blueprint với dạng chỉ định riêng
    req = PlanRequest(
        request="Đề Tin 12",
        subject="Tin học",
        grade=12,
        term="cuối kì II",
        count=6,
        minutes=45,
        types=["truefalse", "short"],
        consent=True,
    )
    bp = deterministic_exam_blueprint(req)
    assert bp["count"] == 6
    assert {r["type"] for r in bp["matrix"]} <= {"truefalse", "short"}
    assert bp["sentToAI"] is False and bp["fallbackLocal"] is True


def test_question_bank_decimal_points_migration_facets_pagination_and_duplicates(tmp_path):
    # 1. Kiểm tự động ALTER TABLE thêm points_real trên DB cũ
    legacy_db = tmp_path / "legacy.sqlite"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute(
            """
            CREATE TABLE question_bank (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '',
                grade TEXT NOT NULL DEFAULT '', topic TEXT NOT NULL DEFAULT '',
                qtype TEXT NOT NULL DEFAULT 'mcq', level INTEGER NOT NULL DEFAULT 0,
                points_q4 INTEGER NOT NULL DEFAULT 1, tags_json TEXT NOT NULL DEFAULT '[]',
                question_json TEXT NOT NULL, search_text TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            )
            """
        )
        ensure_question_bank_schema(conn)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(question_bank)").fetchall()}
        assert "points_real" in cols

    # 2. Kiểm API: 0.4 giữ nguyên, tự rút subject/grade, duplicateOf, offset/hasMore/facets
    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        r1 = client.post(
            "/api/question-bank",
            json={
                "points": 0.4,
                "question": {
                    "type": "mcq",
                    "subject": "Toán",
                    "grade": "9",
                    "topic": "Phương trình bậc hai",
                    "level": 1,
                    "points": 0.4,
                    "stem": "Giải phương trình $x^2 - 4 = 0$.",
                    "options": ["2", "-2", "2 và -2", "4"],
                    "answer": 2,
                },
            },
        )
        assert r1.status_code == 201, r1.text
        b1 = r1.json()
        assert b1["duplicateOf"] is None
        assert b1["item"]["subject"] == "Toán"
        assert b1["item"]["grade"] == "9"
        assert b1["item"]["points"] == pytest.approx(0.4)
        assert b1["item"]["points_q4"] == 2

        # Câu trùng stem + subject + grade (khác hoa thường/dấu) -> duplicateOf trỏ về câu 1
        r_dup = client.post(
            "/api/question-bank",
            json={
                "subject": "Toán",
                "grade": "9",
                "topic": "Phương trình bậc hai",
                "question": {
                    "type": "mcq",
                    "points": 0.4,
                    "stem": "giai phuong trinh $x^2 - 4 = 0$.",
                    "options": ["A", "B", "C", "D"],
                    "answer": 0,
                },
            },
        )
        assert r_dup.status_code == 201
        assert r_dup.json()["duplicateOf"] == b1["item"]["id"]

        # Thêm câu môn khác để kiểm facets toàn tập và phân trang offset/hasMore
        r3 = client.post(
            "/api/question-bank",
            json={
                "subject": "Ngữ văn",
                "grade": "7",
                "topic": "Nghị luận xã hội",
                "points": 1.25,
                "question": {
                    "type": "essay",
                    "stem": "Viết đoạn văn về lòng nhân ái.",
                    "points": 1.25,
                },
            },
        )
        assert r3.status_code == 201
        assert r3.json()["duplicateOf"] is None

        # PATCH points giữ chính xác 0.35
        patched = client.patch(
            f"/api/question-bank/{b1['item']['id']}",
            json={"points": 0.35},
            headers={"If-Match": str(b1["item"]["updated_at"])},
        )
        assert patched.status_code == 200
        assert patched.json()["item"]["points"] == pytest.approx(0.35)

        page1 = client.get("/api/question-bank", params={"limit": 2, "offset": 0}).json()
        assert page1["total"] == 3
        assert len(page1["items"]) == 2
        assert page1["hasMore"] is True
        assert set(page1["facets"]["subjects"]) == {"Toán", "Ngữ văn"}
        assert page1["facets"]["grades"] == ["7", "9"]
        assert set(page1["facets"]["topics"]) == {"Phương trình bậc hai", "Nghị luận xã hội"}

        page2 = client.get("/api/question-bank", params={"limit": 2, "offset": 2}).json()
        assert len(page2["items"]) == 1
        assert page2["hasMore"] is False


def test_workspace_backup_endpoint_includes_curriculum_sources_and_restores_040_bank(tmp_path):
    with (
        TestClient(create_app(tmp_path / "src"), headers=ORIGIN) as src,
        TestClient(create_app(tmp_path / "dst"), headers=ORIGIN) as dst,
    ):
        exam_id = str(uuid4())
        state = {
            "exams": [
                {
                    "id": exam_id,
                    "revision": 1,
                    "title": "Đề mẫu sao lưu",
                    "questions": [],
                    "docs": [],
                    "matrix": [],
                    "history": [],
                    "undo": [],
                    "redo": [],
                    "chat": [],
                    "data": [],
                    "quote": {"text": "", "versions": []},
                }
            ],
            "prefs": [],
            "current": exam_id,
        }
        src.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        src.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 9,
                "subject": "Toán",
                "title": "Học liệu tự biên soạn",
                "license_status": "teacher_owned",
                "content_excerpt": "Hệ phương trình bậc nhất hai ẩn.",
            },
        ).raise_for_status()
        src.post(
            "/api/question-bank",
            json={
                "subject": "Toán",
                "grade": "9",
                "points": 0.4,
                "question": {"type": "mcq", "stem": "Câu 0.4 điểm", "points": 0.4},
            },
        ).raise_for_status()

        backup_res = src.get("/api/workspace/backup")
        assert backup_res.status_code == 200, backup_res.text
        backup = backup_res.json()
        assert len(backup["curriculumSources"]) == 1
        assert len(backup["questionBank"]) == 1
        assert backup["questionBank"][0]["points"] == pytest.approx(0.4)

        preview = dst.post("/api/workspace/restore/preview", json=backup)
        assert preview.status_code == 200, preview.text
        assert preview.json()["curriculumSources"] == 1
        assert preview.json()["questionBank"] == 1

        applied = dst.post("/api/workspace/restore", json=backup, headers={"If-Match": "0"})
        assert applied.status_code == 200, applied.text
        restored_bank = dst.get("/api/question-bank").json()
        assert restored_bank["items"][0]["points"] == pytest.approx(0.4)
        restored_sources = dst.get("/api/lesson-catalog/sources").json()
        assert len(restored_sources["sources"]) == 1


def test_exam_analytics_empty_selected_option_incomplete_and_duplicate_cap():
    empty_opt_exam = {
        "minutes": 15,
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "level": 0,
                "points": 10.0,
                "stem": "Câu hỏi có đáp án trỏ vào phương án trống?",
                "options": ["Phương án A", "   ", "Phương án C", "Phương án D"],
                "answer": 1,
                "explanation": "Lời giải.",
            }
        ],
    }
    report = analyze_exam(empty_opt_exam)
    codes = {i["code"]: i for i in report["issues"]}
    assert "empty_selected_option" in codes
    assert codes["empty_selected_option"]["severity"] == "error"
    assert (
        codes["empty_selected_option"]["message"]
        == "Câu 1: Phương án đang chọn làm đáp án bị trống nội dung."
    )
    assert "incomplete_options" in codes
    assert codes["incomplete_options"]["severity"] == "warn"

    # 20 câu giống nhau -> 190 cặp trùng, nhưng issues chỉ giữ tối đa 15 + 1 summary warn
    many_dups = {
        "minutes": 30,
        "questions": [
            {
                "id": f"d{i}",
                "type": "mcq",
                "level": 0,
                "points": 0.5,
                "stem": "Tính giá trị biểu thức đại số bậc nhất theo ẩn x trong tập số thực.",
                "options": ["1", "2", "3", "4"],
                "answer": i % 4,
                "explanation": "Giải thích.",
            }
            for i in range(20)
        ],
    }
    dup_report = analyze_exam(many_dups)
    assert len(dup_report["duplicates"]) == 190
    dup_issues = [i for i in dup_report["issues"] if i["code"] == "duplicate_question"]
    dup_summary = [i for i in dup_report["issues"] if i["code"] == "duplicate_question_summary"]
    assert len(dup_issues) == 15
    assert len(dup_summary) == 1
    assert "175" in dup_summary[0]["message"]


def test_export_filenames_history_lock_position_layout_watermark_and_extract_errors(tmp_path):
    wm_url = _png_data_url("red")
    exam = {
        "id": str(uuid4()),
        "revision": 3,
        "title": "Đề kiểm tra giữa kì",
        "subject": "Toán học",
        "grade": "9",
        "minutes": 45,
        "layout": {
            "font": "Times New Roman",
            "fontSize": 14,
            "lineHeight": 1.6,
            "mcqColumns": 2,
            "watermarkImage": wm_url,
        },
        "questions": [
            {
                "id": "q1",
                "type": "mcq",
                "stem": "Câu một",
                "options": ["1", "2", "3", "4"],
                "answer": 0,
                "explanation": "G1",
            },
            {
                "id": "q2",
                "type": "mcq",
                "lockPosition": True,
                "stem": "Câu hai cố định",
                "options": ["A1", "B1", "C1", "D1"],
                "answer": 1,
                "explanation": "G2",
            },
            {
                "id": "q3",
                "type": "mcq",
                "stem": "Câu ba",
                "options": ["5", "6", "7", "8"],
                "answer": 2,
                "explanation": "G3",
            },
            {
                "id": "q4",
                "type": "mcq",
                "stem": "Câu bốn",
                "options": ["9", "10", "11", "12"],
                "answer": 3,
                "explanation": "G4",
            },
        ],
    }

    # 1. lockPosition giữ đúng vị trí câu 2 khi trộn mã đề & preview
    var = exam_variant(exam, {"questionIds": ["q1", "q2", "q3", "q4"], "offset": 1})
    assert [q["id"] for q in var["questions"]] == ["q3", "q2", "q4", "q1"]
    prev = preview_exam_variant(
        {"exam": exam, "variant": {"questionIds": ["q1", "q2", "q3", "q4"], "offset": 1}}
    )
    assert prev["questionMappings"][1]["originalNumber"] == 2
    assert prev["questionMappings"][1]["locked"] is True

    # 2. Layout lineHeight, mcqColumns=2, watermarkImage trên HTML & DOCX
    rendered_html = exam_html(exam, False, "http://localhost")
    assert "line-height:1.6" in rendered_html
    assert 'class="mcq-cols-2"' in rendered_html
    assert 'class="watermark-img"' in rendered_html

    docx_bytes = export_docx(exam, False, None)
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
        names = zf.namelist()
        assert any(n.startswith("word/header") for n in names)
        assert any(n.startswith("word/media/") for n in names)
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "<w:tbl>" in doc_xml
        assert 'w:val="none"' in doc_xml

    bad_wm_exam = {**exam, "layout": {"watermarkImage": "data:image/svg+xml;base64,PHN2Zz4="}}
    with pytest.raises(AIError, match="PNG hoặc JPEG"):
        exam_html(bad_wm_exam, False, "http://localhost")

    # 3. Tên tệp xuất có nghĩa bắt đầu bằng De_thi_, lịch sử xuất SQLite & chặn workspace.sqlite
    with TestClient(create_app(tmp_path), headers=ORIGIN) as client:
        r_html = client.post(
            "/api/save-export",
            json={"type": "exam", "exam": exam, "format": "html", "classLabel": "9A1"},
        )
        assert r_html.status_code == 200, r_html.text
        fname = r_html.json()["filename"]
        assert fname.startswith("De_thi_Toan_hoc_9_9A1_v3_HS_") and fname.endswith(".html")
        assert client.get(r_html.json()["url"]).status_code == 200
        assert client.get("/api/exports/workspace.sqlite").status_code == 404

        r_tn = client.post("/api/exports/tnmaker-pack", json={"exam": exam, "classLabel": "9A1"})
        assert r_tn.status_code == 200, r_tn.text

        r_omr = client.post(
            "/api/exports/omr-sheet",
            json={"exam": exam, "teacher": False, "variantCode": "101", "format": "html"},
        )
        assert r_omr.status_code == 200, r_omr.text

        hist = client.get(f"/api/exams/{exam['id']}/exports")
        assert hist.status_code == 200, hist.text
        rows = hist.json()["exports"]
        assert len(rows) == 3
        assert {row["format"] for row in rows} == {"html", "tnmaker-zip", "omr-html"}
        assert any(row["classLabel"] == "9A1" and row["revision"] == 3 for row in rows)

    # 4. Tách lỗi .docx hỏng, .xlsx gợi ý nhập ma trận và >15MB
    with pytest.raises(AIError) as exc_docx:
        extract_text(
            "hong.docx",
            "data:application/octet-stream;base64," + base64.b64encode(b"notzip").decode(),
        )
    assert "hỏng" in str(exc_docx.value).casefold()
    assert "15 MB" not in str(exc_docx.value)

    with pytest.raises(AIError) as exc_xlsx:
        extract_text(
            "matran.xlsx",
            "data:application/octet-stream;base64," + base64.b64encode(b"abc").decode(),
        )
    assert exc_xlsx.value.code == "unsupported_document"
    assert "Ma trận → Nhập ma trận từ file" in str(exc_xlsx.value)


def test_hybrid_retrieval_teacher_only_and_masked_status_gateway_url(tmp_path):
    # 1. Hybrid retrieval BM25 + char-trigram cosine
    frags = [
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=1),
            text="Bài thơ Mùa xuân nho nhỏ của Thanh Hải viết về khát vọng cống hiến.",
        ),
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=2),
            text=(
                "Định lí Pytago trong tam giác vuông: bình phương cạnh huyền "
                "bằng tổng bình phương hai cạnh góc vuông."
            ),
        ),
        SourceFragment(
            ownerId="local",
            sourceId=uuid4(),
            sourceVersion=1,
            locator=Locator(kind="page", index=3),
            text="Chuyển động thẳng biến đổi đều và công thức gia tốc trong vật lí.",
        ),
    ]
    ranked = rank_source_fragments("dinh li pytago tam giac vuong", frags, top_k=2)
    assert len(ranked) == 2
    assert "Pytago" in ranked[0].text

    # 2. workspace_page_sources(teacher_files_only=True) loại nguồn catalog=True
    cat_id, teacher_id = str(uuid4()), str(uuid4())
    exam_docs = {
        "docs": [
            {
                "id": cat_id,
                "catalog": True,
                "version": 2,
                "pages": [{"number": 1, "text": "Nguồn thư viện mẫu", "method": "manual"}],
            },
            {
                "id": teacher_id,
                "catalog": False,
                "version": 1,
                "pages": [{"number": 1, "text": "Tài liệu riêng của giáo viên"}],
            },
        ]
    }
    keys = (
        (uuid4() if False else __import__("uuid").UUID(cat_id), Locator(kind="page", index=1)),
        (__import__("uuid").UUID(teacher_id), Locator(kind="page", index=1)),
    )
    filtered = workspace_page_sources(exam_docs, "local", keys, None, teacher_files_only=True)
    assert len(filtered) == 1
    assert str(filtered[0].sourceId) == teacher_id

    # 3. Chat teacherFilesOnly lọc nguồn catalog & /api/status che custom gateway URL
    captured_payloads: list[dict] = []

    async def capture_call(_purpose, body):
        captured_payloads.append(body)
        return {"content": '{"message": "Đã bám tài liệu giáo viên."}', "model": "fixture"}

    app = create_app(tmp_path, agent_call=capture_call)
    with TestClient(app, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "deepseek": {
                    "url": "https://secret-private-gw.example.test/v1",
                    "key": "sk-fake-mask-test-0001",
                },
            },
        ).raise_for_status()

        st = client.get("/api/status").json()
        assert st["config"]["deepseek"]["url"] == "[cổng riêng đã cấu hình]"
        assert st["config"]["deepseek"]["customGatewayConfigured"] is True
        assert "secret-private-gw.example.test" not in json.dumps(st)

        cfg = client.get("/api/config").json()
        assert cfg["deepseek"]["url"] == "https://secret-private-gw.example.test/v1"
        assert cfg["deepseek"]["customGatewayConfigured"] is True

        # Reset về DEEPSEEK_BASE mặc định -> hiện DEEPSEEK_BASE, customGatewayConfigured=False
        client.post(
            "/api/config", json={"saveLocally": False, "deepseek": {"url": ""}}
        ).raise_for_status()
        st_def = client.get("/api/status").json()
        assert st_def["config"]["deepseek"]["url"] == DEEPSEEK_BASE
        assert st_def["config"]["deepseek"]["customGatewayConfigured"] is False

        # Gửi chat với teacherFilesOnly=True
        chat_res = client.post(
            "/api/assistant/chat",
            json={
                "text": "Hỏi về tài liệu",
                "consent": True,
                "teacherFilesOnly": True,
                "context": [
                    {
                        "kind": "attached-source",
                        "name": "SGK Mẫu",
                        "catalog": True,
                        "excerpt": "NGUON_MAU_CAM",
                    },
                    {
                        "kind": "attached-source",
                        "name": "Giáo án GV",
                        "catalog": False,
                        "excerpt": "NGUON_RIENG_GV",
                    },
                ],
            },
        )
        assert chat_res.status_code == 200, chat_res.text
        sent_user = captured_payloads[-1]["messages"][1]["content"]
        assert "NGUON_RIENG_GV" in sent_user
        assert "NGUON_MAU_CAM" not in sent_user
        assert "CHỈ BÁM TÀI LIỆU GIÁO VIÊN" in captured_payloads[-1]["messages"][0]["content"]


def test_chat_endpoint_derives_budget_timeout_from_time_preset(tmp_path, monkeypatch):
    from mach_backend import local_workspace
    from mach_backend.poc_policy import ExtendedCallBudget

    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_bytes(b"MZ")
    recorded: list[tuple[int, str | None]] = []

    class SpyBudget(ExtendedCallBudget):
        pass

    class SpyAgy:
        def __init__(self, _log, *, custom_path="", budget=None, effort=None):
            assert custom_path == str(fake_agy)
            assert budget is not None
            recorded.append((int(budget.seconds), effort))

        async def __call__(self, _purpose, _body):
            return {"content": '{"message": "OK"}', "model": "agy-cli"}

    monkeypatch.setattr(local_workspace, "ExtendedCallBudget", SpyBudget)
    monkeypatch.setattr(local_workspace, "AgyCliModel", SpyAgy)

    app = create_app(tmp_path)
    with TestClient(app, headers=ORIGIN) as client:
        client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "fixedRouter": {"enabled": True, "agyCustomPath": str(fake_agy)},
            },
        ).raise_for_status()
        for preset in ("fast", "standard", "deep", "extended"):
            res = client.post(
                "/api/assistant/chat",
                json={"text": "Xin chào", "consent": True, "timePreset": preset},
            )
            assert res.status_code == 200, res.text

    assert recorded == [
        (120, "low"),
        (300, "low"),
        (1200, "medium"),
        (3600, "high"),
    ]
