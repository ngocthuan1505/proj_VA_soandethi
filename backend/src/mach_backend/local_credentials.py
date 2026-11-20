"""Lưu cấu hình AI bằng DPAPI CurrentUser; không có nhánh ghi khóa dạng rõ."""

import csv
import ctypes
import json
import os
import subprocess
import tempfile
from pathlib import Path

MAGIC = b"EXAM-AI-DPAPI-1\0"


def protect(data: bytes, *, decrypt=False):
    if os.name != "nt":
        raise OSError("Lưu khóa mã hóa hiện chỉ hỗ trợ Windows.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint32), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(Blob),
    ]
    function.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        # UI_FORBIDDEN; không dùng LOCAL_MACHINE để tránh cấp giải mã cho mọi user.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise OSError("Windows không mã hóa/mở được cấu hình AI cho tài khoản này.")
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.memset(buffer, 0, len(buffer))
        if target.data:
            ctypes.memset(target.data, 0, target.size)
            kernel.LocalFree(target.data)


def restrict_to_current_user(path):
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=5,
    )
    try:
        sid = next(csv.reader(identity.stdout.decode(errors="replace").splitlines()))[1]
    except (StopIteration, IndexError):
        raise OSError("Không xác định được tài khoản Windows để bảo vệ file.") from None
    if identity.returncode or not sid.startswith("S-1-"):
        raise OSError("Không xác định được tài khoản Windows để bảo vệ file.")
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=5,
    )
    if result.returncode:
        raise OSError("Không đặt được quyền riêng cho file cấu hình AI.")


class LocalConnectionStore:
    def __init__(self, directory: Path):
        self.path = directory / "ai-connection.dpapi"
        self.available = os.name == "nt"

    def load(self):
        if not self.path.exists():
            return None
        if self.path.stat().st_size > 131072:
            raise OSError("File cấu hình mã hóa không hợp lệ.")
        encrypted = self.path.read_bytes()
        if not encrypted.startswith(MAGIC):
            raise OSError("File cấu hình mã hóa không hợp lệ.")
        try:
            envelope = json.loads(protect(encrypted[len(MAGIC) :], decrypt=True))
            if envelope.get("version") != 1 or not isinstance(envelope.get("config"), dict):
                raise ValueError
            return envelope["config"]
        except (ValueError, TypeError, AttributeError):
            raise OSError("Không mở được file cấu hình mã hóa.") from None

    def save(self, config):
        plain = json.dumps({"version": 1, "config": config}, ensure_ascii=False).encode()
        if len(plain) > 65536:
            raise OSError("Cấu hình AI vượt giới hạn lưu cục bộ.")
        encrypted = MAGIC + protect(plain)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=".ai-connection-", suffix=".dpapi", dir=self.path.parent
        )
        os.close(descriptor)
        temporary = Path(name)
        try:
            restrict_to_current_user(temporary)
            with temporary.open("wb") as file:
                file.write(encrypted)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def clear(self):
        self.path.unlink(missing_ok=True)
