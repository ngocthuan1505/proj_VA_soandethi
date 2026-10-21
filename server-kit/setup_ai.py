"""Project-only CUDA runtime and model setup. Run from /network-volume/ProJ_VA."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

PROJECT = Path('/network-volume/ProJ_VA').resolve(strict=True)
ROOT = PROJECT / 'soande_ai'
if ROOT.is_symlink():
    raise RuntimeError('Refusing symlink workspace')
ROOT.mkdir(exist_ok=True)
os.chdir(ROOT)
for name in ['tmp', 'cache', 'models', 'logs', 'jobs']:
    (ROOT / name).mkdir(exist_ok=True)
os.environ.update(TMPDIR=str(ROOT/'tmp'), XDG_CACHE_HOME=str(ROOT/'cache'),
                  HF_HOME=str(ROOT/'cache/huggingface'), CUDA_CACHE_PATH=str(ROOT/'cache/cuda'), LLAMA_CACHE=str(ROOT/'cache/llama'), CCACHE_DIR=str(ROOT/'cache/ccache'),
                  PYTHONPYCACHEPREFIX=str(ROOT/'cache/pycache'))
STATE = {'phase': 'preparing', 'project': str(PROJECT), 'model': 'qwen3:8b', 'started': time.time()}

def status(**values):
    STATE.update(values)
    temp = ROOT/'setup-status.tmp'
    temp.write_text(json.dumps(STATE), encoding='utf-8')
    temp.replace(ROOT/'setup-status.json')

def run(args, log):
    with (ROOT/'logs'/log).open('ab') as stream:
        subprocess.run(args, cwd=ROOT, env=os.environ.copy(), stdout=stream, stderr=stream, check=True)

def build_runtime():
    source = ROOT/'runtime-src'
    if not source.exists():
        run(['git', 'clone', '--depth', '1', '--branch', 'v0.7.0',
             'https://github.com/ggml-org/llama.cpp.git', str(source)], 'build.log')
    run(['cmake', '-S', str(source), '-B', str(source/'build'),
         '-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON', '-DCMAKE_CUDA_ARCHITECTURES=90',
         '-DGGML_CCACHE=OFF', '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF',
         '-DLLAMA_BUILD_SERVER=ON'], 'build.log')
    run(['cmake', '--build', str(source/'build'), '--target', 'llama-server', '-j', '4'], 'build.log')
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    return revision

def sha256(file):
    digest = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def download_model():
    # Official model layer: no account, upload or private document involved.
    registry = 'https://registry.ollama.ai/v2/library/qwen3'
    with urllib.request.urlopen(registry+'/manifests/8b', timeout=60) as response:
        manifest = json.load(response)
    layer = next(x for x in manifest['layers'] if x['mediaType']=='application/vnd.ollama.image.model')
    digest = layer['digest'].removeprefix('sha256:')
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise RuntimeError('Invalid model digest')
    target = ROOT/'models/qwen3-8b.gguf'
    if target.exists() and target.stat().st_size==layer['size'] and sha256(target)==digest:
        return digest
    part = target.with_suffix('.gguf.part')
    offset = part.stat().st_size if part.exists() else 0
    if offset>layer['size']:
        raise RuntimeError('Partial model is too large; not overwriting it')
    if offset<layer['size']:
        request = urllib.request.Request(registry+'/blobs/'+layer['digest'], headers={'Range':f'bytes={offset}-'} if offset else {})
        with urllib.request.urlopen(request, timeout=120) as response:
            if offset and response.status!=206:
                offset = 0
            with part.open('ab' if offset else 'wb') as stream:
                shutil.copyfileobj(response, stream, length=8*1024*1024)
    if part.stat().st_size!=layer['size'] or sha256(part)!=digest:
        raise RuntimeError('Model SHA-256 mismatch; model not activated')
    part.replace(target)
    (ROOT/'models/manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return digest

try:
    if shutil.disk_usage(ROOT).free<12*1024**3:
        raise RuntimeError('Need at least 12 GB of free project storage')
    status(phase='downloading-and-building')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        runtime = pool.submit(build_runtime)
        model = pool.submit(download_model)
        revision, digest = runtime.result(), model.result()
    status(phase='installed', runtimeRevision=revision, modelSHA256=digest, finished=time.time())
    print('Installed in', ROOT, flush=True)
except Exception as error:
    status(phase='error', error=str(error), finished=time.time())
    raise
