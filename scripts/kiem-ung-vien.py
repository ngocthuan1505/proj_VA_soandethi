"""Chạy 11 ca trình duyệt trên một commit FastAPI với kho thử riêng từng ca."""

import argparse
import json
import os
import runpy
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("01", "scripts/kiem-ui-kho-nhom.mjs", "team"),
    ("02", "scripts/kiem-ui-nhap-nguon.mjs", "source"),
    ("03", "scripts/kiem-ui-co-cau.mjs", "repair"),
    ("04", "scripts/kiem-ui-matrix-chat.mjs", "repair"),
    ("05", "tests/ui2-baseline-browser.mjs", None),
    ("06", "scripts/kiem-ui-de-xuat-sua.mjs", "repair"),
    ("07", "scripts/kiem-ui-giai-doc-lap.mjs", "unsupported"),
    ("08", "scripts/kiem-ui-du-kien.mjs", "repair"),
    ("09", "scripts/kiem-ui-nguon-ab.mjs", "repair"),
    ("10", "scripts/kiem-ui-xuat-chia-se.mjs", "repair"),
    ("11", "scripts/kiem-ui-khoi-phuc.mjs", "restore"),
)


def serve(mode, output):
    fixture = runpy.run_path(str(ROOT / "scripts/chay-fixture-poc.py"))["FixtureCase"]
    from mach_backend.local_workspace import create_app
    from mach_backend.team_workspace import create_team_app
    from mach_backend.workspace_store import WorkspaceStore
    from test_workspace_backup import backup_fixture
    from uvicorn import Config, Server

    directory = output / "data"
    if mode in {"team", "restore"}:
        app = create_team_app(directory, agent_call=fixture("repair"))
        accounts = app.state.accounts
        owner = accounts.create(
            "restore-admin@example.test",
            "mat-khau-qa-18-11",
            "Quản trị thử",
            accounts.invite(bootstrap=True),
        )
        accounts.create(
            "restore-member@example.test",
            "mat-khau-qa-18-11",
            "Thành viên thử",
            accounts.invite(),
        )
        if mode == "restore":
            backup = backup_fixture()
            exam = json.loads(
                subprocess.check_output(
                    [
                        "node",
                        "--input-type=module",
                        "-e",
                        "import {sample} from './core.js'; console.log(JSON.stringify(sample()));",
                    ],
                    cwd=ROOT,
                    encoding="utf-8",
                )
            )
            file_id = next(iter(backup["files"]))
            exam["docs"].append(
                {"id": file_id, "fileId": file_id, "kind": "image", "name": "anh-mau.png"}
            )
            store = WorkspaceStore(directory / "users" / owner["id"], owner=owner["id"])
            store.put("state", {"version": 1, "current": exam["id"], "exams": [exam], "prefs": []})
            for file_id, value in backup["files"].items():
                store.put("file:" + file_id, value)
    elif mode == "source":
        from test_source_documents import pdf

        (output / "nguon-2-trang.pdf").write_bytes(pdf("Nguon trang mot", "Nguon trang hai"))
        app = create_app(directory, agent_call=fixture("repair"))
    else:
        app = create_app(directory, agent_call=fixture(mode))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        (output / "port").write_text(str(port), encoding="ascii")
        Server(Config(app, host="127.0.0.1", port=port, log_level="warning")).run(
            sockets=[listener]
        )


def wait_for_server(process, output, mode):
    port_file = output / "port"
    path = "/login" if mode in {"team", "restore"} else "/api/status"
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("FastAPI kết thúc trước khi sẵn sàng.")
        if port_file.is_file():
            base = "http://127.0.0.1:" + port_file.read_text(encoding="ascii")
            try:
                with urlopen(base + path, timeout=1):
                    return base
            except URLError:
                pass
        time.sleep(0.25)
    raise RuntimeError("FastAPI chưa sẵn sàng.")


def run_case(script, mode, output):
    output.mkdir()
    env = {
        **os.environ,
        "QA_PYTHON": sys.executable,
        "QA_OUTPUT": str(output),
        "MACH_DATA_DIR": str(output / "module-local"),
        "MACH_TEAM_DATA_DIR": str(output / "module-team"),
    }
    env.pop("POC_URL", None)
    server = None
    with (output / "server.log").open("wb") as server_log:
        try:
            if mode:
                server = subprocess.Popen(
                    [sys.executable, __file__, str(output), "--serve", mode],
                    cwd=ROOT,
                    env=env,
                    stdout=server_log,
                    stderr=subprocess.STDOUT,
                )
                env["POC_URL"] = wait_for_server(server, output, mode)
            with (output / "browser.log").open("wb") as browser_log:
                subprocess.run(
                    ["node", script, str(output)],
                    cwd=ROOT,
                    env=env,
                    stdout=browser_log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=300 if Path(script).name == "kiem-ui-xuat-chia-se.mjs" else 180,
                )
        finally:
            if server and server.poll() is None:
                server.terminate()
                server.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", action="append", choices=[number for number, _, _ in CASES])
    parser.add_argument("--serve", choices=("team", "restore", "source", "repair", "unsupported"))
    args = parser.parse_args()
    output = args.output.resolve()
    if args.serve:
        serve(args.serve, output)
        return
    output.mkdir(parents=True)
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    commit = subprocess.check_output([*git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output([*git, "status", "--porcelain"], cwd=ROOT, text=True)
    if dirty:
        parser.error("Dùng worktree sạch để kết quả truy vết đúng commit.")
    cases = []
    for number, script, mode in CASES:
        if args.case and number not in args.case:
            continue
        target = output / f"IT-{number}"
        try:
            run_case(script, mode, target)
            report = {"05": "ui2-baseline-report.json", "10": "browser-result.json"}.get(
                number, "result.json"
            )
            if not (target / report).is_file():
                raise RuntimeError(f"Thiếu báo cáo {report}.")
            passed = True
            detail = ""
        except (subprocess.SubprocessError, OSError, RuntimeError) as error:
            passed = False
            detail = str(error)
        cases.append({"case": target.name, "passed": passed, "detail": detail})
        print(f"{target.name} {'đạt' if passed else 'lỗi'} · {target}", flush=True)
        (output / "result.json").write_text(
            json.dumps(
                {"commit": commit, "fixture": True, "cases": cases}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
    sys.exit(0 if all(row["passed"] for row in cases) else 1)


if __name__ == "__main__":
    main()
