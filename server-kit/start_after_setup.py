"""Continue this project's current installation without touching other tasks."""
import json
from pathlib import Path
import subprocess
import time
ROOT = Path('/network-volume/ProJ_VA/soande_ai').resolve(strict=True)
deadline = time.time()+3600
while time.time()<deadline:
    status = json.loads((ROOT/'setup-status.json').read_text())
    if status['phase']=='error':
        raise RuntimeError(status.get('error','Setup failed'))
    if status['phase']=='installed':
        subprocess.run(['bash',str(ROOT/'start_ai.sh')],cwd=ROOT,check=True)
        break
    time.sleep(3)
else:
    raise TimeoutError('Setup not finished after one hour')
