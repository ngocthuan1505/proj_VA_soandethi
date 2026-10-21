"""File queue over the existing Jupyter Contents API. No new public listening port."""
import json
import fcntl
import os
from pathlib import Path
import subprocess
import signal
import time
import urllib.request

PROJECT = Path('/network-volume/ProJ_VA').resolve(strict=True)
ROOT = PROJECT/'soande_ai'
if ROOT.is_symlink():
    raise RuntimeError('Refusing symlink workspace')
os.chdir(ROOT)
lock = (ROOT/'worker.lock').open('w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
(ROOT/'worker.pid').write_text(str(os.getpid()))
for name in ['tmp', 'cache', 'models', 'logs', 'jobs']:
    (ROOT/name).mkdir(exist_ok=True)
os.environ.update(TMPDIR=str(ROOT/'tmp'), XDG_CACHE_HOME=str(ROOT/'cache'),
                  HF_HOME=str(ROOT/'cache/huggingface'), CUDA_CACHE_PATH=str(ROOT/'cache/cuda'), LLAMA_CACHE=str(ROOT/'cache/llama'), PYTHONPYCACHEPREFIX=str(ROOT/'cache/pycache'))
URL = 'http://127.0.0.1:11436'
MODEL = 'qwen3:8b'

def call(path, body=None, timeout=5):
    request = urllib.request.Request(URL+path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)

def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)

def healthy():
    try:
        return call('/health').get('status')=='ok'
    except Exception:
        return False

child = None
def stop(_signal, _frame):
    write_json(ROOT/'status.json', {'ready':False,'model':MODEL,'updated':time.time(),'project':str(PROJECT)})
    if child is not None:
        child.terminate()
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
if not healthy():
    stream = (ROOT/'logs/model.log').open('ab')
    child = subprocess.Popen([str(ROOT/'runtime-src/build/bin/llama-server'),
                              '--model', str(ROOT/'models/qwen3-8b.gguf'), '--alias', MODEL,
                              '--host','127.0.0.1','--port','11436','--ctx-size','16384',
                              '--parallel','1','--n-gpu-layers','99','--threads','4',
                              '--batch-size','512','--ubatch-size','128','--flash-attn','on',
                              '--no-webui'], cwd=ROOT, env=os.environ.copy(), stdout=stream, stderr=stream)
    (ROOT/'model.pid').write_text(str(child.pid))

last_status = 0
while True:
    now = time.time()
    ready = healthy()
    if now-last_status>3:
        write_json(ROOT/'status.json', {'ready':ready,'model':MODEL,'updated':now,
                   'project':str(PROJECT),'transport':'jupyter-contents-queue',
                   'gpuLayers':99,'context':16384,'workerPID':os.getpid(),
                   'modelExited':child.poll() if child else None})
        last_status = now
    if child and child.poll() is not None:
        raise RuntimeError('Model exited; inspect logs/model.log')
    if ready:
        for file in sorted((ROOT/'jobs').glob('q-*.json')):
            if file.is_symlink() or file.stat().st_size>900000:
                continue
            request = None
            try:
                request = json.loads(file.read_text(encoding='utf-8'))
                job_id = file.stem.removeprefix('q-')
                if len(job_id)!=36 or any(c not in '0123456789abcdef-' for c in job_id):
                    raise ValueError('Invalid job id')
                if request.get('id')!=job_id or request.get('model')!=MODEL or request.get('task') not in ['generate','patch','check']:
                    raise ValueError('Invalid job')
                if time.time()-request.get('created',0)>600:
                    raise ValueError('Expired job')
                prompt = request['prompt']
                if not isinstance(prompt,str) or len(prompt)>180000:
                    raise ValueError('Invalid prompt')
                tokens = len(call('/tokenize', {'content':prompt}, timeout=15)['tokens'])
                budget = min(4096 if request['task']=='generate' else 2048, 16384-tokens-64)
                if budget<512:
                    raise ValueError('Nguồn quá dài cho mô hình cục bộ. Chọn ít trang hơn.')
                started = time.time()
                result = call('/completion', {'prompt':prompt,'n_predict':budget,'temperature':0.2,
                              'json_schema':{'type':'object'},'cache_prompt':True,'stream':False}, timeout=240)
                if result.get('stop_type')=='limit' or result.get('truncated'):
                    raise ValueError('Phản hồi vượt giới hạn. Chọn ít câu hoặc ít trang hơn.')
                output = {'id':job_id,'model':MODEL,'text':result['content'],'seconds':round(time.time()-started,2)}
            except Exception as error:
                output = {'id':file.stem.removeprefix('q-'),'error':str(error)}
            write_json(ROOT/'jobs'/('r-'+file.stem.removeprefix('q-')+'.json'), output)
            file.unlink()  # only the transient request created for this worker
    time.sleep(0.5)
