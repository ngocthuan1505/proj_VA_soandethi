"""Lối gọi tương thích script nhánh PoC; xử lý chính nằm trong backend Python."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))

from mach_backend.poc_trace import inspect_run, main  # noqa: E402, F401

if __name__ == "__main__":
    raise SystemExit(main())
