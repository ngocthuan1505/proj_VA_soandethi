"""Dùng Chrome/KaTeX cục bộ để trình bày công thức/hình, không dùng Node API hoặc AI."""

import html
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from mach_backend.ai_contract import AIError

ROOT = Path(__file__).resolve().parents[3]


def render_assets(math, figures, chrome):
    if not math and not figures:
        return {"math": {}, "figures": []}
    if not chrome:
        raise AIError(
            "browser_unavailable",
            "Cần Chrome/Edge để xuất công thức hoặc hình. Đặt BROWSER_PATH rồi thử lại.",
        )
    if (
        len(math) > 1000
        or len(figures) > 100
        or any(not isinstance(x, str) or len(x) > 12000 for x in math)
    ):
        raise AIError("export_limit", "Đề quá nhiều công thức/hình hoặc có công thức quá dài.")
    data = json.dumps({"math": list(dict.fromkeys(math)), "figures": figures}, ensure_ascii=False)
    if len(data) > 2_000_000:
        raise AIError("export_limit", "Dữ liệu công thức/hình quá lớn; tách đề trước khi xuất.")
    module = (ROOT / "assets/export-render.mjs").as_uri()
    with tempfile.TemporaryDirectory(prefix="exam-assets-") as temp:
        source = Path(temp) / "render.html"
        source.write_text(
            '<!doctype html><meta charset="utf-8"><pre id="input">'
            + html.escape(data)
            + '</pre><pre id="result"></pre><script type="module">'
            + "import {renderExportAssets} from "
            + json.dumps(module)
            + ";"
            + 'try {const input=JSON.parse(document.querySelector("#input").textContent);'
            + "const result=await renderExportAssets(input);"
            + 'document.querySelector("#result").textContent=JSON.stringify(result);}'
            + 'catch(error){document.querySelector("#result").textContent='
            + "JSON.stringify({error:error.message});}</script>",
            encoding="utf-8",
        )
        base_args = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--host-resolver-rules=MAP * ~NOTFOUND",
            "--no-proxy-server",
            "--user-data-dir=" + str(Path(temp) / "profile"),
            "--virtual-time-budget=6000",
            "--dump-dom",
            source.as_uri(),
        ]
        try:
            try:
                output = subprocess.run(
                    base_args,
                    capture_output=True,
                    timeout=40,
                    check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.SubprocessError:
                if os.name == "nt":
                    raise
                retry_args = [
                    chrome,
                    "--headless",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    *base_args[2:],
                ]
                output = subprocess.run(
                    retry_args,
                    capture_output=True,
                    timeout=40,
                    check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            match = re.search(r'<pre id="result">(.*?)</pre>', output.stdout.decode("utf-8"), re.S)
            result = json.loads(html.unescape(match[1])) if match else None
            if (
                not isinstance(result, dict)
                or result.get("error")
                or set(result) != {"math", "figures"}
            ):
                raise AIError(
                    "export_render_failed",
                    "Chưa dựng được công thức/hình: "
                    + str((result or {}).get("error", "không có kết quả"))[:350],
                )
            return result
        except AIError:
            raise
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            raise AIError(
                "export_render_failed",
                "Chưa dựng được công thức/hình trong thời hạn. Nội dung đề được giữ nguyên.",
            ) from None
