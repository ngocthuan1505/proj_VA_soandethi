"""Chỉ dùng khóa giả để kiểm DPAPI thật trên Windows; không gọi AI."""

import os

import pytest
from fastapi.testclient import TestClient

from mach_backend.local_credentials import LocalConnectionStore
from mach_backend.local_workspace import create_app

KEY = "fake-credential-for-local-storage-test"
BACKUP = "fake-backup-for-encrypted-storage-test"


@pytest.mark.skipif(os.name != "nt", reason="DPAPI là API Windows, không giả làm mã hóa trên Linux")
def test_dpapi_file_is_not_plaintext_and_survives_new_app(tmp_path):
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        saved = client.post(
            "/api/config",
            json={
                "saveLocally": True,
                "routes": {"generate": "gemini", "check": "gemini"},
                "gemini": {
                    "key": KEY,
                    "backupKey": BACKUP,
                    "freeTierConfirmed": True,
                    "model": "gemini-3.8-flash",
                    "checkModel": "gemini-3.6-flash",
                },
                "runBudget": {"maxModelCalls": 12, "timeoutSeconds": 300},
            },
        )
        assert saved.status_code == 200, saved.text
        assert KEY not in saved.text and saved.json()["persistence"]["saved"]
        assert BACKUP not in saved.text and saved.json()["gemini"]["hasBackupKey"]
    store = LocalConnectionStore(tmp_path)
    assert KEY.encode() not in store.path.read_bytes()
    assert BACKUP.encode() not in store.path.read_bytes()
    assert store.load()["gemini"]["key"] == KEY
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as restarted:
        config = restarted.get("/api/config").json()
        assert config["gemini"]["hasKey"] and KEY not in str(config)
        assert config["gemini"]["hasBackupKey"] and BACKUP not in str(config)
        assert config["gemini"]["checkModel"] == "gemini-3.6-flash"
        assert config["runBudget"]["maxModelCalls"] == 12
        assert restarted.get("/api/status").json()["model"] == "gemini-3.8-flash"
        restarted.post(
            "/api/config",
            json={
                "saveLocally": False,
                "routes": {"generate": "ollama", "check": "ollama"},
                "gemini": {"clearKey": True, "clearBackupKey": True},
            },
        ).raise_for_status()
    assert not store.path.exists()
    with TestClient(create_app(tmp_path)) as cleared:
        assert not cleared.get("/api/config").json()["gemini"]["hasKey"]


def test_encryption_failure_is_atomic_and_never_falls_back_to_plaintext(tmp_path, monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("Lỗi giả lập không chứa khóa.")

    monkeypatch.setattr("mach_backend.local_credentials.protect", fail)
    with TestClient(create_app(tmp_path), headers={"Origin": "http://testserver"}) as client:
        before = client.get("/api/config").json()
        response = client.post(
            "/api/config",
            json={
                "saveLocally": True,
                "gemini": {"key": KEY, "freeTierConfirmed": True},
                "routes": {"generate": "gemini"},
            },
        )
        assert response.status_code == 503 and KEY not in response.text
        assert client.get("/api/config").json() == before
        assert not LocalConnectionStore(tmp_path).path.exists()


def test_corrupt_credential_file_is_preserved_and_does_not_crash_app(tmp_path):
    store = LocalConnectionStore(tmp_path)
    store.path.write_bytes(b"invalid-encrypted-file")
    with TestClient(create_app(tmp_path)) as client:
        config = client.get("/api/config").json()
        assert not config["gemini"]["hasKey"] and config["persistence"]["warning"]
        assert client.get("/ai-connection.dpapi").status_code == 404
    assert store.path.read_bytes() == b"invalid-encrypted-file"
