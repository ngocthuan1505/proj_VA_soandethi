"""Khôi phục xuyên API trên kho thử; không dùng dữ liệu hoặc khóa thật."""

import base64
import io
import json
from uuid import uuid4

import pytest
from PIL import Image
from test_local_workspace import workspace  # noqa: F401


def backup_fixture():
    question = {
        "id": str(uuid4()),
        "v": 3,
        "stem": r"Tính $\sqrt{9}$ và $\frac{1}{2}$.",
        "type": "mcq",
        "level": 0,
        "options": ["3", "2", "1", "0"],
        "answer": 0,
        "explanation": "Căn bậc hai số học là 3.",
        "points": 2.5,
        "richDoc": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "attrs": {"id": "p-giữ-id"},
                    "content": [
                        {"type": "text", "text": "Nội dung đậm", "marks": [{"type": "bold"}]}
                    ],
                }
            ],
        },
    }
    exam = {
        "id": str(uuid4()),
        "revision": 7,
        "title": "Đề khôi phục tự viết",
        "subject": "Toán",
        "grade": "9",
        "questions": [question],
        "docs": [],
        "matrix": [{"topic": "Căn", "targets": [1, 0, 0, 0]}],
        "history": [],
        "undo": [{"label": "Gỡ ảnh", "state": {"fileId": "image-history"}}],
        "redo": [],
        "chat": [],
        "data": [],
        "quote": {"text": "", "versions": []},
    }
    image = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, "PNG")
    return {
        "format": "tro-ly-soan-de",
        "version": 1,
        "state": {"current": exam["id"], "exams": [exam], "prefs": [{"text": "Giữ tiếng Việt"}]},
        "files": {
            "image-history": "data:image/png;base64," + base64.b64encode(image.getvalue()).decode()
        },
    }


def test_restore_legacy_generic_mime_uses_referenced_filename(workspace):  # noqa: F811
    client, _, _ = workspace
    backup = backup_fixture()
    exam = backup["state"]["exams"][0]
    exam["history"] = [{"state": {"docs": [{"fileId": "image-history", "name": "scan.png"}]}}]
    png = backup["files"]["image-history"]
    backup["files"]["image-history"] = png.replace("image/png", "application/octet-stream")
    preview = client.post("/api/workspace/restore/preview", json=backup)
    assert preview.status_code == 200, preview.text
    restored = client.post(
        "/api/workspace/restore", json=backup, headers={"If-Match": str(preview.json()["revision"])}
    )
    assert restored.status_code == 200, restored.text
    assert client.get("/api/kv?key=file:image-history").json()["value"] == png
    assert client.get("/api/kv?key=state").json()["value"] == backup["state"]


@pytest.mark.parametrize("names", [[], ["scan.jpg"], ["scan.png", "scan.pdf"]])
def test_generic_mime_rejects_missing_mismatched_or_conflicting_names(workspace, names):  # noqa: F811
    client, _, _ = workspace
    backup = backup_fixture()
    backup["state"]["exams"][0]["docs"] = [
        {"fileId": "image-history", "name": name} for name in names
    ]
    backup["files"]["image-history"] = backup["files"]["image-history"].replace("image/png", "")
    before = client.get("/api/kv?key=state").json()
    rejected = client.post(
        "/api/workspace/restore", json=backup, headers={"If-Match": str(before["revision"])}
    )
    assert rejected.status_code == 409, rejected.text
    assert client.get("/api/kv?key=state").json() == before


def test_preview_apply_roundtrip_keeps_ids_rich_history_and_files(workspace):  # noqa: F811
    client, _, _ = workspace
    backup = backup_fixture()
    before = client.get("/api/kv?key=state").json()
    preview = client.post("/api/workspace/restore/preview", json=backup)
    assert preview.status_code == 200, preview.text
    assert preview.json() == {"revision": before["revision"], "exams": 1, "files": 1, "prefs": 1}
    assert client.get("/api/kv?key=state").json() == before
    response = client.post(
        "/api/workspace/restore", json=backup, headers={"If-Match": str(before["revision"])}
    )
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == before["revision"] + 1
    assert client.get("/api/kv?key=state").json()["value"] == backup["state"]
    assert (
        client.get("/api/kv?key=file:image-history").json()["value"]
        == backup["files"]["image-history"]
    )
    assert (
        client.post(
            "/api/workspace/restore", json=backup, headers={"If-Match": str(before["revision"])}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing-history-file",
        "broken-image",
        "broken-json",
        "duplicate-question",
        "wrong-answer",
        "wrong-format",
    ],
)
def test_invalid_backup_never_replaces_current_workspace(workspace, case):  # noqa: F811
    client, _, _ = workspace
    before = client.get("/api/kv?key=state").json()
    backup = backup_fixture()
    if case == "missing-history-file":
        backup["files"].clear()
    elif case == "broken-image":
        backup["files"]["image-history"] = "data:image/png;base64,aGVsbG8="
    elif case == "duplicate-question":
        backup["state"]["exams"][0]["questions"] *= 2
    elif case == "wrong-answer":
        backup["state"]["exams"][0]["questions"][0]["answer"] = "không phải chỉ số"
    elif case == "wrong-format":
        backup["format"] = "không phải bản sao app"
    arguments = {"content": b'{"state":'} if case == "broken-json" else {"json": backup}
    for path in ["/preview", ""]:
        response = client.post(
            "/api/workspace/restore" + path,
            headers={"If-Match": str(before["revision"])},
            **arguments,
        )
        assert response.status_code == 409, response.text
    assert client.get("/api/kv?key=state").json() == before


def test_restore_requires_preview_revision_and_refuses_busy_ai(workspace):  # noqa: F811
    client, _, _ = workspace
    backup = backup_fixture()
    assert client.post("/api/workspace/restore", json=backup).status_code == 400
    store = client.app.state.store
    before = store.get("state")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(type(client.app.state.runner), "active", property(lambda _: True))
        response = client.post(
            "/api/workspace/restore", json=backup, headers={"If-Match": str(before["revision"])}
        )
        assert response.status_code == 409 and response.json()["code"] == "job_limit"
    assert store.get("state") == before


def test_restore_body_limits_are_specific_and_origin_still_checked(workspace, monkeypatch):  # noqa: F811
    from mach_backend import workspace_backup

    client, _, _ = workspace
    backup = backup_fixture()
    # Không cấp phát40MB trong test: kiểm middleware nhận đúng hạn mức qua header.
    assert (
        client.post(
            "/api/workspace/restore/preview",
            json=backup,
            headers={"Content-Length": str(40 * 1024 * 1024)},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/workspace/restore/preview",
            json=backup,
            headers={"Content-Length": str(151 * 1024 * 1024)},
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/api/workspace/restore/preview",
            json=backup,
            headers={"Origin": "https://other.example"},
        ).status_code
        == 403
    )
    monkeypatch.setattr(workspace_backup, "MAX_BACKUP", 100)
    assert client.post("/api/workspace/restore/preview", json=backup).status_code == 413


def test_failed_file_write_rolls_back_state_and_ai_records(workspace, monkeypatch):  # noqa: F811
    from mach_backend.workspace_backup import restore

    client, _, _ = workspace
    store = client.app.state.store
    before = store.get("state")
    original = store.put

    def fail_file(key, *args, **kwargs):
        if key.startswith("file:"):
            raise OSError("Lỗi ghi tệp giả lập")
        return original(key, *args, **kwargs)

    monkeypatch.setattr(store, "put", fail_file)
    with pytest.raises(OSError):
        restore(store, backup_fixture(), before["revision"])
    assert store.get("state") == before
    assert store.get("file:image-history")["value"] is None


def test_restore_invalidates_old_ai_pending_without_changing_connection(workspace):  # noqa: F811
    client, _, _ = workspace
    store = client.app.state.store
    job_id = str(uuid4())
    store.put("matrix-latest:old", {"jobId": job_id})
    store.put("connection-untouched", {"value": "synthetic-configuration"})
    with store.connect() as db:
        db.execute(
            "INSERT INTO matrix_pending(job_id,owner,payload) VALUES(?,?,?)",
            (job_id, "local", "{}"),
        )
        db.execute("INSERT INTO matrix_trace(job_id,payload) VALUES(?,?)", (job_id, "{}"))
    revision = store.get("state")["revision"]
    response = client.post(
        "/api/workspace/restore", json=backup_fixture(), headers={"If-Match": str(revision)}
    )
    assert response.status_code == 200, response.text
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM matrix_pending").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM matrix_trace").fetchone()[0] == 0
    assert store.get("matrix-latest:old")["value"] is None
    assert store.get("connection-untouched")["value"] == {"value": "synthetic-configuration"}


@pytest.mark.parametrize("token", ["NaN", "1e999"])
def test_nonstandard_json_number_is_rejected_before_commit(workspace, token):  # noqa: F811
    client, _, _ = workspace
    before = client.get("/api/kv?key=state").json()
    backup = backup_fixture()
    backup["state"]["exams"][0]["questions"][0]["points"] = float("nan")
    response = client.post(
        "/api/workspace/restore",
        content=json.dumps(backup).replace("NaN", token),
        headers={"If-Match": str(before["revision"])},
    )
    assert response.status_code == 409 and response.json()["code"] == "invalid_backup"
    assert client.get("/api/kv?key=state").json() == before
