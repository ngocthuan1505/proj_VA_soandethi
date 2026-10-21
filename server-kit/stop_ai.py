"""Stop only the model/worker owned by this project, never other GPU jobs."""
import os
from pathlib import Path
import signal
ROOT = Path('/network-volume/ProJ_VA/soande_ai').resolve(strict=True)
for name, marker in [('worker.pid',str(ROOT/'worker.py')),('model.pid',str(ROOT/'runtime-src/build/bin/llama-server'))]:
    try:
        pid = int((ROOT/name).read_text())
        command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
        if marker not in command:
            print('PID changed, not stopping:', name)
            continue
        os.kill(pid,signal.SIGTERM)
        print('Stopped',name)
    except (FileNotFoundError,ProcessLookupError):
        print('Already stopped:',name)
