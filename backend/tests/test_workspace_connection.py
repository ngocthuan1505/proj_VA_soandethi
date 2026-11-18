import sqlite3
from contextlib import closing
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mach_backend.local_workspace import create_app
from mach_backend.workspace_store import WorkspaceStore


def test_connection_closes_and_failed_transaction_rolls_back(tmp_path):
    store = WorkspaceStore(tmp_path)
    with store.connect() as connection:
        store.put("test", "ban-dau", db=connection)
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with pytest.raises(ValueError):
        with store.connect() as connection:
            store.put("test", "chua-luu", db=connection)
            raise ValueError("Dừng giao dịch")
    assert store.get("test")["value"] == "ban-dau"
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_linked_data_and_question_revision_roll_back_on_failed_workspace_write(tmp_path):
    app = create_app(tmp_path)
    path = "/api/kv"
    question_id = str(uuid4())
    state = {
        "exams": [
            {
                "id": str(uuid4()),
                "data": [{"label": "Khu vực B", "value": 240}],
                "questions": [{"id": question_id, "v": 1, "dataLinked": True}],
            }
        ],
        "prefs": [],
    }
    revised = deepcopy(state)
    revised["exams"][0]["data"][0]["value"] = 300
    revised["exams"][0]["questions"][0]["v"] = 2
    with (
        TestClient(
            app, raise_server_exceptions=False, headers={"Origin": "http://testserver"}
        ) as client,
        closing(sqlite3.connect(tmp_path / "workspace.sqlite")) as db,
    ):
        client.put(path, json={"key": "state", "value": state}).raise_for_status()
        before = client.get(path, params={"key": "state"}).json()
        db.execute("""
            CREATE TRIGGER fail_workspace AFTER UPDATE ON kv
            WHEN new.key = 'state'
            BEGIN
                SELECT RAISE(ABORT, 'Loi ghi thu nghiem');
            END
        """)
        req = {
            "headers": {"If-Match": str(before["revision"])},
            "json": {"key": "state", "value": revised},
        }
        assert client.put(path, **req).status_code == 500
        assert client.get(path, params={"key": "state"}).json() == before

        db.execute("DROP TRIGGER fail_workspace")
        client.put(path, **req).raise_for_status()
        assert client.get(path, params={"key": "state"}).json() == {
            "revision": before["revision"] + 1,
            "value": revised,
        }
