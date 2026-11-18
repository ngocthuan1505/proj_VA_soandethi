"""Chỉ kiểm cấu hình local bằng khóa giả; không gọi Google."""

from fastapi.testclient import TestClient

from mach_backend.gemini_model import GEMINI_MODEL
from mach_backend.local_workspace import create_app

KEY = "fake-secret-only-for-test"


def test_key_is_ram_only_and_updates_are_atomic(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        initial = client.get("/api/config").json()
        assert initial["routes"]["generate"] == "ollama"
        config = {"saveLocally": False, "routes": {"generate": "gemini"}, "gemini": {"key": KEY}}
        assert client.post("/api/config", json=config).status_code == 400
        assert not client.get("/api/config").json()["gemini"]["hasKey"]
        config["gemini"]["freeTierConfirmed"] = True
        saved = client.post("/api/config", json=config)
        assert saved.status_code == 200
        assert KEY not in saved.text
        assert saved.json()["gemini"]["hasKey"]
        status = client.get("/api/status").json()
        assert status["model"] == GEMINI_MODEL
        assert status["aiProvider"] == "gemini"
        assert client.post("/api/config", json={"gemini": {"key": ""}}).status_code == 200
        for body in (
            {"gemini": {"url": "https://other-host.invalid"}},
            {"gemini": {"model": "another-model"}},
            {"gemini": {"key": [KEY]}},
            {"routes": {"generate": "unknown"}},
            {"routes": {"generate": ["gemini"]}},
            {"ollama": {"model": 123}},
            {"gemini": []},
            [],
        ):
            response = client.post("/api/config", json=body)
            assert 400 <= response.status_code < 500
            assert KEY not in response.text
            assert client.get("/api/config").json() == saved.json()
        response = client.post("/api/config", content=KEY)
        assert response.status_code == 400
        assert KEY not in response.text
        assert client.post("/api/config", json={"gemini": {"clearKey": True}}).status_code == 400
        switched = client.post("/api/config", json={"gemini": {"model": "gemini-3.6-flash"}})
        assert switched.status_code == 200
        assert client.get("/api/status").json()["model"] == "gemini-3.6-flash"
        assert switched.json()["gemini"]["hasKey"]
        cleared = client.post(
            "/api/config",
            json={"routes": {"generate": "ollama"}, "gemini": {"clearKey": True}},
        )
        assert cleared.status_code == 200
        assert not cleared.json()["gemini"]["hasKey"]
    assert all(KEY.encode() not in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    with TestClient(create_app(tmp_path)) as restarted:
        assert not restarted.get("/api/config").json()["gemini"]["hasKey"]


def test_cross_origin_cannot_store_a_key(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post("/api/config", json={"gemini": {"key": KEY}}).status_code == 403


def test_hydrogen_can_be_selected_without_changing_keys_or_default(tmp_path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        assert client.get("/api/config").json()["gemini"]["model"] == GEMINI_MODEL
        response = client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "routes": {"generate": "gemini", "check": "gemini"},
                "gemini": {
                    "key": KEY,
                    "freeTierConfirmed": True,
                    "model": "gemini-4-hydrogen",
                    "checkModel": "gemini-4-hydrogen",
                },
            },
        )
        assert response.status_code == 200
        assert KEY not in response.text
        status = client.get("/api/status").json()
        assert status["model"] == status["reviewer"]["model"] == "gemini-4-hydrogen"


def test_generation_and_check_models_and_budget_are_independent_and_atomic(tmp_path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        configured = client.post(
            "/api/config",
            json={
                "routes": {"generate": "gemini", "check": "gemini"},
                "gemini": {
                    "key": KEY,
                    "freeTierConfirmed": True,
                    "model": "gemini-3.8-flash",
                    "checkModel": GEMINI_MODEL,
                },
                "runBudget": {"maxModelCalls": 16, "timeoutSeconds": 300},
            },
        )
        assert configured.status_code == 200
        status = client.get("/api/status").json()
        assert status["model"] == "gemini-3.8-flash"
        assert status["reviewer"] == {"provider": "gemini", "model": GEMINI_MODEL}
        assert status["runBudget"] == {"maxModelCalls": 16, "timeoutSeconds": 300}
        for bad in (
            {"runBudget": {"maxModelCalls": 65}},
            {"routes": {"check": []}},
            {"gemini": {"checkModel": "other"}},
        ):
            assert client.post("/api/config", json=bad).status_code == 400
            assert client.get("/api/config").json() == configured.json()
        client.post(
            "/api/config", json={"gemini": {"model": "gemini-3.8-flash"}}
        ).raise_for_status()
        assert client.get("/api/status").json()["reviewer"]["model"] == GEMINI_MODEL


def test_backup_key_is_private_atomic_and_changes_consent_fingerprint(tmp_path):
    backup = "fake-backup-only-for-config-test"
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        original = client.post(
            "/api/config",
            json={
                "saveLocally": False,
                "routes": {"generate": "gemini"},
                "gemini": {"key": KEY, "freeTierConfirmed": True},
            },
        ).json()
        configured = client.post("/api/config", json={"gemini": {"backupKey": backup}})
        assert configured.status_code == 200
        assert configured.json()["gemini"]["hasBackupKey"]
        assert configured.json()["fingerprint"] != original["fingerprint"]
        assert KEY not in configured.text and backup not in configured.text
        for body in ({"backupKey": KEY}, {"backupKey": [backup]}, {"clearKey": True}):
            response = client.post("/api/config", json={"gemini": body})
            assert 400 <= response.status_code < 500
            assert client.get("/api/config").json() == configured.json()
        kept = client.post("/api/config", json={"gemini": {"backupKey": ""}})
        assert kept.json() == configured.json()
        cleared = client.post("/api/config", json={"gemini": {"clearBackupKey": True}})
        assert cleared.json() == original
