"""Kiểm thử CRUD, lọc phân cấp, phân quyền owner, citation và SHA-256 cho nguồn học liệu."""

from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import contextmanager
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.curriculum_sources import (
    compute_source_sha256,
    install_curriculum_sources,
)


def _header_owner(request: Request) -> str:
    owner_id = request.headers.get("X-Owner")
    if not owner_id:
        raise HTTPException(401, "Yêu cầu đăng nhập trước khi truy cập nguồn học liệu.")
    return owner_id


def _sample_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "grade": 10,
        "subject": "Toán",
        "series": "Kết nối tri thức",
        "volume": "Tập 1",
        "chapter": "Chương 1: Mệnh đề và tập hợp",
        "lesson": "Bài 1: Mệnh đề",
        "title": "Định nghĩa mệnh đề và mệnh đề chứa biến",
        "license_status": "allowed",
        "license_note": "Tài liệu minh họa nội bộ được phép trích dẫn.",
        "source_origin": "Ngữ liệu tự biên soạn theo cấu trúc GDPT 2018",
        "locator": "Trang 6, Mục 1",
        "content_excerpt": "Một mệnh đề toán học là một câu khẳng định đúng hoặc sai.",
    }
    data.update(overrides)
    return data


def _build_app(db_target, *, owner_resolver=_header_owner, clock=None) -> FastAPI:
    app = FastAPI()
    kwargs = {"owner_resolver": owner_resolver}
    if clock is not None:
        kwargs["clock"] = clock
    install_curriculum_sources(app, db_target, **kwargs)
    return app


def test_crud_and_persistence_across_reload(tmp_path):
    db_file = tmp_path / "nested" / "curriculum.sqlite"
    app = _build_app(db_file)

    with TestClient(app) as client:
        headers = {"X-Owner": "user_a"}
        created_resp = client.post(
            "/api/curriculum/sources", headers=headers, json=_sample_payload()
        )
        assert created_resp.status_code == 201, created_resp.text
        created = created_resp.json()

        UUID(created["id"])
        assert created["owner_id"] == "user_a"
        assert created["grade"] == 10
        assert created["subject"] == "Toán"
        assert created["series"] == "Kết nối tri thức"
        assert created["volume"] == "Tập 1"
        assert created["chapter"] == "Chương 1: Mệnh đề và tập hợp"
        assert created["lesson"] == "Bài 1: Mệnh đề"
        assert created["license_status"] == "allowed"
        assert len(created["sha256"]) == 64
        assert created["created_at"] == created["updated_at"]

        with sqlite3.connect(db_file) as conn:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(curriculum_sources)")]
        assert cols == [
            "id",
            "owner_id",
            "grade",
            "subject",
            "series",
            "volume",
            "chapter",
            "lesson",
            "title",
            "license_status",
            "license_note",
            "source_origin",
            "locator",
            "content_excerpt",
            "sha256",
            "created_at",
            "updated_at",
        ]

        detail_resp = client.get(f"/api/curriculum/sources/{created['id']}", headers=headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json() == created

        patched_resp = client.patch(
            f"/api/curriculum/sources/{created['id']}",
            headers=headers,
            json={
                "chapter": "Chương 2: Bất phương trình bậc nhất hai ẩn",
                "lesson": "Bài 3: Bất phương trình bậc nhất hai ẩn",
                "license_status": "teacher_owned",
                "locator": "Trang 25, Ví dụ 2",
            },
        )
        assert patched_resp.status_code == 200, patched_resp.text
        patched = patched_resp.json()
        assert patched["chapter"] == "Chương 2: Bất phương trình bậc nhất hai ẩn"
        assert patched["lesson"] == "Bài 3: Bất phương trình bậc nhất hai ẩn"
        assert patched["license_status"] == "teacher_owned"
        assert patched["locator"] == "Trang 25, Ví dụ 2"
        assert patched["title"] == created["title"]
        assert patched["created_at"] == created["created_at"]
        assert patched["updated_at"] > created["updated_at"]
        assert patched["sha256"] != created["sha256"]

    # Tải lại trên FastAPI app mới trỏ tới cùng tệp SQLite (truyền str path).
    reloaded_app = _build_app(str(db_file))
    with TestClient(reloaded_app) as reloaded:
        headers = {"X-Owner": "user_a"}
        fetched = reloaded.get(f"/api/curriculum/sources/{created['id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json() == patched

        deleted = reloaded.delete(f"/api/curriculum/sources/{created['id']}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json() == {"ok": True, "id": created["id"]}

        assert (
            reloaded.get(f"/api/curriculum/sources/{created['id']}", headers=headers).status_code
            == 404
        )
        listing = reloaded.get("/api/curriculum/sources", headers=headers).json()
        assert listing == {"sources": [], "total": 0}


def test_default_owner_resolver_and_connector_variants(tmp_path):
    # Mặc định owner_resolver=None trả về "local", hỗ trợ ":memory:"
    app_mem = FastAPI()
    install_curriculum_sources(app_mem, ":memory:")
    with TestClient(app_mem) as client:
        res = client.post(
            "/api/curriculum/sources", json=_sample_payload(grade=8, subject="Vật lí")
        )
        assert res.status_code == 201
        assert res.json()["owner_id"] == "local"
        listed = client.get("/api/curriculum/sources").json()
        assert listed["total"] == 1

    # Callable trả context manager sqlite3.Connection (cả row_factory=None và sqlite3.Row)
    for idx, use_row_factory in enumerate((False, True)):
        db_path = tmp_path / f"callable_{idx}.sqlite"

        @contextmanager
        def connect_ctx(path=db_path, with_row=use_row_factory):
            conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
            if with_row:
                conn.row_factory = sqlite3.Row
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

        app_ctx = _build_app(connect_ctx, owner_resolver=None)
        with TestClient(app_ctx) as client:
            created = client.post("/api/curriculum/sources", json=_sample_payload(grade=6)).json()
            assert created["owner_id"] == "local"
            got = client.get(f"/api/curriculum/sources/{created['id']}").json()
            assert got["id"] == created["id"]


def test_hierarchical_filters_and_vietnamese_search(tmp_path):
    app = _build_app(tmp_path / "filter.sqlite")
    headers = {"X-Owner": "user_a"}

    fixtures = [
        _sample_payload(
            grade=10,
            subject="Toán",
            series="Kết nối tri thức",
            volume="Tập 1",
            chapter="Chương 1",
            lesson="Bài 1",
            title="Mệnh đề đảo",
            license_status="allowed",
            content_excerpt="Định lý thuận và mệnh đề đảo.",
        ),
        _sample_payload(
            grade=10,
            subject="Toán",
            series="Kết nối tri thức",
            volume="Tập 1",
            chapter="Chương 10",
            lesson="Bài 10",
            title="Xác suất cổ điển",
            license_status="teacher_owned",
            content_excerpt="Không gian mẫu và biến cố ngẫu nhiên.",
        ),
        _sample_payload(
            grade=10,
            subject="Toán",
            series="Cánh diều",
            volume="Tập 2",
            chapter="Chương 5",
            lesson="Bài 2",
            title="Phương trình đường tròn",
            license_status="pending_review",
            content_excerpt="Đường tròn tâm I bán kính R.",
        ),
        _sample_payload(
            grade=8,
            subject="Vật lí",
            series="Chân trời sáng tạo",
            volume="Cả năm",
            chapter="Chương 2",
            lesson="Bài 4",
            title="Áp suất chất lỏng",
            license_status="restricted",
            content_excerpt="Độ sâu tăng thì áp suất tăng.",
        ),
        _sample_payload(
            grade=12,
            subject="Ngữ văn",
            series="Chủ biên riêng",
            volume="Tập 2",
            chapter="Chương 3",
            lesson="Bài 7",
            title="Nghị luận xã hội",
            license_status="teacher_owned",
            content_excerpt="Dẫn chứng rõ ràng và lập luận chặt chẽ.",
        ),
    ]

    with TestClient(app) as client:
        for item in fixtures:
            assert (
                client.post("/api/curriculum/sources", headers=headers, json=item).status_code
                == 201
            )

        # Lọc theo từng lớp/môn/bộ sách/tập/chương/bài không bị nhầm tiền tố Chương 1 vs Chương 10
        by_chapter_1 = client.get(
            "/api/curriculum/sources",
            headers=headers,
            params={
                "grade": 10,
                "subject": "toán",
                "series": "kết nối tri thức",
                "volume": "tập 1",
                "chapter": "Chương 1",
            },
        ).json()
        assert by_chapter_1["total"] == 1
        assert by_chapter_1["sources"][0]["title"] == "Mệnh đề đảo"

        by_lesson_1 = client.get(
            "/api/curriculum/sources",
            headers=headers,
            params={"lesson": "Bài 1"},
        ).json()
        assert by_lesson_1["total"] == 1
        assert by_lesson_1["sources"][0]["lesson"] == "Bài 1"

        by_status = client.get(
            "/api/curriculum/sources",
            headers=headers,
            params={"license_status": "teacher_owned"},
        ).json()
        assert {item["subject"] for item in by_status["sources"]} == {"Toán", "Ngữ văn"}

        # Tìm q không phân biệt hoa thường tiếng Việt (kể cả ký tự Đ/đ và NFC/NFD)
        # trên 4 trường title/chapter/lesson/content_excerpt
        q_title = client.get(
            "/api/curriculum/sources", headers=headers, params={"q": "ĐƯỜNG TRÒN"}
        ).json()
        assert [s["title"] for s in q_title["sources"]] == ["Phương trình đường tròn"]

        q_excerpt = client.get(
            "/api/curriculum/sources", headers=headers, params={"q": "độ sâu"}
        ).json()
        assert [s["title"] for s in q_excerpt["sources"]] == ["Áp suất chất lỏng"]

        q_lesson = client.get(
            "/api/curriculum/sources", headers=headers, params={"q": "bài 7"}
        ).json()
        assert [s["title"] for s in q_lesson["sources"]] == ["Nghị luận xã hội"]

        q_chapter = client.get(
            "/api/curriculum/sources", headers=headers, params={"q": "CHƯƠNG 10"}
        ).json()
        assert [s["title"] for s in q_chapter["sources"]] == ["Xác suất cổ điển"]

        q_nfd = client.get(
            "/api/curriculum/sources",
            headers=headers,
            params={"q": unicodedata.normalize("NFD", "Mệnh đề đảo")},
        ).json()
        assert [s["title"] for s in q_nfd["sources"]] == ["Mệnh đề đảo"]


def test_owner_isolation_blocks_cross_owner_access(tmp_path):
    app = _build_app(tmp_path / "owners.sqlite")
    headers_a = {"X-Owner": "user_a"}
    headers_b = {"X-Owner": "user_b"}

    with TestClient(app) as client:
        # Không có header owner -> 401
        assert client.get("/api/curriculum/sources").status_code == 401

        source_a = client.post(
            "/api/curriculum/sources",
            headers=headers_a,
            json=_sample_payload(title="Nguồn mật của A", license_status="allowed"),
        ).json()
        source_b = client.post(
            "/api/curriculum/sources",
            headers=headers_b,
            json=_sample_payload(title="Nguồn riêng của B", license_status="allowed"),
        ).json()

        list_a = client.get("/api/curriculum/sources", headers=headers_a).json()
        list_b = client.get("/api/curriculum/sources", headers=headers_b).json()
        assert [s["id"] for s in list_a["sources"]] == [source_a["id"]]
        assert [s["id"] for s in list_b["sources"]] == [source_b["id"]]

        # user_b không thể xem, sửa, xóa hoặc lấy citation nguồn của user_a (trả 404)
        assert (
            client.get(f"/api/curriculum/sources/{source_a['id']}", headers=headers_b).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/curriculum/sources/{source_a['id']}",
                headers=headers_b,
                json={"title": "B cố sửa của A"},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/curriculum/sources/{source_a['id']}", headers=headers_b
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/curriculum/sources/{source_a['id']}/citation", headers=headers_b
            ).status_code
            == 404
        )

        # Nguồn của user_a vẫn nguyên vẹn
        still_a = client.get(f"/api/curriculum/sources/{source_a['id']}", headers=headers_a).json()
        assert still_a == source_a


def test_citation_enforces_license_and_returns_provenance(tmp_path):
    app = _build_app(tmp_path / "citation.sqlite")
    headers = {"X-Owner": "user_a"}

    with TestClient(app) as client:
        allowed = client.post(
            "/api/curriculum/sources",
            headers=headers,
            json=_sample_payload(license_status="allowed", title="Nguồn cho phép"),
        ).json()
        teacher_owned = client.post(
            "/api/curriculum/sources",
            headers=headers,
            json=_sample_payload(license_status="teacher_owned", title="Nguồn GV tự soạn"),
        ).json()
        pending = client.post(
            "/api/curriculum/sources",
            headers=headers,
            json=_sample_payload(license_status="pending_review", title="Nguồn chờ duyệt"),
        ).json()
        restricted = client.post(
            "/api/curriculum/sources",
            headers=headers,
            json=_sample_payload(license_status="restricted", title="Nguồn hạn chế"),
        ).json()

        for rec in (allowed, teacher_owned):
            res = client.get(f"/api/curriculum/sources/{rec['id']}/citation", headers=headers)
            assert res.status_code == 200, res.text
            assert res.json() == {
                "sourceId": rec["id"],
                "grade": rec["grade"],
                "subject": rec["subject"],
                "series": rec["series"],
                "volume": rec["volume"],
                "chapter": rec["chapter"],
                "lesson": rec["lesson"],
                "title": rec["title"],
                "locator": rec["locator"],
                "licenseStatus": rec["license_status"],
                "licenseNote": rec["license_note"],
                "sha256": rec["sha256"],
                "excerpt": rec["content_excerpt"],
            }

        # pending_review mặc định chặt -> 403 source_license_restricted
        pending_default = client.get(
            f"/api/curriculum/sources/{pending['id']}/citation", headers=headers
        )
        assert pending_default.status_code == 403
        assert pending_default.json()["code"] == "source_license_restricted"

        pending_false = client.get(
            f"/api/curriculum/sources/{pending['id']}/citation",
            headers=headers,
            params={"allow_unverified": "false"},
        )
        assert pending_false.status_code == 403
        assert pending_false.json()["code"] == "source_license_restricted"

        # Cho phép xem trước pending_review khi bật allow_unverified=true
        pending_override = client.get(
            f"/api/curriculum/sources/{pending['id']}/citation",
            headers=headers,
            params={"allow_unverified": "true"},
        )
        assert pending_override.status_code == 200
        assert pending_override.json()["licenseStatus"] == "pending_review"

        # restricted luôn bị chặn ngay cả khi allow_unverified=true
        for query in ({}, {"allow_unverified": "false"}, {"allow_unverified": "true"}):
            restricted_res = client.get(
                f"/api/curriculum/sources/{restricted['id']}/citation",
                headers=headers,
                params=query,
            )
            assert restricted_res.status_code == 403
            assert restricted_res.json()["code"] == "source_license_restricted"

        # Khi giáo viên cập nhật pending_review -> allowed thì citation mặc định hoạt động
        updated = client.patch(
            f"/api/curriculum/sources/{pending['id']}",
            headers=headers,
            json={"license_status": "allowed"},
        ).json()
        approved_citation = client.get(
            f"/api/curriculum/sources/{pending['id']}/citation",
            headers=headers,
        )
        assert approved_citation.status_code == 200
        assert approved_citation.json()["sha256"] == updated["sha256"]
        assert approved_citation.json()["licenseStatus"] == "allowed"


def test_curriculum_error_preserves_403_and_404_when_ai_error_handler_exists(tmp_path):
    app = FastAPI()

    # Mô phỏng local_workspace đã đăng ký handler AIError chung trả 409
    @app.exception_handler(AIError)
    async def legacy_ai_handler(_request: Request, exc: AIError) -> JSONResponse:
        return JSONResponse({"error": str(exc), "code": exc.code}, status_code=409)

    install_curriculum_sources(app, tmp_path / "compat.sqlite", owner_resolver=_header_owner)

    with TestClient(app) as client:
        headers = {"X-Owner": "user_a"}
        restricted = client.post(
            "/api/curriculum/sources",
            headers=headers,
            json=_sample_payload(license_status="restricted"),
        ).json()
        blocked = client.get(
            f"/api/curriculum/sources/{restricted['id']}/citation", headers=headers
        )
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "source_license_restricted"

        missing = client.get("/api/curriculum/sources/khong-ton-tai", headers=headers)
        assert missing.status_code == 404
        assert missing.json()["code"] == "source_not_found"


def test_sha256_stability_and_update_sensitivity(tmp_path):
    ticks = iter([1000.0, 2000.0, 3000.0, 4000.0])
    app = _build_app(tmp_path / "hash.sqlite", clock=lambda: next(ticks))

    with TestClient(app) as client:
        payload = _sample_payload()
        first = client.post(
            "/api/curriculum/sources", headers={"X-Owner": "user_a"}, json=payload
        ).json()
        second = client.post(
            "/api/curriculum/sources", headers={"X-Owner": "user_b"}, json=payload
        ).json()

        assert first["id"] != second["id"]
        assert first["created_at"] != second["created_at"]
        assert first["sha256"] == second["sha256"] == compute_source_sha256(payload)

        # PATCH không đổi giá trị -> sha256 vẫn ổn định
        noop = client.patch(
            f"/api/curriculum/sources/{first['id']}",
            headers={"X-Owner": "user_a"},
            json={"title": payload["title"]},
        ).json()
        assert noop["sha256"] == first["sha256"]
        assert noop["updated_at"] == 3000000

        # Thay đổi một dấu/nội dung trích -> sha256 đổi
        changed = client.patch(
            f"/api/curriculum/sources/{first['id']}",
            headers={"X-Owner": "user_a"},
            json={"content_excerpt": "Một mệnh đề toán học là khẳng định đúng hoặc sai."},
        ).json()
        assert changed["sha256"] != first["sha256"]
        assert changed["updated_at"] == 4000000


def test_validation_and_extra_forbid(tmp_path):
    app = _build_app(tmp_path / "validation.sqlite")
    headers = {"X-Owner": "user_a"}

    with TestClient(app) as client:
        # extra="forbid" trên POST (kể cả khi cố giả mạo owner_id, sha256, id)
        for bad_extra in (
            {"unexpected": "boom"},
            {"owner_id": "user_b"},
            {"id": "custom-id"},
            {"sha256": "0" * 64},
        ):
            res = client.post(
                "/api/curriculum/sources",
                headers=headers,
                json=_sample_payload(**bad_extra),
            )
            assert res.status_code == 422

        # grade ngoài 1..12 hoặc sai kiểu (bool, float, str)
        for bad_grade in (0, -1, 13, True, False, 10.5, "10"):
            res = client.post(
                "/api/curriculum/sources",
                headers=headers,
                json=_sample_payload(grade=bad_grade),
            )
            assert res.status_code == 422

        # subject/title rỗng hoặc license_status sai
        assert (
            client.post(
                "/api/curriculum/sources",
                headers=headers,
                json=_sample_payload(subject="   "),
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/curriculum/sources",
                headers=headers,
                json=_sample_payload(title="   "),
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/curriculum/sources",
                headers=headers,
                json=_sample_payload(license_status="public_domain"),
            ).status_code
            == 422
        )

        # GET query validation
        assert (
            client.get("/api/curriculum/sources", headers=headers, params={"grade": 13}).status_code
            == 422
        )
        assert (
            client.get(
                "/api/curriculum/sources",
                headers=headers,
                params={"license_status": "invalid"},
            ).status_code
            == 422
        )

        # Tạo bản ghi hợp lệ để kiểm extra="forbid" và null rejection trên PATCH
        valid = client.post(
            "/api/curriculum/sources", headers=headers, json=_sample_payload()
        ).json()
        assert (
            client.patch(
                f"/api/curriculum/sources/{valid['id']}",
                headers=headers,
                json={"extra_field": 1},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/curriculum/sources/{valid['id']}",
                headers=headers,
                json={"grade": 0},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/curriculum/sources/{valid['id']}",
                headers=headers,
                json={"grade": None},
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/curriculum/sources/{valid['id']}",
                headers=headers,
                json={"title": "  "},
            ).status_code
            == 422
        )


def test_installer_rejects_invalid_arguments(tmp_path):
    app = FastAPI()
    with pytest.raises(TypeError):
        install_curriculum_sources(app, 12345)  # type: ignore[arg-type]
    invalid_owner_resolver: object = "invalid"
    with pytest.raises(TypeError):
        install_curriculum_sources(
            app,
            tmp_path / "ok.sqlite",
            owner_resolver=invalid_owner_resolver,  # type: ignore[arg-type]
        )
