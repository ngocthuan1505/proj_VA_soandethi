"""Kiểm thử tích hợp một API / một Schema thống nhất trên local_workspace và team_workspace."""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

import pytest
from docx import Document
from fastapi.testclient import TestClient

from mach_backend.local_workspace import create_app
from mach_backend.team_workspace import create_team_app

LOCAL_ORIGIN = {"Origin": "http://testserver"}
TEAM_PASSWORD = "mat-khau-tich-hop-mo-rong"


def _sample_exam() -> dict:
    doc_restricted = str(uuid4())
    return {
        "id": str(uuid4()),
        "title": "Đề kiểm tra giữa kì I — Toán 7",
        "subject": "Toán",
        "grade": "7",
        "series": "Kết nối tri thức",
        "chapter": "Số hữu tỉ",
        "school": "THCS Mẫu Tích Hợp",
        "revision": 1,
        "chat": [{"role": "user", "text": "BÍ_MẬT_CHAT_KHÔNG_ĐƯỢC_CÔNG_BỐ"}],
        "aiConfig": {"apiKey": "SECRET_TOKEN_KHÔNG_CÔNG_BỐ"},
        "docs": [
            {
                "id": doc_restricted,
                "version": 1,
                "name": "Tai lieu han che",
                "licenseStatus": "restricted",
                "pages": [
                    {"number": 1, "text": "Đoạn nguồn hạn chế quyền AI có đủ ký tự để kiểm."}
                ],
            }
        ],
        "questions": [
            {
                "id": str(uuid4()),
                "blockIds": [str(uuid4()), str(uuid4())],
                "type": "mcq",
                "level": 0,
                "topic": "Số hữu tỉ",
                "lesson": "Cộng trừ số hữu tỉ",
                "stem": "Giá trị của $\\frac{1}{2} + \\frac{1}{4}$ là bao nhiêu?",
                "options": ["$\\frac{3}{4}$", "$\\frac{1}{3}$", "$\\frac{2}{6}$", "1"],
                "answer": 0,
                "points": 0.5,
                "explanation": "ĐÁP_ÁN_LỜI_GIẢI_TRẮC_NGHIỆM_RIÊNG",
            },
            {
                "id": str(uuid4()),
                "blockIds": [str(uuid4())],
                "type": "essay",
                "level": 2,
                "topic": "Số hữu tỉ",
                "lesson": "Phép chia số hữu tỉ",
                "stem": "Tính giá trị biểu thức $A = \\frac{3}{2} : \\frac{3}{4}$.",
                "options": [],
                "points": 1.5,
                "explanation": "ĐÁP_ÁN_TỰ_LUẬN_RIÊNG",
                "rubric": [
                    {
                        "text": (
                            "Đổi phép chia thành nhân nghịch đảo $\\frac{3}{2} \\cdot \\frac{4}{3}$"
                        ),
                        "points": 0.75,
                    },
                    {"text": "Rút gọn và kết luận đúng $A = 2$", "points": 0.75},
                ],
            },
        ],
    }


def _shareable_plain_exam() -> dict:
    return {
        "id": str(uuid4()),
        "title": "Đề kiểm tra giữa kì I — Toán 7",
        "subject": "Toán",
        "grade": "7",
        "series": "Kết nối tri thức",
        "chapter": "Số hữu tỉ",
        "school": "THCS Mẫu Tích Hợp",
        "revision": 1,
        "chat": [{"role": "user", "text": "BÍ_MẬT_CHAT_KHÔNG_ĐƯỢC_CÔNG_BỐ"}],
        "aiConfig": {"apiKey": "SECRET_TOKEN_KHÔNG_CÔNG_BỐ"},
        "questions": [
            {
                "id": str(uuid4()),
                "type": "mcq",
                "level": 0,
                "topic": "Số hữu tỉ",
                "lesson": "Cộng trừ số hữu tỉ",
                "stem": "Tổng của hai số 1 và 2 là bao nhiêu?",
                "options": ["3", "4", "5", "6"],
                "answer": 0,
                "points": 0.5,
                "explanation": "ĐÁP_ÁN_LỜI_GIẢI_TRẮC_NGHIỆM_RIÊNG",
            }
        ],
    }


def _seed_exam(client: TestClient, *exams: dict) -> None:
    current_rev = client.get("/api/kv", params={"key": "state"}).json()["revision"]
    res = client.put(
        "/api/kv",
        headers={"If-Match": str(current_rev)},
        json={
            "key": "state",
            "value": {"version": 1, "current": exams[0]["id"], "exams": list(exams), "prefs": []},
        },
    )
    assert res.status_code == 200, res.text


@pytest.fixture
def local_client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers=LOCAL_ORIGIN) as client:
        yield client


@pytest.fixture
def team_bundle(tmp_path):
    now = [2000]
    app = create_team_app(tmp_path, clock=lambda: now[0])
    accounts = app.state.accounts
    admin = accounts.create(
        "admin@example.test", TEAM_PASSWORD, "Quản trị viên", accounts.invite(bootstrap=True)
    )
    member = accounts.create(
        "member@example.test",
        TEAM_PASSWORD,
        "Giáo viên thành viên",
        accounts.invite(email="member@example.test"),
    )
    return app, admin, member, now


def _login(app, email: str) -> TestClient:
    client = TestClient(app, headers=LOCAL_ORIGIN)
    res = client.post("/api/account/login", json={"email": email, "password": TEAM_PASSWORD})
    assert res.status_code == 200, res.text
    return client


def test_unified_local_workspace_lesson_sources_community_shares_ocr_and_a4_exports(
    local_client: TestClient,
):
    # 1. Trục nguồn: /api/lesson-catalog, /api/lesson-catalog/sources & chặn AI restricted
    catalog_res = local_client.get("/api/lesson-catalog")
    assert catalog_res.status_code == 200
    collections = catalog_res.json()["collections"]
    assert collections and collections[0]["licenseStatus"] == "allowed"
    assert len(collections[0]["sha256"]) == 64

    allowed_res = local_client.post(
        "/api/lesson-catalog/sources",
        json={
            "grade": 7,
            "subject": "Toán",
            "book": "Kết nối tri thức",
            "volume": "Tập 1",
            "chapter": "Chương 1: Số hữu tỉ",
            "lesson": "Bài 2: Cộng, trừ, nhân, chia số hữu tỉ",
            "title": "Ví dụ tính toán phân số",
            "licenseStatus": "allowed",
            "licenseNote": "Tự biên soạn dùng công khai",
            "sourceOrigin": "SGK tự viết",
            "locator": "Trang 12, mục 2",
            "contentExcerpt": "Quy tắc cộng hai số hữu tỉ: đưa về cùng mẫu dương.",
        },
    )
    assert allowed_res.status_code == 201, allowed_res.text
    allowed_id = allowed_res.json()["id"]

    restricted_res = local_client.post(
        "/api/lesson-catalog/sources",
        json={
            "grade": 7,
            "subject": "Toán",
            "series": "Kết nối tri thức",
            "volume": "Tập 1",
            "chapter": "Chương 1",
            "lesson": "Bài 2",
            "title": "Ngữ liệu chưa có quyền",
            "license_status": "restricted",
            "locator": "Trang 99",
            "content_excerpt": "Nội dung hạn chế trích dẫn tự động.",
        },
    )
    assert restricted_res.status_code == 201, restricted_res.text
    restricted_id = restricted_res.json()["id"]

    assert local_client.get(f"/api/lesson-catalog/sources/{allowed_id}/citation").status_code == 200
    cite_blocked = local_client.get(
        f"/api/lesson-catalog/sources/{restricted_id}/citation",
        params={"allow_unverified": "true"},
    )
    assert cite_blocked.status_code == 403
    assert cite_blocked.json()["code"] == "source_license_restricted"

    exam = _sample_exam()
    share_exam = _shareable_plain_exam()
    _seed_exam(local_client, exam, share_exam)

    # Chặn nguồn restricted ngay tại POST /api/exams/{exam_id}/matrix/approve
    approve_blocked = local_client.post(
        f"/api/exams/{exam['id']}/matrix/approve",
        json={
            "baseRevision": 1,
            "sourceText": "",
            "sourceName": "Nguồn hạn chế",
            "sourceMode": "provided",
            "sources": [
                {
                    "sourceId": exam["docs"][0]["id"],
                    "sourceVersion": 1,
                    "locator": {"kind": "page", "index": 1},
                }
            ],
        },
    )
    assert approve_blocked.status_code == 403, approve_blocked.text
    assert approve_blocked.json()["code"] == "source_license_restricted"

    # 2. Kho cộng đồng thống nhất qua /api/share + /api/community-exams + /clone + /api/share/revoke
    denied = local_client.post(
        "/api/share",
        json={
            "examId": share_exam["id"],
            "baseRevision": 1,
            "answers": False,
            "allowCopy": True,
            "community": True,
            "consentPublic": False,
        },
    )
    assert denied.status_code == 400
    assert denied.json()["code"] == "consent_required"

    pub = local_client.post(
        "/api/share",
        json={
            "examId": share_exam["id"],
            "baseRevision": 1,
            "answers": False,
            "allowCopy": True,
            "community": True,
            "consentPublic": True,
            "series": "Kết nối tri thức",
            "chapter": "Số hữu tỉ",
        },
    )
    assert pub.status_code == 201 or pub.status_code == 200, pub.text
    token = pub.json()["token"]

    listed = local_client.get(
        "/api/community-exams", params={"series": "ket noi", "chapter": "huu ti"}
    )
    assert listed.status_code == 200
    assert any(it["token"] == token for it in listed.json()["exams"])

    cloned = local_client.post(f"/api/community-exams/{token}/clone")
    assert cloned.status_code == 201, cloned.text
    cloned_exam = cloned.json()["clonedExam"]
    assert cloned_exam["id"] != share_exam["id"]
    assert cloned_exam["revision"] == 1
    assert cloned_exam["clonedFrom"]["token"] == token
    assert cloned_exam["questions"][0]["id"] != share_exam["questions"][0]["id"]
    cloned_raw = str(cloned_exam)
    assert "BÍ_MẬT_CHAT_KHÔNG_ĐƯỢC_CÔNG_BỐ" not in cloned_raw
    assert "SECRET_TOKEN_KHÔNG_CÔNG_BỐ" not in cloned_raw
    assert "ĐÁP_ÁN_LỜI_GIẢI_TRẮC_NGHIỆM_RIÊNG" not in cloned_raw

    rev = local_client.post("/api/share/revoke", json={"token": token})
    assert rev.status_code == 200
    assert local_client.post(f"/api/community-exams/{token}/clone").status_code == 410

    # 3. OCR cấu trúc giữ LaTeX & hình vẽ + đánh dấu vùng chưa chắc
    ocr_res = local_client.post(
        "/api/ocr/structure",
        json={
            "pages": [
                {
                    "number": 1,
                    "text": (
                        "Câu 1. Tính $\\frac{x+1}{2}$ biết "
                        "[HÌNH 1: Đường tròn tâm O] và chữ [không rõ]."
                    ),
                    "uncertain": True,
                }
            ]
        },
    )
    assert ocr_res.status_code == 200, ocr_res.text
    ocr_data = ocr_res.json()
    assert ocr_data["needs_teacher_review"] is True
    assert ocr_data["math_blocks"]
    assert ocr_data["figures"]
    assert ocr_data["uncertain_regions"]

    # 4. Đáp án & barem 0,25đ (chặn học sinh) + Ma trận/Đặc tả HTML A4 & DOCX OMML
    student_blocked = local_client.post(
        "/api/exports/answer-key-rubric",
        json={"exam": exam, "audience": "student", "teacher": False, "format": "html"},
    )
    assert student_blocked.status_code == 403

    key_html = local_client.post(
        "/api/exports/answer-key-rubric",
        json={"exam": exam, "audience": "teacher", "teacher": True, "format": "html"},
    )
    assert key_html.status_code == 200
    assert "@page" in key_html.text and "A4" in key_html.text

    key_docx = local_client.post(
        "/api/exports/answer-key-rubric",
        json={"exam": exam, "audience": "teacher", "teacher": True, "format": "docx"},
    )
    assert key_docx.status_code == 200
    with zipfile.ZipFile(io.BytesIO(key_docx.content)) as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "m:oMath" in doc_xml
    assert len(Document(io.BytesIO(key_docx.content)).tables) >= 1

    spec_html = local_client.post(
        "/api/exports/matrix-specification",
        json={"exam": exam, "format": "html"},
    )
    assert spec_html.status_code == 200
    assert "Nhận biết" in spec_html.text and "Vận dụng" in spec_html.text

    spec_docx = local_client.post(
        "/api/exports/matrix-specification",
        json={"exam": exam, "format": "docx"},
    )
    assert spec_docx.status_code == 200
    assert len(Document(io.BytesIO(spec_docx.content)).tables) >= 1


def test_unified_team_workspace_guest_csrf_owner_isolation_and_community_shares(team_bundle):
    app, admin, member, _ = team_bundle
    exam = _sample_exam()

    # Khách chưa đăng nhập bị chặn 401 ở tất cả route hợp nhất
    with TestClient(app, headers=LOCAL_ORIGIN) as guest:
        for method, url, body in (
            ("GET", "/api/lesson-catalog", None),
            ("GET", "/api/lesson-catalog/sources", None),
            ("POST", "/api/lesson-catalog/sources", {"grade": 7, "subject": "Toán", "title": "T"}),
            ("GET", "/api/community-exams", None),
            ("GET", "/api/community-exams/clones", None),
            ("POST", "/api/ocr/structure", {"pages": [{"number": 1, "text": "x"}]}),
            ("POST", "/api/exports/matrix-specification", {"exam": exam}),
        ):
            res = guest.request(method, url, json=body)
            assert res.status_code == 401, f"{method} {url} -> {res.status_code} {res.text}"

    with _login(app, admin["email"]) as admin_client, _login(app, member["email"]) as member_client:
        # CSRF Origin sai -> 403; stale X-Workspace-Context -> 409
        bad_origin = admin_client.post(
            "/api/lesson-catalog/sources",
            headers={"Origin": "https://evil.example"},
            json={"grade": 7, "subject": "Toán", "title": "CSRF"},
        )
        assert bad_origin.status_code == 403

        stale_ctx = admin_client.get(
            "/api/community-exams",
            headers={"X-Workspace-Context": f"team:{member['id']}"},
        )
        assert stale_ctx.status_code == 409
        assert stale_ctx.json()["code"] == "workspace_context_changed"

        # Cách ly nguồn phân cấp giữa admin và member
        created_src = admin_client.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 8,
                "subject": "Vật lí",
                "book": "Chân trời sáng tạo",
                "volume": "Cả năm",
                "chapter": "Chương 1",
                "lesson": "Bài 1",
                "title": "Nguồn riêng của admin",
                "licenseStatus": "teacher_owned",
                "locator": "Trang 5",
                "contentExcerpt": "Đo khối lượng riêng.",
            },
        )
        assert created_src.status_code == 201, created_src.text
        src_id = created_src.json()["id"]
        assert member_client.get(f"/api/lesson-catalog/sources/{src_id}").status_code == 404

        # Kho cộng đồng dùng chung qua /api/share & /api/community-exams
        share_exam = _shareable_plain_exam()
        _seed_exam(admin_client, share_exam)
        pub = admin_client.post(
            "/api/share",
            json={
                "examId": share_exam["id"],
                "baseRevision": 1,
                "answers": False,
                "allowCopy": True,
                "community": True,
                "consentPublic": True,
                "series": "Kết nối tri thức",
                "chapter": "Số hữu tỉ",
            },
        )
        assert pub.status_code == 200, pub.text
        token = pub.json()["token"]

        listed = member_client.get(
            "/api/community-exams", params={"grade": "7", "subject": "toan", "series": "ket noi"}
        )
        assert listed.status_code == 200
        assert any(it["token"] == token for it in listed.json()["exams"])

        member_clone = member_client.post(f"/api/community-exams/{token}/clone")
        assert member_clone.status_code == 201, member_clone.text
        clone_id = member_clone.json()["cloneRecord"]["clone_id"]

        # Member không được revoke snapshot của admin -> 404
        assert member_client.post("/api/share/revoke", json={"token": token}).status_code == 404

        # Admin thu hồi -> clone mới trả 410 nhưng bản clone trước đó của member vẫn còn nguyên
        assert admin_client.post("/api/share/revoke", json={"token": token}).status_code == 200
        assert member_client.post(f"/api/community-exams/{token}/clone").status_code == 410
        kept = member_client.get(f"/api/community-exams/clones/{clone_id}")
        assert kept.status_code == 200
        assert kept.json()["clonedExam"]["clonedFrom"]["token"] == token

        # Member dùng được endpoint xuất ma trận/đặc tả A4 trong workspace riêng của mình
        spec_res = member_client.post(
            "/api/exports/matrix-specification",
            json={"exam": exam, "format": "html"},
        )
        assert spec_res.status_code == 200
        assert "@page" in spec_res.text


def _seed_single_mcq_with_personal_lesson(
    client: TestClient,
    source_id: str,
    version: int,
    *,
    pages: list[dict],
) -> tuple[dict, str]:
    exam_id = str(uuid4())
    q_id = str(uuid4())
    exam = {
        "id": exam_id,
        "title": "Đề kiểm tra học liệu cá nhân",
        "subject": "Sinh học",
        "grade": "10",
        "revision": 1,
        "matrixConfirmed": True,
        "matrix": [{"topic": "Tế bào", "type": "mcq", "targets": [1, 0, 0, 0]}],
        "docs": [
            {
                "id": source_id,
                "name": "Nguồn cá nhân",
                "kind": "text",
                "version": version,
                "personalLesson": True,
                "licenseStatus": "allowed",
                "pages": pages,
            }
        ],
        "questions": [
            {
                "id": q_id,
                "v": 1,
                "type": "mcq",
                "level": 0,
                "topic": "Tế bào",
                "stem": "Thành phần nào là nguồn năng lượng chính của tế bào?",
                "options": ["ATP", "ADN", "Xenlulozơ", "Tinh bột"],
                "answer": 0,
                "points": 1.0,
            }
        ],
    }
    _seed_exam(client, exam)
    return exam, q_id


def test_personal_lesson_authoritative_resolution_and_cross_owner_isolation(tmp_path):
    # 1. Local workspace: server-authoritative restricted/version/text cho schema personalLesson
    app = create_app(tmp_path)
    with TestClient(app, headers=LOCAL_ORIGIN) as client:
        allowed = client.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 10,
                "subject": "Sinh học",
                "series": "Kết nối tri thức",
                "volume": "Tập 1",
                "chapter": "Chương 1",
                "lesson": "Bài 1",
                "title": "Năng lượng tế bào",
                "licenseStatus": "teacher_owned",
                "locator": "Trang 15",
                "contentExcerpt": "ATP là đồng tiền năng lượng chuẩn từ SQLite.",
            },
        )
        assert allowed.status_code == 201, allowed.text
        allowed_data = allowed.json()

        restricted = client.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 10,
                "subject": "Sinh học",
                "title": "Tài liệu bị hạn chế",
                "licenseStatus": "restricted",
                "contentExcerpt": "Không được phép gửi cho AI.",
            },
        )
        assert restricted.status_code == 201, restricted.text
        restricted_data = restricted.json()

        stamp = app.state.provider.connection_stamp

        # 1a. Client giả mạo licenseStatus="allowed" trên nguồn restricted -> chặn 403
        exam_tampered, q_tampered = _seed_single_mcq_with_personal_lesson(
            client,
            restricted_data["id"],
            restricted_data["updated_at"],
            pages=[{"number": 1, "text": "Client giả mạo nội dung được phép dùng."}],
        )
        approve_tampered = client.post(
            f"/api/exams/{exam_tampered['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Tài liệu bị hạn chế",
                "sourceMode": "provided",
                "sources": [
                    {
                        "sourceId": restricted_data["id"],
                        "sourceVersion": restricted_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert approve_tampered.status_code == 403, approve_tampered.text
        assert approve_tampered.json()["code"] == "source_license_restricted"

        check_tampered = client.post(
            f"/api/exams/{exam_tampered['id']}/questions/{q_tampered}/check",
            headers={"X-PoC-Config": stamp},
            json={
                "baseRevision": 1,
                "questionVersion": 1,
                "consent": True,
                "sources": [
                    {
                        "sourceId": restricted_data["id"],
                        "sourceVersion": restricted_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert check_tampered.status_code == 403, check_tampered.text
        assert check_tampered.json()["detail"]["code"] == "source_license_restricted"

        # 1b. Nguồn teacher_owned -> lấy content_excerpt chuẩn từ SQLite dù client sửa pages[0].text
        exam_ok, q_ok = _seed_single_mcq_with_personal_lesson(
            client,
            allowed_data["id"],
            allowed_data["updated_at"],
            pages=[{"number": 1, "text": "VAN_BAN_CLIENT_GIA_MAO"}],
        )
        approve_ok = client.post(
            f"/api/exams/{exam_ok['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Năng lượng tế bào",
                "sourceMode": "provided",
                "sources": [
                    {
                        "sourceId": allowed_data["id"],
                        "sourceVersion": allowed_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert approve_ok.status_code == 200, approve_ok.text
        stored_sources = app.state.store.get("matrix-source:" + exam_ok["id"])["value"]
        assert stored_sources[0]["text"] == "ATP là đồng tiền năng lượng chuẩn từ SQLite."
        assert "VAN_BAN_CLIENT_GIA_MAO" not in stored_sources[0]["text"]

        # 1c. PATCH đổi nội dung (tăng updated_at) -> đính kèm version cũ bị chặn 409 stale_snapshot
        patched = client.patch(
            f"/api/lesson-catalog/sources/{allowed_data['id']}",
            headers={"If-Match": str(allowed_data["updated_at"])},
            json={"contentExcerpt": "Nội dung đã cập nhật mới trên server SQLite."},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["updated_at"] > allowed_data["updated_at"]

        approve_stale = client.post(
            f"/api/exams/{exam_ok['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Năng lượng tế bào",
                "sourceMode": "provided",
                "sources": [
                    {
                        "sourceId": allowed_data["id"],
                        "sourceVersion": allowed_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert approve_stale.status_code == 409, approve_stale.text
        assert approve_stale.json()["code"] == "stale_snapshot"

        check_stale = client.post(
            f"/api/exams/{exam_ok['id']}/questions/{q_ok}/check",
            headers={"X-PoC-Config": stamp},
            json={
                "baseRevision": 1,
                "questionVersion": 1,
                "consent": True,
                "sources": [
                    {
                        "sourceId": allowed_data["id"],
                        "sourceVersion": allowed_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert check_stale.status_code == 409, check_stale.text
        assert check_stale.json()["detail"]["code"] == "stale_snapshot"

    # 2. Team workspace: member gắn chéo sourceId của admin -> chặn 404 source_not_found
    team_app = create_team_app(tmp_path / "team-isolation")
    accounts = team_app.state.accounts
    admin = accounts.create(
        "admin-iso@example.test", TEAM_PASSWORD, "Admin", accounts.invite(bootstrap=True)
    )
    member = accounts.create(
        "member-iso@example.test",
        TEAM_PASSWORD,
        "Member",
        accounts.invite(email="member-iso@example.test"),
    )
    with _login(team_app, admin["email"]) as admin_c, _login(team_app, member["email"]) as member_c:
        admin_src = admin_c.post(
            "/api/lesson-catalog/sources",
            json={
                "grade": 10,
                "subject": "Sinh học",
                "title": "Nguồn mật của Admin",
                "licenseStatus": "teacher_owned",
                "contentExcerpt": "Nội dung chỉ Admin sở hữu.",
            },
        )
        assert admin_src.status_code == 201, admin_src.text
        admin_src_data = admin_src.json()
        member_exam, _ = _seed_single_mcq_with_personal_lesson(
            member_c,
            admin_src_data["id"],
            admin_src_data["updated_at"],
            pages=[{"number": 1, "text": "Member gắn chéo source ID của Admin"}],
        )
        cross = member_c.post(
            f"/api/exams/{member_exam['id']}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceText": "",
                "sourceName": "Chéo quyền",
                "sourceMode": "provided",
                "sources": [
                    {
                        "sourceId": admin_src_data["id"],
                        "sourceVersion": admin_src_data["updated_at"],
                        "locator": {"kind": "page", "index": 1},
                    }
                ],
            },
        )
        assert cross.status_code == 404, cross.text
        assert cross.json()["code"] == "source_not_found"
