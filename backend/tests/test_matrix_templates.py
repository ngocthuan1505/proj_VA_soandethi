"""Kiểm thử CRUD, If-Match, validation, cô lập chủ sở hữu và sao lưu mẫu ma trận cá nhân."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from mach_backend.ai_contract import AIError
from mach_backend.local_workspace import create_app
from mach_backend.matrix_templates import install_matrix_templates
from mach_backend.team_workspace import create_team_app

ORIGIN = {"Origin": "http://testserver"}


def _sample_template(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Giữa kỳ I Toán 9 · Chuẩn 10 điểm",
        "subject": "Toán",
        "grade": "9",
        "rows": [
            {"topic": "Căn bậc hai", "type": "mcq", "targets": [2, 2, 0, 0], "pointsQ4": 2},
            {"topic": "Hàm số bậc nhất", "type": "essay", "targets": [0, 1, 1, 0], "pointsQ4": 16},
        ],
        "notes": "Ưu tiên kiểm tra bước biến đổi căn thức.",
    }
    payload.update(overrides)
    return payload


def _isolated_template_app(tmp_path: Path):
    db_path = tmp_path / "templates.sqlite3"
    now = [1_000_000.0]

    @contextmanager
    def connect():
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def owner(request: Request) -> str:
        val = request.headers.get("X-Owner")
        if not val:
            raise HTTPException(401, "Chưa đăng nhập.")
        return val

    app = FastAPI()

    @app.exception_handler(AIError)
    async def on_ai_error(_req: Request, exc: AIError):
        return JSONResponse({"error": str(exc), "code": exc.code}, exc.http_status or 400)

    install_matrix_templates(app, connect, owner_resolver=owner, clock=lambda: now[0])
    return app, now


def test_matrix_templates_crud_filtering_and_if_match(tmp_path: Path):
    app, now = _isolated_template_app(tmp_path)
    with TestClient(app) as client:
        owner_a = {"X-Owner": "teacher_a"}
        owner_b = {"X-Owner": "teacher_b"}

        created = client.post("/api/matrix-templates", headers=owner_a, json=_sample_template())
        assert created.status_code == 201, created.text
        tpl = created.json()
        tpl_id = tpl["id"]
        assert tpl["total_questions"] == 6
        assert tpl["total_points_q4"] == 40
        assert tpl["updated_at"] == 1_000_000.0

        client.post(
            "/api/matrix-templates",
            headers=owner_a,
            json=_sample_template(name="Kiểm tra 15 phút Sinh 10", subject="Sinh học", grade="10"),
        )

        # Lọc tiếng Việt không phân biệt hoa thường & theo subject/grade
        filtered = client.get(
            "/api/matrix-templates",
            headers=owner_a,
            params={"subject": "toán", "grade": "9", "q": "căn bậc"},
        )
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        assert filtered.json()["templates"][0]["id"] == tpl_id

        # Cô lập chủ sở hữu trên cùng SQLite DB
        assert client.get("/api/matrix-templates", headers=owner_b).json()["total"] == 0
        assert client.get(f"/api/matrix-templates/{tpl_id}", headers=owner_b).status_code == 404
        assert (
            client.patch(
                f"/api/matrix-templates/{tpl_id}", headers=owner_b, json={"name": "X"}
            ).status_code
            == 404
        )
        assert client.delete(f"/api/matrix-templates/{tpl_id}", headers=owner_b).status_code == 404

        # If-Match 409 khi sai phiên bản, 200 khi đúng
        stale = client.patch(
            f"/api/matrix-templates/{tpl_id}",
            headers={**owner_a, "If-Match": "999.0"},
            json={"name": "Cũ"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "template_conflict"

        now[0] += 5.0
        updated = client.patch(
            f"/api/matrix-templates/{tpl_id}",
            headers={**owner_a, "If-Match": str(tpl["updated_at"])},
            json={"name": "Giữa kỳ I Toán 9 · Bản 2"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == "Giữa kỳ I Toán 9 · Bản 2"
        assert updated.json()["updated_at"] == 1_000_005.0

        deleted = client.delete(f"/api/matrix-templates/{tpl_id}", headers=owner_a)
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True, "id": tpl_id}
        assert client.get(f"/api/matrix-templates/{tpl_id}", headers=owner_a).status_code == 404


def test_matrix_templates_validation_rejects_invalid_inputs(tmp_path: Path):
    app, _ = _isolated_template_app(tmp_path)
    with TestClient(app) as client:
        headers = {"X-Owner": "teacher_a"}
        cases = [
            _sample_template(rows=[{"topic": "Trống", "type": "mcq", "targets": [0, 0, 0, 0]}]),
            _sample_template(
                rows=[{"topic": "Quá nhiều", "type": "mcq", "targets": [15, 16, 0, 0]}]
            ),
            _sample_template(rows=[{"topic": "Sai loại", "type": "fill", "targets": [1, 0, 0]}]),
            _sample_template(rows=[{"topic": "Bool", "type": "mcq", "targets": [True, 0, 0]}]),
            _sample_template(
                rows=[{"topic": "Điểm sai", "type": "mcq", "targets": [1, 0, 0], "pointsQ4": 0}]
            ),
            _sample_template(
                rows=[
                    {
                        "topic": "Lệch điểm mức",
                        "type": "mcq",
                        "targets": [1, 0, 0],
                        "pointsByLevelQ4": [2, 2],
                    }
                ]
            ),
            {**_sample_template(), "extraField": 1},
        ]
        for bad in cases:
            res = client.post("/api/matrix-templates", headers=headers, json=bad)
            assert res.status_code == 422, (bad, res.text)


def test_matrix_templates_team_auth_and_backup_atomic_restore(tmp_path: Path):
    from test_workspace_backup import backup_fixture

    team_app = create_team_app(tmp_path / "team")
    accounts = team_app.state.accounts
    accounts.create(
        "admin@example.test", "mat-khau-du-dai-123", "Admin", accounts.invite(bootstrap=True)
    )
    accounts.create(
        "member@example.test",
        "mat-khau-du-dai-123",
        "Member",
        accounts.invite(email="member@example.test"),
    )
    with TestClient(team_app, headers=ORIGIN) as guest:
        assert guest.get("/api/matrix-templates").status_code == 401
        assert guest.post("/api/matrix-templates", json=_sample_template()).status_code == 401

    with (
        TestClient(team_app, headers=ORIGIN) as admin_client,
        TestClient(team_app, headers=ORIGIN) as member_client,
    ):
        assert (
            admin_client.post(
                "/api/account/login",
                json={"email": "admin@example.test", "password": "mat-khau-du-dai-123"},
            ).status_code
            == 200
        )
        assert (
            member_client.post(
                "/api/account/login",
                json={"email": "member@example.test", "password": "mat-khau-du-dai-123"},
            ).status_code
            == 200
        )
        created = admin_client.post("/api/matrix-templates", json=_sample_template()).json()
        assert member_client.get("/api/matrix-templates").json()["total"] == 0
        assert admin_client.get("/api/matrix-templates").json()["total"] == 1
        assert member_client.get(f"/api/matrix-templates/{created['id']}").status_code == 404

    with (
        TestClient(create_app(tmp_path / "origin"), headers=ORIGIN) as origin,
        TestClient(create_app(tmp_path / "target"), headers=ORIGIN) as target,
    ):
        tpl = origin.post("/api/matrix-templates", json=_sample_template()).json()
        backup = backup_fixture()
        backup["matrixTemplates"] = [tpl]

        preview = target.post("/api/workspace/restore/preview", json=backup)
        assert preview.status_code == 200, preview.text
        assert preview.json()["matrixTemplates"] == 1

        restored = target.post(
            "/api/workspace/restore",
            json=backup,
            headers={"If-Match": str(preview.json()["revision"])},
        )
        assert restored.status_code == 200, restored.text
        target_list = target.get("/api/matrix-templates").json()
        assert target_list["total"] == 1
        assert target_list["templates"][0]["id"] == tpl["id"]

        # Xung đột nội dung trùng UUID không ghi đè đề hay mẫu
        before_state = target.get("/api/kv?key=state").json()
        conflicting = {
            **backup,
            "matrixTemplates": [{**tpl, "name": "Bản ghi đè bất hợp pháp"}],
        }
        rejected = target.post(
            "/api/workspace/restore",
            json=conflicting,
            headers={"If-Match": str(before_state["revision"])},
        )
        assert rejected.status_code == 409
        assert target.get("/api/kv?key=state").json() == before_state
        assert target.get(f"/api/matrix-templates/{tpl['id']}").json()["name"] == tpl["name"]
