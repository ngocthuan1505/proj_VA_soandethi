"""Launcher chỉ mở đúng app local; không dừng dịch vụ hoặc tự tải model."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts/mo-app-local.py"
    spec = importlib.util.spec_from_file_location("local_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.delenv("MACH_MODEL", raising=False)
    return module


def test_second_click_opens_existing_app(launcher, monkeypatch):
    opened = []
    monkeypatch.setattr(launcher, "read", lambda _: {"localPoC": True})
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    monkeypatch.setattr(launcher, "start", lambda *_: pytest.fail("Không được tạo server thứ hai"))
    launcher.main()
    assert opened == ["http://127.0.0.1:4182?ui=demo-20261117-2"]


def test_launcher_does_not_replace_another_app(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "read", lambda _: {"name": "other-app"})
    with pytest.raises(RuntimeError, match="ứng dụng khác"):
        launcher.main()


def test_launcher_starts_python_with_installed_local_model(launcher, monkeypatch):
    calls, opened = [], []
    monkeypatch.setattr(
        launcher,
        "read",
        lambda url: {"models": [{"name": launcher.MODEL}]} if url.endswith("/api/tags") else None,
    )
    monkeypatch.setattr(
        launcher,
        "start",
        lambda args, name, env: calls.append((args, name, env)) or SimpleNamespace(),
    )
    monkeypatch.setattr(launcher, "wait", lambda *_: {"localPoC": True})
    monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
    launcher.main()
    assert len(calls) == 1 and "mach_backend.local_workspace:app" in calls[0][0]
    assert calls[0][2]["MACH_DATA_DIR"].endswith("local-demo\\data") or calls[0][2][
        "MACH_DATA_DIR"
    ].endswith("local-demo/data")
    assert "127.0.0.1" in calls[0][0] and "4182" in calls[0][0]
    assert opened == ["http://127.0.0.1:4182?ui=demo-20261117-2"]
