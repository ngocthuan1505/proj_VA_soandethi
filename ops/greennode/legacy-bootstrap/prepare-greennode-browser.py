import os,json,subprocess,sys
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root)
code=r'''import os,json,subprocess,time,signal
from pathlib import Path
root=Path('/network-volume/ProJ_VA/mach_web').resolve(strict=True)
assert root.parent==Path('/network-volume/ProJ_VA').resolve(strict=True)
os.chdir(root);os.umask(0o077);os.nice(5)
status=root/'browser-status.json'
def report(stage,**extra):
    temporary=root/'browser-status.tmp';temporary.write_text(json.dumps({'stage':stage,'updated':time.time(),**extra}));os.replace(temporary,status)
try:
    process=json.loads((root/'web-process.json').read_text());app=Path(process['app']);node=Path(process['node'])
    assert app.resolve().is_relative_to(root) and node.resolve().is_relative_to(root)
    runtime=root/'.runtime';browsers=runtime/'browsers';cache=runtime/'apt-cache';lists=runtime/'apt-lists';empty=runtime/'apt-empty';packages=runtime/'browser-packages';libs=runtime/'browser-libs'
    for folder in [cache/'archives/partial',lists/'partial',empty,packages,libs,runtime/'font-cache']:folder.mkdir(parents=True,exist_ok=True)
    (runtime/'apt.conf').touch(exist_ok=True)
    environment=os.environ.copy();environment.update({'PATH':str(node.parent)+os.pathsep+environment.get('PATH',''),'TMPDIR':str(runtime/'tmp'),'PLAYWRIGHT_BROWSERS_PATH':str(browsers)})
    report('downloading-browser')
    subprocess.run([str(node),str(app/'node_modules/playwright-core/cli.js'),'install','chromium','--only-shell'],cwd=app,env=environment,check=True,timeout=900)
    candidates=[p for name in ['chrome-headless-shell','headless_shell'] for p in browsers.rglob(name) if p.is_file() and os.access(p,os.X_OK)]
    assert candidates,'Cannot locate installed Chromium headless shell'
    browser=candidates[0]
    report('downloading-private-system-libraries')
    options=['-o','Dir::Etc::parts='+str(empty),'-o','Dir::Etc::main='+str(runtime/'apt.conf'),'-o','Dir::State::lists='+str(lists),'-o','Dir::Cache='+str(cache),'-o','Dir::State::extended_states='+str(runtime/'apt-extended-states'),'-o','Debug::NoLocking=1']
    subprocess.run(['apt-get',*options,'update'],cwd=packages,env=environment,check=True,timeout=300)
    required=['libnss3','libnspr4','libatk1.0-0','libatk-bridge2.0-0','libcups2','libdrm2','libxkbcommon0','libxcomposite1','libxdamage1','libxfixes3','libxrandr2','libxrender1','libxcb-randr0','libxi6','libgbm1','libpango-1.0-0','libcairo2','libatspi2.0-0','libwayland-server0','libdbus-1-3','libglib2.0-0','libfontconfig1','fonts-liberation','fonts-dejavu-core']
    subprocess.run(['apt-get',*options,'download',*required],cwd=packages,env=environment,check=True,timeout=300)
    for package in packages.glob('*.deb'):subprocess.run(['dpkg-deb','-x',str(package),str(libs)],check=True,timeout=30)
    library_path=os.pathsep.join(str(p) for p in [libs/'usr/lib/x86_64-linux-gnu',libs/'lib/x86_64-linux-gnu',libs/'usr/lib'] if p.exists())
    environment.update({'BROWSER_PATH':str(browser),'LD_LIBRARY_PATH':library_path})
    dependencies=subprocess.run(['ldd',str(browser)],env=environment,capture_output=True,text=True,timeout=20)
    assert 'not found' not in dependencies.stdout,dependencies.stdout
    fonts=runtime/'browser-fonts.conf';fonts.write_text('<fontconfig><dir>'+str(libs/'usr/share/fonts')+'</dir><dir>/usr/share/fonts</dir><cachedir>'+str(runtime/'font-cache')+'</cachedir></fontconfig>')
    environment['FONTCONFIG_FILE']=str(fonts)
    font_dir=libs/'usr/share/fonts/truetype/dejavu';assert font_dir.is_dir()
    preload=runtime/'canvas-fonts.mjs'
    preload.write_text("import {createRequire} from 'node:module';const require=createRequire("+json.dumps(str(app/'package.json'))+");const fonts=require('@napi-rs/canvas').GlobalFonts;if(!fonts.loadFontsFromDir(process.env.APP_FONT_DIR))throw Error('Private canvas fonts unavailable');")
    environment.update({'APP_FONT_DIR':str(font_dir),'NODE_OPTIONS':'--import='+str(preload)})
    report('testing-pdf-word-ocr')
    check="""import assert from 'node:assert/strict';import {sample} from './core.js';import {makePDF,makeDocx,closePDFBrowser} from './exports.mjs';import {extractFile,recognize} from './importers.mjs';import {dependency} from './runtime.mjs';try{const exam=sample('Toán'),pdf=await makePDF(exam,false,'https://mach-setup.invalid');assert.ok(pdf.subarray(0,5).toString()==='%PDF-');const parsed=await extractFile('fixture.pdf',pdf);assert.ok(parsed.pages.some(p=>p.text.includes('phương trình')));const docx=await makeDocx(exam,false);assert.ok(docx.length>1000);const {createCanvas}=dependency('@napi-rs/canvas'),canvas=createCanvas(1000,180),c=canvas.getContext('2d');c.fillStyle='#fff';c.fillRect(0,0,1000,180);c.fillStyle='#111';c.font='32px sans-serif';c.fillText('Câu 1. Tính 2 + 3 = 5.',35,70);const ocr=await recognize(canvas.toBuffer('image/png'));assert.ok(ocr.text.includes('2 + 3')||ocr.text.includes('2+3'));console.log(JSON.stringify({pdfBytes:pdf.length,pdfVietnameseText:true,wordBytes:docx.length,ocr:true}));}finally{await closePDFBrowser();}"""
    qa=app/'.data/deployment-check.mjs';qa.parent.mkdir(exist_ok=True);qa.write_text(check.replace("from './","from '../"))
    result=subprocess.run([str(node),str(qa)],cwd=app,env=environment,capture_output=True,text=True,timeout=180)
    if result.returncode:raise RuntimeError(result.stderr[-6000:])
    checks=json.loads(result.stdout.strip().splitlines()[-1])
    private=json.loads((root/'private-runtime.json').read_text());private.update({'BROWSER_PATH':str(browser),'LD_LIBRARY_PATH':library_path,'PLAYWRIGHT_BROWSERS_PATH':str(browsers),'FONTCONFIG_FILE':str(fonts),'APP_FONT_DIR':str(font_dir),'NODE_OPTIONS':'--import='+str(preload)})
    temporary=root/'private-runtime.tmp';temporary.write_text(json.dumps(private));os.replace(temporary,root/'private-runtime.json')
    pid=process['pid'];cmdline=Path('/proc/'+str(pid)+'/cmdline').read_bytes();assert str(app/'server.mjs').encode() in cmdline
    os.kill(pid,signal.SIGTERM)
    for attempt in range(100):
        try:
            if Path('/proc/'+str(pid)+'/stat').read_text().split(') ',1)[1].startswith('Z '):break
        except FileNotFoundError:break
        try:os.kill(pid,0)
        except ProcessLookupError:break
        time.sleep(.2)
    else:raise RuntimeError('Old private server did not stop; no second server started')
    environment.update(private)
    with (root/'web-server.log').open('ab') as log:new=subprocess.Popen([str(node),str(app/'server.mjs')],cwd=app,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    process['pid']=new.pid;(root/'web-process.json').write_text(json.dumps(process))
    import urllib.request
    for attempt in range(100):
        if new.poll() is not None:raise RuntimeError('Restarted private server exited')
        try:
            with urllib.request.urlopen('http://127.0.0.1:4174/api/health',timeout=2) as response:
                if response.status==200:break
        except Exception:time.sleep(.2)
    else:raise RuntimeError('Restarted private server health timeout')
    web=json.loads((root/'web-status.json').read_text());web.update({'pid':new.pid,'pdf_browser_ready':True,'linux_checks':checks,'updated':time.time()});(root/'web-status.json').write_text(json.dumps(web))
    report('browser-ready',checks=checks,private_app_health=True,public_endpoint=False)
except Exception as error:report('failed',error=str(error));raise
'''
script=root/'install_browser.py'
if (root/'browser-status.json').exists() and json.loads((root/'browser-status.json').read_text())['stage']!='failed':print(json.dumps({'existing_setup':json.loads((root/'browser-status.json').read_text())}))
else:
    script.write_text(code)
    with (root/'install-browser.log').open('ab') as log:process=subprocess.Popen([sys.executable,str(script)],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print(json.dumps({'setup_pid':process.pid,'scope':str(root),'worker_unchanged':True,'public_endpoint':False}))
