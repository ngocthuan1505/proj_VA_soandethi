"""Tài khoản/kho riêng bằng dữ liệu tự viết, không khóa thật hoặc GreenNode."""

import base64
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mach_backend.team_accounts import TeamAccounts, digest
from mach_backend.team_workspace import COOKIE, create_team_app

PASSWORD = "mat-khau-chi-dung-test"
ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def team(tmp_path):
    now = [1000]
    app = create_team_app(tmp_path, clock=lambda: now[0])
    accounts = app.state.accounts
    admin = accounts.create(
        "admin@example.test", PASSWORD, "Quản trị thử", accounts.invite(bootstrap=True)
    )
    member = accounts.create(
        "member@example.test",
        PASSWORD,
        "Thành viên thử",
        accounts.invite(email="member@example.test"),
    )
    return app, accounts, admin, member, now


def signed_client(app, email):
    client = TestClient(app, headers=ORIGIN)
    response = client.post("/api/account/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def test_stale_tab_cannot_read_or_change_another_account_workspace(team):
    from test_workspace_backup import backup_fixture

    app, _, admin, member, _ = team
    with signed_client(app, member["email"]) as client:
        stale = {"X-Workspace-Context": f"team:{admin['id']}", "If-Match": "0"}
        backup = backup_fixture()
        for method, path, payload in (
            ("GET", "/api/account", None),
            ("POST", "/api/account/logout", {}),
            ("GET", "/api/kv?key=state", None),
            ("PUT", "/api/kv", {"key": "state", "value": backup["state"]}),
            ("POST", "/api/save-export", {"type": "backup", "state": backup["state"]}),
            ("POST", "/api/share", {}),
            ("POST", "/api/assistant/chat", {}),
            ("POST", "/api/workspace/restore/preview", backup),
            ("POST", "/api/workspace/restore", backup),
        ):
            response = client.request(method, path, headers=stale, json=payload)
            assert response.status_code == 409, response.text
            assert response.json()["code"] == "workspace_context_changed"
        assert not app.state.workspaces
        own = {"X-Workspace-Context": f"team:{member['id']}"}
        assert client.get("/api/kv?key=state", headers=own).json()["value"] is None
        assert client.post("/api/workspace/restore/preview", headers=own, json=backup).is_success


def test_restore_only_changes_signed_in_workspace_and_keeps_other_owner(team):
    from test_workspace_backup import backup_fixture

    app, _, admin, member, _ = team
    with signed_client(app, admin["email"]) as owner, signed_client(app, member["email"]) as other:
        backup = backup_fixture()
        assert owner.post("/api/workspace/restore/preview", json=backup).status_code == 200
        assert (
            owner.post("/api/workspace/restore", json=backup, headers={"If-Match": "0"}).status_code
            == 200
        )
        other_backup = backup_fixture()
        assert (
            other.post(
                "/api/workspace/restore", json=other_backup, headers={"If-Match": "0"}
            ).status_code
            == 200
        )
        assert owner.get("/api/kv?key=state").json()["value"] == backup["state"]
        assert other.get("/api/kv?key=state").json()["value"] == other_backup["state"]
        assert owner.get("/api/account").json()["user"]["id"] == admin["id"]
        assert other.get("/api/account").json()["user"]["id"] == member["id"]
    with TestClient(app, headers=ORIGIN) as guest:
        for suffix in ["", "/preview"]:
            assert guest.post("/api/workspace/restore" + suffix, json=backup).status_code == 401


def test_password_session_invite_are_hashed_and_logout_revokes(team):
    app, accounts, admin, _, _ = team
    with signed_client(app, admin["email"]) as client:
        token = client.cookies.get(COOKIE)
        header = client.post(
            "/api/account/login", json={"email": admin["email"], "password": PASSWORD}
        ).headers["set-cookie"]
        assert "HttpOnly" in header and "SameSite=strict" in header
        assert accounts.user(token)["id"] == admin["id"]
        with accounts.connect() as db:
            row = db.execute(
                "SELECT password,salt FROM users WHERE id=?", (admin["id"],)
            ).fetchone()
            assert PASSWORD.encode() not in row["password"] and len(row["salt"]) == 16
            assert (
                db.execute("SELECT token FROM sessions WHERE token=?", (token,)).fetchone() is None
            )
            assert db.execute(
                "SELECT token FROM sessions WHERE token=?", (digest(token),)
            ).fetchone()
        current = client.cookies.get(COOKIE)
        assert client.post("/api/account/logout").status_code == 200
        assert accounts.user(current) is None
        assert client.get("/api/kv?key=state").status_code == 401


def test_expired_session_denies_data_even_with_cookie(team):
    app, _, admin, _, now = team
    with signed_client(app, admin["email"]) as client:
        now[0] += 8 * 3600 + 1
        assert client.get("/api/account").status_code == 401
        assert client.get("/api/kv?key=state").status_code == 401


def test_invite_is_email_bound_one_use_and_expires(team):
    _, accounts, _, _, now = team
    invite = accounts.invite(email="third@example.test")
    with pytest.raises(HTTPException):
        accounts.create("other@example.test", PASSWORD, "Khác", invite)
    user = accounts.create("third@example.test", PASSWORD, "Người thứ ba", invite)
    assert user["role"] == "member"
    with pytest.raises(HTTPException):
        accounts.create("fourth@example.test", PASSWORD, "Người thứ tư", invite)
    expired = accounts.invite()
    now[0] += 86401
    with pytest.raises(HTTPException):
        accounts.create("fifth@example.test", PASSWORD, "Người thứ năm", expired)
    with pytest.raises(HTTPException):
        accounts.invite(bootstrap=True)


def test_invitation_atomic_under_two_registrations(team):
    _, accounts, *_ = team
    token = accounts.invite()

    def register(index):
        try:
            return accounts.create(f"race{index}@example.test", PASSWORD, "Đồng thời", token)["id"]
        except HTTPException:
            return None

    with ThreadPoolExecutor(2) as pool:
        assert sum(bool(result) for result in pool.map(register, range(2))) == 1


def test_failed_login_rate_is_persistent(team):
    _, accounts, admin, _, now = team
    for _ in range(10):
        with pytest.raises(HTTPException) as error:
            accounts.login(admin["email"], "sai-mat-khau-thu", "127.0.0.1")
        assert error.value.status_code == 401
    reopened = TeamAccounts(accounts.file.parent, clock=lambda: now[0])
    with pytest.raises(HTTPException) as error:
        reopened.login(admin["email"], PASSWORD, "127.0.0.1")
    assert error.value.status_code == 429
    now[0] += 601
    assert reopened.login(admin["email"].upper(), PASSWORD, "127.0.0.1")["id"] == admin["id"]


def test_anonymous_and_cross_origin_cannot_access_data(team):
    app, *_ = team
    with TestClient(app) as client:
        assert client.get("/", follow_redirects=False).headers["location"] == "/login"
        assert client.get("/login").status_code == 200
        assert client.get("/assets/team-login.js").status_code == 200
        assert client.get("/api/kv?key=state").status_code == 401
        assert client.get("/api/source-file/known").status_code == 401
        assert client.get("/backend/pyproject.toml").status_code == 404
        assert client.get("/.data/team-workspace/accounts.sqlite").status_code == 404
        assert client.post("/api/account/login", json={}).status_code == 403
        assert (
            client.post(
                "/api/account/login", headers={"Origin": "http://evil.test"}, json={}
            ).status_code
            == 403
        )
        assert client.get("/", headers={"Host": "public.example.test"}).status_code == 403
        invalid = "password-too-long-" * 20
        response = client.post(
            "/api/account/login",
            headers=ORIGIN,
            json={"email": "owner@example.test", "password": invalid},
        )
        assert response.status_code == 422 and invalid not in response.text


def test_two_users_have_private_state_files_exports_and_admin_settings(team, tmp_path):
    app, accounts, admin, member, _ = team
    with signed_client(app, admin["email"]) as first, signed_client(app, member["email"]) as second:
        exam_id = str(uuid4())
        exam = {"id": exam_id, "revision": 1, "title": "ĐỀ RIÊNG A", "questions": []}
        first.put(
            "/api/kv", json={"key": "state", "value": {"exams": [exam], "prefs": []}}
        ).raise_for_status()
        assert second.get("/api/kv?key=state").json()["value"] is None
        text = base64.b64encode("NGUỒN RIÊNG A".encode()).decode()
        first.put(
            "/api/kv", json={"key": "file:known", "value": "data:text/plain;base64," + text}
        ).raise_for_status()
        assert second.get("/api/kv?key=file:known").json()["value"] is None
        assert second.get("/api/source-file/known").status_code == 404
        assert (
            second.post("/api/extract", json={"fileId": "known", "name": "a.txt"}).status_code
            != 200
        )
        output = first.post(
            "/api/save-export",
            json={"type": "exam", "format": "html", "exam": exam, "allowDraft": True},
        )
        output.raise_for_status()
        url = output.json()["url"]
        assert "ĐỀ RIÊNG A" in first.get(url).text
        assert second.get(url).status_code == 404
        assert second.get(f"/api/exams/{exam_id}/proposals/latest").status_code == 404
        assert second.post("/api/config", json={}).status_code == 403
        assert (
            second.post("/api/account/invitations", json={"email": "a@example.test"}).status_code
            == 403
        )
        assert first.get("/api/account").json()["admin"]
        assert not second.get("/api/account").json()["admin"]
        assert not second.get("/api/status").json()["admin"]
        assert (
            second.get("/api/account").json()["workspace"]
            != first.get("/api/account").json()["workspace"]
        )
        invitation = first.post("/api/account/invitations", json={"email": "new@example.test"})
        invitation.raise_for_status()
        assert "inviteCode" in invitation.json()
        assert accounts.administrator()["id"] == admin["id"]
        assert (tmp_path / "users" / member["id"] / "workspace.sqlite").exists()


def test_workspace_persists_and_conflict_is_per_user(team, tmp_path):
    app, _, admin, member, _ = team
    with signed_client(app, admin["email"]) as first, signed_client(app, member["email"]) as second:
        first.put(
            "/api/kv",
            headers={"If-Match": "0"},
            json={"key": "state", "value": {"exams": [], "prefs": []}},
        ).raise_for_status()
        response = first.put(
            "/api/kv",
            headers={"If-Match": "0"},
            json={"key": "state", "value": {"exams": [{"id": "bad"}], "prefs": []}},
        )
        assert response.status_code == 409
        second.put(
            "/api/kv",
            headers={"If-Match": "0"},
            json={"key": "state", "value": {"exams": [], "prefs": []}},
        ).raise_for_status()
        cookie = first.cookies.get(COOKIE)
    reloaded = create_team_app(tmp_path, clock=lambda: 1000)
    with TestClient(reloaded, headers=ORIGIN, cookies={COOKIE: cookie}) as client:
        assert client.get("/api/kv?key=state").json() == {
            "value": {"exams": [], "prefs": []},
            "revision": 1,
        }
    with sqlite3.connect(tmp_path / "accounts.sqlite") as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 2


def test_operator_password_reset_revokes_all_sessions(team):
    _, accounts, admin, *_ = team
    first, second = accounts.new_session(admin["id"]), accounts.new_session(admin["id"])
    replacement = "mat-khau-thay-moi-de-test"
    accounts.reset_password(admin["email"], replacement)
    assert accounts.user(first) is None and accounts.user(second) is None
    with pytest.raises(HTTPException):
        accounts.login(admin["email"], PASSWORD, "127.0.0.1")
    assert accounts.login(admin["email"], replacement, "127.0.0.1")["id"] == admin["id"]


def test_password_reset_during_login_cannot_issue_old_password_session(team, monkeypatch):
    from mach_backend import team_accounts

    _, accounts, admin, *_ = team
    original, reset = team_accounts.password_hash, [False]

    def racing_hash(password, salt):
        result = original(password, salt)
        if not reset[0]:
            reset[0] = True
            accounts.reset_password(admin["email"], "mat-khau-da-doi-trong-luc-login")
        return result

    monkeypatch.setattr(team_accounts, "password_hash", racing_hash)
    with pytest.raises(HTTPException, match="Mật khẩu đã đổi"):
        accounts.login(admin["email"], PASSWORD, "127.0.0.1", with_session=True)
    with accounts.connect() as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


def test_member_uses_shared_settings_without_seeing_or_persisting_key(team, tmp_path):
    app, _, admin, member, _ = team
    with signed_client(app, admin["email"]) as first, signed_client(app, member["email"]) as second:
        first.get("/api/status").raise_for_status()
        master = app.state.workspaces[admin["id"]].state.provider
        master.gemini_key, master.gemini_free_tier, master.provider_name = (
            "fixture-key-no-network",
            True,
            "gemini",
        )
        config = second.get("/api/config")
        config.raise_for_status()
        assert config.json()["gemini"]["hasKey"]
        assert config.json()["routes"]["generate"] == "gemini"
        assert "fixture-key-no-network" not in config.text
        assert not (tmp_path / "users" / member["id"] / "ai-connection.dpapi").exists()
        master.gemini_key, master.gemini_free_tier, master.provider_name = "", False, "ollama"
        assert not second.get("/api/config").json()["gemini"]["hasKey"]
        app.state.workspaces[admin["id"]].state.ai_busy = lambda: True
        blocked = second.post("/api/ai/exam-plan", json={})
        assert blocked.status_code == 409 and blocked.json()["code"] == "job_limit"
        assert (
            second.post(
                "/api/assistant/chat", json={"text": "Không gọi AI thật", "consent": True}
            ).status_code
            == 409
        )


def test_matrix_and_feedback_use_actual_account_owner(team):
    app, _, admin, *_ = team
    with signed_client(app, admin["email"]) as client:
        exam_id = str(uuid4())
        value = {
            "exams": [
                {
                    "id": exam_id,
                    "revision": 1,
                    "subject": "Toán",
                    "grade": 9,
                    "matrixConfirmed": True,
                    "matrix": [{"topic": "Vận tốc", "targets": [1, 0, 0]}],
                    "questions": [],
                }
            ],
            "prefs": [],
        }
        client.put("/api/kv", json={"key": "state", "value": value}).raise_for_status()
        client.post(
            f"/api/exams/{exam_id}/matrix/approve",
            json={
                "baseRevision": 1,
                "sourceName": "Nguồn tự viết",
                "sourceText": "Vận tốc bằng quãng đường chia thời gian, đơn vị km/h.",
            },
        ).raise_for_status()
        store = app.state.workspaces[admin["id"]].state.store
        assert store.owner == admin["id"] and store.sources(exam_id)[0].ownerId == admin["id"]
