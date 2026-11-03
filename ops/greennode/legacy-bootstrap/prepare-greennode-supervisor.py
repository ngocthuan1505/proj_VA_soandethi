import json,subprocess,sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
code=r'''import os,json,subprocess,time,signal,urllib.request,sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root);os.umask(0o077)
runtime=root/'.runtime';status=root/'supervisor-setup-status.json'
def report(stage,**extra):
    temporary=root/'supervisor-setup-status.tmp';temporary.write_text(json.dumps({'stage':stage,'updated':time.time(),**extra}));os.replace(temporary,status)
def alive(pid):
    try:return not Path('/proc/'+str(pid)+'/stat').read_text().split(') ',1)[1].startswith('Z ')
    except FileNotFoundError:return False
def health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:4174/api/health',timeout=2) as response:return response.status==200
    except Exception:return False
try:
    assert json.loads((root/'browser-status.json').read_text())['stage']=='browser-ready'
    assert json.loads((root/'tunnel-status.json').read_text())['stage']=='agent-ready'
    report('preparing-private-supervision')
    agent=runtime/'ngrok.json';agent.write_text(json.dumps({'version':'3','agent':{'web_addr':False,'inspect_db_size':-1,'remote_management':False,'log_level':'warn','log_format':'json','log':'stdout'}}))
    subprocess.run([str(runtime/'ngrok'),'config','check','--config='+str(agent)],check=True,capture_output=True,text=True,timeout=15)
    metadata=json.loads((root/'web-process.json').read_text());pid=metadata['pid'];app=Path(metadata['app']).resolve()
    assert app.is_relative_to(root)
    if alive(pid):
        assert str(app/'server.mjs').encode() in Path('/proc/'+str(pid)+'/cmdline').read_bytes()
        os.kill(pid,signal.SIGTERM)
        for attempt in range(100):
            if not alive(pid):break
            time.sleep(.2)
        else:raise RuntimeError('Private server did not stop')
    old=root/'private-runtime.json';new=runtime/'private-runtime.json'
    if old.exists():
        assert not new.exists(),'Refusing to overwrite a private configuration'
        config=json.loads(old.read_text())
    else:config=json.loads(new.read_text())
    data=root/'data';hidden=root/'.data'
    assert data.resolve().parent==root and hidden.resolve().parent==root
    if data.exists():
        assert not hidden.exists(),'Refusing to overwrite an existing data directory'
        data.rename(hidden)
    assert hidden.is_dir()
    config['APP_DATA_DIR']=str(hidden);new.write_text(json.dumps(config));new.chmod(0o600)
    if old.exists():old.unlink()
    compile((root/'supervise_web.py').read_text(),str(root/'supervise_web.py'),'exec')
    report('starting-private-supervisor')
    with (root/'supervisor.log').open('ab') as stream:supervisor=subprocess.Popen([sys.executable,str(root/'supervise_web.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    for attempt in range(100):
        if supervisor.poll() is not None:raise RuntimeError('Private supervisor exited')
        if health():break
        time.sleep(.2)
    else:raise RuntimeError('Private supervisor health timeout')
    initial=json.loads((root/'service-status.json').read_text());first=initial['children']['web-server']['pid']
    assert not initial['public_requested'] and 'ngrok' not in initial['children']
    assert str(app/'server.mjs').encode() in Path('/proc/'+str(first)+'/cmdline').read_bytes()
    report('checking-owned-process-restart')
    os.kill(first,signal.SIGTERM)
    for attempt in range(160):
        current=json.loads((root/'service-status.json').read_text());child=current['children']['web-server']
        if child['pid']!=first and child['exit'] is None and health():break
        time.sleep(.2)
    else:raise RuntimeError('Private supervisor did not recover its own app process')
    report('supervisor-ready',supervisor_pid=supervisor.pid,app_pid=child['pid'],private_app_health=True,restart_verified=True,private_data_hidden=True,ngrok_config_valid=True,public_endpoint=False,token_loaded=False)
except Exception as error:report('failed',error=str(error));raise
'''
script=root/'install_supervisor.py'
if (root/'supervisor-setup-status.json').exists() and json.loads((root/'supervisor-setup-status.json').read_text())['stage']!='failed':print(json.dumps({'existing_setup':json.loads((root/'supervisor-setup-status.json').read_text())}))
else:
    script.write_text(code)
    with (root/'install-supervisor.log').open('ab') as stream:process=subprocess.Popen([sys.executable,str(script)],cwd=root,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'setup_pid':process.pid,'public_endpoint':False,'token_loaded':False}))
