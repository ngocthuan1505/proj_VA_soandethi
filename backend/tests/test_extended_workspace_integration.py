"""Kiểm thử tích hợp các router Python mở rộng trên local_workspace và team_workspace."""

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
    return {
        "id": str(uuid4()),
        "title": "Đề kiểm tra giữa kì I — Toán 7",
        "subject": "Toán",
        "grade": 7,
        "series": "Kết nối tri thức",
        "chapter": "Số hữu tỉ",
        "school": "THCS Mẫu Tích Hợp",
        "revision": 1,
        "chat": [{"role": "user", "text": "BÍ_MẬT_CHAT_KHÔNG_ĐƯỢC_CÔNG_BỐ"}],
        "aiConfig": {"apiKey": "SECRET_TOKEN_KHÔNG_CÔNG_BỐ"},
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


def test_local_workspace_routes_curriculum_community_ocr_and_a4_exports(local_client: TestClient):
    # 1. Nguồn phân cấp + kiểm soát license_status 403/200 trong local_workspace
    allowed_res = local_client.post(
        "/api/curriculum/sources",
        json={
            "grade": 7,
            "subject": "Toán",
            "series": "Kết nối tri thức",
            "volume": "Tập 1",
            "chapter": "Chương 1: Số hữu tỉ",
            "lesson": "Bài 2: Cộng, trừ, nhân, chia số hữu tỉ",
            "title": "Ví dụ tính toán phân số",
            "license_status": "allowed",
            "license_note": "Tự biên soạn dùng công khai",
            "source_origin": "SGK tự viết",
            "locator": "Trang 12, mục 2",
            "content_excerpt": "Quy tắc cộng hai số hữu tỉ: đưa về cùng mẫu dương.",
        },
    )
    assert allowed_res.status_code == 201, allowed_res.text
    allowed_id = allowed_res.json()["id"]

    restricted_res = local_client.post(
        "/api/curriculum/sources",
        json={
            "grade": 7,
            "subject": "Toán",
            "series": "Kết nối tri thức",
            "volume": "Tập 1",
            "chapter": "Chương 1: Số hữu tỉ",
            "lesson": "Bài 2: Cộng, trừ, nhân, chia số hữu tỉ",
            "title": "Ngữ liệu chưa có quyền",
            "license_status": "restricted",
            "license_note": "Chỉ tham khảo nội bộ",
            "source_origin": "Kho hạn chế",
            "locator": "Trang 99",
            "content_excerpt": "Nội dung hạn chế trích dẫn tự động.",
        },
    )
    assert restricted_res.status_code == 201, restricted_res.text
    restricted_id = restricted_res.json()["id"]

    cite_ok = local_client.get(f"/api/curriculum/sources/{allowed_id}/citation")
    assert cite_ok.status_code == 200, cite_ok.text
    assert cite_ok.json()["locator"] == "Trang 12, mục 2"
    assert len(cite_ok.json()["sha256"]) == 64

    cite_blocked = local_client.get(
        f"/api/curriculum/sources/{restricted_id}/citation",
        params={"allow_unverified": "true"},
    )
    assert cite_blocked.status_code == 403, cite_blocked.text
    assert cite_blocked.json()["code"] == "source_license_restricted"

    # 2. Kho cộng đồng: ép consent_public, cắt đáp án/chat/token, clone UUID mới & revoke
    exam = _sample_exam()
    no_consent = local_client.post(
        "/api/community/publish",
        json={"consent_public": False, "exam": exam},
    )
    assert no_consent.status_code == 400
    assert no_consent.json()["code"] == "consent_required"

    pub = local_client.post(
        "/api/community/publish",
        json={"consent_public": True, "include_answers": False, "exam": exam},
    )
    assert pub.status_code == 201, pub.text
    pub_json = pub.json()
    item_id = pub_json["id"]
    pub_text = str(pub_json)
    assert "BÍ_MẬT_CHAT_KHÔNG_ĐƯỢC_CÔNG_BỐ" not in pub_text
    assert "SECRET_TOKEN_KHÔNG_CÔNG_BỐ" not in pub_text
    assert "ĐÁP_ÁN_LỜI_GIẢI_TRẮC_NGHIỆM_RIÊNG" not in pub_text
    assert "ĐÁP_ÁN_TỰ_LUẬN_RIÊNG" not in pub_text

    cloned = local_client.post(f"/api/community/items/{item_id}/clone")
    assert cloned.status_code == 201, cloned.text
    cloned_exam = cloned.json()["clonedExam"]
    assert cloned_exam["id"] != exam["id"]
    assert cloned_exam["revision"] == 1
    assert cloned_exam["clonedFrom"]["communityItemId"] == item_id
    assert cloned_exam["questions"][0]["id"] != exam["questions"][0]["id"]

    revoked = local_client.post(f"/api/community/items/{item_id}/revoke")
    assert revoked.status_code == 200
    assert local_client.get(f"/api/community/items/{item_id}").status_code == 410
    assert local_client.post(f"/api/community/items/{item_id}/clone").status_code == 410

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
    assert "Đổi phép chia thành nhân nghịch đảo" in key_html.text

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


def test_team_workspace_guest_csrf_owner_isolation_and_shared_community(team_bundle):
    app, admin, member, _ = team_bundle

    # Khách chưa đăng nhập bị chặn 401 ở tất cả nhóm mở rộng
    with TestClient(app, headers=LOCAL_ORIGIN) as guest:
        for method, url, body in (
            ("GET", "/api/curriculum/sources", None),
            ("POST", "/api/curriculum/sources", {"grade": 7, "subject": "Toán", "title": "T"}),
            ("GET", "/api/community/items", None),
            ("POST", "/api/community/publish", {"consent_public": True, "exam": _sample_exam()}),
            ("POST", "/api/ocr/structure", {"pages": [{"number": 1, "text": "x"}]}),
            ("POST", "/api/exports/matrix-specification", {"exam": _sample_exam()}),
        ):
            res = guest.request(method, url, json=body)
            assert res.status_code == 401, f"{method} {url} -> {res.status_code} {res.text}"

    with _login(app, admin["email"]) as admin_client, _login(app, member["email"]) as member_client:
        # CSRF Origin sai -> 403; stale X-Workspace-Context -> 409
        bad_origin = admin_client.post(
            "/api/curriculum/sources",
            headers={"Origin": "https://evil.example"},
            json={"grade": 7, "subject": "Toán", "title": "CSRF"},
        )
        assert bad_origin.status_code == 403

        stale_ctx = admin_client.get(
            "/api/community/items",
            headers={"X-Workspace-Context": f"team:{member['id']}"},
        )
        assert stale_ctx.status_code == 409
        assert stale_ctx.json()["code"] == "workspace_context_changed"

        # Cách ly nguồn phân cấp giữa admin và member
        created_src = admin_client.post(
            "/api/curriculum/sources",
            json={
                "grade": 8,
                "subject": "Vật lí",
                "series": "Chân trời sáng tạo",
                "volume": "Cả năm",
                "chapter": "Chương 1",
                "lesson": "Bài 1",
                "title": "Nguồn riêng của admin",
                "license_status": "teacher_owned",
                "locator": "Trang 5",
                "content_excerpt": "Đo khối lượng riêng.",
            },
        )
        assert created_src.status_code == 201, created_src.text
        src_id = created_src.json()["id"]
        assert member_client.get(f"/api/curriculum/sources/{src_id}").status_code == 404

        # Kho cộng đồng dùng chung giữa thành viên đã đăng nhập & kiểm quyền revoke
        exam = _sample_exam()
        pub = admin_client.post(
            "/api/community/publish",
            json={"consent_public": True, "include_answers": False, "exam": exam},
        )
        assert pub.status_code == 201, pub.text
        item_id = pub.json()["id"]

        listed = member_client.get("/api/community/items", params={"grade": 7, "subject": "Toán"})
        assert listed.status_code == 200
        assert any(it["id"] == item_id for it in listed.json()["items"])

        member_clone = member_client.post(f"/api/community/items/{item_id}/clone")
        assert member_clone.status_code == 201, member_clone.text
        clone_id = member_clone.json()["cloneRecord"]["clone_id"]

        # Member không được phép thu hồi đề của admin
        forbidden_revoke = member_client.post(f"/api/community/items/{item_id}/revoke")
        assert forbidden_revoke.status_code == 403
        assert forbidden_revoke.json()["code"] == "forbidden"

        # Admin thu hồi -> item trả 410 nhưng clone trước đó của member vẫn còn nguyên
        assert admin_client.post(f"/api/community/items/{item_id}/revoke").status_code == 200
        assert member_client.get(f"/api/community/items/{item_id}").status_code == 410
        kept_clone = member_client.get(f"/api/community/clones/{clone_id}")
        assert kept_clone.status_code == 200
        assert kept_clone.json()["clonedExam"]["clonedFrom"]["communityItemId"] == item_id

        # Member dùng được endpoint xuất ma trận/đặc tả A4 trong workspace riêng của mình
        spec_res = member_client.post(
            "/api/exports/matrix-specification",
            json={"exam": exam, "format": "html"},
        )
        assert spec_res.status_code == 200
        assert "@page" in spec_res.text
