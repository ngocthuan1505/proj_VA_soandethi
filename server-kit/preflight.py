"""Read-only checks. No installation, model download, account or secret access."""
import json
import os
from pathlib import Path

project_root = Path("/network-volume/ProJ_VA").resolve(strict=True)
os.chdir(project_root)
print("Working directory:", Path.cwd())
import subprocess
import urllib.request

try:
    gpu = subprocess.run([
        'nvidia-smi', '--query-gpu=name,memory.total,memory.free',
        '--format=csv,noheader'
    ], capture_output=True, text=True, timeout=10)
    print('GPU:', gpu.stdout.strip() or 'nvidia-smi returned no GPU data')
except (OSError, subprocess.TimeoutExpired):
    print('GPU: nvidia-smi not available')

for label, endpoint in [
    ('Ollama', 'http://127.0.0.1:11434/api/tags'),
    ('OpenAI-compatible', 'http://127.0.0.1:8000/v1/models'),
]:
    try:
        with urllib.request.urlopen(endpoint, timeout=4) as response:
            data = json.load(response)
        models = [m.get('name', m.get('id')) for m in data.get('models', data.get('data', []))]
        print(label, json.dumps({'models': models}, ensure_ascii=False))
    except Exception as error:
        print(label, type(error).__name__, '(unavailable or requires authorization)')
