import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_team_launcher_help_does_not_create_account_data(tmp_path, monkeypatch):
    script = ROOT / "scripts/chay-nhom-tai-khoan.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--help", "--data", str(tmp_path / "unused")])
    module = runpy.run_path(str(script))
    with pytest.raises(SystemExit) as result:
        module["main"]()
    assert result.value.code == 0
    assert not (tmp_path / "unused").exists()


def test_team_launcher_refuses_old_poc_store(monkeypatch):
    script = ROOT / "scripts/chay-nhom-tai-khoan.py"
    monkeypatch.setattr(sys, "argv", [str(script), "--data", str(ROOT / "outputs/local-demo/data")])
    module = runpy.run_path(str(script))
    with pytest.raises(SystemExit) as result:
        module["main"]()
    assert result.value.code == 2
