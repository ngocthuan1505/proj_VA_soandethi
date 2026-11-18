"""Bật app và Ollama local từ shortcut; chạy lại chỉ mở tab đang có."""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:4182"
RUNTIME = ROOT / ".runtime" / "demo-local"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def read(url):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            url, timeout=2
        ) as r:
            return json.load(r)
    except (OSError, ValueError, urllib.error.URLError):
        return None


def start(args, name, env):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (
        (RUNTIME / (name + ".out.log")).open("a", encoding="utf8") as out,
        (RUNTIME / (name + ".err.log")).open("a", encoding="utf8") as err,
    ):
        process = subprocess.Popen(
            args,
            cwd=ROOT / "backend",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    (RUNTIME / (name + ".pid")).write_text(str(process.pid), encoding="utf8")
    return process


def wait(url, process):
    for _ in range(40):
        result = read(url)
        if result:
            return result
        if process.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError("Chưa bật được dịch vụ. Xem log trong " + str(RUNTIME))


def main():
    status = read(URL + "/api/status")
    if status and status.get("localPoC"):
        webbrowser.open(URL + "?ui=demo-20261117-2")
        return
    if status:
        raise RuntimeError("Cổng 4182 đang thuộc ứng dụng khác. Chưa dừng ứng dụng đó.")
    config_file = ROOT / ".runtime" / "local-demo.json"
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
        "MACH_DATA_DIR": str(ROOT / "outputs" / "local-demo" / "data"),
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
            "4182",
            "--app-dir",
            "src",
        ],
        "app",
        env,
    )
    wait(URL + "/api/status", process)
    webbrowser.open(URL + "?ui=demo-20261117-2")
    print("Đã mở app tại " + URL + ". Dữ liệu giữ trong outputs/local-demo/data.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error))
        sys.exit(1)
