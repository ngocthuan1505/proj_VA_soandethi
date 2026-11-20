"""Trình quay demo chỉ đọc; không nhầm log model với thao tác duyệt của người dùng."""

import importlib.util
import io
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_local_workspace import AgentModelFixture, generate, workspace  # noqa: F401

from mach_backend.local_workspace import create_app

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/theo-doi-poc.py"
spec = importlib.util.spec_from_file_location("poc_observer", SCRIPT)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


def test_follow_keeps_reading_after_clock_passes_deadline(monkeypatch):
    class Stream(io.StringIO):
        def reconfigure(self, **_):
            pass

    calls = []

    class Watch:
        def __init__(self, *_, **__):
            self.exported_path = None

        def poll(self):
            calls.append(1)
            if len(calls) == 2:
                raise KeyboardInterrupt

    monkeypatch.setattr(observer.sys, "stdout", Stream())
    monkeypatch.setattr(observer.sys, "stderr", Stream())
    monkeypatch.setattr(
        observer.argparse.ArgumentParser,
        "parse_args",
        lambda _: SimpleNamespace(
            port=4182,
            exam_id=None,
            job_id=None,
            once=False,
            seconds=1,
            follow=True,
            new_run=False,
            output=None,
            demo=False,
        ),
    )
    clock = iter([0, 10000, 10001])
    monkeypatch.setattr(
        observer, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None)
    )
    monkeypatch.setattr(
        observer, "Reader", lambda _: SimpleNamespace(get=lambda _: {"localPoC": True})
    )
    monkeypatch.setattr(observer, "Watcher", Watch)
    with pytest.raises(KeyboardInterrupt):
        observer.main()
    assert len(calls) == 2


def test_observer_shows_actual_model_switch_without_provider_message_or_key():
    result = observer.trace_summary(
        {
            "event": "provider_model_switch",
            "fromModel": "gemini-3.6-flash",
            "toModel": "gemini-3.8-flash",
            "httpStatus": 429,
            "key": "fake-secret",
            "message": "private-content",
        }
    )
    assert result == {
        "event": "provider_model_switch",
        "fromModel": "gemini-3.6-flash",
        "toModel": "gemini-3.8-flash",
        "httpStatus": 429,
    }


@pytest.mark.parametrize("tags", [None, {"models": []}])
def test_launcher_does_not_require_local_ai_to_open_gemini_app(tmp_path, monkeypatch, tags):
    location = SCRIPT.parent / "mo-app-local.py"
    spec = importlib.util.spec_from_file_location("demo_launcher", location)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    calls = []
    opened = []
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher, "read", lambda url: tags if url.endswith("/api/tags") else None)
    monkeypatch.setattr(launcher.shutil, "which", lambda _: None)
    monkeypatch.setattr(launcher, "start", lambda args, name, env: calls.append(name))
    monkeypatch.setattr(launcher, "wait", lambda url, process: {"localPoC": True})
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    launcher.main()
    assert calls == ["app"] and opened == ["http://127.0.0.1:4182?ui=demo-20261117-2"]


def test_reader_only_gets_loopback_and_does_not_follow_redirects():
    with pytest.raises(ValueError):
        observer.Reader(443)
    reader = observer.Reader(4184)
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self):
            return b'{"fixture":true}'

    class Opener:
        def open(self, request, **_):
            requests.append(request)
            return Response()

    reader.opener = Opener()
    assert reader.get("/api/status") == {"fixture": True}
    assert requests[0].get_method() == "GET"
    assert requests[0].full_url == "http://127.0.0.1:4184/api/status"
    assert observer.NoRedirect().redirect_request(None, None, 302, None, None, "https://x") is None


def test_trace_hides_payloads_and_unknown_text():
    row = {
        "event": "tool_call",
        "tool": "check_exam",
        "toolCallNumber": 1,
        "sourceText": "riêng tư",
        "apiKey": "bí mật",
        "reason": "bí mật",
        "errorCode": "bí mật",
        "seconds": "bí mật",
        "purpose": "bí mật",
    }
    assert observer.trace_summary(row) == {
        "event": "tool_call",
        "tool": "check_exam",
        "toolCallNumber": 1,
    }


def test_trace_preserves_actual_check_codes_and_durations_without_free_text():
    row = {
        "event": "check_report",
        "toolName": "solve_blind",
        "status": "FAIL",
        "durationMs": 200,
        "elapsedSeconds": 1.25,
        "findings": [
            {"code": "answer_disagreement", "message": "riêng tư"},
            {"code": "khóa riêng tư"},
        ],
    }
    assert observer.trace_summary(row) == {
        "event": "check_report",
        "toolName": "solve_blind",
        "status": "FAIL",
        "durationMs": 200,
        "elapsedSeconds": 1.25,
        "findingsCodes": ["answer_disagreement"],
    }


def test_direct_help_works_with_cp1252_stdout():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        check=False,
    )
    assert result.returncode == 0
    assert "không tạo tác vụ" in result.stdout.decode("utf-8")
    assert not result.stderr


def test_observer_before_job_and_after_review_confirm_discard_and_undo():
    exam_id, job_id = str(uuid4()), str(uuid4())
    exam = {"id": exam_id, "revision": 1, "questions": [], "history": [], "undo": [], "redo": []}
    state = {"current": exam_id, "exams": [exam]}
    latest = None
    calls, lines = [], []

    class Reader:
        def get(self, path):
            calls.append(path)
            if path == "/api/kv?key=state":
                return {"value": deepcopy(state)}
            if path.endswith("/latest"):
                return deepcopy(latest)
            if path.endswith("/status"):
                return {"status": "complete"}
            if path.endswith("/trace"):
                return [{"event": "run_end", "status": "ready_for_teacher_review", "saved": False}]
            pytest.fail("Đường dẫn ngoài phạm vi chỉ đọc")

    watcher = observer.Watcher(Reader(), lambda kind, value: lines.append((kind, deepcopy(value))))
    watcher.poll()
    assert lines[-1][1]["jobId"] is None
    latest = {
        "jobId": job_id,
        "discarded": False,
        "proposal": {"questions": [{"level": 0}]},
        "reviews": {"0": {"observed": 0, "contentOk": False, "reviewer": "không xuất"}},
    }
    watcher.poll()
    assert lines[-1][1]["unresolvedReviewCount"] == 1
    assert not lines[-1][1]["savedHistoryObserved"]
    latest["reviews"]["0"]["contentOk"] = True
    watcher.poll()
    assert lines[-1][1]["unresolvedReviewCount"] == 0
    exam.update(revision=2, questions=[{"id": str(uuid4())}], history=[{"id": job_id}], undo=[{}])
    watcher.poll()
    assert lines[-1][1]["savedHistoryObserved"] and lines[-1][1]["questionCount"] == 1
    latest["discarded"] = True
    watcher.poll()
    assert lines[-1][1]["discarded"]
    exam.update(revision=3, questions=[], undo=[], redo=[{}])
    state["current"] = str(uuid4())
    watcher.poll()
    assert lines[-1][1]["questionCount"] == 0 and lines[-1][1]["redoCount"] == 1
    assert watcher.exam_id == exam_id and watcher.job_id == job_id
    latest["jobId"] = str(uuid4())
    watcher.poll()
    assert "discarded" not in lines[-1][1]
    traces = [value for kind, value in lines if kind == "APP_TRACE"]
    assert len(traces) == 1 and traces[0]["saved"] is False
    assert all("config" not in path and "generate" not in path for path in calls)


def test_reject_invalid_job_scope_and_chrome_launcher_is_normal_window():
    with pytest.raises(ValueError):
        observer.Watcher(None, None, job_id=str(uuid4()))
    with pytest.raises(ValueError):
        observer.Watcher(None, None, exam_id="https://example.com")
    launcher = SCRIPT.with_name("xem-demo-poc.cmd").read_text(encoding="utf-8")
    assert "--new-window" in launcher and "--app" not in launcher
    assert "mo-app-local.py" not in launcher


def test_observer_follows_new_demo_exam_before_first_job_then_pins():
    first, second = str(uuid4()), str(uuid4())
    state = {"current": first, "exams": [{"id": first}, {"id": second}]}

    class Reader:
        def get(self, path):
            if path == "/api/kv?key=state":
                return {"value": state}
            if path.endswith("/latest"):
                return None
            raise AssertionError(path)

    watcher = observer.Watcher(Reader(), lambda *_: None)
    watcher.poll()
    assert watcher.exam_id == first
    state["current"] = second
    watcher.poll()
    assert watcher.exam_id == second
    fixed = observer.Watcher(Reader(), lambda *_: None, exam_id=first)
    fixed.poll()
    assert fixed.exam_id == first


@pytest.mark.parametrize("terminal", ["complete", "failed", "cancelled"])
def test_fresh_demo_ignores_all_old_jobs_and_exports_only_new_run(tmp_path, terminal):
    first, second, new_exam = (str(uuid4()) for _ in range(3))
    old_a, old_b, new_job = (str(uuid4()) for _ in range(3))
    state = {"current": first, "exams": [{"id": first}, {"id": second}]}
    jobs = {first: {"jobId": old_a}, second: {"jobId": old_b}}
    status = {"jobId": new_job, "status": "running", "saved": False}
    rows = [{"event": "run_start", "mode": "fixture"}]
    paths, lines = [], []

    class Reader:
        def get(self, path):
            paths.append(path)
            if path == "/api/kv?key=state":
                return deepcopy({"value": state})
            if path.endswith("/latest"):
                return deepcopy(jobs.get(path.split("/")[3]))
            assert new_job in path, "Không được đọc trạng thái, trace hoặc báo cáo của lượt cũ"
            if path.endswith("/status"):
                return deepcopy(status)
            if path.endswith("/trace"):
                return deepcopy(rows)
            if path.endswith("/report"):
                return {"jobId": new_job, "checks": []}
            if path.endswith("/audit"):
                return {"traceVerified": terminal == "complete"}
            pytest.fail(path)

    watcher = observer.Watcher(
        Reader(),
        lambda kind, value: lines.append((kind, deepcopy(value))),
        new_run=True,
        output_root=tmp_path,
    )
    watcher.fixture = True
    watcher.arm_new_run()
    watcher.poll()
    state["current"] = second
    watcher.poll()
    assert [kind for kind, _ in lines] == ["CHO_LUOT_MOI"]
    assert not list(tmp_path.iterdir())
    # Tạo đề mới trên web rồi sinh: ghim đúng lượt đó, kể cả khi đổi đề đang xem.
    state["exams"].append({"id": new_exam})
    state["current"] = new_exam
    jobs[new_exam] = {"jobId": new_job, "input": {"sourceText": "Nguồn tự viết"}}
    watcher.poll()
    assert [value["index"] for kind, value in lines if kind == "APP_TRACE"] == [1]
    assert not list(tmp_path.iterdir())
    rows.append({"event": "tool_call", "tool": "check_exam"})
    watcher.poll()
    assert [value["index"] for kind, value in lines if kind == "APP_TRACE"] == [1, 2]
    state["current"] = first
    status["status"] = terminal
    rows.append(
        {
            "event": "run_end",
            "status": "ready_for_teacher_review" if terminal == "complete" else terminal,
        }
    )
    watcher.poll()
    folder = watcher.exported_path
    assert folder.parent == tmp_path and new_job in folder.name
    assert len(list(folder.glob("*.json"))) == 6
    assert json_read(folder / "trace.json") == rows
    assert json_read(folder / "result.json") == status
    assert json_read(folder / "input.json") == {"sourceText": "Nguồn tự viết"}
    session = json_read(folder / "session.json")
    assert session["fixture"] and session["jobId"] == new_job
    assert session["armedAt"] <= session["exportedAt"]
    assert lines[-2][0] == "DA_LUU_JSON"
    assert not any("config" in path or "generate" in path for path in paths)
    # Chỉ xuất một lần; không ghi đè khi giáo viên lưu đề sau đó.
    status["saved"] = True
    watcher.poll()
    assert json_read(folder / "result.json")["saved"] is False
    assert len([kind for kind, _ in lines if kind == "DA_LUU_JSON"]) == 1


def json_read(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def test_fresh_launcher_requests_new_run_and_has_visible_error():
    launcher = (SCRIPT.parents[1] / "MO_APP_VA_LOG.cmd").read_text(encoding="utf-8")
    assert "--new-run" in launcher and "--follow" in launcher
    assert "echo CHO" not in launcher and "echo Chi theo doi" not in launcher
    assert "if errorlevel 1 (\n  pause\n  exit /b 1\n)" in launcher


@pytest.mark.parametrize("fixture", [False, True])
def test_fresh_cmd_prints_one_ready_line_without_verbose_intro(monkeypatch, fixture):
    class Stream(io.StringIO):
        def reconfigure(self, **_):
            pass

    output = Stream()
    monkeypatch.setattr(observer.sys, "stdout", output)
    monkeypatch.setattr(observer.sys, "stderr", Stream())
    monkeypatch.setattr(observer.sys, "argv", [str(SCRIPT), "--new-run", "--once"])

    class Reader:
        def get(self, path):
            return (
                {"localPoC": True, "fixture": fixture} if path == "/api/status" else {"value": {}}
            )

    monkeypatch.setattr(observer, "Reader", lambda _: Reader())
    assert observer.main() == 0
    assert output.getvalue().splitlines() == [
        "Sẵn sàng. Tạo đề trên web để bắt đầu." + (" [GIẢ LẬP]" if fixture else "")
    ]


def test_fresh_export_retries_disk_error_without_claiming_success(tmp_path, monkeypatch):
    watcher = observer.Watcher(None, lambda kind, value: lines.append((kind, value)), new_run=True)
    watcher.exam_id, watcher.job_id = str(uuid4()), str(uuid4())
    watcher.output_dir = tmp_path / watcher.job_id
    watcher.reader = SimpleNamespace(get=lambda _: {})
    lines = []
    original = Path.write_text

    def fail_write(*args, **kwargs):
        raise PermissionError("Ổ đĩa giả lập không ghi được")

    monkeypatch.setattr(Path, "write_text", fail_write)
    watcher.export_result("/job", {"status": "failed"}, [])
    assert not watcher.exported_path and lines[-1][0] == "LOI_LUU_JSON"
    monkeypatch.setattr(Path, "write_text", original)
    watcher.export_result("/job", {"status": "failed"}, [])
    assert watcher.exported_path and lines[-1][0] == "DA_LUU_JSON"
    assert len(list(tmp_path.iterdir())) == 1
    assert len(list(watcher.exported_path.glob("*.json"))) == 6


def test_fresh_demo_with_actual_app_api_and_fixture_agent(workspace, tmp_path):  # noqa: F811
    original, exam, _ = workspace
    state = original.get("/api/kv?key=state").json()["value"]
    directory = tmp_path / "fixture-only"
    with TestClient(
        create_app(directory, agent_call=AgentModelFixture()),
        headers={"Origin": "http://testserver"},
    ) as client:
        client.put("/api/kv", json={"key": "state", "value": state}).raise_for_status()
        old_base, _ = generate(client, exam)

        class Reader:
            def get(self, path):
                response = client.get(path)
                response.raise_for_status()
                return response.json()

        lines = []
        watcher = observer.Watcher(
            Reader(),
            lambda kind, value: lines.append((kind, value)),
            new_run=True,
            output_root=tmp_path / "exports",
        )
        watcher.fixture = client.get("/api/status").json()["fixture"]
        watcher.arm_new_run()
        watcher.poll()
        assert [kind for kind, _ in lines] == ["CHO_LUOT_MOI"]
        new_base, result = generate(client, exam)
        watcher.poll()
        assert old_base != new_base and result["status"] == "complete"
        assert watcher.exported_path
        assert (
            json_read(watcher.exported_path / "trace.json")
            == client.get(new_base + "/trace").json()
        )
        # Fixture không có HTTP model thật; giữ nguyên kết luận audit, không nâng thành verified.
        assert (
            json_read(watcher.exported_path / "audit.json")
            == client.get(new_base + "/audit").json()
        )
        assert json_read(watcher.exported_path / "session.json")["fixture"]
        assert client.get("/api/kv?key=state").json()["value"] == state
