import sqlite3

import pytest

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
