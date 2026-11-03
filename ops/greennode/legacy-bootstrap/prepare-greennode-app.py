import os,json,subprocess,sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root)
code=r'''import os,json,hashlib,zipfile,subprocess,secrets,time,urllib.request
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root);os.umask(0o077);os.nice(5)
status=root/'web-status.json'
def report(stage,**extra):
    temporary=root/'web-status.tmp';temporary.write_text(json.dumps({'stage':stage,'updated':time.time(),**extra}));os.replace(temporary,status)
try:
    expected='1fcb59a0b7c6878d25434156913d16908e633397a079b7041df33cf8d2fb203b'
    source=root/('source-'+expected[:16]+'.zip')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
    release=root/'releases'/expected[:16];release.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        for name in archive.namelist():
            target=(release/name).resolve();assert target.is_relative_to(release.resolve())
            assert name.startswith('app/')
        archive.extractall(release)
    app=release/'app';node=root/'.runtime/node-v24.22.0-linux-x64/bin/node'
    assert node.exists() and (app/'server.mjs').exists()
    environment=os.environ.copy()
    environment.update({'PATH':str(node.parent)+os.pathsep+environment.get('PATH',''),'npm_config_cache':str(root/'.runtime/npm-cache'),'npm_config_userconfig':str(root/'.runtime/npmrc'),'npm_config_update_notifier':'false','TMPDIR':str(root/'.runtime/tmp')})
    Path(environment['TMPDIR']).mkdir(exist_ok=True);Path(environment['npm_config_userconfig']).touch(exist_ok=True)
    report('installing-dependencies',source_sha256=expected)
    npm=node.parent.parent/'lib/node_modules/npm/bin/npm-cli.js'
    subprocess.run([str(node),str(npm),'ci','--omit=dev','--no-audit','--no-fund'],cwd=app,env=environment,check=True,timeout=900)
    config={'PORT':'4174','HOST':'127.0.0.1','APP_DATA_DIR':str(root/'data'),'APP_SQLITE_EXCLUSIVE':'1','APP_PUBLIC_URL':'https://mach-setup.invalid','APP_ADMIN_EMAIL':'owner@setup.invalid','APP_SIGNUP_CODE':secrets.token_hex(32),'APP_AI_CONFIG':json.dumps({'greennode':{'url':'https://YOUR-NOTEBOOK.example.test','model':'qwen3:8b'},'routes':{'generate':'greennode','patch':'greennode','check':'greennode'}})}
    config_file=root/'private-runtime.json'
    assert not config_file.exists(),'Runtime config already exists; refusing to replace credentials'
    config_file.write_text(json.dumps(config));config_file.chmod(0o600)
    environment.update(config)
    report('starting-private-server',port=4174)
    with (root/'web-server.log').open('ab') as log:
        process=subprocess.Popen([str(node),str(app/'server.mjs')],cwd=app,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    (root/'web-process.json').write_text(json.dumps({'pid':process.pid,'app':str(app),'node':str(node),'port':4174,'source_sha256':expected}))
    for attempt in range(100):
        if process.poll() is not None:raise RuntimeError('Private server exited; inspect web-server.log')
        try:
            with urllib.request.urlopen('http://127.0.0.1:4174/api/health',timeout=2) as response:
                if response.status==200:break
        except Exception:time.sleep(.2)
    else:raise RuntimeError('Private server health timeout')
    with urllib.request.urlopen('http://127.0.0.1:4174/api/account',timeout=3) as response:
        account=json.load(response);assert account['online'] and account['user'] is None
    try:urllib.request.urlopen('http://127.0.0.1:4174/api/kv?key=state',timeout=3);raise AssertionError('Anonymous library unexpectedly accessible')
    except urllib.error.HTTPError as error:assert error.code==401
    report('private-server-ready',port=4174,pid=process.pid,app=str(app),health=True,anonymous_library_blocked=True,sqlite_mode='DELETE / EXCLUSIVE / FULL',source_sha256=expected,public_endpoint=False,pdf_browser_ready=False,admin_setup_pending=True)
except Exception as error:report('failed',error=str(error));raise
'''
script=root/'install_web.py'
if (root/'web-status.json').exists():print(json.dumps({'existing_setup':json.loads((root/'web-status.json').read_text())}))
else:
    script.write_text(code)
    with (root/'install-web.log').open('ab') as log:
        process=subprocess.Popen([sys.executable,str(script)],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'setup_pid':process.pid,'scope':str(root),'worker_unchanged':True,'public_endpoint':False}))
