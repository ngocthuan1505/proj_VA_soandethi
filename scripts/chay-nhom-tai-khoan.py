"""Bật chế độ tài khoản nhóm riêng tại máy; không nhập hoặc chuyển kho PoC cũ."""

import argparse
import getpass
import json
import os
import socket
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / ".data/team-workspace")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reset-password", metavar="EMAIL")
    args = parser.parse_args()
    data = args.data.resolve()
    if data == (ROOT / "outputs/local-demo/data").resolve():
        parser.error("Không dùng kho PoC đang có cho chế độ nhóm.")
    os.environ["MACH_TEAM_DATA_DIR"] = str(data)
    sys.path.insert(0, str(ROOT / "backend/src"))
    from mach_backend.team_accounts import TeamAccounts, digest

    accounts = TeamAccounts(data)
    if args.reset_password:
        password = getpass.getpass("Mật khẩu mới (ít nhất 10 ký tự): ")
        if password != getpass.getpass("Nhập lại mật khẩu mới: "):
            parser.error("Hai mật khẩu chưa khớp.")
        accounts.reset_password(args.reset_password, password)
        print("Đã đổi mật khẩu và thu hồi các phiên của tài khoản.")
        return
    url = "http://127.0.0.1:4185"
    with socket.socket() as probe:
        occupied = probe.connect_ex(("127.0.0.1", 4185)) == 0
    if occupied:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(url + "/api/team/health", timeout=3) as response:
                status = json.load(response)
                if status.get("teamMode") is not True or status.get("instance") != digest(
                    str(data).casefold()
                )[:16]:
                    raise ValueError
        except (OSError, ValueError):
            parser.error("Cổng 4185 thuộc ứng dụng khác; chưa dừng tiến trình đó.")
        if not args.no_browser:
            webbrowser.open(url)
        print("Chế độ nhóm đã chạy tại " + url)
        return
    invite_file = data / "bootstrap-invite.txt"
    login_url = url
    if accounts.administrator() is None:
        token = invite_file.read_text(encoding="utf-8").strip() if invite_file.is_file() else ""
        with accounts.connect() as db:
            valid = db.execute(
                "SELECT 1 FROM invites WHERE token=? AND role='admin' AND used=0 AND expires>?",
                (digest(token), int(accounts.clock())),
            ).fetchone()
        if not valid:
            token = accounts.invite(bootstrap=True)
            invite_file.write_text(token, encoding="utf-8")
            if os.name == "nt":
                from mach_backend.local_credentials import restrict_to_current_user

                restrict_to_current_user(invite_file)
            else:
                invite_file.chmod(0o600)
        login_url = url + "/login#invite=" + quote(token, safe="")
        print("Chưa có quản trị viên. Mã mời nằm riêng trong " + str(invite_file))
        print("Không gửi tệp mã mời hoặc thư mục dữ liệu lên GitHub.")
    else:
        invite_file.unlink(missing_ok=True)
    if not args.no_browser:
        import threading

        def open_when_ready():
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(40):
                try:
                    with opener.open(url + "/api/team/health", timeout=1) as response:
                        if json.load(response).get("instance") == digest(str(data).casefold())[:16]:
                            webbrowser.open(login_url)
                            return
                except (OSError, ValueError):
                    pass
                time.sleep(0.25)

        threading.Thread(target=open_when_ready, daemon=True).start()
    print("Chế độ nhóm: " + url + " — đóng cửa sổ này hoặc Ctrl+C để dừng.")
    import uvicorn
    from mach_backend.team_workspace import app

    uvicorn.run(app, host="127.0.0.1", port=4185, log_level="warning")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
