import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import {blank} from '../core.js';

const api=process.env.POC_URL||'http://127.0.0.1:4182';
const output=path.resolve(process.argv[2]||'outputs/kiem-ui-poc');
const runReal=process.argv.includes('--run-real');
await fs.mkdir(output,{recursive:true});
async function request(url,options={}){
 const r=await fetch(api+url,{...options,headers:{Origin:api,'Content-Type':'application/json',...options.headers}});
 assert(r.ok,await r.clone().text());return r.json();
}
const info=await request('/api/status');
assert.equal(info.matrixAgent,true);
const job=JSON.parse(await fs.readFile(new URL('../backend/poc-data/thu-vien.json',import.meta.url),'utf8'));
const before=await request('/api/kv?key=state');
const exam=blank('Ngữ văn',[]);
exam.title='PoC · Thư viện · ngữ liệu tự viết';exam.grade='6';
exam.matrix=[{topic:'Chi tiết trong ngữ liệu',targets:[1,1,0]},{topic:'Ý nghĩa hành động',targets:[1,1,0]}];
exam.matrixConfirmed=true;
exam.docs=[{id:job.sources[0].sourceId,kind:'text',version:1,name:'Ngữ liệu tự viết để thử PoC',text:job.sources[0].text,pages:[{number:1,text:job.sources[0].text}]}];
exam.assistantSources=[job.sources[0].sourceId];
const state=before.value||{version:1,exams:[],prefs:[]};
state.exams.push(exam);state.current=exam.id;
await request('/api/kv',{method:'PUT',headers:{'If-Match':String(before.revision)},body:JSON.stringify({key:'state',value:state})});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(api);await page.waitForLoadState('networkidle');
 await page.screenshot({path:path.join(output,'01-ban-soan.png'),fullPage:true});
 await page.locator('[data-action="menu"][data-menu="view"]').click();
 await page.locator('[data-action="matrix"]').first().click();
 await page.getByRole('button',{name:'Sinh theo ma trận · Python'}).click();
 await page.locator('#matrix-source-text').waitFor();
 assert.equal(await page.locator('#matrix-source-text').inputValue(),job.sources[0].text);
 assert.equal(await page.locator('#matrix-confirm-save').isDisabled(),true);
 assert((await page.locator('.matrix-chat-session').innerText()).includes('ngân sách'));
 await page.screenshot({path:path.join(output,'02-yeu-cau-agent.png'),fullPage:true});
 let realResult=null;
 if(runReal){
  await page.locator('#matrix-consent').check();
  const response=page.waitForResponse(r=>r.url().endsWith('/proposals/generate')&&r.request().method()==='POST');
  const started=performance.now();
  await page.locator('#matrix-start').click();
  const submission=await (await response).json();
  assert.equal(submission.status,'running');
  const base='/api/exams/'+exam.id+'/proposals/'+submission.jobId;
  await fs.writeFile(path.join(output,'submission.json'),JSON.stringify(submission,null,2));
  let result;
  for(let i=0;i<960;i++){
   result=await request(base+'/status');
   if(result.status!=='running')break;
   await new Promise(resolve=>setTimeout(resolve,1000));
  }
  assert.notEqual(result.status,'running');
  await page.waitForFunction(()=>document.querySelector('#matrix-start')?.disabled===false);
  await page.screenshot({path:path.join(output,'03-ket-qua-app-that.png'),fullPage:true});
  const trace=await request(base+'/trace');
  const saved=await request('/api/kv?key=state');
  const current=saved.value.exams.find(e=>e.id===exam.id);
  assert.equal(current.questions.length,0);
  assert.equal(current.revision,exam.revision);
  await fs.writeFile(path.join(output,'app-real-result.json'),JSON.stringify({model:info.model,mode:'real_local_model',seconds:(performance.now()-started)/1000,job:result,trace,savedQuestionCount:current.questions.length,revision:current.revision,teacherConfirmed:false},null,2));
  realResult=result;
 }
 assert.deepEqual(errors,[]);
 await fs.writeFile(path.join(output,'ui-result.json'),JSON.stringify({status:'ui_checks_passed',url:api,examId:exam.id,modelCalled:runReal,generationStatus:realResult?.status||'not_started',checks:['Bàn soạn hiện có','Nguồn tự viết đúng nguyên văn','Ma trận 4 câu','Giới hạn ngân sách hiển thị','Chưa cho lưu trước kết quả'],pageErrors:errors},null,2));
 console.log(JSON.stringify({status:'ui_checks_passed',examId:exam.id,modelCalled:runReal,generationStatus:realResult?.status||'not_started',output}));
}finally{await browser.close();}
