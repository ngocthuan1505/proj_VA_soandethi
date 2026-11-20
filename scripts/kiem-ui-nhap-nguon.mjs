import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright-core';

const base=process.env.POC_URL||'http://127.0.0.1:4183';
const out=path.resolve(process.argv[2]||'outputs/qa-nhap-nguon');
assert((await (await fetch(base+'/api/status')).json()).fixture);
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage({viewport:{width:1366,height:830}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 page.setDefaultTimeout(10000);
 await page.goto(base);
 await page.waitForLoadState('networkidle');
 // Chờ lần lưu ID khối của đề mẫu để mốc so sánh chỉ đo thao tác nhập tệp.
 await page.waitForFunction(async()=>{
  const response=await fetch('/api/kv?key=state');
  if(!response.ok)return false;
  const {value}=await response.json();
  const current=value?.exams?.find(e=>e.id===value.current);
  return current?.blockIds?.heading&&current.questions.every(q=>q.blockIds?.stem);
 },undefined,{polling:150});
 const snapshot=async()=>{const response=await page.request.get(base+'/api/kv?key=state');assert(response.ok());return response.json();};
 const chooser=async()=>{
  await page.getByRole('button',{name:'Tệp',exact:true}).click();
  await page.getByRole('menuitem',{name:'Thêm tài liệu',exact:true}).click();
  return page.locator('#mvp-file');
 };
 const resultFor=()=>page.waitForResponse(r=>r.url()===base+'/api/extract'&&r.request().method()==='POST');
 const before=await snapshot();
 const broken=await chooser();
 const rejected=resultFor();
 await broken.setInputFiles({name:'anh-hong.png',mimeType:'image/png',buffer:Buffer.from('Tep QA khong phai anh')});
 const bad=await rejected;
 assert.equal(bad.status(),409);
 assert.equal((await bad.json()).code,'invalid_document');
 assert.deepEqual(await snapshot(),before);
 assert.equal(await page.locator('#source-ocr-form').count(),0);
 await page.keyboard.press('Escape');

 const pdf=path.join(out,'nguon-2-trang.pdf');
 const upload=await chooser();
 const extracted=resultFor();
 const saved=page.waitForResponse(r=>{
  if(r.url()!==base+'/api/kv'||r.request().method()!=='PUT'||!r.ok())return false;
  const body=r.request().postDataJSON();
  return body.key==='state'&&body.value.exams.some(e=>e.docs.some(d=>d.name==='nguon-2-trang.pdf'));
 });
 await upload.setInputFiles(pdf);
 const valid=await extracted;
 assert(valid.ok(),await valid.text());
 const content=await valid.json();
 assert.equal(content.sentToAI,false);
 assert.deepEqual(content.pages.map(p=>[p.number,p.text.trim()]),[[1,'Nguon trang mot'],[2,'Nguon trang hai']]);
 await page.locator('#source-page').selectOption('2');
 assert.match(await page.locator('#source-text-form[data-page="2"] textarea').inputValue(),/Nguon trang hai/);
 await saved;
 await page.screenshot({path:path.join(out,'trang-2.png')});
 const kept=await snapshot();
 const doc=kept.value.exams.find(e=>e.id===kept.value.current).docs.find(d=>d.name==='nguon-2-trang.pdf');
 assert(doc?.id && doc.fileId);
 assert.equal(doc.version,1);
 assert.deepEqual(doc.pages.map(p=>p.number),[1,2]);
 const original=await page.request.get(base+'/api/source-file/'+doc.fileId);
 assert(original.ok());
 const originalBytes=await fs.readFile(pdf);
 assert.deepEqual(await original.body(),originalBytes);
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify({
  fixture:true,scenario:'IT-02',badImageRejectedBeforeConsent:true,noFailedSave:true,
  pdfPages:[1,2],sourceVersion:doc.version,originalSha256:createHash('sha256').update(originalBytes).digest('hex'),
  matchesOriginal:true,pageErrors:errors,sentToAI:false,
 },null,2));
} finally {
 await browser.close();
}
