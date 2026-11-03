import json,subprocess,sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
code=r'''import json,tarfile,urllib.request,subprocess,os,time
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root);os.umask(0o077)
status=root/'tunnel-status.json'
def report(stage,**extra):
    temporary=root/'tunnel-status.tmp';temporary.write_text(json.dumps({'stage':stage,'updated':time.time(),**extra}));os.replace(temporary,status)
try:
    binary=root/'.runtime/ngrok'
    if not binary.exists():
        report('downloading-agent')
        archive=root/'.runtime/ngrok.tgz'
        with urllib.request.urlopen('https://bin.ngrok.com/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz',timeout=60) as response,archive.open('wb') as output:
            received=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                received+=len(chunk);assert received<=100*1024*1024;output.write(chunk)
        with tarfile.open(archive) as tar:
            entry=tar.getmember('ngrok');assert entry.isfile() and entry.size<=150*1024*1024
            with tar.extractfile(entry) as source,binary.open('wb') as output:
                import shutil;shutil.copyfileobj(source,output)
        binary.chmod(0o700);archive.unlink()
    version=subprocess.run([str(binary),'version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
    help_text=subprocess.run([str(binary),'http','--help'],capture_output=True,text=True,check=True,timeout=10).stdout
    assert '--url' in help_text and '--inspect' in help_text
    report('agent-ready',version=version,public_endpoint=False,token_loaded=False)
except Exception as error:report('failed',error=str(error));raise
'''
script=root/'install_tunnel.py'
if (root/'tunnel-status.json').exists():print(json.dumps({'existing_setup':json.loads((root/'tunnel-status.json').read_text())}))
else:
    script.write_text(code)
    with (root/'install-tunnel.log').open('ab') as log:process=subprocess.Popen([sys.executable,str(script)],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'setup_pid':process.pid,'public_endpoint':False,'token_loaded':False}))
