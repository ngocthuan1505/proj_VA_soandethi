import os, json, subprocess, sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root)
target=root/'mach_web'
target.mkdir(mode=0o700,exist_ok=True)
assert target.resolve().parent==root
setup=target/'install_node.py'
code=r'''import os, json, hashlib, tarfile, urllib.request, subprocess, shutil, ctypes.util, time
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root)
runtime=root/'.runtime';runtime.mkdir(exist_ok=True)
status=root/'setup-status.json'
def report(stage,**extra):
    temporary=root/'setup-status.tmp'
    temporary.write_text(json.dumps({'stage':stage,'updated':time.time(),**extra}))
    os.replace(temporary,status)
try:
    version='v24.22.0';name='node-'+version+'-linux-x64'
    executable=runtime/name/'bin/node'
    if not executable.exists():
        report('downloading-node')
        manifest=urllib.request.urlopen('https://nodejs.org/dist/'+version+'/SHASUMS256.txt',timeout=60).read().decode()
        expected=next(line.split()[0] for line in manifest.splitlines() if line.split()[-1]==name+'.tar.xz')
        archive=runtime/(name+'.tar.xz')
        digest=hashlib.sha256();received=0
        with urllib.request.urlopen('https://nodejs.org/dist/'+version+'/'+name+'.tar.xz',timeout=60) as response,archive.open('wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                received+=len(chunk)
                assert received<=100*1024*1024
                output.write(chunk);digest.update(chunk)
                report('downloading-node',bytes=received)
        assert digest.hexdigest()==expected,'Official Node checksum mismatch'
        report('extracting-node',bytes=received)
        with tarfile.open(archive) as tar:
            for entry in tar.getmembers():
                assert (runtime/entry.name).resolve().is_relative_to(runtime.resolve())
                if entry.issym():assert (runtime/entry.name).parent.joinpath(entry.linkname).resolve().is_relative_to(runtime.resolve())
                if entry.islnk():assert (runtime/entry.linkname).resolve().is_relative_to(runtime.resolve())
            tar.extractall(runtime)
        archive.unlink()
    result=subprocess.run([str(executable),'--version'],check=True,capture_output=True,text=True,timeout=20)
    report('node-ready',node=result.stdout.strip(),node_path=str(executable),browsers={n:shutil.which(n) for n in ['chromium','chromium-browser','google-chrome']},libraries={n:bool(ctypes.util.find_library(n)) for n in ['nss3','atk-1.0','X11','gbm','asound']},app_started=False,public_endpoint=False)
except Exception as error:
    report('failed',error=str(error));raise
'''
if (target/'setup-status.json').exists():
    print(json.dumps({'existing_setup':json.loads((target/'setup-status.json').read_text())}))
else:
    setup.write_text(code)
    with (target/'install-node.log').open('ab') as log:
        child=subprocess.Popen([sys.executable,str(setup)],cwd=target,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'installation_pid':child.pid,'scope':str(target),'worker_unchanged':True,'public_endpoint':False}))
