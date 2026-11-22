"""Bật app và Ollama local từ shortcut; kiểm tra server cũ & cache-busting động để luôn mở UI mới nhất."""

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 4182
URL = f"http://127.0.0.1:{PORT}"
RUNTIME = ROOT / ".runtime" / "demo-local"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DEFAULT_UI_VERSION = "demo-20261117-2"
PRIORITY_UI_FILES = (
    "index.html",
    "style.css",
    "assets/usability.css",
    "app.js",
    "mvp.js",
    "reference.js",
    "workbench.js",
    "studio.js",
    "matrix-chat.js",
    "matrix-synthesis.js",
    "lesson-picker.js",
    "sharing.js",
)


def read(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            url, timeout=2
        ) as r:
            return json.load(r)
    except (OSError, ValueError, urllib.error.URLError):
        return None


def read_text(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            url, timeout=3
        ) as r:
            return r.read().decode("utf-8", errors="replace")
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _runtime_dir(root=None):
    """Trả về thư mục runtime động theo ROOT hiện hành (hỗ trợ monkeypatch khi test)."""
    return Path(root or ROOT) / ".runtime" / "demo-local"


def collect_ui_files(root=None):
    """Thu thập toàn bộ tệp UI phục vụ giao diện để tính phiên bản cache-busting động."""
    root = Path(root or ROOT)
    files = {}
    for rel in PRIORITY_UI_FILES:
        p = root / rel
        if p.is_file():
            files[rel] = p
    for pattern in ("*.html", "*.js", "*.css"):
        for p in sorted(root.glob(pattern)):
            if p.is_file():
                files[p.relative_to(root).as_posix()] = p
    assets_dir = root / "assets"
    if assets_dir.is_dir():
        for p in sorted(assets_dir.rglob("*")):
            if p.is_file() and p.suffix in {".js", ".mjs", ".css"}:
                files[p.relative_to(root).as_posix()] = p
    return [files[k] for k in sorted(files)]


def compute_ui_version(root=None):
    """Tính mã phiên bản UI động từ hash nội dung và mtime các tệp giao diện."""
    root = Path(root or ROOT)
    ui_files = collect_ui_files(root)
    if not ui_files:
        return DEFAULT_UI_VERSION
    digest = hashlib.sha256()
    for path in ui_files:
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        digest.update(f"{rel}:{file_sha}:{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()[:12]


def compute_backend_version(root=None):
    """Tính hash mã nguồn backend Python để phát hiện server đang chạy từ bản cũ."""
    root = Path(root or ROOT)
    src_dir = root / "backend" / "src" / "mach_backend"
    if not src_dir.is_dir():
        return ""
    digest = hashlib.sha256()
    for path in sorted(src_dir.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        digest.update(f"{rel}:{file_sha}\n".encode())
    return digest.hexdigest()[:12]


def expected_asset_markers(root=None):
    """Tạo chuỗi `?v=<hash16>` khớp cách `ui_entry()` gắn phiên bản cho module UI."""
    root = Path(root or ROOT)
    markers = []
    for rel in PRIORITY_UI_FILES:
        if rel == "index.html":
            continue
        p = root / rel
        if p.is_file():
            markers.append(
                f"/{rel}?v={hashlib.sha256(p.read_bytes()).hexdigest()[:16]}"
            )
    return markers


def build_launch_url(base_url=URL, root=None):
    """Gắn query `?ui=<hash>` động thay vì chuỗi cố định để ép trình duyệt nạp UI mới."""
    return f"{base_url.rstrip('/')}?ui={compute_ui_version(root)}"


def verify_served_ui(base_url=URL, root=None):
    """Kiểm tra HTML trả về từ server có đúng hash các module UI hiện tại không."""
    html = read_text(build_launch_url(base_url, root))
    if not html:
        return False, "Không đọc được HTML giao diện từ server."
    for marker in expected_asset_markers(root):
        if marker not in html:
            return False, f"Server đang phục vụ bản cũ (thiếu {marker})."
    return True, "OK"


def read_recorded_pid(runtime=None):
    pid_file = Path(runtime or _runtime_dir()) / "app.pid"
    if not pid_file.is_file():
        return None
    text = pid_file.read_text(encoding="utf8").strip()
    return int(text) if text.isdigit() else None


def read_app_meta(runtime=None):
    meta_file = Path(runtime or _runtime_dir()) / "app.meta.json"
    if not meta_file.is_file():
        return {}
    try:
        return json.loads(meta_file.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def write_app_meta(
    pid, ui_version, backend_version, root=None, runtime=None, port=PORT
):
    root_path = Path(root or ROOT)
    runtime_path = Path(runtime or _runtime_dir(root_path))
    runtime_path.mkdir(parents=True, exist_ok=True)
    (runtime_path / "app.meta.json").write_text(
        json.dumps(
            {
                "pid": pid,
                "uiVersion": ui_version,
                "backendVersion": backend_version,
                "root": str(root_path.resolve()),
                "port": port,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )


def find_listening_pid(port=PORT):
    """Tìm PID đang lắng nghe TCP trên cổng chỉ định."""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            pattern = re.compile(
                rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE
            )
            for line in out.splitlines():
                m = pattern.match(line)
                if m:
                    return int(m.group(1))
        else:
            out = subprocess.check_output(["lsof", "-ti", f"tcp:{port}"], text=True)
            first = out.strip().splitlines()[:1]
            if first and first[0].isdigit():
                return int(first[0])
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def get_process_cmdline(pid):
    if not pid:
        return ""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine",
                ],
                text=True,
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return out.strip()
        return (
            Path(f"/proc/{int(pid)}/cmdline")
            .read_text(errors="replace")
            .replace("\x00", " ")
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


def is_port_free(port=PORT, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) != 0


def terminate_pid(pid, port=PORT):
    """Dừng an toàn tiến trình server cũ và chờ nhả cổng."""
    if not pid:
        return False
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        os.kill(pid, signal.SIGTERM)
    for _ in range(25):
        if is_port_free(port):
            return True
        time.sleep(0.2)
    return is_port_free(port)


def start(args, name, env):
    runtime = _runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True)
    with (
        (runtime / (name + ".out.log")).open("a", encoding="utf8") as out,
        (runtime / (name + ".err.log")).open("a", encoding="utf8") as err,
    ):
        process = subprocess.Popen(
            args,
            cwd=Path(ROOT) / "backend",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    (runtime / (name + ".pid")).write_text(str(process.pid), encoding="utf8")
    return process


def wait(url, process):
    for _ in range(40):
        result = read(url)
        if result:
            return result
        if process.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError("Chưa bật được dịch vụ. Xem log trong " + str(_runtime_dir()))


def ensure_fresh_port_or_reuse(ui_ver, backend_ver, launch_url):
    """Kiểm tra cổng 4182: mở ngay nếu đúng server mới, hoặc dừng an toàn server cũ trước khi bật lại."""
    status = read(URL + "/api/status")
    if not status:
        return False
    if not status.get("localPoC"):
        raise RuntimeError(
            f"Cổng {PORT} đang thuộc ứng dụng khác. Chưa dừng ứng dụng đó."
        )

    root_path = Path(ROOT)
    runtime = _runtime_dir(root_path)
    has_meta = (runtime / "app.meta.json").is_file()
    if not status.get("uiVersion") and not has_meta and not collect_ui_files(root_path):
        webbrowser.open(launch_url)
        return True

    listening_pid = find_listening_pid(PORT)
    if not status.get("uiVersion") and not has_meta and listening_pid is None:
        webbrowser.open(launch_url)
        return True

    recorded_pid = read_recorded_pid(runtime)
    meta = read_app_meta(runtime)
    ui_ok, ui_reason = verify_served_ui(URL, root_path)

    reasons = []
    if listening_pid is not None and recorded_pid != listening_pid:
        reasons.append(
            f"PID lắng nghe ({listening_pid}) khác app.pid ({recorded_pid or 'chưa có'})"
        )
    if not ui_ok:
        reasons.append(ui_reason)
    if meta.get("backendVersion") and meta.get("backendVersion") != backend_ver:
        reasons.append("mã nguồn backend đã thay đổi")
    if meta.get("root") and Path(meta["root"]).resolve() != root_path.resolve():
        reasons.append(f"server đang chạy từ thư mục khác ({meta['root']})")

    if not reasons:
        webbrowser.open(launch_url)
        print(
            f"Đang dùng server hiện hành (PID {listening_pid or recorded_pid}, ui={ui_ver}). Mở {launch_url}"
        )
        return True

    reason_text = "; ".join(reasons)
    if status.get("aiBusy"):
        raise RuntimeError(
            f"Phát hiện server cũ trên cổng {PORT} ({reason_text}), nhưng AI đang xử lý tác vụ (aiBusy=true). Hãy chờ xong rồi chạy lại."
        )

    cmdline = get_process_cmdline(listening_pid)
    confirmed_same_app = bool(
        listening_pid
        and ("mach_backend.local_workspace" in cmdline or listening_pid == recorded_pid)
    )
    if not confirmed_same_app:
        raise RuntimeError(
            f"Cổng {PORT} đang chạy server cũ không xác minh được nguồn gốc ({reason_text}; PID={listening_pid or '?'}). Hãy đóng tiến trình cũ rồi mở lại."
        )

    print(
        f"Phát hiện server cũ trên cổng {PORT} ({reason_text}). Đang khởi động lại PID {listening_pid} để nạp bản mới…"
    )
    if not terminate_pid(listening_pid, PORT):
        raise RuntimeError(
            f"Chưa dừng được server cũ PID {listening_pid} trên cổng {PORT}."
        )
    return False


def main():
    root_path = Path(ROOT)
    ui_ver = compute_ui_version(root_path)
    backend_ver = compute_backend_version(root_path)
    launch_url = build_launch_url(URL, root_path)
    if ensure_fresh_port_or_reuse(ui_ver, backend_ver, launch_url):
        return
    config_file = root_path / ".runtime" / "local-demo.json"
    config = (
        json.loads(config_file.read_text(encoding="utf-8-sig"))
        if config_file.exists()
        else {}
    )
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "src",
        "MACH_MODEL": os.environ.get("MACH_MODEL", config.get("model", MODEL)),
        "MACH_DATA_DIR": str(root_path / "outputs" / "local-demo" / "data"),
    }
    tags = read("http://127.0.0.1:11434/api/tags")
    if tags is None:
        exe = (
            os.environ.get("OLLAMA_EXE")
            or config.get("ollama")
            or shutil.which("ollama")
        )
        if exe and Path(exe).is_file():
            if config.get("models"):
                env["OLLAMA_MODELS"] = config["models"]
            env["OLLAMA_HOST"] = "127.0.0.1:11434"
            try:
                tags = wait(
                    "http://127.0.0.1:11434/api/tags",
                    start([exe, "serve"], "ollama", env),
                )
            except (OSError, RuntimeError):
                print(
                    "Ollama chưa sẵn sàng. App vẫn mở; có thể dùng Gemini hoặc soạn tay."
                )
    model = env["MACH_MODEL"]
    if not any(
        m.get("name") == model and not m.get("remote_host")
        for m in (tags or {}).get("models", [])
    ):
        print(
            "AI local chưa sẵn sàng; app vẫn mở với kết nối Gemini đã lưu hoặc soạn tay."
        )
    process = start(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mach_backend.local_workspace:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--app-dir",
            "src",
        ],
        "app",
        env,
    )
    wait(URL + "/api/status", process)
    pid = getattr(process, "pid", None)
    if isinstance(pid, int) and not isinstance(pid, bool):
        write_app_meta(
            pid, ui_ver, backend_ver, root_path, _runtime_dir(root_path), PORT
        )
        if collect_ui_files(root_path):
            ui_ok, ui_reason = verify_served_ui(URL, root_path)
            if not ui_ok:
                print("Cảnh báo xác minh UI: " + ui_reason)
    webbrowser.open(launch_url)
    print(
        f"Đã mở app tại {launch_url} (ui={ui_ver}). Dữ liệu giữ trong outputs/local-demo/data."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error))
        sys.exit(1)
