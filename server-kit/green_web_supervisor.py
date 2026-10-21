"""Project-local process supervision. No paid resources or system services."""
import fcntl,json,os,signal,subprocess,time
from pathlib import Path

ROOT=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert ROOT.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
RUNTIME=ROOT/'.runtime'
os.chdir(ROOT);os.umask(0o077)
lock=(RUNTIME/'supervisor.lock').open('a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
config=json.loads((RUNTIME/'private-runtime.json').read_text())
process_info=json.loads((ROOT/'web-process.json').read_text())
app=Path(process_info['app']).resolve();node=Path(process_info['node']).resolve()
assert app.is_relative_to(ROOT) and node.is_relative_to(RUNTIME)
assert config['HOST']=='127.0.0.1' and config['PORT']=='4174' and config['APP_SQLITE_EXCLUSIVE']=='1'
environment=os.environ.copy();environment.update(config)
environment.update({'PATH':str(node.parent)+os.pathsep+environment.get('PATH',''),'TMPDIR':str(RUNTIME/'tmp')})
children={};last_start={};stop=False
def shutdown(*_):
    global stop
    stop=True
signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)

def start(name,command,env):
    log=ROOT/(name+'.log')
    if log.exists() and log.stat().st_size>2*1024*1024:os.replace(log,ROOT/(name+'.previous.log'))
    with log.open('ab') as stream:
        child=subprocess.Popen(command,cwd=app,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
    children[name]=child;last_start[name]=time.monotonic()
    return child

try:
    while not stop and not (RUNTIME/'STOP').exists():
        if ('web-server' not in children or children['web-server'].poll() is not None) and time.monotonic()-last_start.get('web-server',0)>10:
            child=start('web-server',[str(node),str(app/'server.mjs')],environment)
            process_info['pid']=child.pid;(ROOT/'web-process.json').write_text(json.dumps(process_info))
        auth_file=RUNTIME/'ngrok-auth.json'
        public=auth_file.exists() and (RUNTIME/'PUBLIC_READY').exists()
        if not public and 'ngrok' in children:
            child=children.pop('ngrok')
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
        if public and ('ngrok' not in children or children['ngrok'].poll() is not None) and time.monotonic()-last_start.get('ngrok',0)>30:
            auth=json.loads(auth_file.read_text());assert isinstance(auth.get('authtoken'),str) and len(auth['authtoken'])>20
            assert config['APP_PUBLIC_URL'].startswith('https://') and config['APP_PUBLIC_URL'].endswith('.ngrok-free.dev')
            agent_env=environment.copy();agent_env['NGROK_AUTHTOKEN']=auth['authtoken']
            start('ngrok',[str(RUNTIME/'ngrok'),'http','http://127.0.0.1:4174','--url='+config['APP_PUBLIC_URL'],'--inspect=false','--config='+str(RUNTIME/'ngrok.json')],agent_env)
        state={'stage':'running' if public else 'private-only','updated':time.time(),'supervisor_pid':os.getpid(),'children':{name:{'pid':child.pid,'exit':child.poll()} for name,child in children.items()},'public_requested':public}
        temporary=ROOT/'service-status.tmp';temporary.write_text(json.dumps(state));os.replace(temporary,ROOT/'service-status.json')
        for _ in range(20):
            if stop:break
            time.sleep(.1)
finally:
    for child in children.values():
        if child.poll() is None:child.terminate()
    for child in children.values():
        try:child.wait(timeout=15)
        except subprocess.TimeoutExpired:child.kill();child.wait()
