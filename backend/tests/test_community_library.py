"""Kiểm thử kho đề cộng đồng: đồng ý công bố, lọc, sao chép độc lập và thu hồi an toàn."""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections.abc import Generator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mach_backend.community_library import install_community_library
from mach_backend.local_documents import exam_html
from mach_backend.share_snapshot import snapshot as build_share_snapshot


def _header_owner(request: Request) -> str:
    return request.headers.get("X-User-Id", "teacher_a")


def _build_rich_exam(
    *,
    exam_id: str | None = None,
    title: str = "Đề ôn tập Toán 10 — Hàm số",
    subject: str = "Toán",
    grade: str | int = "10",
    series: str = "Kết nối tri thức",
    chapter: str = "Chương 1: Mệnh đề và Tập hợp",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Tạo fixture đề thi có đầy đủ trường nhạy cảm và đáp án để kiểm tra lọc sạch."""
    q1_id = str(uuid4())
    q2_id = str(uuid4())
    q3_id = str(uuid4())
    q4_id = str(uuid4())
    return {
        "id": exam_id or str(uuid4()),
        "revision": 7,
        "title": title,
        "school": "THPT MẪU",
        "subject": subject,
        "grade": grade,
        "minutes": 45,
        "instructions": "Chọn phương án đúng nhất hoặc trình bày rõ ràng.",
        "series": series,
        "chapter": chapter,
        "tags": tags if tags is not None else ["toan-10", "giua-ki"],
        "blockIds": {
            "heading": str(uuid4()),
            "general": str(uuid4()),
            "marking": str(uuid4()),
        },
        "chat": [{"role": "user", "text": "CHAT_NOI_BO_KHONG_DUOC_CONG_BO"}],
        "history": [{"id": "h1", "label": "LICH_SU_NOI_BO_KIN"}],
        "aiConfig": {"provider": "gemini", "model": "AI_CONFIG_NOI_BO"},
        "apiKey": "API_KEY_BI_MAT_12345",
        "secret": "SECRET_NOI_BO_XYZ",
        "token": "TOKEN_PHIEN_LAM_VIEC_ABC",
        "notes": "GHI_CHU_NOI_BO_CUA_GIAO_VIEN",
        "docs": [{"id": "d1", "text": "TAI_LIEU_RIENG_NOI_BO"}],
        "undo": [{"label": "UNDO_NOI_BO"}],
        "redo": [{"label": "REDO_NOI_BO"}],
        "appliedPrefs": [{"text": "PREF_NOI_BO", "confirmedAt": 1}],
        "quote": {"text": "Ngữ liệu công khai minh họa.", "versions": ["PHIEN_BAN_NGU_LIEU_KIN"]},
        "questions": [
            {
                "id": q1_id,
                "v": 4,
                "type": "mcq",
                "stem": "Cho tập hợp $A = \\{1, 2\\}$. Số tập hợp con của $A$ là bao nhiêu?",
                "points": 2.5,
                "topic": "Tập hợp",
                "level": 0,
                "options": ["2", "3", "4", "8"],
                "answer": 2,
                "answerKnown": True,
                "explanation": "GIAI_THICH_MCQ_KIN: $2^2 = 4$.",
                "explanationDoc": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "GIAI_THICH_DOC_KIN"}],
                        }
                    ],
                },
                "rubric": [{"id": str(uuid4()), "text": "BAREM_MCQ_KIN", "points": 2.5}],
                "solution": "LOI_GIAI_SOLUTION_MCQ_KIN",
                "blindSolution": "BLIND_SOLUTION_KIN",
                "check": {"notes": "CHECK_NOI_BO_KIN"},
                "evidence": [{"quote": "DAN_CHUNG_NOI_BO_KIN"}],
                "approval": {"version": 4, "status": "approved", "reviewer": "TEN_NGUOI_RA_KIN"},
                "notes": "NOTE_CAU_HOI_NOI_BO_KIN",
                "apiKey": "Q_API_KEY_KIN",
                "secret": "Q_SECRET_KIN",
                "token": "Q_TOKEN_KIN",
                "aiConfig": {"temp": 0, "tag": "Q_AICONFIG_KIN"},
                "chat": [{"text": "Q_CHAT_KIN"}],
                "history": ["Q_HISTORY_KIN"],
                "blockIds": {
                    "stem": str(uuid4()),
                    "options": str(uuid4()),
                    "explanation": str(uuid4()),
                    "rubric": str(uuid4()),
                },
                "formulas": [{"id": str(uuid4()), "latex": r"2^2 = 4", "display": False}],
                "richDoc": {
                    "type": "doc",
                    "private": "RICHDOC_NODE_KIN",
                    "content": [
                        {
                            "type": "paragraph",
                            "attrs": {"private": "RICHDOC_ATTR_KIN"},
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Cho tập hợp $A = \\{1, 2\\}$. "
                                        "Số tập hợp con của $A$ là bao nhiêu?"
                                    ),
                                    "marks": [
                                        {"type": "bold", "attrs": {"private": "MARK_ATTR_KIN"}}
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
            {
                "id": q2_id,
                "v": 2,
                "type": "short",
                "stem": "Tính $3 + 4 \\times 2$.",
                "points": 2.5,
                "options": [],
                "answer": 0,
                "answerKnown": True,
                "answerText": "DAP_AN_SHORT_11",
                "explanation": "GIAI_THICH_SHORT_KIN: 3 + 8 = 11.",
                "rubric": [{"id": str(uuid4()), "text": "BAREM_SHORT_KIN", "points": 2.5}],
                "solution": "SOLUTION_SHORT_KIN",
                "blockIds": {"stem": str(uuid4()), "answerText": str(uuid4())},
            },
            {
                "id": q3_id,
                "v": 1,
                "type": "truefalse",
                "stem": "Xét tính đúng sai các mệnh đề sau.",
                "points": 2.5,
                "options": ["Mệnh đề 1", "Mệnh đề 2", "Mệnh đề 3", "Mệnh đề 4"],
                "answer": 0,
                "answerKnown": True,
                "truthValues": [True, False, True, False],
                "explanation": "GIAI_THICH_TF_KIN",
                "rubric": [{"id": str(uuid4()), "text": "BAREM_TF_KIN", "points": 2.5}],
                "solution": "SOLUTION_TF_KIN",
                "blockIds": {"stem": str(uuid4()), "truthValues": str(uuid4())},
            },
            {
                "id": q4_id,
                "v": 1,
                "type": "essay",
                "stem": "Chứng minh $n(n+1)$ chia hết cho 2 với mọi số nguyên $n$.",
                "points": 2.5,
                "options": [],
                "explanation": "GIAI_THICH_ESSAY_KIN",
                "explanationDoc": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "GIAI_THICH_ESSAY_DOC_KIN"}],
                        }
                    ],
                },
                "rubric": [{"id": str(uuid4()), "text": "BAREM_ESSAY_KIN", "points": 2.5}],
                "solution": "SOLUTION_ESSAY_KIN",
                "blockIds": {"stem": str(uuid4()), "rubric": str(uuid4())},
            },
        ],
    }


def _make_client(tmp_path: Path, *, db_name: str = "community.sqlite") -> tuple[TestClient, Path]:
    app = FastAPI()
    db_path = tmp_path / db_name
    install_community_library(app, db_path, owner_resolver=_header_owner)
    return TestClient(app), db_path


def test_publish_requires_explicit_consent_public(tmp_path: Path) -> None:
    client, db_path = _make_client(tmp_path)
    exam = _build_rich_exam()

    # Thiếu trường consent_public -> bị chặn 400 với mã consent_required.
    res_missing = client.post("/api/community/publish", json={"exam": exam})
    assert res_missing.status_code == 400
    assert res_missing.json()["code"] == "consent_required"

    # consent_public=False -> bị chặn 400 với mã consent_required.
    res_false = client.post(
        "/api/community/publish",
        json={"consent_public": False, "exam": exam},
    )
    assert res_false.status_code == 400
    assert res_false.json()["code"] == "consent_required"

    # Không chấp nhận chuỗi/số giả mạo boolean và chặn trường lạ ngoài schema.
    res_string = client.post(
        "/api/community/publish",
        json={"consent_public": "true", "exam": exam},
    )
    assert res_string.status_code == 422

    res_extra = client.post(
        "/api/community/publish",
        json={"consent_public": True, "exam": exam, "unknownField": "x"},
    )
    assert res_extra.status_code == 422

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM community_items").fetchone()[0]
    assert count == 0


def test_publish_sanitizes_sensitive_fields_and_strips_answers_by_default(tmp_path: Path) -> None:
    client, db_path = _make_client(tmp_path)
    exam = _build_rich_exam()

    res = client.post(
        "/api/community/publish",
        headers={"X-User-Id": "teacher_a"},
        json={"consent_public": True, "author_label": "Cô Lan", "exam": exam},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["include_answers"] is False
    assert body["status"] == "published"
    assert body["version"] == 1
    assert body["author_id"] == "teacher_a"
    assert body["author_label"] == "Cô Lan"
    assert body["question_count"] == 4

    raw_json = json.dumps(body, ensure_ascii=False)
    for forbidden_marker in (
        "CHAT_NOI_BO",
        "LICH_SU_NOI_BO",
        "AI_CONFIG_NOI_BO",
        "API_KEY_BI_MAT",
        "SECRET_NOI_BO",
        "TOKEN_PHIEN_LAM_VIEC",
        "GHI_CHU_NOI_BO",
        "TAI_LIEU_RIENG",
        "UNDO_NOI_BO",
        "REDO_NOI_BO",
        "PREF_NOI_BO",
        "PHIEN_BAN_NGU_LIEU_KIN",
        "GIAI_THICH_MCQ_KIN",
        "GIAI_THICH_DOC_KIN",
        "BAREM_MCQ_KIN",
        "LOI_GIAI_SOLUTION_MCQ_KIN",
        "BLIND_SOLUTION_KIN",
        "CHECK_NOI_BO_KIN",
        "DAN_CHUNG_NOI_BO_KIN",
        "TEN_NGUOI_RA_KIN",
        "NOTE_CAU_HOI_NOI_BO_KIN",
        "Q_API_KEY_KIN",
        "Q_SECRET_KIN",
        "Q_TOKEN_KIN",
        "Q_AICONFIG_KIN",
        "Q_CHAT_KIN",
        "Q_HISTORY_KIN",
        "RICHDOC_NODE_KIN",
        "RICHDOC_ATTR_KIN",
        "MARK_ATTR_KIN",
        "DAP_AN_SHORT_11",
        "GIAI_THICH_SHORT_KIN",
        "BAREM_SHORT_KIN",
        "SOLUTION_SHORT_KIN",
        "GIAI_THICH_TF_KIN",
        "BAREM_TF_KIN",
        "SOLUTION_TF_KIN",
        "GIAI_THICH_ESSAY_KIN",
        "GIAI_THICH_ESSAY_DOC_KIN",
        "BAREM_ESSAY_KIN",
        "SOLUTION_ESSAY_KIN",
    ):
        assert forbidden_marker not in raw_json

    snapshot = body["snapshot"]
    for forbidden_key in ("chat", "history", "aiConfig", "apiKey", "secret", "token", "notes"):
        assert forbidden_key not in snapshot

    for q in snapshot["questions"]:
        for forbidden_q_key in (
            "answer",
            "answerText",
            "truthValues",
            "explanation",
            "explanationDoc",
            "rubric",
            "solution",
            "blindSolution",
            "approval",
            "chat",
            "history",
            "aiConfig",
            "apiKey",
            "secret",
            "token",
            "notes",
        ):
            assert forbidden_q_key not in q
        assert q["answerKnown"] is False

    # Kiểm tra cả dữ liệu lưu trực tiếp trong SQLite không chứa dữ liệu nhạy cảm.
    with sqlite3.connect(db_path) as conn:
        stored_snapshot = conn.execute(
            "SELECT snapshot_json FROM community_items WHERE id = ?", (body["id"],)
        ).fetchone()[0]
    assert "API_KEY_BI_MAT" not in stored_snapshot
    assert "GIAI_THICH_MCQ_KIN" not in stored_snapshot


def test_publish_with_include_answers_keeps_answers_and_strips_secrets(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    exam = _build_rich_exam()

    res = client.post(
        "/api/community/publish",
        headers={"X-User-Id": "teacher_a"},
        json={"consent_public": True, "include_answers": True, "exam": exam},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["include_answers"] is True

    questions = body["snapshot"]["questions"]
    assert questions[0]["answer"] == 2
    assert questions[0]["answerKnown"] is True
    assert "GIAI_THICH_MCQ_KIN" in questions[0]["explanation"]
    assert (
        questions[0]["explanationDoc"]["content"][0]["content"][0]["text"] == "GIAI_THICH_DOC_KIN"
    )
    assert questions[0]["rubric"][0]["text"] == "BAREM_MCQ_KIN"
    assert questions[0]["solution"] == "LOI_GIAI_SOLUTION_MCQ_KIN"
    assert questions[1]["answerText"] == "DAP_AN_SHORT_11"
    assert questions[2]["truthValues"] == [True, False, True, False]
    assert questions[3]["rubric"][0]["text"] == "BAREM_ESSAY_KIN"

    raw_json = json.dumps(body["snapshot"], ensure_ascii=False)
    for forbidden_secret in (
        "CHAT_NOI_BO",
        "LICH_SU_NOI_BO",
        "AI_CONFIG_NOI_BO",
        "API_KEY_BI_MAT",
        "SECRET_NOI_BO",
        "TOKEN_PHIEN_LAM_VIEC",
        "GHI_CHU_NOI_BO",
        "RICHDOC_NODE_KIN",
    ):
        assert forbidden_secret not in raw_json


def test_filter_published_items_excludes_revoked_and_supports_all_filters(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)

    specs = [
        (
            "teacher_a",
            {
                "consent_public": True,
                "include_answers": False,
                "exam": _build_rich_exam(
                    title="Đề Toán 10 Hàm số bậc hai",
                    subject="Toán",
                    grade=10,
                    series="Kết nối tri thức",
                    chapter="Chương 1: Mệnh đề và Tập hợp",
                    tags=["giua-ki", "trac-nghiem"],
                ),
            },
        ),
        (
            "teacher_b",
            {
                "consent_public": True,
                "include_answers": True,
                "exam": {
                    "id": str(uuid4()),
                    "revision": 1,
                    "title": "Kiểm tra Vật lí 10 Động học",
                    "subject": "Vật lí",
                    "grade": "10",
                    "series": "Cánh diều",
                    "chapter": "Chương 2: Chuyển động biến đổi",
                    "tags": ["giua-ki", "vat-li"],
                    "questions": [
                        {
                            "id": str(uuid4()),
                            "v": 1,
                            "type": "mcq",
                            "stem": "Gia tốc rơi tự do tại mặt đất xấp xỉ bao nhiêu?",
                            "options": ["9,8 m/s²", "5 m/s²", "1 m/s²", "0 m/s²"],
                            "answer": 0,
                        }
                    ],
                },
            },
        ),
        (
            "teacher_c",
            {
                "consent_public": True,
                "include_answers": True,
                "exam": {
                    "id": str(uuid4()),
                    "revision": 1,
                    "title": "Đề Địa lí 12 Đô thị hóa",
                    "subject": "Địa lí",
                    "grade": 12,
                    "series": "Chân trời sáng tạo",
                    "chapter": "Chương 3: Đô thị hóa và dân cư",
                    "tags": ["cuoi-ki", "on-tap"],
                    "questions": [
                        {
                            "id": str(uuid4()),
                            "v": 1,
                            "type": "essay",
                            "stem": "Phân tích xu hướng đô thị hóa hiện nay.",
                            "rubric": [{"text": "Nêu đúng xu hướng", "points": 2.0}],
                        }
                    ],
                },
            },
        ),
        (
            "teacher_a",
            {
                "consent_public": True,
                "include_answers": False,
                "exam": {
                    "id": str(uuid4()),
                    "revision": 1,
                    "title": "Đề sẽ thu hồi Toán 10",
                    "subject": "Toán",
                    "grade": 10,
                    "series": "Kết nối tri thức",
                    "chapter": "Chương 1: Mệnh đề",
                    "tags": ["tam-thoi"],
                    "questions": [],
                },
            },
        ),
    ]

    published_ids = []
    for owner_id, payload in specs:
        resp = client.post("/api/community/publish", headers={"X-User-Id": owner_id}, json=payload)
        assert resp.status_code == 201, resp.text
        published_ids.append(resp.json()["id"])

    # Thu hồi mục thứ 4 -> không được xuất hiện trong danh sách công cộng.
    client.post(
        f"/api/community/items/{published_ids[3]}/revoke",
        headers={"X-User-Id": "teacher_a"},
    ).raise_for_status()

    all_items = client.get("/api/community/items").json()
    assert all_items["total"] == 3
    assert published_ids[3] not in {item["id"] for item in all_items["items"]}

    # Lọc theo lớp + môn + bộ sách (không phân biệt hoa/thường tiếng Việt).
    by_math = client.get(
        "/api/community/items",
        params={"grade": 10, "subject": "toán", "series": "kết nối tri thức"},
    ).json()
    assert [item["id"] for item in by_math["items"]] == [published_ids[0]]

    # Lọc theo môn có chữ Đ tiếng Việt.
    by_geo = client.get("/api/community/items", params={"subject": "địa lí"}).json()
    assert [item["id"] for item in by_geo["items"]] == [published_ids[2]]

    # Lọc theo chương, tag, từ khóa (bao gồm tìm trong stem câu hỏi) và include_answers.
    by_chapter = client.get("/api/community/items", params={"chapter": "chương 2"}).json()
    assert [item["id"] for item in by_chapter["items"]] == [published_ids[1]]

    by_tag = client.get("/api/community/items", params={"tag": "GIUA-KI"}).json()
    assert {item["id"] for item in by_tag["items"]} == {published_ids[0], published_ids[1]}

    by_keyword_in_stem = client.get(
        "/api/community/items", params={"q": "gia tốc rơi tự do"}
    ).json()
    assert [item["id"] for item in by_keyword_in_stem["items"]] == [published_ids[1]]

    with_answers = client.get("/api/community/items", params={"include_answers": True}).json()
    assert {item["id"] for item in with_answers["items"]} == {published_ids[1], published_ids[2]}

    without_answers = client.get("/api/community/items", params={"include_answers": False}).json()
    assert [item["id"] for item in without_answers["items"]] == [published_ids[0]]


def test_clone_creates_independent_uuids_revision_1_and_cloned_from(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    original_exam = _build_rich_exam()
    original_exam_id = original_exam["id"]
    original_q_ids = {q["id"] for q in original_exam["questions"]}
    original_exam_block_ids = set(original_exam["blockIds"].values())
    original_q_block_ids = {
        bid for q in original_exam["questions"] for bid in q.get("blockIds", {}).values()
    }

    pub1 = client.post(
        "/api/community/publish",
        headers={"X-User-Id": "teacher_a"},
        json={"consent_public": True, "include_answers": True, "exam": original_exam},
    )
    assert pub1.status_code == 201
    item_v1 = pub1.json()
    assert item_v1["version"] == 1

    # Công bố lần 2 cùng source_exam_id -> tự tăng version lên 2.
    pub2 = client.post(
        "/api/community/publish",
        headers={"X-User-Id": "teacher_a"},
        json={"consent_public": True, "include_answers": True, "exam": original_exam},
    )
    assert pub2.status_code == 201
    assert pub2.json()["version"] == 2

    # Giáo viên B và Giáo viên C cùng clone bản v1 -> mỗi người nhận một bộ UUID độc lập hoàn toàn.
    clone_b_res = client.post(
        f"/api/community/items/{item_v1['id']}/clone",
        headers={"X-User-Id": "teacher_b"},
    )
    assert clone_b_res.status_code == 201, clone_b_res.text
    clone_b = clone_b_res.json()

    clone_c_res = client.post(
        f"/api/community/items/{item_v1['id']}/clone",
        headers={"X-User-Id": "teacher_c"},
    )
    assert clone_c_res.status_code == 201
    clone_c = clone_c_res.json()

    cloned_exam_b = clone_b["clonedExam"]
    cloned_exam_c = clone_c["clonedExam"]
    record_b = clone_b["cloneRecord"]

    assert UUID(cloned_exam_b["id"])
    assert cloned_exam_b["id"] != original_exam_id
    assert cloned_exam_b["id"] != item_v1["id"]
    assert cloned_exam_b["id"] != cloned_exam_c["id"]
    assert cloned_exam_b["revision"] == 1

    assert cloned_exam_b["clonedFrom"] == {
        "communityItemId": item_v1["id"],
        "authorId": "teacher_a",
        "sourceExamId": original_exam_id,
        "version": 1,
    }
    assert record_b["community_item_id"] == item_v1["id"]
    assert record_b["cloned_exam_id"] == cloned_exam_b["id"]
    assert record_b["cloner_id"] == "teacher_b"

    cloned_b_exam_blocks = set(cloned_exam_b["blockIds"].values())
    assert len(cloned_b_exam_blocks) >= 3
    assert all(UUID(uid) for uid in cloned_b_exam_blocks)
    assert cloned_b_exam_blocks.isdisjoint(original_exam_block_ids)
    assert cloned_b_exam_blocks.isdisjoint(set(cloned_exam_c["blockIds"].values()))

    cloned_b_q_ids = {q["id"] for q in cloned_exam_b["questions"]}
    cloned_c_q_ids = {q["id"] for q in cloned_exam_c["questions"]}
    assert len(cloned_b_q_ids) == 4
    assert all(UUID(qid) for qid in cloned_b_q_ids)
    assert cloned_b_q_ids.isdisjoint(original_q_ids)
    assert cloned_b_q_ids.isdisjoint(cloned_c_q_ids)

    cloned_b_q_blocks = [bid for q in cloned_exam_b["questions"] for bid in q["blockIds"].values()]
    assert len(cloned_b_q_blocks) == len(set(cloned_b_q_blocks))
    assert all(UUID(bid) for bid in cloned_b_q_blocks)
    assert set(cloned_b_q_blocks).isdisjoint(original_q_block_ids)
    assert all(q["v"] == 1 and q["check"] is None for q in cloned_exam_b["questions"])


def test_revoke_checks_owner_blocks_future_access_and_preserves_existing_clones(
    tmp_path: Path,
) -> None:
    client, db_path = _make_client(tmp_path)
    exam = _build_rich_exam()

    pub = client.post(
        "/api/community/publish",
        headers={"X-User-Id": "teacher_a"},
        json={"consent_public": True, "include_answers": False, "exam": exam},
    )
    assert pub.status_code == 201
    item_id = pub.json()["id"]

    # Giáo viên B sao chép trước khi bản gốc bị thu hồi.
    before_revoke = client.post(
        f"/api/community/items/{item_id}/clone",
        headers={"X-User-Id": "teacher_b"},
    )
    assert before_revoke.status_code == 201
    clone_payload = before_revoke.json()
    clone_id = clone_payload["cloneRecord"]["clone_id"]

    # Giáo viên khác thu hồi -> 403 forbidden.
    forbidden = client.post(
        f"/api/community/items/{item_id}/revoke",
        headers={"X-User-Id": "teacher_b"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"
    assert client.get(f"/api/community/items/{item_id}").status_code == 200

    # Đúng chủ sở hữu thu hồi -> 200 revoked.
    revoked = client.post(
        f"/api/community/items/{item_id}/revoke",
        headers={"X-User-Id": "teacher_a"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert isinstance(revoked.json()["revoked_at"], int)

    # Sau khi thu hồi: danh sách ẩn, chi tiết & clone mới trả 410 item_revoked;
    # người khác thu hồi vẫn bị chặn 403.
    assert client.get("/api/community/items").json()["items"] == []
    detail_after = client.get(f"/api/community/items/{item_id}")
    assert detail_after.status_code == 410
    assert detail_after.json()["code"] == "item_revoked"

    clone_after = client.post(
        f"/api/community/items/{item_id}/clone",
        headers={"X-User-Id": "teacher_c"},
    )
    assert clone_after.status_code == 410
    assert clone_after.json()["code"] == "item_revoked"

    assert (
        client.post(
            f"/api/community/items/{item_id}/revoke",
            headers={"X-User-Id": "teacher_b"},
        ).status_code
        == 403
    )

    # Bản không tồn tại -> 404 item_not_found.
    missing = client.get(f"/api/community/items/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "item_not_found"

    # Bản đã sao chép trước đó của Giáo viên B vẫn nguyên vẹn (qua API và trong SQLite)
    # và hoàn toàn tương thích cấu trúc đề của share_snapshot / exam_html, không rò đáp án.
    clones_list = client.get("/api/community/clones", headers={"X-User-Id": "teacher_b"})
    assert clones_list.status_code == 200
    assert clones_list.json()["total"] == 1
    assert clones_list.json()["clones"][0]["clone_id"] == clone_id

    saved_clone = client.get(
        f"/api/community/clones/{clone_id}",
        headers={"X-User-Id": "teacher_b"},
    )
    assert saved_clone.status_code == 200
    restored_exam = saved_clone.json()["clonedExam"]
    assert restored_exam == clone_payload["clonedExam"]
    assert all("answer" not in q and "solution" not in q for q in restored_exam["questions"])
    assert len(build_share_snapshot(restored_exam, False)["questions"]) == 4
    rendered_html = exam_html(restored_exam, False, "http://testserver")
    assert "GIAI_THICH_MCQ_KIN" not in rendered_html
    assert "DAP_AN_SHORT_11" not in rendered_html
    # Chủ sở hữu gốc không đọc được bản sao riêng tư của Giáo viên B.
    assert (
        client.get(
            f"/api/community/clones/{clone_id}",
            headers={"X-User-Id": "teacher_a"},
        ).status_code
        == 404
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT cloned_snapshot_json FROM community_clones WHERE clone_id = ?",
            (clone_id,),
        ).fetchone()
    assert row is not None
    assert json.loads(row[0]) == clone_payload["clonedExam"]


def test_installer_supports_str_path_callable_default_owner_and_reload(tmp_path: Path) -> None:
    db_file = tmp_path / "nested" / "community_default.sqlite"

    # 1) Truyền str path và owner_resolver=None (mặc định "local").
    app_one = FastAPI()
    install_community_library(app_one, str(db_file))
    exam = _build_rich_exam(grade=8, subject="Vật lí")

    with TestClient(app_one) as c1:
        pub = c1.post(
            "/api/community/publish",
            json={"consent_public": True, "exam": exam},
        )
        assert pub.status_code == 201
        item = pub.json()
        assert item["author_id"] == "local"
        assert item["grade"] == 8

    # Khởi tạo app mới trên cùng tệp SQLite -> dữ liệu vẫn còn nguyên vẹn.
    app_reloaded = FastAPI()
    install_community_library(app_reloaded, db_file)
    with TestClient(app_reloaded) as c2:
        listed = c2.get("/api/community/items", params={"grade": 8}).json()
        assert listed["total"] == 1
        assert listed["items"][0]["id"] == item["id"]
        cloned = c2.post(f"/api/community/items/{item['id']}/clone").json()
        assert cloned["cloneRecord"]["cloner_id"] == "local"

    # 2) Truyền callable context manager sqlite3.Connection không đặt row_factory.
    callable_db = tmp_path / "callable.sqlite"

    @contextmanager
    def connect_raw() -> Generator[sqlite3.Connection]:
        conn = sqlite3.connect(callable_db, timeout=5.0)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    app_callable = FastAPI()
    install_community_library(app_callable, connect_raw, owner_resolver=_header_owner)
    with TestClient(app_callable) as c3:
        bad_grade = c3.post(
            "/api/community/publish",
            headers={"X-User-Id": "teacher_x"},
            json={"consent_public": True, "grade": 13, "exam": deepcopy(exam)},
        )
        assert bad_grade.status_code == 422
        assert bad_grade.json()["code"] == "invalid_grade"

        bool_grade = c3.post(
            "/api/community/publish",
            headers={"X-User-Id": "teacher_x"},
            json={"consent_public": True, "grade": True, "exam": deepcopy(exam)},
        )
        assert bool_grade.status_code == 422

        stale_exam = deepcopy(exam)
        stale_exam["questions"][0]["stem"] += " (chưa đồng bộ richDoc)"
        stale_res = c3.post(
            "/api/community/publish",
            headers={"X-User-Id": "teacher_x"},
            json={"consent_public": True, "exam": stale_exam},
        )
        assert stale_res.status_code == 422
        assert stale_res.json()["code"] == "stale_document"

        assert c3.get("/api/community/items", params={"grade": 13}).status_code == 422

    # 3) Hỗ trợ ":memory:" và chuẩn hóa Unicode NFD/NFC khi lọc tiếng Việt.
    app_mem = FastAPI()
    install_community_library(app_mem, ":memory:")
    with TestClient(app_mem) as c_mem:
        c_mem.post(
            "/api/community/publish",
            json={"consent_public": True, "exam": _build_rich_exam(grade=9, subject="Toán")},
        ).raise_for_status()
        nfd_subject = unicodedata.normalize("NFD", "toán")
        mem_listed = c_mem.get("/api/community/items", params={"subject": nfd_subject}).json()
        assert mem_listed["total"] == 1

    with sqlite3.connect(callable_db) as conn:
        item_cols = {row[1] for row in conn.execute("PRAGMA table_info(community_items)")}
        clone_cols = {row[1] for row in conn.execute("PRAGMA table_info(community_clones)")}
    assert {
        "id",
        "source_exam_id",
        "author_id",
        "author_label",
        "title",
        "grade",
        "subject",
        "series",
        "chapter",
        "tags_json",
        "include_answers",
        "status",
        "version",
        "snapshot_json",
        "created_at",
        "revoked_at",
    }.issubset(item_cols)
    assert {
        "clone_id",
        "community_item_id",
        "cloned_exam_id",
        "cloner_id",
        "cloned_at",
        "cloned_snapshot_json",
    }.issubset(clone_cols)
